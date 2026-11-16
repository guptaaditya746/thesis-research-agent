"""A synth3 folder on disk: the papers and manifest a tested system may read, and beside them the truth it may not.

`corpus.json` holds how the folder was made; `ground_truth.json` holds the world, the studies, where every planted
fact sits and the reference facts. `evaluation/truth.py` cannot read this truth; the plan 3 judge reads it directly.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from jsonio import canonical_bytes, sha256_hex, write_json_atomic, write_text_atomic
from synth3.reference import draw_supported_studies, reference_facts
from synth3.spec import DomainSpec
from synth3.world import World
from synth3.write import TEXT_LEVELS, missing_facts, write_paper

GENERATOR = "synth3"
VERSION = 1
PACKAGE = Path(__file__).resolve().parent


def code_sha256() -> str:
    """Hash of the generator's source (line endings normalised, so a Windows checkout hashes the same)."""
    return sha256_hex(canonical_bytes([[p.name, hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()]
                                       for p in sorted(PACKAGE.glob("*.py"))]))


def build_folder(out: Path, spec: DomainSpec, world: World, studies: int, text_level: str) -> str:
    """Write the folder for an approved world and return its id."""
    if not world.approved:
        raise ValueError(f"world {spec.domain}/s{world.seed} is not approved; set approved to true in its file")
    if text_level not in TEXT_LEVELS:
        raise ValueError(f"unknown text level '{text_level}'; known: {', '.join(TEXT_LEVELS)}")
    if studies < 1:
        raise ValueError("a folder needs at least one study")
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"{out} is not empty; choose a new folder")
    drawn, attempt = draw_supported_studies(spec, world, world.seed, studies)
    papers = [write_paper(s, spec, text_level, world.seed) for s in drawn]
    unfaithful = [fact for p, s in zip(papers, drawn) for fact in missing_facts(p, s, spec)]
    if unfaithful:
        raise ValueError(f"papers do not hold their planted facts: {', '.join(unfaithful)}")
    hashes = [[p.study, sha256_hex(p.text.encode("utf-8"))] for p in papers]
    cid = f"{spec.domain}3-{sha256_hex(canonical_bytes(hashes))[:8]}"
    (out / "papers").mkdir(parents=True, exist_ok=True)
    for p in papers:
        write_text_atomic(out / "papers" / f"{p.study}.md", p.text)
    write_json_atomic(out / "manifest.json", {
        "corpus_id": cid,
        "papers": [{"id": sid, "file": f"papers/{sid}.md", "sha256": digest} for sid, digest in hashes]})
    write_json_atomic(out / "corpus.json", {
        "corpus_id": cid,
        "generator": {"name": GENERATOR, "version": VERSION, "code_sha256": code_sha256()},
        "spec": {"domain": spec.domain, "sha256": spec.sha256},
        "settings": {"seed": world.seed, "studies": studies, "text_level": text_level, "attempt": attempt}})
    write_json_atomic(out / "ground_truth.json", {
        "corpus_id": cid,
        "world": world.json(),
        "spec": spec.model_dump(),
        "studies": [s.json() for s in drawn],
        "placements": [{"paper": p.study, "fact": pl.fact, "start": pl.start, "end": pl.end}
                       for p in papers for pl in p.placements],
        "facts": reference_facts(spec, world, drawn)})
    return cid
