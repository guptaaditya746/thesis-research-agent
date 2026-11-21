"""qgraph (evqa/eval/qgraph.py): one question's rows drawn inside its piece of the seed graph."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from evqa.contracts import Row, RunConfig, StdValue, write_jsonl
from evqa.eval import prism, qgraph
from evqa.paths import domain_dir

DOMAIN = "medical"
QID = "Q-med-01"
pytestmark = pytest.mark.skipif(not (domain_dir(DOMAIN) / "seed.ttl").is_file(), reason="seed not built")


def gold_row(fid: str, **over: object) -> Row:
    f = prism.seed_facts(DOMAIN)[fid]
    s, e = prism.l0_spans(DOMAIN, f["paper"])[fid][0]
    dec = len(f["value"].split(".")[1]) if "." in f["value"] else 0
    data = dict(paper=f["paper"], subject=f["subject"], comparator=f["comparator"], measure=f["measure"],
                patient_group=f["context"], dose=f"{f['dose']} mg", time_point=f"week {f['week']}",
                std=StdValue(value=f["value"], unit=f["unit"], decimals=dec), raw=f["value"], quote=f["value"],
                quote_start=s, quote_end=e, quote_ok=True)
    data.update(over)
    return Row(**data)


def make_run(tmp: Path, rows: list[Row]) -> Path:
    cfg = RunConfig(name="g", questions=[QID])
    run = tmp / cfg.run_id()
    (run / QID).mkdir(parents=True)
    (run / "config.yaml").write_text(yaml.safe_dump(cfg.model_dump(mode="json")), encoding="utf-8")
    write_jsonl(run / QID / "rows.jsonl", rows)
    return run


def nodes(out: dict) -> dict[str, dict]:
    return {n["data"]["id"]: n["data"] for n in out["elements"]["nodes"]}


def test_colours_found_missed_wrong_extra_context(tmp_path: Path) -> None:
    gold_ids = prism.gold(DOMAIN)[QID]["row_ids"]
    first, rest = gold_ids[0], gold_ids[1:]
    rows = [gold_row(first, dose="7 mg"),                          # same value and place, wrong dose
            *[gold_row(fid) for fid in rest[:-1]],                 # right
            gold_row(rest[-1], subject="zorbitol", dropped="other subject"),   # dropped: not drawn
            gold_row(first, subject="zorbitol", quote_start=0, quote_end=1, dose="99 mg")]   # extra
    out = qgraph.question_graph(make_run(tmp_path, rows), QID)
    n = nodes(out)
    assert out["counts"]["found"] == len(rest) - 1 and out["counts"]["missed"] == 2
    assert out["counts"]["wrong"] == 1 and out["counts"]["extra"] == 1 and out["counts"]["context"] > 0
    assert n[f"fact:{first}"]["status"] == "missed" and n[f"fact:{rest[0]}"]["status"] == "found"
    assert n[f"fact:{rest[0]}"]["span_from"] == "row" and n[f"fact:{rest[-1]}"]["span_from"] == "seed"
    assert n["row:0"]["status"] == "wrong" and n["row:0"]["fact"] == first
    assert n[f"row:{len(rows) - 1}"]["status"] == "extra"
    assert n["drug:zorbitol"]["status"] == "extra" and n["dose:99 mg"]["status"] == "extra"
    assert f"row:{len(rows) - 2}" not in n
    edges = {(e["data"]["source"], e["data"]["target"]) for e in out["elements"]["edges"]}
    assert ("row:0", f"fact:{first}") in edges and ("row:0", "dose:7 mg") in edges
    assert all(d["parent"] in n for d in n.values() if d.get("parent"))
    assert len(n) <= qgraph.MAX_NODES
    grey = [d for d in n.values() if d["kind"] == "fact" and d["status"] == "context"]
    assert grey and all(d["paper"] in {prism.seed_facts(DOMAIN)[g]["paper"] for g in gold_ids} for d in grey)


def test_closed_book_is_all_red_and_cap_holds(tmp_path: Path) -> None:
    out = qgraph.question_graph(make_run(tmp_path, []), QID, max_nodes=20)
    n = nodes(out)
    facts = [d for d in n.values() if d["kind"] == "fact" and d["status"] != "context"]
    assert facts and all(d["status"] == "missed" for d in facts)
    assert len(n) <= 20 and out["truncated"] > 0


def test_unknown_question(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        qgraph.question_graph(make_run(tmp_path, []), "Q-none")
