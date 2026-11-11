import json
from synth2.cli import main


def test_build_reference_score_end_to_end(tmp_path, capsys):
    root = tmp_path / "grid"
    assert main(["build", "--out", str(root), "--seeds", "2", "--laws", "opposed,uniform", "--texts", "table,split"]) == 0
    assert sorted(p.name for p in root.iterdir() if p.is_dir()) == ["opposed-split", "opposed-table", "uniform-split", "uniform-table"]
    built = sum(1 for _ in root.glob("*/s*/base/manifest.json"))
    skipped = json.loads((root / "skipped.json").read_text(encoding="utf-8"))
    assert built == 8 and isinstance(skipped, list)
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


def test_a_folder_without_families_is_a_bad_argument(tmp_path, capsys):
    (tmp_path / "x" / "stuff" / "base").mkdir(parents=True)
    (tmp_path / "x" / "stuff" / "base" / "manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "answers.json").write_text("{}", encoding="utf-8")
    out = str(tmp_path / "out.json")
    assert main(["reference", "--root", str(tmp_path), "--rule", "pooled", "--out", out]) == 2
    assert main(["score", "--root", str(tmp_path), "--answers", str(tmp_path / "answers.json"), "--out", out]) == 2
    assert main(["export-scir", "--root", str(tmp_path / "x"), "--out", out]) == 2
    assert capsys.readouterr().err.count("no ") == 3
    assert not (tmp_path / "out.json").exists()


def test_build_fills_every_cell_and_every_key_equals_its_law(tmp_path):
    root = tmp_path / "grid"
    assert main(["build", "--out", str(root), "--seeds", "10", "--laws", "one_sided", "--texts", "table"]) == 0
    truths = [json.loads(p.read_text(encoding="utf-8")) for p in root.glob("one_sided-table/s*/*/ground_truth.json")]
    assert len(truths) == 50 and all(t["key_matches_law"] for t in truths)
    skipped = json.loads((root / "skipped.json").read_text(encoding="utf-8"))
    built = {int(p.name[1:]) for p in (root / "one_sided-table").iterdir()}
    assert len(built) == 10 and not built & {s["seed"] for s in skipped}


def test_build_gives_up_after_three_times_the_seeds(tmp_path, monkeypatch, capsys):
    import synth2.cli as cli

    def refuse(base_dir):
        raise ValueError("never")
    monkeypatch.setattr(cli, "make_family", refuse)
    root = tmp_path / "grid"
    assert main(["build", "--out", str(root), "--seeds", "2", "--laws", "opposed", "--texts", "table"]) == 1
    assert len(json.loads((root / "skipped.json").read_text(encoding="utf-8"))) == 6
    assert "opposed-table" in capsys.readouterr().err
