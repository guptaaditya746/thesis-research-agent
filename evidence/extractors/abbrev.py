"""`abbrev_condition` and `abbrev_metric`: names a paper defines for itself ("fact-level accuracy (FLA)").

`definitions` finds "Long Form (LF)" and "LF (Long Form)" where the short form's letters are, in order, the
initials of the long form's words (the parts of a hyphenated word count as words; "of", "the" and similar may
be left out). It also reads phrase definitions ("hallucination rate, abbreviated HR", "the vanilla LLM, denoted
by the code B", "hereafter CB", "FLA for short"); a one-letter code only with the "code" wording, and a code
names a condition, never a metric. The two extractors then find every use of such a short form whose long form names a protocol
term (the terms the regex extractors use, from the config: the domain pack's words or the protocol's): "FLA" in a table header is the metric
"fact-level accuracy". The item's name is the long form, its role or canonical comes from the term found in the
long form, and its spans are on the short forms. A definition anywhere in the document is used inside whatever
parts the task allows. Own module, so every existing extractor keeps its id.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..contract import ExtractionResult, ExtractionTask, ExtractorSpec, Item, RunContext
from . import base, regex, terms

VERSION = 1
SOURCES = (base.HERE / "abbrev.py", base.HERE / "regex.py", base.HERE / "terms.py", *base.SHARED_SOURCES)   # regex.py: INJECTED
CODE_SHA256 = base.source_sha256(*SOURCES)

STOP = frozenset({"of", "the", "and", "for", "in", "on", "to", "a", "an", "with"})
WORD = re.compile(r"[A-Za-z0-9]+")
SHORT = r"[A-Z][A-Za-z0-9+]{1,7}"
AFTER_LONG = re.compile(r"\(\s*(" + SHORT + r")\s*\)")                        # "long form (LF)"
BEFORE_LONG = re.compile(r"(?<![\w-])(" + SHORT + r")\s*\(([^()\n]{3,80})\)")  # "LF (long form)"
BREAK = re.compile(r"[.;:!?\n|()]")
MAX_WORDS = 8
# a long form that ends in a measure noun, and names no known term, is an "other" metric
METRIC_NOUN = re.compile(r"(?i)\b(?:rate|score|ratio|frequency|error|accuracy|latency|time)\s*$")


@dataclass(frozen=True)
class Definition:
    long: str
    short: str
    start: int   # the whole definition, "long (short)" or "short (long)", at raw offsets
    end: int
    subject: bool = False   # `long` is a clause whose term is the name ("The X is prompted ..., and it is denoted B")
    code: bool = False      # "denoted by the code B": a condition's code, never a metric's short form


def _initials(words: list[re.Match[str]], letters: str) -> int | None:
    """How many of the last words spell `letters` (stop words may be skipped), or None."""
    i, taken = len(letters), 0
    for w in reversed(words):
        if i == 0:
            break
        taken += 1
        if w.group()[0].lower() == letters[i - 1]:
            i -= 1
        elif w.group().lower() not in STOP:
            return None
    return taken if i == 0 and words[len(words) - taken].group()[0].lower() == letters[0] else None


def _letters(short: str) -> str:
    return "".join(c for c in short if c.isalnum()).lower()


def definitions(text: str) -> list[Definition]:
    """The "Long Form (LF)" and "LF (Long Form)" definitions in `text`, and the phrase definitions ("long form,
    abbreviated LF", "denoted by the code B", PHRASES), in document order."""
    found: list[Definition] = []
    for m in AFTER_LONG.finditer(text):
        letters = _letters(m.group(1))
        cuts = [b.end() for b in BREAK.finditer(text, max(0, m.start() - 200), m.start())]
        words = list(WORD.finditer(text, cuts[-1] if cuts else max(0, m.start() - 200), m.start()))[-MAX_WORDS:]
        taken = _initials(words, letters) if words else None
        if taken:
            first = words[len(words) - taken]
            found.append(Definition(text[first.start():words[-1].end()], m.group(1), first.start(), m.end()))
    for m in BEFORE_LONG.finditer(text):
        long = m.group(2).strip()
        words = list(WORD.finditer(long))
        if words and _initials(words, _letters(m.group(1))) == len(words):
            found.append(Definition(long, m.group(1), m.start(), m.end()))
    found += _phrased(text)
    return sorted(set(found), key=lambda d: (d.start, d.end))


# Phrase definitions, as the synthetic "distributed" papers write them (synth/render_llm.py): "<long>, abbreviated
# HR", "<long> (abbreviated HR)", "<long>, denoted (by its/the code) B", "<long>, hereafter CB", "<long>, or FLA for
# short". A one-letter short form only with the explicit "code" wording, never as an ordinary letter.
PHRASES = [
    re.compile(r"(?:\s*,)?\s*(?:\(\s*)?(?:is\s+)?abbreviated\s+(?:as\s+)?(" + SHORT + r")\b(?:\s*\))?"),
    re.compile(r"(?:\s*,)?\s*(?:is\s+)?denoted\s+by\s+(?:its|the)\s+code\s+([A-Z][A-Za-z0-9+]{0,7})\b"),
    re.compile(r"(?:\s*,)?\s*(?:is\s+)?denoted\s+(?:as\s+)?(?!by\b)(" + SHORT + r")\b"),
    re.compile(r"(?:\s*,)?\s*hereafter\s+(?:called\s+)?(" + SHORT + r")\b"),
    re.compile(r"(?:\s*,\s*or|\s*\()\s*(" + SHORT + r")\s+for\s+short\b(?:\s*\))?"),
]
CLAUSE_START = re.compile(r"[.!?;:\n]\s*")
# words between the long form and the phrase: "the vanilla LLM, which is denoted"; "and"/"it" mean the phrase
# speaks of the sentence's subject ("..., and is denoted by its code R")
TRAILING = re.compile(r"(?i)(?:[\s,(]+|\b(?:which|that|it|is|are|was|and|also)\b)+$")
CUT = re.compile(r"(?i)^.*(?:,|\(|:|\b(?:is|are|was|with|as|called|on|of|for|reports?|uses?|runs?|measures?|"
                 r"evaluates?|compares?)\b)\s*")
LEADING = re.compile(r"(?i)(?:(?:the|a|an|its|our|this)\s+)*(?:(?:metric|measure|outcome|score)\s+)?")


def _phrased(text: str) -> list[Definition]:
    found = []
    for n, rx in enumerate(PHRASES):
        for m in rx.finditer(text):
            cuts = [c.end() for c in CLAUSE_START.finditer(text, max(0, m.start() - 400), m.start())]
            begin = cuts[-1] if cuts else max(0, m.start() - 400)
            window = text[begin:m.start()]
            tail = TRAILING.search(window)
            head = window[:tail.start()] if tail else window
            if tail and re.search(r"(?i)\b(?:and|it)\b", tail.group()):
                found += _subject(text, m, code=n == 1)
                continue
            words = list(WORD.finditer(head))[-MAX_WORDS:]
            taken = _initials(words, _letters(m.group(1))) if words and len(m.group(1)) > 1 else None
            if taken:   # the short form spells the last words' initials: those words are the long form
                first = words[len(words) - taken]
                long, offset = " ".join(head[first.start():words[-1].end()].split()), first.start()
            else:
                long, offset = _noun_phrase(head)
            if long:
                found.append(Definition(long, m.group(1), begin + offset, m.end(), code=n == 1))
    return found


SENTENCE_START = re.compile(r"[.!?\n]\s*")
SUBJECT_END = re.compile(r"(?i),\s*which\b|;|,\s*and\b|\band\s+it\b|\bwhich\b")


def _subject(text: str, m: re.Match[str], *, code: bool) -> list[Definition]:
    """"The vanilla LLM is prompted with the question, and it is denoted by the code B": the phrase speaks of the
    sentence's subject. The long form is the sentence up to its first clause break ("which", "; ", ", and"),
    marked `subject`: the item takes the term found in it as its name (Abbrev.named)."""
    cuts = [c.end() for c in SENTENCE_START.finditer(text, max(0, m.start() - 400), m.start())]
    begin = cuts[-1] if cuts else max(0, m.start() - 400)
    stop = SUBJECT_END.search(text, begin, m.start())
    clause = text[begin:stop.start() if stop else m.start()]
    lead = LEADING.match(clause)
    start = lead.end() if lead else 0
    words = list(WORD.finditer(clause, start))[:2 * MAX_WORDS]
    if not words:
        return []
    long = " ".join(clause[start:words[-1].end()].split())
    return [Definition(long, m.group(1), begin + start, m.end(), subject=True, code=code)]


def _noun_phrase(head: str) -> tuple[str, int]:
    """The noun phrase that ends `head` (after its last comma, verb or bracket, without articles), with its offset."""
    cut = CUT.match(head)
    start = cut.end() if cut else 0
    lead = LEADING.match(head, start)
    start = lead.end() if lead else start
    long = head[start:].strip()
    if not long or len(WORD.findall(long)) > MAX_WORDS or not long[0].isalnum():
        return "", 0
    return " ".join(long.split()), start


class Abbrev:
    """Common shape: a definition whose long form holds a term becomes one item with a span per use."""
    evidence_type: str = ""
    name: str = ""

    def __init__(self, config: dict[str, Any]) -> None:
        self.given = {k: v for k, v in config.items() if k in regex.INJECTED}
        self.patterns = self.default_patterns() | {k: v for k, v in config.items() if k not in regex.INJECTED}
        self.spec = ExtractorSpec(name=self.name, version=VERSION, kind="regex", evidence_types=(self.evidence_type,),  # type: ignore[arg-type]
                                  code_sha256=CODE_SHA256, config={**self.given, **self.patterns}, determinism="exact")

    def default_patterns(self) -> dict[str, Any]:
        return {"max_spans": 8}

    def extract(self, task: ExtractionTask, ctx: RunContext) -> ExtractionResult:
        text = ctx.text()
        parts = base.ranges(task, text)
        role = "condition_label" if self.evidence_type == "condition" else "metric_label"
        found = []
        for long, short, mention in self.named(text):
            use = re.compile(rf"(?<![\w-]){re.escape(short)}(?![\w-])")
            uses = [(u.start(), u.end()) for a, b in parts for u in use.finditer(text, a, b)]
            if uses:
                spans = [base.span(task, text, s, e, role) for s, e in uses[: self.patterns["max_spans"]]]
                found.append((self.fields(long, mention), {}, spans))
        items: list[Item] = base.group(self.evidence_type, found)
        return ExtractionResult(extractor_id=self.spec.extractor_id, task_sha256=task.task_sha256, status="ok",
                                items=tuple(items), coverage=base.coverage(parts, items)).canonical()

    def named(self, text: str) -> list[tuple[str, str, terms.Mention]]:
        """(long form, short form, term found in the long form) for each definition that names a term."""
        out: dict[tuple[str, str], terms.Mention] = {}
        for d in definitions(text):
            if d.code and self.evidence_type != "condition":
                continue   # "denoted by the code R" names a condition, whatever its clause mentions
            mention = self.term(d.long)
            if mention is not None:
                long = mention.text if d.subject else d.long   # a subject clause: the term in it is the name
                out.setdefault((" ".join(long.split()), d.short), mention)
        return [(long, short, m) for (long, short), m in out.items()]

    def term(self, long: str) -> terms.Mention | None:
        raise NotImplementedError

    def fields(self, long: str, mention: terms.Mention) -> dict[str, Any]:
        raise NotImplementedError


class AbbrevCondition(Abbrev):
    evidence_type, name = "condition", "abbrev_condition"

    def term(self, long: str) -> terms.Mention | None:
        enum = self.given.get("field_schema", {}).get("properties", {}).get("role", {}).get("enum")
        roles = list(enum or self.patterns["conditions"])
        treatment = (self.given.get("compare") or {}).get("treatment")
        mentions = terms.find_conditions(long, terms.condition_patterns(self.patterns["conditions"]), roles,
                                         treatment=treatment, not_a_system=self.patterns["not_a_system"])
        return mentions[0] if mentions else None

    def fields(self, long: str, mention: terms.Mention) -> dict[str, Any]:
        return {"label": long, "role": mention.key}


class AbbrevMetric(Abbrev):
    evidence_type, name = "metric", "abbrev_metric"

    def term(self, long: str) -> terms.Mention | None:
        found = terms.find_all(long, [tuple(m) for m in self.patterns["metrics"]])  # type: ignore[misc]
        if found:
            return found[0]
        # wording the metric patterns lack, consulted after them ("unsupported-answer rate"; pack metric_supplement)
        for pattern, canonical, higher in self.patterns["supplement"]:
            if re.search(pattern, long):
                return terms.Mention(0, len(long), canonical, long, higher)
        enum = self.given.get("field_schema", {}).get("properties", {}).get("canonical", {}).get("enum")
        if METRIC_NOUN.search(long) and (enum is None or "other" in enum):
            return terms.Mention(0, len(long), "other", long, True)
        return None

    def fields(self, long: str, mention: terms.Mention) -> dict[str, Any]:
        return {"name": long, "canonical": mention.key, "higher_is_better": mention.higher_is_better}


FACTORIES = {"abbrev_condition": AbbrevCondition, "abbrev_metric": AbbrevMetric}
