"""The `evidence` CLI end to end with regex-only extractors (no model), the PROV-O export, the synthesis
rules on hand-made evidence and the regex helpers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import PROV, RDF

from evidence import cli, protocol, synthesis
from evidence.contract import Item, Span
from evidence.extractors import base

from .conftest import PROTOCOL


def test_cli_end_to_end_regex_only(protocol_file: Path, corpus: Path, tmp_path: Path,
                                   capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "runs"
    assert cli.main(["run", "--protocol", str(protocol_file), "--corpus", str(corpus), "--out", str(out),
                     "--extractors", "regex-only", "--run-id", "r1"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["label"] == "mixed" and printed["cost"]["model_calls"] == 0
    run = out / "r1"
    assert cli.main(["verify", str(run)]) == 0 and json.loads(capsys.readouterr().out)["ok"]
    assert cli.main(["replay", str(run)]) == 0 and json.loads(capsys.readouterr().out)["ok"]
    assert cli.main(["reexec", str(run), "--extractor", "regex_condition"]) == 0
    assert json.loads(capsys.readouterr().out)["summary"]["regex_condition"]["identical"] == 5
    assert cli.main(["prov", str(run)]) == 0 and (run / "prov.ttl").is_file()
    capsys.readouterr()
    assert cli.main(["replay", str(run), "--cache", str(tmp_path / "nothing")]) == 1
    assert "not recorded" in capsys.readouterr().err
    events = (run / "events.jsonl").read_bytes().splitlines(keepends=True)
    (run / "events.jsonl").write_bytes(b"".join(events[:3] + events[4:]))   # drop one record
    assert cli.main(["verify", str(run)]) == 1


def test_prov_walks_from_the_answer_to_the_table_cell(protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    out = tmp_path / "runs"
    cli.main(["run", "--protocol", str(protocol_file), "--corpus", str(corpus), "--out", str(out),
              "--extractors", "regex-only", "--run-id", "r1"])
    cli.main(["prov", str(out / "r1")])
    g = Graph().parse(out / "r1" / "prov.ttl", format="turtle")
    answer = URIRef("urn:thesis-evidence:run/r1/answer")
    derived = set(g.objects(answer, PROV.wasDerivedFrom))
    s2 = json.loads((out / "r1" / "answer.json").read_text())["studies"][1]
    rag = URIRef(f"urn:thesis-evidence:item/{s2['rag']['measurement']}")
    assert rag in derived
    passages = list(g.objects(rag, PROV.wasDerivedFrom))
    exacts = {str(e) for p in passages for sel in g.objects(p, URIRef("http://www.w3.org/ns/oa#hasSelector"))
              for e in g.objects(sel, URIRef("http://www.w3.org/ns/oa#exact"))}
    assert "66.5" in exacts and "retrieval-augmented variant (R)" in exacts
    merge = next(g.objects(rag, PROV.wasGeneratedBy))
    call = next(g.objects(merge, PROV.wasInformedBy))
    agent = next(g.objects(call, PROV.wasAssociatedWith))
    assert (agent, RDF.type, PROV.SoftwareAgent) in g
    assert any(True for _ in g.objects(call, PROV.used))
    first = (out / "r1" / "prov.ttl").read_bytes()
    cli.main(["prov", str(out / "r1")])
    assert (out / "r1" / "prov.ttl").read_bytes() == first


def _item(kind: str, fields: dict, start: int, links: dict | None = None) -> Item:
    span = Span(role="x", selector={"file": "d.md", "start": start, "end": start + 1, "exact": "x", "prefix": "",
                                    "suffix": "", "sha256": "0" * 64})
    return Item.build(kind, fields, [span], links=links)  # type: ignore[arg-type]


def test_synthesis_pairs_on_the_primary_metric_and_datasets() -> None:
    proto = protocol.load(PROTOCOL)
    rag = _item("condition", {"label": "RAG", "role": "rag"}, 0)
    base_c = _item("condition", {"label": "CB", "role": "baseline"}, 1)
    acc = _item("metric", {"name": "acc", "canonical": "factual_accuracy", "higher_is_better": True}, 2)
    hal = _item("metric", {"name": "hal", "canonical": "hallucination_rate", "higher_is_better": False}, 3)
    m = [_item("measurement", {"value": v, "dataset": d}, 10 + n, {"condition": c.item_id, "metric": k.item_id})
         for n, (v, d, c, k) in enumerate([(0.5, "A", rag, acc), (0.7, "B", base_c, acc), (0.6, "A", base_c, acc),
                                           (0.1, None, rag, hal), (0.3, None, base_c, hal)])]
    entry, used = synthesis.study(proto, "D", [rag, base_c, acc, hal, *m])
    assert entry["direction"] == "contradicts" and entry["delta"] == pytest.approx(-0.1)   # dataset A with A
    assert entry["baseline"]["measurement"] == m[2].item_id and m[0].item_id in used
    entry, _ = synthesis.study(proto, "D", [rag, base_c, hal, m[3], m[4]])
    assert entry["direction"] == "supports" and entry["metric"] == "hallucination_rate"
    entry, _ = synthesis.study(proto, "D", [rag, acc])
    assert entry["direction"] == "undetermined" and entry["reason"] == "no baseline condition found"
    entry, _ = synthesis.study(proto, "D", [rag, base_c, acc])
    assert entry["reason"] == "no rag and baseline measurement on a question metric"


def test_numbers_and_tables() -> None:
    assert base.to_fraction("62%", percent=False, rate_like=False) == 0.62
    assert base.to_fraction("0.62", percent=False, rate_like=True) == 0.62
    assert base.to_fraction("62.0", percent=True, rate_like=False) == 0.62
    assert base.to_fraction("410", percent=False, rate_like=False) == 410.0
    text = "Table 3: accuracy (%)\n\n| a | b |\n|---|---|\n| R | 1.5 |\n\nafter"
    (table,) = base.tables(text)
    assert [c.text for c in table.header] == ["a", "b"] and text[table.rows[0][1].start:table.rows[0][1].end] == "1.5"
    assert table.caption.startswith("Table 3")
    prose = "One here. Two there.\n\n## Head\n\nThree.\n\n" + text
    assert [prose[a:b] for a, b in base.sentences(prose)][:4] == ["One here.", "Two there.", "Three.",
                                                                 "Table 3: accuracy (%)"]
    assert "|" not in "".join(prose[a:b] for a, b in base.sentences(prose))   # table lines are not prose
