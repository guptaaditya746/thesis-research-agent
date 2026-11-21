"""S3 paper writer (vendored PaperOrchestra) with a fake `claude` binary: no real LLM calls.

Checks: the Claude adapter never runs more than 3 calls at once (threads and separate backends sharing the slot
locks), calls are cached, the value repair is bounded (one call per failing section, no second round), and a
single missing value triggers exactly one repair call, end to end through `write_paper`.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import textwrap
import threading
from pathlib import Path

import pytest

from evqa import paperwriter

PO = paperwriter.PO_DIR


def _load(name: str):
    """Load one stdlib-only module of the vendored code by path (its `utils` package is not importable here)."""
    spec = importlib.util.spec_from_file_location(f"po_{name}", PO / "utils" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cc = _load("claude_code_utils")
fc = _load("fact_check")

FAKE_CLAUDE = r'''#!{python}
"""Fake `claude -p`: records start/end times, sleeps, answers by the JSON schema it is given."""
import json, os, sys, time
args = sys.argv[1:]
schema = json.loads(args[args.index("--json-schema") + 1])
system = args[args.index("--system-prompt") + 1]
user = sys.stdin.read()
rec = os.environ["FAKE_RECORD"]
t0 = time.time()
time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
props = schema.get("properties", {})
facts = json.loads(os.environ.get("FAKE_FACTS", "[]"))
def table(rows):
    return "Table 1: Results\n\n| Row | Value (pp) |\n|---|---|\n" + "".join(f"| a | {v} |\n" for v in rows)
if "table_plan" in props:
    out = {"table_plan": [], "sentence_facts": [], "section_plan": [],
           "intro_related_work_plan": {"introduction_strategy": {"hook_hypothesis": "h", "problem_gap_hypothesis": "g",
                                       "key_points": []}, "related_work_strategy": {"overview": "o", "subsections": []}}}
elif "introduction" in props:
    out = {"introduction": "Intro text.", "related_work": os.environ.get("FAKE_RELATED", "Prior approaches.")}
elif "Overall" in props:
    out = {k: 3 for k in ("Originality", "Quality", "Clarity", "Significance", "Soundness", "Presentation",
                          "Contribution", "Confidence")}
    out.update({"Overall": 6, "Decision": "Accept", "Summary": "s", "Strengths": [], "Weaknesses": [],
                "Questions": [], "Limitations": []})
elif "worklog" in props:  # refinement: returns the paper unchanged (taken from the prompt)
    paper = user.split("--- CURRENT PAPER (paper.md) ---", 1)[1].split("INSTRUCTION:", 1)[0].strip()
    out = {"worklog": {"addressed_weaknesses": [], "integrated_answers": [], "actions_taken": []}, "markdown": paper}
elif system.startswith("Task: Fix one section"):  # repair: writes every failed value into a sentence
    failed = json.loads(user.split("'failed_values':", 1)[1].split("'section':", 1)[0])
    section = user.split("'section':\n", 1)[1]
    out = {"markdown": section.rstrip() + "\n\n" + " ".join(f"The change was {f['value']} {f['unit']}." for f in failed) + "\n"}
else:  # section writing: every table fact in a table, every sentence fact in a sentence, except FAKE_DROP
    drop = os.environ.get("FAKE_DROP", "")
    tab = [f["value"] for f in facts if f["placement"] == "table" and f["id"] != drop]
    txt = " ".join(f"It changed by {f['value']} {f['unit']}." for f in facts if f["placement"] == "text" and f["id"] != drop)
    related = ("## 2. Related Work\n\n" + os.environ["FAKE_RELATED"] + "\n\n") if os.environ.get("FAKE_RELATED") else ""
    out = {"markdown": "# Paper\n\n## Abstract\n\nA.\n\n## 1. Introduction\n\nIntro text.\n\n" + related + "## 4. Results\n\n"
                       + table(tab) + "\n" + txt + "\n\n## 6. Conclusion\n\nDone.\n"}
with open(rec, "a") as f:
    f.write(json.dumps({"start": t0, "end": time.time(), "step_props": sorted(props)}) + "\n")
print(json.dumps({"structured_output": out, "total_cost_usd": 0.001, "modelUsage": {"fake-model": {}},
                  "usage": {"input_tokens": 1, "output_tokens": 1}}))
'''


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    path = tmp_path / "claude"
    path.write_text(FAKE_CLAUDE.replace("{python}", sys.executable), encoding="utf-8")
    path.chmod(0o755)
    record = tmp_path / "record.jsonl"
    monkeypatch.setenv("FAKE_RECORD", str(record))
    return path, record


def _calls(record: Path) -> list[dict]:
    return [json.loads(line) for line in record.read_text().splitlines()] if record.exists() else []


def _max_overlap(calls: list[dict]) -> int:
    events = sorted([(c["start"], 1) for c in calls] + [(c["end"], -1) for c in calls], key=lambda e: (e[0], e[1]))
    cur = best = 0
    for _, d in events:
        cur += d
        best = max(best, cur)
    return best


def test_adapter_caps_parallel_calls_at_three(tmp_path, fake_claude, monkeypatch):
    path, record = fake_claude
    monkeypatch.setenv("FAKE_SLEEP", "0.4")
    # two backends (as two writer processes would have) share the slot folder; each also asks for more than 3
    lms = [cc.ClaudeCodeLM("fake", cache_dir=tmp_path / "cache", lock_dir=tmp_path / "locks", claude_bin=str(path),
                           max_parallel=8, poll=0.02) for _ in range(2)]
    assert all(lm.max_parallel == 3 for lm in lms)
    threads = [threading.Thread(target=lms[i % 2], args=("sys", f"user {i}", cc.markdown_schema()),
                                kwargs={"step": "t"}) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    calls = _calls(record)
    assert len(calls) == 10
    assert _max_overlap(calls) == 3


def test_adapter_caches_calls(tmp_path, fake_claude):
    path, record = fake_claude
    log = tmp_path / "log.jsonl"
    lm = cc.ClaudeCodeLM("fake", cache_dir=tmp_path / "cache", lock_dir=tmp_path / "locks", claude_bin=str(path),
                         log_path=log)
    a = lm("sys", "same", cc.markdown_schema(), step="s")
    b = lm("sys", "same", cc.markdown_schema(), step="s")
    assert a == b and len(_calls(record)) == 1
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert [r["cached"] for r in rows] == [False, True] and rows[1]["cost_usd"] == 0.0


FACTS = [
    {"id": "R-x-01-01", "value": "-0.46", "unit": "pp", "placement": "table", "line": "l1"},
    {"id": "R-x-01-02", "value": "-0.57", "unit": "pp", "placement": "text", "line": "l2"},
    {"id": "R-x-01-03", "value": "-1.2", "unit": "kg", "placement": "text", "line": "l3"},
]
GOOD = ("# P\n\n## 4. Results\n\nTable 1: r\n\n| Arm | HbA1c (pp) |\n|---|---|\n| a | -0.46 |\n\n"
        "HbA1c fell by -0.57 pp.\n\n## 5. Discussion\n\nWeight changed by -1.2 kg.\n")


def test_check_exact_value_and_place():
    assert all(r["ok"] for r in fc.check_facts(GOOD, FACTS))
    wrong = GOOD.replace("-0.57 pp", "−0.57 pp").replace("| -0.46 |", "| -0.460 |")
    assert [r["ok"] for r in fc.check_facts(wrong, FACTS)] == [False, False, True]
    in_table = GOOD + "\n| Arm | Weight (kg) |\n|---|---|\n| a | -1.2 |\n"
    assert not fc.check_facts(in_table, FACTS)[2]["ok"]       # a sentence value must not sit in a table


def test_repair_is_bounded_to_one_call_per_failing_section():
    paper = GOOD.replace("HbA1c fell by -0.57 pp.", "HbA1c fell.").replace("by -1.2 kg", "a bit")
    seen = []

    def never_fixes(title, text, failed):
        seen.append((title, [f["id"] for f in failed]))
        return text

    out, attempts = fc.repair_round(paper, FACTS, {"R-x-01-03": "5. Discussion"}, never_fixes)
    assert sorted(seen) == [("4. Results", ["R-x-01-02"]), ("5. Discussion", ["R-x-01-03"])]
    assert len(attempts) == 2 and not any(a["accepted"] for a in attempts) and out == paper


def test_repair_that_breaks_a_passing_value_is_rejected():
    paper = GOOD.replace("HbA1c fell by -0.57 pp.", "HbA1c fell.")

    def breaks_table(title, text, failed):
        return text.replace("| -0.46 |", "| -0.5 |") + "\nIt fell by -0.57 pp.\n"

    out, attempts = fc.repair_round(paper, FACTS, {}, breaks_table)
    assert attempts[0]["newly_broken"] == ["R-x-01-01"] and not attempts[0]["accepted"] and out == paper


def test_one_missing_value_triggers_exactly_one_repair(tmp_path, fake_claude, monkeypatch):
    path, record = fake_claude
    facts = [{"id": f"R-med-01-0{i}", "value": v, "unit": "pp", "placement": p}
             for i, (v, p) in enumerate([("-0.46", "table"), ("-0.57", "text"), ("-0.72", "table")], 1)]
    monkeypatch.setenv("FAKE_FACTS", json.dumps(facts))
    monkeypatch.setenv("FAKE_DROP", "R-med-01-02")
    paper_dir = tmp_path / "medical" / "P-med-01"
    paper_dir.mkdir(parents=True)
    (paper_dir / "idea_sparse.md").write_text("# A trial\n\n- Problem: p\n- Hypothesis: h\n", encoding="utf-8")
    rows = "".join(f"| {f['id']} | change in HbA1c | {f['value']} | pp | "
                   f"{'put in a table' if f['placement'] == 'table' else 'state in a sentence'} |\n" for f in facts)
    (paper_dir / "experimental_log.md").write_text(
        "# Log\n\n| Row id | Measure | Value | Unit | Placement |\n|---|---|---|---|---|\n" + rows, encoding="utf-8")
    monkeypatch.setattr(paperwriter, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(paperwriter, "WORK", tmp_path / "work")

    paper = paperwriter.write_paper(paper_dir, model="fake", claude_bin=str(path))

    log = [json.loads(line) for line in (paper_dir / "writer_log.jsonl").read_text().splitlines()]
    repairs = [r for r in log if r["event"] == "repair"]
    assert len(repairs) == 1 and repairs[0]["failed_facts"] == ["R-med-01-02"] and repairs[0]["accepted"]
    repair_calls = [r for r in log if r["event"] == "call" and r["step"].startswith("repair")]
    assert len(repair_calls) == 1
    assert "-0.57 pp" in paper.read_text()
    run = log[-1]
    assert run["event"] == "run" and run["facts_ok"] == 3 and run["facts_failed"] == []
    # outline, intro, section writing, review v0, refine, review v1, repair = 7 calls; max 3 at once
    assert run["calls"] == 7 and _max_overlap(_calls(record)) <= 3
