"""synth3.judge, score C: the judge ticks each answer-sheet point; code checks every tick and its quote, gives one
repair, and leaves the answer pending when the reply stays bad or the call fails. Every model is a fake."""
import pytest

from modelcall import JsonlCache
from synth3.judge import Tick, Ticks, c_input, check_ticks, score_c, squash
from synth3.sheetfacts import FactLine
from synth3.sheets import Point, Sheet
from synth3.tests.conftest import q
from synth3.tests.fakes import boom, failing, rec, scripted


def sheet3() -> Sheet:
    """A drafted sheet of three points on the demo spec's names, with the fact lines they cite."""
    facts = [FactLine(id="pair:a:m1", text="Targeted therapy against Standard care on Response rate: better."),
             FactLine(id="pair:b:m1", text="Combined therapy against Standard care on Response rate: no real "
                                           "difference."),
             FactLine(id="pair:a:m2", text="Targeted therapy against Standard care on Relapse rate: worse.")]
    points = [Point(id="p1", text="Targeted therapy gives a higher Response rate than Standard care.",
                    facts=["pair:a:m1"]),
              Point(id="p2", text="Combined therapy and Standard care show no real difference in Response rate.",
                    facts=["pair:b:m1"]),
              Point(id="p3", text="Targeted therapy gives a higher Relapse rate than Standard care.",
                    facts=["pair:a:m2"])]
    return Sheet(domain="demo", seed=1, question_id="x", question_sha256="0" * 64, truth_sha256="1" * 64,
                 cant_tell=False, facts=facts, points=points, status="drafted", drafted_by={"model": "fake"})


def ticks(*marks: tuple[str, bool, str | None]) -> Ticks:
    return Ticks(ticks=[Tick(point=p, met=m, quote=qt, reason="") for p, m, qt in marks])


def test_two_of_three_points_give_two_thirds(tmp_path):
    t = "Targeted therapy does better. Combined therapy is no different."
    out = score_c(q("Q?"), sheet3(), rec(t), scripted(Ticks(ticks=[
        Tick(point="p1", met=True, quote="Targeted therapy does better", reason=""),
        Tick(point="p2", met=True, quote="combined therapy is no different", reason=""),
        Tick(point="p3", met=False, quote=None, reason="")])), JsonlCache(tmp_path / "c"))
    assert out["score"] == pytest.approx(2 / 3) and out["missed"] == ["p3"] and out["status"] == "ok"
    assert [t["point"] for t in out["ticks"]] == ["p1", "p2", "p3"] and out["problems"] == []
    assert out["calls"] == 1 and out["served_models"] == ["fake"] and len(out["prompt_sha256"]) == 64


def test_a_quote_not_in_the_answer_gets_one_repair(tmp_path):
    bad = Ticks(ticks=[Tick(point=p, met=True, quote="never said", reason="") for p in ("p1", "p2", "p3")])
    good = Ticks(ticks=[Tick(point=p, met=False, quote=None, reason="") for p in ("p1", "p2", "p3")])
    model = scripted(bad, good)
    out = score_c(q("Q?"), sheet3(), rec("Something else."), model, JsonlCache(tmp_path / "c"))
    assert out["score"] == 0 and out["calls"] == 2 and "quote not in the answer" in model.prompts[1]


def test_a_reply_that_stays_bad_is_pending(tmp_path):
    bad = Ticks(ticks=[Tick(point="p1", met=False, quote=None, reason="")])
    out = score_c(q("Q?"), sheet3(), rec("x"), scripted(bad, bad), JsonlCache(tmp_path / "c"))
    assert out["status"] == "pending" and out["score"] is None and "p2 missing" in out["problems"]
    assert out["calls"] == 2 and out["ticks"] == [] and out["missed"] == []


def test_a_failing_call_is_pending(tmp_path):
    out = score_c(q("Q?"), sheet3(), rec("x"), failing(), JsonlCache(tmp_path / "c"))
    assert out["status"] == "pending" and out["score"] is None and "model call failed" in out["problems"][0]


def test_an_empty_answer_scores_zero_without_a_call(tmp_path):
    model = boom()
    out = score_c(q("Q?"), sheet3(), rec(" "), model, JsonlCache(tmp_path / "c"))
    assert out["score"] == 0 and out["calls"] == 0 and model.calls == 0
    assert out["missed"] == ["p1", "p2", "p3"] and out["status"] == "ok" and out["served_models"] == []
    assert [t["met"] for t in out["ticks"]] == [False, False, False]


def test_the_judge_sees_no_sub_question_no_fact_and_no_system():
    text = c_input(q("Q?", sub_questions=["Secret sub-question?"]), sheet3(), "An answer.")
    assert "Secret sub-question?" not in text and "pair:" not in text and "rag-baseline" not in text


def test_c_input_lists_the_question_the_points_and_the_answer():
    s = sheet3()
    assert c_input(q("Does it help?"), s, "An answer.") == (
        "Question: Does it help?\n\nPoints:\n" + "\n".join(f"{p.id}: {p.text}" for p in s.points)
        + "\n\nAnswer:\nAn answer.")


def test_squash_folds_spaces_and_case():
    assert squash("  Method\n K   DOES\tbetter ") == "method k does better"


def test_check_ticks_names_each_problem():
    t = "Targeted therapy does better."
    assert check_ticks(ticks(("p1", True, "targeted   THERAPY does"), ("p2", False, None), ("p3", False, None)),
                       sheet3(), t) == []
    assert check_ticks(ticks(("p1", False, None), ("p1", False, None), ("p9", False, None)), sheet3(), t) == [
        "p1 twice", "unknown point p9", "p2 missing", "p3 missing"]
    assert check_ticks(ticks(("p1", True, "says nothing"), ("p2", True, None), ("p3", True, " ")), sheet3(), t) == [
        "p1: quote not in the answer", "p2: a met point needs a quote", "p3: a met point needs a quote"]


def test_the_sheet_points_reach_the_judge_and_the_repair_holds_the_rejected_reply(tmp_path):
    bad = ticks(("p1", True, "never said"), ("p2", False, None), ("p3", False, None))
    good = ticks(("p1", False, None), ("p2", False, None), ("p3", False, None))
    model = scripted(bad, good)
    score_c(q("Q?"), sheet3(), rec("Something else."), model, JsonlCache(tmp_path / "c"))
    assert "p3: Targeted therapy gives a higher Relapse rate than Standard care." in model.prompts[0]
    assert '"quote":"never said"' in model.prompts[1] and "Answer:\nSomething else." in model.prompts[1]
