"""The names step (`Settings.names`, D38): after every document is merged, the names of the items whose type has a
name field are grouped corpus-wide (evidence/names.py), and a model check asks about each name no step matched.
`off` (the default, runs before it) writes nothing new; `on` writes names.json and counts `unresolved_names` in
funnel.json and run.json, as `dangling_links` is counted. A model "same" counts only with a verbatim quote, and the
check's calls are recorded, so a replay never calls a model."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models.function import AgentInfo, FunctionModel

from evidence import engine
from evidence.extractors import gliner
from evidence.names import Match, Mention, NameGroups, confirm_leftovers, group_names
from evidence.pack import protocol_path
from evidence.replay import replay

from .conftest import PROTOCOL, corpus_of, make_corpus, prompt_of, respond, scripted, screen_yes

INVENTORY = protocol_path("rag", "inv-methods")
PAPER = "# Agents on NQ\n\nWe test Agent Z, also called Zeta, on NQ.\n\nThe system answers 70% of the questions.\n"
NAMES_MARK = "You decide whether one name"     # the first words of prompts/names-confirm-v1.md


@pytest.fixture(autouse=True)
def no_gliner(monkeypatch: pytest.MonkeyPatch) -> None:
    gliner.forget()
    monkeypatch.delenv("GLINER_URL", raising=False)


def run_json(run: Path) -> dict[str, Any]:
    return json.loads((run / "run.json").read_text(encoding="utf-8"))


def funnel_json(run: Path) -> dict[str, Any]:
    return json.loads((run / "funnel.json").read_text(encoding="utf-8"))


def answer_json(run: Path) -> dict[str, Any]:
    return json.loads((run / "answer.json").read_text(encoding="utf-8"))


def regex_names_run(tmp_path: Path, names: str) -> Path:
    settings = engine.Settings(corpus=str(make_corpus(tmp_path / "corpus")), cache=str(tmp_path / "cache"),
                               selection="regex-only", strategy="all", names=names)  # type: ignore[arg-type]
    return engine.execute_run(PROTOCOL.read_bytes(), settings, tmp_path / "runs", provider=None)


def agent_script(kind: str, _doc: str, prompt: str) -> dict[str, Any]:
    if kind == "screen":
        return screen_yes(prompt)
    if kind == "condition":
        return {"items": [{"fields": {"label": "Agent Z"}, "quotes": {"condition_label": "Agent Z"}},
                          {"fields": {"label": "Zeta"}, "quotes": {"condition_label": "Zeta"}}]}
    return {"items": []} if kind != "retry" else {"quotes": []}


def with_names(reply: dict[str, Any], asked: list[str]) -> FunctionModel:
    """The scripted reader of PAPER; a names-check prompt gets `reply` and is appended to `asked`."""
    inner = scripted(agent_script, [])

    def function(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if NAMES_MARK in (info.instructions or ""):
            asked.append(prompt_of(messages))
            return respond(info, reply)
        return inner.function(messages, info)  # type: ignore[misc]
    return FunctionModel(function, model_name="scripted")


def inventory_run(tmp_path: Path, names: str, reply: dict[str, Any], asked: list[str]) -> Path:
    if not (tmp_path / "corpus").exists():
        corpus_of(tmp_path / "corpus", {"P1": PAPER})
    settings = engine.Settings(corpus=str(tmp_path / "corpus"), cache=str(tmp_path / "cache"), model="scripted-alias",
                               selection="llm-only", strategy="all", names=names)  # type: ignore[arg-type]
    model = with_names(reply, asked)
    return engine.execute_run(INVENTORY.read_bytes(), settings, tmp_path / "runs", provider=lambda _alias: model)


SAME = {"same": True, "quote": "Agent Z, also called Zeta"}


# --- the engine step ---------------------------------------------------------------------------------------

def test_names_off_writes_nothing_new(tmp_path: Path) -> None:
    out = regex_names_run(tmp_path, "off")
    assert not (out / "names.json").exists() and "unresolved_names" not in run_json(out)
    assert "unresolved_names" not in funnel_json(out) and "names" not in run_json(out)["settings"]
    assert "names.json" not in run_json(out)["outputs"]


def test_names_on_writes_groups_and_count(tmp_path: Path) -> None:
    out = regex_names_run(tmp_path, "on")
    data = json.loads((out / "names.json").read_text(encoding="utf-8"))
    assert set(data) == {"groups", "matches", "unresolved"}
    assert run_json(out)["unresolved_names"] == len(data["unresolved"]) == funnel_json(out)["unresolved_names"]
    assert run_json(out)["settings"]["names"] == "on" and "names.json" in run_json(out)["outputs"]


def test_names_off_and_on_give_the_same_effect_answer(tmp_path: Path) -> None:
    """An effect answer reads sides and canonical metrics, not names: the names step leaves it byte-identical."""
    off, on = regex_names_run(tmp_path / "a", "off"), regex_names_run(tmp_path / "b", "on")
    assert (off / "answer.json").read_bytes() == (on / "answer.json").read_bytes()


def test_model_check_joins_leftovers_and_the_inventory_answer_follows(tmp_path: Path) -> None:
    asked: list[str] = []
    off = inventory_run(tmp_path / "off", "off", SAME, asked)
    assert asked == [] and sorted(e["name"] for e in answer_json(off)["entries"]) == ["Agent Z", "Zeta"]
    on = inventory_run(tmp_path / "on", "on", SAME, asked)
    assert len(asked) == 1 and "Agent Z" in asked[0] and "Zeta" in asked[0]
    data = json.loads((on / "names.json").read_text(encoding="utf-8"))
    assert data["unresolved"] == [] and run_json(on)["unresolved_names"] == 0
    assert {(m["mention"]["name"], m["step"], m["quote"]) for m in data["matches"]} == {
        ("Agent Z", "model", SAME["quote"]), ("Zeta", "model", SAME["quote"])}
    [entry] = answer_json(on)["entries"]
    assert (entry["name"], entry["aliases"]) == ("Zeta", ["Agent Z"])
    checks = [e for e in map(json.loads, (on / "events.jsonl").read_text(encoding="utf-8").splitlines())
              if e["subtype"] == "names"]
    assert len(checks) == 1 and checks[0]["custom_metadata"]["unresolved"] == 0
    assert run_json(on)["cost"]["model_calls"] >= 1 + 2      # the screen, the condition call and the names check


def test_model_check_without_a_verbatim_quote_leaves_them_unresolved(tmp_path: Path) -> None:
    run = inventory_run(tmp_path, "on", {"same": True, "quote": "Agent Z is Zeta"}, [])
    assert run_json(run)["unresolved_names"] == 2
    assert len(answer_json(run)["entries"]) == 2


def test_replay_repeats_the_names_step_without_a_model(tmp_path: Path) -> None:
    asked: list[str] = []
    run = inventory_run(tmp_path, "on", SAME, asked)
    _, report = replay(run)       # replay has no provider: the names check comes from the record cache
    assert report["ok"], report
    assert len(asked) == 1


def test_a_second_run_reads_the_names_check_from_the_cache(tmp_path: Path) -> None:
    asked: list[str] = []
    inventory_run(tmp_path, "on", SAME, asked)
    again = engine.execute_run(INVENTORY.read_bytes(), engine.Settings(
        corpus=str(tmp_path / "corpus"), cache=str(tmp_path / "cache"), model="scripted-alias", selection="llm-only",
        strategy="all", names="on"), tmp_path / "runs2", provider=lambda _alias: with_names(SAME, asked))
    assert len(asked) == 1 and run_json(again)["unresolved_names"] == 0


@pytest.mark.parametrize("names", ["on", "off"])
def test_replay_repeats_names_setting(tmp_path: Path, names: str) -> None:
    _, report = replay(regex_names_run(tmp_path, names))
    assert report["ok"], report


def test_cli_names_default_off() -> None:
    from evidence.cli import _parser
    assert _parser().parse_args(["run", "--protocol", "p", "--corpus", "c"]).names == "off"
    assert _parser().parse_args(["run", "--protocol", "p", "--corpus", "c", "--names", "on"]).names == "on"


# --- confirm_leftovers -------------------------------------------------------------------------------------

TEXT = "Agent Z was tested. Zeta answers well."
LEFTOVER = group_names([Mention("Agent Z", "p1", 0, 7, "condition"), Mention("Zeta", "p1", 20, 24, "condition")],
                       {"p1": TEXT})


def test_model_match_needs_a_verbatim_quote() -> None:
    g = confirm_leftovers(LEFTOVER, {"p1": "Agent Z was tested."}, ask=lambda _: '{"same": true, "quote": "not in text"}')
    assert g.unresolved == LEFTOVER.unresolved


@pytest.mark.parametrize("reply", ['{"same": true, "quote": ""}', '{"same": false, "quote": "Agent Z"}', "not json",
                                   '{"same": "yes", "quote": "Agent Z"}', '{"error": "no model provider"}'])
def test_anything_but_a_quoted_yes_is_no(reply: str) -> None:
    assert confirm_leftovers(LEFTOVER, {"p1": TEXT}, ask=lambda _: reply) == LEFTOVER


def test_quoted_yes_joins_the_leftover_into_the_candidate_group() -> None:
    prompts: list[str] = []

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return json.dumps({"same": True, "quote": "Zeta answers well"})
    g = confirm_leftovers(LEFTOVER, {"p1": TEXT}, ask=ask)
    assert len(prompts) == 1                         # Zeta joined with Agent Z: it is no longer a leftover to ask about
    assert g.unresolved == [] and g.groups == {"Zeta": ["Zeta", "Agent Z"]}
    assert g.group_of("Agent Z") == "Zeta"
    assert {(m.mention.name, m.group, m.step) for m in g.matches} == {("Agent Z", "Zeta", "model"),
                                                                     ("Zeta", "Zeta", "model")}
    payload = json.loads(prompts[0])
    assert (payload["name"], payload["group"], payload["type"]) == ("Agent Z", "Zeta", "condition")
    assert payload["passages"] == ["Agent Z was tested.", "Zeta answers well."]


def test_different_version_numbers_are_never_asked() -> None:
    g = group_names([Mention("GPT-3", "p1", 0, 5, "condition"), Mention("GPT 3.5 turbo", "p1", 10, 23, "condition")], {})
    assert confirm_leftovers(g, {}, ask=lambda _: pytest.fail("asked")) == g


def test_names_of_other_types_are_never_asked() -> None:
    g = group_names([Mention("Agent Z", "p1", 0, 7, "condition"), Mention("Zeta", "p1", 20, 24, "metric")], {})
    assert confirm_leftovers(g, {"p1": TEXT}, ask=lambda _: pytest.fail("asked")) == g


def test_a_matched_name_stays_as_it_was() -> None:
    g = NameGroups({"Drug A": ["Drug A", "drug-A"]}, [Match(Mention("Drug A", "p1", 0, 6, "c"), "Drug A", "clean", None),
                                                    Match(Mention("drug-A", "p1", 9, 15, "c"), "Drug A", "clean", None)], [])
    assert confirm_leftovers(g, {}, ask=lambda _: pytest.fail("asked")) == g


# --- the kinds read the groups -----------------------------------------------------------------------------

def test_best_kind_of_follows_the_name_group() -> None:
    from evidence.contract import Item, Span
    from evidence.kinds import best
    from evidence.protocol import parse
    protocol = parse(protocol_path("rag", "best-accuracy").read_text(encoding="utf-8"))
    span = Span(role="condition_label", selector={"file": "p.md", "start": 0, "end": 6, "exact": "Plain-LM"})
    thing = Item.build("condition", {"label": "Plain-LM", "role": "baseline"}, [span])
    groups = NameGroups({"vanilla LLM": ["vanilla LLM", "Plain-LM"]}, [], [])
    assert best.kind_of(thing, best.spec(protocol), protocol.roles()) is None
    assert best.kind_of(thing, best.spec(protocol), protocol.roles(), groups) == "no-retrieval"
