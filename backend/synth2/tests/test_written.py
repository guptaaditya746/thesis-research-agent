import json
from pathlib import Path

from evaluation import oracle
from evaluation.score import score
from evaluation.truth import GroundTruth
from evidence.rundir import Corpus
from repo_paths import DATA
from synth2.cli import main
from synth2.written import assemble

PROTOCOL = DATA / "domains/rag/protocols/rag-factuality.yaml"


def rewrite(tiny: Path, folder: Path, skip: str | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for p in sorted((tiny / "papers").glob("*.md")):
        if p.stem != skip:
            (folder / p.name).write_text("A new opening sentence.\n\n" + p.read_text(encoding="utf-8"), encoding="utf-8")
    return folder


def test_written_corpus_loads_in_the_engine_and_the_evaluation(tiny, tmp_path):
    papers, out = rewrite(tiny, tmp_path / "w"), tmp_path / "out"
    assert main(["written-corpus", "--template", str(tiny), "--papers", str(papers), "--out", str(out)]) == 0
    corpus = Corpus(out)
    for p in corpus.papers:
        assert corpus.text(p).startswith("A new opening sentence.")
    template, written = GroundTruth.load(tiny / "ground_truth.json"), GroundTruth.load(out / "ground_truth.json")
    assert len(written.facts) == len(template.facts)
    assert not written.placements and written.levels == ["written"]
    assert json.loads((out / "manifest.json").read_text(encoding="utf-8"))["corpus_id"] == \
        json.loads((tiny / "manifest.json").read_text(encoding="utf-8"))["corpus_id"]


def test_a_missing_written_paper_is_refused(tiny, tmp_path, capsys):
    first = sorted((tiny / "papers").glob("*.md"))[0].stem
    papers = rewrite(tiny, tmp_path / "w", skip=first)
    code = main(["written-corpus", "--template", str(tiny), "--papers", str(papers), "--out", str(tmp_path / "out")])
    assert code == 2 and first in capsys.readouterr().err


def test_a_lost_count_is_a_miss_not_a_crash(tiny, tmp_path):
    out = tmp_path / "out"
    assemble(tiny, rewrite(tiny, tmp_path / "w"), out)
    full = oracle.run(PROTOCOL, tiny, tmp_path / "full")
    lines = [json.loads(x) for x in (full / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
    drop = next(i for i, l in enumerate(lines) if l["evidence_type"] == "measurement")
    del lines[drop]
    from evidence.contract import Item
    run = oracle.write_run(tmp_path / "run", [Item.model_validate(l) for l in lines],
                           json.loads((full / "answer.json").read_text(encoding="utf-8")),
                           json.loads((full / "run.json").read_text(encoding="utf-8")))
    report = score(run, out)
    all_all = next(r for r in report["extraction"]["rows"] if r["evidence_type"] == "all" and r["level"] == "all")
    assert all_all["recall"] < 1.0
    assert all_all["span_accuracy"] is None


def test_an_existing_out_folder_is_refused(tiny, tmp_path, capsys):
    out = tmp_path / "out"
    out.mkdir()
    (out / "x").write_text("x")
    code = main(["written-corpus", "--template", str(tiny), "--papers", str(rewrite(tiny, tmp_path / "w")),
                 "--out", str(out)])
    assert code == 2 and "not empty" in capsys.readouterr().err
