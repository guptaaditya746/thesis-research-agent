"""Template corpora on disk: byte-identical rebuilds, exact placements, the interface files, the variants."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.anchor import read_text
from evidence import rules
from synth import corpus
from synth.levels import LEVELS
from synth.render_template import TemplateRenderer

ALL = (*LEVELS, "mixed")


def build(out: Path, seed: int = 5, studies: int = 10, **kw) -> dict:
    return corpus.build(name="t", seed=seed, studies=studies, renderer=TemplateRenderer(), out=out, **kw)


def files(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def load(directory: Path, name: str) -> dict:
    return json.loads((directory / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("corpora")
    build(out)
    return out


def test_same_seed_identical_bytes(built: Path, tmp_path: Path) -> None:
    build(tmp_path)
    assert files(tmp_path) == files(built)
    build(tmp_path / "other", seed=6)
    assert files(tmp_path / "other")["t-explicit/papers/S001.md"] != files(built)["t-explicit/papers/S001.md"]


def test_one_corpus_per_level_plus_mixed_same_paper_ids(built: Path) -> None:
    assert sorted(p.name for p in built.iterdir()) == sorted(f"t-{lv}" for lv in ALL)
    ids = {lv: [p["id"] for p in load(built / f"t-{lv}", "manifest.json")["papers"]] for lv in ALL}
    assert all(v == [f"S{i:03d}" for i in range(1, 11)] for v in ids.values())


def test_manifest_has_only_allowed_keys_and_true_hashes(built: Path) -> None:
    import hashlib
    for lv in ALL:
        d = built / f"t-{lv}"
        m = load(d, "manifest.json")
        assert set(m) == {"corpus_id", "papers"}
        assert lv not in m["corpus_id"] and m["corpus_id"].startswith("t-")
        for p in m["papers"]:
            assert set(p) == {"id", "file", "sha256"}
            assert hashlib.sha256((d / p["file"]).read_bytes()).hexdigest() == p["sha256"]
        assert load(d, "ground_truth.json")["corpus_id"] == m["corpus_id"] == load(d, "corpus.json")["corpus_id"]


def test_every_placement_holds_on_the_stored_file(built: Path) -> None:
    for lv in ALL:
        d = built / f"t-{lv}"
        gt = load(d, "ground_truth.json")
        texts = {p["id"]: read_text(d / p["file"]) for p in load(d, "manifest.json")["papers"]}
        facts = {s["paper"]: {f["id"] for k in ("conditions", "metrics", "measurements") for f in s[k]}
                 | {s["author_claim"]["id"]} for s in gt["studies"]}
        assert gt["placements"]
        for p in gt["placements"]:
            assert set(p) == {"fact", "role", "paper", "start", "end", "exact"}
            assert texts[p["paper"]][p["start"]:p["end"]] == p["exact"]
            assert p["fact"] in facts[p["paper"]]
        for text in texts.values():
            assert "\r" not in text and text.endswith("\n")


def test_effects_and_answer_follow_rules(built: Path) -> None:
    for lv in ALL:
        gt = load(built / f"t-{lv}", "ground_truth.json")
        counts = {"supports": [], "contradicts": [], "neutral": []}
        for s in gt["studies"]:
            ms = {m["id"]: m for m in s["measurements"]}
            metric = next(k for k in s["metrics"] if k["id"] == s["effect"]["metric"])
            assert metric is s["metrics"][0] and metric["canonical"] in rules.METRICS
            roles = {c["id"]: c["role"] for c in s["conditions"]}
            rag, base = ms[s["effect"]["rag"]], ms[s["effect"]["baseline"]]
            assert (roles[rag["condition"]], roles[base["condition"]]) == ("rag", "baseline")
            assert rag["dataset"] == base["dataset"] and rag["metric"] == base["metric"] == metric["id"]
            direction, delta = rules.effect(rag["value"], base["value"], metric["higher_is_better"])
            assert (s["effect"]["direction"], s["effect"]["delta"]) == (direction, delta)
            counts[direction].append(s["paper"])
        assert gt["answer"] == {"label": rules.label(*(len(v) for v in counts.values())),
                                "supporting": counts["supports"], "contradicting": counts["contradicts"],
                                "neutral": counts["neutral"]}


def test_answer_is_the_same_in_every_variant(built: Path) -> None:
    answers = {json.dumps(load(built / f"t-{lv}", "ground_truth.json")["answer"]) for lv in ALL}
    assert len(answers) == 1


def test_mixed_papers_equal_their_level_papers(built: Path) -> None:
    mixed = load(built / "t-mixed", "corpus.json")
    assert [p["level"] for p in mixed["papers"]] == [LEVELS[i % len(LEVELS)] for i in range(10)]
    for p in mixed["papers"]:
        assert (built / "t-mixed/papers" / f"{p['id']}.md").read_bytes() == \
               (built / f"t-{p['level']}/papers/{p['id']}.md").read_bytes()


def test_corpus_json_and_fidelity_json(built: Path) -> None:
    for lv in ALL:
        d = built / f"t-{lv}"
        c = load(d, "corpus.json")
        assert c["level"] == lv and c["renderer"] == "template" and c["models"] is None and c["seed"] == 5
        assert c["generator"] == {"name": "synth", "version": corpus.GENERATOR_VERSION,
                                  "code_sha256": corpus.code_sha256()}
        f = load(d, "fidelity.json")
        assert f["excluded"] == [] and all(p["ok"] and p["attempts"] == 1 for p in f["papers"])
        assert {c["name"] for c in f["papers"][0]["checks"]} >= {"anchored", "values_match", "stray_numbers"}


def test_levels_subset_and_effect_mix(tmp_path: Path) -> None:
    out = build(tmp_path, studies=4, levels=["distributed", "explicit"], mix={"neutral": 1})
    assert sorted(p.name for p in tmp_path.iterdir()) == ["t-distributed", "t-explicit", "t-mixed"]
    assert out["answer"]["label"] == "no_effect"
    mixed = load(tmp_path / "t-mixed", "corpus.json")
    assert [p["level"] for p in mixed["papers"]] == ["distributed", "explicit"] * 2


def test_refuses_to_overwrite_a_foreign_directory(tmp_path: Path) -> None:
    (tmp_path / "t-explicit").mkdir()
    (tmp_path / "t-explicit" / "notes.txt").write_text("mine")
    with pytest.raises(SystemExit):
        build(tmp_path, studies=2, levels=["explicit"])


def test_corpus_id_is_a_hash_of_the_papers_not_of_the_level(built: Path) -> None:
    """Review item 7: an id hashed from (name, level, seed, renderer) gave the level away by brute force."""
    from agent.canonical import canonical_bytes, sha256_hex
    ids = set()
    for lv in ALL:
        m = load(built / f"t-{lv}", "manifest.json")
        digest = sha256_hex(canonical_bytes([[p["id"], p["sha256"]] for p in m["papers"]]))[:8]
        assert m["corpus_id"] == f"t-{digest}"
        guesses = {sha256_hex(canonical_bytes(["t", level, seed, r]))[:8]
                   for level in ALL for seed in range(10) for r in ("template", "llm")}
        assert digest not in guesses
        ids.add(m["corpus_id"])
    assert len(ids) == len(ALL)