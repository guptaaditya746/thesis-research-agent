"""synth3.report: the judge-test sample, the agreement number and the report. No model is called."""
import json
from collections import Counter
from pathlib import Path

from jsonio import write_json_atomic
from synth3.answers import PulledFact, save_answer
from synth3.cli import main
from synth3.judge import planted_facts
from synth3.marking import marks_path
from synth3.questions import load_questions, question_sha256
from synth3.report import (FLAG_BELOW, agreement, build_report, load_hand_marks, load_sample, pick_sample,
                           render_report, save_hand_mark)
from synth3.sheetfacts import load_folder
from synth3.sheets import make_sheet, save_sheet
from synth3.tests.fakes import rec

FIX = Path(__file__).parent / "fixtures" / "questions"
BASELINE = "rag-baseline"


def fake_marks(results, systems=("engine", BASELINE), questions=10, seeds=5, domain="demo", qids=None,
               status="checked", c_score=0.5, pending=()):
    """Marks files in the shape `judge_answer` returns, for a grid of systems x seeds x questions; returns the item
    ids. The baseline has no A. `pending` lists item ids whose C is pending."""
    names = qids or [f"q{i + 1:02d}" for i in range(questions)]
    items = []
    for system in systems:
        for seed in range(1, seeds + 1):
            for qid in names:
                item = f"{domain}/s{seed}/{system}/{qid}"
                is_pend = item in pending
                a = None if system == BASELINE else {
                    "score": 0.5, "found": 1, "wrong": 0, "missing": 1, "total": 2, "anchored": 0.5,
                    "pending_papers": [], "pulled_cut": [], "papers": {}, "problems": {}, "calls": 0}
                ticks = [] if is_pend else [{"point": "p1", "met": True, "quote": "q", "reason": ""},
                                            {"point": "p2", "met": False, "quote": None, "reason": ""}]
                marks = {"item": item, "question_id": qid, "seed": seed, "system": system, "corpus_id": "c",
                         "answer_sha256": "x",
                         "sheet": {"sha256": "s", "status": status, "cant_tell": False,
                                   "points": [{"id": "p1", "text": "One."}, {"id": "p2", "text": "Two."}]},
                         "A": a,
                         "B": {"score": 1.0, "claims": [], "invented": 0, "contradicted": 0, "status": "ok",
                               "problems": [], "calls": 0},
                         "C": {"score": None if is_pend else c_score, "status": "pending" if is_pend else "ok",
                               "ticks": ticks, "missed": [] if is_pend else ["p2"], "problems": [], "calls": 0},
                         "judge": {}, "calls": 0}
                write_json_atomic(marks_path(results, domain, seed, system, qid), marks)
                items.append(item)
    return items


def test_agreement_and_the_flag():
    judged = {f"i{k}": {"C": {"ticks": [{"point": "p1", "met": True}]}} for k in range(10)}
    hand = {f"i{k}": {"points": {"p1": k < 9}, "faithful": None} for k in range(10)}
    a = agreement(list(judged), hand, judged)
    assert a["rate"] == 0.9 and not a["flag"] and a["answers_marked"] == 10
    hand = {f"i{k}": {"points": {"p1": k < 7}, "faithful": None} for k in range(10)}
    a = agreement(list(judged), hand, judged)
    assert a["rate"] == 0.7 and a["flag"] and len(a["disagreements"]) == 3
    assert FLAG_BELOW == 0.80


def test_unmarked_items_do_not_count():
    judged = {"i1": {"C": {"ticks": [{"point": "p1", "met": True}]}}}
    assert agreement(["i1"], {}, judged)["rate"] is None and not agreement(["i1"], {}, judged)["flag"]


def test_agreement_compares_faithful_with_b_and_leaves_a_pending_b_out():
    ok = {"B": {"status": "ok", "invented": 0, "contradicted": 0}, "C": {"ticks": []}}
    bad = {"B": {"status": "ok", "invented": 1, "contradicted": 0}, "C": {"ticks": []}}
    pend = {"B": {"status": "pending", "invented": None, "contradicted": None}, "C": {"ticks": []}}
    judged = {"a": ok, "b": ok, "c": bad, "d": pend}
    hand = {"a": {"points": {}, "faithful": True}, "b": {"points": {}, "faithful": False},
            "c": {"points": {}, "faithful": False}, "d": {"points": {}, "faithful": True}}
    a = agreement(list(judged), hand, judged)
    assert a["faithful"] == {"n": 3, "agree": 2, "rate": 2 / 3}


def test_hand_marks_and_sample_round_trip(tmp_path):
    save_hand_mark(tmp_path, "demo/s1/engine/q01", {"p1": True}, None, "aditya", "2026-11-18")
    save_hand_mark(tmp_path, "demo/s1/engine/q02", {"p1": False}, True, "aditya", "2026-11-18")
    got = load_hand_marks(tmp_path)
    assert got["demo/s1/engine/q01"] == {"points": {"p1": True}, "faithful": None, "by": "aditya",
                                         "at": "2026-11-18"}
    assert got["demo/s1/engine/q02"]["faithful"] is True and load_hand_marks(tmp_path / "none") == {}
    assert load_sample(tmp_path) == []


def test_sample_is_balanced_capped_and_stable(tmp_path):
    fake_marks(tmp_path / "res", systems=("engine", BASELINE), questions=10, seeds=5)
    s = pick_sample(tmp_path / "res", ["demo"], n=10)
    assert s == pick_sample(tmp_path / "res", ["demo"], n=10) and len(s) == 10
    assert sum("/rag-baseline/" in i for i in s) == 5
    assert max(Counter(i.split("/")[3] for i in s).values()) <= 2
    assert s == sorted(s)


def test_sample_skips_held_items_and_pending_c_and_the_other_half_fills_up(tmp_path):
    items = fake_marks(tmp_path / "res", questions=10, seeds=5)
    s = pick_sample(tmp_path / "res", ["demo"], n=10, have=items[:50])
    assert not set(s) & set(items[:50]) and len(s) == 10
    pend = [i for i in items if "/engine/" in i]
    fake_marks(tmp_path / "res2", questions=10, seeds=5, pending=pend)
    s = pick_sample(tmp_path / "res2", ["demo"], n=10)
    assert len(s) == 10 and all("/rag-baseline/" in i for i in s)


def test_report_puts_the_baseline_next_to_the_system_and_flags(folder, tmp_path, spec_dir):
    res, jt = tmp_path / "res", tmp_path / "jt"
    items = fake_marks(res, questions=5, seeds=1)   # 10 answers; the judge ticks p1 met on each
    write_json_atomic(jt / "sample.json", items)
    for k, item in enumerate(items):                # 7 of the 10 hand marks agree: 70%
        save_hand_mark(jt, item, {"p1": k < 7}, None, "a", "t")
    r = build_report(res, ["demo"], tmp_path / "sh", jt, folders=folder.parent, spec_root=spec_dir,
                     questions_root=FIX)
    md = render_report(r)
    d = r["domains"]["demo"]
    assert set(d["systems"]) == {"engine", BASELINE}
    assert d["systems"]["engine"]["answers"] == 5 and d["systems"][BASELINE]["answers"] == 5
    assert d["systems"][BASELINE]["a_mean"] is None and d["systems"]["engine"]["a_mean"] == 0.5
    assert "engine" in md and BASELINE in md and "n/a" in md
    assert md.index("engine") < md.index(BASELINE)
    assert "Judge agreement 70% (below 80%: reported as a limitation)." in md
    assert r["agreement"]["flag"] is True
    assert [i for i in d["judge_test_items"]] == sorted(items)


def test_report_leaves_a_pending_answer_out_of_its_means_and_counts_unchecked_marks(folder, tmp_path, spec_dir):
    res = tmp_path / "res"
    fake_marks(res, questions=3, seeds=1, qids=["d01", "d02", "d03"], status="drafted",
               pending=["demo/s1/engine/d03"])
    r = build_report(res, ["demo"], tmp_path / "sh", tmp_path / "jt", folders=folder.parent, spec_root=spec_dir,
                     questions_root=FIX)
    eng = r["domains"]["demo"]["systems"]["engine"]
    assert eng["answers"] == 3 and eng["pending"] == 1
    assert eng["c_mean"] == 0.5 and eng["b_mean"] == 1.0   # C's mean leaves the pending one out; B's keeps it
    assert eng["unchecked"] == 3 and r["domains"]["demo"]["systems"][BASELINE]["unchecked"] == 3
    assert "unchecked" in render_report(r)


def test_report_counts_sheets_checked_drafted_and_missing(folder, tmp_path, spec_dir, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX)
    sh = tmp_path / "sh"
    save_sheet(sh, make_sheet(f, qs.get("d01"), [("T", ["pair:a:m1"])], {"model": "x"}))
    res = tmp_path / "res"
    fake_marks(res, questions=2, seeds=1, qids=["d01", "d02"])
    r = build_report(res, ["demo"], sh, tmp_path / "jt", folders=folder.parent, spec_root=spec_dir,
                     questions_root=FIX)
    assert r["domains"]["demo"]["sheets"] == {"checked": 0, "drafted": 1, "missing": 2}   # 3 questions x 1 seed
    top = r["domains"]["demo"]["most_missed"][0]
    assert (top["question"], top["point"], top["missed"], top["of"]) == ("d01", "p2", 2, 2)   # both systems missed it


def test_report_a_cross_check_compares_the_judge_with_the_spans(folder, tmp_path, spec_dir, SPEC):
    """A `found` mark with no pulled fact on its span and a `missing` mark with one are what the cross-check counts."""
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); q = qs.get("d01")
    planted = [p for ps in planted_facts(f, q).values() for p in ps]
    first = planted[0]
    a, b = first.spans[0]
    touch = PulledFact(paper=first.paper, kind="measurement", fields={}, quote="x", start=a, end=b)
    res = tmp_path / "res"
    save_answer(res, rec("t", question_id="d01", question_sha256=question_sha256(q), corpus_id=f.corpus_id,
                         facts=[touch]))
    fake_marks(res, systems=("engine",), questions=1, seeds=1, qids=["d01"])
    path = marks_path(res, "demo", 1, "engine", "d01")
    mk = json.loads(path.read_text(encoding="utf-8"))
    papers: dict = {}
    for p in planted:
        papers.setdefault(p.paper, []).append({"fact": p.id, "verdict": "missing" if p is first else "found",
                                               "pulled": None if p is first else 1, "reason": ""})
    mk["A"]["papers"] = papers
    write_json_atomic(path, mk)
    r = build_report(res, ["demo"], tmp_path / "sh", tmp_path / "jt", folders=folder.parent, spec_root=spec_dir,
                     questions_root=FIX)
    row = r["domains"]["demo"]["systems"]["engine"]
    assert row["a_found_untouched"] == 1.0   # no `found` fact has a pulled fact on its span (the touched one is missing)
    assert row["a_missing_touched"] == 1.0   # the one `missing` fact has one


def test_judge_sample_by_command(tmp_path, capsys):
    res, jt = tmp_path / "res", tmp_path / "jt"
    fake_marks(res, questions=10, seeds=5)
    argv = ["judge-sample", "--domains", "demo", "--n", "10", "--results", str(res), "--judge-test", str(jt)]
    assert main(argv) == 0
    first = load_sample(jt)
    assert len(first) == 10
    assert main(argv) == 2 and "sample.json" in capsys.readouterr().err
    assert main(argv + ["--add", "4"]) == 0
    both = load_sample(jt)
    assert len(both) == 14 and both[:10] == first


def test_report_by_command(folder, tmp_path, spec_dir, capsys):
    res = tmp_path / "res"
    fake_marks(res, questions=3, seeds=1, qids=["d01", "d02", "d03"])
    out = tmp_path / "out" / "r.json"
    code = main(["report", "--domains", "demo", "--out", str(out), "--results", str(res),
                 "--sheets", str(tmp_path / "sh"), "--judge-test", str(tmp_path / "jt"),
                 "--folders", str(folder.parent), "--spec-root", str(spec_dir), "--questions-root", str(FIX)])
    assert code == 0 and out.is_file() and out.with_suffix(".md").is_file()
    assert json.loads(out.read_text(encoding="utf-8"))["domains"]["demo"]
    assert "demo" in capsys.readouterr().out
