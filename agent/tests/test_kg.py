from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import kg
from agent.canonical import canonical
from agent.cli import main as cli

from .runs import Built, baseline, corpus_env, research  # noqa: F401  (pytest fixtures)


def test_predicate_mapping() -> None:
    assert kg.map_predicate("based on")["curie"] == "cskg:based-on"
    assert kg.map_predicate("basedOn")["curie"] == "cskg:based-on"
    assert kg.map_predicate("executesMethod")["iri"] == "https://w3id.org/cskg/ontology#executesMethod"
    assert kg.map_predicate("analyzes task")["curie"] == "cskg:analyzesTask"
    assert kg.map_predicate("Improves")["curie"] == "cskg:improves"
    assert kg.map_predicate("authored by")["iri"] == "https://dblp.org/rdf/schema#authoredBy"
    assert kg.map_predicate("year")["literal_object"] is True
    unmapped = kg.map_predicate("evaluates on")
    assert (unmapped["curie"], unmapped["vocabulary"], unmapped["text"]) == ("ours:evaluatesOn", "ours", "evaluates on")
    assert kg.map_predicate("evaluatesOn")["curie"] == "ours:evaluatesOn"
    assert kg.map_predicate("reports_metric")["curie"] == "ours:reportsMetric"
    assert kg.map_predicate("--")["curie"] == "ours:relatedTo"


def test_every_mapped_curie_has_a_namespace() -> None:
    assert {t.curie.split(":")[0] for t in kg.PREDICATES.values()} == {"cskg", "dblp"}


def test_slug_merges_spelling_variants() -> None:
    assert kg.slug("Natural Questions") == kg.slug("natural-questions") == "natural-questions"
    assert kg.slug("GPT-4") == kg.slug("gpt 4")


def test_research_graph(research: Built) -> None:
    path, graph = kg.write(research.run, research.manifest)
    assert path == research.run.root / "graph.json"
    assert path.read_text(encoding="utf-8") == canonical(graph) + "\n"
    edges = {e["claim"]: e for e in graph["edges"]}
    assert sorted(edges) == [f"claim-{i:06d}" for i in range(1, 7)]  # the rejected claim is not an edge
    spider = edges["claim-000001"]
    assert (spider["id"], spider["source"], spider["target"], spider["literal"]) == \
        ("edge-000001", "paper:p1", "entity:spider", None)
    assert spider["predicate"]["curie"] == "ours:evaluatesOn"
    assert spider["evidence"]["paper"] == "p1" and spider["evidence"]["file"] == "p1.md"
    assert (spider["origin"], spider["step_id"], spider["agent_id"]) == ("research", 1, "main")
    assert edges["claim-000003"]["predicate"] == {
        "text": "evaluates on", "curie": "ours:evaluatesOn", "iri": "urn:thesis-agent:vocab#evaluatesOn",
        "vocabulary": "ours"}
    author = edges["claim-000004"]
    assert author["predicate"]["curie"] == "dblp:authoredBy" and author["target"] == "entity:hanbing-liu"
    megapairs = edges["claim-000006"]
    assert megapairs["predicate"]["curie"] == "cskg:proposes" and megapairs["agent_id"] == "sub-01"
    nodes = {n["id"]: n for n in graph["nodes"]}
    assert nodes["paper:p4"] == {"id": "paper:p4", "kind": "paper", "label": "p4", "paper": "p4"}
    assert nodes["entity:bird"]["label"] == "BIRD"
    assert graph["sources"]["claims_sha256"] and graph["run_id"] == "research-r1"


def test_baseline_graph_has_attach_edges(baseline: Built) -> None:
    graph = kg.build(baseline.run, baseline.manifest)
    assert len(graph["edges"]) == 3
    assert {e["origin"] for e in graph["edges"]} == {"attach"}
    assert [e["step_id"] for e in graph["edges"]] == [5, 6, 7]


def test_graph_is_deterministic(research: Built) -> None:
    first = kg.build(research.run, research.manifest)
    assert canonical(first) == canonical(kg.build(research.run, research.manifest))


def test_wrong_manifest_refused(research: Built, tmp_path: Path) -> None:
    other = tmp_path / "manifest.json"
    data = json.loads(research.manifest.read_text(encoding="utf-8"))
    data["paper_count"] += 1
    other.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="the run was made with"):
        kg.build(research.run, other)


def test_literal_objects(research: Built) -> None:
    graph = kg.build(research.run, research.manifest)
    assert all((e["target"] is None) != (e["literal"] is None) for e in graph["edges"])


def test_cli_graph(research: Built, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli(["graph", str(research.run.root), "--manifest", str(research.manifest)]) == 0
    assert capsys.readouterr().out.startswith("PASS edges=6 nodes=")
    assert (research.run.root / "graph.json").is_file()
