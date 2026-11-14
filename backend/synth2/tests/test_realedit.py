import json
import re

import pytest

from synth2 import realedit
from synth2.realedit import (SURNAME_POOL, apply_edits, apply_map, build_map, check_paper, surviving)

from synth2.tests.conftest import SOURCE_PAPER, STUDY_INPUT


def test_renaming_is_deterministic_for_a_seed():
    a = build_map(SOURCE_PAPER, "seed-1")
    assert a == build_map(SOURCE_PAPER, "seed-1")
    assert a != build_map(SOURCE_PAPER, "seed-2")
    assert list(a) == sorted(a)                      # same file on every run
    assert apply_map(SOURCE_PAPER, a, "seed-1") == apply_map(SOURCE_PAPER, a, "seed-1")


def test_renaming_is_consistent_across_variants_of_a_name():
    m = build_map(SOURCE_PAPER, "seed-1")
    assert "FiD" in m and "FiD-RAG" in m
    assert m["FiD-RAG"] == m["FiD"] + "-RAG"        # RAG is a field word: kept
    out = apply_map(SOURCE_PAPER, m, "seed-1")
    assert out.count(m["FiD"]) == 5 and "FiD" not in out.replace(m["FiD-RAG"], "")


def test_renaming_keeps_the_shape_and_the_keep_words():
    m = build_map(SOURCE_PAPER, "seed-1")
    for old, new in m.items():
        if new in SURNAME_POOL:
            continue                              # cited surnames come from the pool, any length
        assert len(old) == len(new) and old != new
        assert [c.isupper() for c in old] == [c.isupper() for c in new]
    out = apply_map(SOURCE_PAPER, m, "seed-1")
    assert "Wikipedia" in out and "RAG" in out
    assert not set(m) & {"Wikipedia", "RAG"}


def test_cited_surnames_come_from_the_surname_pool():
    m = build_map(SOURCE_PAPER, "seed-1")
    for s in ("Karpukhin", "Smith", "Jones", "Roberts"):
        assert m[s] in SURNAME_POOL and m[s] != s
    assert len({m[s] for s in ("Karpukhin", "Smith", "Jones", "Roberts")}) == 4
    out = apply_map(SOURCE_PAPER, m, "seed-1")
    assert f"{m['Karpukhin']} et al. (2020)" in out and f"{m['Smith']} and {m['Jones']} (2019)" in out


def test_no_mapped_name_is_left_and_urls_become_invented():
    m = build_map(SOURCE_PAPER, "seed-1")
    out = apply_map(SOURCE_PAPER, m, "seed-1")
    assert surviving(out, m) == []
    assert surviving(SOURCE_PAPER, m) != []
    assert "someone/tool" not in out and re.search(r"https://github\.com/\w+/\w+", out)


def test_prepare_writes_sources_maps_and_inputs(edit_base):
    inp = json.loads((edit_base / "inputs" / "S001.json").read_text(encoding="utf-8"))
    assert set(inp) == set(realedit.KEEP_FIELDS) | {"source"}
    mp = json.loads((edit_base / "maps" / "S001.json").read_text(encoding="utf-8"))
    assert mp["source_id"] == "source" and "FiD" in mp["map"]
    renamed = (edit_base / "sources" / "S001.md").read_text(encoding="utf-8")
    assert surviving(renamed, mp["map"]) == []
    assert all((edit_base / d).is_dir() for d in ("edits", "papers", "inserted"))


def test_apply_edits_fails_a_string_that_is_not_there_exactly_once():
    renamed = "# Old\n\nAlpha beta. Alpha gamma. Delta.\n"
    text, inserted, problems = apply_edits(renamed, {"title": "New", "replace": [
        {"old": "Alpha", "new": "X"}, {"old": "missing", "new": "Y"}, {"old": "Delta.", "new": "Done."}],
        "insert_after": [{"anchor": "Alpha", "text": "Z"}, {"anchor": "nothing", "text": "Z"}]}, "Lee et al. (2021)")
    assert len(problems) == 4
    assert "found 2 times" in problems[0] and "found 0 times" in problems[1]
    assert "anchor found 2 times" in problems[2] and "anchor found 0 times" in problems[3]
    assert text == "# New\n\nLee et al. (2021)\n\nAlpha beta. Alpha gamma. Done.\n"
    assert inserted == ["New", "Done."]


def test_apply_edits_replaces_inserts_and_renames():
    renamed = "# Old\n\nFirst para. Cat sat.\n\nSecond para.\n"
    text, inserted, problems = apply_edits(renamed, {
        "title": " Title ", "rename": [{"old": "Cat", "new": "Dog"}, {"old": "Bird", "new": "Owl"}],
        "replace": [{"old": "First para.", "new": "One."}],
        "insert_after": [{"anchor": "Second para.", "text": " Added text. "}]}, "Lee et al. (2021)")
    assert problems == ["rename: 'Bird' not found"]
    assert text == "# Title\n\nLee et al. (2021)\n\nOne. Dog sat.\n\nSecond para.\n\nAdded text.\n\n"
    assert inserted == [" Title ", "One.", " Added text. "]


def test_a_rename_to_control_wording_is_a_problem():
    _, _, problems = apply_edits("# O\n\nCat sat.\n", {"title": "T", "rename": [{"old": "Cat", "new": "vanilla"}]}, "L")
    assert any("control wording" in p for p in problems)


GOOD = ("# A Study\n\nLee et al. (2021)\n\nOn TrivBench the augmented system answered 70 of 100 questions (70.0%), "
        "and the other 50 of 100 (50.0%). TrivBench was used again.\n")


def problems_of(text, inserted=None, mapping=None, inp=None):
    return check_paper(text, ["A Study"] if inserted is None else inserted, inp or STUDY_INPUT, mapping or {})


def test_a_good_paper_passes_the_checks():
    assert problems_of(GOOD) == []


def test_check_flags_a_missing_count():
    assert "count 70 missing" in problems_of(GOOD.replace("70 of", "seventy of"))
    assert "accuracy of 50/100 missing" in problems_of(GOOD.replace("50.0", "fifty"))


def test_check_flags_a_verbatim_level_name():
    assert "level name 'Low Noise' written verbatim" in problems_of(GOOD + "Under low noise it held.\n")


def test_check_flags_a_surviving_real_name():
    out = problems_of(GOOD + "Karpukhin said so.\n", mapping={"Karpukhin": "Vogel"})
    assert any(p.startswith("real names survive ['Karpukhin']") for p in out)


def test_check_flags_control_wording_outside_inserted_text_only():
    text = GOOD + "The closed-book run and PlainSys did worse.\n"
    out = problems_of(text)
    assert any("outside the inserted text" in p and "closed-book" in p and "PlainSys" in p for p in out)
    assert problems_of(text, inserted=["A Study", "The closed-book run and PlainSys did worse."]) == []


def test_check_flags_meta_wording_inside_inserted_text_only():
    assert any("meta wording 'as instructed'" in p for p in problems_of(GOOD, inserted=["A Study", "as instructed"]))
    assert problems_of(GOOD + "Follow the instructions.\n") == []          # real text may say it


def test_check_flags_more_than_1800_inserted_words():
    out = problems_of(GOOD, inserted=["A Study", "word " * 1801])
    assert any(p.startswith("1803 inserted words") for p in out)
    assert problems_of(GOOD, inserted=["A Study", "word " * 1798]) == []


CLAIMED = {**STUDY_INPUT, "claim_sentence": "Overall, the augmented system answers more questions than the baseline."}


def claim_problems_of(inserted):
    return check_paper(GOOD, ["A Study"] + inserted, CLAIMED, {}, claim_rules=True)


def test_claim_rules_flag_a_copied_run_of_four_claim_words():
    out = claim_problems_of(["We see that the augmented system answers more often."])
    assert "inserted text copies the claim sentence: ['augmented system answers more', 'the augmented system answers']" \
        in out


def test_claim_rules_pass_a_claim_in_the_paper_s_own_words():
    assert claim_problems_of(["Adding retrieved passages helps: FindSys is right more often than PlainSys."]) == []


def test_claim_rules_cap_overused_words_in_inserted_text_only():
    out = claim_problems_of(["Overall it works. Overall it holds. One subset, a second subset, a third subset."])
    assert "inserted text: 'overall' 2 times (limit 1)" in out
    assert "inserted text: 'subset/subsets' 3 times (limit 2)" in out
    real = GOOD + "Overall, overall, overall: each subset was correctly asked.\n"
    assert check_paper(real, ["A Study"], CLAIMED, {}, claim_rules=True) == []


def test_claim_rules_are_off_by_default():
    assert check_paper(GOOD, ["A Study", "Overall, the augmented system answers more questions."], CLAIMED, {}) == []


def test_check_flags_a_label_that_is_not_under_the_title():
    assert "label is not the author line under the title" in problems_of(GOOD.replace("Lee et al. (2021)", "Other"))


def test_apply_study_writes_the_paper_and_reports_problems(edit_base):
    mp = json.loads((edit_base / "maps" / "S001.json").read_text(encoding="utf-8"))["map"]
    fid = mp["FiD"]
    edits = {"title": "New Title", "insert_after": [
        {"anchor": "## Results", "text": "On TrivBench the augmented system answered 70 of 100 "
                                           "(70.0%) and the other 50 of 100 (50.0%). TrivBench again."}]}
    (edit_base / "edits" / "S001.json").write_text("﻿" + json.dumps(edits), encoding="utf-8")   # BOM is fine
    done = realedit.apply_study(edit_base, "S001")
    assert done["problems"] == [] and done["inserted"] > 0
    paper = (edit_base / "papers" / "S001.md").read_text(encoding="utf-8")
    assert paper.startswith("# New Title\n\nLee et al. (2021)\n\n") and fid in paper
    assert json.loads((edit_base / "inserted" / "S001.json").read_text(encoding="utf-8"))[0] == "New Title"
    (edit_base / "edits" / "S001.json").write_text("{not json", encoding="utf-8")
    bad = realedit.apply_study(edit_base, "S001")
    assert bad["problems"][0].startswith("edits file unreadable")


def test_apply_study_reports_an_anchor_that_is_missing(edit_base):
    (edit_base / "edits" / "S001.json").write_text(
        json.dumps({"title": "T", "insert_after": [{"anchor": "no such text", "text": "x"}]}), encoding="utf-8")
    assert any("anchor found 0 times" in p for p in realedit.apply_study(edit_base, "S001")["problems"])


def test_apply_study_and_check_base_pass_claim_rules_on(edit_base, tmp_path):
    claim = json.loads((edit_base / "inputs" / "S001.json").read_text(encoding="utf-8"))["claim_sentence"]
    edits = {"title": "New Title", "insert_after": [
        {"anchor": "## Results", "text": f"On TrivBench the augmented system answered 70 of 100 (70.0%) and the other "
                                         f"50 of 100 (50.0%). TrivBench again. {claim}"}]}
    (edit_base / "edits" / "S001.json").write_text(json.dumps(edits), encoding="utf-8")
    assert realedit.apply_study(edit_base, "S001")["problems"] == []
    on = realedit.apply_study(edit_base, "S001", claim_rules=True)["problems"]
    assert any(p.startswith("inserted text copies the claim sentence") for p in on)
    reader = make_truth(tmp_path / "grid", [CELL])
    report, _ = realedit.check_base(tmp_path / "grid", edit_base, [reader], claim_rules=True)
    assert any(p.startswith("inserted text copies the claim sentence") for p in report["S001"]["problems"])


def make_truth(base_dir, reader_cells):
    truth = {"conditions": [{"levels": [{"name": "Low Noise", "id": "L0"}]}],
             "studies": [{"id": "S001", "label": "Lee et al. (2021)", "claim": "better", "dataset": "TrivBench",
                          "cells": [{"levels": {"noise": "L0"}, "k_t": 70, "n_t": 100, "k_c": 50, "n_c": 100}]}]}
    base_dir.mkdir()
    (base_dir / "ground_truth.json").write_text(json.dumps(truth), encoding="utf-8")
    reader = [{"paper": "S001", "label": "Lee et al. (2021)", "claim": "better", "benchmark": "TrivBench",
               "other_results": [], "cells": reader_cells}]
    f = base_dir / "reader.json"
    f.write_text(json.dumps(reader), encoding="utf-8")
    return f


def checked_base(edit_base):
    paper = GOOD.replace("# A Study", "# New Title")
    (edit_base / "papers" / "S001.md").write_text(paper, encoding="utf-8")
    (edit_base / "inserted" / "S001.json").write_text(json.dumps(["New Title"]), encoding="utf-8")
    mp = json.loads((edit_base / "maps" / "S001.json").read_text(encoding="utf-8"))["map"]
    assert not any(n in paper for n in mp)


CELL = {"levels": ["Low Noise"], "treatment_correct": 70, "treatment_total": 100, "control_correct": 50,
        "control_total": 100}


def test_check_base_keeps_a_study_the_reader_reads_right(edit_base, tmp_path):
    checked_base(edit_base)
    reader = make_truth(tmp_path / "grid", [CELL])
    report, extras = realedit.check_base(tmp_path / "grid", edit_base, [reader])
    assert report["S001"]["ok"] and extras == 0
    assert json.loads((edit_base / "check.json").read_text(encoding="utf-8")) == report


def test_check_base_flags_what_the_reader_got_wrong(edit_base, tmp_path):
    checked_base(edit_base)
    reader = make_truth(tmp_path / "grid", [{**CELL, "control_correct": 51}])
    report, _ = realedit.check_base(tmp_path / "grid", edit_base, [reader])
    assert not report["S001"]["ok"] and "reader cells" in report["S001"]["problems"][0]
    report, _ = realedit.check_base(tmp_path / "grid", edit_base, [])          # no reader: code checks only
    assert report["S001"]["ok"]


def test_check_base_flags_a_missing_reader_entry(edit_base, tmp_path):
    checked_base(edit_base)
    make_truth(tmp_path / "grid", [CELL])
    other = tmp_path / "other.json"
    other.write_text(json.dumps([{"paper": "S999"}]), encoding="utf-8")
    report, _ = realedit.check_base(tmp_path / "grid", edit_base, [other])
    assert report["S001"]["problems"] == ["reader gave nothing"]


def test_assign_sources_gives_each_study_its_own_candidate(tmp_path):
    def text(cited):
        return ("word " * 4500) + (" Smith et al. (2020) " if cited else " [1] [2] ")
    rows, full = [], tmp_path / "full"
    full.mkdir()
    for i, (title, cited, year) in enumerate([("RAG one", True, "2021"), ("RAG two", True, "2021"),
                                              ("RAG survey", True, "2021"), ("RAG numeric", False, "2021"),
                                              ("RAG old", True, "2015")]):
        pid = f"p{i}"
        rows.append({"arxiv_id": pid, "title": title, "summary": "", "published": f"{year}-01-01"})
        (full / f"{pid}.md").write_text(text(cited), encoding="utf-8")
    rows_path = tmp_path / "rows.jsonl"
    rows_path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    split = tmp_path / "split.json"
    split.write_text(json.dumps({"sources": [r["arxiv_id"] for r in rows], "test": []}), encoding="utf-8")
    inputs = tmp_path / "in"
    inputs.mkdir()
    for s in ("S001", "S002"):
        (inputs / f"{s}.json").write_text(json.dumps({"label": s}), encoding="utf-8")
    done = realedit.assign_sources(inputs, rows_path, split, full, tmp_path / "out")
    assert {pid for _, pid in done} == {"p0", "p1"}          # not the survey, numeric citations or old paper
    out = json.loads((tmp_path / "out" / "S001.json").read_text(encoding="utf-8"))
    assert out["skeleton_source"].endswith(".md") and out["label"] == "S001"
    (inputs / "S003.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="candidate sources"):
        realedit.assign_sources(inputs, rows_path, split, full, tmp_path / "out2")


def test_assign_sources_refuses_a_paper_on_both_sides(tmp_path):
    rows = tmp_path / "rows.jsonl"
    rows.write_text("", encoding="utf-8")
    split = tmp_path / "split.json"
    split.write_text(json.dumps({"sources": ["a"], "test": ["a"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="both sides"):
        realedit.assign_sources(tmp_path, rows, split, tmp_path, tmp_path / "o")
