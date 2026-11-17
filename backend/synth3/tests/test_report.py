"""synth3.report: the judge-test sample, the agreement number and the report. No model is called."""
import json
from collections import Counter
from pathlib import Path

import pytest

from jsonio import write_json_atomic
from synth3.answers import PulledFact, item_id, save_answer
from synth3.cli import main
from synth3.corpus import build_folder
from synth3.judge import planted_facts
from synth3.marking import answer_sha256, marks_path
from synth3.questions import load_questions, question_sha256
from synth3.report import (FLAG_BELOW, agreement, build_report, current_marks_of, load_hand_marks, load_sample,
                           pick_sample, render_report, save_hand_mark)
from synth3.sheetfacts import load_folder
from synth3.sheets import make_sheet, save_sheet, sheet_sha256
from synth3.tests.conftest import approved
from synth3.tests.fakes import rec

FIX = Path(__file__).parent / "fixtures" / "questions"
BASELINE = "rag-baseline"
QIDS = ("d01", "d02", "d03")


def marks_of(item, *, answer="x", sheet="s", status="checked", c_score=0.5, pending=False) -> dict:
    """One marks file in the shape `judge_answer` returns: the judge ticks p1 met and p2 missed. The baseline has
    no A."""
    domain, s, system, qid = item.split("/")
    a = None if system == BASELINE else {
        "score": 0.5, "found": 1, "wrong": 0, "missing": 1, "total": 2, "anchored": 0.5,
        "pending_papers": [], "pulled_cut": [], "papers": {}, "problems": {}, "calls": 0}
    ticks = [] if pending else [{"point": "p1", "met": True, "quote": "q", "reason": ""},
                                {"point": "p2", "met": False, "quote": None, "reason": ""}]
    return {"item": item, "question_id": qid, "seed": int(s[1:]), "system": system, "corpus_id": "c",
            "answer_sha256": answer,
            "sheet": {"sha256": sheet, "status": status, "cant_tell": False,
                      "points": [{"id": "p1", "text": "One."}, {"id": "p2", "text": "Two."}]},
            "A": a,
            "B": {"score": 1.0, "claims": [], "invented": 0, "contradicted": 0, "status": "ok",
                  "problems": [], "calls": 0},
            "C": {"score": None if pending else c_score, "status": "pending" if pending else "ok",
                  "ticks": ticks, "missed": [] if pending else ["p2"], "problems": [], "calls": 0},
            "judge": {}, "calls": 0}


def grid(systems=("engine", BASELINE), questions=10, seeds=5, domain="demo", pending=()) -> dict[str, dict]:
    """Current marks (in memory) for a grid of systems x seeds x questions, by item id."""
    items = [f"{domain}/s{seed}/{system}/q{i + 1:02d}" for system in systems for seed in range(1, seeds + 1)
             for i in range(questions)]
    return {i: marks_of(i, pending=i in pending) for i in items}


def judged(tmp_path, folder, SPEC, systems=("engine", BASELINE), qids=QIDS, status="checked", pending=(),
           facts=()) -> list[str]:
    """On disk, for the `folder` fixture (seed 1): a sheet per question, a saved answer per system and question,
    and a current marks file for each (made from that answer and that sheet). Returns the item ids."""
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX)
    items = []
    for qid in qids:
        q = qs.get(qid)
        sheet = make_sheet(f, q, [("One.", ["pair:a:m1"]), ("Two.", ["pair:a:m1"])], {"model": "x"})
        if status == "checked":
            sheet = sheet.model_copy(update={"status": "checked", "checked_by": "a"})
        save_sheet(tmp_path / "sh", sheet)
        for system in systems:
            r = rec("t", question_id=qid, question_sha256=question_sha256(q), corpus_id=f.corpus_id, system=system,
                    facts=None if system == BASELINE else list(facts))
            save_answer(tmp_path / "res", r)
            item = item_id(r)
            write_json_atomic(marks_path(tmp_path / "res", "demo", 1, system, qid),
                              marks_of(item, answer=answer_sha256(r), sheet=sheet_sha256(sheet), status=status,
                                       pending=item in pending))
            items.append(item)
    return items


def report(tmp_path, folder, spec_dir, jt=None):
    return build_report(tmp_path / "res", ["demo"], tmp_path / "sh", jt or tmp_path / "jt", folders=folder.parent,
                        spec_root=spec_dir, questions_root=FIX)


def hand(m: dict, points: dict, faithful=None) -> dict:
    """A hand mark made on the answer and sheet of the marks file `m`."""
    return {"points": points, "faithful": faithful, "answer_sha256": m["answer_sha256"],
            "sheet_sha256": m["sheet"]["sha256"]}


def test_agreement_and_the_flag():
    judged_ = {f"i{k}": marks_of(f"demo/s1/engine/q{k:02d}") for k in range(10)}
    marks = {i: hand(m, {"p1": k < 9}) for k, (i, m) in enumerate(judged_.items())}
    a = agreement(list(judged_), marks, judged_)
    assert a["rate"] == 0.9 and not a["flag"] and a["answers_marked"] == 10
    marks = {i: hand(m, {"p1": k < 7}) for k, (i, m) in enumerate(judged_.items())}
    a = agreement(list(judged_), marks, judged_)
    assert a["rate"] == 0.7 and a["flag"] and len(a["disagreements"]) == 3
    assert FLAG_BELOW == 0.80


def test_unmarked_items_do_not_count():
    judged_ = {"i1": marks_of("demo/s1/engine/q01")}
    assert agreement(["i1"], {}, judged_)["rate"] is None and not agreement(["i1"], {}, judged_)["flag"]


def test_agreement_compares_faithful_with_b_and_leaves_a_pending_b_out():
    def with_b(**b):
        m = marks_of("demo/s1/engine/q01")
        m["B"] |= b
        return m
    judged_ = {"a": with_b(), "b": with_b(), "c": with_b(invented=1),
               "d": with_b(status="pending", invented=None, contradicted=None)}
    marks = {"a": hand(judged_["a"], {}, True), "b": hand(judged_["b"], {}, False),
             "c": hand(judged_["c"], {}, False), "d": hand(judged_["d"], {}, True)}
    a = agreement(list(judged_), marks, judged_)
    assert a["faithful"] == {"n": 3, "agree": 2, "rate": 2 / 3}


def test_a_hand_mark_on_another_answer_or_sheet_is_left_out_and_marked_again():
    """The point ids are positions: after a re-judge, p2 can be a different statement."""
    judged_ = {f"i{k}": marks_of(f"demo/s1/engine/q{k:02d}", answer=f"a{k}", sheet=f"s{k}") for k in range(4)}
    marks = {i: hand(m, {"p1": True, "p2": False}) for i, m in judged_.items()}
    marks["i1"]["answer_sha256"] = "older answer"
    marks["i2"]["sheet_sha256"] = "older sheet"
    del marks["i3"]["sheet_sha256"]   # made before the hashes were kept
    a = agreement(list(judged_), marks, judged_)
    assert a["points"] == 2 and a["answers_marked"] == 1 and a["to_mark_again"] == [2, 3, 4]
    assert a["marked"] == 1 and a["of"] == 4 and a["disagreements"] is None


def test_disagreements_wait_for_every_item_and_never_name_the_item():
    judged_ = {f"demo/s1/{s}/q01": marks_of(f"demo/s1/{s}/q01") for s in ("engine", BASELINE)}
    items = list(judged_)
    one = {items[0]: hand(judged_[items[0]], {"p1": False, "p2": False})}
    a = agreement(items, one, judged_)
    assert a["marked"] == 1 and a["of"] == 2 and a["disagreements"] is None and a["rate"] == 0.5
    both = one | {items[1]: hand(judged_[items[1]], {"p1": True, "p2": False})}
    a = agreement(items, both, judged_)
    assert a["disagreements"] == [{"n": 1, "point": "p1", "judge": True, "hand": False}]
    assert "engine" not in json.dumps(a) and BASELINE not in json.dumps(a)


def test_a_marked_item_with_no_current_marks_is_listed_as_not_judged():
    m = marks_of("demo/s1/engine/q01")
    a = agreement(["demo/s1/engine/q01"], {"demo/s1/engine/q01": hand(m, {"p1": True})}, {})
    assert a["not_judged"] == [1] and a["points"] == 0 and a["disagreements"] is None


def test_hand_marks_and_sample_round_trip(tmp_path):
    save_hand_mark(tmp_path, "demo/s1/engine/q01", {"p1": True}, None, "aditya", "2026-11-18",
                   answer_sha256="a1", sheet_sha256="s1")
    save_hand_mark(tmp_path, "demo/s1/engine/q02", {"p1": False}, True, "aditya", "2026-11-18",
                   answer_sha256="a2", sheet_sha256="s2")
    got = load_hand_marks(tmp_path)
    assert got["demo/s1/engine/q01"] == {"points": {"p1": True}, "faithful": None, "by": "aditya",
                                         "at": "2026-11-18", "answer_sha256": "a1", "sheet_sha256": "s1"}
    assert got["demo/s1/engine/q02"]["faithful"] is True and load_hand_marks(tmp_path / "none") == {}
    assert load_sample(tmp_path) == []


@pytest.mark.parametrize("name, text", [("sample.json", "[not json"), ("sample.json", '{"a": 1}'),
                                        ("marks.json", "{not json"), ("marks.json", "[1]")])
def test_a_damaged_sample_or_marks_file_is_a_value_error_naming_it(tmp_path, name, text):
    (tmp_path / name).write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=name):
        (load_sample if name == "sample.json" else load_hand_marks)(tmp_path)


def test_sample_is_balanced_capped_and_stable():
    marks = grid(questions=10, seeds=5)
    s = pick_sample(marks, n=10)
    assert s == pick_sample(marks, n=10) and len(s) == 10
    assert sum("/rag-baseline/" in i for i in s) == 5
    assert max(Counter(i.split("/")[3] for i in s).values()) <= 2


def test_sample_order_does_not_group_the_systems():
    """The review page numbers items in sample order; a sorted order would put every engine item first."""
    s = pick_sample(grid(questions=10, seeds=5), n=10, seed=0)
    assert s != sorted(s) and len({i.split("/")[2] for i in s[:5]}) == 2


def test_sample_skips_held_items_and_pending_c_and_the_other_half_fills_up():
    marks = grid(questions=10, seeds=5)
    items = list(marks)
    held = [i for i in items if i.startswith("demo/s1/engine/")]   # one per question: one more fits under the cap
    s = pick_sample(marks, n=10, have=held)
    assert not set(s) & set(held) and len(s) == 10
    pend = [i for i in items if "/engine/" in i]
    s = pick_sample(grid(questions=10, seeds=5, pending=pend), n=10)
    assert len(s) == 10 and all("/rag-baseline/" in i for i in s)


def test_the_cap_of_two_per_question_counts_the_items_already_in_the_sample():
    marks = grid(questions=3, seeds=5)
    have = pick_sample(marks, n=6)   # 3 questions x 2: every question is full
    assert sorted(Counter(i.split("/")[3] for i in have).values()) == [2, 2, 2]
    assert pick_sample(marks, n=4, have=have) == []


def test_only_current_marks_reach_the_sample(folder, tmp_path, SPEC, spec_dir):
    items = judged(tmp_path, folder, SPEC)
    f = load_folder(folder)
    q = load_questions("demo", SPEC, FIX).get("d01")
    save_answer(tmp_path / "res", rec("Re-collected.", question_id="d01", question_sha256=question_sha256(q),
                                      corpus_id=f.corpus_id))   # judge not run again
    got = current_marks_of(tmp_path / "res", ["demo"], tmp_path / "sh", folder.parent, spec_dir, FIX)
    assert set(got) == set(items) - {"demo/s1/engine/d01"}


def test_report_puts_the_baseline_next_to_the_system_and_flags(folder, tmp_path, spec_dir, SPEC):
    items = judged(tmp_path, folder, SPEC)   # 6 answers; the judge ticks p1 met on each
    jt = tmp_path / "jt"
    write_json_atomic(jt / "sample.json", items)
    current = current_marks_of(tmp_path / "res", ["demo"], tmp_path / "sh", folder.parent, spec_dir, FIX)
    for k, item in enumerate(items):                # 4 of the 6 hand marks agree on p1: 67%
        m = current[item]
        save_hand_mark(jt, item, {"p1": k < 4}, None, "a", "t", answer_sha256=m["answer_sha256"],
                       sheet_sha256=m["sheet"]["sha256"])
    r = report(tmp_path, folder, spec_dir, jt)
    md = render_report(r)
    d = r["domains"]["demo"]
    assert set(d["systems"]) == {"engine", BASELINE}
    assert d["systems"]["engine"]["answers"] == 3 and d["systems"][BASELINE]["judged"] == 3
    assert d["systems"][BASELINE]["a_mean"] is None and d["systems"]["engine"]["a_mean"] == 0.5
    assert "engine" in md and BASELINE in md and "n/a" in md
    assert md.index("engine") < md.index(BASELINE)
    assert "Judge agreement 67% (below 80%: reported as a limitation)." in md
    assert r["agreement"]["flag"] is True and len(r["agreement"]["disagreements"]) == 2


def test_the_report_never_shows_the_system_of_a_judge_test_item(folder, tmp_path, spec_dir, SPEC):
    """Aditya marks blind; the report is read before and while he marks."""
    items = judged(tmp_path, folder, SPEC)
    jt = tmp_path / "jt"
    write_json_atomic(jt / "sample.json", items)
    m = current_marks_of(tmp_path / "res", ["demo"], tmp_path / "sh", folder.parent, spec_dir, FIX)[items[0]]
    save_hand_mark(jt, items[0], {"p1": False, "p2": False}, None, "a", "t", answer_sha256=m["answer_sha256"],
                   sheet_sha256=m["sheet"]["sha256"])
    r = report(tmp_path, folder, spec_dir, jt)
    md = render_report(r)
    listed = r["domains"]["demo"]["judge_test_items"]
    assert listed[0] == {"n": 1, "domain": "demo", "seed": 1, "question": "d01"} and len(listed) == 6
    assert not any(i in md or i in json.dumps(listed) for i in items)
    assert r["agreement"]["disagreements"] is None and "Judge test: 1 of 6 marked." in md
    judge_test = md[md.index("Judge-test items"):]
    assert "engine" not in judge_test and BASELINE not in judge_test


def test_report_counts_only_current_marks_and_shows_the_rest(folder, tmp_path, spec_dir, SPEC):
    """A re-collected answer that is not judged again, and an answer that was never judged, are not in the means;
    `answers` counts every saved answer."""
    judged(tmp_path, folder, SPEC, systems=("engine",))
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX)
    save_answer(tmp_path / "res", rec("Re-collected.", question_id="d01", question_sha256=question_sha256(qs.get("d01")),
                                      corpus_id=f.corpus_id))
    path = marks_path(tmp_path / "res", "demo", 1, "engine", "d02")
    m = json.loads(path.read_text(encoding="utf-8")); m["C"]["score"] = 0.0
    write_json_atomic(path, m)
    save_answer(tmp_path / "res", rec("Never judged.", question_id="d03", system="other",
                                      question_sha256=question_sha256(qs.get("d03")), corpus_id=f.corpus_id))
    rows = report(tmp_path, folder, spec_dir)["domains"]["demo"]["systems"]
    eng = rows["engine"]
    assert (eng["answers"], eng["judged"], eng["not_current"], eng["skipped"]) == (3, 2, 1, 0)
    assert eng["c_mean"] == 0.25   # d02 (0.0) and d03 (0.5); the old d01 marks are left out
    assert (rows["other"]["answers"], rows["other"]["judged"], rows["other"]["skipped"]) == (1, 0, 1)
    md = render_report(report(tmp_path, folder, spec_dir))
    assert "not current" in md and "skipped" in md


def test_report_leaves_a_pending_answer_out_of_its_means_and_counts_unchecked_marks(folder, tmp_path, spec_dir,
                                                                                    SPEC):
    judged(tmp_path, folder, SPEC, status="drafted", pending=["demo/s1/engine/d03"])
    r = report(tmp_path, folder, spec_dir)
    eng = r["domains"]["demo"]["systems"]["engine"]
    assert eng["answers"] == 3 and eng["pending"] == 1
    assert eng["c_mean"] == 0.5 and eng["b_mean"] == 1.0   # C's mean leaves the pending one out; B's keeps it
    assert eng["unchecked"] == 3 and r["domains"]["demo"]["systems"][BASELINE]["unchecked"] == 3
    assert "unchecked" in render_report(r)


def test_report_counts_the_sheets_of_every_seed_with_stale_ones_apart(folder, tmp_path, spec_dir, SPEC):
    judged(tmp_path, folder, SPEC, qids=("d01",))   # s1: d01 checked
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX)
    old = make_sheet(f, qs.get("d02"), [("T", ["pair:a:m1"])], {"model": "x"})
    save_sheet(tmp_path / "sh", old.model_copy(update={"status": "checked", "question_sha256": "1" * 64}))
    build_folder(folder.parent / "s2", SPEC, approved(SPEC, 2), 40, "table")   # no answers: still counted
    r = report(tmp_path, folder, spec_dir)
    assert r["domains"]["demo"]["sheets"] == {"checked": 1, "drafted": 0, "stale": 1, "missing": 4}
    assert "1 checked, 0 drafted, 1 stale, 4 missing" in render_report(r)


def test_most_missed_takes_the_text_the_judge_saw(folder, tmp_path, spec_dir, SPEC):
    judged(tmp_path, folder, SPEC, qids=("d01",))
    for system in ("engine", BASELINE):
        path = marks_path(tmp_path / "res", "demo", 1, system, "d01")
        m = json.loads(path.read_text(encoding="utf-8"))
        m["sheet"]["points"][1]["text"] = "The text the judge saw."
        write_json_atomic(path, m)
    top = report(tmp_path, folder, spec_dir)["domains"]["demo"]["most_missed"][0]
    assert (top["question"], top["point"], top["missed"], top["of"]) == ("d01", "p2", 2, 2)   # both systems missed it
    assert top["text"] == "The text the judge saw."


def test_report_a_cross_check_compares_the_judge_with_the_spans(folder, tmp_path, spec_dir, SPEC):
    """A `found` mark with no pulled fact on its span and a `missing` mark with one are what the cross-check counts."""
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); q = qs.get("d01")
    planted = [p for ps in planted_facts(f, q).values() for p in ps]
    first = planted[0]
    a, b = first.spans[0]
    touch = PulledFact(paper=first.paper, kind="measurement", fields={}, quote="x", start=a, end=b)
    judged(tmp_path, folder, SPEC, systems=("engine",), qids=("d01",), facts=[touch])
    path = marks_path(tmp_path / "res", "demo", 1, "engine", "d01")
    mk = json.loads(path.read_text(encoding="utf-8"))
    papers: dict = {}
    for p in planted:
        papers.setdefault(p.paper, []).append({"fact": p.id, "verdict": "missing" if p is first else "found",
                                               "pulled": None if p is first else 1, "reason": ""})
    mk["A"]["papers"] = papers
    write_json_atomic(path, mk)
    row = report(tmp_path, folder, spec_dir)["domains"]["demo"]["systems"]["engine"]
    assert row["a_found_untouched"] == 1.0   # no `found` fact has a pulled fact on its span (the touched one is missing)
    assert row["a_missing_touched"] == 1.0   # the one `missing` fact has one


def test_judge_sample_by_command(folder, tmp_path, spec_dir, SPEC, capsys):
    judged(tmp_path, folder, SPEC)
    jt = tmp_path / "jt"
    argv = ["judge-sample", "--domains", "demo", "--n", "4", "--results", str(tmp_path / "res"),
            "--judge-test", str(jt), "--sheets", str(tmp_path / "sh"), "--folders", str(folder.parent),
            "--spec-root", str(spec_dir), "--questions-root", str(FIX)]
    assert main(argv) == 0
    first = load_sample(jt)
    assert len(first) == 4
    assert main(argv) == 2 and "sample.json" in capsys.readouterr().err
    assert main(argv + ["--add", "2"]) == 0
    both = load_sample(jt)
    assert len(both) == 6 and both[:4] == first


def test_report_by_command(folder, tmp_path, spec_dir, SPEC, capsys):
    judged(tmp_path, folder, SPEC)
    out = tmp_path / "out" / "r.json"
    argv = ["report", "--domains", "demo", "--out", str(out), "--results", str(tmp_path / "res"),
            "--sheets", str(tmp_path / "sh"), "--judge-test", str(tmp_path / "jt"),
            "--folders", str(folder.parent), "--spec-root", str(spec_dir), "--questions-root", str(FIX)]
    code = main(argv)
    assert code == 0 and out.is_file() and out.with_suffix(".md").is_file()
    assert json.loads(out.read_text(encoding="utf-8"))["domains"]["demo"]
    assert "demo" in capsys.readouterr().out


def test_judge_sample_names_a_bad_row_of_the_sample(folder, tmp_path, spec_dir, SPEC, capsys):
    judged(tmp_path, folder, SPEC)
    write_json_atomic(tmp_path / "jt" / "sample.json", ["nonsense"])
    code = main(["judge-sample", "--domains", "demo", "--add", "2", "--results", str(tmp_path / "res"),
                 "--judge-test", str(tmp_path / "jt"), "--sheets", str(tmp_path / "sh"), "--folders",
                 str(folder.parent), "--spec-root", str(spec_dir), "--questions-root", str(FIX)])
    assert code == 2 and "'nonsense' is not <domain>/s<seed>/<system>/<qid>" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["report", "judge-sample"])
def test_folders_with_more_than_one_domain_is_refused(tmp_path, command, capsys):
    """`--folders` holds one domain's `s<seed>/`; two domains would read the same folders."""
    argv = [command, "--domains", "demo,law", "--folders", str(tmp_path), "--results", str(tmp_path / "res")]
    argv += ["--out", str(tmp_path / "r.json")] if command == "report" else ["--judge-test", str(tmp_path / "jt")]
    assert main(argv) == 2 and "--folders" in capsys.readouterr().err


def test_help_lists_every_command(capsys):
    """argparse expands % in help text: a bare "80%" crashed `synth3 --help`."""
    try:
        main(["--help"])
    except SystemExit as e:
        assert e.code == 0
    out = capsys.readouterr().out
    for cmd in ("questions", "draft-sheets", "collect", "baseline", "judge", "judge-sample", "report"):
        assert cmd in out
