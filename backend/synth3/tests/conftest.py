import pytest
import yaml

from synth3.spec import load_spec


def _authors() -> list[str]:
    firsts = ["Ada", "Ben", "Cleo", "Dev", "Eli", "Fay", "Gus", "Hana"]
    lasts = ["Stone", "Reed", "Marsh", "Cole", "Wells"]
    return [f"{f} {l}" for f in firsts for l in lasts]


def good() -> dict:
    """A valid spec as a plain dict; later tests edit one part and expect a named failure."""
    return {
        "field": "medicine",
        "arms": [
            {"id": "ctrl", "label": "Standard care", "description": "the usual treatment given to every patient", "control": True},
            {"id": "a", "label": "Targeted therapy", "description": "a drug aimed at one pathway"},
            {"id": "b", "label": "Combined therapy", "description": "two drugs given together"},
        ],
        "measures": [
            {"id": "m1", "name": "Response rate", "kind": "count", "higher_is_better": True,
             "effect": [0.10, 0.16], "min_effect": 0.05, "min_gap": 0.10,
             "unit": "participants", "outcome": "responded to treatment", "base_rate": [0.40, 0.55]},
            {"id": "m2", "name": "Relapse rate", "kind": "count", "higher_is_better": False,
             "effect": [0.10, 0.14], "min_effect": 0.05, "min_gap": 0.10,
             "unit": "participants", "outcome": "relapsed within the follow-up", "base_rate": [0.40, 0.50]},
            {"id": "m3", "name": "Systolic pressure", "kind": "value", "higher_is_better": False,
             "effect": [0.08, 0.12], "min_effect": 0.04, "min_gap": 0.08,
             "unit": "mmHg", "base_value": [120.0, 150.0], "spread": 0.15, "decimals": 1},
        ],
        "conditions": [
            {"id": "age", "name": "Age group", "levels": [
                {"id": "young", "name": "Younger patients"}, {"id": "old", "name": "Older patients"}]},
            {"id": "site", "name": "Care site", "from_setting": True, "levels": [
                {"id": "urban", "name": "Urban clinics"}, {"id": "rural", "name": "Rural clinics"}]},
            {"id": "phase", "name": "Trial stage", "levels": [
                {"id": "early", "name": "Early stage"}, {"id": "late", "name": "Late stage"}]},
        ],
        "settings": [
            {"name": "Northern hospital network", "levels": {"site": "urban"}},
            {"name": "Coastal health service", "levels": {"site": "urban"}},
            {"name": "Highland medical trust", "levels": {"site": "rural"}},
            {"name": "Valley care alliance", "levels": {"site": "rural"}},
        ],
        "n_range": [300, 900],
        "n_step": 50,
        "head_to_head_rate": 0.15,
        "overclaim_rate": 0.15,
        "uncovered_rate": 0.4,
        "authors": _authors(),
        "years": [2008, 2023],
    }


def write(dir, d, newline="\n"):
    dir.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(d, sort_keys=False).replace("\n", newline)
    (dir / "demo.yaml").write_bytes(text.encode("utf-8"))
    return dir


@pytest.fixture
def SPEC(tmp_path):
    return load_spec("demo", write(tmp_path, good()))
