"""`evidence tune STEP --train DIR... --test DIR... --optimizer gepa|miprov2`: DSPy tunes one step's instructions.

Every step has the same budget (decision of Aditya, 3 Nov): GEPA's light size, capped at `MAX_METRIC_CALLS` = 500 model
calls (DSPy accepts `auto` or `max_metric_calls`, not both, so the cap is passed and `auto` is left out).
The result is `evidence/steps/tuned/<step>.json`: `{"instructions": ..., ...}`; `evidence.steps.Step` reads only the
`instructions` key, the rest (optimizer, call budget, calls made, train and test scores before and after, corpus ids)
is the report. Every model call goes through a `RecordedLM` (the caller gives it, on the recorder).

Data. A step either tunes on the Claude-written synthetic corpora (`ground_truth.json` + `papers/`) or, for the
real-paper steps (`REAL_STEPS`), on the held-out slice of a real set: the set's folder has `tune_split.json`
(evaluation/wholerun.tune_split: {"papers": held out for tuning, "rest": the others}) and `tune_examples.json`
({"examples": [{"step", "paper", "inputs", "gold"}]}). Training uses only held-out papers, testing only the rest.
Train and test must not share a corpus id (or, in a real set, a paper): refused with `TuneError`.

Gold per step (the metric reads it, whatever the source): write_words / write_more_words {"names": [...]} (recall;
on the test side only names not in the training answer keys count); recheck {"keep": [bool per item]} (precision of
the finds kept); map_experiments {"n": count} (closeness of the count, and every quote must be in the paper);
claims.read_claim {"is_claim": bool, "direction": str | None} (claim sentences and non-claim sentences, balanced;
the score is the mean over both, so calling every sentence a claim scores about 0.5).

`tune_examples.json` (built per real set by the runbook, Task 8.4) has exactly this format:
  {"examples": [{"step": "recheck" | "map_experiments" | "claims.read_claim", "paper": "<paper id of the set>",
                 "inputs": {<the step signature's input fields>}, "gold": {<gold of the step, above>}}]}
and sits next to `tune_split.json` ({"papers": [...], "rest": [...]}); a real-set folder without it is refused.

Disjointness is by content, not by name: train and test must share no paper text (sha256, whitespace-normalised)
and no ground-truth studies (hash), and in a real set no paper id.

Budget (decision of Aditya): per step `min(GEPA's light budget for that step's train size, 500)`; the file records
`light_budget`, `max_metric_calls` (the cap used), and the model calls really made. MIPROv2 is capped the same way
(its number of trials is chosen to fit, and the calls of its compile are counted and refused above the cap).

Known gap: `planner_query` is not tunable yet (its metric must be the whole-run score on synthetic questions, which
is not wired); the planner stays untuned."""
from __future__ import annotations

import hashlib
import importlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import dspy
from dspy.utils.exceptions import AdapterParseError

from modelcall.dspy_lm import RecordedLM

from . import TUNED_DIR

MAX_METRIC_CALLS = 500
MAX_FAILED_SHARE = 0.2        # more failed (unparseable) examples than this share: no tuned file
OPTIMIZERS = ("gepa", "miprov2")
TUNE_FILE = "tune_split.json"       # same name and format as evaluation/wholerun.TUNE_FILE
EXAMPLES_FILE = "tune_examples.json"
REAL_STEPS = ("recheck", "map_experiments", "claims.read_claim")


class TuneError(ValueError):
    """A refused tuning request (overlap, no examples, a step with no metric)."""


# ---- corpora ----------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Source:
    """One folder of examples: its corpus id and, for a real set, which papers a side may use."""
    path: Path
    corpus_id: str
    papers: frozenset[str] | None       # None: every paper (synthetic)
    hashes: frozenset[str] = frozenset()   # sha256 of each paper text and of the ground-truth studies


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _corpus_id(path: Path) -> str:
    manifest = path / "manifest.json"
    if manifest.is_file():
        return str(_read(manifest).get("corpus_id") or path.name)
    return path.name


def _text_hash(text: str) -> str:
    return "paper:" + hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


def _hashes(path: Path, papers: frozenset[str] | None) -> frozenset[str]:
    """Content hashes of the papers a side may use (all of them, or the listed ids) and of the ground-truth studies."""
    out = ({_text_hash(f.read_text(encoding="utf-8")) for f in sorted((path / "papers").glob("*.md"))
            if papers is None or f.stem in papers} if (path / "papers").is_dir() else set())
    if papers is None and (path / "ground_truth.json").is_file():
        studies = json.dumps(_read(path / "ground_truth.json").get("studies"), sort_keys=True)
        out.add("truth:" + hashlib.sha256(studies.encode("utf-8")).hexdigest())
    return frozenset(out)


def _split_of(path: Path) -> dict[str, Any] | None:
    for folder in (path, path.parent):
        if (folder / TUNE_FILE).is_file():
            return _read(folder / TUNE_FILE)
    return None


def sources(step: str, dirs: list[Path], side: str) -> list[Source]:
    """The folders of one side ("train" or "test"). A real step reads its held-out slice (train) or the rest (test)
    of a real set; a folder that is neither a real set with its example file nor a synthetic corpus is refused."""
    out = []
    for d in map(Path, dirs):
        if step in REAL_STEPS and (d / EXAMPLES_FILE).is_file():
            split = _split_of(d)
            if split is None:
                raise TuneError(f"{d}: a real set needs {TUNE_FILE} (the papers held out for tuning)")
            papers = frozenset(split["papers"] if side == "train" else split.get("rest", []))
            out.append(Source(d, _corpus_id(d), papers, _hashes(d, papers)))
        elif (d / "ground_truth.json").is_file():
            out.append(Source(d, _corpus_id(d), None, _hashes(d, None)))
        elif step in REAL_STEPS and _split_of(d) is not None:
            raise TuneError(f"{d}: a real set ({TUNE_FILE} found) needs {EXAMPLES_FILE} (format in "
                            "evidence/steps/tune.py); it is not tuned on without it")
        else:
            raise TuneError(f"{d}: neither a synthetic corpus (ground_truth.json) nor a real set ({EXAMPLES_FILE})")
    return out


def check_disjoint(train: list[Source], test: list[Source]) -> None:
    """Refuse any shared paper text or ground truth (by hash, whatever the corpus ids), a corpus id on both sides
    that is a whole synthetic corpus, and a paper id on both sides of a real set."""
    for a in train:
        for b in test:
            shared = a.hashes & b.hashes
            if shared:
                raise TuneError(f"train corpus {a.corpus_id} and test corpus {b.corpus_id} share {len(shared)} paper "
                                "texts or ground truths: tuning papers and test papers must be disjoint")
            if a.corpus_id == b.corpus_id and (a.papers is None or b.papers is None):
                raise TuneError(f"train and test share corpus {a.corpus_id}: tuning papers and test papers must "
                                "be disjoint")
            if a.corpus_id == b.corpus_id and a.papers is not None and b.papers is not None and a.papers & b.papers:
                raise TuneError(f"train and test share papers {sorted(a.papers & b.papers)} of {a.corpus_id}")


# ---- examples ---------------------------------------------------------------------------------------------------

Example = dict[str, Any]     # {"inputs": {...}, "gold": {...}}


def _synthetic(d: Path) -> tuple[dict[str, Any], dict[str, str]]:
    truth = _read(d / "ground_truth.json")
    texts = ({p.stem: p.read_text(encoding="utf-8") for p in sorted((d / "papers").glob("*.md"))}
             if (d / "papers").is_dir() else {})
    return truth, texts


def _names_by_role(truth: dict[str, Any]) -> dict[str, list[str]]:
    roles: dict[str, list[str]] = {}
    for study in truth["studies"]:
        for c in study.get("conditions", []):
            if c["role"] == "other":
                continue
            names = roles.setdefault(c["role"], [])
            for name in [c["label"], *c.get("aliases", [])]:
                if name.casefold() not in {n.casefold() for n in names}:
                    names.append(name)
    return roles


def build_words(d: Path) -> list[Example]:
    truth, _ = _synthetic(d)
    return [{"inputs": {"question": truth["question"], "thing": role}, "gold": {"names": names}}
            for role, names in _names_by_role(truth).items()]


def build_more_words(d: Path) -> list[Example]:
    truth, _ = _synthetic(d)
    return [{"inputs": {"question": truth["question"], "thing": role, "already": names[:2]},
             "gold": {"names": names[2:]}} for role, names in _names_by_role(truth).items() if len(names) > 2]


def build_recheck(d: Path) -> list[Example]:
    """Per paper: its condition-label finds are true (keep), a measured number offered as a condition is not (drop)."""
    truth, texts = _synthetic(d)
    out = []
    for paper, text in texts.items():
        marks = [p for p in truth["placements"] if p["paper"] == paper and p["role"] in ("condition_label", "value")]
        keep = [p for p in marks if p["role"] == "condition_label"][:2]
        drop = [p for p in marks if p["role"] == "value"][:2]
        if not keep or not drop:
            continue
        ps = sorted(keep + drop, key=lambda p: p["start"])
        start = text.rfind("\n\n", 0, ps[0]["start"])
        start = 0 if start < 0 else start + 2
        out.append({"inputs": {"paragraph": text[start:ps[-1]["end"]],
                               "items": [f'{n}. condition | {json.dumps({"label": p["exact"]})} | {p["exact"]}'
                                         for n, p in enumerate(ps, 1)]},
                    "gold": {"keep": [p["role"] == "condition_label" for p in ps]}})
    return out


def build_experiments(d: Path) -> list[Example]:
    """Only corpora of level multi_experiment (their truth lists the experiments: the datasets a study measured)."""
    truth, texts = _synthetic(d)
    level = _read(d / "corpus.json").get("level") if (d / "corpus.json").is_file() else None
    if level != "multi_experiment":
        return []
    out = []
    for s in truth["studies"]:
        n = len({m.get("dataset") for m in s.get("measurements", []) if m.get("dataset")})
        if s["paper"] in texts and n:
            out.append({"inputs": {"paper": texts[s["paper"]]}, "gold": {"n": n, "text": texts[s["paper"]]}})
    return out


_SENTENCE = re.compile(r"[^.!?\n]+[.!?]")


def build_claims(d: Path) -> list[Example]:
    """The claim sentences (gold: a claim, the study's direction) and as many non-claim sentences of the same papers
    (gold: not a claim): sentences with no claim placement in them that hold a condition or a number."""
    truth, texts = _synthetic(d)
    claims = {s["paper"]: s["author_claim"]["direction"] for s in truth["studies"] if s.get("author_claim")}
    out: list[Example] = []
    for paper, text in texts.items():
        marks = [p for p in truth["placements"] if p["paper"] == paper]
        pos = []
        for p in marks:
            direction = claims.get(p["fact"].split(".")[0])
            if p["role"] == "claim" and direction is not None:
                pos.append({"inputs": {"sentence": text[p["start"]:p["end"]]},
                            "gold": {"is_claim": True,
                                     "direction": direction if direction in ("improves", "worsens", "no_effect") else None}})
        spans = [(p["start"], p["end"]) for p in marks if p["role"] == "claim"]
        other = [p["start"] for p in marks if p["role"] in ("condition_label", "value")]
        neg = []
        for m in _SENTENCE.finditer(text):
            a, b = m.span()
            if len(m.group().split()) >= 5 and not any(a < e and x < b for x, e in spans) \
                    and any(a <= x < b for x in other):
                neg.append({"inputs": {"sentence": m.group().strip()}, "gold": {"is_claim": False, "direction": None}})
        out += pos + neg[:len(pos)]
    return out


def real_examples(src: Source, step: str) -> list[Example]:
    rows = _read(src.path / EXAMPLES_FILE)["examples"]
    return [{"inputs": r["inputs"], "gold": r["gold"]} for r in rows
            if r["step"] == step and (src.papers is None or r["paper"] in src.papers)]


# ---- metrics ----------------------------------------------------------------------------------------------------

def _norm(s: Any) -> str:
    return " ".join(str(s).casefold().split())


def metric_words(gold: dict, pred: Any, seen: frozenset[str] = frozenset()) -> float:
    """Recall of the answer-key names; names in `seen` (the training side's keys) do not count."""
    want = {_norm(n) for n in gold["names"]} - seen
    if not want:
        return 1.0
    got = {_norm(n) for n in (getattr(pred, "names", None) or [])}
    return len(want & got) / len(want)


def metric_recheck(gold: dict, pred: Any, seen: frozenset[str] = frozenset()) -> float:
    """Item precision: of the finds the model keeps, the share that are true finds (keeping none scores 0, and so does keeping under half of the true finds)."""
    said = {v.number: v.verdict for v in (getattr(pred, "verdicts", None) or [])}
    kept = [i for i in range(1, len(gold["keep"]) + 1) if said.get(i, "keep") != "drop"]
    if not kept:
        return 0.0 if any(gold["keep"]) else 1.0
    hit = sum(gold["keep"][i - 1] for i in kept)
    if any(gold["keep"]) and hit / sum(gold["keep"]) < 0.5:
        return 0.0                  # floor: dropping almost every true find is not a good check
    return hit / len(kept)


def metric_experiments(gold: dict, pred: Any, seen: frozenset[str] = frozenset()) -> float:
    found = list(getattr(pred, "experiments", None) or [])
    n = gold["n"]
    text = _norm(gold.get("text", ""))
    quoted = [e for e in found if not text or _norm(e.quote) in text]
    return max(0.0, 1 - abs(len(quoted) - n) / max(n, len(found), 1))


def metric_claims(gold: dict, pred: Any, seen: frozenset[str] = frozenset()) -> float:
    ok = bool(getattr(pred, "is_claim", False)) == gold["is_claim"]
    if not gold["is_claim"]:
        return float(ok)
    return (float(ok) + float(getattr(pred, "direction", None) == gold["direction"])) / 2


@dataclass(frozen=True)
class Spec:
    name: str
    signature: Callable[[], type[dspy.Signature]]
    build: Callable[[Path], list[Example]]
    metric: Callable[..., float]


def _sig(module: str, cls: str) -> Callable[[], type[dspy.Signature]]:
    return lambda: getattr(importlib.import_module(module), cls)


SPECS: dict[str, Spec] = {s.name: s for s in (
    Spec("write_words", _sig("evidence.words.write", "WriteWords"), build_words, metric_words),
    Spec("write_more_words", _sig("evidence.words.write", "WriteMoreWords"), build_more_words, metric_words),
    Spec("recheck", _sig("evidence.extractors.recheck", "Recheck"), build_recheck, metric_recheck),
    Spec("map_experiments", _sig("evidence.experiments", "MapExperiments"), build_experiments, metric_experiments),
    Spec("claims.read_claim", _sig("evidence.claims", "ReadClaim"), build_claims, metric_claims),
)}


def examples_of(spec: Spec, srcs: list[Source]) -> list[Example]:
    out: list[Example] = []
    for s in srcs:
        out += real_examples(s, spec.name) if s.papers is not None else spec.build(s.path)
    return out


# ---- running ----------------------------------------------------------------------------------------------------

class _Program(dspy.Module):
    def __init__(self, signature: type[dspy.Signature], instructions: str) -> None:
        super().__init__()
        self.predict = dspy.Predict(signature.with_instructions(instructions))

    def forward(self, **inputs: Any) -> dspy.Prediction:
        return self.predict(**inputs)


def _dspy(ex: Example) -> dspy.Example:
    return dspy.Example(**ex["inputs"], gold=ex["gold"]).with_inputs(*ex["inputs"])


def _score(program: dspy.Module, examples: list[Example], metric: Callable[..., float], lm: RecordedLM,
           seen: frozenset[str] = frozenset()) -> tuple[float, int]:
    """(mean metric, number of examples whose reply could not be parsed; those score 0). Other errors propagate."""
    total, failed = 0.0, 0
    for ex in examples:
        try:
            with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
                total += metric(ex["gold"], program(**ex["inputs"]), seen)
        except AdapterParseError:
            failed += 1
    return (total / len(examples) if examples else 0.0), failed


def light_budget(n_train: int) -> int:
    """GEPA's own light budget (auto="light") for one predictor and `n_train` examples."""
    return dspy.GEPA(metric=lambda *a, **k: 0.0, auto="light",
                     reflection_lm=dspy.LM("openai/unused")).auto_budget(num_preds=1, num_candidates=6,
                                                                          valset_size=n_train)


class BudgetExceeded(RuntimeError):
    pass


def default_optimizer(name: str, metric: Callable[..., float], lm: RecordedLM, budget: int) -> Any:
    """GEPA with `max_metric_calls=budget`, or MIPROv2 with trials chosen to fit `budget` calls; both on `lm`."""
    def gepa_metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
        return metric(gold.gold, pred)

    def mipro_metric(gold, pred, trace=None):
        return metric(gold.gold, pred)
    if name == "gepa":
        return dspy.GEPA(metric=gepa_metric, max_metric_calls=budget, reflection_lm=lm)
    return _Mipro(dspy.MIPROv2(metric=mipro_metric, prompt_model=lm, task_model=lm, auto=None, num_candidates=3),
                  budget)


class _Mipro:
    """MIPROv2 with an explicit trial count: about 3 candidate prompts + trials x minibatch calls must fit `budget`."""
    MINIBATCH = 10

    def __init__(self, inner: Any, budget: int) -> None:
        self.inner, self.budget = inner, budget

    def compile(self, student: Any, trainset: list) -> Any:
        trials = max(1, (self.budget - 40) // (self.MINIBATCH + 2))
        return self.inner.compile(student, trainset=trainset, num_trials=trials, minibatch_size=self.MINIBATCH,
                                  max_bootstrapped_demos=0, max_labeled_demos=0, requires_permission_to_run=False)


def tune(step: str, train: list[Path], test: list[Path], *, lm: RecordedLM, optimizer: str = "gepa",
         make_optimizer: Callable[[str, Callable[..., float], RecordedLM, int], Any] = default_optimizer,
         tuned_dir: Path | None = None) -> dict[str, Any]:
    """Tune `step`; write `<tuned_dir>/<step>.json` and return the report (also in that file)."""
    if step not in SPECS:
        raise TuneError(f"no tuning metric for step {step!r}; tunable: {', '.join(SPECS)}")
    if optimizer not in OPTIMIZERS:
        raise TuneError(f"optimizer must be one of {OPTIMIZERS}")
    spec = SPECS[step]
    train_src, test_src = sources(step, train, "train"), sources(step, test, "test")
    check_disjoint(train_src, test_src)
    train_ex, test_ex = examples_of(spec, train_src), examples_of(spec, test_src)
    seen = frozenset(_norm(n) for ex in train_ex for n in ex["gold"].get("names", []))
    dropped = 0
    if spec.metric is metric_words:     # a test example with no name unseen in training says nothing
        kept = [e for e in test_ex if {_norm(n) for n in e["gold"]["names"]} - seen]
        dropped, test_ex = len(test_ex) - len(kept), kept
    if not train_ex or not test_ex:
        raise TuneError(f"{step}: {len(train_ex)} train and {len(test_ex)} test examples"
                        f"{f' ({dropped} test examples dropped: no unseen names)' if dropped else ''}; both sides need some")
    light = light_budget(len(train_ex))
    cap = min(light, MAX_METRIC_CALLS)
    calls = {"n": 0, "limit": None}
    ask = lm._ask

    def counting(*a: Any, **k: Any) -> str:
        calls["n"] += 1
        if calls["limit"] is not None and calls["n"] > calls["limit"]:
            raise BudgetExceeded(f"the optimizer needed more than {cap} model calls")
        return ask(*a, **k)
    lm._ask = counting
    previous = TUNED_DIR / f"{step}.json" if tuned_dir is None else Path(tuned_dir) / f"{step}.json"
    try:
        signature = spec.signature()
        base = _Program(signature, signature.instructions)     # the signature's own text, never an earlier tuned file
        b_train, f1 = _score(base, train_ex, spec.metric, lm)
        b_test, f2 = _score(base, test_ex, spec.metric, lm, seen)
        calls["limit"] = calls["n"] + cap if optimizer == "miprov2" else None
        start = calls["n"]
        with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
            tuned = make_optimizer(optimizer, spec.metric, lm, cap).compile(base, trainset=[_dspy(e) for e in train_ex])
        optimizer_calls = calls["n"] - start
        calls["limit"] = None
        a_train, f3 = _score(tuned, train_ex, spec.metric, lm)
        a_test, f4 = _score(tuned, test_ex, spec.metric, lm, seen)
    finally:
        lm._ask = ask
    failed = {"train": f3, "test": f4}
    share = (f3 + f4) / (len(train_ex) + len(test_ex))
    if share > MAX_FAILED_SHARE:
        raise TuneError(f"{f3 + f4} of {len(train_ex) + len(test_ex)} examples of the tuned program failed to parse "
                        f"(more than {MAX_FAILED_SHARE:.0%}); no tuned file written")
    report = {"instructions": tuned.predict.signature.instructions, "step": step, "optimizer": optimizer,
              "light_budget": light, "max_metric_calls": cap, "model_calls": calls["n"],
              "optimizer_calls": optimizer_calls, "model": lm.alias,
              "train_corpora": sorted({s.corpus_id for s in train_src}),
              "test_corpora": sorted({s.corpus_id for s in test_src}),
              "n_train": len(train_ex), "n_test": len(test_ex), "test_dropped_no_unseen_names": dropped,
              "n_failed": {"before": {"train": f1, "test": f2}, "after": failed},
              "scores": {"before": {"train": b_train, "test": b_test}, "after": {"train": a_train, "test": a_test}}}
    if previous.is_file():
        report["previous_instructions"] = json.loads(previous.read_text(encoding="utf-8")).get("instructions")
    out = Path(tuned_dir or TUNED_DIR)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{step}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                      newline="\n")
    return report
