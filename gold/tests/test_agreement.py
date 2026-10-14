"""gold/agreement.py and gold/screening_check.py: kappa, the bootstrap over questions, Wilson intervals, the
triage miss estimate and the screening false-negative rate, against values computed by hand."""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from gold import agreement, review, screening_check

from .fixtures import ANSWERS, QID, Env, cid, env, pulled, rids  # noqa: F401

Z = 1.959963984540054  # the 97.5 % normal quantile


def hand_wilson(k: int, n: int) -> tuple[float, float]:
    p = k / n
    centre = (p + Z * Z / (2 * n)) / (1 + Z * Z / n)
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / (1 + Z * Z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def test_wilson_against_the_formula() -> None:
    assert agreement.wilson(3, 10) == pytest.approx(hand_wilson(3, 10))
    assert [round(x, 4) for x in agreement.wilson(3, 10)] == [0.1078, 0.6032]
    assert [round(x, 4) for x in agreement.wilson(2, 10)] == [0.0567, 0.5098]
    assert agreement.wilson(0, 5)[0] == 0.0 and agreement.wilson(0, 0) == (0.0, 1.0)


def test_kappa_against_a_hand_table() -> None:
    # 10 items: both yes 4, a yes b no 1, a no b yes 2, both no 3. p_o = 0.7, p_e = .5*.6 + .5*.4 = 0.5.
    a = ["y"] * 5 + ["n"] * 5
    b = ["y"] * 4 + ["n"] + ["y"] * 2 + ["n"] * 3
    assert agreement.kappa(a, b) == pytest.approx(0.4)
    # Weight 3 on the a-yes/b-no item: p_o = 7/12, p_e = 7/12*6/12 + 5/12*6/12 = 0.5 -> 1/6.
    assert agreement.kappa(a, b, sample_weight=[1, 1, 1, 1, 3, 1, 1, 1, 1, 1]) == pytest.approx(1 / 6)
    assert agreement.kappa(["y", "y"], ["y", "y"]) is None  # one label: undefined
    assert agreement.kappa([], []) is None
    assert agreement.kappa(["y", "y"], ["n", "n"]) == 0.0


STRATA = {f"r{n}": "sample" if n in (4, 5) else "triaged" for n in range(1, 11)}  # from the pool, by record id


def overlap() -> list[dict]:
    """ann and bob on 8 records of q01/q02 (labels a/b), one record ann alone, one ann with carol, and one
    stale record (its id is not a current record) that both answered."""
    def rec(n: int | str, qid: str, a: dict, b: dict, other: str = "bob") -> dict:
        return pulled(f"r{n}", "overlap", {"ann": a, other: b} if b else {"ann": a}, qid=qid)

    c, i, u = {"label": "correct"}, {"label": "incorrect"}, {"label": "unsure"}
    return [rec(1, "q01", c, c), rec(2, "q01", c, i), rec(3, "q01", i, i), rec(4, "q01", i, i), rec(5, "q01", u, i),
            rec(6, "q02", {**c, "vital": "yes"}, {**c, "vital": "yes"}),
            rec(7, "q02", {**c, "vital": "yes"}, {**c, "vital": "no"}),
            rec(8, "q02", i, c), rec(9, "q02", c, {}), rec(10, "q02", c, c, "carol"), rec("-old", "q02", c, i)]


def test_agreement_per_field_and_stratum() -> None:
    k = agreement.agreement(overlap(), STRATA)
    assert k["reviewers"] == ["ann", "bob"] and k["items"] == 8 and k["questions"] == 2
    assert (k["records_one_reviewer"], k["records_other_reviewers"], k["records_stale"]) == (1, 1, 1)
    # label: p_o = 5/8; ann c4 i3 u1, bob c4 i4 -> p_e = 28/64; (5/8 - 28/64) / (36/64) = 1/3
    assert k["label"]["kappa"] == pytest.approx(1 / 3, abs=1e-4)
    # keep (unsure -> drop): p_o = 6/8, both 4 keep 4 drop -> p_e = 0.5 -> 0.5
    assert k["keep"]["kappa"] == pytest.approx(0.5)
    # vital where both kept (r1, r6, r7): (no, no), (yes, yes), (yes, no) -> (2/3 - 4/9) / (5/9) = 0.4
    assert k["vital"]["items"] == 3 and k["vital"]["kappa"] == pytest.approx(0.4)
    # triaged (r1-r3, r6-r8): p_o = 4/6, ann c4 i2, bob c4 i2 -> p_e = 20/36 -> 0.25; sample: p_o = 1/2 = p_e -> 0
    assert k["label"]["by_stratum"]["triaged"]["kappa"] == pytest.approx(0.25)
    assert k["label"]["by_stratum"]["sample"]["kappa"] == 0.0
    assert len(k["keep"]["kappa_95"]) == 2 and k["keep"]["bootstrap"]["questions"] == 2
    assert k["keep_kappa_meets_bar"] is False


def test_bootstrap_resamples_questions() -> None:
    groups = {"q1": [("k", "k")] * 4, "q2": [("k", "d"), ("d", "d"), ("d", "d")], "q3": [("d", "k"), ("k", "k")]}
    first = agreement.bootstrap_kappa(groups)
    assert first == agreement.bootstrap_kappa(groups)  # seeded
    low, high = first["interval"]
    assert -1.0 <= low <= high <= 1.0
    assert first["resamples"] == 2000 and 0 < first["undefined"] < 2000  # q1 alone has one label
    assert agreement.bootstrap_kappa({"q1": [("k", "d"), ("d", "d")]})["interval"] is None


def test_triage_miss_estimate_as_the_labelling_formula() -> None:
    sizes = {"triaged": True, "reviewed_tiers": 25, "rest": 40, "sampled": 12}
    items = {f"t{n}": {"stratum": "triaged"} for n in range(25)} | {f"s{n}": {"stratum": "sample"} for n in range(12)}
    decisions = [SimpleNamespace(candidate_id=f"t{n}", keep=n < 20) for n in range(25)]
    decisions += [SimpleNamespace(candidate_id=f"s{n}", keep=n < 2) for n in range(10)]  # s10, s11 unresolved
    out = agreement.triage_miss(items, decisions, sizes)
    low, high = hand_wilson(2, 10)
    unreviewed = 40 - 10
    assert out["sample_kept_share"] == 0.2 and out["sample_unresolved"] == 2 and out["tiers_unresolved"] == 0
    assert out["estimated_missed"] == 6.0  # 30 x 2/10
    assert out["estimated_missed_95"] == [round(unreviewed * low, 1), round(unreviewed * high, 1)] == [1.7, 15.3]
    assert out["estimated_recall"] == round(20 / (20 + 2 + 6), 4) == 0.7143
    assert out["estimated_recall_95"] == [round(20 / (22 + unreviewed * high), 4), round(20 / (22 + unreviewed * low), 4)]
    assert agreement.triage_miss(items, decisions, {"triaged": False}) is None


def test_screening_false_negative_rate() -> None:
    records = [pulled(f"screening-q01-p{n}", "screening", {"ann": {"relevant": "yes" if n == 1 else "no"}},
                      paper_id=f"p{n}", not_relevant_total=40) for n in range(1, 6)]
    records.append(pulled("screening-q01-p6", "screening", {}, paper_id="p6"))  # not checked yet
    records.append(pulled("screening-q01-p7", "screening", {"ann": {"relevant": "yes"}}, paper_id="p7"))  # an old draw
    drawn = {"not_relevant": 40, "sampled": 6, "unread": 3, "papers": [f"p{n}" for n in range(1, 7)]}
    out = screening_check.report(records, drawn)
    low, high = hand_wilson(1, 5)
    assert (out["checked"], out["found_relevant"], out["false_negative_rate"]) == (5, 1, 0.2)
    assert out["outside_sample"] == 1
    assert out["false_negative_rate_95"] == [round(low, 4), round(high, 4)] == [0.0362, 0.6245]
    assert out["estimated_missed_papers"] == 8.0 and out["estimated_missed_papers_95"] == [1.4, 25.0]
    assert out["papers_found_relevant"] == ["p1"]
    both = screening_check.overall({"q01": out, "q02": screening_check.report([], {"not_relevant": 10, "sampled": 0})})
    assert both["not_relevant"] == 50 and both["checked"] == 5 and both["estimated_missed_papers"] == 8.0
    assert both["estimated_missed_papers_bounds"] == [1.4, 35.0]  # q02 unchecked: 0 to 10 more


def test_screening_sample_is_seeded(env: Env) -> None:
    first = screening_check.sample(env.root, QID, size=2)
    assert first["not_relevant"] == 4 and first["unread"] == 1 and first["sampled"] == 2
    assert set(first["papers"]) <= {"p2", "p7", "p8", "p9"}
    again = screening_check.sample(env.root, QID, size=10)  # drawn once: kept
    assert again["kept"] is True and again["papers"] == first["papers"] and first["kept"] is False
    assert screening_check.sample(env.root, QID, size=10, force=True)["sampled"] == 4
    assert screening_check.sample(env.root, QID, size=2, force=True)["papers"] == first["papers"]  # seeded


def test_kappa_comes_from_the_first_complete_snapshot(env: Env) -> None:
    before = [pulled("q01-c000001", "overlap", {"ann": {"label": "correct"}, "bob": {"label": "incorrect"}}),
              pulled("q01-c000002", "overlap", {"ann": {"label": "correct"}})]
    review.store(env.root, {"overlap": before})
    assert len(review.snapshot(env.root, before, taken_at="2026-10-14T10:00:00.000000Z")) == 1
    assert review.snapshot(env.root, before) == []  # nothing changed: no second file
    after = [pulled("q01-c000001", "overlap", {"ann": {"label": "correct"}, "bob": {"label": "correct"}}),
             pulled("q01-c000002", "overlap", {"ann": {"label": "correct"}, "bob": {"label": "correct"}})]
    review.store(env.root, {"overlap": after})  # bob changed his answer after talking to ann
    review.snapshot(env.root, after, taken_at="2026-10-14T11:00:00.000000Z")
    records, sources = review.overlap_records(env.root, QID)
    assert sources["records_from_snapshots"] == 2 and len(sources["snapshots"]) == 2
    labels = {r["id"]: review.submitted(r)["bob"]["label"] for r in records}
    assert labels == {"q01-c000001": "incorrect", "q01-c000002": "correct"}  # the first complete version each


def test_overall_kappa_says_whether_it_is_independent(env: Env) -> None:
    ids = rids(env)
    both = [pulled(ids[cid(n)], "overlap", {"ann": {"label": "correct"}, "bob": {"label": label}})
            for n, label in ((1, "correct"), (2, "incorrect"), (3, "correct"), (4, "incorrect"))]
    review.store(env.root, {"overlap": both})  # pulled, never snapshotted
    kappa = agreement.write_reports(env.root, [QID])["kappa"]
    assert kappa["items"] == 4 and kappa["records_from_live"] == 4 and kappa["independent"] is False
    assert "gold snapshot" in kappa["warning"]
    review.snapshot(env.root, both)
    kappa = agreement.write_reports(env.root, [QID])["kappa"]
    assert kappa["records_from_snapshots"] == 4 and kappa["independent"] is True and "warning" not in kappa
    mine = review.read_json(env.root / QID / "report.json")["kappa"]
    assert mine["independent"] is True and mine["label"]["by_stratum"]["triaged"]["items"] == 3  # c4: sample


def test_write_reports(env: Env) -> None:
    ids = rids(env)
    review.store(env.root, {"review": [pulled(ids[c], "review", {"aditya": v}) for c, v in ANSWERS.items()]})
    drawn = screening_check.sample(env.root, QID, size=2)
    review.store(env.root, {"screening": [
        pulled(f"screening-{QID}-{p}", "screening", {"aditya": {"relevant": "yes" if n == 0 else "no"}},
               paper_id=p, not_relevant_total=4) for n, p in enumerate(drawn["papers"])]})
    overall = agreement.write_reports(env.root, [QID])
    mine = review.read_json(env.root / QID / "report.json")
    t = mine["triage"]  # c4 kept, c5 dropped in the sample of the rest (4): (4 - 2) x 1/2 = 1 missed
    assert (t["tiers_kept"], t["sample_reviewed"], t["sample_kept"], t["estimated_missed"]) == (3, 2, 1, 1.0)
    assert t["estimated_recall"] == 0.6
    assert mine["screening"]["false_negative_rate"] == 0.5 and mine["screening"]["estimated_missed_papers"] == 2.0
    assert mine["kappa"] is None and mine["review"]["kept"] == 4
    assert overall == review.read_json(env.root / "report.json")
    assert overall["triage"]["estimated_missed"] == 1.0 and overall["kappa"]["items"] == 0
    assert overall["screening"]["overall"]["found_relevant"] == 1
