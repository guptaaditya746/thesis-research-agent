"""A synth3 folder built from renamed real papers: the same truth as the template build of the same approved world,
plus one top-level key `real` that records which source paper each study came from.

Beside the truth, `real/maps/<sid>.json` holds the real names and the invented names that replaced them (private:
never published) and `real/inserted/<sid>.json` the three blocks we inserted.
"""
from __future__ import annotations

from pathlib import Path

from jsonio import canonical_bytes, sha256_hex, write_json_atomic
from synth3.corpus import check_build, write_folder
from synth3.pool import folder_sources, load_split, source_order
from synth3.realspec import RealSpec
from synth3.realwrite import RealPaper, _words, edit_study
from synth3.reference import draw_supported_studies
from synth3.spec import DomainSpec
from synth3.world import World

MAX_SOURCES = 3   # builder's call: sources tried per study before the build stops


def build_real_folder(out: Path, spec: DomainSpec, world: World, studies: int, text_level: str, rs: RealSpec,
                      pool: Path) -> str:
    """Write the real folder for an approved world and return its id `<domain>3r-<8 hex>`. Each study takes the
    next unused source of this folder's order; a source with problems is replaced by the next one, at most
    MAX_SOURCES per study. Nothing is written before every paper passes."""
    check_build(out, spec, world, studies, text_level)
    split = load_split(pool)
    order = folder_sources(source_order(split, rs.domain), world.seed, studies)
    drawn, attempt = draw_supported_studies(spec, world, world.seed, studies)
    nxt = 0
    chosen: dict[str, tuple[str, RealPaper]] = {}
    rejected: dict[str, list[dict]] = {}
    for study in drawn:
        tries: list[tuple[str, RealPaper]] = []
        while len(tries) < MAX_SOURCES and nxt < len(order):
            source_id, nxt = order[nxt], nxt + 1
            source = (pool / "full" / f"{source_id}.md").read_text(encoding="utf-8")
            rp = edit_study(source, study, spec, rs, text_level, f"synth3:{world.seed}:real:{study.id}:{source_id}")
            tries.append((source_id, rp))
            if not rp.problems:
                break
        if not tries or tries[-1][1].problems:
            why = "; ".join(f"{sid} ({rp.problems[0]})" for sid, rp in tries) or "none left"
            raise ValueError(f"{study.id}: no clean source in {len(tries)} tries "
                             f"(at most {MAX_SOURCES}, {len(order)} in the order): {why}")
        chosen[study.id] = tries[-1]
        if len(tries) > 1:
            rejected[study.id] = [{"source": sid, "problem": rp.problems[0]} for sid, rp in tries[:-1]]
    real = {
        "real_spec_sha256": rs.sha256,
        "split_sha256": sha256_hex(canonical_bytes(split)),
        "sources": {sid: source_id for sid, (source_id, _) in chosen.items()},
        "rejected": rejected,
        "words": {sid: _words(rp.paper.text) for sid, (_, rp) in chosen.items()},
        "inserted_words": {sid: sum(_words(t) for t in rp.inserted) for sid, (_, rp) in chosen.items()},
    }
    papers = [chosen[s.id][1].paper for s in drawn]
    settings = {"seed": world.seed, "studies": studies, "text_level": text_level, "real": True}
    cid = write_folder(out, spec, world, drawn, attempt, papers, settings, "3r", {"real": real})
    for sid, (_, rp) in chosen.items():
        write_json_atomic(out / "real" / "maps" / f"{sid}.json", rp.mapping)
        abstract, section, conclusion = rp.inserted
        write_json_atomic(out / "real" / "inserted" / f"{sid}.json",
                          {"seed": rp.seed, "abstract": abstract, "section": section, "conclusion": conclusion})
    return cid
