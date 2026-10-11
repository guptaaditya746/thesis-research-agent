"""Reply parser, prompt v1 and its baseline, the hand-written concept, answer completion (rows 1.8, 1.10)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import prompts
from agent.answer import build_answer, empty_answer
from agent.concept import concept_sha256, validate_answer, validate_concept
from agent.parse import files_read, normalise_command, parse_reply

from .conftest import fixture

FENCE = "`" * 3
CONCEPTS = Path(prompts.__file__).resolve().parent / "concepts"


# --- parser ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("content, kind, mode, payload", [
    (f"Look.\n{FENCE}bash\nrg -l RAG \"$CORPUS\"\n{FENCE}", "command", "strict", 'rg -l RAG "$CORPUS"'),
    (f"x\n{FENCE}sh\nls\n{FENCE}\n", "command", "strict", "ls"),
    (f"{FENCE}bash\nls\n{FENCE}\nthen\n{FENCE}bash\npwd\n{FENCE}", "command", "lenient_first_of_many", "ls"),
    (f"Done.\n{FENCE}json\n{{\"rows\": []}}\n{FENCE}", "answer", "answer_json_block", '{"rows": []}'),
    (f"{FENCE}\nrg -c x p1.md\n{FENCE}", "command", "lenient_unlabelled_fence", "rg -c x p1.md"),
    (f"{FENCE}\n{{\"rows\": []}}\n{FENCE}", "answer", "lenient_answer_fence", '{"rows": []}'),
    ("<tool_call><function=bash><parameter=command>ls -la</parameter></function></tool_call>",
     "command", "lenient_tool_call", "ls -la"),
    ("rg -l retrieval $CORPUS", "command", "lenient_bare_command", "rg -l retrieval $CORPUS"),
    ("cd $CORPUS\nls | head", "command", "lenient_bare_command", "cd $CORPUS\nls | head"),
    ('{"rows": [], "notes": "none"}', "answer", "lenient_bare_answer", '{"rows": [], "notes": "none"}'),
    ("I will look at the corpus first.\nThen I will count papers.\nFinally I report.\nOK.", "none", "unparsed", ""),
    ("", "none", "unparsed", ""),
    (None, "none", "unparsed", ""),
])
def test_parse_reply(content: str | None, kind: str, mode: str, payload: str) -> None:
    parsed = parse_reply(content)
    assert (parsed.kind, parsed.mode) == (kind, mode)
    assert (parsed.command if kind == "command" else parsed.answer) == payload


def test_several_blocks_tell_the_agent() -> None:
    parsed = parse_reply(f"{FENCE}bash\nls\n{FENCE}\n{FENCE}bash\npwd\n{FENCE}")
    assert "2 bash blocks" in parsed.notice


def test_bash_block_wins_over_json_block() -> None:
    """A json block next to a bash block is data for the command, not the final answer."""
    parsed = parse_reply(f"{FENCE}json\n{{\"rows\": []}}\n{FENCE}\n{FENCE}bash\nls\n{FENCE}")
    assert (parsed.kind, parsed.command) == ("command", "ls")


@pytest.mark.parametrize("command, files, corpus_dir", [
    ('sed -n 1,40p "$CORPUS/p12.md"', ["p12.md"], False),
    ('rg -o -N "x" "$CORPUS"/p3.md "$CORPUS/p12.md" p3.md', ["p3.md", "p12.md"], False),
    ('rg -l RAG "$CORPUS"', [], True),
    ("rg -c retrieval ${CORPUS} | sort", [], True),
    ("cd $CORPUS && head p7.md", ["p7.md"], True),
    ("echo hi; cat notes/xp1.md", [], False),
])
def test_files_read(command: str, files: list[str], corpus_dir: bool) -> None:
    assert files_read(command) == (files, corpus_dir)


def test_normalise_command() -> None:
    assert normalise_command("rg  -l\tx  \n $CORPUS ") == "rg -l x $CORPUS"


# --- prompts ---------------------------------------------------------------------------------------

def test_prompt_files_are_lf_and_hashed() -> None:
    for name in ("system-v1.txt", "system-v1-baseline.txt", "task-v1.txt", "system-v1.diff"):
        assert b"\r" not in (prompts.PROMPT_DIR / name).read_bytes(), name
    on, off = prompts.load("v1", "claim_on"), prompts.load("v1", "claim_off")
    assert on.system_name == "system-v1.txt" and off.system_name == "system-v1-baseline.txt"
    assert on.sha256 != off.sha256 and on.files["task-v1.txt"] == off.files["task-v1.txt"]
    with pytest.raises(ValueError):
        prompts.load("v1", "claim_maybe")


def test_baseline_is_v1_minus_the_claim_block() -> None:
    """2.4: the baseline prompt differs from v1 only by the claim block, as the checked-in diff says."""
    v1 = (prompts.PROMPT_DIR / "system-v1.txt").read_text(encoding="utf-8")
    baseline = (prompts.PROMPT_DIR / "system-v1-baseline.txt").read_text(encoding="utf-8")
    assert baseline == prompts.baseline_from(v1)
    diff = prompts.prompt_diff(v1, baseline)
    assert diff == (prompts.PROMPT_DIR / "system-v1.diff").read_text(encoding="utf-8")
    changed = [ln for ln in diff.splitlines()[2:] if ln[:1] in "+-" and not ln.startswith("@@")]
    assert changed and all(ln.startswith("-") for ln in changed)  # lines removed, none added
    removed = "\n".join(ln[1:] for ln in changed)
    assert removed.startswith(prompts.CLAIM_BLOCK_START) and "partial_number" in removed
    assert "claim" not in baseline.lower()


def test_prompt_v1_content() -> None:
    v1 = (prompts.PROMPT_DIR / "system-v1.txt").read_text(encoding="utf-8")
    for gone in ("spawn", "save_tool", "/corpus", "/work"):
        assert gone not in v1
    for needed in ("$CORPUS", "scratch", "{{steps}}", "{{tokens}}", "rg -o", "EXACTLY ONE fenced bash block",
                   "EXACTLY ONE fenced json block"):
        assert needed in v1
    # Every rejection reason the broker or the anchor library can return is explained.
    for reason in ("not_found", "ambiguous", "partial_number", "empty_quote", "unknown_file",
                   "file_outside_corpus", "malformed_json", "missing_field", "bad_field", "request_too_large",
                   "corpus_file_hash_mismatch"):
        assert f"{reason}" in v1, reason


def test_broker_reasons_are_all_in_the_prompt() -> None:
    """If broker.py or anchor.py gains a rejection reason, the prompt must explain it."""
    source = "".join((prompts.PROMPT_DIR.parent / f).read_text(encoding="utf-8") for f in ("broker.py", "anchor.py"))
    import re
    reasons = set(re.findall(r'Rejected\(f?"([a-z_]+)', source)) | set(re.findall(r'AnchorError\("([a-z_]+)"', source))
    assert {"not_found", "ambiguous", "partial_number", "unknown_file"} <= reasons
    v1 = (prompts.PROMPT_DIR / "system-v1.txt").read_text(encoding="utf-8")
    assert sorted(r for r in reasons if r not in v1) == []


def test_task_message_for_table_and_graph() -> None:
    table = prompts.task_vars(fixture("concept_table.json"))
    assert json.loads(table["row_example"])["cells"] == {"author": "<Person>", "first_author_papers": "<integer>",
                                                         "papers": ["<Paper>"]}
    graph = prompts.task_vars(fixture("concept_graph.json"))
    assert graph["shape_kind"].startswith("graph; each row is one edge")
    assert "facts" in json.loads(graph["row_example"])


# --- the hand-written concept ----------------------------------------------------------------------

def test_hand_written_concept_validates() -> None:
    files = sorted(CONCEPTS.glob("*.json"))
    assert files
    for path in files:
        assert b"\r" not in path.read_bytes()
        assert validate_concept(json.loads(path.read_text(encoding="utf-8"))) == [], path.name


# --- final answer ----------------------------------------------------------------------------------

def test_build_answer_completes_and_checks() -> None:
    concept = fixture("concept_table.json")
    text = json.dumps({"rows": [{"id": "r1", "cells": {"author": "A", "first_author_papers": 2, "papers": ["p1", "p2"]},
                                 "facts": [{"id": "f1", "s": "A", "p": "first author of", "o": "p1",
                                            "claims": ["claim-000001"]},
                                           {"id": "f2", "s": "A", "p": "first author of", "o": "p2"}]}],
                       "notes": "n"})
    answer, problems = build_answer(text, concept, {"claim-000001"})
    assert problems == [] and answer is not None
    assert answer["concept_sha256"] == concept_sha256(concept) and answer["kind"] == "table"
    assert answer["rows"][0]["facts"][1] == {"id": "f2", "s": "A", "p": "first author of", "o": "p2",
                                             "claims": [], "origin": "research"}
    assert validate_answer(answer, concept) == []
    _, problems = build_answer(text, concept, set())
    assert problems == ["claim-000001 is not an accepted claim of this run"]


@pytest.mark.parametrize("text, problem", [
    ("not json", "not valid JSON"),
    ("[1]", "must be one object"),
    ('{"answer": 1}', "unexpected key 'answer'"),
    ('{"rows": [{"id": "r1", "cells": {}, "facts": []}]}', "rows/0"),
])
def test_build_answer_problems(text: str, problem: str) -> None:
    answer, problems = build_answer(text, fixture("concept_table.json"))
    assert answer is None and any(problem in p for p in problems), problems


def test_empty_answer_is_valid() -> None:
    concept = fixture("concept_graph.json")
    assert validate_answer(empty_answer(concept, "budget"), concept) == []
