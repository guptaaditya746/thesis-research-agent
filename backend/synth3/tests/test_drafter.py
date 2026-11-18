"""synth3.drafter: model sheets checked by code with one repair, can't-tell sheets with no call, Aditya's checked
sheets never overwritten, and the `draft-sheets` command. Every model is a fake; none is a live call."""
from dataclasses import replace
from pathlib import Path

import pytest

from modelcall import JsonlCache
from synth3.cli import main
from synth3.drafter import PROMPT, DraftPoint, DraftSheet, draft_folder_sheets, draft_sheet, drafter_input
from synth3.questions import load_questions
from synth3.sheetfacts import load_folder, relevant_facts
from synth3.sheets import check_sheet, load_sheet, make_sheet, person_sheet, save_sheet, sheet_path
from synth3.tests.conftest import built, label, q, seed_with
from synth3.tests.fakes import answering, boom, failing, scripted

FIX = Path(__file__).parent / "fixtures" / "questions"


def set_of_cant_tell(out: dict) -> set[str]:
    """The questions that got a code sheet (none or more, by seed)."""
    return set(out["cant_tell"])


def first_fact(prompt: str) -> str:
    """The first fact id listed in a drafter input."""
    return prompt.split("Facts:\n", 1)[1].split(": ", 1)[0]


def a_point(prompt: str) -> DraftSheet:
    return DraftSheet(points=[DraftPoint(text="A point.", facts=[first_fact(prompt)])])


def test_a_good_draft_becomes_a_sheet(folder, tmp_path):
    f = load_folder(folder); qq = q("Does Targeted therapy raise the Response rate?")
    s = draft_sheet(f, qq, scripted(DraftSheet(points=[DraftPoint(text="Targeted therapy does better.",
                                                                  facts=["pair:a:m1"])])), JsonlCache(tmp_path / "c"))
    assert [p.id for p in s.points] == ["p1"] and s.status == "drafted" and s.drafted_by["attempts"] == 1
    assert s.drafted_by["model"] == "fake" and s.drafted_by["served_models"] == ["fake"]
    assert len(s.drafted_by["prompt_sha256"]) == 64


def test_cant_tell_needs_no_model_call(tmp_path, SPEC):
    f = load_folder(built(tmp_path, SPEC, seed_with(SPEC, lambda t: t["world"]["uncovered"])))
    tr, m = f.truth["world"]["uncovered"][0]
    model = boom()
    s = draft_sheet(f, q(f"Does {label(SPEC, tr)} change the {SPEC.measure(m).name}?"), model, JsonlCache(tmp_path / "c"))
    assert s.cant_tell and model.calls == 0


def test_a_bad_draft_gets_one_repair_with_its_problems(folder, tmp_path):
    bad = DraftSheet(points=[DraftPoint(text="x", facts=["pair:zz:m9"])])
    good = DraftSheet(points=[DraftPoint(text="Targeted therapy does better.", facts=["pair:a:m1"])])
    model = scripted(bad, good)
    s = draft_sheet(load_folder(folder), q("Does Targeted therapy raise the Response rate?"), model, JsonlCache(tmp_path / "c"))
    assert s.drafted_by["attempts"] == 2 and "unknown fact pair:zz:m9" in model.prompts[1]


def test_two_bad_drafts_fail_with_the_problems(folder, tmp_path):
    bad = DraftSheet(points=[])
    with pytest.raises(ValueError, match="x s1: .*point"):
        draft_sheet(load_folder(folder), q("Does Targeted therapy raise the Response rate?"), scripted(bad, bad),
                    JsonlCache(tmp_path / "c"))


def test_a_number_in_a_point_is_a_problem_but_a_spec_name_is_not(folder, tmp_path):
    """The drafter passes the spec's names to the check (a digit inside a name is allowed, any other is not)."""
    f = load_folder(folder); qq = q("Does Targeted therapy raise the Response rate?")
    f2 = replace(f, spec=f.spec.model_copy(update={"arms": [a.model_copy(update={"label": "Drug B12"})
                                                            if a.id == "a" else a for a in f.spec.arms]}))
    bad = DraftSheet(points=[DraftPoint(text="Drug B12 raises it by 5 points.", facts=["pair:a:m1"])])
    good = DraftSheet(points=[DraftPoint(text="Drug B12 does better in S004.", facts=["pair:a:m1"])])
    model = scripted(bad, good)
    s = draft_sheet(f2, qq.model_copy(update={"question": "Does Drug B12 raise the Response rate?"}), model,
                    JsonlCache(tmp_path / "c"))
    assert "point 1: holds a number" in model.prompts[1] and s.points[0].text == "Drug B12 does better in S004."


def test_the_prompt_says_exactly_which_rules_code_checks():
    """prompt-writing.md: say what is checked. check_points checks the count, the length, repeats, the fact ids and
    numbers; the other rules are for the person who checks the sheet."""
    rules = PROMPT.read_text(encoding="utf-8").split("\nRules (", 1)[1].splitlines()
    assert rules[0].startswith("code checks the first three;")
    checked = " ".join(rules[1:4])
    for word in ("1 to 6", "300 characters", "same text", "cites at least one fact", "holds a number"):
        assert word in checked
    assert "one thing" not in checked and "Use only" not in checked


def test_the_input_holds_the_fact_lines_but_no_sub_question(folder):
    f = load_folder(folder); qq = q("Which is best for Relapse rate?", sub_questions=["Do older patients differ?"])
    text = drafter_input(qq, relevant_facts(f.spec, f.truth, qq))
    assert "Do older patients differ?" not in text and "pair:a:m2:" in text and "rank:m2:" in text
    assert text.startswith("Question: Which is best for Relapse rate?\n\nFacts:\npair:a:m2: ")


def test_a_failing_call_is_a_failure_and_the_folder_goes_on(folder, tmp_path, SPEC):
    out = draft_folder_sheets(load_folder(folder), load_questions("demo", SPEC, FIX), failing(),
                              JsonlCache(tmp_path / "c"), tmp_path / "sh", now="t")
    assert set(out["failed"]) | set_of_cant_tell(out) == {"d01", "d02", "d03"}
    assert all("model call failed" in why for why in out["failed"].values())


def test_folder_drafting_keeps_checked_sheets(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); root = tmp_path / "sh"
    for qq in qs.questions:
        save_sheet(root, check_sheet(make_sheet(f, qq, [("Kept.", [])], {"model": "x"}), [("Kept.", [])], "aditya", "t"))
    edited = qs.get("d01").model_copy(update={"question": "Changed?"})
    qs2 = qs.model_copy(update={"questions": [edited, *qs.questions[1:]]})
    model = boom()
    out = draft_folder_sheets(f, qs2, model, JsonlCache(tmp_path / "c"), root, redraft={"d02"}, now="t")
    assert out["stale_checked"] == ["d01"] and out["kept_checked"] == ["d02"] and model.calls == 0
    assert load_sheet(root, "demo", 1, "d01").points[0].text == "Kept."


def test_a_stale_checked_sheet_in_redraft_is_archived_and_drafted_again(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); root = tmp_path / "sh"
    d01 = qs.get("d01")
    save_sheet(root, check_sheet(make_sheet(f, d01, [("Kept.", [])], {"model": "x"}), [("Kept.", [])], "aditya", "t"))
    edited = d01.model_copy(update={"question": "Does Targeted therapy change the Response rate?"})
    qs2 = qs.model_copy(update={"questions": [edited]})
    out = draft_folder_sheets(f, qs2, answering(a_point), JsonlCache(tmp_path / "c"), root, redraft={"d01"}, now="t")
    assert out["drafted"] == ["d01"] and out["stale_checked"] == []
    assert load_sheet(root, "demo", 1, "d01").status == "drafted"
    assert sheet_path(root, "demo", 1, "d01").with_name("d01.stale-1.json").is_file()


def test_a_sheet_aditya_wrote_is_kept_even_stale_unless_redrafted(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); root = tmp_path / "sh"
    d01 = qs.get("d01")
    save_sheet(root, person_sheet(f, d01, [("Mine.", [])], "aditya", "t", checked=False))
    edited = d01.model_copy(update={"question": "Does Targeted therapy change the Response rate?"})
    qs2 = qs.model_copy(update={"questions": [edited]})
    model = boom()
    out = draft_folder_sheets(f, qs2, model, JsonlCache(tmp_path / "c"), root, now="t")
    assert out["kept"] == ["d01"] and out["drafted"] == [] and model.calls == 0
    assert load_sheet(root, "demo", 1, "d01").points[0].text == "Mine."
    failed = draft_folder_sheets(f, qs2, failing(), JsonlCache(tmp_path / "c"), root, redraft={"d01"}, now="t")
    assert "d01" in failed["failed"] and load_sheet(root, "demo", 1, "d01").points[0].text == "Mine."
    out = draft_folder_sheets(f, qs2, answering(a_point), JsonlCache(tmp_path / "c"), root, redraft={"d01"}, now="t2")
    assert out["drafted"] == ["d01"] and load_sheet(root, "demo", 1, "d01").points[0].text == "A point."
    archived = sheet_path(root, "demo", 1, "d01").with_name("d01.stale-1.json")
    assert archived.is_file() and "Mine." in archived.read_text(encoding="utf-8")


def test_a_fresh_drafted_sheet_is_kept_and_a_stale_one_drafted_again(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); root = tmp_path / "sh"
    first = draft_folder_sheets(f, qs, answering(a_point), JsonlCache(tmp_path / "c"), root, now="t")
    assert set(first["drafted"]) == {"d01", "d02", "d03"}
    edited = qs.get("d01").model_copy(update={"question": "Does Targeted therapy change the Response rate?"})
    qs2 = qs.model_copy(update={"questions": [edited, *qs.questions[1:]]})
    model = answering(a_point)
    out = draft_folder_sheets(f, qs2, model, JsonlCache(tmp_path / "c"), root, now="t")
    assert out["drafted"] == ["d01"] and out["kept"] == ["d02", "d03"] and len(model.prompts) == 1


def test_redraft_calls_again_after_two_cached_failures(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); c = JsonlCache(tmp_path / "c")
    bad = DraftSheet(points=[])
    first = scripted(*[bad] * 6)
    assert "d01" in draft_folder_sheets(f, qs, first, c, tmp_path / "sh", now="t0")["failed"]
    again = answering(lambda p: DraftSheet(points=[DraftPoint(text="A point.", facts=[first_fact(p)])]))
    out = draft_folder_sheets(f, qs, again, c, tmp_path / "sh", redraft={"d01"}, now="t1")
    assert "d01" not in out["failed"] and load_sheet(tmp_path / "sh", "demo", 1, "d01") is not None


def _command(tmp_path, spec_dir, *more):
    return main(["draft-sheets", "--domain", "demo", "--folders", str(tmp_path / "f"), "--seeds", "1",
                 "--spec-root", str(spec_dir), "--questions-root", str(FIX), "--sheets", str(tmp_path / "sh"),
                 "--results", str(tmp_path / "r"), *more])


def test_draft_sheets_by_command(folder, tmp_path, spec_dir, monkeypatch, capsys):
    seen = []
    monkeypatch.setattr("modelcall.gateway.openai_model", lambda alias, **kw: seen.append(alias) or answering(a_point))
    assert _command(tmp_path, spec_dir) == 0
    assert len(list((tmp_path / "sh" / "demo" / "s1").glob("*.json"))) == 3
    assert "s1: drafted 3" in capsys.readouterr().out and seen == ["orch-model"]
    assert (tmp_path / "r" / "demo" / "drafter-calls.jsonl").is_file()


def test_draft_sheets_by_command_exits_1_on_a_failure(folder, tmp_path, spec_dir, monkeypatch, capsys):
    monkeypatch.setattr("modelcall.gateway.openai_model", lambda alias, **kw: failing())
    assert _command(tmp_path, spec_dir) == 1
    out = capsys.readouterr().out
    assert "failed 3" in out and "model call failed" in out


def test_draft_sheets_by_command_names_a_stale_checked_sheet(folder, tmp_path, spec_dir, SPEC, monkeypatch, capsys):
    f = load_folder(folder); d01 = load_questions("demo", SPEC, FIX).get("d01")
    old = d01.model_copy(update={"question": "Does Targeted therapy change the Response rate?"})
    save_sheet(tmp_path / "sh", check_sheet(make_sheet(f, old, [("Kept.", [])], {"model": "x"}), [("Kept.", [])],
                                            "aditya", "t"))
    monkeypatch.setattr("modelcall.gateway.openai_model", lambda alias, **kw: answering(a_point))
    assert _command(tmp_path, spec_dir) == 0
    assert ("  stale checked sheet: d01 (fix it on the review page, or pass --redraft d01)"
            in capsys.readouterr().out)


def test_draft_sheets_by_command_refuses_an_unknown_redraft_id(folder, tmp_path, spec_dir, monkeypatch, capsys):
    monkeypatch.setattr("modelcall.gateway.openai_model", lambda alias, **kw: boom())
    assert _command(tmp_path, spec_dir, "--redraft", "d01,zz") == 2
    assert "zz" in capsys.readouterr().err


def test_draft_sheets_by_command_stops_on_a_missing_folder(folder, tmp_path, spec_dir, monkeypatch, capsys):
    monkeypatch.setattr("modelcall.gateway.openai_model", lambda alias, **kw: boom())
    assert _command(tmp_path, spec_dir, "--seeds", "1,2") == 2
    assert "s2" in capsys.readouterr().err
    assert not (tmp_path / "sh").exists()
