"""LLM judge (plan "Judge": C2 for scoring, D, and the web app, E), calibrated against people.

API (contract in docs/e2e-build-plan.md):
- `support(fact, quote, *, context=None) -> Verdict`, Verdict = `{label: supports | partial | no,
  rationale, model, prompt_sha256, cached}`: does the quote support the fact?
- `same_fact(run_fact, key_fact, concept) -> {match, rationale, model, prompt_sha256, cached}`: soft
  fact matching;
- `same_row(run_row, key_row, concept) -> {match, ...}`: row matching when cells differ in wording.
The module functions use a default `Judge` over $GOLD and the LiteLLM sub-models; `Judge` has the same
calls plus async twins (`asupport`, ...) and `gather` to run many with bounded concurrency.

Calls go through gold/llm.py: pydantic-ai, the reply decoded under the output's JSON schema (rationale
first, then the label), temperature 0, seed 0, thinking off, round robin over sub-model-1/-2. Both
replicas serve the same weights, so the model identity is the pinned name and revision, not the alias.
Every result is cached in $GOLD/judge-cache.jsonl (llm.JsonlCache), keyed by sha256 of the canonical
input, the model identity, the prompt hash and the settings: a rescore costs no model call, and a changed
prompt or model never reuses an old answer. `Judge(cache_only=True)` never calls a model and returns None
for an input it has not seen (pending), so the web app can read verdicts without spending tokens. The
prompts are gold/prompts/judge-*.txt; a verdict records its prompt_sha256 (llm.prompt_sha256 of the text
and the output schema).

Context: the calibration judges each quote with `context_for(...)`, the paper id and CONTEXT_CHARS of
text on each side of the quote. Scoring should pass the same context so that the judge it uses is the
one that was calibrated; `Judge.support_pair(pair, corpus)` does it for a line of a run's pairs.jsonl.

Calibration (labelling README step 11, adapted from "same fact?" to support): `gold judge-sample` draws
SAMPLE_SIZE fact-quote pairs from the runs' pairs.jsonl, stratified by condition (equal allocation; the
population of each condition is recorded); `gold judge-push` loads them into `<name>-judge`, where people
answer supports / partial / no without seeing the judge; `gold judge-agreement` asks the judge (cached),
splits the answered pairs into two seeded halves, picks on the first half whether the judge's `partial`
counts as yes or no (the higher kappa; a tie: no), and reports on the other half Cohen's kappa, raw and
weighted to the conditions' population shares (N_h / n_h), the judge's yes-precision P(person yes | judge
yes) and P(person yes | judge no), each with a Wilson interval. A person's `supports` is yes, `partial`
and `no` are no: the primary outcome counts facts whose quote supports them. Weighted kappa below
KAPPA_BAR (0.61): the report says to report soft scores without the judge, as the labelling repo did.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections import Counter
from collections.abc import Awaitable, Coroutine, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict, TypeVar

from pydantic import BaseModel, Field
from pydantic_ai.models import Model

from . import argilla_io, llm, review
from .agreement import KAPPA_BAR, kappa, wilson

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
CACHE_FILE = "judge-cache.jsonl"
REPORT_FILE = "judge-report.json"
JUDGE_DIR = "judge"
CONTEXT_CHARS = 600
SAMPLE_SIZE = 240
SAMPLE_SEED = "judge-v1"
CONCURRENCY = 6  # 3 active sequences per sub-model replica without preemption (STATE.md, L3)
MAX_TOKENS = 512
LABELS = ("supports", "partial", "no")
T = TypeVar("T")


class SupportReply(BaseModel):
    rationale: str = Field(description="One or two sentences: what the quote says and how it bears on the fact")
    label: Literal["supports", "partial", "no"]


class MatchReply(BaseModel):
    rationale: str = Field(description="One or two sentences")
    match: bool


class Verdict(TypedDict):
    label: str
    rationale: str
    model: str
    prompt_sha256: str
    cached: bool


TASKS: dict[str, type[BaseModel]] = {"support": SupportReply, "same-fact": MatchReply, "same-row": MatchReply}


@dataclass(frozen=True)
class Prompt:
    task: str
    text: str
    output: type[BaseModel]

    @property
    def sha256(self) -> str:
        return llm.prompt_sha256(self.text, self.output)

    @property
    def file(self) -> str:
        return f"gold/prompts/judge-{self.task}.txt"


def load_prompt(task: str) -> Prompt:
    return Prompt(task, (PROMPT_DIR / f"judge-{task}.txt").read_text(encoding="utf-8"), TASKS[task])


# --- what the model sees ----------------------------------------------------------------------------------

def _spo(fact: dict[str, Any]) -> dict[str, Any]:
    return {k: fact[k] for k in ("s", "p", "o")}


def _triple(fact: dict[str, Any]) -> list[str]:
    return [f"  subject: {fact['s']}", f"  predicate: {fact['p']}", f"  object: {fact['o']}"]


def _block(title: str, text: str) -> list[str]:
    return [f"{title}:", '"""', text, '"""']


def concept_brief(concept: dict[str, Any] | None) -> dict[str, Any] | None:
    if not concept:
        return None
    return {k: concept.get(k) for k in ("title", "definition", "answer_shape")}


def row_fields(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k not in ("id", "facts")}


def support_prompt(fact: dict[str, Any], quote: str, context: str | None) -> str:
    lines = ["Fact:", *_triple(fact), "", *_block("Quote", quote)]
    if context:
        lines += ["", *_block("Context", context)]
    return "\n".join(lines)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _concept_lines(concept: dict[str, Any] | None) -> list[str]:
    if not concept:
        return ["Concept: (none given)"]
    return [f"Concept: {concept.get('title', '')}: {concept.get('definition', '')}",
            f"Answer shape: {_json(concept.get('answer_shape'))}"]


def fact_match_prompt(run_fact: dict[str, Any], key_fact: dict[str, Any], concept: dict[str, Any] | None) -> str:
    return "\n".join([*_concept_lines(concept), "", "Run fact:", *_triple(run_fact), "", "Key fact:",
                      *_triple(key_fact)])


def row_match_prompt(run_row: dict[str, Any], key_row: dict[str, Any], concept: dict[str, Any] | None) -> str:
    return "\n".join([*_concept_lines(concept), "", f"Run row: {_json(row_fields(run_row))}",
                      f"Key row: {_json(row_fields(key_row))}"])


def context_for(corpus: review.Corpus, file: str, start: int, end: int, chars: int = CONTEXT_CHARS) -> str | None:
    """The paper id and about `chars` characters on each side of the quote (cut at line ends)."""
    if not file or not corpus.has(file):
        return None
    text = corpus.text(file)
    a, b = argilla_io.window(text, start, end, chars)
    return f"Paper {corpus.paper_id(file)} ({corpus.file_name(file)}):\n{text[a:b]}"


def run_sync(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine from sync code, also when an event loop is already running (FastAPI, notebooks)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(asyncio.run, coro).result()


# --- the judge ------------------------------------------------------------------------------------------

class Judge:
    """The cached judge. `models`: pydantic-ai models to rotate over (tests pass FunctionModels);
    default the LiteLLM sub-models, made at the first call."""

    def __init__(self, root: Path | str | None = None, models: list[Model] | None = None, *,
                 model_id: str | None = None, cache_only: bool = False, temperature: float = 0.0,
                 seed: int = 0, concurrency: int = CONCURRENCY) -> None:
        self.root = review.gold_root(root)
        self.cache = llm.JsonlCache(self.root / CACHE_FILE)
        self._models = models
        self._rotation: llm.Rotation | None = None
        self.model_id = model_id or (llm.model_name(models[0]) if models
                                     else f"{llm.SUB_MODEL['name']}@{llm.SUB_MODEL['revision']}")
        self.cache_only = cache_only
        self.settings = {"temperature": temperature, "seed": seed}
        self.prompts = {task: load_prompt(task) for task in TASKS}
        self.concurrency = concurrency
        self.calls = 0  # model calls made by this object

    def prompt_hashes(self) -> dict[str, str]:
        return {task: p.sha256 for task, p in self.prompts.items()}

    def _model(self) -> Model:
        if self._rotation is None:
            self._rotation = llm.Rotation(self._models)
        return self._rotation.next()

    async def _ask(self, task: str, payload: dict[str, Any], user_prompt: str) -> dict[str, Any] | None:
        prompt = self.prompts[task]
        key = llm.cache_key({"task": task, "input": payload, "model": self.model_id,
                             "prompt_sha256": prompt.sha256, "settings": self.settings})
        meta = {"model": self.model_id, "prompt_sha256": prompt.sha256}
        hit = self.cache.get(key)
        if hit is not None:
            return {**hit, **meta, "cached": True}
        if self.cache_only:
            return None
        reply = await llm.structured(prompt.text, user_prompt, prompt.output, model=self._model(),
                                     model_settings=llm.settings(**self.settings, max_tokens=MAX_TOKENS))
        self.calls += 1
        value = reply.model_dump()
        self.cache.put(key, value)
        return {**value, **meta, "cached": False}

    async def asupport(self, fact: dict[str, Any], quote: str, *, context: str | None = None) -> Verdict | None:
        return await self._ask("support", {"fact": _spo(fact), "quote": quote, "context": context},
                               support_prompt(fact, quote, context))  # type: ignore[return-value]

    async def asame_fact(self, run_fact: dict[str, Any], key_fact: dict[str, Any],
                         concept: dict[str, Any] | None) -> dict[str, Any] | None:
        brief = concept_brief(concept)
        return await self._ask("same-fact", {"run": _spo(run_fact), "key": _spo(key_fact), "concept": brief},
                               fact_match_prompt(run_fact, key_fact, brief))

    async def asame_row(self, run_row: dict[str, Any], key_row: dict[str, Any],
                        concept: dict[str, Any] | None) -> dict[str, Any] | None:
        brief = concept_brief(concept)
        return await self._ask("same-row", {"run": row_fields(run_row), "key": row_fields(key_row), "concept": brief},
                               row_match_prompt(run_row, key_row, brief))

    async def asupport_pair(self, pair: dict[str, Any], corpus: review.Corpus) -> Verdict | None:
        """A pairs.jsonl line (or a calibration sample row): None for an unsourced fact."""
        if not pair.get("quote"):
            return None
        fact = pair.get("fact") or _spo(pair)
        context = context_for(corpus, pair.get("file") or "", int(pair.get("start") or 0), int(pair.get("end") or 0))
        return await self.asupport(fact, pair["quote"], context=context)

    def support(self, fact: dict[str, Any], quote: str, *, context: str | None = None) -> Verdict | None:
        return run_sync(self.asupport(fact, quote, context=context))

    def same_fact(self, run_fact: dict[str, Any], key_fact: dict[str, Any],
                  concept: dict[str, Any] | None) -> dict[str, Any] | None:
        return run_sync(self.asame_fact(run_fact, key_fact, concept))

    def same_row(self, run_row: dict[str, Any], key_row: dict[str, Any],
                 concept: dict[str, Any] | None) -> dict[str, Any] | None:
        return run_sync(self.asame_row(run_row, key_row, concept))

    def support_pair(self, pair: dict[str, Any], corpus: review.Corpus) -> Verdict | None:
        return run_sync(self.asupport_pair(pair, corpus))

    async def gather(self, calls: Iterable[Awaitable[T]]) -> list[T]:
        """Await many judge calls, at most `concurrency` at a time, results in order."""
        gate = asyncio.Semaphore(self.concurrency)

        async def one(call: Awaitable[T]) -> T:
            async with gate:
                return await call

        return list(await asyncio.gather(*(one(c) for c in calls)))


_defaults: dict[str, Judge] = {}


def default_judge() -> Judge:
    """One Judge per $GOLD, on the LiteLLM sub-models."""
    root = str(review.gold_root())
    if root not in _defaults:
        _defaults[root] = Judge(root)
    return _defaults[root]


def support(fact: dict[str, Any], quote: str, *, context: str | None = None, judge: Judge | None = None) -> Verdict | None:
    return (judge or default_judge()).support(fact, quote, context=context)


def same_fact(run_fact: dict[str, Any], key_fact: dict[str, Any], concept: dict[str, Any] | None, *,
              judge: Judge | None = None) -> dict[str, Any] | None:
    return (judge or default_judge()).same_fact(run_fact, key_fact, concept)


def same_row(run_row: dict[str, Any], key_row: dict[str, Any], concept: dict[str, Any] | None, *,
             judge: Judge | None = None) -> dict[str, Any] | None:
    return (judge or default_judge()).same_row(run_row, key_row, concept)


# --- calibration sample ---------------------------------------------------------------------------------

def _qid(run_id: str, config: dict[str, Any]) -> str | None:
    found = config.get("question_id") or config.get("qid")
    if found:
        return str(found)
    match = re.match(r"(q\d+)-", run_id)
    return match.group(1) if match else None


def population(runs_root: Path) -> list[dict[str, Any]]:
    """Every fact-quote pair with a quote in the runs under `runs_root` (any depth: batch roots nest)."""
    rows = []
    for path in sorted(Path(runs_root).rglob("pairs.jsonl")):
        config = review.read_json(path.parent / "config.json") or {}
        for line in review.read_jsonl(path):
            if not line.get("quote") or not line.get("claim_id"):
                continue
            run_id = str(line.get("run_id") or path.parent.name)
            ident = hashlib.sha256(f"{run_id}|{line['fact_id']}|{line['claim_id']}".encode()).hexdigest()[:16]
            rows.append({"id": f"judge-{ident}", "run_id": run_id, "qid": _qid(run_id, config),
                         "condition": str(config.get("condition") or "unknown"), "row_id": line.get("row_id"),
                         "fact_id": line["fact_id"], "claim_id": line["claim_id"], "origin": line.get("origin"),
                         "fact": _spo(line), "file": line.get("file"), "start": line.get("start"),
                         "end": line.get("end"), "quote": line["quote"]})
    return rows


def allocate(sizes: dict[str, int], total: int) -> dict[str, int]:
    """Equal allocation over strata; what a small stratum cannot take goes to the others."""
    out = {k: 0 for k in sizes}
    left = total
    open_ = sorted(k for k, n in sizes.items() if n > 0)
    while left > 0 and open_:
        share, extra = divmod(left, len(open_))
        for i, k in enumerate(open_):
            give = min(share + (i < extra), sizes[k] - out[k])
            out[k] += give
            left -= give
        open_ = [k for k in open_ if out[k] < sizes[k]]
    return out


def sample_pairs(runs_root: Path, *, size: int = SAMPLE_SIZE, seed: str = SAMPLE_SEED,
                 ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """A seeded sample of `size` pairs stratified by condition, and its manifest (population, sample)."""
    rows = population(runs_root)
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(row["condition"], []).append(row)
    sizes = {c: len(g) for c, g in groups.items()}
    taken = allocate(sizes, size)
    chosen: list[dict[str, Any]] = []
    for condition, group in sorted(groups.items()):
        by_id = {r["id"]: r for r in group}
        chosen += [by_id[i] for i in review.seeded_order(by_id, f"{seed}:{condition}")[:taken[condition]]]
    chosen = sorted(chosen, key=lambda r: hashlib.sha256(f"{seed}:{r['id']}".encode()).hexdigest())
    manifest = {"seed": seed, "size": size, "runs_root": str(runs_root), "drawn_at": review.utc_now(),
                "runs": len({r["run_id"] for r in rows}), "population": sizes, "sampled": taken}
    return chosen, manifest


def write_sample(root: Path, rows: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    review.write_jsonl(Path(root) / JUDGE_DIR / "sample.jsonl", rows)
    review.write_json(Path(root) / JUDGE_DIR / "sample.json", manifest)


def load_sample(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return (review.read_jsonl(Path(root) / JUDGE_DIR / "sample.jsonl"),
            review.read_json(Path(root) / JUDGE_DIR / "sample.json") or {})


def records(rows: list[dict[str, Any]], corpus: review.Corpus) -> list[dict[str, Any]]:
    """Argilla records for the sample: fact, quote and the passage around it (the judge's answer is
    never in a record)."""
    out = []
    for row in rows:
        file = row.get("file") or ""
        if corpus.has(file) and row.get("end"):
            passage = argilla_io.passage_markdown(corpus.text(file), int(row["start"]), int(row["end"]))
        else:
            passage = f"_`{file}` is not in the corpus directory._"
        out.append(argilla_io.judge_record(row, passage_md=passage))
    return out


# --- calibration report ------------------------------------------------------------------------------------

def people(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per answered record: one person's label (the alphabetically first user who submitted, a rule blind
    to the answer) and everyone's answers."""
    out = {}
    for record in records:
        answers = {u: str(a["support"]) for u, a in review.submitted(record).items() if a.get("support") in LABELS}
        if answers:
            first = min(answers)
            out[record["id"]] = {"label": answers[first], "user": first, "answers": answers}
    return out


def binary(label: str, *, partial_yes: bool) -> str:
    return "yes" if label == "supports" or (partial_yes and label == "partial") else "no"


def halves(ids: Iterable[str], seed: str) -> tuple[list[str], list[str]]:
    """Two seeded halves: the first picks the partial mapping, the second is reported."""
    order = review.seeded_order(sorted(ids), f"{seed}:halves")
    return order[:len(order) // 2], order[len(order) // 2:]


def _weights(ids: list[str], condition: dict[str, str], population_sizes: dict[str, int]) -> list[float] | None:
    if not population_sizes:
        return None
    n = Counter(condition[i] for i in ids)
    return [population_sizes.get(condition[i], 0) / n[condition[i]] for i in ids]


def _conditional(pairs: list[tuple[str, str]], judged: str) -> dict[str, Any]:
    stratum = [person for person, judge in pairs if judge == judged]
    hits = sum(person == "yes" for person in stratum)
    low, high = wilson(hits, len(stratum))
    return {"rate": round(hits / len(stratum), 4) if stratum else None, "n": len(stratum),
            "ci95": [round(low, 4), round(high, 4)]}


def _r(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def calibrate(sample: list[dict[str, Any]], manifest: dict[str, Any], answered: dict[str, dict[str, Any]],
              verdicts: dict[str, Verdict | None], *, seed: str = SAMPLE_SEED) -> dict[str, Any]:
    """The calibration report (see the module docstring) from people's answers and the judge's verdicts."""
    condition = {r["id"]: r["condition"] for r in sample}
    sizes = {k: int(v) for k, v in (manifest.get("population") or {}).items()}
    ids = sorted(i for i in answered if i in condition and verdicts.get(i))
    warnings = []
    if len(ids) < len(answered):
        warnings.append(f"{len(answered) - len(ids)} answered records are not in the sample or have no verdict")
    first, second = halves(ids, seed)

    def score(subset: list[str], partial_yes: bool) -> dict[str, Any]:
        h = [binary(answered[i]["label"], partial_yes=False) for i in subset]
        j = [binary(verdicts[i]["label"], partial_yes=partial_yes) for i in subset]  # type: ignore[index]
        w = _weights(subset, condition, sizes)
        return {"items": len(subset), "kappa": _r(kappa(h, j)),
                "weighted_kappa": _r(kappa(h, j, sample_weight=w)) if w else None}

    def rank(result: dict[str, Any]) -> float:
        value = result["weighted_kappa"] if result["weighted_kappa"] is not None else result["kappa"]
        return -2.0 if value is None else value

    options = {"no": score(first, False), "yes": score(first, True)}
    partial = "yes" if rank(options["yes"]) > rank(options["no"]) else "no"
    partial_yes = partial == "yes"
    tested = score(second, partial_yes)
    pairs = [(binary(answered[i]["label"], partial_yes=False), binary(verdicts[i]["label"], partial_yes=partial_yes))  # type: ignore[index]
             for i in second]
    order = {label: n for n, label in enumerate(reversed(LABELS))}  # no < partial < supports
    confusion: dict[str, dict[str, int]] = {j: {h: 0 for h in LABELS} for j in LABELS}
    for i in second:
        confusion[verdicts[i]["label"]][answered[i]["label"]] += 1  # type: ignore[index]
    users = sorted({u for i in second for u in answered[i]["answers"]})
    per_person = {}
    for user in users:
        mine = [i for i in second if user in answered[i]["answers"]]
        per_person[user] = {"items": len(mine), "kappa": _r(kappa(
            [binary(answered[i]["answers"][user], partial_yes=False) for i in mine],
            [binary(verdicts[i]["label"], partial_yes=partial_yes) for i in mine]))}  # type: ignore[index]
    decided = tested["weighted_kappa"] if tested["weighted_kappa"] is not None else tested["kappa"]
    use = decided is not None and decided >= KAPPA_BAR
    advice = ("The judge agrees with people well enough: score support and soft matching with it."
              if use else
              f"Kappa {decided} is below {KAPPA_BAR}: report soft scores without the judge (strict and "
              "normalised matching only), as the labelling repo did, and give the judge's support share only "
              "as an unvalidated secondary number.")
    return {
        "generated_at": review.utc_now(), "sample": manifest, "answered": len(answered), "judged": len(ids),
        "one_response_rule": "per record, the alphabetically first user who submitted",
        "people_binary": "supports = yes; partial and no = no",
        "split": {"seed": seed, "calibration": len(first), "test": len(second)},
        "calibration": {"partial_counts_as": partial, "if_partial_no": options["no"], "if_partial_yes": options["yes"]},
        "test": {**tested, "kappa_basis": "population-weighted by condition (N_h/n_h)" if sizes else "raw sample",
                 "raw_agreement": _r(sum(a == b for a, b in pairs) / len(pairs)) if pairs else None,
                 "precision_judge_yes": _conditional(pairs, "yes"),
                 "person_yes_given_judge_no": _conditional(pairs, "no"),
                 "three_way_linear_kappa": _r(kappa([order[answered[i]["label"]] for i in second],
                                                    [order[verdicts[i]["label"]] for i in second],  # type: ignore[index]
                                                    weights="linear")),
                 "confusion_judge_by_person": confusion, "per_person": per_person},
        "bar": KAPPA_BAR, "use_judge": use, "advice": advice, "warnings": warnings,
    }


def calibration_report(root: Path, corpus: review.Corpus, *, judge: Judge, seed: str = SAMPLE_SEED) -> dict[str, Any]:
    """Judge every answered sample pair (through the cache), calibrate, write $GOLD/judge-report.json."""
    sample, manifest = load_sample(root)
    answered = people(review.read_jsonl(Path(root) / JUDGE_DIR / "responses.jsonl"))
    by_id = {r["id"]: r for r in sample}
    ids = [i for i in sorted(answered) if i in by_id]
    found = run_sync(judge.gather([judge.asupport_pair(by_id[i], corpus) for i in ids]))
    report = calibrate(sample, manifest, answered, dict(zip(ids, found)), seed=seed)
    prompt = judge.prompts["support"]
    report = {**report, "model": judge.model_id, "prompt_file": prompt.file, "prompt_sha256": prompt.sha256,
              "context_chars": CONTEXT_CHARS, "model_calls": judge.calls}
    review.write_json(Path(root) / REPORT_FILE, report)
    return report
