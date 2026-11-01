"""The SciREX real-paper check (D21, spec 6.12): corpus from the SciREX JSON lines, names scored at mention level and
at salient-cluster level. The fixture `scirex_tiny.jsonl` is two hand-made papers in SciREX's shape (not SciREX
data). Every coref cluster is salient (SciREX README). d1 has the clusters BERT and SQuAD (its relation's task and
metric name no cluster); d2 has three clusters, and its relation's method (GAT) names no cluster, so d2 has no
salient method (GCN and ResNet are ner mentions only)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from evaluation import cli
from evaluation.realpapers.common import items_of, write_real
from evaluation.realpapers.scirex import GOLD_FILE, score, to_corpus
from evidence.contract import Item, Span
from evidence.pack import load_pack, protocol_path
from evidence.protocol import load
from evidence.rundir import EVIDENCE_FILE, PROTOCOL_FILE, write_lines
from evidence.tests.conftest import regex_run_dir

from .helpers import guard_corpus

TINY = Path(__file__).resolve().parent / "data" / "scirex_tiny.jsonl"
ML_NAMES_PROTOCOL = protocol_path("ml", "names")


@pytest.fixture(autouse=True)
def code_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sealed runs name commit `test` (no `git rev-parse` per run; F54)."""
    monkeypatch.setenv("EVIDENCE_CODE_COMMIT", "test")


def run_with_items(tmp: Path, items: list[tuple[str, str, tuple[int, int]]], doc: str = "d1") -> Path:
    """A run directory holding only the ml names protocol and the given items (type, name, (start, end)) of paper
    `doc`; the selector carries the offsets only, so a span may be empty (it then overlaps no mention)."""
    run = tmp / "run"
    run.mkdir(parents=True)
    (run / PROTOCOL_FILE).write_bytes(ML_NAMES_PROTOCOL.read_bytes())
    load(ML_NAMES_PROTOCOL)   # registers the ml types
    built = [Item.build(etype, {"name": name}, [Span(role="quote", selector={"file": f"papers/{doc}.md", "start": s,
                                                                            "end": e})])
             for etype, name, (s, e) in items]
    write_lines(run / EVIDENCE_FILE, [i.model_dump(mode="json") for i in built])
    return run


def gold_of(corpus: Path) -> dict[str, Any]:
    return json.loads((corpus / GOLD_FILE).read_text(encoding="utf-8"))


def test_corpus_offsets_match_tokens(tmp_path: Path) -> None:
    c = to_corpus(TINY, tmp_path)
    gold = json.loads((c / "scirex_gold.json").read_text())["d1"]
    text = (c / "papers/d1.md").read_text()
    assert [text[s:e] for s, e, *_ in gold["mentions"]] == ["BERT", "SQuAD"]


def test_corpus_joins_words_by_spaces_and_sections_by_blank_lines(tmp_path: Path) -> None:
    c = to_corpus(TINY, tmp_path)
    assert (c / "papers/d1.md").read_bytes() == b"Reading with BERT\n\nWe fine-tune BERT on SQuAD and report F1 ."
    manifest = json.loads((c / "manifest.json").read_text(encoding="utf-8"))
    assert [p["id"] for p in manifest["papers"]] == ["d1", "d2"]
    gold = gold_of(c)["d2"]
    text = (c / "papers/d2.md").read_text(encoding="utf-8")
    assert [(text[s:e], t) for s, e, t, _ in gold["mentions"]] == [
        ("GCN", "method"), ("Cora", "dataset"), ("node classification", "task"), ("accuracy", "metric"),
        ("ResNet", "method")]
    assert all(text[s:e] == written for s, e, _, written in gold["mentions"])
    assert {name: [text[s:e] for s, e in spans] for name, spans in gold["clusters"].items()}["Node_Classification"] \
        == ["node classification"]


def test_salient_clusters_are_the_coref_clusters(tmp_path: Path) -> None:
    c = to_corpus(TINY, tmp_path)
    gold = gold_of(c)
    assert gold["d1"]["salient"] == ["BERT", "SQuAD"]      # the relation's Task and Metric name no cluster of d1
    assert gold["d2"]["salient"] == ["Accuracy", "Cora", "Node_Classification"]
    assert gold["d2"]["types"] == {"Accuracy": "metric", "Cora": "dataset", "Node_Classification": "task"}
    source = json.loads((c / "scirex_corpus.json").read_text(encoding="utf-8"))
    assert (source["coref_clusters"], source["clusters_in_no_relation"], source["clusters_untyped"],
            source["clusters_without_spans"]) == (5, 0, 0, 0)


def test_a_cluster_no_relation_names_is_salient_and_counted(tmp_path: Path) -> None:
    """The relation filter's drop count: a coref cluster no relation names stays salient, typed by its ner mention;
    one with no ner mention at its spans is left out and counted as untyped."""
    doc = {"doc_id": "x1", "words": ["ELMo", "and", "BERT", "on", "SQuAD", "use", "pooling"], "sections": [[0, 7]],
           "ner": [[0, 1, "Method"], [2, 3, "Method"], [4, 5, "Material"]],
           "coref": {"ELMo": [[0, 1]], "BERT": [[2, 3]], "SQuAD": [[4, 5]], "Pooling": [[6, 7]]},
           "n_ary_relations": [{"Method": "BERT", "Material": "SQuAD", "Task": "QA", "Metric": "EM", "Score": "80"}]}
    jsonl = tmp_path / "x.jsonl"
    jsonl.write_text(json.dumps(doc) + "\n", encoding="utf-8")
    c = to_corpus(jsonl, tmp_path / "c")
    gold = gold_of(c)["x1"]
    assert gold["salient"] == ["BERT", "ELMo", "SQuAD"] and gold["types"]["ELMo"] == "method"
    assert (gold["in_no_relation"], gold["untyped"]) == (["ELMo", "Pooling"], ["Pooling"])
    source = json.loads((c / "scirex_corpus.json").read_text(encoding="utf-8"))
    assert (source["coref_clusters"], source["clusters_in_no_relation"], source["clusters_untyped"]) == (4, 2, 1)


def test_limit_below_one_and_a_bad_line_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        to_corpus(TINY, tmp_path / "a", limit=0)
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({"doc_id": "b1", "words": ["x"], "sections": [[0, 1]], "ner": [[0, 1, "Thing"]]}) + "\n",
                   encoding="utf-8")
    with pytest.raises(ValueError, match="SciREX paper b1"):
        to_corpus(bad, tmp_path / "b")


def test_limit_keeps_the_first_papers_and_is_recorded(tmp_path: Path) -> None:
    c = to_corpus(TINY, tmp_path, limit=1)
    assert [p["id"] for p in json.loads((c / "manifest.json").read_text(encoding="utf-8"))["papers"]] == ["d1"]
    assert list(gold_of(c)) == ["d1"]
    source = json.loads((c / "scirex_corpus.json").read_text(encoding="utf-8"))
    assert (source["limit"], source["papers"], source["papers_in_file"]) == (1, 1, 2)


def test_engine_never_reads_scirex_gold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The open-monitor (F38): inside the corpus only manifest.json and papers/ may be opened; the gold is also
    made unparsable, so a reader that slipped past the monitor would fail."""
    c = to_corpus(TINY, tmp_path / "c")
    (c / "scirex_gold.json").write_text("not json")
    attempts = guard_corpus(monkeypatch, c)
    with pytest.raises(AssertionError):   # the monitor is live: opening the gold is caught
        open(c / "scirex_gold.json", encoding="utf-8")
    attempts.clear()
    run = regex_run_dir(c, tmp_path, ML_NAMES_PROTOCOL)   # must not fail
    assert attempts == []
    assert json.loads((run / "answer.json").read_text(encoding="utf-8"))["target"] == "method"


def test_two_levels(tmp_path: Path) -> None:
    r = score(run_with_items(tmp_path, [("method", "bert", (0, 0))]), to_corpus(TINY, tmp_path / "c"))
    assert r["mention"]["method"]["recall"] == 0.0 and r["salient"]["method"]["recall"] == 1.0


def test_both_levels_count_per_type(tmp_path: Path) -> None:
    corpus = to_corpus(TINY, tmp_path / "c")
    text = (corpus / "papers/d2.md").read_text(encoding="utf-8")
    at = text.index("Cora")
    r = score(run_with_items(tmp_path, [("dataset", "cora", (at, at + 2)), ("dataset", "CORA", (0, 3)),
                                        ("dataset", "ImageNet", (0, 5)), ("method", "ResNet", (0, 1))], doc="d2"),
              corpus)
    assert r["papers"] == 2
    # mention level: of three dataset items one overlaps the Cora mention; one of the two dataset mentions is matched
    assert r["mention"]["dataset"] == {"items": 3, "right_items": 1, "mentions": 2, "matched_mentions": 1,
                                       "precision": pytest.approx(1 / 3), "recall": 0.5}
    # salient level: "cora" and "CORA" are one name; Cora (d2) is hit, SQuAD (d1) is not; ImageNet is wrong
    assert r["salient"]["dataset"] == {"names": 2, "right_names": 1, "clusters": 2, "clusters_hit": 1,
                                       "precision": 0.5, "recall": 0.5}
    # ResNet is a ner mention of d2 but no coref cluster: not salient, so the name is wrong at this level (and
    # the one salient method cluster, BERT of d1, is not hit)
    assert r["salient"]["method"]["right_names"] == 0 and r["salient"]["method"]["recall"] == 0.0
    assert r["mention"]["task"] == {"items": 0, "right_items": 0, "mentions": 1, "matched_mentions": 0,
                                    "precision": None, "recall": 0.0}


def test_items_of_reads_through_the_run_dir(tmp_path: Path) -> None:
    run = run_with_items(tmp_path, [("task", "node classification", (0, 4))])
    assert [(i.evidence_type, i.fields["name"]) for i in items_of(run)] == [("task", "node classification")]


def test_real_md_says_real_paper_check(tmp_path: Path) -> None:
    write_real({"papers": 1}, tmp_path, "SciREX test split")
    assert (tmp_path / "real.md").read_text().startswith("# real-paper check: SciREX test split (not a synthetic score)")


def test_write_real_writes_json_and_tables(tmp_path: Path) -> None:
    result = {"papers": 2, "mention": {"method": {"precision": 0.5, "recall": None}}, "notes": ["gold read by the scorer only"]}
    js, md = write_real(result, tmp_path / "out", "SciREX test split")
    assert json.loads(js.read_text(encoding="utf-8")) == result
    text = md.read_text(encoding="utf-8")
    assert "- papers: 2" in text and "| method | 0.5 | - |" in text and "- gold read by the scorer only" in text


def test_ml_pack_is_a_names_pack(tmp_path: Path) -> None:
    pack = load_pack("ml")
    assert {t: d.role.value for t, d in pack.types.items()} == {
        "method": "compared_thing", "dataset": "context", "task": "context", "metric": "metric",
        "measurement": "measured_value"}
    rag = load_pack("rag")
    assert all(pack.types[t].prefix == rag.types[t].prefix for t in ("metric", "dataset", "measurement"))
    protocol = load(ML_NAMES_PROTOCOL)
    assert (protocol.kind, protocol.domain, protocol.inventory.target) == ("inventory", "ml", "method")
    assert set(protocol.evidence_types) == {"method", "dataset", "task", "metric"}
    questions = yaml.safe_load((ML_NAMES_PROTOCOL.parents[1] / "questions.yaml").read_text(encoding="utf-8"))
    assert [q["kind"] for q in questions["questions"]] == ["inventory"]


def test_cli_corpus_then_score(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    corpus, out = tmp_path / "c", tmp_path / "out"
    assert cli.main(["scirex", "corpus", "--jsonl", str(TINY), "--out", str(corpus), "--limit", "2"]) == 0
    run = run_with_items(tmp_path, [("method", "BERT", (0, 0))])
    estimate = tmp_path / "estimate.json"
    estimate.write_text(json.dumps({"calls": {"low": 8, "high": 8}, "tokens": {"low": 100, "high": 100}}),
                        encoding="utf-8")
    assert cli.main(["scirex", "score", "--run", str(run), "--corpus", str(corpus), "--out", str(out),
                     "--estimate", str(estimate)]) == 0
    real = json.loads((out / "real.json").read_text(encoding="utf-8"))
    assert real["papers"] == 2 and real["limit"] == 2 and real["estimate"]["calls"] == {"low": 8, "high": 8}
    assert (real["coref_clusters"], real["clusters_in_no_relation"]) == (5, 0)
    md = (out / "real.md").read_text(encoding="utf-8")
    assert md.startswith("# real-paper check: SciREX (not a synthetic score)")
    assert "evidence estimate" in md


def test_a_run_of_another_corpus_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no paper of"):
        score(run_with_items(tmp_path, [("method", "BERT", (0, 4))], doc="other"), to_corpus(TINY, tmp_path / "c"))
