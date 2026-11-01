"""Counterfactual variant of a built corpus (the supervisor's controlled variant, 14 Oct section 6: change
one study's result and the answer should shift predictably; contract docs/evidence-system.md F3).

`synth variant --corpus DIR --study S --direction D` draws the base corpus's study set again from its
recorded settings, replaces S's treatment/control pair on both datasets with one of direction D (from
`random.Random(f"synth:{seed}:{S}:variant:{D}")`; same ids, names, datasets and distractor values; the claim
follows the new effect, a contradictory-level paper keeps a false claim), re-renders only S's paper at its
level with the same fidelity checks as `build`, re-applies the flags to the whole set, and writes a corpus
whose every other paper is byte for byte the base corpus's (copied, sha256 verified). `variant.json`
records what changed and the expected answer before and after. The base corpus does not hold the
protocol file: `--protocol` (default the recipe's effect protocol) must hash to the base's `protocol.sha256`.
The set is drawn from the recipe corpus.json `recipe` names (a corpus from before generator version 3 names
none: the default pack's), which must still hash to its `sha256`.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

from evidence import protocol as protocol_module
from evidence.protocol import Protocol
from synth import truth
from synth.corpus import GENERATOR, GENERATOR_VERSION, Renderer, code_sha256, corpus_id, dump, prepare, study_flags, study_truth
from synth.recipe import Recipe, default_recipe, effect_protocol_path, load_recipe
from synth.truth import Study


def _read(directory: Path, name: str) -> Any:
    path = directory / name
    if not path.is_file():
        raise SystemExit(f"{directory} is not a synth corpus: {name} is missing")
    return json.loads(path.read_text(encoding="utf-8"))


def base_recipe(meta: dict[str, Any]) -> Recipe:
    """The recipe the base corpus was drawn from (corpus.json `recipe`; none recorded: the default pack's)."""
    recorded = meta.get("recipe")
    if not recorded:
        return default_recipe()
    recipe = load_recipe(recorded["domain"])
    if recipe.sha256 != recorded["sha256"]:
        raise SystemExit(f"domains/{recorded['domain']}/generator.yaml (sha256 {recipe.sha256[:12]}...) is not the "
                         f"recipe the base corpus was drawn from ({recorded['sha256'][:12]}...)")
    return recipe


def base_studies(meta: dict[str, Any], protocol: Protocol) -> list[Study]:
    """The base corpus's study set, drawn again from corpus.json `settings` with the base's protocol and recipe."""
    st = meta.get("settings")
    if not st:
        raise SystemExit("the base corpus.json has no `settings` (built by an older generator); rebuild it first")
    if protocol.sha256 != meta["protocol"]["sha256"]:
        raise SystemExit(f"protocol {protocol.id} (sha256 {protocol.sha256[:12]}...) is not the one the base corpus "
                         f"was built from ({meta['protocol']['id']}, {meta['protocol']['sha256'][:12]}...); pass it "
                         "with --protocol")
    return truth.generate(meta["seed"], st["studies"], st["mix"], protocol.synthesis, recipe=base_recipe(meta),
                          duplicates=st["duplicates"], missing=st["missing"], outliers=st["outliers"],
                          irrelevant=st["irrelevant"], hard=st.get("hard", False))


def counterfactual(seed: int, studies: list[Study], study_id: str, direction: str, spec: protocol_module.Synthesis,
                   ) -> tuple[list[Study], Study, Study]:
    """The set with `study_id` redrawn to `direction` (flags not yet re-applied: `make` does that over the
    studies the corpus holds); plus (before, after)."""
    if direction not in truth.DIRECTIONS:
        raise SystemExit(f"--direction {direction!r}: choose from {', '.join(truth.DIRECTIONS)}")
    before = next((s for s in studies if s.study_id == study_id), None)
    if before is None:
        raise SystemExit(f"--study {study_id}: not in the base corpus's study set")
    if not before.counted:
        why = ("has no experiment" if not before.relevant else f"lacks its {before.missing} measurement"
               if before.missing else f"is a duplicate of {before.duplicate_of}")
        raise SystemExit(f"--study {study_id} {why}; choose a study the answer counts")
    if before.effect.direction == direction:
        raise SystemExit(f"--study {study_id} already has the effect {direction!r}")
    rng = random.Random(f"synth:{seed}:{study_id}:variant:{direction}")
    after = truth.redrawn(rng, before, direction, spec)
    while truth.collides(after, studies):
        after = truth.redrawn(rng, before, direction, spec)
    return [after if s.study_id == study_id else s for s in studies], before, after


def make(*, corpus_dir: Path, study_id: str, direction: str, renderer: Renderer, out: Path | None = None,
         protocol: Protocol | Path | str | None = None) -> dict[str, Any]:
    corpus_dir = Path(corpus_dir)
    meta, gt, manifest = _read(corpus_dir, "corpus.json"), _read(corpus_dir, "ground_truth.json"), _read(corpus_dir, "manifest.json")
    fid, decoys = _read(corpus_dir, "fidelity.json"), _read(corpus_dir, "decoys.json")
    if not isinstance(protocol, Protocol):
        protocol = protocol_module.load(protocol or effect_protocol_path(base_recipe(meta)))
    spec = protocol.synthesis
    seed = meta["seed"]
    studies = base_studies(meta, protocol)
    ids = [p["id"] for p in manifest["papers"]]
    if study_id not in ids:
        raise SystemExit(f"--study {study_id}: not a paper of {corpus_dir} (excluded or unknown)")
    changed, before, after = counterfactual(seed, studies, study_id, direction, spec)
    level = next(p["level"] for p in meta["papers"] if p["id"] == study_id)
    rendered = renderer.render_all([(after, level)], seed)[(study_id, level)]
    if not rendered.fidelity.ok:
        failed = [f"{c.name}: {c.detail}" for c in rendered.fidelity.checks if not c.ok]
        raise SystemExit(f"the counterfactual paper {study_id} failed fidelity at level {level}: " + "; ".join(failed))

    out = Path(out) if out else corpus_dir.parent / f"{corpus_dir.name}-cf-{study_id}-{direction}"
    prepare(out)
    new_manifest = []
    for entry in manifest["papers"]:
        if entry["id"] == study_id:
            data = rendered.text.encode("utf-8")
        else:
            data = (corpus_dir / entry["file"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise SystemExit(f"{corpus_dir / entry['file']} does not match its manifest sha256; the base corpus is damaged")
        (out / "papers" / f"{entry['id']}.md").write_bytes(data)
        new_manifest.append({"id": entry["id"], "file": f"papers/{entry['id']}.md", "sha256": hashlib.sha256(data).hexdigest()})
    name = meta["settings"]["name"]
    cid = corpus_id(f"{name}-cf", new_manifest)
    (out / "manifest.json").write_bytes(dump({"corpus_id": cid, "papers": new_manifest}))
    variant = {"base_corpus_id": meta["corpus_id"], "study": study_id, "from": before.effect.direction, "to": direction}
    (out / "corpus.json").write_bytes(dump({
        **meta, "corpus_id": cid,
        "generator": {"name": GENERATOR, "version": GENERATOR_VERSION, "code_sha256": code_sha256()},
        "recipe": {"domain": after.recipe.domain, "sha256": after.recipe.sha256},
        "renderer": renderer.name, "models": renderer.models(), "variant": variant,
    }))

    # flags re-applied over the studies the corpus holds (the manifest's), as write_corpus does
    kept = truth.flagged([s for s in changed if s.study_id in ids], spec)
    by_id = {s.study_id: s for s in kept}
    base_flags = {s["study_id"]: s["flags"] for s in gt["studies"]}
    flags: dict[str, list[str]] = {}
    records = []
    for record in gt["studies"]:
        sid = record["study_id"]
        if sid == study_id:
            record = study_truth(rendered, spec, by_id[sid])
            flags[sid] = record["flags"]
        else:   # the set-level flags are re-applied; claim_disagrees depends on the paper, which is unchanged
            s = by_id[sid]
            flags[sid] = sorted(set(s.flags) | ({"claim_disagrees"} & set(base_flags[sid])))
            record = {**record, "flags": flags[sid], "duplicate_of": s.duplicate_of}
        records.append(record)
    answer_after = truth.answer(kept, spec, flags)
    placements = [p for p in gt["placements"] if p["paper"] != study_id] + [p.json() for p in rendered.placements]
    placements.sort(key=lambda p: (p["paper"], p["start"], p["end"], p["role"], p["fact"]))
    (out / "ground_truth.json").write_bytes(dump({
        **{k: gt[k] for k in ("seed", "question", "protocol")}, "corpus_id": cid,
        "studies": records, "placements": placements, "answer": answer_after,
    }))
    fidelity_records = [rendered.fidelity.json() if r["id"] == study_id else r for r in fid["papers"]]
    (out / "fidelity.json").write_bytes(dump({"corpus_id": cid, "papers": fidelity_records, "excluded": fid["excluded"]}))
    (out / "decoys.json").write_bytes(dump(
        [d for d in decoys if d["paper"] != study_id]
        + [{"paper": study_id, "measurement": d.measurement, "stated_value": d.stated_value,
            "true_value": after.value_of(d.measurement), "start": d.start, "end": d.end, "exact": d.exact}
           for d in rendered.decoys]))
    before_answer = gt["answer"]
    expected = {"before": {"label": before_answer["label"], "counts": truth.answer_counts(before_answer)},
                "after": {"label": answer_after["label"], "counts": truth.answer_counts(answer_after)}}
    expected["label_changes"] = expected["before"]["label"] != expected["after"]["label"]
    record = {
        **variant, "corpus_id": cid, "paper": study_id,
        "changed": [{"measurement": m.id, "from": before.value_of(m.id), "to": m.value}
                    for m in after.measurements if m.value != before.value_of(m.id)],
        "expected": expected,
    }
    (out / "variant.json").write_bytes(dump(record))
    return {"out": str(out), **record}
