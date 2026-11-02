"""The benchmark knobs (docs/evidence-system.md F2): counts, ids, flags, answer lists, the plain build
unchanged, the generator's self-check. Template renderer only."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from evidence import protocol, rules
from synth import corpus, truth
from synth.levels import LEVELS
from synth.recipe import default_recipe
from synth.render_template import TemplateRenderer, render_study

PROTO = protocol.load(truth.DEFAULT_PROTOCOL)
SPEC = PROTO.synthesis
SCREEN_TERMS = [t.lower() for t in PROTO.screen.terms]


def load(directory: Path, name: str) -> dict:
    return json.loads((directory / name).read_text(encoding="utf-8"))


def build(out: Path, **kw) -> dict:
    return corpus.build(name="k", seed=5, studies=8, renderer=TemplateRenderer(), out=out, **kw)


def test_plain_set_has_the_defaults_and_is_not_changed_by_the_knob_code() -> None:
    plain = truth.generate(5, 10)
    assert [s.study_id for s in plain] == [f"S{i:03d}" for i in range(1, 11)]
    assert all(s.relevant and s.missing is None and s.duplicate_of is None and s.topic is None for s in plain)
    assert all("duplicate" not in s.flags for s in plain)
    assert truth.answer(plain)["undetermined"] == [] and truth.answer(plain)["duplicates"] == []
    # duplicates and irrelevant papers are appended; the drawn studies keep their values
    more = truth.generate(5, 10, duplicates=2, irrelevant=1)
    assert [s.measurements for s in more[:10]] == [s.measurements for s in plain]
    assert [s.study_id for s in more[10:]] == ["S011", "S012", "S013"]


def test_knobs_use_their_own_streams() -> None:
    """Each knob's draw is independent of the others, so adding one does not reshuffle another."""
    a = truth.generate(5, 10, duplicates=2)
    b = truth.generate(5, 10, duplicates=2, irrelevant=3, missing=1)
    assert [s.duplicate_of for s in a[10:12]] == [s.duplicate_of for s in b[10:12]]


def test_duplicates() -> None:
    studies = truth.generate(5, 10, duplicates=3)
    assert len(studies) == 13
    dups = [s for s in studies if s.duplicate_of]
    assert [s.study_id for s in dups] == ["S011", "S012", "S013"]
    assert len({d.duplicate_of for d in dups}) == 3
    for d in dups:
        o = next(s for s in studies if s.study_id == d.duplicate_of)
        assert d.flags == ("duplicate",) and o.index < 10 and o.duplicate_of is None
        assert [m.value for m in d.measurements] == [m.value for m in o.measurements]
        assert [(c.label, c.role) for c in d.conditions] == [(c.label, c.role) for c in o.conditions]
        assert d.datasets == o.datasets and d.claim == o.claim and d.decoy == o.decoy
        assert all(m.id.startswith(d.study_id + ".") and m.condition.startswith(d.study_id + ".") for m in d.measurements)
        assert (d.effect.direction, d.effect.delta) == (o.effect.direction, o.effect.delta)
        assert d.effect.treatment == d.study_id + o.effect.treatment[len(o.study_id):]
        assert d.effect.control == d.study_id + o.effect.control[len(o.study_id):]
    ans = truth.answer(studies)
    assert ans["duplicates"] == ["S011", "S012", "S013"] == ans["flags"]["duplicate"]
    counted = ans["supporting"] + ans["contradicting"] + ans["neutral"]
    assert len(counted) == 10 and not set(ans["duplicates"]) & set(counted + ans["undetermined"])
    assert ans["label"] == truth.answer(studies[:10])["label"]


def test_missing() -> None:
    studies = truth.generate(5, 10, missing=3)
    missing = [s for s in studies if s.missing]
    assert len(studies) == 10 and len(missing) == 3
    assert [s.missing for s in missing] == ["control", "treatment", "control"]    # in turn, in id order
    for s in missing:
        e = s.effect
        assert e.direction == "undetermined" and e.delta is None and e.reason == f"missing_{s.missing}"
        assert (e.control is None) == (s.missing == "control") and (e.treatment is None) == (s.missing == "treatment")
        assert e.metric == s.primary.id and not e.determined
        gone = s.condition(s.control_role if s.missing == "control" else s.treatment_role)
        assert not [m for m in s.measurements if m.condition == gone.id and m.metric == s.primary.id]
        assert [m for m in s.measurements if m.condition == gone.id]           # the distractor metrics stay
        assert len(s.measurements) == len(s.conditions) * len(s.metrics) * 2 - 2
        assert s.decoy is None and s.flags == () and s.pair(s.datasets[0]) is None
    ans = truth.answer(studies)
    assert ans["undetermined"] == [s.study_id for s in missing]
    assert len(ans["supporting"] + ans["contradicting"] + ans["neutral"]) == 7


def test_outliers() -> None:
    studies = truth.generate(5, 10, outliers=2)
    out = [s for s in studies if "large_effect" in s.flags]
    assert len(out) == 2
    for s in out:
        low, high = default_recipe().effects["large"]
        assert s.effect.direction == "supports" and low <= s.effect.delta <= high
        assert rules.claim_agrees(s.claim, "supports", SPEC.claim_map)
        q, (c2, t2) = s.primary, s.pair(s.datasets[1])
        assert rules.effect(t2.value, c2.value, q.higher_is_better, SPEC.min_effect)[0] == "supports"
        values = sorted(m.value for m in s.measurements)
        assert min(b - a for a, b in zip(values, values[1:])) > truth.DECOY_GAP
    ans = truth.answer(studies)
    assert ans["flags"]["large_effect"] == [s.study_id for s in out]
    assert set(ans["flags"]["large_effect"]) <= set(ans["supporting"])      # counted, only flagged
    plain, ids = truth.generate(5, 10), {o.study_id for o in out}
    assert [s.measurements for s in studies if s.study_id not in ids] == \
           [s.measurements for s in plain if s.study_id not in ids]


def test_irrelevant() -> None:
    studies = truth.generate(5, 6, irrelevant=3)
    irr = studies[6:]
    assert [s.study_id for s in irr] == ["S007", "S008", "S009"]
    assert [s.topic for s in irr] == ["survey", "other", "survey"]
    for s in irr:
        assert not s.relevant and s.conditions == () and s.metrics == () and s.measurements == ()
        assert s.effect == truth.Effect("undetermined", None, None, None, None, "screened_out")
        assert s.flags == () and s.duplicate_of is None and s.missing is None and not s.counted
    ans = truth.answer(studies)
    assert ans["undetermined"] == ["S007", "S008", "S009"] and ans["label"] == truth.answer(studies[:6])["label"]


def test_knob_combination_order_and_protection() -> None:
    """Outliers are drawn first, duplicates copy the (possibly redrawn) study, missing never touches an
    outlier or a duplicated original, irrelevant papers come last."""
    studies = truth.generate(7, 12, duplicates=2, missing=3, outliers=1, irrelevant=1)
    assert len(studies) == 15 and [s.study_id for s in studies] == [f"S{i:03d}" for i in range(1, 16)]
    protected = {s.study_id for s in studies if "large_effect" in s.flags} | {s.duplicate_of for s in studies if s.duplicate_of}
    assert not any(s.missing for s in studies if s.study_id in protected)
    assert all(s.effect.determined for s in studies[12:14]) and not studies[14].relevant
    ans = truth.answer(studies)
    assert len(ans["undetermined"]) == 4 and len(ans["duplicates"]) == 2


@pytest.mark.parametrize("level", LEVELS)
def test_template_papers_with_knobs_pass_every_check(level: str) -> None:
    for seed in range(1, 6):
        for s in truth.generate(seed, 8, duplicates=2, missing=2, outliers=1, irrelevant=2):
            r = render_study(s, level, seed)
            bad = [(c.name, c.detail) for c in r.fidelity.checks if not c.ok]
            assert not bad, (seed, level, s.study_id, bad)
            if s.missing:
                gone = s.condition(s.control_role if s.missing == "control" else s.treatment_role).id
                assert not [p for p in r.placements if p.role == "value" and p.fact.startswith(s.study_id)
                            and next(m.condition for m in s.measurements if m.id == p.fact) == gone
                            and next(m.metric for m in s.measurements if m.id == p.fact) == s.primary.id]
                if level in ("distributed", "complex", "contradictory"):
                    assert " – |" in r.text                     # the missing cell is a dash, never a number
                if level == "complex":                          # no relative sentence without the pair
                    assert "than the" not in r.text and "see text" not in r.text
                    assert not [p for p in r.placements if p.fmt == "relative"]
                assert not r.decoys
            if not s.relevant:
                assert r.placements == [] and r.decoys == [] and "|" not in r.text and not any(ch.isdigit() for ch in r.text)


def test_corpus_files_with_every_knob(tmp_path: Path) -> None:
    out = build(tmp_path, duplicates=2, missing=2, outliers=1, irrelevant=2)
    assert out["settings"] == {"name": "k", "studies": 8, "mix": truth.DEFAULT_MIX, "levels": list(LEVELS),
                               "duplicates": 2, "missing": 2, "outliers": 1, "irrelevant": 2}
    for lv in (*LEVELS, "mixed"):
        d = tmp_path / f"k-{lv}"
        meta, gt, manifest = load(d, "corpus.json"), load(d, "ground_truth.json"), load(d, "manifest.json")
        assert meta["settings"] == out["settings"] and meta["generator"]["version"] == corpus.GENERATOR_VERSION
        ids = [p["id"] for p in manifest["papers"]]
        assert ids == [f"S{i:03d}" for i in range(1, 13)]
        by = {s["study_id"]: s for s in gt["studies"]}
        for s in gt["studies"]:
            assert {"relevant", "flags", "duplicate_of", "missing"} <= set(s)
            assert s["flags"] == sorted(s["flags"]) and set(s["flags"]) <= set(rules.FLAGS)
        dups = [s for s in gt["studies"] if s["duplicate_of"]]
        assert [s["study_id"] for s in dups] == ["S009", "S010"]
        for s in dups:
            assert "duplicate" in s["flags"] and s["effect"]["direction"] == by[s["duplicate_of"]]["effect"]["direction"]
            assert s["level"] == by[s["duplicate_of"]]["level"]          # a second report at the original's level
            assert (d / "papers" / f"{s['study_id']}.md").read_text(encoding="utf-8").splitlines()[0] != \
                   (d / "papers" / f"{s['duplicate_of']}.md").read_text(encoding="utf-8").splitlines()[0]
        missing = [s for s in gt["studies"] if s["missing"]]
        assert len(missing) == 2
        for s in missing:
            e = s["effect"]
            assert e["direction"] == "undetermined" and e["delta"] is None and e["reason"] == f"missing_{s['missing']}"
            assert (e["control"] is None) if s["missing"] == "control" else (e["treatment"] is None)
            assert "claim_disagrees" not in s["flags"]
        irrelevant = [s for s in gt["studies"] if not s["relevant"]]
        assert [s["study_id"] for s in irrelevant] == ["S011", "S012"]
        for s in irrelevant:
            assert s["conditions"] == [] and s["metrics"] == [] and s["measurements"] == [] and s["author_claim"] is None
            assert s["effect"] == {"direction": "undetermined", "delta": None, "metric": None, "treatment": None,
                                   "control": None, "reason": "screened_out"}
            assert s["flags"] == [] and not [p for p in gt["placements"] if p["paper"] == s["study_id"]]
        survey = (d / "papers" / "S011.md").read_text(encoding="utf-8").lower()
        other = (d / "papers" / "S012.md").read_text(encoding="utf-8").lower()
        assert "retrieval" in survey
        assert not any(re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", other) for t in SCREEN_TERMS)
        ans = gt["answer"]
        assert set(ans) == {"label", "supporting", "contradicting", "neutral", "undetermined", "duplicates", "flags"}
        assert ans["duplicates"] == ["S009", "S010"] and ans["flags"]["duplicate"] == ["S009", "S010"]
        assert ans["undetermined"] == [s["study_id"] for s in missing] + ["S011", "S012"]
        assert len(ans["flags"]["large_effect"]) == 1 and ans["flags"]["large_effect"][0] in ans["supporting"]
        counted = ans["supporting"] + ans["contradicting"] + ans["neutral"]
        assert len(counted) == 6 and not set(counted) & set(ans["undetermined"] + ans["duplicates"])
        counts = {g: len(ans[g]) for g in ("supporting", "contradicting", "neutral")}
        assert ans["label"] == rules.label(counts, SPEC.table)
        contra = [s["study_id"] for s in gt["studies"] if s["level"] == "contradictory" and s["effect"]["direction"] != "undetermined"]
        assert ans["flags"]["claim_disagrees"] == contra
        assert all("claim_disagrees" in by[sid]["flags"] for sid in contra)
        fid = load(d, "fidelity.json")
        assert fid["excluded"] == [] and all(p["ok"] for p in fid["papers"]) and len(fid["papers"]) == 12
        assert {c["name"] for c in fid["papers"][-1]["checks"]} >= {"added_numbers", "added_claims", "irrelevant"}
    # the mixed corpus's papers are their level corpus's, duplicates and irrelevant papers included
    mixed = load(tmp_path / "k-mixed", "corpus.json")
    for p in mixed["papers"]:
        assert (tmp_path / "k-mixed/papers" / f"{p['id']}.md").read_bytes() == \
               (tmp_path / f"k-{p['level']}/papers/{p['id']}.md").read_bytes()


def test_plain_build_is_unchanged_by_the_knobs(tmp_path: Path) -> None:
    """The first n papers of a build with duplicates and irrelevant papers are byte for byte the plain
    build's (the extra draws come from their own streams)."""
    build(tmp_path / "plain")
    build(tmp_path / "more", duplicates=2, irrelevant=1)
    for lv in (*LEVELS, "mixed"):
        for i in range(1, 9):
            assert (tmp_path / f"plain/k-{lv}/papers/S{i:03d}.md").read_bytes() == \
                   (tmp_path / f"more/k-{lv}/papers/S{i:03d}.md").read_bytes()
        plain, more = load(tmp_path / f"plain/k-{lv}", "ground_truth.json"), load(tmp_path / f"more/k-{lv}", "ground_truth.json")
        assert more["studies"][:8] == plain["studies"]
        first = [f"S{i:03d}" for i in range(1, 9)]
        assert [p for p in more["placements"] if p["paper"] in first] == plain["placements"]
        assert {p["paper"] for p in more["placements"] if p["paper"] not in first} == {"S009", "S010"}


def test_set_level_flags_are_found_over_the_written_studies(tmp_path: Path) -> None:
    """When a renderer excludes a study (here: told to write_corpus as failed), the flags in
    ground_truth.json are what the rules give on the papers written, not on the drawn set."""
    studies = truth.generate(5, 10, outliers=1, duplicates=1)
    outlier = next(s for s in studies if "large_effect" in s.flags)
    dup = next(s for s in studies if s.duplicate_of)
    rendered = TemplateRenderer().render_all([(s, "explicit") for s in studies], 5)
    papers = {s.study_id: rendered[(s.study_id, "explicit")] for s in studies}
    settings = corpus.settings_of(name="k", studies=10, mix=None, levels=["explicit"], outliers=1, duplicates=1)
    for failed in ({outlier.study_id: ["explicit"]}, {dup.duplicate_of: ["explicit"], dup.study_id: ["(its original failed)"]}):
        corpus.write_corpus(tmp_path / "w", name="k", level="explicit", seed=5, renderer=TemplateRenderer(), protocol=PROTO,
                            studies=studies, papers=papers, failed=failed, settings=settings)
        gt = load(tmp_path / "w", "ground_truth.json")
        kept = truth.flagged([s for s in studies if s.study_id not in failed], SPEC)
        assert [s["study_id"] for s in gt["studies"]] == [s.study_id for s in kept]
        for record, s in zip(gt["studies"], kept):
            assert (record["flags"], record["duplicate_of"]) == (sorted(s.flags), s.duplicate_of)
        assert gt["answer"]["flags"]["large_effect"] == [s.study_id for s in kept if "large_effect" in s.flags]
        assert gt["answer"]["flags"]["duplicate"] == [s.study_id for s in kept if s.duplicate_of] == gt["answer"]["duplicates"]
    assert not any("large_effect" in s.flags for s in truth.flagged([s for s in studies if s is not outlier], SPEC))


def test_generator_self_check_refuses_a_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit, match="--outliers 7"):
        truth.generate(5, 10, outliers=7)              # only 6 supporting studies
    with pytest.raises(SystemExit, match="--duplicates 11"):
        truth.generate(5, 10, duplicates=11)
    with pytest.raises(SystemExit, match="--missing 9"):
        truth.generate(5, 10, missing=9, outliers=1, duplicates=1)
    with pytest.raises(SystemExit, match="negative"):
        truth.generate(5, 10, missing=-1)
    off = SPEC.model_copy(update={"flags": SPEC.flags.model_copy(update={"duplicates": False})})
    with pytest.raises(SystemExit, match="duplicate detection off"):
        truth.generate(5, 10, spec=off, duplicates=1)
    assert truth.generate(5, 10, spec=off) == truth.generate(5, 10)
    # the rules must find exactly what was planted
    monkeypatch.setattr(rules, "large_effects", lambda *a, **k: [])
    with pytest.raises(SystemExit, match="rules.large_effects flags"):
        truth.generate(5, 10, outliers=1)
    monkeypatch.setattr(rules, "duplicates", lambda *a, **k: {})
    with pytest.raises(SystemExit, match="rules.duplicates finds"):
        truth.generate(5, 10, duplicates=1)


def test_distinct_studies_never_share_a_pair() -> None:
    for seed in range(1, 21):
        studies = truth.generate(seed, 12, duplicates=2, outliers=1)
        keys = [(s.study_id, k) for s in studies if not s.duplicate_of for k in truth.pair_keys(s)]
        assert len({k for _, k in keys}) == len(keys)


def test_cli_knobs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from synth import cli
    assert cli.main(["build", "--name", "c", "--seed", "2", "--studies", "4", "--levels", "explicit", "--out", str(tmp_path),
                     "--duplicates", "1", "--missing", "1", "--irrelevant", "1"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["settings"]["duplicates"] == 1 and printed["answer"]["duplicates"] == ["S005"]
    assert printed["answer"]["undetermined"][-1] == "S006"
    with pytest.raises(SystemExit):
        cli.main(["build", "--name", "c", "--seed", "2", "--out", str(tmp_path), "--duplicates", "-1"])
