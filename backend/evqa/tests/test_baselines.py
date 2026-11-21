"""Baseline runs (evqa/baselines) and the answer-text score (eval/text_answer.py). No model, no subprocess: the
baseline system is a fake runner that writes the thesis-baselines output files; the claim reader is faked."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from pydantic import ValidationError

from evqa import baselines, compare, corpus
from evqa.contracts import Answer, AnswerRow, RunConfig, TextAnswer, TextClaim, TextClaims
from evqa.eval import prism, text_answer

DOMAIN = "medical"


def _cfg(**kw) -> RunConfig:
    base = {"name": "practice-pqa-test", "domain": DOMAIN, "split": "practice", "system": "paperqa2-rag",
            "questions": ["Q-med-p1", "Q-med-p12", "Q-med-p2"]}
    return RunConfig.model_validate({**base, **kw})


# ---------------------------------------------------------------- config
def test_evqa_config_dump_has_no_baseline_keys() -> None:
    """system/baseline are left out while None, so every existing run id stays the same."""
    dumped = RunConfig().model_dump(mode="json", exclude_none=True)
    assert "system" not in dumped and "baseline" not in dumped
    assert RunConfig.load(Path("configs/evqa/practice-qwen.yaml")).run_id() == "practice-qwen-9ac6c1fd8f"


def test_baseline_config_refuses_evqa_step_settings() -> None:
    assert _cfg().is_baseline()
    with pytest.raises(ValidationError):
        _cfg(closed_book=True)
    with pytest.raises(ValidationError):
        _cfg(steps={"spec": {"backend": "qwen", "model": "x"}})
    with pytest.raises(ValidationError):
        _cfg(llm={"backend": "claude", "model": "claude-haiku-5-5"})
    with pytest.raises(ValidationError):
        RunConfig.model_validate({"baseline": {"settings": {}}})        # settings without a baseline system


@pytest.mark.parametrize("path", sorted(Path("configs/evqa").glob("*-pqa-*.yaml"))
                         + sorted(Path("configs/evqa").glob("*-long-context.yaml")))
def test_baseline_configs_load(path: Path) -> None:
    cfg = RunConfig.load(path)
    assert cfg.is_baseline() and cfg.name == path.stem
    assert cfg.split == ("practice" if cfg.name.startswith("practice-") else "test")


def test_command_passes_run_model_and_settings(tmp_path: Path) -> None:
    cfg = _cfg(baseline={"settings": {"evidence_k": 5}})
    cmd = baselines.command(cfg, tmp_path, tmp_path / "bl")
    s = json.loads(cmd[cmd.index("--settings") + 1])
    assert s == {"model": "orch-model", "think": False, "evidence_k": 5}
    assert cmd[cmd.index("--system") + 1] == "paperqa2-rag" and cmd[:4] == ["uv", "run", "--locked", "--project"]


# ---------------------------------------------------------------- import
def test_locate_and_find_hits() -> None:
    paper = "# T\n\nAlpha beta.\n\nGamma delta."
    assert baselines.locate("Gamma delta.", paper) == (18, 30)
    assert baselines.locate("", paper) == (0, len(paper))
    assert baselines.locate("\n Gamma delta.\n", paper) == (18, 30)
    assert baselines.locate("not here", paper) == (-1, -1)
    raw = {"system": "paperqa2-rag", "contexts": [
        {"paper": "P1", "text": "Alpha beta.", "summary": "s", "score": 5},
        {"paper": "P1", "text": "Alpha beta.", "summary": "again", "score": 4},
        {"paper": "P1", "text": "made up", "summary": "", "score": 1},
        {"paper": "P9", "text": "x", "summary": "", "score": 1}]}
    hits, missing = baselines.find_hits(raw, {"P1": paper})
    assert missing == 2 and len(hits) == 1 and hits[0].details["chunks"] == 3
    assert [(p.start, p.end) for p in hits[0].passages] == [(5, 16), (-1, -1)]


def _gold_chunk(qid: str) -> tuple[str, str]:
    """A chunk of the paper holding the first gold fact's L0 span (what a good retriever returns)."""
    g = prism.gold(DOMAIN)[qid]
    f = prism.seed_facts(DOMAIN)[g["row_ids"][0]]
    s, e = prism.l0_spans(DOMAIN, f["paper"])[f["id"]][0]
    text = corpus.papers(DOMAIN)[f["paper"]]
    return f["paper"], text[max(0, s - 40):e + 40]


def _fake_runner(answers: dict[str, dict]):
    def runner(cmd, cwd, stdout, stderr, check):
        out = Path(cmd[cmd.index("--out") + 1])
        qs = [json.loads(x) for x in (out / "questions.jsonl").read_text().splitlines()]
        assert {q["qid"] for q in qs} == set(answers)
        for q in qs:   # the system sees only qid, question, intent card answers (no type, no gold)
            assert set(q) == {"qid", "question", "intent_card"}
            rec = {"qid": q["qid"], "system": "paperqa2-rag", "question_sent": q["question"], "answer": "",
                   "cannot_answer": False, "citations": [], "contexts": [], "tokens": {"prompt": 7, "completion": 3},
                   "cost": 0.0, "seconds": 2.0, "error": None, **answers[q["qid"]]}
            (out / "answers").mkdir(parents=True, exist_ok=True)
            (out / "answers" / f"{q['qid']}.json").write_text(json.dumps(rec))
        return SimpleNamespace(returncode=0)
    return runner


@pytest.fixture()
def baseline_run(tmp_path: Path) -> Path:
    (tmp_path / "bl" / "thesis_baselines").mkdir(parents=True)
    paper, chunk = _gold_chunk("Q-med-p1")
    answers = {
        "Q-med-p1": {"answer": "Veloranide 50 mg lowered HbA1c by 0.52 percentage points at week 12 and by 0.54 "
                               f"percentage points at week 24 versus placebo ({paper}).", "citations": [paper],
                     "contexts": [{"paper": paper, "text": chunk, "summary": "", "score": 9}]},
        "Q-med-p12": {"answer": "I cannot answer.", "cannot_answer": True},
        "Q-med-p2": {"answer": "", "error": "TimeoutError: agent timed out"},
    }
    return baselines.run(_cfg(), tmp_path / "runs", baselines_dir=tmp_path / "bl", runner=_fake_runner(answers))


def test_run_imports_answers_and_prism_scores_l1(baseline_run: Path) -> None:
    out = baseline_run
    assert (out / "config.yaml").is_file() and (out / "manifest.json").is_file()
    ta = TextAnswer.model_validate_json((out / "Q-med-p1" / "answer_text.json").read_text())
    assert ta.citations == ["P-med-05"] and ta.tokens == {"prompt": 7, "completion": 3}
    assert (out / "Q-med-p12" / "answer_text.json").is_file()
    assert not (out / "Q-med-p2").exists()                         # failed question: nothing imported
    events = [json.loads(x) for x in (out / "events.jsonl").read_text().splitlines()]
    end = events[-1]
    assert end["step"] == "run" and end["data"]["failed"] == ["Q-med-p2"] and end["data"]["imported"] == 2
    assert any(e["kind"] == "problem" and e["qid"] == "Q-med-p2" for e in events)
    ev = prism.score_run(out, DOMAIN)
    q1 = ev["questions"]["Q-med-p1"]
    assert q1["l1"] is not None and q1["facts"][0]["l1"] is True and q1["l3"]["score"] is None
    assert q1["advisor"]["score"] is None and q1["l2"]["recall"] is None
    assert ev["system"] == "paperqa2-rag" and ev["totals"]["l3"] is None and ev["totals"]["advisor"] is None
    assert ev["totals"]["not_reported"]["accuracy"] is None          # no structured answer: n/a, not 0
    assert ev["questions"]["Q-med-p2"]["missing_files"] == ["find.jsonl", "answer_text.json"]


# ---------------------------------------------------------------- text score
def _claim(value: str, quote: str, **kw) -> TextClaim:
    return TextClaim(value_text=value, quote=quote, **kw)


def test_check_drops_claims_not_in_the_text() -> None:
    text = "At week 12, X lowered HbA1c by 0.52 percentage points (P-1)."
    assert text_answer.check(_claim("lowered HbA1c by 0.52 percentage points", text), text) is None
    assert text_answer.check(_claim("0.61 percentage points", "lowered by 0.61 percentage points"), text) \
        == "quote is not in the answer text"
    assert text_answer.check(_claim("0.61 pp", text), text) == "value_text is not in its quote"
    assert text_answer.check(_claim("week", "At week"), text) == "value_text holds no number"


def test_same_value_reads_direction_words_and_percent() -> None:
    pp = text_answer.PP
    q = "X lowered HbA1c by 0.52 percentage points at week 12 and by 0.54 at week 24."
    assert text_answer.same_value(_claim("0.54", q), "-0.54", pp)         # sign and unit from its sentence
    assert not text_answer.same_value(_claim("0.54", "X: 0.54 at 12 mg and 2 kg"), "-0.54", pp)
    assert text_answer.same_value(_claim("lowered HbA1c by 0.52 percentage points", ""), "-0.52", pp)
    assert text_answer.same_value(_claim("-0.52%", ""), "-0.52", pp)
    assert not text_answer.same_value(_claim("-0.62 pp", ""), "-0.52", pp)


def _score(qid: str, text: str, claims: list[TextClaim], cannot: bool = False, citations=()) -> dict:
    ta = TextAnswer(qid=qid, system="paperqa2-rag", text=text, cannot_answer=cannot, citations=list(citations))
    tc = TextClaims(qid=qid, text_sha256="x", model="m", claims=claims)
    return text_answer.score_question(prism.gold(DOMAIN)[qid], ta, tc, DOMAIN, None,
                                      sorted(corpus.papers(DOMAIN)))


def test_lookup_needs_each_varying_setting() -> None:
    q = "Veloranide 50 mg lowered HbA1c by 0.52 percentage points at week 12 and by 0.54 percentage points at week 24."
    both = [_claim("lowered HbA1c by 0.52 percentage points", q, subject="Veloranide", time_point="week 12"),
            _claim("0.54 percentage points", q, subject="Veloranide", time_point="week 24")]
    got = _score("Q-med-p1", q, both)
    assert got["score"] == 1.0 and got["exact"] and got["settings_checked"] == ["time_point"]
    swapped = [_claim("lowered HbA1c by 0.52 percentage points", q, subject="Veloranide", time_point="week 24")]
    assert _score("Q-med-p1", q, swapped)["score"] == 0.0           # right number, wrong time point
    q2 = q.replace("Veloranide", "Kavolemin")                     # same numbers, another drug
    other = [_claim("lowered HbA1c by 0.52 percentage points", q2, subject="Kavolemin", time_point="week 12")]
    assert _score("Q-med-p1", q2, other)["score"] == 0.0
    one = _score("Q-med-p1", q, both[:1])
    assert one["recall"] == 0.5 and one["precision"] == 1.0 and not one["exact"]


def test_not_reported_and_list() -> None:
    right = _score("Q-med-p12", "I cannot answer.", [], cannot=True)
    assert right["score"] == 1.0 and not right["hallucination"]
    wrong = _score("Q-med-p12", "It changed by -0.4 mmol/L.", [_claim("-0.4 mmol/L", "It changed by -0.4 mmol/L.")])
    assert wrong["score"] == 0.0 and wrong["hallucination"]
    gold = {r["paper"] for r in prism.gold(DOMAIN)["Q-med-p2"]["answer"]["table"]}
    text = "Studies: " + ", ".join(sorted(gold))
    assert _score("Q-med-p2", text, [])["score"] == 1.0
    assert _score("Q-med-p2", text + ", P-med-01", [])["precision"] < 1.0


def test_render_evqa_answer_states_values_and_papers() -> None:
    rows = [SimpleNamespace(paper="P-med-05")]
    ans = Answer(qid="Q", type="lookup", sentence="Two values.",
                 table=[AnswerRow(cells={"time point": "12 wk"}, value="-0.52", unit=text_answer.PP, rows=[0])])
    text = text_answer.render(ans, rows)   # type: ignore[arg-type]
    assert text == "Two values.\n- time point 12 wk: -0.52 pp [P-med-05]"


def test_score_run_merges_into_eval_and_resolves_blame(baseline_run: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prism.score_run(baseline_run, DOMAIN)
    calls: list[str] = []

    def fake_read(question, text, lm, model, qid):
        calls.append(qid)
        claims = [] if "cannot" in text else [
            _claim("lowered HbA1c by 0.52 percentage points", text, subject="Veloranide", time_point="week 12")]
        return TextClaims(qid=qid, text_sha256=__import__("hashlib").sha256(text.encode()).hexdigest(), model=model,
                          claims=claims)

    monkeypatch.setattr(text_answer, "read_claims", fake_read)
    out = text_answer.score_run(baseline_run, reader_lm=object(), judge_lm=object())   # type: ignore[arg-type]
    assert out["questions"]["Q-med-p1"]["recall"] == 0.5 and out["questions"]["Q-med-p12"]["score"] == 1.0
    assert out["questions"]["Q-med-p2"]["missing"] == "no answer"
    ev = json.loads((baseline_run / "eval.json").read_text())
    assert ev["totals"]["l3_text"] == out["totals"]["l3_text"] and ev["text_eval"]["version"] == "text-1"
    assert ev["questions"]["Q-med-p1"]["l3_text"]["score"] == out["questions"]["Q-med-p1"]["score"]
    blames = [f["blame"] for f in ev["questions"]["Q-med-p1"]["facts"]]
    assert "unscored" not in blames and "none" in blames
    assert ev["totals"]["blame"]["unscored"] == 0
    text_answer.score_run(baseline_run, reader_lm=object(), judge_lm=object())   # type: ignore[arg-type]
    assert len(calls) == 2                                      # claims.json reused for the same text and model
    report = compare.report([baseline_run])
    assert "| system | paperqa2-rag |" in report and "| l3_text |" in report


def test_shipped_configs_are_named_like_their_files() -> None:
    for p in Path("configs/evqa").glob("*.yaml"):
        data = yaml.safe_load(p.read_text())
        if data.get("system"):
            assert data["name"] == p.stem, p
