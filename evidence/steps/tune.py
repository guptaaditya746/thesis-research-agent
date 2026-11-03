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
claims.read_claim {"is_claim": bool, "direction": str | None}; planner_query {} (the query must pass the plan's own
parser check and use the run-filled `$sides` or `$metrics`; a proxy for the whole-run score, see the task report)."""
from __future__ import annotations

import importlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import dspy

from modelcall.dspy_lm import RecordedLM

from . import TUNED_DIR, Step

MAX_METRIC_CALLS = 500
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


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _corpus_id(path: Path) -> str:
    manifest = path / "manifest.json"
    if manifest.is_file():
        return str(_read(manifest).get("corpus_id") or path.name)
    return path.name


def _split_of(path: Path) -> dict[str, Any] | None:
    for folder in (path, path.parent):
        if (folder / TUNE_FILE).is_file():
            return _read(folder / TUNE_FILE)
    return None


def sources(step: str, dirs: list[Path], side: str) -> list[Source]:
    """The folders of one side ("train" or "test"). A real step reads its held-out slice (train) or the rest (test)."""
    out = []
    for d in map(Path, dirs):
        if step in REAL_STEPS and (d / EXAMPLES_FILE).is_file():
            split = _split_of(d)
            if split is None:
                raise TuneError(f"{d}: a real set needs {TUNE_FILE} (the papers held out for tuning)")
            papers = frozenset(split["papers"] if side == "train" else split.get("rest", []))
            out.append(Source(d, _corpus_id(d), papers))
        else:
            out.append(Source(d, _corpus_id(d), None))
    return out


def check_disjoint(train: list[Source], test: list[Source]) -> None:
    """Refuse a corpus id on both sides, and for a real set a paper on both sides."""
    both = sorted({s.corpus_id for s in train if s.papers is None} & {s.corpus_id for s in test if s.papers is None})
    if both:
        raise TuneError(f"train and test share corpora {both}: tuning papers and test papers must be disjoint")
    for a in train:
        for b in test:
            if a.papers is not None and b.papers is not None and a.corpus_id == b.corpus_id:
                shared = sorted(a.papers & b.papers)
                if shared:
                    raise TuneError(f"train and test share papers {shared} of {a.corpus_id}")


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


def build_claims(d: Path) -> list[Example]:
    truth, texts = _synthetic(d)
    claims = {s["paper"]: s["author_claim"]["direction"] for s in truth["studies"] if s.get("author_claim")}
    out = []
    for p in truth["placements"]:
        paper = p["fact"].split(".")[0]
        if p["role"] == "claim" and p["paper"] in texts and paper in claims:
            direction = claims[paper]
            out.append({"inputs": {"sentence": texts[p["paper"]][p["start"]:p["end"]]},
                        "gold": {"is_claim": True,
                                 "direction": direction if direction in ("improves", "worsens", "no_effect") else None}})
    return out


def build_query(d: Path) -> list[Example]:
    truth, _ = _synthetic(d)
    roles = sorted({c["role"] for s in truth["studies"] for c in s["conditions"] if c["role"] != "other"})
    metrics = sorted({m["canonical"] for s in truth["studies"] for m in s["metrics"] if m["canonical"] != "other"})
    if not roles or not metrics:
        return []
    return [{"inputs": {"question": truth["question"], "line": truth["question"], "template": "",
                        "choice_params": "[]", "things": json.dumps(roles), "measures": json.dumps(metrics),
                        "problem": ""}, "gold": {}}]


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
    """Item precision: of the finds the model keeps, the share that are true finds (keeping none scores 0)."""
    said = {v.number: v.verdict for v in (getattr(pred, "verdicts", None) or [])}
    kept = [i for i in range(1, len(gold["keep"]) + 1) if said.get(i, "keep") != "drop"]
    if not kept:
        return 0.0 if any(gold["keep"]) else 1.0
    return sum(gold["keep"][i - 1] for i in kept) / len(kept)


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


def metric_query(gold: dict, pred: Any, seen: frozenset[str] = frozenset()) -> float:
    from evidence.planner.plan import query_problem
    q = str(getattr(pred, "query", "") or "")
    return float(query_problem(q) is None and bool(re.search(r"\$(sides|metrics)", q)))


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
    Spec("planner_query", _sig("evidence.planner.plan", "QuerySig"), build_query, metric_query),
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
           seen: frozenset[str] = frozenset()) -> float:
    total = 0.0
    for ex in examples:
        try:
            with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
                total += metric(ex["gold"], program(**ex["inputs"]), seen)
        except Exception:   # an unparseable reply scores 0 (it is recorded as a failed attempt)
            pass
    return total / len(examples) if examples else 0.0


def default_optimizer(name: str, metric: Callable[..., float], lm: RecordedLM) -> Any:
    """GEPA (light cap: max_metric_calls=500) or MIPROv2 (auto light), both on `lm`."""
    def gepa_metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
        return metric(gold.gold, pred)

    def mipro_metric(gold, pred, trace=None):
        return metric(gold.gold, pred)
    if name == "gepa":
        return dspy.GEPA(metric=gepa_metric, max_metric_calls=MAX_METRIC_CALLS, reflection_lm=lm)
    return dspy.MIPROv2(metric=mipro_metric, prompt_model=lm, task_model=lm, auto="light")


def tune(step: str, train: list[Path], test: list[Path], *, lm: RecordedLM, optimizer: str = "gepa",
         make_optimizer: Callable[[str, Callable[..., float], RecordedLM], Any] = default_optimizer,
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
    if not train_ex or not test_ex:
        raise TuneError(f"{step}: {len(train_ex)} train and {len(test_ex)} test examples; both sides need some")
    seen = frozenset(_norm(n) for ex in train_ex for n in ex["gold"].get("names", []))
    calls = {"n": 0}
    ask = lm._ask

    def counting(*a: Any, **k: Any) -> str:
        calls["n"] += 1
        return ask(*a, **k)
    lm._ask = counting
    try:
        signature = spec.signature()
        base = _Program(signature, Step(signature, step).instructions())
        before = {"train": _score(base, train_ex, spec.metric, lm),
                  "test": _score(base, test_ex, spec.metric, lm, seen)}
        with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
            tuned = make_optimizer(optimizer, spec.metric, lm).compile(base, trainset=[_dspy(e) for e in train_ex])
        after = {"train": _score(tuned, train_ex, spec.metric, lm),
                 "test": _score(tuned, test_ex, spec.metric, lm, seen)}
    finally:
        lm._ask = ask
    report = {"instructions": tuned.predict.signature.instructions, "step": step, "optimizer": optimizer,
              "max_metric_calls": MAX_METRIC_CALLS, "model_calls": calls["n"], "model": lm.alias,
              "train_corpora": sorted({s.corpus_id for s in train_src}),
              "test_corpora": sorted({s.corpus_id for s in test_src}),
              "n_train": len(train_ex), "n_test": len(test_ex), "scores": {"before": before, "after": after}}
    out = Path(tuned_dir or TUNED_DIR)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{step}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                      newline="\n")
    return report
