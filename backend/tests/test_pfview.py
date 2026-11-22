"""The Workbench's view of an exported paperfactory domain (evqa/seed/pfview.py). The export itself is tested in the
paper factory service (services/paper-factory, tests/test_workbench.py); here the files are written by hand in the
export's format."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

MD = "# A Study of Things\n\n## Abstract\n\n**Kor v. Bel** relied on *section 1*. Nothing else here.\n"


def _export(data: Path) -> None:
    a = MD.index("Kor v. Bel")
    b = MD.index("section 1*.") + len("section 1*.")
    seed = data / "seed" / "pf_law"
    (seed / "papers" / "P-01").mkdir(parents=True)
    for name in ("idea_sparse.md", "experimental_log.md"):
        (seed / "papers" / "P-01" / name).write_text(f"brief {name}", encoding="utf-8")
    (seed / "seed.ttl").write_text("# seed\n", encoding="utf-8")
    facts = [{"id": "D1-relies_on-P1", "kind": "claim", "subject": "Kor v. Bel", "relation": "relies_on",
              "object": "section 1", "spans": [[a, b]]},
             {"id": "D2-relies_on-P1", "kind": "decoy", "subject": "Ab v. Cd", "relation": "relies_on",
              "object": "section 1", "spans": []}]
    (seed / "paperfactory.json").write_text(json.dumps({"source": "paperfactory", "field": "law", "genre": "argument",
                                                        "planned": 2, "papers": [{"id": "P-01", "title": "A Study of Things",
                                                                                  "facts": facts}]}), encoding="utf-8")
    (data / "dataset" / "pf_law" / "P-01").mkdir(parents=True)
    (data / "dataset" / "pf_law" / "P-01" / "paper.md").write_text(MD, encoding="utf-8")


def test_view_of_an_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _export(tmp_path / "data")
    import evqa.paths as paths
    monkeypatch.setattr(paths, "SEED", tmp_path / "data" / "seed")
    monkeypatch.setattr(paths, "DATASET", tmp_path / "data" / "dataset")
    from evqa.seed import pview, view
    [item] = pview.papers("pf_law")
    assert item["title"] == "A Study of Things" and item["has_brief"] and item["l0"]["found"] == 1
    p = pview.paper("pf_law", "P-01")
    claim, decoy = p["l0"]["facts"]
    span = claim["spans"][0]
    assert p["paper"][span["start"]:span["end"]] == "Kor v. Bel** relied on *section 1*."
    assert decoy["status"] == "missing" and decoy["spans"] == []
    assert len(view.overview("pf_law")["rows"]) == 2
    with pytest.raises(KeyError):
        pview.paper("pf_law", "P-02")
