"""The 100-question generator (bench.py) and its rewording check (reword.py). No real LLM: fake models only.

Gold of every type is checked against a plain Python scan of the seed facts, so SPARQL and the scan must agree. The
tests read whatever seed.ttl holds (5 or 20 papers) and assert only what must hold for any seed.
"""
from __future__ import annotations

import json
import threading
import time
from decimal import Decimal
from pathlib import Path

import pytest

from evqa import llm
from evqa.seed import bench, reword
from evqa.seed import questions as qs

DOMAIN = "medical"


@pytest.fixture(scope="module")
def world() -> bench.World:
    return bench.World(DOMAIN)


@pytest.fixture(scope="module")
def valid(world):
    """Up to 6 valid candidates of each type."""
    rng = __import__("random").Random(1)
    cands = bench.candidates(world)
    out = {}
    for t in bench.TYPES:
        pool = bench.Pool(world, cands[t], rng, set())
        pool.fill(6)
        out[t] = pool.ok
    return out


def _match(f: dict, spec: qs.Spec, *, card: bool = True) -> bool:
    fx = spec.fixed
    if f["split"] != spec.split:
        return False
    if card and (f["stat"] != "MeanDifference" or f["comparator"] != (fx.get("comparator") or "placebo")):
        return False
    if fx.get("subject") and f["subject"] not in fx["subject"]:
        return False
    for slot in ("measure", "context"):
        if fx.get(slot) is not None and f[slot] != fx[slot]:
            return False
    for slot in ("dose", "week"):
        if fx.get(slot) is not None and f[slot] != Decimal(str(fx[slot])):
            return False
    return True


# ---------------------------------------------------------------- SPARQL -> gold, per type

def test_lookup_gold_is_every_matching_fact(world, valid) -> None:
    assert valid["lookup"]
    for spec, g in valid["lookup"]:
        assert sorted(g["row_ids"]) == sorted(f["id"] for f in world.facts if _match(f, spec))
        assert g["answerable"] is True and g["status"] == "answered" and g["spec"]["type"] == "lookup"


def test_effect_gold_is_one_row_per_study_with_a_verdict(world, valid) -> None:
    assert valid["effect"]
    for spec, g in valid["effect"]:
        want = [f for f in world.facts if _match(f, spec, card=False) and f["stat"] == "MeanDifference"
                and f["comparator"] == spec.fixed["comparator"]]
        assert sorted(g["row_ids"]) == sorted(f["id"] for f in want)
        m = world.measures[spec.fixed["measure"]]
        for row in g["answer"]["table"]:
            v = Decimal(row["value"])
            if abs(v) <= m["step"]:
                assert row["verdict"] == "no clear difference"
            else:
                assert row["verdict"].endswith("better")
        assert {s["paper"] for s in g["answer"]["per_study"]} == {f["paper"] for f in want}


def test_verdict_and_direction_rules() -> None:
    step = Decimal("0.1")
    assert bench._verdict(Decimal("-0.5"), False, step, "A", "B") == "A better"
    assert bench._verdict(Decimal("0.5"), False, step, "A", "B") == "B better"
    assert bench._verdict(Decimal("-0.1"), False, step, "A", "B") == "no clear difference"
    assert bench._direction([Decimal("-0.2"), Decimal("-0.5"), Decimal("-0.9")], step) == "goes down"
    assert bench._direction([Decimal("-0.5"), Decimal("-0.45")], step) == "flat"
    assert bench._direction([Decimal("-0.5"), Decimal("-0.9"), Decimal("-0.3")], step) == "mixed"


def test_best_gold_winner_has_the_best_value_and_a_margin(world, valid) -> None:
    assert valid["best"]
    for _, g in valid["best"]:
        a = g["answer"]
        for grp in a["groups"]:
            if grp["status"] == "winner":
                vals = [Decimal(r["value"]) for r in grp["ranking"]]
                best = max(vals) if a["higher_is_better"] else min(vals)
                assert Decimal(grp["ranking"][0]["value"]) == best and grp["ranking"][0]["candidate"] == grp["winner"]
                assert Decimal(grp["margin"]) > Decimal(a["rounding_step"])


def test_trend_gold_orders_points_and_names_the_direction(world, valid) -> None:
    assert valid["trend"]
    for spec, g in valid["trend"]:
        assert sorted(g["row_ids"]) == sorted(f["id"] for f in world.facts if _match(f, spec))
        step = Decimal(g["answer"]["rounding_step"])
        assert any(len(s["points"]) >= 2 for s in g["answer"]["series"])
        for s in g["answer"]["series"]:
            at = [Decimal(p["at"].split()[0]) for p in s["points"]]
            assert at == sorted(at)
            if len(at) >= 2:
                assert s["direction"] == bench._direction([Decimal(p["value"]) for p in s["points"]], step)


def test_list_gold_is_the_papers_with_a_matching_row(world, valid) -> None:
    assert valid["list"]
    for spec, g in valid["list"]:
        want = {f["paper"] for f in world.facts if _match(f, spec, card=False)}
        assert {p["paper"] for p in g["answer"]["papers"]} == want and g["open_columns"] == []


def test_conflict_gold_flags_two_papers_that_disagree(world, valid) -> None:
    if not valid["conflict"]:
        pytest.skip("this seed reports no fact twice")
    for spec, g in valid["conflict"]:
        assert g["answer"]["conflict"] is True
        hit = [grp for grp in g["answer"]["groups"] if grp["status"] == "conflict"]
        assert hit and all(len({r["paper"] for r in grp["rows"]}) >= 2 for grp in hit)
        step = Decimal(g["answer"]["rounding_step"])
        assert all(Decimal(grp["spread"]) > step for grp in hit)


def test_conflict_needs_a_real_disagreement(world, valid) -> None:
    for spec, _ in valid["lookup"][:3]:   # one paper per fact: no conflict
        if len(spec.fixed.get("subject") or []) == 1 and spec.fixed.get("dose") and spec.fixed.get("week"):
            with pytest.raises(qs.Rejected):
                bench.gold_conflict(world, qs.Spec("x", "conflict", spec.split, "", spec.fixed,
                                                   ("patient_group", "measure_variant")))


def test_absent_and_near_miss_gold_is_not_reported_with_why(world, valid) -> None:
    for t in ("absent", "near_miss"):
        assert valid[t], t
        for spec, g in valid[t]:
            assert g["answerable"] is False and g["status"] == "not_reported" and g["row_ids"] == []
            assert g["answer"]["status"] == "not_reported" and g["answer"]["why"].startswith("no paper reports")
            assert not [f for f in world.facts if _match(f, spec)]
            subj = spec.fixed["subject"][0]
            assert any(f["subject"] == subj and f["split"] == spec.split for f in world.facts)   # a corpus drug
            if t == "near_miss":
                near = [f for f in world.facts if f["id"] in set(g["near_rows"])]
                assert near and all(f["subject"] == subj and f["measure"] == spec.fixed["measure"] for f in near)


def test_near_miss_group_is_no_real_group(world, valid) -> None:
    for spec, _ in valid["near_miss"]:
        ctx = spec.fixed.get("context")
        if ctx:
            label = ctx[len(qs.LABEL):]
            assert label not in world.contexts.values()
            assert world.new_group(label, ())


def test_out_of_scope_terms_are_in_no_paper_and_not_in_the_seed(world, valid) -> None:
    assert valid["out_of_scope"]
    for spec, g in valid["out_of_scope"]:
        assert spec.split == "test" and g["absence_check"]["hits"] == 0
        for term in g["absence_check"]["terms"]:
            assert term.lower() not in world.seed_text
            assert all(not bench.mentions(t, term) for t in world.texts.values())


def test_out_of_scope_rejected_when_a_paper_names_it(world) -> None:
    texts = {**{k: v for k, v in world.texts.items()}, "P-fake": "We also compared atorvastatin in a side arm."}
    w2 = bench.World.__new__(bench.World)
    w2.__dict__.update(world.__dict__)
    w2.texts = texts
    spec = bench._spec("out_of_scope", "test", "What does atorvastatin do to HbA1c?",
                       {"subject": ["atorvastatin"], "measure": sorted(world.measures)[0]}, kind="drug",
                       terms=["atorvastatin"], why="x")
    assert bench.gold_not_reported(world, spec)["answerable"] is False
    with pytest.raises(qs.Rejected, match="out-of-scope terms found"):
        bench.gold_not_reported(w2, spec)
    assert not w2.absent_everywhere("atorvastatin")
    assert not [s for s in bench.candidates(w2)["out_of_scope"] if "atorvastatin" in s.extra["terms"]]


def test_not_reported_rejected_when_the_seed_has_the_fact(world, valid) -> None:
    spec, _ = valid["lookup"][0]
    with pytest.raises(qs.Rejected, match="reported"):
        bench.gold_not_reported(world, qs.Spec("x", "absent", spec.split, spec.text, spec.fixed, spec.open,
                                               extra={"why": "x"}))


def test_regold_round_trips_through_json(world, valid) -> None:
    for t in bench.TYPES:
        for spec, g in valid[t][:2]:
            back = bench.spec_from("x", json.loads(json.dumps(g["spec"])))
            assert bench.gold(world, back)["row_ids"] == g["row_ids"]


# ---------------------------------------------------------------- choosing

def test_choose_is_seeded_keeps_quota_and_reports_shortfall(world) -> None:
    quota = {t: 2 for t in bench.TYPES} | {"conflict": 40}
    a = bench.choose(world, 7, quota)
    b = bench.choose(world, 7, quota)
    assert [s.text for s, _ in a["chosen"]] == [s.text for s, _ in b["chosen"]]
    rep = a["report"]
    assert rep["conflict"]["shortfall"] > 0                                    # the seed cannot give 40 conflicts
    in_corpus = sum(rep[t]["total"] for t in bench.IN_CORPUS)
    assert in_corpus == sum(max(quota[t], rep[t]["kept"]) for t in bench.IN_CORPUS) - rep["missing_in_corpus"]
    assert sum(rep[t]["total"] for t in bench.NOT_REPORTED) == 6 - rep["missing_not_reported"]
    kept = {s.text for s in qs.SPECS[DOMAIN]}
    assert not kept & {s.text for s, _ in a["chosen"]}


def test_ids_continue_after_the_kept_questions(world) -> None:
    picked = bench.choose(world, 3, {t: 1 for t in bench.TYPES})["chosen"]
    ids = [s.qid for s, _ in bench.assign_ids(DOMAIN, picked)]
    test_ids = [i for i in ids if "-p" not in i]
    assert test_ids and min(int(i.rsplit("-", 1)[1]) for i in test_ids) == 5
    assert all(int(i.rsplit("-p", 1)[1]) >= 2 for i in ids if "-p" in i)


# ---------------------------------------------------------------- rewording check

def _task() -> reword.Task:
    return reword.Task("Q", "How much does brenoxalin 20 mg change HbA1c at 24 weeks in elderly adults with type 2 "
                            "diabetes on metformin?",
                       [reword.Keep("name", "brenoxalin"), reword.Keep("dose", "20 mg"), reword.Keep("week", "24 weeks"),
                        reword.Keep("group", "elderly adults with type 2 diabetes on metformin"),
                        reword.Keep("measure", "HbA1c", ("ΔHbA1c", "glycated haemoglobin"))],
                       values=["-0.78"], other_names=["kavolemin", "atorvastatin"])


def test_check_accepts_a_faithful_rewording() -> None:
    ok = "In elderly adults with type 2 diabetes on metformin, what HbA1c change does brenoxalin 20 mg give at week 24?"
    assert reword.check(_task(), ok) == []


@pytest.mark.parametrize("text, problem", [
    ("How much does 20 mg change HbA1c at 24 weeks in elderly adults with type 2 diabetes on metformin?", "drops name"),
    ("How much does brenoxalin change HbA1c at 24 weeks in elderly adults with type 2 diabetes on metformin?",
     "drops dose"),
    ("How much does brenoxalin 20 mg change HbA1c at 24 weeks in adults with type 2 diabetes on metformin?",
     "drops group"),
    ("Does brenoxalin 20 mg lower HbA1c by 0.78 at 24 weeks in elderly adults with type 2 diabetes on metformin?",
     "leaks gold value"),
    ("How much does brenoxalin 20 mg change HbA1c at 24 or 52 weeks in elderly adults with type 2 diabetes on "
     "metformin?", "adds number"),
    ("How much does brenoxalin 20 mg change HbA1c at 24 weeks versus kavolemin in elderly adults with type 2 diabetes"
     " on metformin?", "adds drug"),
    ("Is it not reported how much brenoxalin 20 mg changes HbA1c at 24 weeks in elderly adults with type 2 diabetes"
     " on metformin?", "hints at the answer"),
    ("How much does brenoxalin 20 mg change weight at 24 weeks in elderly adults with type 2 diabetes on metformin?",
     "drops measure"),
])
def test_check_rejects(text: str, problem: str) -> None:
    assert any(p.startswith(problem) for p in reword.check(_task(), text)), reword.check(_task(), text)


class FakeGen:
    """Rewords by a script: a list of answers per template, used in turn; counts parallel calls."""
    model = "fake-gen"

    def __init__(self, script: dict[str, list[str]]):
        self.script, self.seen, self.lock, self.running, self.peak = script, {}, threading.Lock(), 0, 0

    def __call__(self, system: str, user: str, schema: dict) -> dict:
        with self.lock:
            self.running += 1
            self.peak = max(self.peak, self.running)
        time.sleep(0.02)
        tpl = json.loads(user)["template"]
        with self.lock:
            self.running -= 1
            i = self.seen.get(tpl, 0)
            self.seen[tpl] = i + 1
        answers = self.script.get(tpl, [tpl])
        return {"output": {"question": answers[min(i, len(answers) - 1)]}}


class FakeVer:
    model = "fake-ver"

    def __init__(self, same: bool = True):
        self.same, self.calls = same, 0

    def __call__(self, system: str, user: str, schema: dict) -> dict:
        self.calls += 1
        assert set(json.loads(user)) == {"original", "candidate"}   # blind: no generator reasons
        return {"output": {"same": self.same, "difference": None if self.same else "dose changed"}}


@pytest.fixture()
def no_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "CACHE", tmp_path)
    monkeypatch.setattr(llm, "LLM_LOG", tmp_path / "log.jsonl")


def test_reword_repairs_a_leak_then_passes(no_cache) -> None:
    t = _task()
    good = "For elderly adults with type 2 diabetes on metformin, how much does brenoxalin 20 mg move HbA1c at 24 weeks?"
    gen = FakeGen({t.template: [t.template.replace("change HbA1c", "lower HbA1c by 0.78"), good]})
    out = reword.reword_one(gen, FakeVer(), t)
    assert out["source"] == "llm" and out["text"] == good and len(out["attempts"]) == 2
    assert out["attempts"][0]["problems"] and out["attempts"][0]["verifier"] is None   # code check comes first


def test_reword_falls_back_to_template_when_verifier_disagrees(no_cache) -> None:
    t = _task()
    ver = FakeVer(same=False)
    out = reword.reword_one(FakeGen({}), ver, t)
    assert out["source"] == "template" and out["text"] == t.template
    assert len(out["attempts"]) == reword.ATTEMPTS and ver.calls == 1   # same pair again: from the call cache
    assert all(a["problems"][0].startswith("verifier") for a in out["attempts"])


def test_reword_all_runs_at_most_three_at_once(no_cache) -> None:
    tasks = [reword.Task(f"Q{i}", f"Which studies tested drug{i}x?", [reword.Keep("name", f"drug{i}x")])
             for i in range(9)]
    gen = FakeGen({})
    out = reword.reword_all(gen, FakeVer(), tasks)
    assert gen.peak <= 3 and set(out) == {t.qid for t in tasks}


def test_render_with_fake_models(world, no_cache, monkeypatch) -> None:
    monkeypatch.setattr(bench, "QUOTA", {t: 2 for t in bench.TYPES} | {"lookup": 4, "best": 3})
    files, rep = bench.render(DOMAIN, gen=FakeGen({}), ver=FakeVer(), w=world)
    recs = [json.loads(x) for p, t in files.items() if p.suffix == ".jsonl" for x in t.splitlines()]
    assert len(recs) == rep["questions"] == len([p for p in files if p.name.startswith("Q-")])
    assert all({"type", "answerable"} <= set(r) for r in recs)
    assert all("not reported" not in r["question"].lower() for r in recs)
    oos = [r for r in recs if r["type"] == "out_of_scope"]
    assert oos and {r["split"] for r in oos} == {"test"}
    kept = {s.qid: qs._dump(qs.gold(DOMAIN, s, world.g)) for s in qs.SPECS[DOMAIN]}
    for qid, text in kept.items():
        assert files[qs.gold_dir(DOMAIN) / f"{qid}.json"] == text            # kept gold unchanged
    for r in recs:
        g = json.loads(files[qs.gold_dir(DOMAIN) / f"{r['qid']}.json"])
        assert g["split"] == r["split"] and g.get("answerable", True) == r["answerable"]
        if r["type"] in bench.NOT_REPORTED:
            assert g["answer"]["why"] and g["row_ids"] == []
    m = json.loads(files[qs.gold_dir(DOMAIN) / "manifest.json"])
    assert m["generator"]["reword"]["generator"] == "fake-gen" and len(m["questions"]) == len(recs)


def test_frozen_bench_set_regolds_without_llm(world) -> None:
    m = json.loads((qs.gold_dir(DOMAIN) / "manifest.json").read_text(encoding="utf-8"))
    if "generator" not in m:
        pytest.skip("the 100-question set is not written yet")
    assert qs.verify(DOMAIN) == []
    for qid in m["questions"]:
        g = json.loads((qs.gold_dir(DOMAIN) / f"{qid}.json").read_text(encoding="utf-8"))
        g.pop("wording", None)
        assert json.loads(qs._dump(bench.regold(world, g))) == g, qid
