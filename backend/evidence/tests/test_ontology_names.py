"""Ontology names go into the word list, apart from the LLM's own names."""
from pathlib import Path

from evidence.ontology import load
from evidence.ontology.names import add_ontology_names
from evidence.plan import WordList

FIX = Path(__file__).parent / "fixtures"


def _words():
    return WordList(things={"mi": ["myocardial infarction", "MI"], "x": ["unknown thing"]}, cues=["reduces"],
                    written_by="llm", ontology_names={})


def test_adds_mesh_synonyms(tmp_path, monkeypatch):
    (tmp_path / "mesh_desc.xml").write_bytes((FIX / "mesh_mini.xml").read_bytes())
    monkeypatch.setenv("EV_ONTOLOGY_DIR", str(tmp_path))
    out = add_ontology_names(_words(), load("medicine"))
    assert "Heart Attack" in out.ontology_names["mi"]
    assert "x" not in out.ontology_names
    assert out.things == _words().things and out.written_by == "llm"


def test_no_graph_no_change():
    words = _words()
    assert add_ontology_names(words, None) == words
