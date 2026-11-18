from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from evidence.kindtext import kind_lines, plan_names
from evidence.plan import with_answer
from evidence.protocol import parse
from evidence.readable import refusal
from evidence.readable.runview import (DIFFERS, LINES, NotRebuilt, RunAnswer, answer_text, checked_view, headline,
                                       read_refusal, read_run, view_of)
from evidence.tests.conftest import DOCS
from evidence.tests.test_plan_run import clean_registry, make_plan, plan_run  # noqa: F401  (autouse fixture)
from evidence.tests.test_written_stage import written_run

GOOD = lambda p: {"sentences": [{"text": "Retrieval helped.", "says": "finding", "facts": [1]}]}


@pytest.mark.parametrize("by, target", [("effect", None), ("consistency", None), ("inventory", "condition"),
                                        ("inventory", "metric"), ("best", None)])
def test_a_fixed_kind_run_reads_as_its_lines(tmp_path, by, target):
    root = plan_run(tmp_path, with_answer(make_plan(), by, target))
    ra = read_run(root)
    answer = json.loads((root / "answer.json").read_text(encoding="utf-8"))["synthesis"]
    protocol = parse((root / "protocol.yaml").read_text(encoding="utf-8"))
    assert ra.kind == by and ra.answer == answer and ra.names == plan_names(make_plan())
    assert answer_text(ra) == "\n".join(l.text for l in kind_lines(protocol, answer, ra.names))
    assert list(ra.items) == list(DOCS) and ra.texts is not None   # DOCS of evidence/tests/conftest.py


def test_a_written_run_reads_as_its_text(tmp_path):
    root = written_run(tmp_path, GOOD)
    out = json.loads((root / "written-answer.json").read_text(encoding="utf-8"))
    ra = read_run(root)
    assert ra.kind == "written" and answer_text(ra) == out["answer_text"] and headline(ra) == "ok"
    assert checked_view(ra) == {"status": "ok", "answer_text": out["answer_text"],
                                "tries": [t["problems"] for t in out["tries"]], "sentences": out["sentences"],
                                "fact_texts": [f["text"] for f in out["facts"]]}


def test_runs_that_cannot_be_rebuilt_say_why(tmp_path):
    assert read_refusal(plan_run(tmp_path / "a")) == LINES
    failed = written_run(tmp_path / "b", lambda p: RuntimeError("gateway down"))
    assert read_refusal(failed).startswith("the written answer's model call failed: ")
    assert read_refusal(failed).endswith("; run it again with retry")
    gone = plan_run(tmp_path / "c", with_answer(make_plan(), "effect", None))
    (gone / "run.json").unlink()
    assert read_refusal(gone) == "the run is not complete (state unsealed)"
    with pytest.raises(NotRebuilt, match="not complete"):
        read_run(gone)


def tamper(root: Path, name: str) -> None:
    """Change a sealed run file after the run: the written answer as a whole (its text, its tries and its sentences,
    so the file is still consistent with itself), any other file by one more blank line or key order."""
    path = root / name
    if name == "written-answer.json":
        path.write_bytes(path.read_bytes().replace(b"Retrieval helped", b"Retrieval did not help"))
    elif name.endswith(".jsonl"):
        path.write_bytes(path.read_bytes() + b"\n")   # read_lines skips the blank line: the items stay the same
    else:
        path.write_text(json.dumps(json.loads(path.read_text(encoding="utf-8")), indent=3), encoding="utf-8")


@pytest.mark.parametrize("by, name", [("written", "written-answer.json"), ("written", "evidence.jsonl"),
                                      ("effect", "answer.json"), ("effect", "evidence.jsonl"),
                                      ("consistency", "reason.json")])
def test_a_file_changed_after_the_run_is_refused(tmp_path, by, name):
    """I1: a program never says "this is the answer the run recorded" for an answer the run did not record."""
    root = written_run(tmp_path, GOOD) if by == "written" else plan_run(tmp_path, with_answer(make_plan(), by, None))
    assert read_refusal(root) is None
    tamper(root, name)
    want = DIFFERS.format(file=name)
    assert want == f"the {name} of the run differs from what run.json recorded; run evidence verify"
    assert read_refusal(root) == want and refusal(root) == want
    with pytest.raises(NotRebuilt) as caught:
        read_run(root)
    assert str(caught.value) == want


def test_a_reasoned_run_carries_its_inferences_and_texts_can_be_skipped(tmp_path):
    root = plan_run(tmp_path, with_answer(make_plan(), "consistency", None))   # plan_run reasons (reason on)
    assert (root / "reason.json").is_file() and read_run(root).inferred is not None
    assert read_run(root, texts=False).texts is None


def test_without_the_corpus_items_group_by_file_and_texts_are_none(tmp_path):
    root = plan_run(tmp_path, with_answer(make_plan(), "effect", None))
    shutil.rmtree(tmp_path / "corpus")
    ra = read_run(root)
    assert ra.texts is None and set(ra.items) <= set(DOCS) and answer_text(ra)


def test_views_leave_ids_out_and_headlines_name_the_result():
    best = {"metric": "accuracy", "wins": {"rag": 2}, "winner": "rag", "tied": [], "studies": [
        {"document": "S001", "winner": "rag", "tied": [], "values": {"rag": 0.6, "closed_book": 0.5}, "reason": None}]}
    assert view_of("best", best) == best
    inv = {"target": "condition", "entries": [{"name": "A", "aliases": ["a"], "papers": ["S001"],
                                               "items": ["condition-0123456789abcdef"]}]}
    assert view_of("inventory", inv) == {"target": "condition", "entries": [{"name": "A", "aliases": ["a"],
                                                                              "papers": ["S001"]}]}


def test_headlines():
    def built(kind, answer):
        return RunAnswer(run=Path("x"), kind=kind, protocol=None, roles=None, plan=None, names={}, answer=answer,
                         items={}, texts=None, record={}, outputs={})
    assert headline(built("effect", {"label": "supported"})) == "supported"
    assert headline(built("consistency", {"agreeing": 2, "disagreeing": 1})) == "agreeing 2, disagreeing 1"
    assert headline(built("best", {"winner": None, "tied": ["a", "b"]})) == "tie: a, b"
    assert headline(built("best", {"winner": None, "tied": []})) == "none"
    assert headline(built("inventory", {"entries": [{"name": "A"}, {"name": "B"}]})) == "A, B"
