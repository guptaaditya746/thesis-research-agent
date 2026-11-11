import json
import pytest
from jsonio import file_sha256
from synth2.conclude import Answer, pooled
from synth2.corpus import Settings, build_base, load_studies, load_truth
from synth2.recipe import load_recipe

S = Settings(domain="rag", seed=11, studies=20, law_kind="opposed", text_level="table")


def test_build_writes_the_four_parts(tmp_path):
    cid = build_base(tmp_path / "base", S)
    out = tmp_path / "base"
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["corpus_id"] == cid and cid.startswith("rag2-") and len(manifest["papers"]) == 20
    for p in manifest["papers"]:
        assert file_sha256(out / p["file"]) == p["sha256"]
        assert b"\r" not in (out / p["file"]).read_bytes()
    truth = load_truth(out)
    assert Answer.parse(truth["key"]) == pooled(load_studies(out), load_recipe("rag"))
    assert Settings.parse(json.loads((out / "corpus.json").read_text(encoding="utf-8"))["settings"]) == S


def test_same_settings_same_corpus_id(tmp_path):
    assert build_base(tmp_path / "a", S) == build_base(tmp_path / "b", S)


def test_id_does_not_leak_the_settings(tmp_path):
    cid = build_base(tmp_path / "a", S)
    assert "opposed" not in cid and "table" not in cid and "11" not in cid.split("-")[0]


def test_exact_corpora_recover_the_planted_law(tmp_path):
    for seed in range(10):
        for kind in ("uniform", "one_sided", "opposed"):
            out = tmp_path / f"{kind}-{seed}"
            build_base(out, Settings("rag", seed, 20, kind, "table", exact=True))
            assert load_truth(out)["key_matches_law"] is True, (kind, seed)


def test_refuses_a_folder_that_is_not_empty(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "keep.txt").write_text("mine", encoding="utf-8")
    with pytest.raises(SystemExit):
        build_base(tmp_path / "x", S)
    assert (tmp_path / "x" / "keep.txt").read_text(encoding="utf-8") == "mine"
