"""evqa run folders scored by the scorer service (evqa/scoring.py -> thesis_scorer): a fake run made from gold scores
1.0; each broken layer is blamed; closed book ~0. The scorer's own rules are tested in services/thesis-scorer."""
from __future__ import annotations

from pathlib import Path

import yaml

from evqa import answer
from evqa.contracts import (FindHit, Name, OpenPoint, Passage, Row, RunConfig, Spec, StdValue, write_json,
                            write_jsonl)
from thesis_scorer import structured
from thesis_scorer.llm import Chat

from evqa import scoring
from evqa.seed import questions as seed_questions

DOMAIN = "medical"
QIDS = ["Q-med-01", "Q-med-02", "Q-med-03", "Q-med-04"]


def gold_spec(g: dict) -> Spec:
    """The spec a perfect advisor writes for gold question g (any dataset type)."""
    names = seed_questions.names(DOMAIN)
    facts = scoring.seed_facts(DOMAIN)
    f = facts[g["row_ids"][0]] if g["row_ids"] else None
    slots = g["slots"]
    fixed = {}
    if slots.get("dose") is not None:
        fixed["dose"] = f"{slots['dose']} mg"
    if slots.get("week") is not None:
        fixed["time_point"] = f"{slots['week']} weeks"
    if slots.get("context") is not None:
        fixed["patient_group"] = f["context"] if f else scoring.blueprint_label(DOMAIN, slots["context"])
    best_by = None
    if g["type"] == "best":
        best_by = "subject" if len(slots["subject"]) > 1 else "dose"
    subjects = [Name(label=names.get(s, s)) for s in slots.get("subject") or []]
    comparator = None
    if g["type"] == "effect" and slots.get("comparator") not in (None, "placebo"):
        subjects.append(Name(label=names[slots["comparator"]]))       # effect vs a drug: [A, B], no comparator
    elif slots.get("comparator"):
        comparator = Name(label=slots["comparator"])
    measure = ""
    if slots.get("measure"):
        measure = f["measure"] if f else scoring.measure_names(DOMAIN, slots["measure"])["measure"]
    columns = list(g["open_columns"])
    trend_by = None
    if g["type"] == "trend":
        trend_by = g["answer"]["axis"]["key"]
        columns = sorted({*columns, trend_by})
    return Spec(qid=g["qid"], question="q", type=structured.SPEC_TYPE.get(g["type"], g["type"]), subjects=subjects,
                comparator=comparator, measure=Name(label=measure), fixed=fixed, columns=columns,
                open_points=[OpenPoint(id=c, question="?", choice="all") for c in columns],
                higher_is_better=g["answer"].get("higher_is_better"), best_by=best_by, trend_by=trend_by)


def gold_row(fid: str) -> Row:
    f = scoring.seed_facts(DOMAIN)[fid]
    s, e = scoring.l0_spans(DOMAIN, f["paper"])[fid][0]
    dec = len(f["value"].split(".")[1]) if "." in f["value"] else 0
    return Row(paper=f["paper"], subject=f["subject"], comparator=f["comparator"], measure=f["measure"],
               patient_group=f["context"], dose=f"{f['dose']} mg", time_point=f"week {f['week']}",
               std=StdValue(value=f["value"], unit=f["unit"], decimals=dec), raw=f["value"], quote=f["value"],
               quote_start=s, quote_end=e, quote_ok=True)


def make_run(root: Path, *, closed_book: bool = False, edit=None, qids: list[str] = QIDS) -> Path:
    """A run folder whose files are what a perfect pipeline would write; `edit(qid, spec, hits, rows)` breaks it."""
    cfg = RunConfig(name="fake", questions=qids, closed_book=closed_book)
    run = root / cfg.run_id()
    run.mkdir(parents=True)
    (run / "config.yaml").write_text(yaml.safe_dump(cfg.model_dump(mode="json")), encoding="utf-8")
    golds = scoring.gold(DOMAIN)
    for qid in qids:
        g = golds[qid]
        spec = gold_spec(g)
        rows = [] if closed_book else [gold_row(fid) for fid in g["row_ids"]]
        hits: dict[str, FindHit] = {}
        for r in rows:
            hits.setdefault(r.paper, FindHit(paper=r.paper)).passages.append(
                Passage(start=r.quote_start - 40, end=r.quote_end + 40, text="..."))
        if edit:
            edit(qid, spec, hits, rows)
        write_json(run / qid / "spec.json", spec)
        write_jsonl(run / qid / "find.jsonl", list(hits.values()))
        write_jsonl(run / qid / "rows.jsonl", rows)
        write_json(run / qid / "answer.json", answer.run(spec, rows))
    return run


def test_perfect_run_scores_one(tmp_path: Path) -> None:
    res = scoring.score_run(make_run(tmp_path))
    t = res["totals"]
    assert (tmp_path / res["run_id"] / "eval.json").is_file()
    for k in ("l0", "l1", "l1_paper", "l2_recall", "l2_precision", "l2_name_ok", "l2_complete", "l2_complete_upper",
              "l3", "advisor"):
        assert t[k] == 1.0, (k, t, {q: v["advisor"]["mismatches"] for q, v in res["questions"].items()})
    assert t["l3_exact"] == 4 and t["blame"]["none"] == t["facts"] > 0 and not res["closed_book"]


def test_missing_passage_is_blamed_on_find(tmp_path: Path) -> None:
    def edit(qid, spec, hits, rows):
        if qid == "Q-med-01":
            hits.pop("P-med-04")          # R-med-04-01's only paper
    q = scoring.score_run(make_run(tmp_path, edit=edit))["questions"]["Q-med-01"]
    blame = {f["id"]: f["blame"] for f in q["facts"]}
    assert blame["R-med-04-01"] == "find" and list(blame.values()).count("none") == 4
    assert q["l1"] == 0.8 and q["blame"]["find"] == 1


def test_wrong_value_is_blamed_on_extract(tmp_path: Path) -> None:
    def edit(qid, spec, hits, rows):
        if qid == "Q-med-02":
            rows[0].std = rows[0].std.model_copy(update={"value": "-0.9"})
    q = scoring.score_run(make_run(tmp_path, edit=edit))["questions"]["Q-med-02"]
    assert q["facts"][0]["blame"] == "extract" and q["l2"]["recall"] == 0.75 and q["l2"]["precision"] == 0.75
    assert q["l3"]["recall"] == 0.75 and not q["l3"]["exact"]


def test_wrong_slot_is_name_not_value(tmp_path: Path) -> None:
    def edit(qid, spec, hits, rows):
        if qid == "Q-med-02":
            rows[0].time_point = "week 52"
    q = scoring.score_run(make_run(tmp_path, edit=edit))["questions"]["Q-med-02"]
    f = q["facts"][0]
    assert f["l2"] and not f["name_ok"] and f["blame"] == "extract" and q["l2"]["recall"] == 1.0


def test_wrong_winner_fails_l3(tmp_path: Path) -> None:
    def edit(qid, spec, hits, rows):
        if qid == "Q-med-03":
            spec.higher_is_better = True      # the advisor got the direction wrong: 10 mg "wins"
    q = scoring.score_run(make_run(tmp_path, edit=edit))["questions"]["Q-med-03"]
    assert q["l3"]["score"] == 0.0 and not q["l3"]["exact"] and q["l3"]["groups"][0]["winner"] == "10 mg"
    assert q["l2"]["recall"] == 1.0 and q["blame"]["none"] == 3
    assert q["advisor"]["score"] < 1.0 and any("higher_is_better" in m for m in q["advisor"]["mismatches"])


def test_best_groups_and_patient_group_wording(tmp_path: Path) -> None:
    def edit(qid, spec, hits, rows):
        if qid == "Q-med-04":
            for r in rows:
                if "metformin" in r.patient_group:
                    r.patient_group = "Adults with T2D who are taking metformin"
    q = scoring.score_run(make_run(tmp_path, edit=edit))["questions"]["Q-med-04"]
    assert q["l3"]["score"] == 1.0 and {g["gold_status"] for g in q["l3"]["groups"]} == {"winner", "not_reported"}
    assert q["l2"]["name_ok"] == 1.0


def test_advisor_mismatches(tmp_path: Path) -> None:
    def edit(qid, spec, hits, rows):
        if qid == "Q-med-01":
            spec.columns = ["patient_group"]
            spec.fixed["time_point"] = "24 weeks"
    q = scoring.score_run(make_run(tmp_path, edit=edit))["questions"]["Q-med-01"]
    assert q["advisor"]["score"] < 1.0
    assert any("time_point" in m for m in q["advisor"]["mismatches"])


def test_closed_book_scores_about_zero(tmp_path: Path) -> None:
    run = make_run(tmp_path, closed_book=True)
    (run / "Q-med-04" / "answer.json").unlink()
    (run / "Q-med-04" / "rows.jsonl").unlink()
    res = scoring.score_run(run)
    t = res["totals"]
    assert res["closed_book"] and t["l1"] == t["l2_recall"] == t["l2_precision"] == t["l3"] == 0.0
    assert t["l0"] == 1.0 and t["blame"]["find"] == t["facts"]
    assert res["questions"]["Q-med-04"]["missing_files"] == ["rows.jsonl", "answer.json"]


def test_empty_run_folder(tmp_path: Path) -> None:
    res = scoring.score_run(tmp_path)            # no config, no question folders
    tests = [q for q, g in scoring.gold(DOMAIN).items() if g["split"] == "test"]   # 4 before the 100-question set
    assert res["totals"]["questions"] == len(tests) >= 4 and res["totals"]["l3"] == 0.0


def test_advisor_fixed_patient_group_is_checked_by_presence_not_wording(tmp_path: Path) -> None:
    def edit(qid, spec, hits, rows):
        if qid == "Q-med-03":
            spec.fixed["patient_group"] = "patients who already take metformin"   # the question's own words
    q = scoring.score_run(make_run(tmp_path, edit=edit))["questions"]["Q-med-03"]
    assert q["advisor"]["score"] == 1.0, q["advisor"]["mismatches"]


def test_measure_names_match_as_whole_phrases_without_a_word_list() -> None:
    fact = {"measure": "change in HbA1c from baseline", "measure_alt": []}
    assert structured.measure_ok("HbA1c", [], fact)
    assert not structured.measure_ok("change in body weight", [], fact)   # sharing "change" is not enough


# one question per dataset type: conflict, list, absent, out_of_scope, near_miss, effect vs a drug, trend, effect vs
# placebo, trend over dose
TYPED = ["Q-med-05", "Q-med-06", "Q-med-07", "Q-med-08", "Q-med-11", "Q-med-13", "Q-med-16", "Q-med-24", "Q-med-49"]


def test_perfect_run_of_every_type_scores_one(tmp_path: Path) -> None:
    res = scoring.score_run(make_run(tmp_path, qids=TYPED))
    t, qs = res["totals"], res["questions"]
    for qid, q in qs.items():
        assert q["l3"]["score"] == 1.0 and q["l3"]["exact"], (qid, q["l3"])
        assert q["advisor"]["score"] == 1.0, (qid, q["advisor"]["mismatches"])
    assert t["l3"] == 1.0 and t["l3_exact"] == t["answerable"] == 6
    assert t["not_reported"] == {"questions": 3, "accuracy": 1.0, "hallucination": 0.0, "near_miss_trap": 0.0,
                                 "near_miss_questions": 1}
    assert set(t["per_type"]) == {"conflict", "list", "absent", "out_of_scope", "near_miss", "effect", "trend"}
    nr = qs["Q-med-07"]
    assert nr["l0"] is None and nr["l1"] is None and nr["l2"]["recall"] is None and nr["facts"] == []
    assert t["l1"] == 1.0                                  # n/a questions stay out of the means
    assert res["intervals"]["l3"] == [1.0, 1.0] and res["intervals"]["l0"] == [1.0, 1.0]   # eval.json "intervals"
    assert list(res) == ["run_id", "domain", "config_name", "closed_book", "system", "unknown_questions", "totals",
                         "questions", "intervals", "data", "scorer"]
    assert len(res["scorer"]["source_sha256"]) == 64 and res["system"] == "evqa"
    assert set(res["data"]) == {"data_hash", "papers", "questions", "gold"}   # the data the score was made on


def test_near_miss_answer_with_the_closest_facts_is_a_trap(tmp_path: Path) -> None:
    def edit(qid, spec, hits, rows):
        if qid == "Q-med-11":                              # the obesity group answered with the plain group's rows
            rows.extend(gold_row(fid) for fid in scoring.gold(DOMAIN)[qid]["spec"]["extra"]["near"])
            spec.fixed.pop("patient_group", None)
    res = scoring.score_run(make_run(tmp_path, qids=["Q-med-11", "Q-med-07"], edit=edit))
    q = res["questions"]["Q-med-11"]["l3"]
    assert q["score"] == 0.0 and q["hallucination"] and q["near_miss_trap"] and len(q["trap_rows"]) == 4
    nr = res["totals"]["not_reported"]
    assert nr["accuracy"] == 0.5 and nr["hallucination"] == 0.5 and nr["near_miss_trap"] == 1.0


def test_effect_wrong_verdict_and_trend_wrong_direction_fail(tmp_path: Path) -> None:
    def edit(qid, spec, hits, rows):
        if qid in ("Q-med-13", "Q-med-24"):
            spec.higher_is_better = True                   # the better side flips
        if qid == "Q-med-16":
            rows[:] = [r for r in rows if r.paper != "P-med-14" or r.time_point != "week 24"]
    qs = scoring.score_run(make_run(tmp_path, qids=["Q-med-13", "Q-med-16", "Q-med-24"], edit=edit))["questions"]
    for qid in ("Q-med-13", "Q-med-24"):
        eff = qs[qid]["l3"]["effects"]
        assert all(e["value_ok"] and not e["verdict_ok"] for e in eff) and qs[qid]["l3"]["score"] == 0.0
    ser = qs["Q-med-16"]["l3"]["series"]
    assert [s["ok"] for s in ser] == [False, True] and not ser[0]["points_ok"]


def test_list_f1_and_conflict_needs_both_values(tmp_path: Path) -> None:
    def edit(qid, spec, hits, rows):
        if qid == "Q-med-06":
            rows[:] = [r for r in rows if r.paper != "P-med-04"]
        if qid == "Q-med-05":
            rows[:] = [r for r in rows if r.paper != "P-med-08"]   # one side of the conflict lost
    qs = scoring.score_run(make_run(tmp_path, qids=["Q-med-05", "Q-med-06"], edit=edit))["questions"]
    assert qs["Q-med-06"]["l3"]["recall"] == round(2 / 3, 4) and qs["Q-med-06"]["l3"]["precision"] == 1.0
    assert qs["Q-med-05"]["l3"]["score"] == 0.0 and qs["Q-med-05"]["l3"]["flagged"] == 0


def test_advisor_accepts_effect_against_a_drug_as_two_subjects(tmp_path: Path) -> None:
    q = scoring.score_run(make_run(tmp_path, qids=["Q-med-13"]))["questions"]["Q-med-13"]
    assert q["advisor"]["score"] == 1.0, q["advisor"]["mismatches"]


def test_settings_are_scored_by_provenance_not_by_the_label(tmp_path: Path) -> None:
    """A right value at the right place counts whatever words label its patients; the label is the judge's job."""
    def relabel(qid, spec, hits, rows):
        new = {c: f"study cohort {n}" for n, c in enumerate(scoring.contexts(DOMAIN))}   # no seed words
        for r in rows:
            r.patient_group = new[r.patient_group]
        if "patient_group" in spec.fixed:
            spec.fixed["patient_group"] = new[spec.fixed["patient_group"]]
    res = scoring.score_run(make_run(tmp_path, edit=relabel))
    assert res["totals"]["l3"] == 1.0 and res["totals"]["l2_name_ok"] == 1.0


def test_an_item_pooling_two_contexts_matches_no_gold_context(tmp_path: Path) -> None:
    facts = scoring.seed_facts(DOMAIN)
    by_ctx: dict[str, str] = {}
    for fid, f in facts.items():
        by_ctx.setdefault(f["context"], fid)
    a, b = list(by_ctx.values())[:2]
    rows = [gold_row(a), gold_row(b)]
    gold = scoring.Gold(scoring.GoldFile.model_validate(scoring.gold_file(DOMAIN, "test", [])))
    prov = structured.Provenance([structured.Row.model_validate(r.model_dump()) for r in rows], gold)
    assert prov.value("patient_group", [0]) == facts[a]["context"]
    assert prov.value("patient_group", [0, 1]) == "?"


def test_label_judge_is_blind_and_reported_apart(tmp_path: Path) -> None:
    import json as _json

    run = make_run(tmp_path, qids=["Q-med-01"])
    scoring.score_run(run)
    seen: list[str] = []

    def ask(body: dict) -> str:
        seen.append("\n".join(m["content"] for m in body["messages"]))
        return _json.dumps({"verdict": "matches", "reason": "same patients"})
    out = scoring.judge_run(run, chat=Chat("fake", send=ask, cache=False))
    ev = _json.loads((run / "eval.json").read_text())
    assert ev["label_judge"]["items"] == out["items"] > 0 and out["counts"]["matches"] == out["items"]
    assert ev["totals"]["l3"] == 1.0                                   # provenance scores untouched
    assert seen and all("R-med" not in p and "eval" not in p.lower() for p in seen)   # no ids, no scores


# ---------------------------------------------------------------- paper recall, complete facts, L0 gaps (21 Nov 2026)
def test_right_paper_wrong_passage_gets_paper_recall_not_span_recall(tmp_path: Path) -> None:
    def edit(qid, spec, hits, rows):
        if qid == "Q-med-01":
            hits["P-med-04"].passages = [Passage(start=0, end=10, text="title")]   # right paper, wrong passage
    q = scoring.score_run(make_run(tmp_path, qids=["Q-med-01"], edit=edit))["questions"]["Q-med-01"]
    blame = {f["id"]: f["blame"] for f in q["facts"]}
    assert blame["R-med-04-01"] == "find" and q["l1"] == 0.8
    assert "P-med-04" in q["papers"]["found"] and q["l1_paper"] == 1.0


def test_paper_recall_counts_distinct_papers_and_skips_screened_out_hits(tmp_path: Path) -> None:
    golds = scoring.gold(DOMAIN)

    def edit(qid, spec, hits, rows):
        if hits:
            hits[sorted(hits)[0]].screen = "no"           # Extract does not read a screened-out paper
    res = scoring.score_run(make_run(tmp_path, qids=["Q-med-01", "Q-med-07"], edit=edit))
    q = res["questions"]["Q-med-01"]
    n = len({scoring.seed_facts(DOMAIN)[r]["paper"] for r in golds["Q-med-01"]["row_ids"]})
    assert len(q["papers"]["gold"]) == n and q["l1_paper"] == round((n - 1) / n, 4)
    nr = res["questions"]["Q-med-07"]                     # not reported: no gold papers, n/a, out of the mean
    assert nr["l1_paper"] is None and res["totals"]["counts"]["l1_paper_na_questions"] == 1
    assert res["totals"]["l1_paper"] == q["l1_paper"]


def test_right_number_wrong_qualifier_is_not_a_complete_fact(tmp_path: Path) -> None:
    def edit(qid, spec, hits, rows):
        if qid == "Q-med-02":
            rows[0].time_point = "week 52"                # value, quote and paper right; time point wrong
            rows[1].comparator = None                     # comparator not extracted
    q = scoring.score_run(make_run(tmp_path, qids=["Q-med-02"], edit=edit))["questions"]["Q-med-02"]
    f0, f1 = q["facts"][0], q["facts"][1]
    assert f0["l2"] and f0["complete"] == "incomplete" and f0["complete_checks"]["time_point"] == "fail"
    assert f1["l2"] and f1["complete"] == "incomplete" and f1["complete_checks"]["comparator"] == "fail"
    assert q["l2"]["recall"] == 1.0 and q["l2"]["complete"] == q["l2"]["complete_upper"] == 0.5


def test_population_is_read_from_the_row_not_from_provenance(tmp_path: Path) -> None:
    ctxs = scoring.contexts(DOMAIN)

    def edit(qid, spec, hits, rows):
        if qid == "Q-med-02":
            other = next(c for c in ctxs if c != rows[0].patient_group)
            rows[0].patient_group = rows[0].patient_group_raw = other          # another seed group: fail
            rows[1].patient_group = "study cohort A"                           # other words: unverified
            rows[2].patient_group = None                                       # no group: fail
    res = scoring.score_run(make_run(tmp_path, qids=["Q-med-02"], edit=edit))
    q = res["questions"]["Q-med-02"]
    pop = [f["complete_checks"]["population"] for f in q["facts"]]
    assert pop == ["fail", "unverified", "fail", "pass"]
    assert [f["complete"] for f in q["facts"]] == ["incomplete", "pending", "incomplete", "complete"]
    assert q["l2"]["recall"] == 1.0 and q["l2"]["complete"] == 0.25 and q["l2"]["complete_upper"] == 0.5
    c = res["totals"]["counts"]
    assert c["l2_complete"] == 1 and c["l2_complete_pending"] == 1
    assert c["complete_field_fail"]["population"] == 2 and c["complete_field_unverified"]["population"] == 1


def test_facts_without_an_l0_span_are_counted(tmp_path: Path, monkeypatch) -> None:
    real = scoring.l0_facts

    def no_span(domain, paper):
        return {k: ({**v, "spans": []} if k == "R-med-04-01" else v) for k, v in real(domain, paper).items()}
    run = make_run(tmp_path, qids=["Q-med-01"])
    monkeypatch.setattr(scoring, "l0_facts", no_span)
    res = scoring.score_run(run, write=False)
    assert not (run / "eval.json").exists()               # write=False keeps a saved eval.json untouched
    t = res["totals"]
    assert t["l0_missing_facts"] == t["counts"]["l0_missing"] == t["blame"]["L0"] == 1
    q = res["questions"]["Q-med-01"]
    assert q["l1"] == 0.8 and q["l1_paper"] == 1.0          # paper recall does not need L0


def test_population_judge_settles_only_unverified_and_is_blind(tmp_path: Path) -> None:
    import json as _json

    def edit(qid, spec, hits, rows):
        rows[0].patient_group = rows[0].patient_group_raw = "study cohort A"   # other words: unverified
        rows[1].patient_group = rows[1].patient_group_raw = "study cohort B"
    run = make_run(tmp_path, qids=["Q-med-02"], edit=edit)
    scoring.score_run(run)
    before = (run / "eval.json").read_text()
    seen: list[str] = []

    def ask(body: dict) -> str:
        prompt = "\n".join(m["content"] for m in body["messages"])
        seen.append(prompt)
        verdict = "matches" if "cohort A" in prompt else "does not match"
        return _json.dumps({"verdict": verdict, "reason": "r"})
    out = scoring.judge_population(run, chat=Chat("fake", send=ask, cache=False))
    assert out["items"] == 2 and out["counts"]["matches"] == 1 and out["counts"]["does not match"] == 1
    assert out["l2_complete"] == 0.5 and out["l2_complete_upper"] == 1.0 and out["l2_complete_judged"] == 0.75
    assert (run / "eval.json").read_text() == before and (run / "population_judge.json").is_file()
    assert seen and all("R-med" not in p and "eval" not in p.lower() for p in seen)   # no ids, no scores
