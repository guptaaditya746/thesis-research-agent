"""Rewording of benchmark questions: the only LLM step of the question generator (bench.py).

Code writes every question from a template and keeps the slots it states (drug, comparator, dose, time point, patient
group, measure). The LLM only rewords that text so the set does not read like one template. Three separate checks:

  1. generate  one call (REWORD prompt) proposes a wording from the template and the phrases to keep;
  2. code      `check()` rejects a wording that drops a slot, adds a number, a drug or a gold value, or hints at the
               answer ("not reported");
  3. verify    a second, blind call (VERIFY prompt) sees only the template and the wording and says whether they ask
               for the same thing. It never sees the generator's output reasons.

A failed attempt goes to one repair call with only the template, the rejected wording and the failed checks; at most
`ATTEMPTS` attempts, each kept. When none passes, the template text stays (source "template").
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from evqa import llm

ATTEMPTS = 3
MAX_WORDS = 35
BANNED = ("not reported", "unreported", "no data", "no study", "no studies", "no paper", "no trial", "never been",
          "isn't reported", "is not known", "unknown", "if any")
STOP = {"with", "on", "the", "of", "and", "in", "a", "an", "to", "for", "who", "at", "by", "or"}

REWORD_SCHEMA = {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"],
                 "additionalProperties": False}
VERIFY_SCHEMA = {"type": "object", "properties": {"same": {"type": "boolean"},
                                                  "difference": {"type": ["string", "null"]}},
                 "required": ["same", "difference"], "additionalProperties": False}

REWORD = """Task: reword one question about clinical trial results so it reads like a question a doctor would type.
Keep its meaning exactly.

Input fields:
- template: the question written by code. It is correct but stiff.
- keep: phrases that must appear in your question, spelled exactly as given (drug names, doses, time points,
  patient groups, what is measured).
- failed: only on a repair; the checks your last wording failed. Fix exactly these.

Output: {"question": "<one question>"}. One sentence ending with "?", at most 30 words.
Rules:
- Use every phrase in keep, spelled the same.
- Ask for the same thing as the template: the same drugs, comparator, dose, time point, patient group and measure,
  and the same kind of answer (one value, a list of studies, the best option, a trend, a comparison).
- Add no number, drug, dose, time point or patient group that the template does not state, and no answer.
- When the template leaves something out (no dose, no time point), leave it out too.

Examples:
input: {"template": "How much does brenoxalin 20 mg change HbA1c?", "keep": ["brenoxalin", "20 mg", "HbA1c"]}
output: {"question": "What change in HbA1c is seen with brenoxalin 20 mg?"}

input (a modifier in the group must stay; "type 2" is part of the group, not a value):
{"template": "How much does kavolemin change body weight in elderly adults with type 2 diabetes on metformin?",
 "keep": ["kavolemin", "body weight", "elderly adults with type 2 diabetes on metformin"]}
output: {"question": "In elderly adults with type 2 diabetes on metformin, how does kavolemin affect body weight?"}

input (nothing about dose or time is stated, so none is added):
{"template": "Which studies tested veloranide?", "keep": ["veloranide"]}
output: {"question": "Which trials have looked at veloranide?"}"""

VERIFY = """Task: decide whether two questions ask for exactly the same information.

Input fields:
- original: a question about clinical trial results.
- candidate: another wording of it.

Output: {"same": true or false, "difference": "<the first thing that differs, a few words>" or null when same}.
Same means: the same drugs, comparator, dose, time point, patient group and measure, and the same kind of answer
(one value, a list of studies, the best option, a trend, a comparison). Word order and plain synonyms do not matter.

Examples:
input: {"original": "How much does brenoxalin 20 mg change HbA1c?",
        "candidate": "What change in HbA1c is seen with brenoxalin 20 mg?"}
output: {"same": true, "difference": null}

input (a dropped modifier changes the patients):
{"original": "How much does kavolemin change body weight in elderly adults with type 2 diabetes on metformin?",
 "candidate": "How much does kavolemin change body weight in adults with type 2 diabetes on metformin?"}
output: {"same": false, "difference": "elderly dropped from the patient group"}

input (a dropped time point):
{"original": "How much does brenoxalin change HbA1c at 52 weeks?",
 "candidate": "How much does brenoxalin change HbA1c?"}
output: {"same": false, "difference": "the 52-week time point is missing"}"""


def prompt_sha() -> str:
    return hashlib.sha256((REWORD + "\n----\n" + VERIFY).encode()).hexdigest()


# ---------- what must be kept ----------

@dataclass(frozen=True)
class Keep:
    """One thing the wording must keep. kind: name | measure | group | phrase | a setting slot (dose, week, ...)."""
    kind: str
    text: str                                # shown to the model
    forms: tuple[str, ...] = ()              # measure: other accepted wordings (alt labels)
    pattern: str = ""                        # a setting: the blueprint's mention regex, {n} = the number


@dataclass
class Task:
    """One question to reword: the template, what to keep, and what must not appear."""
    qid: str
    template: str
    keep: list[Keep]
    values: list[str] = field(default_factory=list)      # gold values (numbers) that must not leak
    other_names: list[str] = field(default_factory=list)  # drug names the question does not mention


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower().replace("-", " "))


def _numbers(text: str) -> set[str]:
    return {n.rstrip(".") for n in re.findall(r"\d+(?:\.\d+)?", text)}


def _has_name(text: str, name: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(name.lower())}(?![a-z])", text.lower()) is not None


def _content(text: str) -> list[str]:
    return [w for w in _words(text) if w not in STOP]


def _has_all_words(text: str, phrase: str) -> bool:
    have = set(_words(text))
    return all(w in have for w in _content(phrase))


def keeps(k: Keep, text: str) -> bool:
    """Does the wording `text` keep this slot?"""
    low = text.lower()
    if k.kind == "name":
        return _has_name(low, k.text)
    if k.pattern:   # a setting value, as the blueprint says it may be written
        return re.search(k.pattern.replace("{n}", re.escape(k.text.split()[0])), low) is not None
    # Kept for Keep()s made without a pattern (older callers, tests): the medical dose and week forms.
    if k.kind == "dose":
        num = re.escape(k.text.split()[0])
        return re.search(rf"(?<![\d.]){num}\s*-?\s*mg\b", low) is not None
    if k.kind == "week":
        num = re.escape(k.text.split()[0])
        return re.search(rf"(?<![\d.]){num}\s*-?\s*(weeks?|wk)\b|\bweek\s+{num}(?![\d.])", low) is not None
    if k.kind == "measure":
        return any(_has_all_words(low, f) for f in (k.text, *k.forms))
    return _has_all_words(low, k.text)   # group, phrase: every content word (modifiers and "no"/"not" included)


def check(task: Task, text: str) -> list[str]:
    """Code check of one wording. [] = passed; else one short reason per failed rule."""
    problems = []
    t = (text or "").strip()
    if not t.endswith("?") or "\n" in t or "{" in t or "}" in t:
        problems.append("must be one line ending with '?'")
    if len(t.split()) > MAX_WORDS:
        problems.append(f"longer than {MAX_WORDS} words")
    for k in task.keep:
        if not keeps(k, t):
            problems.append(f"drops {k.kind} {k.text!r}")
    extra = _numbers(t) - _numbers(task.template)
    leaked = sorted(v for v in extra if any(v == x.lstrip("-") for x in task.values))
    if leaked:
        problems.append(f"leaks gold value(s) {leaked}")
    if extra - set(leaked):
        problems.append(f"adds number(s) {sorted(extra - set(leaked))}")
    added = [n for n in task.other_names if _has_name(t, n) and not _has_name(task.template, n)]
    if added:
        problems.append(f"adds drug(s) {added}")
    hint = [b for b in BANNED if b in t.lower() and b not in task.template.lower()]
    if hint:
        problems.append(f"hints at the answer ({', '.join(hint)})")
    return problems


# ---------- the calls ----------

def _reword_user(task: Task, rejected: str | None = None, failed: list[str] | None = None) -> str:
    body: dict[str, Any] = {"template": task.template, "keep": [k.text for k in task.keep]}
    if rejected is not None:
        body.update(rejected=rejected, failed=failed or [])
    return json.dumps(body, ensure_ascii=False)


def reword_one(gen: Any, ver: Any, task: Task) -> dict[str, Any]:
    """Generate -> code check -> blind verify, with bounded repairs. Returns the wording record of the question."""
    attempts: list[dict[str, Any]] = []
    rejected: str | None = None
    failed: list[str] | None = None
    for i in range(ATTEMPTS):
        out = llm.call(gen, REWORD, _reword_user(task, rejected, failed), REWORD_SCHEMA, step="seed.bench.reword")
        text = str(out.get("question", "")).strip()
        problems = check(task, text)
        verdict = None
        if not problems:
            verdict = llm.call(ver, VERIFY, json.dumps({"original": task.template, "candidate": text},
                                                       ensure_ascii=False), VERIFY_SCHEMA, step="seed.bench.verify")
            if not verdict.get("same"):
                problems = [f"verifier: {verdict.get('difference') or 'not the same question'}"]
        attempts.append({"attempt": i + 1, "text": text, "problems": problems, "verifier": verdict})
        if not problems:
            return {"template": task.template, "source": "llm", "text": text, "attempts": attempts}
        rejected, failed = text, problems
    return {"template": task.template, "source": "template", "text": task.template, "attempts": attempts}


def reword_all(gen: Any, ver: Any, tasks: list[Task]) -> dict[str, dict[str, Any]]:
    """qid -> wording record; at most llm.MAX_WORKERS (3) questions at once."""
    done = llm.pmap(lambda t: reword_one(gen, ver, t), tasks)
    return {t.qid: w for t, w in zip(tasks, done, strict=True)}


def template_only(tasks: list[Task]) -> dict[str, dict[str, Any]]:
    """No LLM (dry run): every question keeps its template text."""
    return {t.qid: {"template": t.template, "source": "template", "text": t.template, "attempts": []} for t in tasks}
