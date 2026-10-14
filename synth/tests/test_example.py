"""The committed example corpora (synth/examples/rag-demo-*) are what the generator makes now; the CLI and
the review sample work on them."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from synth import cli, corpus
from synth.render_template import TemplateRenderer
from synth.review import CHECKS, write_sample

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
REBUILD = "uv run synth build --name rag-demo --seed 1 --studies 6 --out synth/examples"


def tree(root: Path, prefix: str) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and p.relative_to(root).as_posix().startswith(prefix) and "/review/" not in p.as_posix()}


def test_example_corpus_is_up_to_date(tmp_path: Path) -> None:
    corpus.build(name="rag-demo", seed=1, studies=6, renderer=TemplateRenderer(), out=tmp_path)
    want, have = tree(tmp_path, "rag-demo-"), tree(EXAMPLES, "rag-demo-")
    stale = sorted(k for k in want.keys() | have.keys() if want.get(k) != have.get(k))
    assert not stale, f"synth/examples is stale ({stale[:5]} ...); rebuild with: {REBUILD}"


def test_example_papers_are_lf_only() -> None:
    papers = list(EXAMPLES.glob("rag-demo-*/papers/*.md"))
    assert len(papers) == 36
    assert all(b"\r" not in p.read_bytes() for p in papers)


def test_cli_build_and_sample(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["build", "--name", "c", "--seed", "4", "--studies", "3", "--levels", "explicit,complex",
                     "--effects", "supports=0,contradicts=1", "--out", str(tmp_path)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["answer"]["label"] == "refuted"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["c-complex", "c-explicit", "c-mixed"]
    assert cli.main(["sample", "--corpus", str(tmp_path / "c-mixed"), "--n", "2", "--seed", "1"]) == 0
    md = (tmp_path / "c-mixed" / "review" / "review-s1.md").read_text(encoding="utf-8")
    rows = list(csv.DictReader((tmp_path / "c-mixed" / "review" / "review-s1.csv").open(encoding="utf-8")))
    papers = sorted({r["paper"] for r in rows})
    assert len(papers) == 2 and all(f"## {p}" in md for p in papers) and "[ ]" in md
    gt = json.loads((tmp_path / "c-mixed" / "ground_truth.json").read_text(encoding="utf-8"))
    assert len(rows) == sum(1 for p in gt["placements"] if p["paper"] in papers)
    for r in rows:
        assert all(r[c] == "" for c in CHECKS) and "[[" + r["exact"] + "]]" in r["context"]
        assert r["truth"]


@pytest.mark.parametrize("bad", [["build", "--name", "x", "--seed", "1", "--levels", "easy"],
                                 ["build", "--name", "x", "--seed", "1", "--effects", "positive=1"]])
def test_cli_rejects_bad_arguments(bad: list[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main(bad)


def test_sample_on_the_committed_example(tmp_path: Path) -> None:
    md, cs = write_sample(EXAMPLES / "rag-demo-mixed", 3, 2, tmp_path)
    assert md.exists() and cs.read_bytes().count(b"\n") > 3
