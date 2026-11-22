"""export-workbench (paperfactory/workbench.py) + the Workbench's reading of it (evqa/seed/pfview.py)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperfactory import workbench
from paperfactory.text import normalize_paper

MD = "# A Study of Things\n\n## Abstract\n\n**Kor v. Bel** relied on *section 1*. Nothing else here.\n"


def _run(tmp: Path) -> Path:
    run = tmp / "run"
    (run / "work" / "P-01").mkdir(parents=True)
    (run / "work" / "P-01" / "paper.md").write_text(MD, encoding="utf-8")
    (run / "work" / "P-02").mkdir(parents=True)   # not in tagged.json: failed the check, never copied
    (run / "papers" / "P-01").mkdir(parents=True)
    for b in workbench.BRIEFS:
        (run / "papers" / "P-01" / b).write_text(f"brief {b}", encoding="utf-8")
    (run / "seed.ttl").write_text("# seed\n", encoding="utf-8")
    ents = {"D1": {"label": "Kor v. Bel"}, "D2": {"label": "Ab v. Cd"}, "P1": {"label": "section 1"}}
    papers = {"P-01": {"title_hint": "x", "claims": [["D1", "relies_on", "P1"]], "decoys": [["D2", "relies_on", "P1"]]},
              "P-02": {"title_hint": "y", "claims": [], "decoys": []}}
    (run / "world.json").write_text(json.dumps({"field": "law", "genre": "argument", "entities": ents,
                                                "papers": papers}), encoding="utf-8")
    norm = normalize_paper(MD).text
    a = norm.index("Kor v. Bel")
    b = norm.index("section 1.") + len("section 1.")
    tagged = {"papers": {"P-01": {"spans": {"D1-relies_on-P1": [[a, b]]}, "sentences": [[a, b, norm[a:b]]]}}}
    (run / "tagged.json").write_text(json.dumps(tagged), encoding="utf-8")
    return run


def test_export_and_view(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    assert workbench.export(_run(tmp_path), "pf_law", data) == {"domain": "pf_law", "papers": 1, "planned": 2}
    import evqa.paths as paths
    monkeypatch.setattr(paths, "SEED", data / "seed")
    monkeypatch.setattr(paths, "DATASET", data / "dataset")
    from evqa.seed import pview, view
    [item] = pview.papers("pf_law")
    assert item["title"] == "A Study of Things" and item["has_brief"] and item["l0"]["found"] == 1
    p = pview.paper("pf_law", "P-01")
    claim, decoy = p["l0"]["facts"]
    span = claim["spans"][0]
    assert p["paper"][span["start"]:span["end"]] == "Kor v. Bel** relied on *section 1*."   # raw Markdown offsets
    assert decoy["status"] == "missing" and decoy["spans"] == []
    assert len(view.overview("pf_law")["rows"]) == 2
    with pytest.raises(KeyError):
        pview.paper("pf_law", "P-02")


def test_never_overwrites_an_evqa_domain(tmp_path: Path) -> None:
    (tmp_path / "data" / "seed" / "materials").mkdir(parents=True)
    with pytest.raises(ValueError, match="not a paperfactory export"):
        workbench.export(_run(tmp_path), "materials", tmp_path / "data")
