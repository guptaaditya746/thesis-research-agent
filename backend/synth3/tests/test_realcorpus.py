import json

import pytest

from synth3 import realcorpus
from synth3.cli import main
from synth3.corpus import build_folder
from synth3.pool import load_split, split_pool
from synth3.realcorpus import build_real_folder
from synth3.realwrite import edit_study
from synth3.tests.conftest import approved, make_pool


def test_real_truth_is_the_template_truth(tmp_path, SPEC, REAL, pool):
    build_folder(tmp_path / "t", SPEC, approved(SPEC, 1), 40, "table")
    build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 1), 40, "table", REAL, pool)
    t, r = (json.loads((tmp_path / x / "ground_truth.json").read_text()) for x in ("t", "r"))
    assert set(r) == set(t) | {"real"}
    assert all(r[k] == t[k] for k in ("world", "spec", "studies", "facts"))
    assert {(p["paper"], p["fact"]) for p in r["placements"]} == {(p["paper"], p["fact"]) for p in t["placements"]}


def test_every_placement_points_at_its_planted_text(tmp_path, SPEC, REAL, pool):
    build_folder(tmp_path / "t", SPEC, approved(SPEC, 2), 40, "table")
    build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 2), 40, "table", REAL, pool)
    def spans(d):
        g = json.loads((d / "ground_truth.json").read_text())
        text = {p.stem: p.read_text(encoding="utf-8") for p in (d / "papers").glob("S*.md")}
        return {(p["paper"], p["fact"]): text[p["paper"]][p["start"]:p["end"]] for p in g["placements"]}
    assert spans(tmp_path / "r") == spans(tmp_path / "t")


def test_sources_unique_in_a_folder_and_never_test_papers(tmp_path, SPEC, REAL, pool):
    build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 1), 40, "table", REAL, pool)
    used = list(json.loads((tmp_path / "r" / "ground_truth.json").read_text())["real"]["sources"].values())
    assert len(used) == len(set(used)) == 40 and not set(used) & set(load_split(pool)["test"])


def test_same_world_same_bytes(tmp_path, SPEC, REAL, pool):
    for x in ("a", "b"):
        build_real_folder(tmp_path / x, SPEC, approved(SPEC, 3), 40, "table", REAL, pool)
    files = sorted(p.relative_to(tmp_path / "a") for p in (tmp_path / "a").rglob("*") if p.is_file())
    assert files and all((tmp_path / "a" / f).read_bytes() == (tmp_path / "b" / f).read_bytes() for f in files)


def test_pool_without_split_or_too_small_is_refused(tmp_path, SPEC, REAL):
    bare = make_pool(tmp_path / "bare", 50, REAL)
    with pytest.raises(ValueError, match="pool-split"):
        build_real_folder(tmp_path / "r1", SPEC, approved(SPEC, 1), 40, "table", REAL, bare)
    small = make_pool(tmp_path / "small", 30, REAL); split_pool(small, REAL)
    with pytest.raises(ValueError, match="needs at least 40"):
        build_real_folder(tmp_path / "r2", SPEC, approved(SPEC, 1), 40, "table", REAL, small)


def test_build_real_by_command(tmp_path, spec_dir, real_dir, pool_root):
    common = ["--domain", "demo", "--spec-root", str(spec_dir), "--seeds", "1", "--worlds", str(tmp_path / "w")]
    assert main(["draw", *common]) == 0
    f = tmp_path / "w" / "demo" / "s1.json"; d = json.loads(f.read_text()); d["approved"] = True
    f.write_text(json.dumps(d))
    assert main(["build-real", *common, "--real-root", str(real_dir), "--pools", str(pool_root),
                 "--out", str(tmp_path / "o")]) == 0
    assert (tmp_path / "o" / "s1" / "real" / "maps").is_dir()


def test_build_real_checks_the_pool_before_writing(tmp_path, spec_dir, real_dir, capsys):
    common = ["--domain", "demo", "--spec-root", str(spec_dir), "--seeds", "1", "--worlds", str(tmp_path / "w")]
    assert main(["draw", *common]) == 0
    capsys.readouterr()
    assert main(["build-real", *common, "--real-root", str(real_dir), "--pools", str(tmp_path / "none"),
                 "--out", str(tmp_path / "o")]) == 2
    err = capsys.readouterr().err
    assert "pool-split" in err and "not approved" in err and not (tmp_path / "o").exists()


# ---- a rejected source is replaced from the rest of the order, at most 3 sources per study ----------------------

def _reject(monkeypatch, bad):
    """`edit_study` that reports a problem for every source id in `bad` (the id is the seed's last part)."""
    def fake(source, study, spec, rs, text_level, seed):
        rp = edit_study(source, study, spec, rs, text_level, seed)
        if seed.rsplit(":", 1)[1] in bad:
            return type(rp)(rp.paper, rp.mapping, rp.inserted, ("made up problem",), rp.seed)
        return rp
    monkeypatch.setattr(realcorpus, "edit_study", fake)


def test_a_rejected_source_is_replaced_and_recorded(tmp_path, SPEC, REAL, pool, monkeypatch):
    clean = tmp_path / "clean"
    build_real_folder(clean, SPEC, approved(SPEC, 1), 40, "table", REAL, pool)
    first = json.loads((clean / "ground_truth.json").read_text())["real"]["sources"]
    sid, bad = next(iter(first.items()))
    _reject(monkeypatch, {bad})
    build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 1), 40, "table", REAL, pool)
    real = json.loads((tmp_path / "r" / "ground_truth.json").read_text())["real"]
    assert real["rejected"] == {sid: [{"source": bad, "problem": "made up problem"}]}
    used = list(real["sources"].values())
    assert bad not in used and len(set(used)) == 40


def test_a_study_with_three_rejected_sources_stops_the_build(tmp_path, SPEC, REAL, pool, monkeypatch):
    _reject(monkeypatch, set(load_split(pool)["sources"]))
    with pytest.raises(ValueError, match=r"S\w+: no clean source in 3 tries") as err:
        build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 1), 40, "table", REAL, pool)
    assert str(err.value).count("made up problem") == 3
    assert not (tmp_path / "r").exists() or not any((tmp_path / "r").iterdir())
