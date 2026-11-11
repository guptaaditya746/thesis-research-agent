import pytest
import yaml
from synth2.recipe import RECIPES, load_recipe


def test_rag_recipe_loads():
    r = load_recipe("rag")
    assert [c.id for c in r.conditions] == ["fact_rarity", "model_size", "question_length"]
    assert [lv.id for lv in r.conditions[0].levels] == ["rare", "common"]
    assert r.min_effect == 0.01 and r.min_gap == 0.05
    assert len(r.sha256) == 64


def _copy(tmp_path, **changes):
    data = yaml.safe_load((RECIPES / "rag.yaml").read_text(encoding="utf-8"))
    data.update(changes)
    (tmp_path / "rag.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return tmp_path


def test_refuses_a_name_inside_another(tmp_path):
    data = yaml.safe_load((RECIPES / "rag.yaml").read_text(encoding="utf-8"))
    data["conditions"][1]["levels"][1]["name"] = "very compact generator"
    (tmp_path / "rag.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="compact generator"):
        load_recipe("rag", tmp_path)


def test_refuses_an_unknown_key(tmp_path):
    with pytest.raises(ValueError, match="overclaim_rate"):
        load_recipe("rag", _copy(tmp_path, overclaim_rate=0.25))


def test_refuses_too_few_authors(tmp_path):
    with pytest.raises(ValueError, match="authors"):
        load_recipe("rag", _copy(tmp_path, authors=["Okafor"]))


def test_missing_recipe_names_the_path(tmp_path):
    with pytest.raises(ValueError, match="nope.yaml"):
        load_recipe("nope", tmp_path)


@pytest.mark.parametrize("changes, word", [
    ({"datasets": ["HotpotQA 2018"]}, "digit"),
    ({"metric": "accuracy | recall"}, r"\|"),
    ({"unit": ""}, "unit"),
    ({"metric": "accuracy on rare items"}, "rare"),
    ({"n_range": [210, 1000]}, "n_range"),
    ({"min_effect": -1.0}, "min_effect"),
    ({"base_rate": [0.9, 1.5]}, "base_rate"),
    ({"effect": [0.0, 0.0]}, "effect"),
])
def test_refuses_text_and_numbers_that_would_spoil_the_papers(tmp_path, changes, word):
    with pytest.raises(ValueError, match=word):
        load_recipe("rag", _copy(tmp_path, **changes))
