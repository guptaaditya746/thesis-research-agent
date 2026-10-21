"""The committed example corpora (synth/examples/rag-demo-*) are what the generator makes now; the CLI and
the review sample work on them."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from synth import cli, corpus
from synth.fidelity import Check
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
    with (tmp_path / "c-mixed" / "review" / "review-s1.csv").open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    papers = sorted({r["paper"] for r in rows})
    assert len(papers) == 2 and all(f"## {p}" in md for p in papers) and "[ ]" in md
    gt = json.loads((tmp_path / "c-mixed" / "ground_truth.json").read_text(encoding="utf-8"))
    assert len(rows) == sum(1 for p in gt["placements"] if p["paper"] in papers)
    for r in rows:
        assert all(r[c] == "" for c in CHECKS) and "[[" + r["exact"] + "]]" in r["context"]
        assert r["truth"]


def test_cli_fails_when_fidelity_excludes_every_paper(tmp_path: Path, monkeypatch, capsys) -> None:
    class RejectedRenderer(TemplateRenderer):
        def render_all(self, jobs, seed):
            rendered = super().render_all(jobs, seed)
            for paper in rendered.values():
                paper.fidelity.ok = False
            return rendered

    monkeypatch.setattr(cli, "make_renderer", lambda args, out: RejectedRenderer())
    code = cli.main(["build", "--name", "rejected", "--seed", "1", "--studies", "1",
                     "--levels", "explicit", "--out", str(tmp_path)])
    assert code == 1
    assert "no papers retained" in capsys.readouterr().err
    fidelity = json.loads((tmp_path / "rejected-explicit" / "fidelity.json").read_text())
    assert fidelity["excluded"] == ["S001"]
    assert json.loads((tmp_path / "rejected-explicit" / "manifest.json").read_text())["papers"] == []


class HalfRejectedRenderer(TemplateRenderer):
    """Fails fidelity for study S001 only."""
    def render_all(self, jobs, seed):
        rendered = super().render_all(jobs, seed)
        for (sid, _), paper in rendered.items():
            if sid == "S001":
                paper.fidelity.ok = False
                paper.fidelity.checks.append(Check("forced", False, "test"))
        return rendered


def test_build_records_selection_counters(tmp_path: Path) -> None:
    result = corpus.build(name="half", seed=1, studies=2, renderer=HalfRejectedRenderer(), out=tmp_path,
                          levels=["explicit"])
    sel = result["selection"]
    assert (sel["requested_studies"], sel["records"], sel["retained_studies"]) == (2, 2, 1)
    assert sel["per_level"]["explicit"]["failed_checks"] == {"forced": 1}
    assert sel["per_level"]["explicit"]["passed"] == 1
    assert sel["per_level"]["explicit"]["mean_attempts"] >= 1
    assert sel["excluded"] == {"S001": ["explicit"]}
    for lv in ("explicit", "mixed"):
        directory = tmp_path / f"half-{lv}"
        assert json.loads((directory / "corpus.json").read_text())["selection"] == sel
        assert "selection" not in json.loads((directory / "manifest.json").read_text())


def test_cli_min_retained_floor(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "make_renderer", lambda args, out: HalfRejectedRenderer())
    base = ["build", "--name", "half", "--seed", "1", "--studies", "2", "--levels", "explicit"]
    assert cli.main([*base, "--out", str(tmp_path / "a"), "--min-retained", "0.75"]) == 1
    assert "ERROR: retained 1/2 below --min-retained 0.75" in capsys.readouterr().err
    assert cli.main([*base, "--out", str(tmp_path / "b")]) == 0
    assert cli.main([*base, "--out", str(tmp_path / "c"), "--min-retained", "0.5"]) == 0   # 1/2 is not below 0.5


@pytest.mark.parametrize("bad", [["build", "--name", "x", "--seed", "1", "--levels", "easy"],
                                 ["build", "--name", "x", "--seed", "1", "--effects", "positive=1"]])
def test_cli_rejects_bad_arguments(bad: list[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main(bad)


def test_sample_on_the_committed_example(tmp_path: Path) -> None:
    md, cs = write_sample(EXAMPLES / "rag-demo-mixed", 3, 2, tmp_path)
    assert md.exists() and cs.read_bytes().count(b"\n") > 3


def test_sample_sheet_puts_numbers_and_claims_first_and_names_the_file(tmp_path: Path) -> None:
    """Per paper the priority-1 rows (measurements, author claims) come first; every row names the paper file,
    and the check columns sit right after the text so the sheet can be filled left to right."""
    from synth.review import SHEET_COLUMNS
    _, cs = write_sample(EXAMPLES / "rag-demo-mixed", 2, 1, tmp_path)
    with cs.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        assert tuple(reader.fieldnames or ()) == SHEET_COLUMNS
        rows = list(reader)
    assert SHEET_COLUMNS[:10] == ("paper", "priority", "kind", "fact", "truth", "exact", "context",
                                  "present", "states_truth", "unambiguous")
    for paper in {r["paper"] for r in rows}:
        mine = [r for r in rows if r["paper"] == paper]
        priorities = [r["priority"] for r in mine]
        assert priorities == sorted(priorities) and set(priorities) == {"1", "2"}
        assert {r["kind"] for r in mine if r["priority"] == "1"} <= {"measurement", "author_claim"}
        assert all(r["file"] == f"papers/{paper}.md" for r in mine)
    assert cs.read_bytes().startswith(b"\xef\xbb\xbf")      # Excel opens it as UTF-8
