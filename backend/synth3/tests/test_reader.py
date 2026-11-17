"""synth3.reader: a perfect reader passes, named problems are found, the prompt input hides the planted names.
Every model is a fake; none is a live call."""
import json

from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from modelcall import JsonlCache
from synth3.cli import main
from synth3.reader import Claim, ReaderNotes, Row, check_notes, read_folder, read_paper
from synth3.realcorpus import build_real_folder
from synth3.tests.conftest import approved, supported
from synth3.world import Study


def reply(notes: ReaderNotes) -> ModelResponse:
    return ModelResponse(parts=[TextPart(notes.model_dump_json())])   # the cluster models answer in native JSON


def empty_notes() -> ReaderNotes:
    return ReaderNotes(label=None, setting=None, results=[], claims=[])


def scripted(*notes: ReaderNotes) -> FunctionModel:
    calls = []

    def answer(messages, info):
        calls.append(1)
        return reply(notes[len(calls) - 1])
    return FunctionModel(answer, model_name="fake")


def _line(text: str, start: int, end: int) -> str:
    return text[text.rfind("\n", 0, start) + 1:(text.find("\n", end) if text.find("\n", end) >= 0 else len(text))]


def perfect(study: Study, spec, folder) -> ReaderNotes:
    """The notes a perfect reader gives: the truth, each quote cut from the paper by placement."""
    text = (folder / "papers" / f"{study.id}.md").read_text(encoding="utf-8")
    truth = json.loads((folder / "ground_truth.json").read_text(encoding="utf-8"))
    spans = {p["fact"]: (p["start"], p["end"]) for p in truth["placements"] if p["paper"] == study.id}
    label = {a.id: a.label for a in spec.arms}
    level = {lv.id: lv.name for c in spec.conditions for lv in c.levels}
    rows = []
    for cell in study.cells:
        m = spec.measure(cell.measure)
        for r in cell.results:
            first = spans[f"{study.id}.c{cell.index}.{r.arm}.{'k' if m.kind == 'count' else 'mean'}"]
            rows.append(Row(arm=label[r.arm], subgroup=[level[cell.levels[c.id]] for c in spec.conditions],
                            measure=m.name, k=r.k, n=r.n, mean=r.mean, sd=r.sd, quote=_line(text, *first)))
    claims = []
    for key, word in study.claims.items():
        a, b, m = key.split("|")
        start, end = spans[f"{study.id}.claim.{a}.{b}.{m}.conclusion"]
        claims.append(Claim(arm=label[a], against=label[b], measure=spec.measure(m).name, direction=word,
                            quote=text[start:end]))
    return ReaderNotes(label=study.label, setting=study.setting, results=rows, claims=claims)


def test_a_perfect_reader_passes_every_paper(tmp_path, SPEC, REAL, pool):
    build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 1), 40, "table", REAL, pool)
    truth = json.loads((tmp_path / "r" / "ground_truth.json").read_text(encoding="utf-8"))
    studies = [Study.parse(s) for s in truth["studies"]]
    out = read_folder(tmp_path / "r", SPEC, scripted(*[perfect(s, SPEC, tmp_path / "r") for s in studies]),
                      tmp_path / "calls.jsonl")
    assert out["ok"] == out["papers"] == 40
    assert json.loads((tmp_path / "r" / "real" / "reader-check.json").read_text())["ok"] == 40
    assert set(json.loads((tmp_path / "r" / "real" / "reader.json").read_text())) == {s.id for s in studies}


def test_a_missing_row_a_false_quote_and_a_contradiction_are_named(tmp_path, SPEC, REAL, pool):
    build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 1), 40, "table", REAL, pool)
    s = supported(SPEC, 1)[0]
    text = (tmp_path / "r" / "papers" / f"{s.id}.md").read_text(encoding="utf-8")
    good = perfect(s, SPEC, tmp_path / "r")
    assert check_notes(good, s, SPEC, text)["ok"]
    dropped = good.model_copy(update={"results": good.results[1:]})
    fake = good.model_copy(update={"claims": [good.claims[0].model_copy(update={"quote": "never said"})]})
    extra = good.model_copy(update={"results": [*good.results, good.results[0].model_copy(update={"n": 7})]})
    assert any("missing" in p for p in check_notes(dropped, s, SPEC, text)["problems"])
    assert any("quote" in p for p in check_notes(fake, s, SPEC, text)["problems"])
    assert any("not planted" in p for p in check_notes(extra, s, SPEC, text)["problems"])


def test_label_setting_direction_and_other_rows(tmp_path, SPEC, REAL, pool):
    build_real_folder(tmp_path / "r", SPEC, approved(SPEC, 1), 40, "table", REAL, pool)
    s = supported(SPEC, 1)[0]
    text = (tmp_path / "r" / "papers" / f"{s.id}.md").read_text(encoding="utf-8")
    good = perfect(s, SPEC, tmp_path / "r")
    flipped = good.claims[0].model_copy(update={"direction": "hurts" if good.claims[0].direction == "helps" else "helps"})
    bad = good.model_copy(update={"label": "Nobody (1999)", "setting": None, "claims": [flipped, *good.claims[1:]]})
    problems = check_notes(bad, s, SPEC, text)["problems"]
    assert any("label" in p for p in problems) and any("setting" in p for p in problems)
    assert any("another direction" in p for p in problems)
    stray = good.results[0].model_copy(update={"arm": "Some real drug", "n": 3})
    out = check_notes(good.model_copy(update={"results": [*good.results, stray]}), s, SPEC, text)
    assert out["ok"] and out["other_results"] == 1


def test_the_prompt_input_hides_the_planted_names(tmp_path, SPEC):
    seen = []
    model = FunctionModel(lambda messages, info: seen.append(messages) or reply(empty_notes()))
    read_paper("# T\n\nSome text.", SPEC, model, JsonlCache(tmp_path / "c.jsonl"))
    sent = str(seen[0])
    assert all(a.label not in sent for a in SPEC.arms) and all(m.name in sent for m in SPEC.measures)


def test_reader_by_command(tmp_path, spec_dir, monkeypatch):
    seen = {}
    monkeypatch.setattr("synth3.cli.read_folder", lambda folder, spec, model, cache: seen.update(
        folder=folder, cache=cache, model=model.model_name) or {"papers": 3, "ok": 2, "other_results": 5})
    assert main(["reader", "--domain", "demo", "--spec-root", str(spec_dir), "--folder", str(tmp_path / "f")]) == 0
    assert seen["cache"] == tmp_path / "f" / "real" / "reader-calls.jsonl" and seen["model"] == "sub-model-1"
