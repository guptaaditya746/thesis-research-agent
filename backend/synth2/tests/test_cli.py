import json
from synth2.cli import main


def test_build_reference_score_end_to_end(tmp_path, capsys):
    root = tmp_path / "grid"
    assert main(["build", "--out", str(root), "--seeds", "2", "--laws", "opposed,uniform", "--texts", "table,split"]) == 0
    assert sorted(p.name for p in root.iterdir() if p.is_dir()) == ["opposed-split", "opposed-table", "uniform-split", "uniform-table"]
    built = sum(1 for _ in root.glob("*/s*/base/manifest.json"))
    skipped = json.loads((root / "skipped.json").read_text(encoding="utf-8"))
    assert built + len(skipped) == 8
    assert main(["reference", "--root", str(root), "--rule", "pooled", "--out", str(tmp_path / "oracle.json")]) == 0
    assert main(["score", "--root", str(root), "--answers", str(tmp_path / "oracle.json"), "--out", str(tmp_path / "report.json")]) == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["all"]["recovers_law"]["mean"] == 1.0
    assert report["all"]["follows_evidence"]["mean"] == 1.0
    assert report["all"]["resists_overclaiming"]["mean"] == 1.0
    assert report["all"]["stays_steady"]["mean"] == 1.0
    assert "recovers_law" in capsys.readouterr().out


def test_bad_arguments_exit_2(tmp_path):
    assert main(["build", "--out", str(tmp_path / "g"), "--laws", "sideways"]) == 2
    assert main(["reference", "--root", str(tmp_path), "--rule", "guess", "--out", str(tmp_path / "a.json")]) == 2


def test_more_studies_than_authors_is_a_bad_argument(tmp_path, capsys):
    assert main(["build", "--out", str(tmp_path / "g"), "--studies", "25", "--seeds", "1"]) == 2
    assert "authors" in capsys.readouterr().err
    assert not (tmp_path / "g").exists()
