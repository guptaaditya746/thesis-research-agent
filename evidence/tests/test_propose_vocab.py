"""Vocabulary snapshots (docs/evidence-system.md Part E): built offline from local files, sha256 over the
content without the sha256 key, stable across builds; the committed snapshot is the build of its sources."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.canonical import canonical_bytes, sha256_hex
from evidence import cli
from evidence.propose import vocab


def fixture(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "sources.json").write_text(json.dumps([
        {"name": "pwc", "version": "2024-01", "url": "https://example.org/pwc", "file": "metrics.csv"},
        {"name": "kg", "version": "2.0", "url": None, "file": "kg.json"}]), encoding="utf-8")
    (root / "metrics.csv").write_text("label,synonyms,kind,higher_is_better\n"
                                      "Exact Match,EM;exact-match;EM,metric,true\n"
                                      "Hallucination  rate,,metric,false\n", encoding="utf-8")
    (root / "kg.json").write_text(json.dumps([
        {"label": "retrieval-augmented generation", "kind": "method", "synonyms": ["RAG", "retrieval-augmented generation"]},
        {"id": "kg:closed", "label": "closed-book", "kind": "condition"}]), encoding="utf-8")
    return root


def test_build_from_local_files(tmp_path: Path) -> None:
    data = vocab.build("tiny", fixture(tmp_path / "src"))
    assert data["sources"] == [{"name": "pwc", "version": "2024-01", "url": "https://example.org/pwc"},
                               {"name": "kg", "version": "2.0", "url": None}]
    assert [t["id"] for t in data["terms"]] == ["kg:closed", "kg:retrieval_augmented_generation", "pwc:exact_match",
                                                "pwc:hallucination_rate"]
    terms = {t["id"]: t for t in data["terms"]}
    assert terms["pwc:exact_match"] == {"id": "pwc:exact_match", "label": "Exact Match", "synonyms": ["EM", "exact-match"],
                                        "kind": "metric", "source": "pwc", "higher_is_better": True}
    assert terms["pwc:hallucination_rate"]["label"] == "Hallucination rate"
    assert terms["kg:retrieval_augmented_generation"]["synonyms"] == ["RAG"]       # the label is not its own synonym
    assert "higher_is_better" not in terms["kg:closed"]
    body = {k: v for k, v in data.items() if k != "sha256"}
    assert data["sha256"] == sha256_hex(canonical_bytes(body))                       # how the sha256 is made


def test_sha256_is_stable_and_checked(tmp_path: Path) -> None:
    src = fixture(tmp_path / "src")
    first, second = vocab.build("tiny", src), vocab.build("tiny", src)
    assert first == second
    path = vocab.write(first, tmp_path / "tiny.json")
    assert vocab.load(path).sha256 == first["sha256"]
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["terms"][0]["label"] = "open-book"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(vocab.VocabError, match="does not match"):
        vocab.load(path)


def test_duplicate_ids_are_refused(tmp_path: Path) -> None:
    src = fixture(tmp_path / "src")
    (src / "kg.json").write_text(json.dumps([{"label": "closed book", "kind": "condition"},
                                             {"label": "closed-book", "kind": "condition"}]), encoding="utf-8")
    with pytest.raises(vocab.VocabError, match="two terms"):
        vocab.build("tiny", src)


def test_the_committed_snapshot_is_the_build_of_its_sources() -> None:
    committed = vocab.load("rag-factuality")
    rebuilt = vocab.build("rag-factuality", vocab.HERE / "sources" / "rag-factuality")
    assert rebuilt["sha256"] == committed.sha256
    assert committed.match("retrieval augmented generation").id == "hand:retrieval_augmented_generation"
    assert committed.match("Exact-Match").kind == "metric"
    for label in ("closed-book", "factual accuracy", "hallucination rate", "exact match", "F1"):
        assert committed.match(label) is not None, label
    assert committed.match("hallucination rate").higher_is_better is False


def test_cli_vocab_build(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out" / "tiny.json"
    assert cli.main(["vocab", "build", "--name", "tiny", "--source", str(fixture(tmp_path / "src")), "--out", str(out)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["terms"] == 4 and printed["sha256"] == vocab.load(out).sha256
    assert cli.main(["vocab", "build", "--name", "tiny", "--source", str(tmp_path / "missing"), "--out", str(out)]) == 2
