"""Corpus writer and controlled variants (docs/evidence-interfaces.md sections 1 and 2).

One study set is rendered once per difficulty level into `<name>-<level>` plus `<name>-mixed` (levels
round robin over the studies), with the same paper ids everywhere; a mixed paper is byte for byte the
paper of its level's corpus. A study that fails fidelity at any level is left out of every corpus of the
set (so the variants stay comparable) and reported in each fidelity.json.

The manifest holds only {corpus_id, papers: [{id, file, sha256}]}; the corpus id is the set's name plus a
hash of the papers' hashes, so it does not reveal the level (the directory name does, for people; systems
read the manifest).
"""
from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from agent.canonical import canonical_bytes, sha256_hex
from synth import truth, vocab
from synth.fidelity import PaperFidelity
from synth.levels import LEVELS, Plan
from synth.text import Decoy, Placement
from synth.truth import Study

GENERATOR = "synth"
GENERATOR_VERSION = "1"
PACKAGE = Path(__file__).resolve().parent


@dataclass
class Rendered:
    study: Study
    plan: Plan
    text: str
    placements: list[Placement]
    decoys: list[Decoy]
    fidelity: PaperFidelity


class Renderer(Protocol):
    name: str

    def render_all(self, jobs: Sequence[tuple[Study, str]], seed: int) -> dict[tuple[str, str], Rendered]: ...

    def models(self) -> dict[str, Any] | None: ...


def code_sha256() -> str:
    """Hash of the generator's source and prompts (line endings normalised, so a Windows checkout hashes the
    same)."""
    files = sorted([*PACKAGE.glob("*.py"), *PACKAGE.glob("prompts/*.txt")])
    return sha256_hex(canonical_bytes([[p.relative_to(PACKAGE).as_posix(),
                                        hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()]
                                       for p in files]))


def dump(obj: Any) -> bytes:
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def corpus_id(name: str, papers: list[dict[str, str]]) -> str:
    """`<name>-<8 hex>` from the papers' ids and hashes: deterministic, distinct per variant, and nothing
    in it can be traced back to the level, the seed or the renderer."""
    return f"{name}-{sha256_hex(canonical_bytes([[p['id'], p['sha256']] for p in papers]))[:8]}"


def study_truth(r: Rendered) -> dict[str, Any]:
    p, s = r.plan, r.study
    e = s.effect
    return {
        "study_id": s.study_id, "paper": s.study_id, "level": p.level,
        "conditions": [{"id": c.id, "role": c.role, "label": p.cond_name[c.id], "aliases": list(p.cond_aliases[c.id])}
                       for c in p.conditions],
        "metrics": [{"id": k.id, "canonical": k.canonical, "name": p.metric_name[k.id],
                     "higher_is_better": k.higher_is_better} for k in p.metrics],
        "measurements": [{"id": m.id, "condition": m.condition, "metric": m.metric, "value": m.value,
                          "dataset": m.dataset} for m in p.measurements],
        "author_claim": {"id": f"{s.study_id}.a1", "direction": p.claim},
        "effect": {"direction": e.direction, "delta": e.delta, "metric": e.metric, "rag": e.rag,
                   "baseline": e.baseline},
    }


def prepare(directory: Path) -> None:
    """An empty directory to write into; an earlier synth corpus there is replaced, anything else refused."""
    if directory.exists() and any(directory.iterdir()):
        if not (directory / "corpus.json").exists():
            raise SystemExit(f"{directory} is not empty and is not a synth corpus; refusing to overwrite it")
        shutil.rmtree(directory)
    (directory / "papers").mkdir(parents=True)


def write_corpus(directory: Path, *, name: str, level: str, seed: int, renderer: Renderer,
                 studies: list[Study], papers: dict[str, Rendered], failed: dict[str, list[str]]) -> str:
    """Write one corpus; `papers` maps every study id to its rendering for this corpus."""
    prepare(directory)
    kept = [s for s in studies if s.study_id not in failed]
    manifest = []
    for s in kept:
        data = papers[s.study_id].text.encode("utf-8")
        (directory / "papers" / f"{s.study_id}.md").write_bytes(data)
        manifest.append({"id": s.study_id, "file": f"papers/{s.study_id}.md", "sha256": hashlib.sha256(data).hexdigest()})
    cid = corpus_id(name, manifest)
    (directory / "manifest.json").write_bytes(dump({"corpus_id": cid, "papers": manifest}))
    (directory / "corpus.json").write_bytes(dump({
        "corpus_id": cid, "seed": seed,
        "generator": {"name": GENERATOR, "version": GENERATOR_VERSION, "code_sha256": code_sha256()},
        "renderer": renderer.name, "level": level, "question": vocab.QUESTION,
        "papers": [{"id": s.study_id, "study_id": s.study_id, "level": papers[s.study_id].plan.level} for s in kept],
        "models": renderer.models(),
    }))
    placements = sorted((p for s in kept for p in papers[s.study_id].placements),
                        key=lambda p: (p.paper, p.start, p.end, p.role, p.fact))
    (directory / "ground_truth.json").write_bytes(dump({
        "corpus_id": cid, "seed": seed, "question": vocab.QUESTION,
        "studies": [study_truth(papers[s.study_id]) for s in kept],
        "placements": [p.json() for p in placements],
        "answer": truth.answer(kept),
    }))
    records = []
    for s in studies:
        rec = papers[s.study_id].fidelity.json()
        if s.study_id in failed:
            rec["excluded_reason"] = (f"failed fidelity at level(s) {', '.join(failed[s.study_id])}; left out of "
                                      "every corpus of the set so the variants keep the same papers")
        records.append(rec)
    (directory / "fidelity.json").write_bytes(dump({"corpus_id": cid, "papers": records, "excluded": sorted(failed)}))
    (directory / "decoys.json").write_bytes(dump([
        {"paper": s.study_id, "measurement": d.measurement, "stated_value": d.stated_value,
         "true_value": s.value_of(d.measurement), "start": d.start, "end": d.end, "exact": d.exact}
        for s in kept for d in papers[s.study_id].decoys]))
    return cid


def build(*, name: str, seed: int, studies: int, renderer: Renderer, out: Path,
          levels: Sequence[str] = LEVELS, mix: dict[str, float] | None = None) -> dict[str, Any]:
    """Generate the study set, render it at every level, write the level corpora and the mixed one."""
    unknown = [lv for lv in levels if lv not in LEVELS]
    if unknown or not levels:
        raise SystemExit(f"unknown or no levels: {unknown or levels}; choose from {', '.join(LEVELS)}")
    study_set = truth.generate(seed, studies, mix)
    rendered = renderer.render_all([(s, lv) for lv in levels for s in study_set], seed)
    failed: dict[str, list[str]] = {}
    for (sid, lv), r in sorted(rendered.items()):
        if not r.fidelity.ok:
            failed.setdefault(sid, []).append(lv)
    written = {}
    for lv in [*levels, "mixed"]:
        assign = {s.study_id: lv if lv != "mixed" else levels[s.index % len(levels)] for s in study_set}
        papers = {sid: rendered[(sid, a)] for sid, a in assign.items()}
        directory = out / f"{name}-{lv}"
        written[str(directory)] = write_corpus(directory, name=name, level=lv, seed=seed, renderer=renderer,
                                               studies=study_set, papers=papers, failed=failed)
    return {"corpora": written, "excluded": failed, "answer": truth.answer(
        [s for s in study_set if s.study_id not in failed])}
