"""The protocol lock (spec 6.6): every run writes protocol.lock.json, a protocol that cannot run is refused before any
model call or run folder, `evidence protocol diff` names what differs, and a run made before the lock replays."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from evidence import cli, engine, lockfile
from evidence.extractors import gliner
from evidence.pack import load_pack
from evidence.protocol import load
from evidence.replay import replay
from evidence.rundir import LOCK_FILE, RUN_FILE

from .conftest import PAPERS, PROTOCOL, corpus_of, make_corpus, regex_run_dir, run_json


@pytest.fixture(autouse=True)
def no_gliner(monkeypatch: pytest.MonkeyPatch) -> None:
    gliner.forget()
    monkeypatch.delenv("GLINER_URL", raising=False)


def edited(tmp_path: Path, name: str, edit) -> Path:
    """rag-factuality changed by `edit(data)`, written under tmp_path / "in"."""
    data = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    edit(data)
    out = tmp_path / "in" / f"{name}.yaml"
    out.parent.mkdir(exist_ok=True)
    out.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return out


def with_extractor(tmp_path: Path, etype: str, name: str) -> Path:
    return edited(tmp_path, "unknown", lambda d: d["evidence_types"][etype]["extractors"].insert(0, {"name": name}))


def with_term(tmp_path: Path, name: str, term: str | None) -> Path:
    return edited(tmp_path, name, lambda d: d["screen"]["terms"].append(term) if term else None)


def test_every_run_writes_a_lock_with_all_digests(tmp_path):
    out = regex_run_dir(["Accuracy of RAG is 0.71, closed-book is 0.52."], tmp_path, PROTOCOL)
    lock = json.loads((out / LOCK_FILE).read_text())
    assert lock["protocol"] == {"id": load(PROTOCOL).id, "sha256": load(PROTOCOL).sha256}
    assert lock["pack"] == {"name": "rag", "sha256": load_pack("rag").sha256}
    assert "ontology_sha256" in lock
    expected = [r.name for r in load(PROTOCOL).evidence_types["metric"].extractors]
    ids = lock["extractors"]["metric"]
    assert ids and [i.split("@")[0] for i in ids] == [n for n in expected if n in {i.split("@")[0] for i in ids}]
    assert all(i in run_json(out)["extractors"] for i in ids)
    assert LOCK_FILE in run_json(out)["outputs"]


def test_unknown_extractor_fails_before_any_model_call_and_any_folder(tmp_path):
    def provider(alias):
        pytest.fail("model called")
    corpus = make_corpus(tmp_path / "in" / "corpus")
    with pytest.raises(KeyError, match="no extractor named 'nope'"):
        engine.run(with_extractor(tmp_path, "metric", "nope"), corpus, tmp_path / "out", provider=provider)
    assert not (tmp_path / "out").exists() or list((tmp_path / "out").iterdir()) == []


def test_diff_names_a_changed_term_and_extractor(tmp_path):
    a = regex_run_dir(["x"], tmp_path / "a", with_term(tmp_path, "pa", None))
    b = regex_run_dir(["x"], tmp_path / "b", with_term(tmp_path, "pb", "hallucinate"))
    lines = lockfile.diff(a, b)
    assert 'added screen.terms: "hallucinate"' in lines and any(l.startswith("extractor screen[0]:") for l in lines)


def test_diff_of_the_same_protocol_is_same():
    assert lockfile.diff(PROTOCOL, PROTOCOL) == ["same"]


def test_diff_changed_removed_and_scalar_lists(tmp_path):
    a = with_term(tmp_path, "a", None)
    b = edited(tmp_path, "b", lambda d: (d.update(version=d["version"] + 1), d["screen"]["terms"].pop(0)))
    lines = lockfile.diff(a, b)
    assert any(l.startswith("changed version: ") for l in lines)
    assert 'removed screen.terms: "retrieval-augmented"' in lines


def test_diff_of_a_pre_ev4_run_says_so(tmp_path):
    old = regex_run_dir(["x"], tmp_path, PROTOCOL)
    (old / LOCK_FILE).unlink()
    assert f"no lock (pre-EV4): {old}" in lockfile.diff(old, PROTOCOL)


def test_cli_diff_exit_codes(tmp_path, capsys):
    other = with_term(tmp_path, "other", "hallucinate")
    assert cli.main(["protocol", "diff", str(PROTOCOL), str(PROTOCOL)]) == 0
    assert capsys.readouterr().out.strip() == "same"
    assert cli.main(["protocol", "diff", str(PROTOCOL), str(other)]) == 1
    assert 'added screen.terms: "hallucinate"' in capsys.readouterr().out
    assert cli.main(["protocol", "diff", str(PROTOCOL), str(tmp_path / "missing.yaml")]) == 2


def test_replay_of_a_pre_ev4_run_reports_the_lock_as_added(tmp_path):
    out = regex_run_dir(["Accuracy of RAG is 0.71, closed-book is 0.52."], tmp_path, PROTOCOL)
    (out / LOCK_FILE).unlink()
    data = run_json(out)
    del data["outputs"][LOCK_FILE]
    (out / RUN_FILE).write_text(json.dumps(data), encoding="utf-8")
    new, report = replay(out)
    assert report["ok"] and report["mismatched"] == [] and report["added"] == [LOCK_FILE]
    assert (new / LOCK_FILE).is_file()


def test_replay_of_a_run_with_a_lock_reports_nothing_added(tmp_path):
    out = regex_run_dir(["Accuracy of RAG is 0.71, closed-book is 0.52."], tmp_path, PROTOCOL)
    _, report = replay(out)
    assert report["ok"] and "added" not in report
