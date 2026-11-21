import json
from modelcall.dspy_lm import RecordedLM
from evqa.contracts import Dimension, Row
from evqa.spec.dimensions_v3 import DraftDimension, checked
from evqa.extract.settings_v2 import DraftSet, check, read, assign


def test_fixed_quote_and_key_are_checked():
    dims, failures = checked([DraftDimension(key="temperature", question="Where?", why="matters",
        fixed_value="500 C", quote="at 500 C"), DraftDimension(key="temperature", question="X?", why="X")],
        "Strength at 500 C?")
    assert len(dims) == 1 and len(failures) == 1
    dims, failures = checked([DraftDimension(key="temperature", question="Where?", why="matters",
        fixed_value="600 C", quote="500 C")], "Strength at 500 C?")
    assert not dims and failures


def test_setting_requires_source_and_value():
    d = [Dimension(key="temperature", question="Temperature?", why="matters")]
    draft = DraftSet.model_validate({"settings":[{"dimension":"temperature", "value":"600 C",
        "quote":"Tested at 500 C.", "source":"paper"}]})
    result, errors = check("P", d, [draft], "Tested at 500 C.")
    assert errors and result[0].settings[0].value == "not stated"


def test_repair_then_assign_and_unknown_selection():
    d = [Dimension(key="temperature", question="Temperature?", why="matters")]
    source = "Tested at 500 C."
    responses = [{"setting_sets":[{"settings":[{"dimension":"temperature","value":"600 C","quote":source}]}]},
                 {"setting_sets":[{"settings":[{"dimension":"temperature","value":"500 C","quote":source}]}]},
                 {"verdicts":[{"id":"0:0","supported":True}]}]
    seen = []
    def ask(prompt):
        seen.append(prompt)
        return json.dumps(responses.pop(0))
    model = RecordedLM("fake", ask)
    sets = read("P", d, source, source, source, model)
    assert len(seen) == 3 and "Failed checks" in seen[1] and sets[0].settings[0].value == "500 C"
    row = Row(paper="P", subject="alloy", measure="strength", raw="1", quote="1")
    assign(row, sets, "Results", model)
    assert row.settings == "P/setting1" and row.setting_set.label == "500 C"


def test_extra_dimension_requires_two_distinct_result_rows():
    from evqa.extract.settings_v2 import retain_extras
    dims = [Dimension(key="dose", question="Dose?", why="varies")]
    source = "Dose 3 mg: fasting -1. Dose 3 mg: fed -2."
    draft = [DraftSet.model_validate({"settings":[{"dimension":"dose","value":"3 mg","quote":source}],
        "extra_settings":[{"dimension":"meal_state","value":v,"quote":q}]}) for v, q in
        [("fasting", "Dose 3 mg: fasting -1."), ("fed", "Dose 3 mg: fed -2.")]]
    sets, errors = check("P", dims, draft, source)
    assert not errors
    rows = [Row(paper="P", subject="A", measure="M", raw="1", quote=q, quote_ok=True)
            for q in ("Dose 3 mg: fasting -1.", "Dose 3 mg: fed -2.")]
    assert retain_extras(rows, sets) == {"meal_state"}
    assert {s.value for g in sets for s in g.settings if s.extra} == {"fasting", "fed"}
    assign(rows[0], sets, "", RecordedLM("fake", lambda _: "{}"))
    assign(rows[1], sets, "", RecordedLM("fake", lambda _: "{}"))
    assert rows[0].settings != rows[1].settings


def test_answer_displays_extra_and_does_not_pool_values():
    from evqa.answer.core import run
    from evqa.contracts import Name, Spec, StdValue, Setting, SettingSet
    spec = Spec(qid="Q", question="How much?", type="lookup", subjects=[Name(label="A")],
                measure=Name(label="M"), columns=[])
    rows = []
    for i, value in enumerate(("fasting", "fed")):
        setting = Setting(dimension="meal_state", value=value, quote=value, source="row", extra=True)
        group = SettingSet(id=f"P/setting{i}", paper="P", settings=[setting], label=value)
        rows.append(Row(paper="P", subject="A", measure="M", raw="1", quote=value, quote_ok=True,
                        std=StdValue(value="1", unit="", decimals=0), settings=group.id, setting_set=group))
    answer = run(spec, rows)
    column = "meal_state (found in the papers, not asked)"
    assert column in answer.columns
    assert {item.cells[column] for item in answer.table} == {"fasting", "fed"}


def test_extra_is_not_kept_when_only_one_value_is_in_a_checked_result():
    from evqa.extract.settings_v2 import retain_extras
    dims = [Dimension(key="dose", question="Dose?", why="varies")]
    source = "Dose 3 mg: fasting -1. Dose 3 mg: fed -2."
    drafts = [DraftSet.model_validate({"settings":[{"dimension":"dose","value":"3 mg","quote":source}],
        "extra_settings":[{"dimension":"meal_state","value":v,"quote":q}]}) for v, q in
        [("fasting", "Dose 3 mg: fasting -1."), ("fed", "Dose 3 mg: fed -2.")]]
    sets, _ = check("P", dims, drafts, source)
    rows = [Row(paper="P", subject="A", measure="M", raw="1", quote="Dose 3 mg: fasting -1.", quote_ok=True),
            Row(paper="P", subject="A", measure="M", raw="2", quote="Dose 3 mg: fed -2.", quote_ok=False)]
    assert retain_extras(rows, sets) == set()
    assert all(not s.extra for group in sets for s in group.settings)


def test_multiple_extra_values_in_one_set_are_separated_by_checked_rows():
    from evqa.extract.settings_v2 import retain_extras
    from evqa.contracts import Setting, SettingSet
    one = Setting(dimension="meal_state", value="fasting", quote="fasting", source="row", extra=True)
    two = Setting(dimension="meal_state", value="fed", quote="fed", source="row", extra=True)
    sets = [SettingSet(id="P/setting1", paper="P", settings=[one, two])]
    rows = [Row(paper="P", subject="A", measure="M", raw="1", quote=q, quote_ok=True) for q in ("fasting", "fed")]
    assert retain_extras(rows, sets) == {"meal_state"}
    model = RecordedLM("fake", lambda _: "{}")
    for row in rows:
        assign(row, sets, "", model)
    assert rows[0].settings != rows[1].settings
    assert [row.setting_set.settings[0].value for row in rows] == ["fasting", "fed"]


def test_trace_keeps_every_attempt_and_failed_check():
    d = [Dimension(key="temperature", question="Temperature?", why="matters")]
    source = "Tested at 500 C."
    responses = [{"setting_sets":[{"settings":[{"dimension":"temperature","value":"600 C","quote":source}]}]},
                 {"setting_sets":[{"settings":[{"dimension":"temperature","value":"500 C","quote":source}]}]},
                 {"verdicts":[{"id":"0:0","supported":False}]}]
    trace: list[dict] = []
    sets = read("P", d, source, source, source, RecordedLM("fake", lambda _: json.dumps(responses.pop(0))),
                trace=trace)
    assert [t["attempt"] for t in trace] == [0, 1]
    assert trace[0]["drafts"][0]["settings"][0]["value"] == "600 C"
    assert trace[0]["check_failures"] == ["set 1 temperature: value is not copied from quote"]
    assert trace[1]["verifier"]["verdicts"] == [{"id": "0:0", "supported": False}]
    assert trace[1]["verifier_failures"] and not trace[1]["accepted"]
    assert sets[0].settings[0].value == "not stated"


def test_run_saves_settings_audit(tmp_path, monkeypatch):
    from evqa import corpus, lm, run as runner
    from evqa.contracts import Answer, FindHit, Name, Passage, RunConfig, Spec
    monkeypatch.setattr(lm, "CACHE_FILE", tmp_path / "cache.jsonl")
    monkeypatch.setattr(lm, "_caches", {})
    monkeypatch.setattr(corpus, "questions", lambda domain, split: [{"qid": "Q1", "question": "How much?"}])
    steps = {
        "spec": lambda q, cfg: Spec(qid="Q1", question="How much?", type="lookup", subjects=[Name(label="d")],
                                    measure=Name(label="m")).seal(),
        "find": lambda spec, domain, cfg: [FindHit(paper="P1", passages=[Passage(start=0, end=3, text="abc")])],
        "extract": lambda spec, hits, domain, cfg, audit=None: audit.append({"paper": "P1", "attempts": []}) or [],
        "answer": lambda spec, rows: Answer(qid="Q1", type="lookup", not_reported=True)}
    monkeypatch.setattr(runner, "_step", lambda name: steps[name])
    out = runner.run(RunConfig(name="t"), root=tmp_path)
    assert json.loads((out / "Q1" / "settings.jsonl").read_text()) == {"paper": "P1", "attempts": []}


def test_quote_with_line_break_and_en_dash_is_found_with_offsets():
    paper = "Specimens were tested at\n500 C. The anneal lasted 2–4 hours."
    d = [Dimension(key="temperature", question="Temperature?", why="matters"),
         Dimension(key="anneal_time", question="Anneal time?", why="matters")]
    draft = DraftSet.model_validate({"settings": [
        {"dimension": "temperature", "value": "500 C", "quote": "tested at 500 C"},
        {"dimension": "anneal_time", "value": "2-4 hours", "quote": "The anneal lasted 2-4 hours."}],
        "extra_settings": [{"dimension": "atmosphere", "value": "500 C", "quote": "tested at 500 C"}]})
    result, errors = check("P", d, [draft], paper)
    assert not errors
    temp, anneal = result[0].settings[0], result[0].settings[1]
    assert (temp.value, anneal.value) == ("500 C", "2-4 hours")
    assert paper[temp.start:temp.end] == "tested at\n500 C"
    assert paper[anneal.start:anneal.end] == "The anneal lasted 2–4 hours."
    assert result[0].settings[2].extra and result[0].settings[2].start == temp.start


def test_not_stated_setting_first_or_middle_keeps_offsets_right():
    # Haiku practice run, 21 Nov: a "not stated" setting first crashed check() (offsets of no quote); in the middle
    # it reused the previous setting's offsets.
    paper = "Adults with type 2 diabetes took metformin. Outcomes at week 24."
    dims = [Dimension(key=k, question=f"{k}?", why="matters") for k in ("age_group", "condition", "weight", "time")]
    draft = DraftSet.model_validate({"settings": [
        {"dimension": "age_group", "value": "not stated", "quote": "", "source": "paper"},
        {"dimension": "condition", "value": "type 2 diabetes", "quote": "Adults with type 2 diabetes", "source": "paper"},
        {"dimension": "weight", "value": "not stated", "quote": "", "source": "paper"},
        {"dimension": "time", "value": "week 24", "quote": "Outcomes at week 24", "source": "paper"}]})
    result, errors = check("P", dims, [draft], paper)
    assert not errors
    got = {s.dimension: s for s in result[0].settings}
    assert got["age_group"].value == got["weight"].value == "not stated"
    assert got["age_group"].start is None and got["weight"].start is None
    assert paper[got["condition"].start:got["condition"].end] == "Adults with type 2 diabetes"
    assert paper[got["time"].start:got["time"].end] == "Outcomes at week 24"


def test_sets_that_differ_only_in_extras_are_assigned_by_code():
    from evqa.contracts import Setting, SettingSet
    base = [Setting(dimension="age_group", value="adults aged 65 years or older", quote="adults aged 65 years or older")]
    sets = [SettingSet(id=f"P/setting{i}", paper="P", label="x", settings=base + [
        Setting(dimension="arm", value=v, quote=v, extra=True)]) for i, v in enumerate(["drug A 25 mg", "drug B 25 mg"], 1)]
    row = Row(paper="P", subject="drug B", measure="HbA1c", raw="-0.5", quote="The values are -0.5 and -0.3.")

    def ask(prompt):
        raise AssertionError("no model call expected")
    assign(row, sets, "Results", RecordedLM("fake", ask))
    assert row.settings == "P/setting1" and "shared settings taken" in row.note
    assert [x.dimension for x in row.setting_set.settings] == ["age_group"]     # no other arm's extra on this row
