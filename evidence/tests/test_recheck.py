"""The required LLM re-check of regex finds."""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from agent.anchor import Index, find
from evidence import engine, steps
from evidence.contract import DocumentRef, Item, Span
from evidence.engine import DocState
from evidence.extractors import recheck as rc
from evidence.plan import WordList
from evidence.words.compile import compile_words
from modelcall.cache import JsonlCache
from modelcall.dspy_lm import RecordedLM

from .conftest import corpus_of, provider_of, screen_yes, scripted
from .test_funnel import EV1_PROPOSAL, SYNONYMS, events, read

P1 = "Alpha one here. We use alpha in this part.\n\nSecond paragraph mentions beta twice. Beta again."
FILE = "papers/P.md"


def doc_state(text: str = P1) -> DocState:
    return DocState(DocumentRef(id="P", file=FILE, sha256="0" * 64), text, Index(text))


def item(state: DocState, quote: str, label: str, found_by: str = "regex_condition@1#abc", nth: int = 0) -> Item:
    start = -1
    for _ in range(nth + 1):
        start = state.text.index(quote, start + 1)
    sel = find(state.index, quote, file=FILE) if nth == 0 else None
    assert sel is not None
    return Item.build("condition", {"label": label}, [Span.of("condition_label", sel)]).model_copy(update={"found_by": (found_by,)})


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    asked: list[str] = []
    verdicts: dict[str, list[dict]] = {}

    def ask(prompt: str) -> str:
        asked.append(prompt)
        # one reply per paragraph: the numbered finds are in the prompt as "N. type | fields | quote"
        out = []
        for number, quote in re.findall(r'(\d+)\. condition \| \{[^}]*\} \| (\w+)"', prompt):
            out.append({"number": int(number), "verdict": "keep"} | verdicts.get(quote.strip(), {}))
        return json.dumps({"verdicts": out})

    lm = RecordedLM("orch-model", ask, cache=JsonlCache(tmp_path / "c.jsonl"))
    return SimpleNamespace(dspy_lm=lambda purpose: lm, asked=asked, verdicts=verdicts, run_dir=tmp_path / "run")


def test_one_call_per_paragraph(ctx):
    d = doc_state()
    merged = [item(d, "alpha", "a"), item(d, "Alpha", "A"), item(d, "beta", "b"), item(d, "Beta", "B"), item(d, "twice", "t")]
    out = rc.recheck(d, "condition", merged, ctx)
    assert len(ctx.asked) == 2 and len(out) == 5


def test_drop_is_rejected_not_lost(ctx):
    d = doc_state()
    ctx.verdicts["beta"] = {"verdict": "drop", "reason": "a Greek letter, not the thing"}
    merged = [item(d, "alpha", "a"), item(d, "beta", "b")]
    out = rc.recheck(d, "condition", merged, ctx)
    assert [i.fields["label"] for i in out] == ["a"]
    (rej,) = rc.rejected_of(d)
    assert rej.reason == "out_of_scope" and rej.detail == "a Greek letter, not the thing" and rej.quotes == ("beta",)
    assert rej.fields == {"label": "b"}


def test_relabel_keeps_spans(ctx):
    d = doc_state()
    ctx.verdicts["alpha"] = {"verdict": "relabel", "new_label": "first"}
    (old,) = [item(d, "alpha", "a")]
    (new,) = rc.recheck(d, "condition", [old], ctx)
    assert new.fields == {"label": "first"} and new.spans == old.spans and new.found_by == old.found_by


def test_llm_items_not_rechecked(ctx):
    d = doc_state()
    merged = [item(d, "alpha", "a", found_by="llm_condition@1#abc"), item(d, "beta", "b", found_by="agentic@1#abc")]
    assert rc.recheck(d, "condition", merged, ctx) == merged and ctx.asked == []


def test_idempotent_across_funnel_rounds(ctx):
    d = doc_state()
    ctx.verdicts["beta"] = {"verdict": "drop", "reason": "no"}
    merged = [item(d, "alpha", "a"), item(d, "beta", "b")]
    first = rc.recheck(d, "condition", merged, ctx)
    assert len(ctx.asked) == 2
    second = rc.recheck(d, "condition", merged, ctx)
    assert first == second and len(ctx.asked) == 2 and len(rc.rejected_of(d)) == 1


def test_no_screen_hit_goes_to_llm_screen(tmp_path: Path) -> None:
    """Compiled screen terms that match nothing in the paper: with `lexical_miss: escalate` the paper goes to llm_screen."""
    words = WordList(things={"t": ["zorblax", "quuxify"]}, cues=[], written_by="orch-model", ontology_names={})
    data = yaml.safe_load(EV1_PROPOSAL.read_text(encoding="utf-8"))
    data["screen"]["terms"] = compile_words(words)["screen_terms"]
    data["screen"]["lexical_miss"] = "escalate"
    proto = tmp_path / "p.yaml"
    proto.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    seen: list[str] = []

    def reply(kind: str, doc: str, prompt: str) -> dict:
        seen.append(kind)
        return screen_yes(prompt) if kind == "screen" else {"items": []}

    root = engine.run(proto, corpus_of(tmp_path / "corpus", {"P": SYNONYMS}), tmp_path / "runs", cache=tmp_path / "cache",
                      model="offline-scripted", provider=provider_of(scripted(reply, [])), strategy="gaps")
    entry = read(root, "funnel.json")["documents"]["P"]
    assert "screen" in seen and not entry["skipped"] and entry["screen"]["escalated"] is True
    assert entry["screen"]["extractor"].startswith("llm_screen")


def test_each_thread_is_recorded_under_its_own_ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    seen: dict[str, list[str]] = {"a": [], "b": []}

    def ctx_of(name: str):
        def ask(prompt: str) -> str:
            time.sleep(0.05)
            seen[name].append(prompt)
            return json.dumps({"verdicts": [{"number": 1, "verdict": "keep"}]})
        lm = RecordedLM(f"alias-{name}", ask, cache=JsonlCache(tmp_path / f"{name}.jsonl"))
        return SimpleNamespace(dspy_lm=lambda purpose: lm, run_dir=tmp_path / name)

    class SlowStep(steps.Step):
        def __init__(self, *args):
            super().__init__(*args)
            time.sleep(0.1)   # widens the window between setting the model and calling it

    monkeypatch.setattr(rc, "Step", SlowStep)

    def work(name: str, quote: str) -> None:
        d = doc_state()
        rc.recheck(d, "condition", [item(d, quote, "x"), ] , ctx_of(name))

    threads = [threading.Thread(target=work, args=("a", "alpha")), threading.Thread(target=work, args=("b", "beta"))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(seen["a"]) == 1 and len(seen["b"]) == 1
    assert "alpha" in seen["a"][0] and "beta" not in seen["a"][0].split("[user]")[-1]
    assert "beta" in seen["b"][0] and "alpha" not in seen["b"][0].split("[user]")[-1]


def test_report_lists_the_drops_and_the_unchecked(ctx):
    d = doc_state()
    ctx.verdicts["beta"] = {"verdict": "drop", "reason": "a Greek letter"}
    rc.recheck(d, "condition", [item(d, "alpha", "a"), item(d, "beta", "b")], ctx)
    report = rc.recheck_report(None, ctx)
    assert list(report) == ["P"]
    assert [r["reason"] for r in report["P"]["rejected"]] == ["out_of_scope"]
    assert report["P"]["rejected"][0]["detail"] == "a Greek letter"
    assert {v["verdict"] for v in report["P"]["verdicts"]} == {"keep", "drop"} and report["P"]["unchecked"] == []
    assert rc.recheck_report(None, ctx) == {}   # handed over once
