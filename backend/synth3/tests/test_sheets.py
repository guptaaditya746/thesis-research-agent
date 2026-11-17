import pytest

from synth3.sheetfacts import FactLine, load_folder
from synth3.sheets import (CANT_TELL_POINT, archive_sheet, cant_tell_sheet, check_points, check_sheet,
                           coverage_warnings, folders_of, load_sheet, make_sheet, person_sheet, review_queue,
                           save_sheet, stale)
from synth3.tests.conftest import built, label, q, seed_with


def test_cant_tell_sheet_has_the_one_point(tmp_path, SPEC):
    f = load_folder(built(tmp_path, SPEC, seed_with(SPEC, lambda t: t["world"]["uncovered"])))
    tr, m = f.truth["world"]["uncovered"][0]
    s = cant_tell_sheet(f, q(f"Does {label(SPEC, tr)} change the {SPEC.measure(m).name}?"))
    assert s.cant_tell and [p.text for p in s.points] == [CANT_TELL_POINT] and s.drafted_by == {"code": "cant_tell"}


def test_point_checks_name_the_problem():
    facts = [FactLine(id="pair:a:m1", text="x")]
    assert any("at most 6" in p for p in check_points([("t%d" % i, ["pair:a:m1"]) for i in range(7)], facts, by_model=True))
    assert check_points([("t", ["pair:zz:m9"])], facts, by_model=True) == ["point 1: unknown fact pair:zz:m9"]
    assert check_points([("t", [])], facts, by_model=True) and not check_points([("t", [])], facts, by_model=False)
    assert check_points([("Up by 12% in S004.", ["pair:a:m1"])], facts, by_model=True) == ["point 1: holds a number"]
    assert not check_points([("Better in S004.", ["pair:a:m1"])], facts, by_model=True)


def test_every_point_check_names_its_problem():
    facts = [FactLine(id="pair:a:m1", text="x")]
    assert check_points([], facts, by_model=False) == ["no points"]
    assert check_points([("  ", [])], facts, by_model=False) == ["point 1: empty text"]
    assert check_points([("y" * 301, [])], facts, by_model=False) == ["point 1: longer than 300 characters"]
    assert check_points([("Same.", []), (" Same. ", [])], facts, by_model=False) == ["point 2: same text as point 1"]
    assert check_points([("t", ["pair:a:m1"])], facts, by_model=True) == []


def test_a_person_sheet_with_a_bad_point_is_refused(folder):
    with pytest.raises(ValueError, match="point 1: unknown fact pair:zz:m9"):
        person_sheet(load_folder(folder), q("Does Targeted therapy raise the Response rate?"),
                     [("Mine.", ["pair:zz:m9"])], "aditya", "t", checked=True)


def test_no_cant_tell_sheet_when_the_folder_can_answer(folder):
    assert cant_tell_sheet(load_folder(folder), q("Does Targeted therapy raise the Response rate?")) is None


def test_a_digit_inside_a_spec_name_is_not_a_number():
    facts = [FactLine(id="pair:a:m1", text="x")]
    pts = [("Drug B12 does better.", ["pair:a:m1"])]
    assert check_points(pts, facts, by_model=True) == ["point 1: holds a number"]
    assert not check_points(pts, facts, by_model=True, names=["Drug B12"])
    assert check_points([("Drug B12 gains 5 points.", ["pair:a:m1"])], facts, by_model=True,
                        names=["Drug B12"]) == ["point 1: holds a number"]


def test_only_pair_and_head_to_head_lines_warn():
    facts = [FactLine(id="pair:a:m1", text="x"), FactLine(id="rank:m1", text="y"), FactLine(id="study:S001", text="z"),
             FactLine(id="h2h:a:b:m1", text="w")]
    assert coverage_warnings([], facts) == ["fact pair:a:m1 is in no point", "fact h2h:a:b:m1 is in no point"]
    assert coverage_warnings([("t", ["h2h:a:b:m1"])], facts) == ["fact pair:a:m1 is in no point"]


def test_a_sheet_goes_stale_when_the_question_or_truth_changes(folder, SPEC, tmp_path):
    f = load_folder(folder); qq = q("Does Targeted therapy raise the Response rate?")
    s = make_sheet(f, qq, [("Targeted therapy does better.", ["pair:a:m1"])], {"model": "fake"})
    save_sheet(tmp_path / "sh", s)
    assert load_sheet(tmp_path / "sh", "demo", 1, "x") == s and stale(s, qq, f) is None
    assert stale(s, qq.model_copy(update={"notes": "n"}), f) is None
    assert stale(s, qq.model_copy(update={"sub_questions": ["Which studies?"]}), f) is None   # not scored
    assert "question changed" in stale(s, qq.model_copy(update={"question": "Other?"}), f)
    other = load_folder(built(tmp_path, SPEC, 2))
    assert "truth changed" in stale(s, qq, other)


def test_checking_records_who_and_drops_cant_tell(folder, tmp_path, SPEC):
    f = load_folder(folder); qq = q("Does Targeted therapy raise the Response rate?")
    s = make_sheet(f, qq, [("A.", ["pair:a:m1"])], {"model": "fake"})
    done = check_sheet(s, [("Targeted therapy does better than Standard care.", [])], "aditya", "2026-11-18T10:00:00Z")
    assert done.status == "checked" and done.checked_by == "aditya" and done.points[0].id == "p1"
    with pytest.raises(ValueError, match="point 1"):
        check_sheet(s, [("", [])], "aditya", "t")
    # a can't-tell sheet loses the flag once Aditya's points are anything else
    g = load_folder(built(tmp_path, SPEC, seed_with(SPEC, lambda t: t["world"]["uncovered"])))
    tr, m = g.truth["world"]["uncovered"][0]
    ct = cant_tell_sheet(g, q(f"Does {label(SPEC, tr)} change the {SPEC.measure(m).name}?"))
    assert ct.cant_tell
    assert check_sheet(ct, [(CANT_TELL_POINT, [])], "aditya", "t").cant_tell
    assert not check_sheet(ct, [("It does better.", [])], "aditya", "t").cant_tell


def test_a_person_sheet_replaces_a_stale_one_unchecked(folder, tmp_path):
    f = load_folder(folder); old = q("Does Targeted therapy raise the Response rate?")
    s = make_sheet(f, old, [("A.", ["pair:a:m1"])], {"model": "fake"}); save_sheet(tmp_path / "sh", s)
    new = old.model_copy(update={"question": "Does Targeted therapy change the Response rate?"})
    archived = archive_sheet(tmp_path / "sh", s)
    fresh = person_sheet(f, new, [("Targeted therapy does better.", [])], "aditya", "t", checked=False)
    assert archived.name == "x.stale-1.json" and archived.is_file()
    assert fresh.status == "drafted" and stale(fresh, new, f) is None and fresh.drafted_by == {"person": "aditya"}
    assert person_sheet(f, new, [("B.", [])], "aditya", "t", checked=True).status == "checked"


def test_archive_never_overwrites(folder, tmp_path):
    f = load_folder(folder); qq = q("Does Targeted therapy raise the Response rate?")
    s = make_sheet(f, qq, [("A.", ["pair:a:m1"])], {"model": "fake"})
    for n in (1, 2):
        save_sheet(tmp_path / "sh", s)
        assert archive_sheet(tmp_path / "sh", s).name == f"x.stale-{n}.json"
    assert load_sheet(tmp_path / "sh", "demo", 1, "x") is None
    with pytest.raises(ValueError, match=r"x\.json: no sheet file to archive"):
        archive_sheet(tmp_path / "sh", s)


def test_review_queue_full_folder_and_a_sample_that_never_moves(tmp_path):
    seeds, qids = [1, 2, 3, 4, 5], ["d01", "d02", "d03"]
    rows = review_queue(tmp_path, "demo", seeds, qids, rate=0.3)
    assert {(r["seed"], r["must_check"]) for r in rows if r["seed"] == 1} == {(1, "full")}
    picked = {(r["seed"], r["question_id"]) for r in rows if r["must_check"] == "sample"}
    more = review_queue(tmp_path, "demo", seeds, [*qids, "d04"], rate=0.3)
    assert picked == {(r["seed"], r["question_id"]) for r in more if r["must_check"] == "sample"
                      and r["question_id"] != "d04"}
    assert all(r["must_check"] == "sample" for r in review_queue(tmp_path, "demo", seeds, qids, rate=1.0)
               if r["seed"] != 1)
    assert all(r["status"] == "missing" for r in rows)


def test_review_queue_reports_stale_only_when_given_questions_and_folders(folder, tmp_path):
    f = load_folder(folder); qq = q("Does Targeted therapy raise the Response rate?")
    save_sheet(tmp_path / "sh", make_sheet(f, qq, [("A.", ["pair:a:m1"])], {"model": "fake"}))
    plain = review_queue(tmp_path / "sh", "demo", [1], ["x"])
    assert plain[0]["status"] == "drafted" and plain[0]["stale"] is None
    changed = qq.model_copy(update={"question": "Other?"})
    rows = review_queue(tmp_path / "sh", "demo", [1], ["x"], questions={"x": changed}, folders={1: f})
    assert "question changed" in rows[0]["stale"]
    fresh = review_queue(tmp_path / "sh", "demo", [1], ["x"], questions={"x": qq}, folders={1: f})
    assert fresh[0]["stale"] is None


def test_folders_of_prefers_the_real_set(tmp_path):
    (tmp_path / "demo").mkdir()
    assert folders_of("demo", tmp_path) == tmp_path / "demo"
    (tmp_path / "demo-real").mkdir()
    assert folders_of("demo", tmp_path) == tmp_path / "demo-real"
