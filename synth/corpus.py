"""Corpus writer and controlled variants (docs/evidence-system.md A1 and A2; knobs F2).

One study set is rendered once per difficulty level into `<name>-<level>` plus `<name>-mixed` (levels
round robin over the studies), with the same paper ids everywhere; a mixed paper is byte for byte the
paper of its level's corpus. A study that fails fidelity at any level is left out of every corpus of the
set (so the variants stay comparable) and reported in each fidelity.json.

The manifest holds only {corpus_id, papers: [{id, file, sha256}]}; the corpus id is the set's name plus a
hash of the papers' hashes, so it does not reveal the level (the directory name does, for people; systems
read the manifest).

Our additions (not the supervisor's design): the benchmark knobs `duplicates`, `missing`, `outliers`,
`irrelevant` (truth.with_knobs), recorded in corpus.json `settings`; per-study `relevant`, `flags`,
`duplicate_of`, `missing`; the answer's `undetermined`, `duplicates` and `flags` lists. With `hard`
(truth.hardened; settings `hard: true`) a complex-level study record lists its `experiments` (`synthesis:
true` for the main one, the only one its effect is computed from; the others are distractors) and each
measurement its `experiment`; every measurement is a fact, extraction is scored on all of them.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from jsonio import canonical_bytes, sha256_hex
from evidence import protocol as protocol_module
from evidence import rules
from evidence.protocol import Protocol
from synth import truth
from synth.fidelity import PaperFidelity
from synth.levels import LEVELS, Plan
from synth.text import Decoy, Placement
from synth.truth import Study

GENERATOR = "synth"
GENERATOR_VERSION = "2"      # 2: knobs, flags, relevant/missing/duplicate_of, settings, variants
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


def study_flags(r: Rendered, spec: protocol_module.Synthesis, study: Study | None = None) -> list[str]:
    """The study's flags in this corpus: the set-level ones (duplicate, large_effect; from `study`, the
    study as truth.flagged re-flags it over the studies actually written, default the rendering's) plus
    claim_disagrees where the claim as stated disagrees with the computed direction (contradictory
    papers; never an undetermined study, which has no direction to disagree with)."""
    s = study or r.study
    flags = set(s.flags)
    if s.effect.determined and not rules.claim_agrees(r.plan.claim, s.effect.direction, spec.claim_map):
        flags.add("claim_disagrees")
    return sorted(flags)


def study_truth(r: Rendered, spec: protocol_module.Synthesis, study: Study | None = None) -> dict[str, Any]:
    """The ground-truth record of a rendering; `study` (default the rendering's) carries the set-level
    flags and `duplicate_of` as found over the written set."""
    p, s = r.plan, study or r.study
    e = s.effect
    return {
        "study_id": s.study_id, "paper": s.study_id, "level": p.level,
        "relevant": s.relevant, "flags": study_flags(r, spec, s), "duplicate_of": s.duplicate_of, "missing": s.missing,
        "conditions": [{"id": c.id, "role": c.role, "label": p.cond_name[c.id], "aliases": list(p.cond_aliases[c.id])}
                       for c in p.conditions],
        "metrics": [{"id": k.id, "canonical": k.canonical, "name": p.metric_name[k.id],
                     "higher_is_better": k.higher_is_better} for k in p.metrics],
        "measurements": [{"id": m.id, "condition": m.condition, "metric": m.metric, "value": m.value,
                          "dataset": m.dataset, **({"experiment": m.experiment} if p.experiments else {})}
                         for m in p.measurements],
        **({"experiments": [{"id": x.id, "name": x.name, "conditions": list(x.conditions), "datasets": list(x.datasets),
                             "synthesis": i == 0} for i, x in enumerate(p.experiments)]} if p.experiments else {}),
        "author_claim": {"id": f"{s.study_id}.a1", "direction": p.claim} if s.relevant else None,
        "effect": {"direction": e.direction, "delta": e.delta, "metric": e.metric, "treatment": e.treatment,
                   "control": e.control, **({"reason": e.reason} if e.reason else {})},
    }


def prepare(directory: Path) -> None:
    """An empty directory to write into; an earlier synth corpus there is replaced, anything else refused."""
    if directory.exists() and any(directory.iterdir()):
        if not (directory / "corpus.json").exists():
            raise SystemExit(f"{directory} is not empty and is not a synth corpus; refusing to overwrite it")
        shutil.rmtree(directory)
    (directory / "papers").mkdir(parents=True)


def settings_of(*, name: str, studies: int, mix: dict[str, float] | None, levels: Sequence[str],
                duplicates: int = 0, missing: int = 0, outliers: int = 0, irrelevant: int = 0,
                hard: bool = False) -> dict[str, Any]:
    """corpus.json `settings`: what `build` was asked, enough to draw the same study set again (`synth
    variant` does); `hard` only when set, so a plain build's settings are what they were."""
    return {"name": name, "studies": studies, "mix": dict(mix or truth.DEFAULT_MIX), "levels": list(levels),
            "duplicates": duplicates, "missing": missing, "outliers": outliers, "irrelevant": irrelevant,
            **({"hard": True} if hard else {})}


def write_corpus(directory: Path, *, name: str, level: str, seed: int, renderer: Renderer, protocol: Protocol,
                 studies: list[Study], papers: dict[str, Rendered], failed: dict[str, list[str]],
                 settings: dict[str, Any], extra: dict[str, Any] | None = None,
                 selection: dict[str, Any] | None = None) -> str:
    """Write one corpus; `papers` maps every study id to its rendering for this corpus. The protocol whose
    synthesis block made the ground truth is recorded (id and sha256), never its file. `extra` goes into
    corpus.json as it is (`variant`, F3); `selection` (the fidelity counters of `selection_of`) goes into
    corpus.json (never manifest.json: the engine reads that). The set-level flags are found over the studies actually written
    (after the fidelity exclusions), as the engine finds them over the papers it reads."""
    prepare(directory)
    spec = protocol.synthesis
    kept = truth.flagged([s for s in studies if s.study_id not in failed], spec)
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
        "renderer": renderer.name, "level": level, "question": protocol.question,
        "protocol": {"id": protocol.id, "sha256": protocol.sha256},
        "papers": [{"id": s.study_id, "study_id": s.study_id, "level": papers[s.study_id].plan.level} for s in kept],
        "models": renderer.models(),
        "settings": settings,
        **({"selection": selection} if selection else {}),
        **(extra or {}),
    }))
    placements = sorted((p for s in kept for p in papers[s.study_id].placements),
                        key=lambda p: (p.paper, p.start, p.end, p.role, p.fact))
    (directory / "ground_truth.json").write_bytes(dump({
        "corpus_id": cid, "seed": seed, "question": protocol.question,
        "protocol": {"id": protocol.id, "sha256": protocol.sha256},
        "studies": [study_truth(papers[s.study_id], spec, s) for s in kept],
        "placements": [p.json() for p in placements],
        "answer": truth.answer(kept, spec, {s.study_id: study_flags(papers[s.study_id], spec, s) for s in kept}),
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


def level_of(study: Study, studies: list[Study], levels: Sequence[str]) -> str:
    """The level a study takes in the mixed corpus: round robin over the levels by its index; a duplicate
    takes its original's level (F2: a second report at the original's level)."""
    if study.duplicate_of:
        original = next(s for s in studies if s.study_id == study.duplicate_of)
        return level_of(original, studies, levels)
    return levels[study.index % len(levels)]


def exclusions(rendered: dict[tuple[str, str], Rendered], studies: list[Study]) -> dict[str, list[str]]:
    """Study id -> the levels it failed fidelity at; a duplicate of an excluded study is excluded too (its
    `duplicate_of` would point at a paper that is not there)."""
    failed: dict[str, list[str]] = {}
    for (sid, lv), r in sorted(rendered.items()):
        if not r.fidelity.ok:
            failed.setdefault(sid, []).append(lv)
    for s in studies:
        if s.duplicate_of in failed and s.study_id not in failed:
            failed[s.study_id] = [f"(its original {s.duplicate_of} failed)"]
    return failed


def selection_of(rendered: dict[tuple[str, str], Rendered], study_set: list[Study], requested: int,
                 failed: dict[str, list[str]]) -> dict[str, Any]:
    """What fidelity left of the request: study counts (`records` includes the knob papers; the first
    `requested` studies are the base set), per level the papers passed, the failing check names of the final
    attempt of each failed paper, and the mean attempts; and the excluded studies with their levels."""
    per_level: dict[str, dict[str, Any]] = {}
    for (sid, lv), r in sorted(rendered.items()):
        row = per_level.setdefault(lv, {"passed": 0, "failed_checks": {}, "mean_attempts": 0.0, "n": 0})
        row["n"] += 1
        row["mean_attempts"] += r.fidelity.attempts
        if r.fidelity.ok:
            row["passed"] += 1
        for c in r.fidelity.checks:
            if not r.fidelity.ok and not c.ok:
                row["failed_checks"][c.name] = row["failed_checks"].get(c.name, 0) + 1
    for row in per_level.values():
        row["mean_attempts"] = round(row["mean_attempts"] / row.pop("n"), 3)
    return {"requested_studies": requested, "records": len(study_set),
            "retained_studies": sum(s.study_id not in failed for s in study_set[:requested]),
            "per_level": per_level, "excluded": dict(failed)}


def build(*, name: str, seed: int, studies: int, renderer: Renderer, out: Path,
          levels: Sequence[str] = LEVELS, mix: dict[str, float] | None = None,
          protocol: Protocol | Path | str | None = None, duplicates: int = 0, missing: int = 0,
          outliers: int = 0, irrelevant: int = 0, hard: bool = False) -> dict[str, Any]:
    """Generate the study set for the protocol's question (its synthesis block gives the roles, metrics,
    neutral band, claim vocabulary and label table; default domains/rag/protocols/rag-factuality.yaml), apply
    the knobs (and `hard`), render it at every level, write the level corpora and the mixed one."""
    unknown = [lv for lv in levels if lv not in LEVELS]
    if unknown or not levels:
        raise SystemExit(f"unknown or no levels: {unknown or levels}; choose from {', '.join(LEVELS)}")
    if not isinstance(protocol, Protocol):
        protocol = protocol_module.load(protocol or truth.DEFAULT_PROTOCOL)
    settings = settings_of(name=name, studies=studies, mix=mix, levels=levels, duplicates=duplicates,
                           missing=missing, outliers=outliers, irrelevant=irrelevant, hard=hard)
    study_set = truth.generate(seed, studies, mix, protocol.synthesis, duplicates=duplicates, missing=missing,
                               outliers=outliers, irrelevant=irrelevant, hard=hard)
    rendered = renderer.render_all([(s, lv) for lv in levels for s in study_set], seed)
    failed = exclusions(rendered, study_set)
    selection = selection_of(rendered, study_set, studies, failed)
    written = {}
    for lv in [*levels, "mixed"]:
        assign = {s.study_id: lv if lv != "mixed" else level_of(s, study_set, levels) for s in study_set}
        papers = {sid: rendered[(sid, a)] for sid, a in assign.items()}
        directory = out / f"{name}-{lv}"
        written[str(directory)] = write_corpus(directory, name=name, level=lv, seed=seed, renderer=renderer,
                                               protocol=protocol, studies=study_set, papers=papers, failed=failed,
                                               settings=settings, selection=selection)
    kept = truth.flagged([s for s in study_set if s.study_id not in failed], protocol.synthesis)
    flags = {s.study_id: study_flags(papers[s.study_id], protocol.synthesis, s) for s in kept}   # the mixed corpus's
    return {"corpora": written, "excluded": failed, "protocol": {"id": protocol.id, "sha256": protocol.sha256},
            "settings": settings, "selection": selection, "answer": truth.answer(kept, protocol.synthesis, flags)}
