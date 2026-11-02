"""The run-dir helpers of conftest (regex_run_dir, run_json, funnel_json, answer_of) that plans 2 and 3 use, and
RunDir.items() of a run of a pack other than rag read in a fresh process (the type registry is empty there until
the run's pack is registered)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from evidence import contract

from .conftest import answer_of, funnel_json, regex_run, regex_run_dir, run_json

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DRUG_TOY_DOMAINS = HERE / "fixtures"
DRUG_TOY_PROTOCOL = DRUG_TOY_DOMAINS / "drugtoy" / "protocols" / "drugtoy-response.yaml"
PAPER = "# Trial 1\n\nThe response rate was 34% of patients for Zelvora.\n"
RAG_PAPER = "# Study\n\nWith retrieval, accuracy was 0.71; the closed-book model reached 0.52.\n"


@pytest.fixture(autouse=True)
def _registry():
    before = dict(contract.ITEM_PREFIX)
    yield
    contract.ITEM_PREFIX.clear()
    contract.ITEM_PREFIX.update(before)


def test_regex_run_dir_returns_the_run_dir(tmp_path):
    out = regex_run_dir({"S1": RAG_PAPER}, tmp_path)
    assert (out / "run.json").is_file() and out.parent == tmp_path / "runs"
    assert run_json(out)["settings"]["selection"] == "regex-only"
    assert answer_of(out) == json.loads((out / "answer.json").read_text(encoding="utf-8"))
    assert funnel_json(out)["strategy"] == "all"


def test_regex_run_dir_gives_the_same_answer_as_regex_run(tmp_path):
    answer, _ = regex_run({"S1": RAG_PAPER}, tmp_path / "a")
    assert answer_of(regex_run_dir({"S1": RAG_PAPER}, tmp_path / "b")) == answer


def test_regex_run_dir_takes_a_list_settings_and_a_corpus_path(tmp_path):
    out = regex_run_dir([RAG_PAPER], tmp_path, settings={"names": "on", "run_id": "r"})
    assert out == tmp_path / "runs" / "r" and run_json(out)["settings"]["names"] == "on"
    again = regex_run_dir(tmp_path / "corpus", tmp_path / "two", settings={"run_id": "r"})
    assert answer_of(again)["question"] == answer_of(out)["question"]


def test_items_of_a_drugtoy_run_load_in_a_fresh_process(tmp_path):
    out = regex_run_dir({"P1": PAPER}, tmp_path, DRUG_TOY_PROTOCOL, domains=DRUG_TOY_DOMAINS)
    code = ("import sys; from evidence.rundir import RunDir; "
            "print(sorted({i.evidence_type for i in RunDir(sys.argv[1]).items()}))")
    done = subprocess.run([sys.executable, "-c", code, str(out)], cwd=REPO, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert "result" in done.stdout


def test_items_of_a_drugtoy_run_load_after_the_registry_is_cleared(tmp_path):
    out = regex_run_dir({"P1": PAPER}, tmp_path, DRUG_TOY_PROTOCOL, domains=DRUG_TOY_DOMAINS)
    for name in ("arm", "outcome", "result"):
        contract.ITEM_PREFIX.pop(name, None)
    from evidence.rundir import RunDir
    assert "result" in {i.evidence_type for i in RunDir(out).items()}
