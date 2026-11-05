"""C1 -> C2 on C1's real files: `gold build | triage | pool | draft`, then `push`, people answer, `pull`,
`export`, with the scripted model and the in-memory Argilla.

C2 was built against the plan's contract before C1 existed (gold/tests/fixtures.py writes C1's files
by hand); this checks the review on what C1 really writes (pool.jsonl without stratum, pool.strata.json
with id lists, candidates with C1's row fields), and that the reviewed key groups the facts people kept
exactly as the draft key does, since both now take C1's row rule from gold/build.py."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from jsonio import write_json
from gold import build_cli, review
from gold.build import norm
from gold.cli import main

from .fixtures import FakeArgilla, fake  # noqa: F401
from .scripted import GRAPH_RULES, Script, corpus, graph_concept, table_concept

QID = "q01"
QUESTION = "Which benchmarks do the RAG papers evaluate on?"


def rows_as_sets(key: dict[str, Any]) -> list[frozenset[tuple[str, str, str]]]:
    """A key's rows as the sets of their facts' normalised s/p/o, in a fixed order."""
    rows = [frozenset((norm(f["s"]), norm(f["p"]), norm(f["o"])) for f in row["facts"]) for row in key["rows"]]
    return sorted(rows, key=lambda r: sorted(r))


@pytest.mark.parametrize("shape", ["table", "graph"])
def test_reviewed_key_groups_kept_facts_as_the_draft_does(shape: str, tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch, fake: FakeArgilla) -> None:
    c = corpus(tmp_path)
    if shape == "table":
        concept, script = table_concept(), Script()
    else:
        concept = graph_concept()
        script = Script(rules=list(GRAPH_RULES), labels={"HotpotQA": "context", "GSM8K": "answers",
                                                          "exact match": "answers"})
    concepts = tmp_path / "concepts"
    (concepts / QID).mkdir(parents=True)
    write_json(concepts / QID / "concept.json", concept)
    write_json(concepts / QID / "session.json", {"question": QUESTION})
    questions = tmp_path / "questions.json"
    write_json(questions, {"schema_version": 1, "questions": [
        {"id": QID, "category": "corpus_wide", "question": QUESTION, "source": "nlp33", "notes": ""}]})
    gold = tmp_path / "gold"
    for name, value in (("CORPUS", c.root), ("CONCEPTS", concepts), ("GOLD", gold), ("QUESTIONS", questions)):
        monkeypatch.setenv(name, str(value))
    monkeypatch.setattr(build_cli, "_rotation", lambda args: script.rotation())

    # C1, as on the cluster (a trial over three papers, hence --allow-partial).
    assert main(["build", QID, "--only-papers", "p3,p5,p6"]) == 0
    assert main(["triage", QID]) == 0
    assert main(["pool", QID, "--sample", "50", "--allow-partial"]) == 0
    assert main(["draft", QID, "--allow-partial"]) == 0
    draft = json.loads((gold / QID / "key.draft.json").read_text(encoding="utf-8"))
    in_draft = {f["candidate_id"] for row in draft["rows"] for f in row["facts"]}
    in_draft |= {c for merged in draft.get("merged_facts", {}).values() for c in merged}  # fact id -> duplicates
    assert draft["rows"] and in_draft

    # C2 on C1's files: every pool record is pushed; strata come from pool.strata.json's id lists.
    write_json(gold / review.OVERLAP_FILE, {"seed": "test", "share": 0.2, "questions": [QID], "overlap": []})
    paths = ["--gold", str(gold), "--corpus", str(c.root), "--concepts", str(concepts), "--questions", str(questions)]
    assert main(["push", QID, *paths]) == 0
    pool = review.pool(gold, QID)
    strata = json.loads((gold / QID / "pool.strata.json").read_text(encoding="utf-8"))["strata"]
    assert {item["id"]: item["stratum"] for item in pool} == {
        **{i: "triaged" for i in strata["triaged"]}, **{i: "sample" for i in strata["sample"]}}
    dataset = fake.dataset("review")
    assert len(dataset.rows) == len(pool)
    # The reviewer keeps exactly what the draft kept, and drops the rest.
    for item in pool:
        if item["id"] in in_draft:
            dataset.answer(review.record_id(item), "aditya", label="correct", vital="yes")
        else:
            dataset.answer(review.record_id(item), "aditya", label="incorrect")
    assert main(["pull", "--gold", str(gold)]) == 0
    assert main(["export", QID, *paths]) == 0
    key = json.loads((gold / QID / "key.json").read_text(encoding="utf-8"))
    assert key["reviewed"] is True and key["concept_sha256"] == draft["concept_sha256"]
    assert rows_as_sets(key) == rows_as_sets(draft)
    if shape == "table":  # MMLU from p3 and p5 is one row, its count recomputed by C1's count rule
        mmlu = [row for row in key["rows"] if norm(row["cells"]["dataset"]) == "mmlu"]
        assert len(mmlu) == 1 and mmlu[0]["cells"]["paper_count"] == len(mmlu[0]["cells"]["papers"]) == 2
