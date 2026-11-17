import json
import re
from pathlib import Path

import pytest

from synth3.cli import main
from synth3.corpus import build_folder
from synth3.questions import Question
from synth3.realcorpus import build_real_folder
from synth3.sheetfacts import (cant_tell, check_spec, load_folder, named, relevant_facts, scope, truth_sha256)
from synth3.tests.conftest import approved, built, label, q, seed_with

FIX = Path(__file__).parent / "fixtures" / "questions"


def truth(f):
    return json.loads((Path(f) / "ground_truth.json").read_text(encoding="utf-8"))


def test_named_matches_plural_and_case_but_not_inside_words(SPEC):
    n = named(SPEC, "Is targeted therapy better than standard care for Older patients at the Coastal health service?")
    assert n.arms == ["ctrl", "a"] and n.conditions == ["age"] and n.settings == ["Coastal health service"]
    assert named(SPEC, "Response rates of each arm").measures == ["m1"]
    assert named(SPEC, "Targeted therapyX").arms == []


def test_one_treatment_and_one_measure(folder, SPEC):
    t = truth(folder)
    ids = [f.id for f in relevant_facts(SPEC, t, q("Does Targeted therapy raise the Response rate?"))]
    want = [f"h2h:{h['arm']}:{h['against']}:m1" for h in t["facts"]["head_to_head"]
            if h["measure"] == "m1" and "a" in (h["arm"], h["against"])]
    assert ids == ["pair:a:m1", *want]


def test_sub_questions_set_no_scope(folder, SPEC):
    plain = relevant_facts(SPEC, truth(folder), q("Does Targeted therapy raise the Response rate?"))
    more = relevant_facts(SPEC, truth(folder), q("Does Targeted therapy raise the Response rate?",
                                                 sub_questions=["And the Relapse rate of Combined therapy?"]))
    assert plain == more


def test_naming_nothing_gives_everything(folder, SPEC):
    ids = [f.id for f in relevant_facts(SPEC, truth(folder), q("What do these studies show?"))]
    assert sum(i.startswith("pair:") for i in ids) == 6 and sum(i.startswith("rank:") for i in ids) == 3
    assert sum(i.startswith("study:") for i in ids) == 40


def test_about_overrides_the_text(folder, SPEC):
    ids = [f.id for f in relevant_facts(SPEC, truth(folder), q("How is it tolerated?", about=["Relapse rate"]))]
    assert {i for i in ids if i.startswith("pair:")} == {"pair:a:m2", "pair:b:m2"}


def test_texts_use_names_never_ids(folder, SPEC):
    for line in relevant_facts(SPEC, truth(folder), q("What do these studies show?")):
        words = set(re.findall(r"\w+", line.text))
        assert not words & {"ctrl", "m1", "m2", "m3", "young", "old", "urban", "rural", "early", "late"}


def test_depends_names_the_condition_and_both_sides(tmp_path, SPEC):
    s = seed_with(SPEC, lambda t: any(p["answer"]["verdict"] == "depends" for p in t["facts"]["pairs"]))
    t = truth(built(tmp_path, SPEC, s))
    p = next(p for p in t["facts"]["pairs"] if p["answer"]["verdict"] == "depends")
    line = next(f for f in relevant_facts(SPEC, t, q("all?")) if f.id == f"pair:{p['treatment']}:{p['measure']}")
    cond = next(c for c in SPEC.conditions if c.id == p["answer"]["condition"])
    assert f"depends on {cond.name}" in line.text and all(lv.name in line.text for lv in cond.levels)


def test_an_uncovered_pair_is_cant_tell(tmp_path, SPEC):
    s = seed_with(SPEC, lambda t: t["world"]["uncovered"])
    t = truth(built(tmp_path, SPEC, s))
    tr, m = t["world"]["uncovered"][0]
    text = f"Does {label(SPEC, tr)} change the {SPEC.measure(m).name}?"
    assert cant_tell(SPEC, t, q(text)) == [f"pair:{tr}:{m}"]
    assert cant_tell(SPEC, t, q("What do these studies show?")) is None


def test_truth_hash_is_shared_by_template_and_real(tmp_path, SPEC, REAL, pool):
    build_folder(tmp_path / "t", SPEC, approved(SPEC, 1), 40, "table")
    build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 1), 40, "table", REAL, pool)
    assert truth_sha256(truth(tmp_path / "t")) == truth_sha256(truth(tmp_path / "r"))


def test_load_folder_and_spec_check(folder, SPEC, tmp_path):
    f = load_folder(folder)
    assert f.seed == 1 and f.spec.sha256 == SPEC.sha256 and f.corpus_id
    check_spec(f, SPEC)
    other = SPEC.model_copy(update={"sha256": "0" * 64})
    with pytest.raises(ValueError, match="another spec"):
        check_spec(f, other)
    with pytest.raises(ValueError):
        load_folder(tmp_path / "none")


def test_scope_reads_only_the_main_question(SPEC):
    n = scope(SPEC, Question(id="x", question="Does Targeted therapy help?", sub_questions=["Relapse rate?"]))
    assert n.arms == ["a"] and n.measures == []


def test_questions_command_prints_the_scope(tmp_path, spec_dir, capsys):
    assert main(["questions", "--domain", "demo", "--spec-root", str(spec_dir), "--questions-root", str(FIX)]) == 0
    out = capsys.readouterr().out
    assert "3 questions" in out and "d01: arms Standard care, Targeted therapy; measures Response rate" in out


def test_questions_command_bad_file_exits_2(tmp_path, spec_dir, capsys):
    assert main(["questions", "--domain", "demo", "--spec-root", str(spec_dir),
                 "--questions-root", str(tmp_path / "none")]) == 2
    assert "no questions file" in capsys.readouterr().err
