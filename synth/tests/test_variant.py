"""Counterfactual variants (docs/evidence-system.md F3): unchanged papers identical, the changed paper's
effect flips, `expected.label_changes`, a protocol mismatch refused. Template renderer, except the check that
an LLM base corpus is varied with the statement mode it records (scripted writer)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evidence import protocol, rules
from synth import cli, corpus, truth, variant
from synth.render_template import TemplateRenderer

PROTO = protocol.load(truth.DEFAULT_PROTOCOL)
SPEC = PROTO.synthesis


def load(directory: Path, name: str) -> dict:
    return json.loads((directory / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def base(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("corpora")
    corpus.build(name="v", seed=5, studies=6, renderer=TemplateRenderer(), out=out, mix={"supports": 1},
                 duplicates=1, irrelevant=1, missing=1)
    return out / "v-mixed"


def test_variant_changes_one_paper_and_the_expected_answer(base: Path) -> None:
    gt = load(base, "ground_truth.json")
    study = gt["answer"]["supporting"][0]
    res = variant.make(corpus_dir=base, study_id=study, direction="contradicts", renderer=TemplateRenderer())
    out = Path(res["out"])
    assert out == base.parent / f"v-mixed-cf-{study}-contradicts"
    manifest, new_manifest = load(base, "manifest.json"), load(out, "manifest.json")
    assert [p["id"] for p in new_manifest["papers"]] == [p["id"] for p in manifest["papers"]]
    for p, q in zip(manifest["papers"], new_manifest["papers"]):
        same = (base / p["file"]).read_bytes() == (out / q["file"]).read_bytes()
        assert same == (p["id"] != study) and q["sha256"] == hashlib.sha256((out / q["file"]).read_bytes()).hexdigest()
    vj = load(out, "variant.json")
    assert vj == {k: v for k, v in res.items() if k != "out"}
    assert (vj["base_corpus_id"], vj["corpus_id"], vj["study"], vj["paper"]) == (gt["corpus_id"], new_manifest["corpus_id"], study, study)
    assert vj["corpus_id"] != gt["corpus_id"] and vj["corpus_id"].startswith("v-cf-")
    assert (vj["from"], vj["to"]) == ("supports", "contradicts")
    assert len(vj["changed"]) == 4 and all(c["from"] != c["to"] for c in vj["changed"])
    # the changed study: new effect from rules.effect on the new values, other values kept
    new_gt = load(out, "ground_truth.json")
    before = next(s for s in gt["studies"] if s["study_id"] == study)
    after = next(s for s in new_gt["studies"] if s["study_id"] == study)
    ms = {m["id"]: m for m in after["measurements"]}
    assert after["effect"]["direction"] == "contradicts" and after["effect"]["delta"] < 0
    assert (after["effect"]["treatment"], after["effect"]["control"]) == (before["effect"]["treatment"], before["effect"]["control"])
    t, c = ms[after["effect"]["treatment"]], ms[after["effect"]["control"]]
    assert rules.effect(t["value"], c["value"], after["metrics"][0]["higher_is_better"], SPEC.min_effect)[0] == "contradicts"
    changed = {c["measurement"] for c in vj["changed"]}
    for m in before["measurements"]:
        assert (ms[m["id"]]["value"] == m["value"]) == (m["id"] not in changed)
    assert after["conditions"] == before["conditions"] and after["metrics"] == before["metrics"] and after["level"] == before["level"]
    assert after["author_claim"]["direction"] == (truth.FALSE_CLAIM["contradicts"] if after["level"] == "contradictory"
                                                  else truth.true_claim(SPEC, "contradicts"))
    # every other study record is the base's, flags re-applied (unchanged here)
    for s in new_gt["studies"]:
        if s["study_id"] != study:
            assert s == next(b for b in gt["studies"] if b["study_id"] == s["study_id"])
    assert [p for p in new_gt["placements"] if p["paper"] != study] == [p for p in gt["placements"] if p["paper"] != study]
    text = (out / f"papers/{study}.md").read_text(encoding="utf-8")
    for p in (p for p in new_gt["placements"] if p["paper"] == study):
        assert text[p["start"]:p["end"]] == p["exact"]
    # expected answer before and after
    assert vj["expected"]["before"] == {"label": "supported", "counts": truth.answer_counts(gt["answer"])} == {
        "label": "supported", "counts": {"supporting": 5, "contradicting": 0, "neutral": 0, "undetermined": 2, "duplicates": 1}}
    assert vj["expected"]["after"] == {"label": "mixed", "counts": truth.answer_counts(new_gt["answer"])} == {
        "label": "mixed", "counts": {"supporting": 4, "contradicting": 1, "neutral": 0, "undetermined": 2, "duplicates": 1}}
    assert vj["expected"]["label_changes"] is True
    assert new_gt["answer"]["contradicting"] == [study] and study not in new_gt["answer"]["supporting"]
    assert new_gt["answer"]["undetermined"] == gt["answer"]["undetermined"] and new_gt["answer"]["duplicates"] == gt["answer"]["duplicates"]
    meta = load(out, "corpus.json")
    assert meta["variant"] == {"base_corpus_id": gt["corpus_id"], "study": study, "from": "supports", "to": "contradicts"}
    assert meta["corpus_id"] == new_manifest["corpus_id"] == new_gt["corpus_id"] and meta["settings"] == load(base, "corpus.json")["settings"]
    fid = load(out, "fidelity.json")
    assert fid["excluded"] == [] and all(p["ok"] for p in fid["papers"]) and [p["id"] for p in fid["papers"]] == [p["id"] for p in manifest["papers"]]


def test_variant_to_neutral_keeps_the_label(base: Path) -> None:
    gt = load(base, "ground_truth.json")
    study = gt["answer"]["supporting"][1]
    res = variant.make(corpus_dir=base, study_id=study, direction="neutral", renderer=TemplateRenderer(),
                       out=base.parent / "neutral")
    assert res["expected"]["label_changes"] is False and res["expected"]["after"]["label"] == "supported"
    assert load(base.parent / "neutral", "ground_truth.json")["answer"]["neutral"] == [study]


def test_variant_of_a_duplicated_original_frees_the_duplicate(base: Path) -> None:
    gt = load(base, "ground_truth.json")
    dup = next(s for s in gt["studies"] if s["duplicate_of"])
    res = variant.make(corpus_dir=base, study_id=dup["duplicate_of"], direction="contradicts", renderer=TemplateRenderer(),
                       out=base.parent / "freed")
    new_gt = load(base.parent / "freed", "ground_truth.json")
    freed = next(s for s in new_gt["studies"] if s["study_id"] == dup["study_id"])
    assert freed["duplicate_of"] is None and "duplicate" not in freed["flags"]
    assert new_gt["answer"]["duplicates"] == [] and dup["study_id"] in new_gt["answer"]["supporting"]
    assert res["expected"]["after"]["counts"]["duplicates"] == 0


def test_variant_refusals(base: Path, tmp_path: Path) -> None:
    gt = load(base, "ground_truth.json")
    study = gt["answer"]["supporting"][0]
    with pytest.raises(SystemExit, match="already has the effect"):
        variant.make(corpus_dir=base, study_id=study, direction="supports", renderer=TemplateRenderer(), out=tmp_path / "a")
    for sid, why in ((gt["answer"]["duplicates"][0], "duplicate"), ("S008", "no experiment"),
                     (next(s["study_id"] for s in gt["studies"] if s["missing"]), "lacks its")):
        with pytest.raises(SystemExit, match=why):
            variant.make(corpus_dir=base, study_id=sid, direction="contradicts", renderer=TemplateRenderer(), out=tmp_path / "b")
    with pytest.raises(SystemExit, match="not a paper"):
        variant.make(corpus_dir=base, study_id="S099", direction="contradicts", renderer=TemplateRenderer(), out=tmp_path / "c")
    with pytest.raises(SystemExit, match="choose from"):
        variant.make(corpus_dir=base, study_id=study, direction="sideways", renderer=TemplateRenderer(), out=tmp_path / "d")
    other = PROTO.model_copy(update={"synthesis": SPEC.model_copy(update={"min_effect": 0.02})})
    with pytest.raises(SystemExit, match="not the one the base corpus was built from"):
        variant.make(corpus_dir=base, study_id=study, direction="contradicts", renderer=TemplateRenderer(),
                     out=tmp_path / "e", protocol=other)
    assert not (tmp_path / "e").exists()
    with pytest.raises(SystemExit, match="not a synth corpus"):
        variant.make(corpus_dir=tmp_path, study_id=study, direction="contradicts", renderer=TemplateRenderer())


def test_variant_cli_defaults_to_the_base_renderer(base: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    study = load(base, "ground_truth.json")["answer"]["supporting"][2]
    assert cli.main(["variant", "--corpus", str(base), "--study", study, "--direction", "contradicts",
                     "--out", str(tmp_path / "cf")]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["out"] == str(tmp_path / "cf") and printed["to"] == "contradicts"
    assert load(tmp_path / "cf", "corpus.json")["renderer"] == "template"
    with pytest.raises(SystemExit):
        cli.main(["variant", "--corpus", str(base), "--study", study, "--direction", "up"])


@pytest.mark.parametrize("recorded, statements", [({"statements": False, "paper_prompt": "render.txt"}, False),
                                                   ({}, False),          # a corpus from before the statement stage
                                                   ({"statements": True, "paper_prompt": "render-v2.txt"}, True)])
def test_variant_cli_keeps_the_base_statement_mode(base: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                   recorded: dict, statements: bool) -> None:
    """An LLM base corpus is varied with the pipeline it records; one that records none had no statement stage."""
    import shutil

    import modelcall
    from pydantic_ai.models.function import FunctionModel
    from synth.tests.test_llm import Writer

    src = base.parent / "v-explicit"
    copy = tmp_path / "v-explicit"
    shutil.copytree(src, copy)
    meta = load(copy, "corpus.json")
    meta |= {"renderer": "llm", "models": {"renderer": "fake-writer", "verifier": None, "served": [], **recorded}}
    (copy / "corpus.json").write_text(json.dumps(meta), encoding="utf-8")
    study = load(copy, "ground_truth.json")["answer"]["supporting"][0]
    _, _, after = variant.counterfactual(meta["seed"], variant.base_studies(meta, PROTO), study, "contradicts", SPEC)
    writer = Writer([after], fail_first=False)
    monkeypatch.setattr(modelcall, "openai_model", lambda alias: FunctionModel(writer, model_name="fake-writer"))
    assert cli.main(["variant", "--corpus", str(copy), "--study", study, "--direction", "contradicts",
                     "--out", str(tmp_path / "cf"), "--cache", str(tmp_path / "cache.jsonl")]) == 0
    models = load(tmp_path / "cf", "corpus.json")["models"]
    assert (models["statements"], models["paper_prompt"]) == (statements, "render-v2.txt" if statements else "render.txt")
    asked = [c.startswith("Statement tasks") for c in writer.calls]
    assert asked == ([True, False] if statements else [False])
    rec = next(r for r in load(tmp_path / "cf", "fidelity.json")["papers"] if r["id"] == study)
    assert ("statements" in rec) == statements


def test_variant_keeps_the_base_selection(base: Path) -> None:
    study = load(base, "ground_truth.json")["answer"]["supporting"][0]
    out = Path(variant.make(corpus_dir=base, study_id=study, direction="neutral", renderer=TemplateRenderer())["out"])
    assert load(out, "corpus.json")["selection"] == load(base, "corpus.json")["selection"]
    assert "selection" not in load(out, "manifest.json")
