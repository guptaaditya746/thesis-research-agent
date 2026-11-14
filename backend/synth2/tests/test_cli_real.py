import json

import pytest

from synth2.cli import main
from synth2.tests.test_realedit import GOOD, CELL, make_truth
from synth2.tests.test_realpool import long_body, row


def test_realpool_split_cut_and_slice(tmp_path, capsys):
    content = "# T\n\n## 1 Introduction\n\n" + long_body() + "\n\n## References\n\nx"
    rows = tmp_path / "rows.jsonl"
    rows.write_text("\n".join(json.dumps(r) for r in [
        row("t1", "RAG retrieval study", content=content), row("s1", "Dense retrieval", content=content)]),
        encoding="utf-8")
    old = tmp_path / "old.json"
    old.write_text(json.dumps({"style": [], "eval": []}), encoding="utf-8")
    split = tmp_path / "split.json"
    assert main(["realpool-split", "--rows", str(rows), "--old-split", str(old), "--out", str(split)]) == 0
    assert json.loads(split.read_text(encoding="utf-8"))["test"] == ["t1"]
    assert "'test': 1" in capsys.readouterr().out
    out = tmp_path / "cut"
    assert main(["realpool-cut", "--rows", str(rows), "--split", str(split), "--side", "test", "--out", str(out)]) == 0
    assert (out / "full" / "t1.md").is_file() and (out / "pieces" / "index.json").is_file()
    assert "pieces from 1 papers" in capsys.readouterr().out
    assert main(["realpool-cut", "--rows", str(rows), "--split", str(split), "--side", "sources",
                 "--out", str(tmp_path / "src")]) == 0
    assert (tmp_path / "src" / "full" / "s1.md").is_file()
    papers = tmp_path / "papers"
    papers.mkdir()
    (papers / "S001.md").write_text(f"# Our Title\n\nLee et al. (2021)\n\n## Abstract\n\nShort.\n\n## 1 Methods\n\n{long_body()}\n",
                                    encoding="utf-8")
    assert main(["slice", "--papers", str(papers), "--out", str(tmp_path / "sl")]) == 0
    assert (tmp_path / "sl" / "S001_p1.md").is_file()


def test_realedit_prepare_apply_check(tmp_path, edit_base, capsys):  # noqa: ARG001
    base = tmp_path / "cli-base"     # the fixture's own folders hold the study input and its source
    assert main(["realedit-prepare", "--inputs", str(tmp_path / "v10"), "--out", str(base)]) == 0
    assert "S001 source" in capsys.readouterr().out
    assert (base / "maps" / "S001.json").is_file()
    edits = {"title": "New Title", "insert_after": [{"anchor": "## Results", "text": GOOD.split("\n\n", 2)[2]}]}
    (base / "edits" / "S001.json").write_text(json.dumps(edits), encoding="utf-8")
    assert main(["realedit-apply", "--base", str(base)]) == 0
    assert "OK" in capsys.readouterr().out
    reader = make_truth(tmp_path / "grid", [CELL])
    assert main(["realedit-check", "--grid", str(tmp_path / "grid"), "--base", str(base),
                 "--readers", str(reader)]) == 0
    assert "kept 1 of 1" in capsys.readouterr().out


def test_realedit_apply_exits_1_when_a_check_fails(edit_base, capsys):
    (edit_base / "edits" / "S001.json").write_text(
        json.dumps({"title": "T", "insert_after": [{"anchor": "gone", "text": "x"}]}), encoding="utf-8")
    assert main(["realedit-apply", "--base", str(edit_base), "--study", "S001"]) == 1
    assert "FIX" in capsys.readouterr().out


def test_realism_prints_the_five_aucs(tmp_path, capsys):
    pytest.importorskip("sklearn")
    from synth2.tests.test_realism import paper, REAL_WORDS, SYN_WORDS
    import random
    rnd = random.Random(1)
    real, syn = tmp_path / "real", tmp_path / "syn" / "papers"
    real.mkdir()
    syn.mkdir(parents=True)
    for i in range(8):
        (real / f"{i:03d}_p1.md").write_text(paper(rnd, REAL_WORDS, f"R{i}"), encoding="utf-8")
        (syn / f"S{i:03d}.md").write_text(paper(rnd, SYN_WORDS, f"S{i}"), encoding="utf-8")
    out = tmp_path / "diag.json"
    assert main(["realism", "--real", str(real), "--synthetic", str(tmp_path / "syn"), "--out", str(out),
                 f"--gap=same={real}"]) == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    assert len(result["auc"]) == 5 and result["style gap"]["same"]["mean |gap|"] == 0.0
    assert "5 masked + surface" in capsys.readouterr().out


def test_real_commands_report_bad_arguments(tmp_path, capsys):
    missing = str(tmp_path / "nope")
    assert main(["realpool-split", "--rows", missing, "--old-split", missing, "--out", missing]) == 2
    assert main(["realpool-cut", "--rows", missing, "--split", missing, "--side", "middle", "--out", missing]) == 2
    assert main(["slice", "--papers", missing, "--out", str(tmp_path / "o")]) == 0     # nothing to slice
    assert main(["realedit-prepare", "--inputs", missing, "--out", str(tmp_path / "b")]) == 0
    assert main(["realedit-apply", "--base", str(tmp_path / "b")]) == 2               # no inputs
    assert main(["realedit-check", "--grid", missing, "--base", missing]) == 2
    assert main(["realism", "--real", missing, "--synthetic", missing, "--gap", "noequals"]) == 2
    err = capsys.readouterr().err
    assert err.count("synth2:") == 5 and "NAME=ROOT" in err
