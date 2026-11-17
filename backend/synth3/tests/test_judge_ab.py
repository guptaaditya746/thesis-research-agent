"""synth3.judge, scores A and B: the planted facts a question needs (by code), `anchored` (code only), the judge's
found/wrong/missing marks per paper (A) and its supported/invented/contradicted checks of the answer's claims (B).
Code checks every reply, gives one repair, and leaves the paper (A) or the answer (B) pending when the reply stays
bad or the call fails. Every model is a fake."""
import re

import pytest

from modelcall import JsonlCache
from repo_paths import BACKEND
from synth3.answers import PulledFact
from synth3.judge import (MAX_FACTS, MAX_PER_PAPER, ClaimCheck, ClaimChecks, Mark, PaperMarks, a_input, anchored,
                          b_input, check_claims, check_marks, planted_facts, score_a, score_b, used_facts)
from synth3.sheetfacts import load_folder
from synth3.spec import SPECS, Measure, load_spec
from synth3.tests.conftest import good, q
from synth3.tests.fakes import answering, boom, failing, rec, scripted

M = [Measure(**m) for m in good()["measures"]]   # the demo spec's: one higher is better, two lower
Q = "Does Targeted therapy raise the Response rate?"
PROMPTS = BACKEND / "synth3" / "prompts"
NEW_PROMPTS = ("sheet-v1.txt", "judge-a-v1.txt", "judge-b-v1.txt", "judge-c-v1.txt")


def spec_names(spec) -> list[str]:
    return spec.names()


def pulled(paper: str, i: int = 0) -> PulledFact:
    return PulledFact(paper=paper, kind="measurement", fields={"value": i}, quote=f"q{i}", start=None, end=None)


def all_missing(planted) -> PaperMarks:
    return PaperMarks(marks=[Mark(fact=p.id, verdict="missing", pulled=None, reason="") for p in planted])


def test_planted_facts_follow_the_scope(folder):
    f = load_folder(folder); got = planted_facts(f, q(Q))
    rows = [p for ps in got.values() for p in ps if not p.id.endswith(".setting")]
    assert rows and all("Response rate" in p.text and "Combined therapy" not in p.text for p in rows)
    assert all(re.search(r"\d+ of \d+ \(\d+\.\d%\)", p.text) for p in rows if ".claim." not in p.id)
    assert all(p.spans for ps in got.values() for p in ps)
    texts = {p.paper: (folder / "papers" / f"{p.paper}.md").read_text(encoding="utf-8") for ps in got.values() for p in ps}
    assert all(texts[p.paper][a:b] for ps in got.values() for p in ps for a, b in p.spans)


def test_planted_facts_texts_and_spans(folder):
    """Each kind of planted fact in its exact words, and its spans hold what the paper prints."""
    f = load_folder(folder); got = planted_facts(f, q(Q))
    assert list(got) == sorted(got) and all(p.paper == sid for sid, ps in got.items() for p in ps)
    flat = [p for ps in got.values() for p in ps]
    row = next(p for p in flat if re.fullmatch(r"S\d{3}\.c\d+\.a", p.id))
    sid, cell_i = row.paper, int(row.id.split(".")[1][1:])
    study = next(s for s in f.truth["studies"] if s["id"] == sid)
    cell = next(c for c in study["cells"] if c["index"] == cell_i)
    r = next(x for x in cell["results"] if x["arm"] == "a")
    assert row.text.startswith("Targeted therapy, Response rate, ")
    assert row.text.endswith(f": {r['k']} of {r['n']} ({100 * r['k'] / r['n']:.1f}%)")
    text = (folder / "papers" / f"{sid}.md").read_text(encoding="utf-8")
    assert sorted(text[a:b] for a, b in row.spans) == sorted([str(r["k"]), str(r["n"])])
    assert any(p.id == f"{sid}.c{cell_i}.ctrl" and p.text.startswith("Standard care, ") for p in got[sid])
    setting = next(p for p in got[sid] if p.id == f"{sid}.setting")
    assert setting.text == f"The study ran at {study['setting']}"
    claims = [p for p in flat if ".claim." in p.id]
    assert claims and all(re.fullmatch(r"The authors say Targeted therapy (does better than|does worse than|shows no "
                                       r"real difference from) Standard care on Response rate", p.text)
                          for p in claims)
    assert all(len(p.spans) == 2 for p in claims)   # the abstract and the conclusion


def test_planted_value_rows_keep_the_measure_decimals(folder):
    f = load_folder(folder); got = planted_facts(f, q("Does Targeted therapy lower the Systolic pressure?"))
    rows = [p for ps in got.values() for p in ps if re.fullmatch(r"S\d{3}\.c\d+\.\w+", p.id)]
    assert rows and all(re.search(r": mean \d+\.\d, SD \d+\.\d, n \d+$", p.text) for p in rows)


def test_anchored_counts_span_overlap(folder):
    f = load_folder(folder); got = planted_facts(f, q(Q))
    first = next(iter(got.values()))[0]; a, b = first.spans[0]
    hit = PulledFact(paper=first.paper, kind="measurement", fields={}, quote="", start=a, end=a + 1)
    total = sum(len(v) for v in got.values())
    assert anchored(got, [hit]) == pytest.approx(1 / total)


def test_anchored_needs_the_same_paper_and_a_shared_character(folder):
    f = load_folder(folder); got = planted_facts(f, q(Q))
    first = next(iter(got.values()))[0]; a, b = first.spans[0]
    other = next(s for s in (f"S{i:03d}" for i in range(1, 41)) if s not in got)
    misses = [PulledFact(paper=other, kind="m", fields={}, quote="", start=a, end=b),            # another paper
              PulledFact(paper=first.paper, kind="m", fields={}, quote="", start=a - 1, end=a),  # ends where it starts
              PulledFact(paper=first.paper, kind="m", fields={}, quote="", start=None, end=None)]
    assert anchored(got, misses) == 0 and anchored({}, misses) is None


def test_a_paper_without_pulled_facts_is_missing_without_a_call(folder, tmp_path):
    f = load_folder(folder); qq = q(Q)
    model = boom()
    out = score_a(f, qq, rec("x", facts=[]), model, JsonlCache(tmp_path / "c"))
    assert model.calls == 0 and out["found"] == 0 and out["missing"] == out["total"] > 0 and out["score"] == 0


def test_a_marks_count_found_and_wrong(folder, tmp_path):
    f = load_folder(folder); qq = q(Q)
    planted = planted_facts(f, qq); sid = next(iter(planted)); mine = planted[sid]
    marks = [Mark(fact=mine[0].id, verdict="found", pulled=1, reason=""),
             Mark(fact=mine[1].id, verdict="wrong", pulled=2, reason=""),
             *[Mark(fact=p.id, verdict="missing", pulled=None, reason="") for p in mine[2:]]]
    model = scripted(PaperMarks(marks=marks))
    out = score_a(f, qq, rec("x", facts=[pulled(sid, 1), pulled(sid, 2)]), model, JsonlCache(tmp_path / "c"))
    total = sum(len(v) for v in planted.values())
    assert out["found"] == 1 and out["wrong"] == 1 and out["missing"] == total - 2 and out["total"] == total
    assert out["score"] == pytest.approx(1 / total) and out["calls"] == 1 and out["served_models"] == ["fake"]
    assert [m["fact"] for m in out["papers"][sid]] == [p.id for p in mine]
    assert out["papers"][sid][0]["pulled"] == 1 and out["pending_papers"] == [] and out["pulled_cut"] == []
    assert set(out["papers"]) == set(planted) and len(out["prompt_sha256"]) == 64


def test_a_found_mark_without_a_pulled_number_is_repaired_then_pending(folder, tmp_path):
    f = load_folder(folder); qq = q(Q)
    planted = planted_facts(f, qq); sid = next(iter(planted))
    others = sum(len(v) for k, v in planted.items() if k != sid)
    bad = PaperMarks(marks=[Mark(fact=p.id, verdict="found", pulled=None, reason="") for p in planted[sid]])
    model = scripted(bad, bad)
    out = score_a(f, qq, rec("x", facts=[pulled(sid)]), model, JsonlCache(tmp_path / "c"))
    assert out["pending_papers"] == [sid] and sid not in out["papers"] and out["calls"] == 2
    assert out["total"] == others and out["missing"] == others and out["score"] == 0
    assert "found needs a pulled fact number" in model.prompts[1]
    out = score_a(f, qq, rec("x", facts=[pulled(sid)]), failing(), JsonlCache(tmp_path / "d"))
    assert out["pending_papers"] == [sid] and sid not in out["papers"]
    assert set(out["papers"]) == set(planted) - {sid} and out["total"] == others
    assert "model call failed" in out["problems"][sid][0]


def test_a_failed_call_on_one_paper_does_not_stop_the_next(folder, tmp_path):
    f = load_folder(folder); qq = q(Q)
    planted = planted_facts(f, qq); first, second = list(planted)[:2]

    def reply(prompt: str):
        if f"{first}.setting" in prompt:
            raise RuntimeError("the gateway is down")
        return all_missing(planted[second])

    out = score_a(f, qq, rec("x", facts=[pulled(first), pulled(second)]), answering(reply),
                  JsonlCache(tmp_path / "c"))
    assert out["pending_papers"] == [first] and second in out["papers"] and first not in out["papers"]
    assert out["score"] == 0 and out["total"] == sum(len(v) for k, v in planted.items() if k != first)


def test_too_many_pulled_facts_are_cut_and_said(folder, tmp_path):
    f = load_folder(folder); qq = q(Q)
    planted = planted_facts(f, qq); sid = next(iter(planted))
    many = [pulled(sid, i) for i in range(MAX_PER_PAPER + 1)]
    assert MAX_PER_PAPER == 60
    text = a_input(planted[sid], many, measures=M)
    assert "\n60. measurement" in text and "\n61. " not in text and '"q59"' in text and '"q60"' not in text
    model = scripted(all_missing(planted[sid]))
    out = score_a(f, qq, rec("x", facts=many), model, JsonlCache(tmp_path / "c"))
    assert out["pulled_cut"] == [sid] and out["pending_papers"] == [] and "\n61. " not in model.prompts[0]


def test_baseline_has_no_score_a(folder, tmp_path):
    assert score_a(load_folder(folder), q("Q?"), rec("x", facts=None), boom(), JsonlCache(tmp_path / "c")) is None


def test_a_input_lists_measures_planted_and_pulled_facts(folder):
    f = load_folder(folder); planted = next(iter(planted_facts(f, q(Q)).values()))
    p = PulledFact(paper=planted[0].paper, kind="measurement", fields={"value": 0.45, "arm": "x"}, quote="45 of 100")
    assert a_input(planted, [p], measures=M) == (
        "Measures:\nResponse rate: higher is better\nRelapse rate: lower is better\nSystolic pressure: lower is "
        "better\n\nPlanted facts:\n" + "\n".join(f"{x.id}: {x.text}" for x in planted)
        + '\n\nPulled facts:\n1. measurement {"arm":"x","value":0.45} quote: "45 of 100"')


def test_check_marks_names_each_problem(folder):
    f = load_folder(folder); planted = next(iter(planted_facts(f, q(Q)).values()))
    ids = [p.id for p in planted]
    ok = [Mark(fact=ids[0], verdict="found", pulled=1, reason=""), Mark(fact=ids[1], verdict="wrong", pulled=2,
                                                                         reason="")]
    ok += [Mark(fact=i, verdict="missing", pulled=None, reason="") for i in ids[2:]]
    assert check_marks(PaperMarks(marks=ok), planted, 2) == []
    bad = [Mark(fact=ids[0], verdict="found", pulled=None, reason=""),
           Mark(fact=ids[0], verdict="missing", pulled=None, reason=""),
           Mark(fact="S999.setting", verdict="missing", pulled=None, reason=""),
           Mark(fact=ids[1], verdict="wrong", pulled=3, reason="")]
    bad += [Mark(fact=ids[2], verdict="missing", pulled=1, reason="")]
    assert check_marks(PaperMarks(marks=bad), planted, 2) == [
        f"{ids[0]}: found needs a pulled fact number", f"{ids[0]} twice", "unknown fact S999.setting",
        f"{ids[1]}: pulled fact 3 is not in 1 to 2", f"{ids[2]}: missing cites no pulled fact",
        *[f"{i} not marked" for i in ids[3:]]]


@pytest.mark.parametrize("prompt", [PROMPTS / n for n in NEW_PROMPTS])
def test_prompt_examples_use_no_domain_name(prompt):
    names = {n for f in [*SPECS.glob("*.yaml"), *(SPECS / "drafts").glob("*.yaml")]
             for n in spec_names(load_spec(f.stem, f.parent))}
    text = prompt.read_text(encoding="utf-8")
    assert not [n for n in names if re.search(rf"(?i)(?<!\w){re.escape(n)}(?!\w)", text)]


def test_b_counts_supported_claims(tmp_path):
    used = [PulledFact(paper="S001", kind="measurement", fields={"value": 0.5}, quote="50%", start=1, end=4)]
    r = rec("Targeted therapy helps. Combined therapy hurts.", facts=used, cited=["S001"])
    out = score_b(q("Q?"), r, scripted(ClaimChecks(claims=[
        ClaimCheck(claim="Targeted therapy helps", verdict="supported", facts=[1], reason=""),
        ClaimCheck(claim="Combined therapy hurts", verdict="contradicted", facts=[1], reason="")])),
        JsonlCache(tmp_path / "c"), measures=M)
    assert out["score"] == 0.5 and out["contradicted"] == 1
    assert out["invented"] == 0 and out["status"] == "ok" and out["facts_cut"] is False and out["calls"] == 1
    assert [c["verdict"] for c in out["claims"]] == ["supported", "contradicted"] and len(out["prompt_sha256"]) == 64


def test_b_for_the_baseline_reads_its_passages(tmp_path):
    p = PulledFact(paper="S002", kind="passage", fields={}, quote="Relapse fell in older patients.", start=0, end=31)
    r = rec("Relapse fell.", facts=None, passages=[p])
    assert "Relapse fell in older patients." in b_input(q("Q?"), r, used_facts(r)[0], measures=M)


def test_used_facts_are_those_of_the_cited_papers_cut_at_the_limit():
    facts = [pulled("S001", 1), pulled("S002", 2), pulled("S001", 3)]
    assert used_facts(rec("x", facts=facts, cited=["S001"])) == ([facts[0], facts[2]], False)
    assert used_facts(rec("x", facts=facts, cited=[])) == (facts, False)
    many = [pulled("S001", i) for i in range(MAX_FACTS + 1)]
    assert MAX_FACTS == 150
    got, cut = used_facts(rec("x", facts=many, cited=["S001"]))
    assert got == many[:MAX_FACTS] and cut is True


def test_b_input_lists_the_question_the_measures_the_facts_and_the_answer():
    r = rec("Fewer relapses.", facts=[PulledFact(paper="S003", kind="measurement", fields={"k": 4}, quote="4")])
    assert b_input(q("Does it help?", sub_questions=["Secret sub-question?"]), r, r.facts, measures=M) == (
        "Question: Does it help?\n\nMeasures:\nResponse rate: higher is better\nRelapse rate: lower is better\n"
        'Systolic pressure: lower is better\n\nFacts:\n1. S003 measurement {"k":4} quote: "4"\n\nAnswer:\n'
        "Fewer relapses.")
    assert "Facts:\n(none)\n" in b_input(q("Q?"), r, [], measures=M)


def test_check_claims_names_each_problem():
    text = "Targeted therapy helps. Combined   therapy HURTS."
    ok = [ClaimCheck(claim="targeted therapy helps", verdict="supported", facts=[1], reason=""),
          ClaimCheck(claim="Combined therapy hurts", verdict="invented", facts=[], reason="")]
    assert check_claims(ClaimChecks(claims=ok), text, 2) == []
    bad = [ClaimCheck(claim="never said", verdict="supported", facts=[1], reason=""),
           ClaimCheck(claim="Targeted therapy helps", verdict="supported", facts=[], reason=""),
           ClaimCheck(claim="Targeted therapy helps", verdict="contradicted", facts=[3], reason=""),
           ClaimCheck(claim="Combined therapy hurts", verdict="invented", facts=[1], reason=""),
           ClaimCheck(claim=" ", verdict="invented", facts=[], reason="")]
    assert check_claims(ClaimChecks(claims=bad), text, 2) == [
        'claim 1 "never said": not in the answer', 'claim 2 "Targeted therapy helps": supported needs a fact number',
        'claim 3 "Targeted therapy helps": fact 3 is not in 1 to 2',
        'claim 4 "Combined therapy hurts": invented cites no fact', 'claim 5 " ": empty']


def test_b_repairs_then_goes_pending_and_a_failed_call_is_pending(tmp_path):
    r = rec("Targeted therapy helps.", facts=[pulled("S001")])
    bad = ClaimChecks(claims=[ClaimCheck(claim="never said", verdict="invented", facts=[], reason="")])
    model = scripted(bad, bad)
    out = score_b(q("Q?"), r, model, JsonlCache(tmp_path / "c"), measures=M)
    assert out["status"] == "pending" and out["score"] is None and out["calls"] == 2 and out["claims"] == []
    assert "not in the answer" in model.prompts[1] and out["problems"] == ['claim 1 "never said": not in the answer']
    out = score_b(q("Q?"), r, failing(), JsonlCache(tmp_path / "d"), measures=M)
    assert out["status"] == "pending" and out["score"] is None and "model call failed" in out["problems"][0]


def test_b_without_text_or_without_claims_has_no_score(tmp_path):
    model = boom()
    out = score_b(q("Q?"), rec("  "), model, JsonlCache(tmp_path / "c"), measures=M)
    assert out["score"] is None and model.calls == 0 and out["calls"] == 0 and out["status"] == "ok"
    out = score_b(q("Q?"), rec("Hello."), scripted(ClaimChecks(claims=[])), JsonlCache(tmp_path / "d"), measures=M)
    assert out["score"] is None and out["status"] == "ok" and out["claims"] == []


def test_a_and_b_are_told_a_lower_is_better_measure(folder, tmp_path):
    f = load_folder(folder); qq = q(Q)
    planted = planted_facts(f, qq); sid = next(iter(planted))
    model = scripted(all_missing(planted[sid]), ClaimChecks(claims=[]))
    score_a(f, qq, rec("x", facts=[pulled(sid)]), model, JsonlCache(tmp_path / "c"))
    score_b(qq, rec("Something.", facts=[pulled(sid)]), model, JsonlCache(tmp_path / "c"), measures=f.spec.measures)
    assert all("\nRelapse rate: lower is better\n" in p for p in model.prompts)


def test_the_judge_sees_no_sub_question_and_no_system(folder):
    f = load_folder(folder)
    qq = q(Q, sub_questions=["Secret sub-question?"])
    r = rec("An answer.", facts=[pulled("S001")], system="rag-baseline")
    texts = [b_input(qq, r, r.facts, measures=M),
             *(a_input(ps, [pulled(sid)], measures=M) for sid, ps in planted_facts(f, qq).items())]
    assert not [t for t in texts if "Secret sub-question?" in t or "rag-baseline" in t]
