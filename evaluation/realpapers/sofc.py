"""SOFC-Exp checks (materials science, Friedrich et al., ACL 2020; spec 6.12): can the labels rank materials, and does
the experiment map find the experiments the annotators marked?

Layout assumed (UNVERIFIED until the release is opened; `_read` is the one reader to change), a simplified JSON:
  sofc.json  {"papers": [{"id", "text": str | null,
                          "values": [{"value": float, "unit": str, "material": str | null, "measure": str | null}],
                          "experiments": [{"id", "slots": {"material": str, "device": str, ...}}]}]}
`values` are the annotated numbers with the material and the measured quantity they are linked to; `experiments` are
the annotators' experiment frames (an experiment-evoking word and its filled slots). A paper with no open full text
(`text` null) is left out and counted ("left out: N of M (no open full text)").

`label_check`: step 1. Are the values linked to a material AND a measure, so a ranking is possible? If not, only the
experiment-frame check applies and `questions` returns nothing.
`questions`: per measure with values of at least two materials, "Which material gives the highest <measure>?"
(kind rank, field `materials`; gold = the materials ordered by their best value, highest first; every measure is read
as higher-is-better, which the question text states).
`experiment_frames` / `score_experiments`: the gold experiments per paper, and the match of a run's experiment map
(Experiment records of evidence.records, or dicts with `document`, `label`, `setting`).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evidence.names import clean

from ..wholerun import RealQuestion, left_out_line

SOURCE_FILE = "sofc.json"


def _read(src: Path) -> list[dict[str, Any]]:
    return json.loads((Path(src) / SOURCE_FILE).read_text(encoding="utf-8"))["papers"]


def _open(src: Path) -> list[dict[str, Any]]:
    return [p for p in _read(src) if str(p.get("text") or "").strip()]


def left_out(src: Path) -> str:
    papers = _read(src)
    return left_out_line(len(papers) - len(_open(src)), len(papers))


def label_check(src: Path) -> dict[str, Any]:
    """{"complete": bool, "why": str}: every annotated value names a material and a measure."""
    values = [v for p in _read(src) for v in p.get("values", [])]
    if not values:
        return {"complete": False, "why": "no annotated values; only the experiment-frame check applies"}
    bad = [v for v in values if not v.get("material") or not v.get("measure")]
    if bad:
        return {"complete": False, "why": f"{len(bad)} of {len(values)} values lack a material or a measure link; "
                                          "only the experiment-frame check applies"}
    return {"complete": True, "why": f"all {len(values)} values are linked to a material and a measure"}


def questions(src: Path, corpus_dir: Path | None = None) -> list[RealQuestion]:
    """Rank questions per measure (see the module docstring); empty when `label_check` is not complete."""
    if not label_check(src)["complete"]:
        return []
    by_measure: dict[str, dict[str, tuple[float, set[str]]]] = {}
    for paper in _open(src):
        for v in paper.get("values", []):
            best, docs = by_measure.setdefault(str(v["measure"]), {}).get(str(v["material"]), (float("-inf"), set()))
            by_measure[str(v["measure"])][str(v["material"])] = (max(best, float(v["value"])), docs | {str(paper["id"])})
    corpus = Path(corpus_dir) if corpus_dir is not None else Path(src) / "corpus"
    out = []
    for measure in sorted(by_measure):
        materials = by_measure[measure]
        if len(materials) < 2:
            continue
        ranking = sorted(materials, key=lambda m: (-materials[m][0], m))
        out.append(RealQuestion(
            id=f"sofc-{len(out) + 1:03d}", question=f"Which material gives the highest {measure}?", field="materials",
            corpus_dir=corpus, kind="rank",
            gold={"ranking": ranking, "papers": sorted(set().union(*(d for _, d in materials.values()))),
                  "measure": measure}))
    return out


def experiment_frames(src: Path) -> dict[str, list[dict[str, Any]]]:
    """The gold experiments per paper: [{"id", "slots": {slot: value}}], papers with open text only."""
    return {str(p["id"]): [dict(e) for e in p.get("experiments", [])] for p in _open(src)}


def _setting_of(exp: Any) -> tuple[str, list[str]]:
    get = (lambda k: exp.get(k)) if isinstance(exp, dict) else (lambda k: getattr(exp, k, None))
    values = [str(v) for v in (get("setting") or {}).values()] + [str(get("label") or "")]
    return str(get("document")), [clean(v) for v in values if v.strip()]


def score_experiments(run: Any, src: Path) -> dict[str, Any]:
    """The run's experiment map (`run.experiments`, or a list) against the gold frames. A frame is found when some
    run experiment of the same paper has every slot value of the frame (cleaned) among its setting values or label;
    a run experiment is right when it matches some frame. Reports recall, precision and the share of papers with the
    right number of experiments."""
    experiments = list(getattr(run, "experiments", run))
    frames = experiment_frames(src)
    mapped: dict[str, list[list[str]]] = {}
    for exp in experiments:
        doc, values = _setting_of(exp)
        mapped.setdefault(doc, []).append(values)

    def covers(values: list[str], frame: dict[str, Any]) -> bool:
        wanted = [clean(str(v)) for v in frame["slots"].values() if str(v).strip()]
        return bool(wanted) and all(any(w in have or have in w for have in values) for w in wanted)

    found = sum(any(covers(v, f) for v in mapped.get(doc, [])) for doc, fs in frames.items() for f in fs)
    total = sum(len(fs) for fs in frames.values())
    right = sum(any(covers(v, f) for f in frames.get(doc, [])) for doc, vs in mapped.items() for v in vs)
    n_run = sum(len(vs) for vs in mapped.values())
    counts = sum(len(mapped.get(doc, [])) == len(fs) for doc, fs in frames.items())
    return {"recall": found / total if total else None, "precision": right / n_run if n_run else None,
            "frames": total, "run_experiments": n_run,
            "count_agreement": counts / len(frames) if frames else None}
