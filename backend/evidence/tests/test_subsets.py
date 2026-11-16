"""Subsets (protocol `synthesis.moderators`): a measurement names the group it was measured on, a study gets one
cell per group, and the answer may conclude "depends on one condition" from the evidence pooled per level."""
from __future__ import annotations

import pytest

from agent.anchor import selector_at
from evidence import protocol as protocol_module, rules, synthesis
from evidence.contract import Item, Span
from evidence.pack import DOMAINS

PROTOCOLS = DOMAINS / "rag" / "protocols"
SUBSETS = PROTOCOLS / "rag-factuality-subsets.yaml"
CONDITIONS = (("fact_rarity", ("rare", "common")), ("model_size", ("small", "large")),
              ("question_length", ("short", "long")))
TEXT = "x" * 4000


def span(role: str, start: int) -> Span:
    return Span.of(role, selector_at(TEXT, start, start + 3, file="papers/P.md"))


def paper(cells: list[tuple[dict, tuple[int, int], tuple[int, int]]], claim: str = "improves",
          offset: int = 0) -> list[Item]:
    """The items of one paper: a rag and a baseline condition, the accuracy metric, per cell (levels, (k, n) of
    rag, (k, n) of the baseline) two measurements in document order, and the author claim."""
    rag = Item.build("condition", {"label": "RAG", "role": "rag"}, [span("condition_label", offset)])
    base = Item.build("condition", {"label": "closed-book", "role": "baseline"}, [span("condition_label", offset + 10)])
    metric = Item.build("metric", {"name": "accuracy", "canonical": "factual_accuracy", "higher_is_better": True},
                        [span("metric_label", offset + 20)])
    items = [rag, base, metric]
    for j, (levels, (k_t, n_t), (k_c, n_c)) in enumerate(cells):
        for arm, (k, n), start in ((rag, (k_t, n_t), 100), (base, (k_c, n_c), 110)):
            items.append(Item.build("measurement", {"value": k / n, "dataset": "D", "total": n, **levels},
                                    [span("value", offset + start + 40 * j)],
                                    links={"condition": arm.item_id, "metric": metric.item_id}))
    items.append(Item.build("author_claim", {"direction": claim}, [span("claim", offset + 900)]))
    return items


def levels(rarity: str | None = None, size: str | None = None, length: str | None = None) -> dict:
    return {"fact_rarity": rarity, "model_size": size, "question_length": length}


def test_the_subsets_protocol_declares_its_moderators_and_the_old_protocol_keeps_its_hash() -> None:
    new = protocol_module.load(SUBSETS)
    mods = new.synthesis.moderators
    assert [(c.id, tuple(lv.id for lv in c.levels)) for c in mods.conditions] == list(CONDITIONS)
    assert (mods.total, mods.min_gap) == ("total", 0.05)
    old = protocol_module.load(PROTOCOLS / "rag-factuality.yaml")
    assert old.synthesis.moderators is None
    assert old.sha256 == "4dafc4a33588e55744eaf32a60c600e3fc4c39121557b13f9473f02d78f2d11f"


def test_a_moderator_that_is_no_measurement_field_is_refused() -> None:
    text = SUBSETS.read_text(encoding="utf-8").replace("- id: model_size\n", "- id: model_width\n")
    with pytest.raises(ValueError, match="model_width"):
        protocol_module.parse(text)


def test_pooled_delta_adds_counts_and_falls_back_to_the_mean_of_the_values() -> None:
    # 60/100 and 90/300 pooled: 150/400 against 50/100 and 60/300: 110/400
    assert rules.pooled_delta([(0.6, 100, 0.5, 100), (0.3, 300, 0.2, 300)]) == 150 / 400 - 110 / 400
    assert rules.pooled_delta([(0.6, None, 0.5, 100), (0.3, 300, 0.2, 300)]) == pytest.approx(0.45 - 0.35)
    assert [rules.pooled_direction(d, 0.01) for d in (0.01, 0.0099, -0.01, 0.0)] == [
        "supports", "neutral", "contradicts", "neutral"]


def test_moderated_finds_the_condition_whose_levels_differ_most() -> None:
    cells = [(levels("rare", "small", "short"), (0.70, 100, 0.50, 100)),
             (levels("rare", "large", "long"), (0.72, 100, 0.50, 100)),
             (levels("common", "small", "long"), (0.50, 100, 0.50, 100)),
             (levels("common", "large", "short"), (0.51, 100, 0.51, 100))]
    out = rules.moderated(cells, CONDITIONS, 0.01, 0.05)
    assert (out["verdict"], out["condition"]) == ("depends", "fact_rarity")
    assert out["sides"] == {"rare": "supports", "common": "neutral"} and out["untested"] == []


def test_moderated_gives_one_direction_when_no_condition_splits_the_evidence() -> None:
    cells = [(levels("rare", "small", "short"), (0.70, 100, 0.50, 100)),
             (levels("common", "large", "long"), (0.69, 100, 0.50, 100))]
    out = rules.moderated(cells, CONDITIONS, 0.01, 0.05)
    assert (out["verdict"], out["condition"], out["sides"]) == ("supported", None, {})
    assert rules.moderated([], CONDITIONS, 0.01, 0.05)["verdict"] == "insufficient"


def test_moderated_lists_the_levels_no_cell_was_measured_on() -> None:
    cells = [(levels("rare", "small", None), (0.70, 100, 0.50, 100))]
    out = rules.moderated(cells, CONDITIONS, 0.01, 0.05)
    assert out["untested"] == ["fact_rarity.common", "model_size.large", "question_length.long",
                               "question_length.short"]


def test_a_study_with_two_subsets_gets_two_cells_and_its_own_pooled_direction() -> None:
    protocol = protocol_module.load(SUBSETS)
    items = paper([(levels("rare", "small", "short"), (70, 100), (50, 100)),
                   (levels("common", "small", "short"), (40, 100), (50, 100))])
    entry, used = synthesis.study(protocol, "P", items)
    assert [c["subset"] for c in entry["cells"]] == [levels("rare", "small", "short"), levels("common", "small", "short")]
    assert [c["direction"] for c in entry["cells"]] == ["supports", "contradicts"]
    assert [round(c["delta"], 6) for c in entry["cells"]] == [0.2, -0.1]
    assert (entry["direction"], round(entry["delta"], 6)) == ("supports", 0.05)   # 110/200 against 100/200
    assert entry["treatment"] == entry["cells"][0]["treatment"] and entry["treatment"]["total"] == 100
    measurements = {i.item_id for i in items if i.evidence_type == "measurement"}
    assert measurements <= set(used)
    assert entry["author_claim"]["agrees_with_data"] is True


def test_values_of_two_subsets_are_never_paired_across_them() -> None:
    protocol = protocol_module.load(SUBSETS)
    items = paper([(levels("rare"), (70, 100), (50, 100)), (levels("common"), (40, 100), (50, 100))])
    by_id = {i.item_id: i for i in items}
    entry, _ = synthesis.study(protocol, "P", items)
    for cell in entry["cells"]:
        t, c = by_id[cell["treatment"]["measurement"]], by_id[cell["control"]["measurement"]]
        assert t.fields["fact_rarity"] == c.fields["fact_rarity"] == cell["subset"]["fact_rarity"]


def test_the_old_protocol_keeps_its_answer_shape() -> None:
    old = protocol_module.load(PROTOCOLS / "rag-factuality.yaml")
    items = paper([(levels("rare"), (70, 100), (50, 100)), (levels("common"), (40, 100), (50, 100))])
    answer, _ = synthesis.answer(old, ["P"], {"P": items})
    assert "conclusion" not in answer and "cells" not in answer["studies"][0]
    assert set(answer["studies"][0]["treatment"]) == {"condition", "measurement", "value"}


def test_the_answer_concludes_depends_from_the_cells_of_every_counted_study() -> None:
    protocol = protocol_module.load(SUBSETS)
    docs = {"A": paper([(levels("rare", "small", "short"), (70, 100), (50, 100)),
                        (levels("common", "small", "short"), (40, 100), (50, 100))]),
            "B": paper([(levels("rare", "large", "long"), (150, 200), (100, 200))]),
            "C": paper([(levels("common", "large", "long"), (90, 200), (110, 200))], claim="worsens")}
    answer, _ = synthesis.answer(protocol, list(docs), docs)
    assert answer["conclusion"]["verdict"] == "depends" and answer["conclusion"]["condition"] == "fact_rarity"
    assert answer["conclusion"]["sides"] == {"rare": "supports", "common": "contradicts"}
    assert answer["conclusion"]["untested"] == []
    assert answer["label"] == "mixed" and answer["counts"]["supporting"] == 2   # the per-study table is as before


def test_a_copied_study_is_not_pooled_twice() -> None:
    protocol = protocol_module.load(SUBSETS)
    one = [(levels("rare", "small", "short"), (70, 100), (50, 100))]
    other = [(levels("common", "small", "short"), (51, 100), (50, 100))]
    docs = {"A": paper(one), "B": paper(other), "C": paper(one, offset=1000)}
    answer, _ = synthesis.answer(protocol, list(docs), docs)
    assert answer["duplicates"] == ["C"]
    table = next(c for c in answer["conclusion"]["conditions"] if c["condition"] == "fact_rarity")
    assert table["levels"]["rare"]["cells"] == 1


def test_a_paper_without_a_pair_has_no_cells_and_the_answer_is_insufficient() -> None:
    protocol = protocol_module.load(SUBSETS)
    entry, _ = synthesis.study(protocol, "P", [])
    assert entry["direction"] == "undetermined" and entry["cells"] == []
    answer, _ = synthesis.answer(protocol, ["P"], {"P": []})
    assert answer["conclusion"]["verdict"] == "insufficient"


def test_a_study_called_neutral_is_left_out_of_the_large_effect_median() -> None:
    # 57/100 against 56/100 is 0.00999... as counted: neutral. Its delta is shown rounded (0.01), and must still not
    # enter the median of the non-neutral effects (with it the cut would fall to 0.15 and flag D's 0.16)
    protocol = protocol_module.load(SUBSETS)
    docs = {name: paper([(levels("rare", "small", "short"), (k_t, 100), (k_c, 100))], offset=1000 * n)
            for n, (name, k_t, k_c) in enumerate((("A", 57, 56), ("B", 54, 50), ("C", 56, 50), ("D", 66, 50)))}
    answer, _ = synthesis.answer(protocol, list(docs), docs)
    assert answer["studies"][0]["direction"] == "neutral" and answer["studies"][0]["delta"] == 0.01
    assert answer["flags"]["large_effect"] == []


def test_a_regex_only_run_of_the_subsets_protocol_gives_one_overall_answer(tmp_path) -> None:
    # the regex extractors read no subset and no total: every cell is of an unknown group, so the engine can only
    # pool everything into one direction and must call every level untested
    from .conftest import regex_run
    head = "# T\n\n## Setup\n\nWe compare a closed-book baseline (B) with its retrieval-augmented variant (R).\n\n## Results\n\n"
    table = "| System | Dataset | Accuracy (%) |\n|---|---|---|\n| B | NQ | 60.0 |\n| R | NQ | 70.0 |\n"
    answer, items = regex_run({"T": head + table}, tmp_path, protocol=SUBSETS)
    study = answer["studies"][0]
    assert study["direction"] == "supports" and len(study["cells"]) == 1
    assert study["cells"][0]["subset"] == levels() and study["treatment"]["total"] is None
    assert (study["treatment"]["value"], study["control"]["value"]) == (0.7, 0.6)
    conclusion = answer["conclusion"]
    assert (conclusion["verdict"], conclusion["condition"], conclusion["sides"]) == ("supported", None, {})
    assert len(conclusion["untested"]) == 6


def test_the_llm_extractor_is_asked_for_the_subset_and_the_total_of_every_value() -> None:
    # no extractor code changes: the reply type and the instructions come from the protocol's measurement schema
    from evidence.engine import build_extractors
    protocol = protocol_module.load(SUBSETS)
    llm = next(ex for ref, ex in build_extractors(protocol)["measurement"] if ref.name == "llm_measurement")
    row = {"fields": {"value": 0.512, "dataset": "FactProbe", "form": "k_of_n", "total": 650, "fact_rarity": "rare",
                      "model_size": None, "question_length": "short"},
           "links": {"condition": "c1", "metric": "k1"},
           "quotes": {"value": "333 / 650", "condition_label": None, "metric_label": None, "value_total": "650"}}
    reply = llm.output_type.model_validate({"items": [row]})
    assert reply.items[0].fields.fact_rarity == "rare" and reply.items[0].fields.model_size is None
    with pytest.raises(ValueError):
        llm.output_type.model_validate({"items": [{**row, "fields": {**row["fields"], "fact_rarity": "medium"}}]})
    for words in ("fact_rarity", "model_size", "question_length", "the number of questions the value was measured on",
                  "a sentence about the whole experiment"):
        assert words in " ".join(llm.instructions.split())
    old = protocol_module.load(PROTOCOLS / "rag-factuality.yaml")
    plain = next(ex for ref, ex in build_extractors(old)["measurement"] if ref.name == "llm_measurement")
    assert "fact_rarity" not in plain.instructions and plain.spec.extractor_id != llm.spec.extractor_id
