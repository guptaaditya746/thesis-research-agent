"""Cost report (#13): paperfactory calls + PaperOrchestra's logs, per role and paper, unknown stays unknown."""
from __future__ import annotations

import json
from pathlib import Path

from paperfactory import cost


def jl(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_writer_cost_is_counted_per_paper_and_role(tmp_path: Path) -> None:
    jl(tmp_path / "calls.jsonl", [{"role": "world", "step": "world:entities", "cost_usd": 0.1},
                                  {"role": "tagger", "step": "tag:P1", "cost_usd": 0.02},
                                  {"role": "judge", "step": "judge:qa:P2:q1", "cost_usd": 0.01}])
    jl(tmp_path / "work" / "P1.log.jsonl", [{"event": "prompt_version"},
                                            {"event": "call", "cached": False, "cost_usd": 0.05},
                                            {"event": "call", "cached": True, "cost_usd": 0.0,
                                             "original_cost_usd": 0.04},
                                            {"event": "call_error", "error": "timeout"}])
    jl(tmp_path / "work" / "P1.redo-2.log.jsonl", [{"event": "call", "cached": False, "cost_usd": 0.03}])
    jl(tmp_path / "work" / "P2.log.jsonl.stale-1", [{"event": "call", "cached": False, "cost_usd": 9.0}])
    (tmp_path / "work" / "P2.log.jsonl").write_text('{"event": "call", "cached": false, "cost_usd": 0.06}\n{"ev')
    r = cost.report(tmp_path, ["P1", "P2"], [10])
    assert r["usd"] == 0.27 and r["by_role"]["writer"]["usd"] == 0.14
    assert r["per_paper"]["P1"]["usd"] == 0.1 and r["per_paper"]["P1"]["by_role"]["writer"]["calls"] == 2
    assert r["per_paper"]["P2"]["usd"] == 0.07 and r["shared"]["usd"] == 0.1
    assert r["usd_cached_original"] == 0.04 and r["writer_failed_attempts_unpriced"] == 1
    assert r["projection"]["10"] == round(0.085 * 10 + 0.1 * 5, 2)


def test_unknown_cost_makes_the_sums_unknown(tmp_path: Path) -> None:
    jl(tmp_path / "calls.jsonl", [{"role": "qa", "step": "qa:P1:q", "cost_usd": None}])
    jl(tmp_path / "work" / "P1.log.jsonl", [{"event": "call", "cached": False, "cost_usd": 0.05}])
    r = cost.report(tmp_path, ["P1"], [100])
    assert r["usd"] == "unknown" and r["usd_known"] == 0.05
    assert r["per_paper"]["P1"]["usd"] == "unknown" and r["by_role"]["writer"]["usd"] == 0.05
    assert r["projection"]["100"] == "unknown"
