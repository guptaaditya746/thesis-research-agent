"""#11: the hand-labeling test set is built without the verifier; metrics on labels. No model calls."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from paperfactory import config, labels, packs, seed
from paperfactory.evaluate import Eval
from paperfactory.text import split_rules, split_sents

HERE = Path(__file__).resolve().parents[1]
PILOT = json.loads((HERE / "worlds" / "law-pilot.json").read_text())
LAW = packs.field("law")
PAPER = ("Rusk v. Oberline Health relied on section 14 of the Veldra Personal Data Act 2016 in its reasoning.\n\n"
         "Rusk distinguished Marrin on its facts, as the court explained at length.\n\n"
         "Navarre Insurance and Pell are often read together by commentators.\n")


def tagged() -> dict:
    return {"L-01": {"sentences": [list(x) for x in split_sents(PAPER, split_rules(LAW, PILOT))], "spans": {}}}


def test_items_cover_every_kind_and_flag_impossible_pairs() -> None:
    its = labels.items(PILOT, LAW, tagged(), {"L-01": PAPER})
    kinds = {it["kind"] for it in its}
    assert {"candidate", "other_relation", "decoy", "not_recorded", "impossible_pair", "no_world_rel"} <= kinds
    cand = {(it["s"], it["r"], it["o"]) for it in its if it["kind"] == "candidate"}
    assert ("K5", "relies_on", "S14") in cand and ("K5", "distinguishes", "K1") in cand
    # distinguishes needs a decision as object: section 14 is impossible, reported apart
    assert any(it["kind"] == "impossible_pair" and (it["s"], it["r"], it["o"]) == ("K5", "distinguishes", "S14")
               for it in its)
    assert not any(it["kind"] == "other_relation" and it["r"] == "distinguishes" and it["o"] == "S14" for it in its)
    # decoys: planted facts sharing one entity with the pair, whose other end the sentence does not name
    dec = [it for it in its if it["kind"] == "decoy"]
    assert dec and all(len({it["s"], it["o"]} & {"K5", "S14", "K1"}) >= 1 for it in dec)
    nr = [it for it in its if it["kind"] == "not_recorded"]
    assert nr and all(it["context"] == "" for it in nr)


def test_export_writes_blind_csv_and_key(tmp_path: Path) -> None:
    dest = tmp_path / "labels.csv"
    res = labels.export(PILOT, LAW, tagged(), dest, per_field=8, papers_md={"L-01": PAPER})
    with dest.open() as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0]) == labels.COLUMNS
    assert all(r["label"] == "" for r in rows)
    key = json.loads(labels.key_path(dest).read_text())
    assert set(key) == {r["id"] for r in rows} and res["rows"] == len(rows)
    assert sum(k["kind"] != "impossible_pair" for k in key.values()) == 8
    assert not any(k in r["id"] for r in rows for k in labels.KINDS)       # labelers do not see the kind


def test_metrics_precision_recall_kappa() -> None:
    key = {f"x{i}": {"field": "law", "r": "relies_on", "kind": "candidate"} for i in range(6)}
    key["imp"] = {"field": "law", "r": "distinguishes", "kind": "impossible_pair"}
    a = {"x0": "yes", "x1": "yes", "x2": "no", "x3": "no", "x4": "yes", "x5": None, "imp": "no"}
    b = {"x0": "yes", "x1": "yes", "x2": "no", "x3": "no", "x4": "no", "x5": "yes", "imp": "no"}
    ans = {"x0": "yes", "x1": "no", "x2": "yes", "x3": "no", "x5": "yes", "imp": "no"}
    m = labels.metrics([a, b], key, ans)
    assert m["unsettled_disagreements"] == 1               # x4 left out of the main numbers ...
    o = m["test_mix"]
    assert (o["tp"], o["fp"], o["fn"], o["tn"]) == (2, 1, 1, 1)       # x0, x5 | x2 | x1 | x3
    assert o["precision"]["value"] == 0.667 and o["recall"]["value"] == 0.667
    assert o["false_accept"]["value"] == 0.5 and len(o["precision"]["ci95"]) == 2
    assert m["impossible_pairs"]["n"] == 1 and m["by_relation"]["relies_on"]["n"] == 5
    ag = m["agreement"][0]
    assert ag["n"] == 6 and ag["agree"] == 5 and 0 < ag["kappa"] < 1
    assert m["worst_case"]["n"] == 6 and m["worst_case"]["unanswered"] == 1        # x4: no verifier answer
    m2 = labels.metrics([a, b], key, ans | {"x4": "no"})
    assert m2["worst_case"]["fn"] + m2["worst_case"]["fp"] == 3                    # ... counted as an error
    assert m["recall_candidates"]["value"] == 0.667 and m["eval_mix"]["n"] == 5
    settled = labels.metrics([a, b], key, ans, adjudicated={"x4": "yes"})
    assert settled["unsettled_disagreements"] == 0 and settled["test_mix"]["n"] == 6


def test_subject_named_in_the_sentence_before_makes_items() -> None:
    """Review finding 7: "Rusk ... . It relied on section 14." is a candidate, as the tagger would accept it."""
    sents = ["The court decided Rusk v. Oberline Health in 2023.", "It relied on section 14 for its ruling."]
    offs, a = [], 0
    for x in sents:
        offs.append([a, a + len(x), x])
        a += len(x) + 1
    its = labels.items(PILOT, LAW, {"L-01": {"sentences": offs}})
    hit = [i for i in its if i["n"] == 1 and i["kind"] == "candidate"]
    assert hit and hit[0]["s"] == "K5" and hit[0]["o"] == "S14" and hit[0]["via"] == "context"


def test_kappa_edge_cases() -> None:
    assert labels.kappa({"a": "yes"}, {"a": "yes"})["kappa"] is None
    assert labels.kappa({"a": "yes", "b": "no"}, {"a": "yes", "b": "no"})["kappa"] == 1.0


def test_read_labels_and_verifier_answers(tmp_path: Path) -> None:
    p = tmp_path / "l.csv"
    p.write_text("id,label\na,Yes\nb,0\nc,maybe\n")
    assert labels.read_labels(p) == {"a": "yes", "b": "no", "c": None}
    _, gold = seed.make(PILOT, LAW, per_question=3, seed=1)

    def fake(role, step, system, user, schema, check=None):
        return {"answers": [{"id": x["id"], "verdict": "yes"} for x in json.loads(user)]}
    ev = Eval(config.Settings("law", "argument", out=str(tmp_path)), PILOT, LAW, gold, fake)
    key = {"i1": {"context": "", "sentence": "Rusk relied on s. 14.", "s": "K5", "r": "relies_on", "o": "S14"}}
    assert labels.verifier_answers(ev, key) == {"i1": "yes"}


def test_verifier_test_reports_impossible_pairs_apart(tmp_path: Path) -> None:
    _, gold = seed.make(PILOT, LAW, per_question=3, seed=1)

    def fake(role, step, system, user, schema, check=None):
        return {"answers": [{"id": x["id"], "verdict": "no"} for x in json.loads(user)]}
    ev = Eval(config.Settings("law", "argument", out=str(tmp_path)), PILOT, LAW, gold, fake)
    t = tagged()["L-01"]
    t["spans"] = {"K5-relies_on-S14": [t["sentences"][0][:2]]}
    rep = ev.verifier_test({"L-01": t})
    assert "circular" in rep["note"]
    # relies_on S14 -> distinguishes S14 is impossible, rejects S14 is possible
    assert rep["negatives"] == 1 and rep["impossible_pair_negatives"]["n"] == 1


def test_cli_export_and_metrics(tmp_path: Path, capsys) -> None:
    from paperfactory import cli
    run = tmp_path / "run"
    (run / "work" / "L-01").mkdir(parents=True)
    (run / "work" / "L-01" / "paper.md").write_text(PAPER)
    (run / "world.json").write_text(json.dumps(PILOT))
    (run / "tagged.json").write_text(json.dumps({"papers": tagged()}))
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"field": "law", "genre": "argument", "out": str(run)}))
    cli.main(["export-labels", "--config", str(cfg), "--out", str(tmp_path / "l.csv"), "--per-field", "5"])
    assert json.loads(capsys.readouterr().out)["rows"] >= 5
    key = json.loads((tmp_path / "l.key.json").read_text())
    with (tmp_path / "l.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["label"] = "yes" if key[r["id"]]["kind"] == "candidate" else "no"
    with (tmp_path / "l.csv").open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=labels.COLUMNS)
        wr.writeheader()
        wr.writerows(rows)
    (tmp_path / "a.json").write_text(json.dumps({i: "yes" for i in key}))
    cli.main(["label-metrics", "--labels", str(tmp_path / "l.csv"), "--answers", str(tmp_path / "a.json")])
    m = json.loads(capsys.readouterr().out)
    assert m["labeled"] == len(rows) and m["test_mix"]["recall"]["value"] in (1.0, None)
