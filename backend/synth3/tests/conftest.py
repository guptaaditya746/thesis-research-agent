from dataclasses import replace

import pytest
import yaml

from synth3.realspec import load_real_spec
from synth3.reference import draw_supported_studies
from synth3.spec import load_spec
from synth3.world import draw_world


def approved(SPEC, seed):
    return replace(draw_world(SPEC, seed), approved=True)


def supported(SPEC, seed):
    """The studies of the first supported noise attempt for a drawn world."""
    return draw_supported_studies(SPEC, draw_world(SPEC, seed), seed, 40)[0]


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
             "effect": [0.05, 0.075], "min_effect": 0.025, "min_gap": 0.04,
             "unit": "participants", "outcome": "responded to treatment", "base_rate": [0.40, 0.55]},
            {"id": "m2", "name": "Relapse rate", "kind": "count", "higher_is_better": False,
             "effect": [0.05, 0.075], "min_effect": 0.025, "min_gap": 0.04,
             "unit": "participants", "outcome": "relapsed within the follow-up", "base_rate": [0.40, 0.50]},
            {"id": "m3", "name": "Systolic pressure", "kind": "value", "higher_is_better": False,
             "effect": [0.05, 0.075], "min_effect": 0.025, "min_gap": 0.04,
             "unit": "mmHg", "base_value": [120.0, 150.0], "spread": 0.6, "decimals": 1},
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


@pytest.fixture
def spec_dir(tmp_path):
    return write(tmp_path / "specs", good())


def real_good() -> dict:
    """A valid real-paper config as a plain dict (a `files` source, every field set)."""
    return {
        "source": "files", "query": "", "max_fetch": 600,
        "article_types": ["research-article"], "exclude_title": "protocol|review",
        "min_words": 100, "max_words": 5000, "min_tables": 1,
        "results_heading": r"^results?\b|^findings\b", "conclusion_heading": "conclu|discussion|summary",
        "drop_sections": "acknowledg|funding|conflicts? of interest|competing interests?|declarations?",
        "control_words": "placebo|usual care",
        "keep": ["BP", "eGFR", "WHO", "SD"], "name_stems": ["pril", "dipine"], "name_words": ["chlorthalidone"],
        "n_test": 5,
    }


def write_real(dir, d, newline="\n"):
    dir.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(d, sort_keys=False).replace("\n", newline)
    (dir / "demo.yaml").write_bytes(text.encode("utf-8"))
    return dir


@pytest.fixture
def REAL(tmp_path):
    return load_real_spec("demo", write_real(tmp_path / "real", real_good()))


@pytest.fixture
def REAL_PMC(tmp_path):
    d = real_good()
    d.update(source="pmc", query="hypertension AND open access[filter]")
    return load_real_spec("demo", write_real(tmp_path / "real_pmc", d))


_VOCAB = ("patients trial therapy outcome group measured baseline follow clinic dose weeks result blood pressure "
          "daily visit record sample change average measure study report across period higher lower between "
          "during after before each total central local stable regular observed reported adjusted matched "
          "enrolled assigned treated monitored compared analysed collected reviewed recorded balanced").split()


def _para(rng, n: int) -> str:
    ws = [rng.choice(_VOCAB) for _ in range(n)]
    sentences = [" ".join(ws[k:k + 12]).capitalize() + "." for k in range(0, n, 12)]
    return " ".join(sentences)


def fake_paper(i: int) -> str:
    """A markdown paper of about 1,500 words in paragraphs of 60-100 words; the text varies with `i`."""
    import random
    rng = random.Random(i)
    intro = [_para(rng, 80) for _ in range(7)]
    intro[0] = f"Lisinopril is widely used for blood pressure in Brightford. {intro[0]}"
    intro[1] = f"The HOPE-{i} trial compared lisinopril/amlodipine with usual care. {intro[1]}"
    table = "| Outcome | Drug | Placebo |\n| --- | --- | --- |\n| Events | 12 | 20 |"
    parts = [
        f"# HOPE-{i} trial of blood pressure care", "## Abstract", _para(rng, 70), "## Introduction", *intro,
        "## Methods", *[_para(rng, 90) for _ in range(3)],
        "## Results", _para(rng, 90), "Fewer events occurred than in the placebo group. " + _para(rng, 70),
        "Table 1. Outcomes by group.", table, _para(rng, 90),
        "## Discussion", *[_para(rng, 90) for _ in range(3)],
    ]
    return "\n\n".join(parts) + "\n"


def make_pool(root, n: int, rs):
    """A pool of `n` fake papers with ids P001... added through `add_paper`."""
    from synth3.pmc import PoolPaper
    from synth3.pool import add_paper, save_index
    rows = []
    for i in range(1, n + 1):
        text = fake_paper(i)
        paper = PoolPaper(id=f"P{i:03d}", title=f"HOPE-{i} trial of blood pressure care", year=2015,
                          journal="Demo Journal", license="CC-BY", article_type="research-article", text=text)
        rows.append(add_paper(root, paper, rs))
    save_index(root, rows)
    return root
