"""Q5 experiment harness: ablation configs switch off exactly one part; `evqa compare` tables (no LLM)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from evqa import compare
from evqa.contracts import ExtractConfig, LinkConfig, RunConfig
from evqa.paths import REPO

CONFIGS = REPO / "configs" / "evqa"
ABLATIONS = sorted((CONFIGS / "ablations").glob("*.yaml"))


def _flat(cfg: RunConfig) -> dict[str, object]:
    """Every setting as a dotted key; extract/links left out (None) count as their defaults."""
    cfg = cfg.model_copy(update={"extract": cfg.extract or ExtractConfig(), "links": cfg.links or LinkConfig()})

    def walk(d: object, prefix: str) -> dict[str, object]:
        if isinstance(d, dict) and d:
            return {k2: v2 for k, v in d.items() for k2, v2 in walk(v, f"{prefix}{k}.").items()}
        return {prefix.rstrip("."): d}
    return walk(cfg.model_dump(mode="json"), "")


def test_five_ablations_exist() -> None:
    assert len(ABLATIONS) == 5


@pytest.mark.parametrize("path", ABLATIONS, ids=lambda p: p.stem)
def test_ablation_differs_in_one_setting(path: Path) -> None:
    base, abl = _flat(RunConfig.load(CONFIGS / "practice-qwen.yaml")), RunConfig.load(path)
    assert abl.name == path.stem and abl.split == "practice"
    diff = {k for k in base.keys() | _flat(abl).keys() if k != "name" and base.get(k) != _flat(abl).get(k)}
    assert len(diff) == 1, diff
    assert _flat(abl)[diff.pop()] in (False, True)


def test_ablations_switch_off_different_parts() -> None:
    base = _flat(RunConfig.load(CONFIGS / "practice-qwen.yaml"))
    keys = set()
    for p in ABLATIONS:
        f = _flat(RunConfig.load(p))
        keys |= {k for k in f if k != "name" and f[k] != base.get(k)}
    assert keys == {"find.search_terms", "find.agent", "extract.extras", "links.verifier", "closed_book"}


# ---------------------------------------------------------------- compare
def _q(qid: str, qtype: str, l3: float, advisor: float, recall: float | None = 1.0) -> dict:
    return {"qid": qid, "type": qtype, "l3": {"score": l3}, "advisor": {"score": advisor},
            "l2": {"recall": recall, "precision": recall}}


def make_run(root: Path, name: str, split: str, l3: float, questions: dict | None = None, *,
             calls: int = 2, seconds: float = 1.5) -> Path:
    d = root / f"{name}-abc"
    d.mkdir()
    (d / "config.yaml").write_text(yaml.safe_dump({"name": name, "split": split}), encoding="utf-8")
    totals = {"questions": 2, "answerable": 1, "facts": 3, "l0": 1.0, "l1": 1.0, "l2_recall": 0.5, "l3": l3,
              "l3_exact": 1, "advisor": 0.6, "not_reported": {"accuracy": 1.0, "hallucination": 0.0},
              "per_type": {"lookup": {"questions": 1, "l3": l3, "exact": 1, "advisor": 0.7},
                           "absent": {"questions": 1, "l3": 1.0, "exact": 1, "advisor": 0.5}}}
    (d / "eval.json").write_text(json.dumps({"config_name": name, "totals": totals, "questions": questions or {}}),
                                 encoding="utf-8")
    events = [{"ts": 1, "qid": None, "step": "run", "kind": "start", "data": {}}]
    for qid in ("Q1", "Q2"):
        events += [{"ts": 2, "qid": qid, "step": "extract", "kind": "start", "data": {}},
                   {"ts": 3, "qid": qid, "step": "extract", "kind": "end",
                    "data": {"seconds": seconds, "count": 1, "llm": {"requests": calls + 1, "calls": calls,
                                                                     "cache_hits": 1}}},
                   {"ts": 3, "qid": qid, "step": "answer", "kind": "end", "data": {"seconds": 0.5, "llm": {}}}]
    events.append({"ts": 4, "qid": None, "step": "run", "kind": "end", "data": {"seconds": 5.0}})
    (d / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return d


def test_tokens_are_summed_when_recorded(tmp_path: Path) -> None:
    d = make_run(tmp_path, "practice-tok", "practice", 0.5, {})
    lines = (d / "events.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(x) for x in lines]
    for e in rows:
        if e["kind"] == "end" and e["step"] == "extract":
            e["data"]["llm"].update(prompt_tokens=100, completion_tokens=20)
    (d / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in rows), encoding="utf-8")
    assert compare.Run(d).cost()["tokens"] == 120   # 2 questions x 120 / 2 questions


def test_compare_practice_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    a = make_run(tmp_path, "practice-qwen", "practice", 0.5,
                 {"Q1": _q("Q1", "lookup", 0.0, 0.7), "Q2": _q("Q2", "absent", 1.0, 0.5, None)})
    b = make_run(tmp_path, "practice-ablate-agent-off", "practice", 1.0,
                 {"Q1": _q("Q1", "lookup", 1.0, 0.7), "Q2": _q("Q2", "absent", 1.0, 0.5, None)}, calls=4, seconds=2.5)
    out = tmp_path / "cmp.md"
    assert compare.main([str(a), str(b), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    print(text)
    assert "| l3 | 0.5 | 1 |" in text
    assert "| lookup l3 | 0.5 | 1 |" in text and "| absent exact | 1 | 1 |" in text
    assert "| LLM real calls / q | 2 | 4 |" in text           # 2 questions x 2 calls / 2 questions
    assert "| LLM requests / q | 3 | 5 |" in text
    assert "| tokens / q | n/a | n/a |" in text
    assert "| step seconds / q | 2 | 3 |" in text            # (1.5 + 0.5) per question
    assert "| wall seconds / q | 2.5 | 2.5 |" in text
    per_q = text.split("## Per-question")[1]
    assert "| Q1 | lookup | l3 | 0 | 1 |" in per_q
    assert "| Q2 |" not in per_q and "advisor" not in per_q      # same values: no difference row


def test_compare_refuses_per_question_for_bench_and_holdout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p1 = make_run(tmp_path, "practice-qwen", "practice", 0.5, {"Q1": _q("Q1", "lookup", 0.0, 0.7)})
    p2 = make_run(tmp_path, "practice-b", "practice", 0.6, {"Q1": _q("Q1", "lookup", 1.0, 0.7)})
    bench = make_run(tmp_path, "bench-qwen", "test", 0.9, {"Q1": _q("Q1", "lookup", 0.3, 0.1)})
    hold = make_run(tmp_path, "holdout-qwen", "practice", 0.8, {"Q1": _q("Q1", "lookup", 0.4, 0.2)})
    test_split = make_run(tmp_path, "slice1", "test", 0.7, {"Q1": _q("Q1", "lookup", 0.6, 0.3)})
    opened: list[Path] = []
    orig = compare.Run.questions

    def spy(self: compare.Run) -> dict:
        opened.append(self.path)
        return orig(self)
    monkeypatch.setattr(compare.Run, "questions", spy)
    text = compare.report([p1, bench, hold, test_split, p2])
    assert list(dict.fromkeys(opened)) == [p1, p2]      # parts 2 and 3 open only the practice runs
    head, per_q = text.split("## Per-question")
    assert "| question | type | measure | practice-qwen-abc | practice-b-abc |" in per_q
    assert "| l3 | 0.5 | 0.9 | 0.8 | 0.7 | 0.6 |" in head      # totals of every run are still shown
    assert "| Q1 | lookup | l3 | 0 | 1 |" in text
    assert "`bench-qwen-abc`: name 'bench-qwen' is a test/hold-out run" in text
    assert "`holdout-qwen-abc`: name 'holdout-qwen' is a test/hold-out run" in text
    assert "`slice1-abc`: split is 'test'" in text
    for r in (bench, hold, test_split):
        with pytest.raises(PermissionError):
            orig(compare.Run(r))


def test_compare_single_practice_run_and_no_config(tmp_path: Path) -> None:
    a = make_run(tmp_path, "practice-qwen", "practice", 0.5)
    b = make_run(tmp_path, "x", "practice", 0.5)
    (b / "config.yaml").unlink()                            # unknown split: refused
    text = compare.report([a, b])
    assert "split is None" in text and "need at least two practice runs" in text


def test_compare_missing_dir(tmp_path: Path) -> None:
    assert compare.main([str(tmp_path / "nope"), "--out", str(tmp_path / "o.md")]) == 2
