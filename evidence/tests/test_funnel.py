"""The funnel engine (docs/evidence-system.md Part D; our design) with scripted models: the screen cascade,
`gaps` escalating only the gaps with a targeted task (LLM prompt, agentic brief), screened-out documents,
`on_fail: extract_anyway`, replay and re-execution of a `gaps` run, the PROV export of the screen, and the
shapes of funnel.json and the events; `all` mode without a screen block gives today's evidence."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import PROV, RDF

from evaluation.tests.agentic_fakes import FakeRunner
from evidence import cli, engine, extractors, protocol
from evidence.contract import ExtractionTask, Focus
from evidence.extractors import llm_schema
from evidence.replay import reexec, replay

from .conftest import PROTOCOL, context_id, corpus_of, make_corpus, provider_of, screen_yes, scripted

AGENTIC = PROTOCOL.parent / "rag-factuality-agentic.yaml"
HEAD = "# T\n\n## Setup\n\nWe compare a closed-book baseline (B) with its retrieval-augmented variant (R).\n\n## Results\n\n"
COMPLETE = HEAD + "| System | Dataset | Accuracy (%) |\n|---|---|---|\n| B | NQ | 60.0 |\n| R | NQ | 70.0 |\n"
# The baseline is "the standard generator (S)": no regex condition pattern names it, so position 0 leaves the
# control condition (and then its value) to the later positions.
MISSING_BASELINE = ("# Standard against retrieval\n\n## Setup\n\nWe compare the standard generator (S) with its "
                    "retrieval-augmented variant (R).\n\n## Results\n\n| System | Dataset | Accuracy (%) |\n|---|---|---|\n"
                    "| S | NQ | 60.0 |\n| R | NQ | 70.0 |\n")
SURVEY = "# A survey of subword tokenizers\n\n## Abstract\n\nWe survey tokenizers for language models.\n"
DOCS = {"P1": COMPLETE, "P2": MISSING_BASELINE, "P3": SURVEY}


def make_script(seen: list[tuple[str, str]], *, measurement: bool = True, screen: Any = None):
    """A careful reader of P2: the baseline condition, and (when `measurement`) its value; nothing else.
    `screen(doc, prompt)` overrides the screening reply."""
    def script(kind: str, doc: str, prompt: str) -> dict[str, Any]:
        seen.append((kind, doc))
        if kind == "screen":
            return screen(doc, prompt) if screen else screen_yes(prompt)
        if kind == "retry":
            return {"quotes": []}
        if doc == "P2" and kind == "condition":
            return {"items": [{"fields": {"label": "standard generator", "role": "baseline"},
                               "quotes": {"condition_label": "standard generator (S)"}}]}
        if doc == "P2" and kind == "measurement" and measurement:
            base, acc = context_id(prompt, '"baseline"'), context_id(prompt, '"factual_accuracy"')
            return {"items": [{"fields": {"value": 0.6, "dataset": "NQ"}, "links": {"condition": base, "metric": acc},
                               "quotes": {"value": "60.0", "condition_label": None, "metric_label": None}}]}
        return {"items": []}
    return script


def gaps_run(tmp_path: Path, docs: dict[str, str], script: Any, proto: Path = PROTOCOL, **kw: Any) -> Path:
    calls: list[str] = kw.pop("calls", [])
    return engine.run(proto, corpus_of(tmp_path / "corpus", docs), tmp_path / "runs", cache=tmp_path / "cache",
                      provider=provider_of(scripted(script, calls)), model="scripted-alias", strategy="gaps", **kw)


def read(root: Path, name: str) -> Any:
    return json.loads((root / name).read_text(encoding="utf-8"))


def events(root: Path, subtype: str | None = None) -> list[dict[str, Any]]:
    rows = [json.loads(x) for x in (root / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    return [e for e in rows if subtype is None or e["subtype"] == subtype]


def extraction_calls(root: Path, doc: str) -> list[dict[str, Any]]:
    return [e for e in events(root, "extractor_call")
            if e["custom_metadata"]["document"] == doc and e["custom_metadata"]["evidence_type"] != "screen"]


# --- the funnel ------------------------------------------------------------------------------------

def test_complete_after_regex_makes_no_llm_extraction_call_and_the_gaps_escalate_only_the_gaps(tmp_path: Path) -> None:
    seen: list[tuple[str, str]] = []
    calls: list[str] = []
    root = gaps_run(tmp_path, DOCS, make_script(seen), calls=calls)
    record, answer, funnel = read(root, "run.json"), read(root, "answer.json"), read(root, "funnel.json")
    assert record["settings"]["strategy"] == "gaps" and funnel["strategy"] == "gaps"
    # P1: complete after position 0, only regex extraction calls; the LLM saw it for the screen alone
    assert all(e["agent_id"].startswith("regex_") for e in extraction_calls(root, "P1"))
    assert [kind for kind, doc in seen if doc == "P1"] == ["screen"]
    p1 = funnel["documents"]["P1"]
    assert [(s["position"], s["types"]) for s in p1["steps"]] == [(0, ["condition", "metric", "measurement", "author_claim"])]
    assert p1["decisions"] == [{"after_round": 0, "after_position": 0, "complete": True, "gap": None, "gap_types": []}]
    assert p1["stopped_after"] == 0 and p1["skipped"] is False and p1["screen"]["relevant"] is True
    # P2: the baseline condition is the gap, then the pair; only those two types escalate, each with a focus
    assert [kind for kind, doc in seen if doc == "P2"] == ["screen", "condition", "measurement"]
    p2 = funnel["documents"]["P2"]
    assert [(s["round"], s["position"], s["types"]) for s in p2["steps"]] == [
        (0, 0, ["condition", "metric", "measurement", "author_claim"]), (1, 1, ["condition"]), (2, 1, ["measurement"])]
    assert [(d["complete"], d["gap"], d["gap_types"]) for d in p2["decisions"]] == [
        (False, "no_control_condition", ["condition"]), (False, "no_pair", ["measurement"]), (True, None, [])]
    assert p2["stopped_after"] == 1
    condition_prompt = next(c for c in calls if "standard generator" in c and "Focus (gap no_control_condition)" in c)
    assert "only the baseline condition and its measurement" in condition_prompt and "roles found: rag" in condition_prompt
    measurement_prompt = next(c for c in calls if "Focus (gap no_pair)" in c)
    assert "metrics found: factual_accuracy" in measurement_prompt and "roles found: baseline, rag" in measurement_prompt
    focused = [e["custom_metadata"]["focus"] for e in extraction_calls(root, "P2") if e["custom_metadata"]["position"] == 1]
    assert focused == ["no_control_condition", "no_pair"]
    by_doc = {s["document"]: s for s in answer["studies"]}
    assert by_doc["P1"]["direction"] == "supports" and by_doc["P1"]["funnel"] == {"screened": False, "stopped_after": 0}
    assert by_doc["P2"]["direction"] == "supports" and by_doc["P2"]["control"]["value"] == 0.6
    assert by_doc["P2"]["funnel"] == {"screened": False, "stopped_after": 1}
    merged = [i for i in (json.loads(x) for x in (root / "evidence.jsonl").read_text().splitlines())
              if i["evidence_type"] == "condition" and i["fields"]["role"] == "baseline"]
    assert any(i["fields"]["label"] == "standard generator" and i["found_by"][0].startswith("llm_condition") for i in merged)
    # the completeness events carry the decisions
    done = [e["custom_metadata"] for e in events(root, "completeness") if e["custom_metadata"]["document"] == "P2"]
    assert [d["gap"] for d in done] == ["no_control_condition", "no_pair", None]
    assert set(done[0]) == {"document", "after_round", "after_position", "complete", "gap", "gap_types"}


# The question metric under a name no regex knows ("FLA"): only a later metric position can find it.
BEST_FLA = ("# Retrieval or not\n\nWe compare the closed-book model with the retrieval-augmented model on NQ.\n\n"
            "## Results\n\n| System | FLA |\n|---|---|\n| closed-book model | 0.41 |\n| retrieval-augmented model | 0.58 |\n")


def test_best_escalates_the_metric_cascade_when_the_question_metric_is_missing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pre-EV3 review A2: a best paper whose question metric regex misses escalates metric (abbrev, GLiNER, LLM),
    not only measurement; the LLM's metric then lets the measurement step link the values."""
    monkeypatch.delenv("GLINER_URL", raising=False)        # GLiNER is skipped; the round falls through to the LLM
    seen: list[tuple[str, str]] = []

    def script(kind: str, doc: str, prompt: str) -> dict[str, Any]:
        seen.append((kind, doc))
        if kind == "screen":
            return screen_yes(prompt)
        if kind == "metric":
            return {"items": [{"fields": {"name": "FLA", "canonical": "factual_accuracy", "higher_is_better": True},
                               "quotes": {"metric_label": "FLA"}}]}
        if kind == "measurement":
            fla, closed, rag = (context_id(prompt, f) for f in ('"FLA"', '"closed-book model"', '"retrieval-augmented model"'))
            return {"items": [{"fields": {"value": v, "dataset": "NQ"}, "links": {"condition": c, "metric": fla},
                               "quotes": {"value": q, "condition_label": None, "metric_label": None}}
                              for c, v, q in ((closed, 0.41, "0.41"), (rag, 0.58, "0.58"))]}
        return {"items": []}

    root = gaps_run(tmp_path, {"S1": BEST_FLA}, script, proto=PROTOCOL.parent / "best-accuracy.yaml")
    s1 = read(root, "funnel.json")["documents"]["S1"]
    decisions = [(d["gap"], d["gap_types"]) for d in s1["decisions"]]
    assert decisions[0] == ("no_question_metric", ["metric"]), decisions
    assert any(s["position"] >= 1 and s["types"] == ["metric"] for s in s1["steps"]), s1["steps"]
    called = {e["agent_id"].split("@")[0] for e in extraction_calls(root, "S1") if e["status"] != "skipped"}
    assert {"abbrev_metric", "llm_metric"} <= called, called
    assert ("metric", "S1") in seen
    [study] = read(root, "answer.json")["studies"]
    assert study["winner"] == "rag" and study["reason"] is None, (study, decisions)


def test_a_screened_out_paper_gets_no_extraction_and_is_undetermined_screened_out(tmp_path: Path) -> None:
    seen: list[tuple[str, str]] = []
    root = gaps_run(tmp_path, DOCS, make_script(seen))
    answer, funnel = read(root, "answer.json"), read(root, "funnel.json")
    assert extraction_calls(root, "P3") == [] and [kind for kind, doc in seen if doc == "P3"] == []
    p3 = funnel["documents"]["P3"]
    assert p3["skipped"] is True and p3["steps"] == [] and p3["decisions"] == [] and p3["stopped_after"] is None
    assert p3["screen"]["relevant"] is False and p3["screen"]["extractor"].startswith("regex_screen")
    assert p3["screen"]["reason"].startswith("none of the terms retrieval-augmented, ")
    study = next(s for s in answer["studies"] if s["document"] == "P3")
    assert study["direction"] == "undetermined" and study["reason"]["code"] == "screened_out"
    assert study["reason"]["text"].startswith("screened out: none of the terms")
    assert study["funnel"] == {"screened": True, "stopped_after": None}
    assert answer["counts"]["undetermined"] == 1 and answer["label"] == "supported"
    screen = next(e for e in events(root, "screen") if e["custom_metadata"]["document"] == "P3")
    assert set(screen["custom_metadata"]) == {"document", "relevant", "reason", "extractor", "status", "calls", "statuses"}
    assert screen["agent_id"] == screen["custom_metadata"]["extractor"] and screen["custom_metadata"]["status"] == "ok"
    assert len(screen["custom_metadata"]["calls"]) == 1          # regex said no: the LLM screen never ran
    assert screen["custom_metadata"]["statuses"] == ["ok"]
    # the regex screen's negative decision is anchored on the title line
    call = read(root, f"calls/{screen['custom_metadata']['calls'][0]}.json")
    assert call["items"][0]["fields"]["relevant"] is False
    assert call["items"][0]["spans"][0]["selector"]["exact"] == "A survey of subword tokenizers"


def test_extract_anyway_extracts_from_a_screened_out_paper(tmp_path: Path) -> None:
    variant = tmp_path / "anyway.yaml"
    text = PROTOCOL.read_bytes().decode("utf-8")
    assert text.count("on_fail: skip") == 1
    variant.write_text(text.replace("on_fail: skip", "on_fail: extract_anyway"), encoding="utf-8", newline="\n")
    assert protocol.load(variant).screen.on_fail == "extract_anyway"
    root = gaps_run(tmp_path, DOCS, make_script([]), variant)
    assert extraction_calls(root, "P3")
    p3 = read(root, "funnel.json")["documents"]["P3"]
    assert p3["screen"]["relevant"] is False and p3["skipped"] is False and p3["steps"]
    study = next(s for s in read(root, "answer.json")["studies"] if s["document"] == "P3")
    assert study["reason"]["code"] == "no_treatment_condition" and study["funnel"]["screened"] is True


def test_the_llm_screen_decides_after_the_regex_and_falls_back_when_unanchored(tmp_path: Path) -> None:
    def screen(doc: str, prompt: str) -> dict[str, Any]:
        if doc == "P1":   # a relevant paper the model rejects, with a quote that anchors
            return {"relevant": False, "reason": "no comparison", "quote": "We compare a closed-book baseline (B)"}
        return {"relevant": False, "reason": "made up", "quote": "a sentence that is not in the paper"}

    root = gaps_run(tmp_path, {"P1": COMPLETE, "P2": MISSING_BASELINE}, make_script([], screen=screen))
    funnel = read(root, "funnel.json")["documents"]
    p1, p2 = funnel["P1"], funnel["P2"]
    assert p1["screen"]["relevant"] is False and p1["screen"]["extractor"].startswith("llm_screen") and p1["skipped"]
    assert len(p1["screen"]["calls"]) == 2
    # P2: the model's quote does not anchor -> rejected, the regex decision (relevant) stands as "unanchored"
    assert p2["screen"]["relevant"] is True and p2["screen"]["reason"] == "unanchored: made up"
    assert p2["screen"]["extractor"].startswith("llm_screen") and not p2["skipped"]
    llm_call = read(root, f"calls/{p2['screen']['calls'][1]}.json")
    assert [r["reason"] for r in llm_call["rejected"]] == ["not_found"]
    regex_call = read(root, f"calls/{p2['screen']['calls'][0]}.json")
    assert llm_call["items"][0]["spans"] == regex_call["items"][0]["spans"]     # the regex hit's span
    assert regex_call["items"][0]["spans"][0]["selector"]["exact"] == "retrieval"   # the earliest term: the title's


def test_a_failed_llm_screen_call_leaves_the_regex_decision_standing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-secret-1234")

    def screen(doc: str, prompt: str) -> dict[str, Any]:
        raise RuntimeError("gateway down for key sk-secret-1234")

    root = gaps_run(tmp_path, {"P1": COMPLETE}, make_script([], screen=screen))
    p1 = read(root, "funnel.json")["documents"]["P1"]
    assert p1["screen"]["relevant"] is True and p1["screen"]["extractor"].startswith("regex_screen")
    assert p1["screen"]["statuses"] == ["ok", "error"] and p1["screen"]["status"] == "ok" and not p1["skipped"]
    event = next(e for e in events(root, "screen"))
    assert event["custom_metadata"]["statuses"] == ["ok", "error"] and event["agent_id"].startswith("regex_screen")
    failed = read(root, f"calls/{p1['screen']['calls'][1]}.json")
    assert failed["status"] == "error" and failed["items"] == [] and "sk-secret" not in json.dumps(failed)
    assert read(root, "answer.json")["studies"][0]["direction"] == "supports"   # extraction ran as usual


# --- screen.lexical_miss: a keyword miss escalates to the next screen extractor, or is final (default) ----------

EV1 = Path(__file__).resolve().parents[2] / "tests" / "EV1"
EV1_PROPOSAL = EV1 / "diagnostics" / "proposal" / "protocol.yaml"
# tests/EV1/diagnostics/review_repro.py: a treatment and a comparator synonym that none of the screen terms name
SYNONYMS = ("# Retrieval comparison\nThe retrieve-then-read system and the parametric-only model "
            "answer the same questions. We compare exact match: 75% versus 60%.\n")
# sha256 of every existing protocol, captured on main before `screen.lexical_miss` existed
SHA_BEFORE = {
    PROTOCOL: "6b360bca67ce74025cea4ee857de1a7089c3ecc110cbfc2f8e4da1a32b1751d9",
    AGENTIC: "8fe0ed7ea0bbdd393f67177b725c3ba4f16a2f70c2316e35da72f5280863bb79",
    EV1_PROPOSAL: "a4dc881623966e553de7f5418e6142c25b09996ce53598896ae289c72ee4e317",
    EV1 / "live-rerun" / "proposals" / "rag-factuality" / "protocol.yaml":
        "a4dc881623966e553de7f5418e6142c25b09996ce53598896ae289c72ee4e317",
    EV1 / "proposal" / "protocol.yaml": "e40e4902fee172fe9df3e4bb4758f3e888bc1468b73e0ff24cf33eb10303cf91",
}


@pytest.mark.parametrize("path", list(SHA_BEFORE), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_a_default_lexical_miss_leaves_the_protocol_sha256_unchanged(path: Path) -> None:
    loaded = protocol.load(path)
    assert loaded.screen is not None and loaded.screen.lexical_miss == "reject"
    assert loaded.sha256 == SHA_BEFORE[path]


def test_a_non_default_lexical_miss_changes_the_sha256(tmp_path: Path) -> None:
    assert protocol.DIGEST_OMIT_AT_DEFAULT["screen.lexical_miss"] == "reject"
    assert protocol.load(escalating(tmp_path)).sha256 != SHA_BEFORE[EV1_PROPOSAL]


def escalating(tmp_path: Path) -> Path:
    """The EV1 proposal's protocol with `screen.lexical_miss: escalate`."""
    data = yaml.safe_load(EV1_PROPOSAL.read_text(encoding="utf-8"))
    data["screen"]["lexical_miss"] = "escalate"
    path = tmp_path / "escalate.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def synonym_run(tmp_path: Path, proto: Path, screen: Any) -> tuple[list[str], dict[str, Any]]:
    """(the model call kinds, funnel.json's entry) of a `gaps` run over the synonym paper."""
    seen: list[str] = []

    def reply(kind: str, doc: str, prompt: str) -> dict[str, Any]:
        seen.append(kind)
        return screen(prompt) if kind == "screen" else {"items": []}

    root = engine.run(proto, corpus_of(tmp_path / "corpus", {"P": SYNONYMS}), tmp_path / "runs",
                      cache=tmp_path / "cache", model="offline-scripted",
                      provider=provider_of(scripted(reply, [])), strategy="gaps")
    return seen, read(root, "funnel.json")["documents"]["P"]


def test_a_keyword_miss_escalates_to_the_llm_screen_when_asked(tmp_path: Path) -> None:
    call_types, entry = synonym_run(tmp_path, escalating(tmp_path), screen_yes)
    assert "screen" in call_types and not entry["skipped"]
    assert entry["screen"]["escalated"] is True and entry["screen"]["relevant"] is True
    assert entry["screen"]["extractor"].startswith("llm_screen") and entry["screen"]["statuses"] == ["ok", "ok"]


def test_a_keyword_miss_is_final_by_default(tmp_path: Path) -> None:
    call_types, entry = synonym_run(tmp_path, EV1_PROPOSAL, screen_yes)
    assert call_types == [] and entry["skipped"] is True and "escalated" not in entry["screen"]
    assert entry["screen"]["relevant"] is False and entry["screen"]["extractor"].startswith("regex_screen")
    assert len(entry["screen"]["calls"]) == 1


def test_an_escalated_call_that_fails_keeps_the_regex_no(tmp_path: Path) -> None:
    def screen(prompt: str) -> dict[str, Any]:
        raise RuntimeError("gateway down")

    call_types, entry = synonym_run(tmp_path, escalating(tmp_path), screen)
    assert call_types == ["screen"] and entry["skipped"] is True and entry["screen"]["escalated"] is True
    assert entry["screen"]["relevant"] is False and entry["screen"]["extractor"].startswith("regex_screen")
    assert entry["screen"]["statuses"] == ["ok", "error"] and len(entry["screen"]["calls"]) == 2


def test_the_llm_screen_reads_the_head_only(tmp_path: Path) -> None:
    long_paper = COMPLETE + "\n## Appendix\n\n" + "Filler sentence. " * 400
    calls: list[str] = []
    protocol_text = PROTOCOL.read_bytes().decode("utf-8")
    assert protocol_text.count("    - name: llm_screen        # otherwise the model answers the question\n") == 1
    variant = tmp_path / "head.yaml"
    variant.write_text(protocol_text.replace("    - name: llm_screen        # otherwise the model answers the question\n",
                                             "    - name: llm_screen\n      config: {head_chars: 100}\n"),
                       encoding="utf-8", newline="\n")
    root = gaps_run(tmp_path, {"P1": long_paper}, make_script([], screen=lambda d, p: screen_yes(p)), variant, calls=calls)
    prompt = next(c for c in calls if "characters 0-100" in c)
    assert "Appendix" not in prompt and len(prompt.split("<<<\n", 1)[1].rsplit("\n>>>", 1)[0]) == 100
    p1 = read(root, "funnel.json")["documents"]["P1"]
    llm_call = read(root, f"calls/{p1['screen']['calls'][1]}.json")
    assert llm_call["coverage"] == [{"range": [0, 100], "section": None, "status": "found", "found": 1, "reason": None}]
    assert llm_call["extractor_id"] != extractors.get("llm_screen", {"question": "q"}).spec.extractor_id
    assert extractors.get("llm_screen", {}).spec.config["head_chars"] == 12000
    with pytest.raises(ValueError, match="head_chars"):
        extractors.get("llm_screen", {"head_chars": 0})


def test_the_agentic_brief_carries_the_focus_and_only_the_gap_type_reaches_the_agent(tmp_path: Path,
                                                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    from evidence.agentic import extractor as agentic

    fake = FakeRunner({"outcome": {"exit_status": "submitted", "answer_from": "final"}, "claims": [], "commands": [],
                       "model_calls": [], "answer": {"rows": [], "notes": ""}, "trajectory": None, "head": None})
    monkeypatch.setattr(agentic, "ResearchAgentRunner", lambda settings, work_dir=None: fake)
    seen: list[tuple[str, str]] = []
    root = gaps_run(tmp_path, {"P2": MISSING_BASELINE}, make_script(seen, measurement=False), AGENTIC)
    assert [kind for kind, doc in seen] == ["screen", "condition", "measurement"]   # the LLM steps
    assert len(fake.jobs) == 1                                                       # measurement@2 only
    job = fake.jobs[0]
    assert "Every measurement stated in" in job.concept["title"]
    assert job.concept["scope"]["focus"].startswith("gap no_pair: the rag and baseline conditions and a question metric are known")
    assert "roles found: baseline, rag" in job.concept["scope"]["focus"]
    p2 = read(root, "funnel.json")["documents"]["P2"]
    assert [(s["position"], s["types"]) for s in p2["steps"]] == [(0, ["condition", "metric", "measurement", "author_claim"]),
                                                                  (1, ["condition"]), (1, ["measurement"]), (2, ["measurement"])]
    assert p2["decisions"][-1]["gap"] == "no_pair" and p2["stopped_after"] is None     # exhausted, the gap recorded
    study = read(root, "answer.json")["studies"][0]
    assert study["reason"]["code"] == "no_pair" and study["funnel"] == {"screened": False, "stopped_after": None}
    agent_event = next(e for e in events(root, "extractor_call") if e["agent_id"].startswith("agentic@"))
    assert agent_event["custom_metadata"]["position"] == 2 and agent_event["custom_metadata"]["focus"] == "no_pair"


def test_replay_and_reexec_of_a_gaps_run(tmp_path: Path) -> None:
    seen: list[tuple[str, str]] = []
    root = gaps_run(tmp_path, DOCS, make_script(seen))
    made = len(seen)
    new, report = replay(root)      # no model: every call, screen and targeted ones, comes from the cache
    assert report["ok"] and report["mismatched"] == []
    assert read(new, "run.json")["settings"]["strategy"] == "gaps" and len(seen) == made
    assert (new / "funnel.json").read_bytes() == (root / "funnel.json").read_bytes()
    again = reexec(root, provider=provider_of(scripted(make_script(seen), [])))
    totals = read(again, "reexec.json")["totals"]
    assert set(totals) == {"identical"} and totals["identical"] == read(root, "run.json")["cost"]["calls"]
    rows = read(again, "reexec.json")["calls"]
    assert {(c["document"], c["evidence_type"], c["position"]) for c in rows if c["extractor"] == "llm_measurement"} == {("P2", "measurement", 1)}


def test_prov_exports_the_screen_call_and_decision(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "runs"
    assert cli.main(["run", "--protocol", str(PROTOCOL), "--corpus", str(corpus_of(tmp_path / "c", DOCS)), "--out", str(out),
                     "--extractors", "regex-only", "--strategy", "gaps", "--run-id", "g1"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["counts"]["undetermined"] == 2   # P2 (regex is the whole cascade: exhausted) and P3 (screened out)
    assert cli._parser().parse_args(["run", "--protocol", "p", "--corpus", "c"]).strategy == "gaps"
    assert cli.main(["prov", str(out / "g1")]) == 0
    g = Graph().parse(out / "g1" / "prov.ttl", format="turtle")
    ev = "urn:thesis-evidence:vocab#"
    decisions = [s for s, _, o in g.triples((None, URIRef(ev + "subtype"), None)) if str(o) == "screen"]
    assert len(decisions) == 3
    rejected = next(s for s in decisions if (s, URIRef(ev + "relevant"), Literal(False)) in g)
    agent = next(g.objects(rejected, PROV.wasAssociatedWith))
    assert (agent, RDF.type, PROV.SoftwareAgent) in g and "regex_screen" in str(agent)
    call = next(g.objects(rejected, PROV.wasInformedBy))
    assert (call, URIRef(ev + "subtype"), Literal("extractor_call")) in g and (call, PROV.wasAssociatedWith, agent) in g
    assert any(True for _ in g.objects(call, PROV.used))
    capsys.readouterr()   # the prov command printed its path
    assert cli.main(["replay", str(out / "g1")]) == 0 and json.loads(capsys.readouterr().out)["ok"]


def test_all_mode_records_the_screen_and_extracts_anyway_and_without_a_screen_block_is_todays_run(
        protocol_file: Path, corpus: Path, tmp_path: Path) -> None:
    with_screen = engine.run(protocol_file, corpus, tmp_path / "a", selection="regex-only", provider=None, run_id="s",
                           strategy="all")
    assert all(e["custom_metadata"]["relevant"] for e in events(with_screen, "screen"))   # the five papers name retrieval
    survey = corpus_of(tmp_path / "c2", {"P1": COMPLETE, "P3": SURVEY})
    recorded = engine.run(protocol_file, survey, tmp_path / "b", selection="regex-only", provider=None, run_id="s",
                           strategy="all")
    p3 = read(recorded, "funnel.json")["documents"]["P3"]
    assert p3["screen"]["relevant"] is False and p3["skipped"] is False and extraction_calls(recorded, "P3")
    study = next(s for s in read(recorded, "answer.json")["studies"] if s["document"] == "P3")
    assert study["reason"]["code"] != "screened_out" and study["funnel"] == {"screened": True, "stopped_after": None}
    # no screen block: no screen call or event, 20 calls, and the same evidence, locate, graph and answer files
    text = protocol_file.read_text(encoding="utf-8")
    start, end = text.index("screen:"), text.index("evidence_types:")
    bare = tmp_path / "bare.yaml"
    bare.write_text(text[:start] + text[end:], encoding="utf-8", newline="\n")
    assert protocol.load(bare).screen is None
    without = engine.run(bare, corpus, tmp_path / "d", selection="regex-only", provider=None, run_id="s",
                           strategy="all")
    record = read(without, "run.json")
    assert record["cost"]["calls"] == 20 and len(record["extractors"]) == 4 and events(without, "screen") == []
    for name in ("evidence.jsonl", "locate.json", "graph.json", "answer.json"):
        assert (without / name).read_bytes() == (with_screen / name).read_bytes(), name
    assert read(without, "funnel.json")["documents"]["S001"]["screen"] is None


def test_gaps_run_never_opens_ground_truth_and_funnel_json_has_the_documented_shape(tmp_path: Path) -> None:
    import sys

    from .conftest import POISON

    corpus = make_corpus(tmp_path / "corpus")   # written before the hook watches
    opened: list[str] = []
    active = [True]

    def hook(event: str, args: tuple) -> None:
        if active[0] and event == "open" and args and isinstance(args[0], (str, bytes, Path)):
            opened.append(str(args[0]))

    sys.addaudithook(hook)
    try:
        root = engine.run(PROTOCOL, corpus, tmp_path / "runs", selection="regex-only", provider=None, strategy="gaps")
    finally:
        active[0] = False
    assert any(p.endswith("manifest.json") for p in opened) and not [p for p in opened if Path(p).name in POISON]
    funnel = read(root, "funnel.json")
    # `dangling_links` (run total, per document) come with `relink: on`, the default
    assert set(funnel) == {"strategy", "documents", "dangling_links"} and funnel["dangling_links"] == 0
    assert set(funnel["documents"]) == {"S001", "S002", "S003", "S004", "S005"}
    for entry in funnel["documents"].values():
        assert set(entry) == {"screen", "skipped", "steps", "decisions", "stopped_after", "dangling_links"}
        assert set(entry["screen"]) == {"relevant", "reason", "extractor", "status", "calls", "statuses"}
        assert all(set(s) == {"round", "position", "types", "calls"} for s in entry["steps"])
        assert all(set(d) == {"after_round", "after_position", "complete", "gap", "gap_types"} for d in entry["decisions"])
    assert read(root, "run.json")["outputs"]["funnel.json"]
    # S005 has no baseline condition and the regex is the whole cascade: exhausted after position 0
    assert funnel["documents"]["S005"]["decisions"] == [{"after_round": 0, "after_position": 0, "complete": False,
                                                        "gap": "no_control_condition", "gap_types": ["condition"]}]
    assert funnel["documents"]["S005"]["stopped_after"] is None and funnel["documents"]["S001"]["stopped_after"] == 0


# --- pieces ----------------------------------------------------------------------------------------

def test_focus_is_part_of_the_task_hash_and_of_the_prompts() -> None:
    from evaluation.tests.agentic_fakes import MEASUREMENT_SCHEMA, context, task

    from evidence.agentic.task import TEMPLATE_VERSION, concept_for

    plain = task()
    focus = Focus(gap="no_pair", have={"roles": ["baseline", "rag"], "metrics": ["factual_accuracy"]}, want="find both values")
    targeted = ExtractionTask(**{**plain.model_dump(), "focus": focus})
    assert targeted.task_sha256 != plain.task_sha256 and plain.focus is None
    prompt = llm_schema.user_prompt("S001", 1, 1, 0, 10, "text", {}, focus)
    assert "Focus (gap no_pair): find both values (metrics found: factual_accuracy; roles found: baseline, rag)." in prompt
    assert "Focus" not in llm_schema.user_prompt("S001", 1, 1, 0, 10, "text", {})
    assert TEMPLATE_VERSION == "agentic-task-v3"
    brief = concept_for(targeted, MEASUREMENT_SCHEMA, {"condition": "condition", "metric": "metric"}, context(), "S001.md", 10)
    assert brief["scope"]["focus"] == "gap no_pair: find both values (metrics found: factual_accuracy; roles found: baseline, rag)"
    assert "focus" not in concept_for(plain, MEASUREMENT_SCHEMA, {}, [], "S001.md", 10)["scope"]
    proto = protocol.load(PROTOCOL)
    assert engine.focus_for("no_control_condition", proto.synthesis, {}).want.startswith("only the baseline condition")
    assert engine.focus_for("no_treatment_condition", proto.synthesis, {}).have == {"roles": [], "metrics": []}
    assert "factual_accuracy, hallucination_rate" in engine.focus_for("no_question_metric", proto.synthesis, {}).want


def test_screen_extractors_and_the_pseudo_type() -> None:
    spec = protocol.load(PROTOCOL).screen.spec
    assert spec.roles == ("evidence",) and spec.fields["required"] == ["relevant", "reason"]
    regex = extractors.get("regex_screen", {"terms": ["RAG", "closed-book"]})
    assert regex.spec.kind == "regex" and regex.spec.evidence_types == ("screen",) and regex.spec.config["terms"] == ["RAG", "closed-book"]
    assert regex.spec.extractor_id != extractors.get("regex_screen", {"terms": ["RAG"]}).spec.extractor_id
    llm = extractors.get("llm_screen", {"question": "Is it?"})
    assert llm.spec.kind == "llm" and llm.spec.config["question"] == "Is it?" and llm.spec.config["temperature"] == 0.0
    assert llm.spec.extractor_id != extractors.get("llm_screen", {"question": "Other?"}).spec.extractor_id
    assert "Screening question: Is it?" in llm.instructions
    from evidence.extractors.screen import first_hit, term_pattern, title_line
    text = "# Title\n\nA rag doll. The RAG model and a closed-book\nbaseline."
    assert first_hit(text, ["RAG"], [(0, len(text))]) == (text.index("RAG"), text.index("RAG") + 3)   # not "rag doll"
    assert first_hit(text, ["Closed-Book", "RAG"], [(0, len(text))]) == (text.index("RAG"), text.index("RAG") + 3)  # earliest
    assert first_hit(text, ["closed-book"], [(0, len(text))]) == (text.index("closed-book"), text.index("closed-book") + 11)
    assert first_hit(text, ["rag"], [(0, len(text))]) == (text.index("rag doll"), text.index("rag doll") + 3)  # any case
    assert first_hit(text, ["doll the"], [(0, len(text))]) is None and first_hit(text, ["Title"], [(10, len(text))]) is None
    assert term_pattern("closed-book").startswith("(?i)") and not term_pattern("RAG").startswith("(?i)")
    assert title_line(text, [(0, len(text))]) == (2, 7)
    with pytest.raises(ValidationError, match="screen"):
        protocol.parse(PROTOCOL.read_text(encoding="utf-8").replace("  author_claim:\n", "  screen:\n", 1))


# --- the default -----------------------------------------------------------------------------------

def test_a_run_without_a_strategy_is_a_gaps_run(tmp_path: Path) -> None:
    root = engine.run(PROTOCOL, corpus_of(tmp_path / "corpus", DOCS), tmp_path / "runs", cache=tmp_path / "cache",
                      provider=provider_of(scripted(make_script([]), [])), model="scripted-alias")
    assert read(root, "run.json")["settings"]["strategy"] == "gaps"


def test_the_cli_default_strategy_is_gaps() -> None:
    assert cli._parser().parse_args(["run", "--protocol", "p.yaml", "--corpus", "c"]).strategy == "gaps"
