"""The reasoner core: owlrl over the pack's ontology (spec 6.3)."""
import shutil
from pathlib import Path

import pytest

from evidence.pack import DOMAINS, PackError, load_pack
from evidence.reasoner import Inferences, broader_of, counts_as, load_ontology, ontology_sha256

FIXTURE = Path(__file__).parent / "fixtures" / "onto" / "ontology.ttl"


@pytest.fixture
def fixture_pack(tmp_path):
    def make(extra: str = ""):
        shutil.copytree(DOMAINS / "rag", tmp_path / "rag", dirs_exist_ok=True)
        (tmp_path / "rag" / "ontology.ttl").write_text(FIXTURE.read_text(encoding="utf-8") + extra + "\n", encoding="utf-8")
        return load_pack("rag", root=tmp_path), tmp_path
    return make


def test_narrower_metric_counts_for_broader(fixture_pack):
    pack, root = fixture_pack()
    g = load_ontology(pack, root)
    assert "accuracy" in broader_of(g, "top-1 accuracy")
    inf = Inferences(None, {"top-1 accuracy": broader_of(g, "top-1 accuracy")}, [])
    assert counts_as("top-1 accuracy", "accuracy", inf) and not counts_as("accuracy", "top-1 accuracy", inf)


def test_unknown_metric_counts_only_for_itself(fixture_pack):
    pack, root = fixture_pack()
    g = load_ontology(pack, root)
    assert broader_of(g, "made-up score") == []
    assert counts_as("made-up score", "made-up score", None) and not counts_as("made-up score", "accuracy", None)


def test_subclass_cycle_terminates(fixture_pack):
    pack, root = fixture_pack(':A rdfs:label "a" ; rdfs:subClassOf :B . :B rdfs:label "b" ; rdfs:subClassOf :A .')
    assert broader_of(load_ontology(pack, root), "a") == ["b"]


def test_duplicate_label_is_refused_with_both_iris(fixture_pack):
    with pytest.raises(PackError, match=r"label 'accuracy'.*#Acc2.*#Accuracy"):
        pack, root = fixture_pack(':Acc2 rdfs:label "accuracy" .')
        load_ontology(pack, root)


def test_top_classes_are_never_broader_names(fixture_pack):
    pack, root = fixture_pack()
    assert "metric" not in broader_of(load_ontology(pack, root), "accuracy")


def test_a_pack_without_an_ontology_has_neither_graph_nor_digest(fixture_pack):
    pack, root = fixture_pack()
    bare = pack.model_copy(update={"ontology": None})
    assert load_ontology(bare, root) is None and ontology_sha256(bare, root) is None


def test_ontology_digest_ignores_line_ends(fixture_pack):
    pack, root = fixture_pack()
    path = root / "rag" / "ontology.ttl"
    lf = path.read_bytes().replace(b"\r\n", b"\n")
    path.write_bytes(lf)
    before = ontology_sha256(pack, root)
    path.write_bytes(lf.replace(b"\n", b"\r\n"))
    assert ontology_sha256(pack, root) == before


def test_rag_ontology_loads_and_has_a_digest():
    p = load_pack("rag")
    assert load_ontology(p) is not None and len(ontology_sha256(p)) == 64
    assert broader_of(load_ontology(p), "factual accuracy") == []   # only the top class is above it
