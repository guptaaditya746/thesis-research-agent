"""Baseline runs (evqa/baselines) and their answer-text score (evqa/scoring.py -> thesis_scorer.text). No model, no subprocess: the
baseline system is a fake runner that writes the thesis-baselines output files; the claim reader is faked."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from pydantic import ValidationError

from thesis_scorer import text as text_answer
from thesis_scorer.llm import Chat
from thesis_scorer.schema import TextClaim, TextClaims

from evqa import baselines, compare, corpus, scoring
from evqa.contracts import Answer, AnswerRow, RunConfig, TextAnswer

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
    g = scoring.gold(DOMAIN)[qid]
    f = scoring.seed_facts(DOMAIN)[g["row_ids"][0]]
    s, e = scoring.l0_spans(DOMAIN, f["paper"])[f["id"]][0]
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
    ev = scoring.score_run(out, DOMAIN)
    q1 = ev["questions"]["Q-med-p1"]
    assert q1["l1"] is not None and q1["facts"][0]["l1"] is True and q1["l3"]["score"] is None
    assert q1["advisor"]["score"] is None and q1["l2"]["recall"] is None
    assert ev["system"] == "paperqa2-rag" and ev["totals"]["l3"] is None and ev["totals"]["advisor"] is None
    assert ev["totals"]["not_reported"]["accuracy"] is None          # no structured answer: n/a, not 0
    assert ev["questions"]["Q-med-p2"]["missing_files"] == ["find.jsonl", "answer_text.json"]


# ---------------------------------------------------------------- text score (rules: services/thesis-scorer tests)
def _claim(value: str, quote: str, **kw) -> TextClaim:
    return TextClaim(value_text=value, quote=quote, **kw)


def test_render_evqa_answer_states_values_and_papers() -> None:
    rows = [SimpleNamespace(paper="P-med-05")]
    ans = Answer(qid="Q", type="lookup", sentence="Two values.",
                 table=[AnswerRow(cells={"time point": "12 wk"}, value="-0.52", unit=text_answer.PP, rows=[0])])
    text = scoring.render(ans, rows)   # type: ignore[arg-type]
    assert text == "Two values.\n- time point 12 wk: -0.52 pp [P-med-05]"


def test_score_run_merges_into_eval_and_resolves_blame(baseline_run: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scoring.score_run(baseline_run, DOMAIN)
    calls: list[str] = []

    def fake_read(question, text, reader, qid, instructions=text_answer.READ_CLAIMS):
        calls.append(qid)
        claims = [] if "cannot" in text else [
            _claim("lowered HbA1c by 0.52 percentage points", text, subject="Veloranide", time_point="week 12")]
        return TextClaims(qid=qid, text_sha256=__import__("hashlib").sha256(text.encode()).hexdigest(),
                          model=reader.name, claims=claims)

    monkeypatch.setattr(text_answer, "read_claims", fake_read)
    def chat() -> Chat:
        return Chat("m", send=lambda body: 1 / 0, cache=False)        # read_claims is faked; no judge call
    out = scoring.score_text(baseline_run, reader_chat=chat(), judge_chat=chat())
    assert out["questions"]["Q-med-p1"]["recall"] == 0.5 and out["questions"]["Q-med-p12"]["score"] == 1.0
    assert out["questions"]["Q-med-p2"]["missing"] == "no answer"
    ev = json.loads((baseline_run / "eval.json").read_text())
    assert ev["totals"]["l3_text"] == out["totals"]["l3_text"] and ev["text_eval"]["version"] == "text-2"
    assert ev["questions"]["Q-med-p1"]["l3_text"]["score"] == out["questions"]["Q-med-p1"]["score"]
    blames = [f["blame"] for f in ev["questions"]["Q-med-p1"]["facts"]]
    assert "unscored" not in blames and "none" in blames
    assert ev["totals"]["blame"]["unscored"] == 0
    scoring.score_text(baseline_run, reader_chat=chat(), judge_chat=chat())
    assert len(calls) == 2                                      # claims.json reused for the same text and model
    report = compare.report([baseline_run])
    assert "| system | paperqa2-rag |" in report and "| l3_text |" in report


def test_shipped_configs_are_named_like_their_files() -> None:
    for p in Path("configs/evqa").glob("*.yaml"):
        data = yaml.safe_load(p.read_text())
        if data.get("system"):
            assert data["name"] == p.stem, p
