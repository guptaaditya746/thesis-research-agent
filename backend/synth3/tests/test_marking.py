"""synth3.marking: `synth3 judge` writes three separate scores (A, B, C) beside every saved answer. Every model is a
fake; none is a live call."""
import json
import re
from pathlib import Path

import modelcall.gateway

from modelcall import JsonlCache
from synth3.answers import AnswerRecord, PulledFact, item_id, save_answer
from synth3.cli import main
from synth3.judge import ClaimChecks, Mark, PaperMarks, Tick, Ticks
from synth3.marking import judge_domain, marks_path, why_not
from synth3.questions import question_sha256, load_questions
from synth3.sheetfacts import load_folder
from synth3.sheets import make_sheet, save_sheet
from synth3.tests.fakes import answering, boom, failing

FIX = Path(__file__).parent / "fixtures" / "questions"
TEXT = "Targeted therapy does better."


def judge_model():
    """C (`Points:`) gets every point met, quoting the answer's first word; A (`Planted facts:`) gets every listed
    planted id missing; any other call (B) gets no claims."""
    def fn(prompt: str):
        if "Points:" in prompt:
            answer = prompt.split("Answer:\n", 1)[1]
            ids = re.findall(r"^(p\d+): ", prompt.split("Points:\n", 1)[1], re.M)
            return Ticks(ticks=[Tick(point=i, met=True, quote=answer.split()[0], reason="") for i in ids])
        if "Planted facts:" in prompt:
            block = prompt.split("Planted facts:\n", 1)[1].split("\n\nPulled facts:", 1)[0]
            ids = re.findall(r"^(S\d{3}\.\S+): ", block, re.M)
            return PaperMarks(marks=[Mark(fact=i, verdict="missing", pulled=None, reason="") for i in ids])
        return ClaimChecks(claims=[])
    return answering(fn)


def pulled_on(paper: str) -> PulledFact:
    return PulledFact(paper=paper, kind="measurement", fields={"value": 1}, quote="some quote", start=None, end=None)


def engine_rec(f, q, text=TEXT, facts=(), **kw) -> AnswerRecord:
    fields = {"domain": "demo", "seed": f.seed, "corpus_id": f.corpus_id, "question_id": q.id,
              "question_sha256": question_sha256(q), "system": "engine", "text": text, "text_cut": False,
              "cited": [], "facts": None if facts is None else list(facts), "passages": [], "source": "fake"}
    return AnswerRecord(**(fields | kw))


def sheet_for(f, q, tmp_path):
    save_sheet(tmp_path / "sh", make_sheet(f, q, [(TEXT, ["pair:a:m1"])], {"model": "x"}))


def run(folder, tmp_path, SPEC, qs, model, *, cache="c", systems=None):
    return judge_domain("demo", folder.parent, [1], systems, SPEC, qs, model, JsonlCache(tmp_path / cache),
                        tmp_path / "sh", tmp_path / "res")


def marks_of(tmp_path, qid="d01", system="engine") -> dict:
    return json.loads(marks_path(tmp_path / "res", "demo", 1, system, qid).read_text(encoding="utf-8"))


def test_one_answer_gets_three_separate_scores(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); qq = qs.get("d01")
    sheet_for(f, qq, tmp_path)
    save_answer(tmp_path / "res", engine_rec(f, qq, facts=[pulled_on("S001")]))
    out = run(folder, tmp_path, SPEC, qs, judge_model())
    m = marks_of(tmp_path)
    assert out["judged"] == 1 and m["C"]["score"] == 1.0 and m["A"]["score"] == 0 and m["B"]["score"] is None
    assert set(m["judge"]["prompts"]) == {"a", "b", "c"}
    assert m["item"] == "demo/s1/engine/d01" and m["system"] == "engine" and m["corpus_id"] == f.corpus_id
    assert m["sheet"]["status"] == "drafted" and m["sheet"]["cant_tell"] is False and m["sheet"]["sha256"]
    assert m["calls"] == m["A"]["calls"] + m["B"]["calls"] + m["C"]["calls"] >= 2
    assert out["pending"] == [] and out["skipped"] == {} and out["kept"] == 0


def test_a_stale_sheet_is_skipped_with_its_reason(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); qq = qs.get("d01")
    sheet_for(f, qq, tmp_path)
    changed = qq.model_copy(update={"question": qq.question + " Please be brief."})
    qs2 = qs.model_copy(update={"questions": [changed if q.id == "d01" else q for q in qs.questions]})
    save_answer(tmp_path / "res", engine_rec(f, changed))
    model = boom()
    out = run(folder, tmp_path, SPEC, qs2, model)
    assert out["skipped"] == {"demo/s1/engine/d01": "the question changed after drafting"}
    assert out["judged"] == 0 and model.calls == 0
    assert not marks_path(tmp_path / "res", "demo", 1, "engine", "d01").exists()


def test_a_second_run_makes_no_calls(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); qq = qs.get("d01")
    sheet_for(f, qq, tmp_path)
    save_answer(tmp_path / "res", engine_rec(f, qq, facts=[pulled_on("S001")]))
    run(folder, tmp_path, SPEC, qs, judge_model())
    never = boom()
    again = run(folder, tmp_path, SPEC, qs, never)
    assert again["kept"] == 1 and again["judged"] == 0 and never.calls == 0
    path = marks_path(tmp_path / "res", "demo", 1, "engine", "d01")
    m = marks_of(tmp_path); m["judge"]["prompts"]["a"] = "0" * 64
    path.write_text(json.dumps(m), encoding="utf-8")
    third = run(folder, tmp_path, SPEC, qs, judge_model(), cache="c2")
    assert third["judged"] == 1 and third["kept"] == 0
    assert marks_of(tmp_path)["judge"]["prompts"]["a"] != "0" * 64


def test_a_changed_answer_or_sheet_is_judged_again(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); qq = qs.get("d01")
    sheet_for(f, qq, tmp_path)
    save_answer(tmp_path / "res", engine_rec(f, qq))
    run(folder, tmp_path, SPEC, qs, judge_model())
    save_answer(tmp_path / "res", engine_rec(f, qq, text="Targeted therapy does much better."))
    assert run(folder, tmp_path, SPEC, qs, judge_model())["judged"] == 1
    save_sheet(tmp_path / "sh", make_sheet(f, qq, [("Another point.", ["pair:a:m1"])], {"model": "x"}))
    assert run(folder, tmp_path, SPEC, qs, judge_model())["judged"] == 1


def test_an_answer_to_an_older_question_is_skipped(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); qq = qs.get("d01")
    sheet_for(f, qq, tmp_path)
    save_answer(tmp_path / "res", engine_rec(f, qq, question_sha256="9" * 64))
    out = run(folder, tmp_path, SPEC, qs, boom())
    reason = out["skipped"]["demo/s1/engine/d01"]
    assert reason == "the answer is to an older version of the question" and out["judged"] == 0


def test_why_not_checks_in_order(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); qq = qs.get("d01")
    sheet = make_sheet(f, qq, [(TEXT, ["pair:a:m1"])], {"model": "x"})
    assert why_not(f, qq, None, engine_rec(f, qq)) == "no sheet"
    assert why_not(f, qq, sheet, engine_rec(f, qq)) is None
    assert why_not(f, qq, sheet, engine_rec(f, qq, corpus_id="other")) == "the answer is from another folder"
    stale_sheet = sheet.model_copy(update={"question_sha256": "1" * 64})
    assert why_not(f, qq, stale_sheet, engine_rec(f, qq, question_sha256="2" * 64)) == (
        "the question changed after drafting")   # stale comes before the record's own checks


def test_a_failing_judge_leaves_pending_marks_and_goes_on(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX)
    for qid in ("d01", "d02"):
        sheet_for_q = qs.get(qid)
        save_sheet(tmp_path / "sh", make_sheet(f, sheet_for_q, [(TEXT, ["pair:a:m1"])], {"model": "x"}))
        save_answer(tmp_path / "res", engine_rec(f, sheet_for_q, facts=[pulled_on("S001")]))
    out = run(folder, tmp_path, SPEC, qs, failing())
    assert out["judged"] == 2 and out["kept"] == 0
    assert out["pending"] == ["demo/s1/engine/d01", "demo/s1/engine/d02"]
    for qid in ("d01", "d02"):
        m = marks_of(tmp_path, qid)
        assert m["B"]["status"] == "pending" and m["C"]["status"] == "pending" and m["C"]["score"] is None
        assert set(m["judge"]["prompts"]) == {"a", "b", "c"}
    # a pending file is judged again on the next run, not kept
    again = run(folder, tmp_path, SPEC, qs, judge_model(), cache="c2")
    assert again["judged"] == 2 and again["pending"] == [] and again["kept"] == 0


def test_the_baseline_has_no_a_but_records_its_prompt(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); qq = qs.get("d01")
    sheet_for(f, qq, tmp_path)
    rag = engine_rec(f, qq, system="rag-baseline", facts=None, cited=["S001"],
                     passages=[pulled_on("S001").model_copy(update={"kind": "passage"})])
    save_answer(tmp_path / "res", rag)
    out = run(folder, tmp_path, SPEC, qs, judge_model())
    m = marks_of(tmp_path, system="rag-baseline")
    assert out["judged"] == 1 and m["A"] is None and len(m["judge"]["prompts"]["a"]) == 64
    assert m["C"]["score"] == 1.0 and m["item"] == item_id(rag)


def test_an_empty_answer_still_records_all_three_prompts(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); qq = qs.get("d01")
    sheet_for(f, qq, tmp_path)
    save_answer(tmp_path / "res", engine_rec(f, qq, text="", facts=None, system="rag-baseline"))
    model = boom()
    out = run(folder, tmp_path, SPEC, qs, model)
    m = marks_of(tmp_path, system="rag-baseline")
    assert model.calls == 0 and out["judged"] == 1 and m["C"]["score"] == 0.0 and m["A"] is None
    assert all(len(v) == 64 for v in m["judge"]["prompts"].values())


def test_systems_filter_and_no_system_name_reaches_the_judge(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); qq = qs.get("d01")
    sheet_for(f, qq, tmp_path)
    save_answer(tmp_path / "res", engine_rec(f, qq, facts=[pulled_on("S001")]))
    save_answer(tmp_path / "res", engine_rec(f, qq, system="other-system"))
    model = judge_model()
    out = run(folder, tmp_path, SPEC, qs, model, systems=["engine"])
    assert out["judged"] == 1
    assert not marks_path(tmp_path / "res", "demo", 1, "other-system", "d01").exists()
    assert model.prompts and not any("engine" in p.lower() for p in model.prompts)


def test_judge_by_command(folder, tmp_path, spec_dir, monkeypatch, capsys):
    from synth3.spec import load_spec
    SPEC = load_spec("demo", spec_dir)
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); qq = qs.get("d01")
    sheet_for(f, qq, tmp_path)
    save_answer(tmp_path / "res", engine_rec(f, qq, facts=[pulled_on("S001")]))
    seen = []
    monkeypatch.setattr(modelcall.gateway, "openai_model", lambda alias, **kw: seen.append(alias) or judge_model())
    code = main(["judge", "--domain", "demo", "--folders", str(folder.parent), "--seeds", "1",
                 "--spec-root", str(spec_dir), "--questions-root", str(FIX), "--sheets", str(tmp_path / "sh"),
                 "--results", str(tmp_path / "res")])
    assert code == 0 and seen == ["sub-model-1"]
    assert "judged 1, kept 0, skipped 0, pending 0" in capsys.readouterr().out
    assert (tmp_path / "res" / "demo" / "judge-calls.jsonl").is_file()
    assert marks_path(tmp_path / "res", "demo", 1, "engine", "d01").is_file()


def test_a_pending_item_from_bad_replies_is_asked_again_past_the_cache(folder, tmp_path, SPEC):
    f = load_folder(folder); qs = load_questions("demo", SPEC, FIX); qq = qs.get("d01")
    sheet_for(f, qq, tmp_path)
    save_answer(tmp_path / "res", engine_rec(f, qq))
    bad = answering(lambda p: Ticks(ticks=[Tick(point="p1", met=True, quote="never said", reason="")])
                    if "Points:" in p else ClaimChecks(claims=[]))
    first = run(folder, tmp_path, SPEC, qs, bad)   # the bad replies are cached under the same keys
    assert first["pending"] == ["demo/s1/engine/d01"]
    good = judge_model()
    second = run(folder, tmp_path, SPEC, qs, good)
    assert good.prompts and second["judged"] == 1 and second["pending"] == []
    assert marks_of(tmp_path)["C"]["score"] == 1.0
    never = boom()   # a kept item never uses fresh and never calls
    assert run(folder, tmp_path, SPEC, qs, never)["kept"] == 1 and never.calls == 0
