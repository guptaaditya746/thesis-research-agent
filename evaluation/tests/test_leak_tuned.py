"""`evaluate leak` refuses a run whose word writer was tuned on corpora that share condition names with the leak corpus
(C4). Names are compared after `names.clean`, not by hash."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from evaluation import cli
from evidence.plan import WordList, write_plan
from evidence.tests.test_plan_run import make_plan

REAL = Path(__file__).resolve().parents[2] / "tests" / "EV2" / "corpora"


def _renamed(src: Path, dst: Path, prefix: str) -> Path:
    """A copy of a corpus's ground truth whose condition labels all start with `prefix` (so no name is shared)."""
    dst.mkdir(parents=True)
    shutil.copy(src / "manifest.json", dst / "manifest.json")
    text = (src / "ground_truth.json").read_text(encoding="utf-8")
    data = json.loads(text)
    data["corpus_id"] = dst.name
    for study in data["studies"]:
        for c in study.get("conditions", []):
            c["label"], c["aliases"] = f"{prefix} {c['label']}", []
    for f in data.get("facts", []):
        if f.get("type") == "condition":
            f["label"], f["aliases"] = f"{prefix} {f['label']}", []
    (dst / "ground_truth.json").write_text(json.dumps(data), encoding="utf-8")
    return dst


def _tuned(folder: Path, train: list[str], test: list[str], step: str = "write_words") -> Path:
    folder.mkdir(exist_ok=True)
    (folder / f"{step}.json").write_text(json.dumps({"step": step, "train_corpora": train, "test_corpora": test}),
                                         encoding="utf-8")
    return folder


def _run(tmp: Path) -> Path:
    run = tmp / "run"
    run.mkdir()
    plan = make_plan().model_copy(update={"words": WordList(things={"t": ["closed-book"]}, cues=[],
                                                            written_by="orch-model", ontology_names={})})
    write_plan(plan, run / "plan.json")
    return run


def test_leak_refuses_when_the_tuned_writer_saw_the_leak_corpus_names(tmp_path: Path) -> None:
    corpus = REAL / "rag-claude-s1-complex"
    tuned = _tuned(tmp_path / "tuned", ["rag-claude-s1-mixed"], ["rag-claude-small-mixed"])   # other hash, same names
    with pytest.raises(SystemExit, match="tuned write_words.*rag-claude-s1-mixed.*share"):
        cli.main(["leak", "--run", str(_run(tmp_path)), "--corpus", str(corpus), "--out", str(tmp_path / "o"),
                  "--tuned-dir", str(tuned), "--corpora", str(REAL)])
    assert not (tmp_path / "o" / "leak.json").exists()


def test_leak_does_not_refuse_without_a_tuned_file_or_with_other_names(tmp_path: Path, monkeypatch) -> None:
    corpus = REAL / "rag-claude-s1-complex"
    other = _renamed(REAL / "rag-claude-small-mixed", tmp_path / "corpora" / "rag-claude-zzz-mixed", "zzz")
    monkeypatch.setattr("evaluation.score.score_extraction_only", lambda *a, **k: {"missed": []})
    run = _run(tmp_path)
    for tuned in (tmp_path / "no-such-folder", _tuned(tmp_path / "tuned", ["rag-claude-zzz-mixed"], ["rag-claude-zzz-mixed"])):
        assert cli.main(["leak", "--run", str(run), "--corpus", str(corpus), "--out", str(tmp_path / "o"),
                         "--tuned-dir", str(tuned), "--corpora", str(other.parent)]) == 0


def test_leak_refuses_when_a_listed_corpus_cannot_be_read(tmp_path: Path) -> None:
    tuned = _tuned(tmp_path / "tuned", ["rag-claude-nowhere"], [])
    with pytest.raises(SystemExit, match="rag-claude-nowhere"):
        cli.main(["leak", "--run", str(_run(tmp_path)), "--corpus", str(REAL / "rag-claude-s1-complex"),
                  "--out", str(tmp_path / "o"), "--tuned-dir", str(tuned), "--corpora", str(REAL)])


def _manifest_id(folder: Path) -> str:
    return json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["corpus_id"]


def test_leak_resolves_the_manifest_ids_tune_py_writes(tmp_path: Path, monkeypatch) -> None:
    """tune.py records each corpus by its manifest `corpus_id` (rag-claude-k1-<hash>), not by its folder name."""
    train, test = REAL / "rag-claude-k1-mixed", REAL / "rag-claude-small-mixed"
    assert _manifest_id(train) != train.name                                 # the ids differ from the folder names
    run = _run(tmp_path)
    tuned = _tuned(tmp_path / "tuned", [_manifest_id(train)], [_manifest_id(test)])
    with pytest.raises(SystemExit, match="share"):                           # same names: refused, not "cannot be read"
        cli.main(["leak", "--run", str(run), "--corpus", str(REAL / "rag-claude-s1-complex"),
                  "--out", str(tmp_path / "o"), "--tuned-dir", str(tuned), "--corpora", str(REAL)])
    other = _renamed(REAL / "rag-claude-small-mixed", tmp_path / "corpora" / "folder-zzz", "zzz")
    data = json.loads((other / "manifest.json").read_text(encoding="utf-8"))
    data["corpus_id"] = "rag-claude-zzz-0123abcd"
    (other / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr("evaluation.score.score_extraction_only", lambda *a, **k: {"missed": []})
    disjoint = _tuned(tmp_path / "tuned2", [data["corpus_id"]], [data["corpus_id"]])
    assert cli.main(["leak", "--run", str(run), "--corpus", str(REAL / "rag-claude-s1-complex"),
                     "--out", str(tmp_path / "o"), "--tuned-dir", str(disjoint), "--corpora", str(other.parent)]) == 0
