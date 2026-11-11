"""Relatives of a base corpus, made by code, each with a known relation to the base answer.

`twin` changes the law on one side, so the answer must change. The others must leave it as it is:
`twin_neutral` (the same side redrawn with new noise only), `spun` (every author claims "helps", counts
untouched) and `duplicate` (one study published twice). A family whose relation does not hold is refused.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from jsonio import write_json_atomic
from synth2.conclude import Answer, pooled
from synth2.corpus import Settings, load_truth, write_corpus
from synth2.recipe import load_recipe
from synth2.world import Law, direction, draw_studies, study_delta

KINDS = ("twin", "twin_neutral", "spun", "duplicate")
RELATION = {"twin": "must_change", "twin_neutral": "must_stay", "spun": "must_stay", "duplicate": "must_stay"}


def make_family(base_dir: Path) -> list[dict]:
    """Write `<base_dir>/../<kind>/` for every kind and return the four variant records."""
    settings = Settings.parse(json.loads((base_dir / "corpus.json").read_text(encoding="utf-8"))["settings"])
    truth = load_truth(base_dir)
    recipe = load_recipe(settings.domain)
    law = Law.parse(truth["law"])
    a, b = (lv.id for c in recipe.conditions if c.id == law.condition for lv in c.levels)

    def draw(with_law: Law, **changes) -> tuple:
        options = {"exact": settings.exact, "noise_seed": settings.noise_seed, "untested": settings.untested}
        return draw_studies(recipe, with_law, settings.seed, settings.studies, **{**options, **changes})

    base = draw(law)
    flipped = -law.effects[b] if law.effects[b] != 0.0 else -law.effects[a]
    twin_law = Law(law.condition, {**law.effects, b: flipped}, f"twin_of_{law.kind}", law.mirrored)
    made = {
        "twin": (twin_law, draw(twin_law)),
        "twin_neutral": (law, draw(law, noise_seed=settings.noise_seed + 1, redraw_level=b)),
        "spun": (law, tuple(replace(s, claim="helps",
                                    overclaims=direction(study_delta(s), recipe.min_effect) != "helps")
                            for s in base)),
        # the copy gets the next free study number: its id must not say that it is a copy
        "duplicate": (law, (*base, replace(base[0], id=f"S{len(base) + 1:03d}",
                                           label=f"{base[0].label}, extended version", duplicate_of=base[0].id))),
    }
    key_before = pooled(base, recipe)
    keys: dict[str, Answer] = {}
    for kind in KINDS:   # check every relation before anything is written
        keys[kind] = pooled(made[kind][1], recipe)
        if (keys[kind] != key_before) != (RELATION[kind] == "must_change"):
            raise ValueError(f"{kind}: relation {RELATION[kind]} does not hold for seed {settings.seed}")
    records = []
    for kind in KINDS:
        record = {"base_corpus_id": truth["corpus_id"], "kind": kind, "relation": RELATION[kind],
                  "key_before": key_before.json(), "key_after": keys[kind].json()}
        out = base_dir.parent / kind
        record["corpus_id"] = write_corpus(out, recipe, made[kind][0], made[kind][1], settings, record)
        write_json_atomic(out / "variant.json", record)
        records.append(record)
    return records
