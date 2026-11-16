import json
from dataclasses import replace

import pytest

from synth3.cli import main
from synth3.corpus import build_folder
from synth3.world import draw_world


def approved(SPEC, seed):
    return replace(draw_world(SPEC, seed), approved=True)


def test_unapproved_world_is_refused(tmp_path, SPEC):
    with pytest.raises(ValueError, match="approved"):
        build_folder(tmp_path / "f", SPEC, draw_world(SPEC, 1), 40, "table")


def test_same_world_builds_byte_identical_folders(tmp_path, SPEC):
    build_folder(tmp_path / "a", SPEC, approved(SPEC, 1), 40, "table")
    build_folder(tmp_path / "b", SPEC, approved(SPEC, 1), 40, "table")
    files = sorted(p.relative_to(tmp_path / "a") for p in (tmp_path / "a").rglob("*") if p.is_file())
    assert files and all((tmp_path / "a" / f).read_bytes() == (tmp_path / "b" / f).read_bytes() for f in files)


def test_truth_is_beside_the_papers(tmp_path, SPEC):
    out = tmp_path / "f"; build_folder(out, SPEC, approved(SPEC, 2), 40, "prose")
    manifest = json.loads((out / "manifest.json").read_text())
    assert {p["file"] for p in manifest["papers"]} == {f"papers/{p.name}" for p in (out / "papers").glob("*.md")}
    assert set(json.loads((out / "ground_truth.json").read_text())) == \
           {"corpus_id", "world", "spec", "studies", "placements", "facts"}


def test_draw_then_build_by_command(tmp_path, spec_dir, capsys):
    common = ["--domain", "demo", "--spec-root", str(spec_dir), "--seeds", "1,2", "--worlds", str(tmp_path / "w")]
    assert main(["draw", *common]) == 0
    for s in (1, 2):
        f = tmp_path / "w" / "demo" / f"s{s}.json"; d = json.loads(f.read_text()); d["approved"] = True
        f.write_text(json.dumps(d))
    assert main(["build", *common, "--out", str(tmp_path / "o")]) == 0
    assert (tmp_path / "o" / "s2" / "ground_truth.json").is_file()
    assert main(["draw", *common]) != 0   # refuses to overwrite approved worlds


def test_build_refuses_an_unapproved_world_by_name(tmp_path, spec_dir, capsys):
    common = ["--domain", "demo", "--spec-root", str(spec_dir), "--seeds", "1", "--worlds", str(tmp_path / "w")]
    assert main(["draw", *common]) == 0
    capsys.readouterr()
    assert main(["build", *common, "--out", str(tmp_path / "o")]) != 0
    assert "s1.json" in capsys.readouterr().err
