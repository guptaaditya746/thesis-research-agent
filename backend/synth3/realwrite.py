"""The pieces a later step inserts into a renamed real paper: a planted results section and two claim blocks.

Each piece is a `Paper` (text plus where every planted fact sits). The wording comes from small template lists
with no digits and no field words, chosen by a seeded `Random`, so the same seed gives the same text.
"""
from __future__ import annotations

import random
from typing import Literal

from synth2.write import Paper, _Builder
from synth3.spec import DomainSpec
from synth3.world import Study
from synth3.write import _claim_sentence, _fact_claim, results_block

HEADINGS = ("Comparison of the arms", "Additional comparison", "A further comparison between arms")
# `{setting}` is where the comparison was run; it is the planted value.
INTROS = ("This comparison was run at the {setting}.", "The groups in this comparison were followed at the {setting}.",
          "All data for this comparison were collected at the {setting}.")
CAPTIONS = ("Table {table_no}. Results for each arm and measure, split by subset.",
            "Table {table_no}. Counts and means for every group, measure and subset.",
            "Table {table_no}. The measure for each arm, shown subset by subset.")
CLOSERS = ("These values are listed for every arm and every subset.",
           "Each group is reported in the same way for every measure.",
           "The same layout is used for all arms and measures here.")
ABSTRACT_LEADS = ("In short, the comparison of the arms gives these main findings.",
                  "The main findings of the comparison are as follows.",
                  "Looking at each measure, the groups differ in these ways.")
CONCLUSION_LEADS = ("Taken together, the arms compare as follows.",
                    "To sum up, the comparison of the groups shows the following.",
                    "In the end, the evidence on each measure reads like this.")


def planted_section(study: Study, spec: DomainSpec, text_level: str, seed: str, table_no: int) -> Paper:
    rng = random.Random(f"{seed}|section")
    label = {a.id: a for a in spec.arms}
    b = _Builder()
    b.add(f"### {rng.choice(HEADINGS)}\n\n")
    for arm in study.arms:
        b.add(f"{label[arm].label} is {label[arm].description}. ")
    before, after = rng.choice(INTROS).split("{setting}")
    b.add(before)
    b.plant(f"{study.id}.setting", study.setting)
    b.add(after + "\n\n")
    if text_level == "table":
        b.add(rng.choice(CAPTIONS).format(table_no=table_no) + "\n\n")
    results_block(b, study, spec, text_level)
    b.add(rng.choice(CLOSERS))
    return Paper(study.id, "".join(b.parts), tuple(b.placements))


def claims_block(study: Study, spec: DomainSpec, place: Literal["abstract", "conclusion"], seed: str) -> Paper:
    rng = random.Random(f"{seed}|{place}")
    b = _Builder()
    b.add(rng.choice(ABSTRACT_LEADS if place == "abstract" else CONCLUSION_LEADS))
    for key, word in study.claims.items():
        b.add(" ")
        b.plant(_fact_claim(study.id, key, place), _claim_sentence(spec, key, word))
    return Paper(study.id, "".join(b.parts), tuple(b.placements))
