"""Reply parser, prompts v1 and v2 and their baselines, the hand-written concept, answer completion (rows 1.8, 1.10, 1.13)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import prompts
from agent.answer import build_answer, empty_answer, reply_schema
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


@pytest.mark.parametrize("content, kind, mode, payload", [
    ('{"rows": [], "notes": "n"}', "answer", "guided_answer", '{"rows": [], "notes": "n"}'),
    (' \n{"rows": [{"id": "r1", "cel', "answer", "guided_answer", '{"rows": [{"id": "r1", "cel'),  # cut: check says why
    (f"Done.\n{FENCE}json\n{{\"rows\": []}}\n{FENCE}", "answer", "answer_json_block", '{"rows": []}'),
    (f"{FENCE}bash\nls\n{FENCE}", "command", "strict", "ls"),  # the server ignored the schema
    ("<function=bash><parameter=command>rg -l x $CORPUS</parameter></function>", "command", "lenient_tool_call",
     "rg -l x $CORPUS"),
])
def test_parse_guided_reply(content: str, kind: str, mode: str, payload: str) -> None:
    """1.13: a conclude reply decoded under the answer schema is the bare answer object."""
    parsed = parse_reply(content, guided=True)
    assert (parsed.kind, parsed.mode) == (kind, mode)
    assert (parsed.command if kind == "command" else parsed.answer) == payload
    assert parse_reply('{"rows": []}').mode == "lenient_bare_answer"  # unguided: as before


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
    # ACL Anthology ids (the corpus's other file names), with or without .md
    ('sed -n 1,40p "$CORPUS/2025-acl-long-892.md"', ["2025-acl-long-892.md"], False),
    ('rg -c RAG "$CORPUS"/2025-emnlp-main-1032.md p12.md', ["2025-emnlp-main-1032.md", "p12.md"], False),
    ('for f in 2025-acl-long-1106 2025-emnlp-main-549; do rg -o x "$CORPUS/$f.md"; done',
     ["2025-acl-long-1106.md", "2025-emnlp-main-549.md"], True),
    ("cat x2025-acl-long-1.md 2025-acl-long-7.pdf; date -d 2025-10-13", [], False),
])
def test_files_read(command: str, files: list[str], corpus_dir: bool) -> None:
    assert files_read(command) == (files, corpus_dir)


def test_normalise_command() -> None:
    assert normalise_command("rg  -l\tx  \n $CORPUS ") == "rg -l x $CORPUS"


# --- prompts ---------------------------------------------------------------------------------------

VERSIONS = ("v1", "v2")


@pytest.mark.parametrize("version", VERSIONS)
def test_prompt_files_are_lf_and_hashed(version: str) -> None:
    for name in (f"system-{version}.txt", f"system-{version}-baseline.txt", f"task-{version}.txt",
                 f"system-{version}.diff"):
        assert b"\r" not in (prompts.PROMPT_DIR / name).read_bytes(), name
    on, off = prompts.load(version, "claim_on"), prompts.load(version, "claim_off")
    assert on.system_name == f"system-{version}.txt" and off.system_name == f"system-{version}-baseline.txt"
    assert on.sha256 != off.sha256 and on.files[f"task-{version}.txt"] == off.files[f"task-{version}.txt"]
    with pytest.raises(ValueError):
        prompts.load(version, "claim_maybe")


def test_v1_is_the_prompt_of_the_m1_real_runs() -> None:
    """v1 stays byte for byte what the four M1-real runs used (their config.json hashes), so they can be rerun."""
    seen = {}
    for config in sorted(Path(prompts.__file__).resolve().parents[1].glob("tests/M1-real/*/config.json")):
        files = json.loads(config.read_text(encoding="utf-8"))["prompt"]["files"]
        seen.update(files)
    assert set(seen) == {"system-v1.txt", "system-v1-baseline.txt", "task-v1.txt"}
    on, off = prompts.load("v1", "claim_on"), prompts.load("v1", "claim_off")
    assert {**on.files, **off.files} == seen


@pytest.mark.parametrize("version", VERSIONS)
def test_baseline_is_the_prompt_minus_the_claim_block(version: str) -> None:
    """2.4: the baseline prompt differs from the claim_on prompt only by the claim block, as the checked-in diff says."""
    system = (prompts.PROMPT_DIR / f"system-{version}.txt").read_text(encoding="utf-8")
    baseline = (prompts.PROMPT_DIR / f"system-{version}-baseline.txt").read_text(encoding="utf-8")
    assert baseline == prompts.baseline_from(system)
    diff = prompts.prompt_diff(system, baseline, version)
    assert diff == (prompts.PROMPT_DIR / f"system-{version}.diff").read_text(encoding="utf-8")
    changed = [ln for ln in diff.splitlines()[2:] if ln[:1] in "+-" and not ln.startswith("@@")]
    assert changed and all(ln.startswith("-") for ln in changed)  # lines removed, none added
    removed = "\n".join(ln[1:] for ln in changed)
    assert removed.strip().startswith(prompts.CLAIM_BLOCK_START) and "partial_number" in removed
    assert "claim" not in baseline.lower()


def test_prompt_v2_content() -> None:
    """1.13: real file names, no titles in the manifest, claim where found, the draft, the plan, notices, masking."""
    v2 = (prompts.PROMPT_DIR / "system-v2.txt").read_text(encoding="utf-8")
    baseline = (prompts.PROMPT_DIR / "system-v2-baseline.txt").read_text(encoding="utf-8")
    for needed in ("p12.md", "2025-acl-long-892.md", "2025-emnlp-main-1032.md", "manifest.json", "no titles",
                   "first heading", "in the same command that finds it", "./answer-draft.json", "{{plan_steps}}",
                   "{{plan_tokens}}", "75% of the budget", "50%, 75% and 90%", "at 90%, give the final answer now",
                   "{{mask_keep}}", "{{repeat_stop}}", "one JSON object", "EXACTLY ONE fenced bash block",
                   "EXACTLY ONE fenced json block", "{{steps}}", "{{tokens}}"):
        assert needed in v2, needed
    # The draft, the plan and the notices hold for the baseline too; only the claim block goes.
    for needed in ("./answer-draft.json", "{{plan_steps}}", "50%, 75% and 90%", "{{mask_keep}}"):
        assert needed in baseline, needed
    assert "(p1.md, p2.md, ...)" not in v2  # v1's wrong naming (there is no p1.md; most files are anthology ids)
    for jinja_tag in ("{%", "{#"):  # mini-swe-agent renders the prompt with Jinja
        assert jinja_tag not in v2


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


@pytest.mark.parametrize("version", VERSIONS)
def test_broker_reasons_are_all_in_the_prompt(version: str) -> None:
    """If broker.py or anchor.py gains a rejection reason, the prompt must explain it."""
    source = "".join((prompts.PROMPT_DIR.parent / f).read_text(encoding="utf-8") for f in ("broker.py", "anchor.py"))
    import re
    reasons = set(re.findall(r'Rejected\(f?"([a-z_]+)', source)) | set(re.findall(r'AnchorError\("([a-z_]+)"', source))
    assert {"not_found", "ambiguous", "partial_number", "unknown_file"} <= reasons
    system = (prompts.PROMPT_DIR / f"system-{version}.txt").read_text(encoding="utf-8")
    assert sorted(r for r in reasons if r not in system) == []


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


@pytest.mark.parametrize("name", ["concept_table.json", "concept_graph.json"])
def test_reply_schema(name: str) -> None:
    """1.13: the schema conclude replies are decoded under: the agent's {rows, notes}, no harness fields."""
    from agent import schema
    concept = fixture(name)
    reply = reply_schema(concept)
    text = json.dumps(reply)
    for gone in ("$ref", "$defs", "oneOf", "uniqueItems", "description", "concept_sha256", "origin"):
        assert gone not in text, gone
    assert reply["required"] == ["rows", "notes"] and set(reply["properties"]) == {"rows", "notes"}
    concept_row = prompts.row_example(concept)  # placeholders: strings where values are typed
    if concept["answer_shape"]["kind"] == "table":
        concept_row["cells"] = {"author": "Ann Lee", "first_author_papers": 2, "papers": ["p1", "p2"]}
    else:
        concept_row["attributes"] = {"metric": None}
    good = {"rows": [concept_row], "notes": "n"}
    good["rows"][0]["facts"] = [{"id": "f1", "s": "a", "p": "b", "o": 1, "claims": ["claim-000001"]},
                                {"id": "f2", "s": "a", "p": "b", "o": "c"}]  # claims optional
    assert schema.errors(reply, good) == []
    answer, problems = build_answer(json.dumps(good), concept, {"claim-000001"})
    assert problems == [] and answer is not None  # what the schema lets through, the answer check takes
    for bad in ({"rows": []}, {**good, "kind": "table"},
                {**good, "rows": [{**good["rows"][0], "facts": [{"id": "f1", "s": "a", "p": "b", "o": 1,
                                                                  "origin": "research"}]}]}):
        assert schema.errors(reply, bad), bad


def test_reply_schema_keeps_column_names_that_look_like_keywords() -> None:
    concept = fixture("concept_table.json")
    concept["answer_shape"]["columns"] = [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}]
    cells = reply_schema(concept)["properties"]["rows"]["items"]["properties"]["cells"]
    assert set(cells["properties"]) == {"title", "description"} and cells["required"] == ["title", "description"]
