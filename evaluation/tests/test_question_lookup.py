"""One question lookup over every pack (final review I1): `evaluate score`, `rag-baseline` and `agent-baseline`
take a question id of any pack's domains/<pack>/questions.yaml, so a drug-trials question is scored and asked like a
RAG one. The drug pack here is the drugtoy test pack (evidence/tests/fixtures); on the cluster the drugtrials pack
lives under domains/, which the tests stand in for by pointing the packs root at the fixtures."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from evaluation import cli
from evaluation.baselines import common
from evidence import contract
from evidence import pack as pack_module
from evidence import questions

from .agentic_fakes import FakeRunner
from .helpers import Scripted, guard_corpus
from .test_agent_baseline import agent_record
from .test_baseline_new_kinds import chain_reply, two_calls, write_drug_corpus

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "evidence" / "tests" / "fixtures"
DRUG_CHAIN = "drug-chain-zel-mor"


@pytest.fixture(autouse=True)
def _registry() -> Iterator[None]:
    """Each test leaves the evidence-type registry as it found it (a drugtoy protocol registers its types)."""
    before = dict(contract.ITEM_PREFIX)
    yield
    contract.ITEM_PREFIX.clear()
    contract.ITEM_PREFIX.update(before)


@pytest.fixture
def drug_packs(monkeypatch: pytest.MonkeyPatch) -> Path:
    """The packs root holds the drug pack (as domains/drugtrials will on the cluster)."""
    monkeypatch.setattr(pack_module, "DOMAINS", FIXTURES)
    return FIXTURES


# --- the lookup ---------------------------------------------------------------------------------------------------

def test_find_reads_every_pack() -> None:
    entry, path = questions.find("rag-factuality")
    assert entry.kind == "effect" and path == pack_module.DOMAINS / "rag" / "questions.yaml"
    entry, path = questions.find(DRUG_CHAIN, root=FIXTURES)
    assert entry.kind == "chaining" and path == FIXTURES / "drugtoy" / "questions.yaml"
    with pytest.raises(ValueError, match="unknown question id 'nope'"):
        questions.find("nope")


def test_an_id_in_two_packs_is_refused(tmp_path: Path) -> None:
    text = "questions:\n  - id: same\n    question: Does it work?\n    kind: effect\n"
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "questions.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="'same' is in two packs"):
        questions.find("same", root=tmp_path)


def test_kind_params_finds_the_pack_of_the_id(drug_packs: Path) -> None:
    params = common.kind_params(DRUG_CHAIN)
    assert params.kind == "chaining" and params.protocol.domain == "drugtoy"


def test_rag_ids_resolve_as_before() -> None:
    """RAG behaviour unchanged: a RAG id still reads domains/rag/questions.yaml and its protocol."""
    assert common.kind_params("rag-factuality").protocol.id == "rag-factuality"
    with pytest.raises(SystemExit, match="unknown question id"):
        cli.main(["rag-baseline", "--corpus", "c", "--out", "o", "--question-id", DRUG_CHAIN])


# --- the baselines ------------------------------------------------------------------------------------------------

def test_rag_baseline_command_takes_a_drug_question_id(tmp_path: Path, drug_packs: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = write_drug_corpus(tmp_path)
    guard_corpus(monkeypatch, corpus)
    model = two_calls(chain_reply())
    monkeypatch.setattr(cli, "_model", lambda alias: (model.model(alias), alias))
    assert cli.main(["rag-baseline", "--corpus", str(corpus), "--out", str(tmp_path / "rag"),
                     "--question-id", DRUG_CHAIN]) == 0
    answer = json.loads((tmp_path / "rag" / "answer.json").read_text(encoding="utf-8"))
    assert answer["kind"] == "chaining" and answer["question_id"] == DRUG_CHAIN
    assert (answer["source"], answer["target"]) == ("Zelvora", "Morvectin")


def test_agent_baseline_command_takes_a_drug_question_id(tmp_path: Path, drug_packs: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    import agent.cli
    import evidence.agentic.runner as runner

    model = Scripted(lambda prompt: chain_reply())
    monkeypatch.setattr(cli, "_model", lambda alias: (model.model(alias), alias))
    monkeypatch.setattr(agent.cli, "stop_on_sigterm", lambda: None)
    monkeypatch.setattr(runner, "ResearchAgentRunner", lambda settings, work_dir=None: FakeRunner(agent_record()))
    corpus = write_drug_corpus(tmp_path)
    assert cli.main(["agent-baseline", "--corpus", str(corpus), "--out", str(tmp_path / "ag"), "--sandbox",
                     "unsandboxed", "--question-id", DRUG_CHAIN]) == 0
    answer = json.loads((tmp_path / "ag" / "answer.json").read_text(encoding="utf-8"))
    assert answer["kind"] == "chaining" and answer["question_id"] == DRUG_CHAIN


# --- the scorer ---------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def drug_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """A template-built drugtoy corpus and a regex-only run of the drugtoy chaining protocol on it, its pack read
    from the fixtures (run.json settings.domains), the packs root left at domains/."""
    from evidence import engine
    from synth import cli as synth_cli

    root = tmp_path_factory.mktemp("drug")
    before = dict(contract.ITEM_PREFIX)
    try:
        assert synth_cli.main(["build", "--name", "dt", "--seed", "5", "--studies", "8", "--levels", "explicit",
                               "--preset", "builds_on", "--domain", "drugtoy", "--root", str(FIXTURES),
                               "--out", str(root / "corpora")]) == 0
        corpus = root / "corpora" / "dt-explicit"
        run = engine.run(FIXTURES / "drugtoy" / "protocols" / "drugtoy-chain.yaml", corpus, root / "runs",
                         selection="regex-only", provider=None, strategy="all", domains=FIXTURES)
    finally:
        contract.ITEM_PREFIX.clear()
        contract.ITEM_PREFIX.update(before)
    return corpus, run


@pytest.mark.parametrize("with_id", [True, False], ids=["question-id", "from-the-run"])
def test_score_command_scores_a_drug_run(tmp_path: Path, drug_run: tuple[Path, Path], with_id: bool) -> None:
    """With the id, and without it (the question the run's protocol asks, from its own pack's questions file)."""
    corpus, run = drug_run
    argv = ["score", "--run", str(run), "--corpus", str(corpus), "--out", str(tmp_path / "out")]
    assert cli.main(argv + (["--question-id", DRUG_CHAIN] if with_id else [])) == 0
    report = json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))
    assert report["question_id"] == DRUG_CHAIN and report["kind"] == "chaining" and report["domain"] == "drugtoy"


def test_score_command_scores_drug_answers_by_id(tmp_path: Path, drug_run: tuple[Path, Path],
                                                 drug_packs: Path) -> None:
    corpus, run = drug_run
    argv = ["score", "--corpus", str(corpus), "--baseline", str(run / "answer.json"), "--out", str(tmp_path / "o")]
    assert cli.main(argv + ["--question-id", DRUG_CHAIN]) == 0
    report = json.loads((tmp_path / "o" / "report.json").read_text(encoding="utf-8"))
    assert report["question_id"] == DRUG_CHAIN and report["domain"] == "drugtoy"
