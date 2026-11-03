"""Field ontology loaders on tiny committed fixtures (never the real downloads)."""
import hashlib
from pathlib import Path

import pytest

from evidence.ontology import fetch, load, ontology_hashes, other_names, sources
from evidence.pack import load_pack
from evidence.reasoner import load_ontology

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def folder(tmp_path, monkeypatch):
    (tmp_path / "mesh_desc.xml").write_bytes((FIX / "mesh_mini.xml").read_bytes())
    (tmp_path / "qudt_units.ttl").write_bytes((FIX / "qudt_mini.ttl").read_bytes())
    monkeypatch.setenv("EV_ONTOLOGY_DIR", str(tmp_path))
    return tmp_path


def test_mesh_entry_terms(folder):
    g = load("medicine")
    assert "Heart Attack" in other_names(g, "Myocardial Infarction")
    assert (sources.MESH.D009203, sources.RDFS.subClassOf, sources.MESH.D006331) in g


def test_qudt_unit_symbol(folder):
    g = load("other")
    assert "%" in other_names(g, "percent") and "percent" in other_names(g, "%")


def test_cs_field_uses_existing_ttl(monkeypatch, tmp_path):
    monkeypatch.setenv("EV_ONTOLOGY_DIR", str(tmp_path))
    assert set(load_ontology(load_pack("rag"))) == set(load("cs", with_units=False))


def test_missing_mesh_file_is_no_tree_not_a_crash(monkeypatch, tmp_path):
    monkeypatch.setenv("EV_ONTOLOGY_DIR", str(tmp_path))
    assert load("medicine", with_units=False) is None
    assert load("medicine") is not None   # the committed QUDT subset


def test_fetch_refuses_wrong_sha(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "_download", lambda url, accept="*/*": b"data")
    with pytest.raises(sources.OntologyError, match="sha256"):
        fetch("qudt", tmp_path, sha256="0" * 64)
    assert not list(tmp_path.iterdir())


def test_fetch_writes_when_sha_matches_and_hashes_are_reported(tmp_path, monkeypatch, folder):
    monkeypatch.setattr(sources, "_download", lambda url, accept="*/*": b"<x/>")
    path = fetch("mesh", tmp_path, sha256=hashlib.sha256(b"<x/>").hexdigest())
    assert path.read_bytes() == b"<x/>"
    assert set(ontology_hashes()) == {"mesh", "qudt", "cs_fallback"}


def test_unparseable_file_is_no_tree_not_a_crash(tmp_path, monkeypatch):
    (tmp_path / "qudt_units.ttl").write_text("<html><body>Not turtle</body></html>", encoding="utf-8")
    monkeypatch.setenv("EV_ONTOLOGY_DIR", str(tmp_path))
    assert load("other") is None
    assert load("cs") is not None   # the CS-KG fallback still loads


def test_fetch_refuses_html_and_asks_for_turtle(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(sources, "_download", lambda url, accept="*/*": seen.append(accept) or b"<html>hi</html>")
    with pytest.raises(sources.OntologyError, match="does not parse"):
        fetch("qudt", tmp_path)
    assert seen == ["text/turtle"] and not list(tmp_path.iterdir())


def test_hashes_cover_the_cs_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("EV_ONTOLOGY_DIR", str(tmp_path))
    assert set(ontology_hashes("cs")) == {"cs_fallback", "qudt"}
    assert set(sources.files_for("cs")) == set(ontology_hashes("cs"))
