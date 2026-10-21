"""Review fixes of the proposal flow: regex patterns follow the decided roles and metrics, edited files are
not overwritten, malformed inputs are clean refusals, the revision line keeps its comment, a cached reply the
step cannot use says how to ask again."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from evidence import cli
from evidence.extractors import terms as regex_terms
from evidence.propose import amend, cards, critic, frame, freeze, vocab
from evidence.propose.common import ProposalError
from evidence.protocol import load

from .conftest import PROTOCOL
from .propose_support import QUESTION, RAG_FRAME, Scripted, flow


def decide(d: Path, card: str, value: dict[str, Any]) -> None:
    data = yaml.safe_load((d / "decisions.yaml").read_text(encoding="utf-8"))
    for x in data["decisions"]:
        if x["card"] == card:
            x.update(choice="custom", value=value, reason="a person's choice", by="AG")
    (d / "decisions.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def regex_steps(p: Any) -> dict[str, dict[str, Any]]:
    return {s.name: s.config for spec in p.evidence_types.values() for s in spec.extractors if s.name.startswith("regex_")}


def checks_of(d: Path) -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in json.loads((d / "proposal.json").read_text(encoding="utf-8"))["checks"]}


# 1. regex patterns follow the decisions ------------------------------------------------------------------------

def test_a_dropped_metric_leaves_the_regex_steps(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted(), until="cards")
    decide(d, "metrics", {"metrics": [{"canonical": "factual_accuracy", "higher_is_better": True}]})
    freeze.run(d)
    p = load(d / "protocol.yaml")
    steps = regex_steps(p)
    for name in ("regex_metric", "regex_measurement"):
        emitted = {m[1] for m in steps[name]["metrics"]}
        assert emitted <= {"factual_accuracy", "other"} and "factual_accuracy" in emitted, name
    assert checks_of(d)["regex_matches_enums"]["ok"]


def test_an_added_metric_gets_patterns(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted(), until="cards")
    decide(d, "metrics", {"metrics": [{"canonical": "factual_accuracy", "higher_is_better": True},
                                      {"canonical": "f1", "higher_is_better": True}]})
    freeze.run(d)
    p = load(d / "protocol.yaml")
    assert p.evidence_types["metric"].enum_of("canonical") == ("factual_accuracy", "f1", "other")
    for name in ("regex_metric", "regex_measurement"):
        patterns = regex_steps(p)[name]["metrics"]
        assert any(m[1] == "f1" for m in patterns) and not any(m[1] == "hallucination_rate" for m in patterns)
    assert checks_of(d)["regex_matches_enums"]["ok"]


def test_renamed_roles_get_patterns(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted(), until="cards")
    decide(d, "roles", {"treatment": {"role": "retrieval", "definition": "with retrieval"},
                        "control": {"role": "closed_book", "definition": "without retrieval"}})
    freeze.run(d)
    p = load(d / "protocol.yaml")
    assert p.synthesis.compare.treatment == "retrieval"
    for name in ("regex_condition", "regex_measurement"):
        assert list(regex_steps(p)[name]["conditions"]) == ["retrieval", "closed_book"], name
    assert checks_of(d)["regex_matches_enums"]["ok"]


def test_generated_control_pattern_skips_no_retrieval_failures(tmp_path: Path) -> None:
    frame_reply = {**RAG_FRAME, "control": {**RAG_FRAME["control"], "synonyms": ["no retrieval", "no-retrieval baseline"]}}
    d = flow(tmp_path / "p", Scripted(frame_reply), until="cards")
    decide(d, "roles", {"treatment": {"role": "retrieval", "definition": "with retrieval"},
                        "control": {"role": "closed_book", "definition": "without retrieval"}})
    freeze.run(d)
    config = regex_steps(load(d / "protocol.yaml"))["regex_condition"]["conditions"]
    compiled = regex_terms.condition_patterns(config)
    keys = lambda text: {m.key for m in regex_terms.find_all(text, compiled)}   # noqa: E731
    assert "closed_book" not in keys("The RAG model has no retrieval failures.")
    assert "closed_book" in keys("a closed-book model with no retrieval")


def test_freeze_refuses_regex_steps_outside_the_enums(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from evidence.propose import draft
    d = flow(tmp_path / "p", Scripted(), until="cards")
    decide(d, "metrics", {"metrics": [{"canonical": "factual_accuracy", "higher_is_better": True}]})
    monkeypatch.setattr(draft, "sync_regex", lambda p, f: [])     # as before the fix
    with pytest.raises(ProposalError, match="can emit metric.canonical \\['hallucination_rate'\\]"):
        freeze.run(d)
    assert not (d / "protocol.yaml").exists()


def test_critic_check_both_directions() -> None:
    text = PROTOCOL.read_text(encoding="utf-8")
    assert {c["id"]: c for c in critic.checks(text, None)}["regex_matches_enums"]["ok"]
    roles = text.replace("enum: [rag, baseline, other]", "enum: [rag, closed, other]").replace(
        "control: baseline}", "control: closed}")
    check = {c["id"]: c for c in critic.checks(roles, None)}["regex_matches_enums"]
    assert not check["ok"]
    assert "regex_condition can emit condition.role ['baseline']" in check["message"]
    assert "regex_condition has no pattern for condition.role ['closed']" in check["message"]


# 2. edited files are kept ------------------------------------------------------------------------------------

def test_frame_rerun_keeps_an_edited_frame(tmp_path: Path) -> None:
    model = Scripted()
    d = flow(tmp_path / "p", model, until="frame")
    frame.run(QUESTION, d, vocab="rag-factuality", model=model.model)        # untouched: written again
    data = json.loads((d / "frame.json").read_text(encoding="utf-8"))
    data["treatment"]["definition"] = "edited by a person"
    (d / "frame.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProposalError, match="has been edited"):
        frame.run(QUESTION, d, vocab="rag-factuality", model=model.model)
    assert "edited by a person" in (d / "frame.json").read_text(encoding="utf-8")
    frame.run(QUESTION, d, vocab="rag-factuality", model=model.model, force=True)
    assert "edited by a person" not in (d / "frame.json").read_text(encoding="utf-8")


def test_cards_keep_decisions_they_did_not_write(tmp_path: Path) -> None:
    model = Scripted()
    d = flow(tmp_path / "p", model, until="critic")
    (d / "decisions.yaml").write_text("decisions: []  # written by a person before any cards\n", encoding="utf-8")
    with pytest.raises(ProposalError, match="has been edited"):
        cards.run(d, model=model.model)
    cards.run(d, model=model.model, force=True)
    (d / "cards.json").unlink()                  # the hole: no cards.json, an edited decisions.yaml
    decide(d, "min_effect", {"min_effect": 0.02})
    with pytest.raises(ProposalError, match="has been edited"):
        cards.run(d, model=model.model)


# 4. clean refusals -------------------------------------------------------------------------------------------

def test_a_malformed_vocabulary_is_a_clean_refusal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"name": "bad", "terms": []}), encoding="utf-8")
    with pytest.raises(vocab.VocabError, match="not a vocabulary snapshot"):
        vocab.load(bad)
    assert cli.main(["propose", "frame", "--question", "Q?", "--vocab", str(bad), "--out", str(tmp_path / "p")]) == 2
    assert "not a vocabulary snapshot" in capsys.readouterr().err


def test_a_csv_with_a_byte_order_mark(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "sources.json").write_text('﻿[{"name": "pwc", "version": "1", "url": null, "file": "m.csv"}]',
                                      encoding="utf-8")
    (src / "m.csv").write_text("﻿label,synonyms,kind,higher_is_better\nExact Match,EM,metric,true\n",
                               encoding="utf-8")
    data = vocab.build("bom", src)
    assert data["terms"][0]["label"] == "Exact Match"
    (src / "m.csv").write_text("name,kind\nx,metric\n", encoding="utf-8")
    with pytest.raises(vocab.VocabError, match="m.csv: missing key 'label'"):
        vocab.build("bom", src)


def test_a_choice_that_is_not_a_name(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted(), until="cards")
    data = yaml.safe_load((d / "decisions.yaml").read_text(encoding="utf-8"))
    data["decisions"][0]["choice"] = ["draft"]
    (d / "decisions.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ProposalError, match="screen: choice must be an option id"):
        freeze.run(d)


def test_a_broken_base_revision_is_a_clean_refusal(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted())
    (d / "protocol.v1.yaml").write_text("id: [unclosed\n", encoding="utf-8")
    text = (d / "protocol.yaml").read_text(encoding="utf-8")
    (d / "protocol.yaml").write_text(text.replace("min_effect: 0.01", "min_effect: 0.02"), encoding="utf-8")
    with pytest.raises(ProposalError, match="the base\\) does not validate"):
        amend.run(d, "smaller")
    assert cli.main(["propose", "amend", str(d), "--reason", "smaller"]) == 2


# 5. the revision line ----------------------------------------------------------------------------------------

def test_revision_line_keeps_its_comment_and_falls_back_to_a_dump() -> None:
    base = PROTOCOL.read_text(encoding="utf-8").replace("\r\n", "\n")
    commented = base.replace("version: 2\n", "version: 2\nrevision: 1   # first frozen\n")
    out = amend.with_revision(commented, 2)
    assert "revision: 2  # first frozen\n" in out and "# Research protocol" in out     # comments stay
    next_line = base.replace("version: 2\n", "version: 2\nrevision:\n  1\n")
    out = amend.with_revision(next_line, 2)
    assert yaml.safe_load(out)["revision"] == 2 and "# Research protocol" not in out  # full dump
    quoted = base.replace("version: 2\n", 'version: 2\n"revision": 1\n')
    out = amend.with_revision(quoted, 2)
    assert yaml.safe_load(out)["revision"] == 2
    assert load_text(out).revision == 2


def load_text(text: str) -> Any:
    from evidence.protocol import parse
    return parse(text)


# 6. a cached reply the step cannot use --------------------------------------------------------------------------

def test_a_cached_bad_frame_says_how_to_ask_again(tmp_path: Path) -> None:
    bad = json.loads(json.dumps(RAG_FRAME))
    bad["control"]["role"] = "rag"                       # treatment and control the same role
    model = Scripted(frame_reply=bad)
    d = tmp_path / "p"
    with pytest.raises(ProposalError, match="run the step again with --refresh") as err:
        frame.run(QUESTION, d, model=model.model)
    assert "cache.jsonl" in str(err.value)
    with pytest.raises(ProposalError, match="--refresh"):
        frame.run(QUESTION, d, model=model.model)
    assert model.calls == ["frame"]                      # the second run answered from the cache
    model.frame = json.loads(json.dumps(RAG_FRAME))
    frame.run(QUESTION, d, model=model.model, refresh=True)
    assert model.calls == ["frame", "frame"]
    frame.run(QUESTION, d, model=model.model)            # the refreshed reply is the cached one now
    assert model.calls == ["frame", "frame"]
    assert json.loads((d / "frame.json").read_text(encoding="utf-8"))["control"]["role"] == "baseline"


# 3. metric rules do not map one surface to two canonicals -------------------------------------------------------

def _live_frame() -> frame.Frame:
    return frame.load(Path(__file__).resolve().parents[2] / "tests/EV1/diagnostics/proposal/frame.json")


def test_metric_canonical_is_order_invariant() -> None:
    from evidence.extractors import terms
    from evidence.propose import draft
    f = _live_frame()
    config, _ = draft.metric_patterns([(o.canonical, o.higher_is_better, draft._names(o)) for o in f.outcomes])
    assert config is not None
    rules = [tuple(m) for m in config]
    for surface in ("FActScore", "factuality score", "accuracy", "factual accuracy"):
        forward = [m.key for m in terms.find_all(surface, rules)]       # type: ignore[arg-type]
        reverse = [m.key for m in terms.find_all(surface, list(reversed(rules)))]  # type: ignore[arg-type]
        assert forward and forward == reverse, surface


def test_collisions_are_reported(tmp_path: Path) -> None:
    reply = json.loads(json.dumps(RAG_FRAME))
    reply["outcomes"].append({"canonical": "factscore", "label": "fact score", "higher_is_better": True,
                              "scale": "fraction", "synonyms": ["FActScore"]})
    reply["outcomes"][0]["synonyms"].append("FActScore")
    d = flow(tmp_path / "p", Scripted(frame_reply=reply), until="draft")
    p = load_text((d / "draft.yaml").read_text(encoding="utf-8"))
    assert critic.metric_collisions(p, frame.load(d / "frame.json")) == ["FActScore: factscore vs factual_accuracy"]
    assert not {c["id"]: c for c in critic.checks((d / "draft.yaml").read_text(encoding="utf-8"),
                                                  frame.load(d / "frame.json"))}["metric_rules_collide"]["ok"]


# 5. locate params match the strategy -------------------------------------------------------------------------

def test_cards_offer_exhaustive_without_params(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted(), until="cards")
    card = next(c for c in json.loads((d / "cards.json").read_text(encoding="utf-8"))["cards"] if c["id"] == "locate")
    draft = card["options"][0]
    assert draft["id"] == "draft" and draft["value"] == {"strategy": "exhaustive", "params": {}}
    assert next(o for o in card["options"] if o["id"] == "bm25")["value"]["params"] == {"chunk_chars": 1500, "top_k": 6}


# sha256 of each protocol, computed with the code of main before this change
EV1_SHA256 = {
    "evidence/protocols/rag-factuality.yaml": "6b360bca67ce74025cea4ee857de1a7089c3ecc110cbfc2f8e4da1a32b1751d9",
    "evidence/protocols/rag-factuality-agentic.yaml": "8fe0ed7ea0bbdd393f67177b725c3ba4f16a2f70c2316e35da72f5280863bb79",
    "tests/EV1/diagnostics/proposal/protocol.yaml": "a4dc881623966e553de7f5418e6142c25b09996ce53598896ae289c72ee4e317",
    "tests/EV1/live-rerun/proposals/rag-factuality/protocol.yaml":
        "a4dc881623966e553de7f5418e6142c25b09996ce53598896ae289c72ee4e317",
    "tests/EV1/proposal/protocol.yaml": "e40e4902fee172fe9df3e4bb4758f3e888bc1468b73e0ff24cf33eb10303cf91",
}


def test_ev1_protocols_still_parse_with_the_same_sha256() -> None:
    root = Path(__file__).parents[2]
    found = {p.relative_to(root).as_posix() for pattern in ("evidence/protocols/*.yaml", "tests/EV1/**/protocol.yaml")
             for p in root.glob(pattern)}
    assert found == set(EV1_SHA256)
    for rel, sha in EV1_SHA256.items():
        assert load(root / rel).sha256 == sha, rel


# 7. blocking and advisory checks, human waivers, review status -------------------------------------------------

LIVE_PROPOSAL = Path(__file__).resolve().parents[2] / "tests/EV1/diagnostics/proposal"


@pytest.fixture
def copied_live_proposal(tmp_path: Path) -> Path:
    """The EV1 proposal before freeze (as tests/EV1/diagnostics/review_repro.py replays it). The files are
    copied with LF line ends, the bytes the steps hashed (a Windows checkout may hold them with CRLF)."""
    d = tmp_path / "proposal"
    d.mkdir()
    for src in LIVE_PROPOSAL.iterdir():
        (d / src.name).write_bytes(src.read_bytes().replace(b"\r\n", b"\n"))
    for name in ("protocol.yaml", "protocol.v1.yaml", "proposal.json"):
        (d / name).unlink(missing_ok=True)
    return d


def read_proposal(d: Path) -> dict[str, Any]:
    return json.loads((d / "proposal.json").read_text(encoding="utf-8"))


def add_waivers(d: Path, checks: list[str], *, by: str) -> None:
    data = yaml.safe_load((d / "decisions.yaml").read_text(encoding="utf-8"))
    data["waivers"] = [{"check": c, "reason": "accepted for the EV1 replay", "by": by} for c in checks]
    (d / "decisions.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


# the live draft predates A1, so its frozen protocol fails bounds_cover_rate_metrics too (metric_rules_collide passes:
# freeze makes the metric rules again, draft.sync_regex)
LIVE_BLOCKING = ["terms_cover_synonyms", "bounds_cover_rate_metrics"]


def test_freeze_blocks_on_uncovered_synonyms_when_the_screen_rejects_misses(copied_live_proposal: Path) -> None:
    with pytest.raises(ProposalError, match="terms_cover_synonyms"):
        freeze.run(copied_live_proposal)
    assert not (copied_live_proposal / "protocol.yaml").exists()


def test_human_waivers_unblock_and_are_recorded(copied_live_proposal: Path) -> None:
    add_waivers(copied_live_proposal, LIVE_BLOCKING, by="aditya")
    freeze.run(copied_live_proposal)
    review = read_proposal(copied_live_proposal)["review"]
    assert [w["check"] for w in review["waivers"]] == LIVE_BLOCKING
    assert all(w["by"] == "aditya" and w["reason"] for w in review["waivers"])


def test_an_unwaived_blocking_check_is_named(copied_live_proposal: Path) -> None:
    add_waivers(copied_live_proposal, LIVE_BLOCKING[:1], by="aditya")
    with pytest.raises(ProposalError, match="bounds_cover_rate_metrics") as refused:
        freeze.run(copied_live_proposal)
    assert "terms_cover_synonyms" not in str(refused.value)


def test_a_model_authored_waiver_is_refused(copied_live_proposal: Path) -> None:
    add_waivers(copied_live_proposal, ["terms_cover_synonyms"], by="model")
    with pytest.raises(ProposalError, match="waiver.*by"):
        freeze.run(copied_live_proposal)


@pytest.mark.parametrize("waiver, problem", [
    ({"check": "no_such_check", "reason": "r", "by": "aditya"}, "no_such_check"),
    ({"check": "terms_cover_synonyms", "reason": " ", "by": "aditya"}, "reason"),
    ({"check": "terms_cover_synonyms", "reason": "r", "by": ""}, "by"),
    ("terms_cover_synonyms", "mapping"),
])
def test_waivers_are_validated(waiver: Any, problem: str) -> None:
    with pytest.raises(ProposalError, match=problem):
        cards.waivers({"decisions": [], "waivers": [waiver]})
    assert cards.waivers({"decisions": []}) == []


def test_review_status_counts_who_decided(copied_live_proposal: Path) -> None:
    add_waivers(copied_live_proposal, LIVE_BLOCKING, by="aditya")
    freeze.run(copied_live_proposal)
    record = read_proposal(copied_live_proposal)
    assert record["review"]["status"] == "model_defaults"
    assert record["review"]["decided_by"] == record["decided_by"]
    assert freeze.review_status([{"by": "model"}, {"by": "AG"}]) == "partly_human"
    assert freeze.review_status([{"by": "AG"}, {"by": "TK"}]) == "human"


@pytest.mark.parametrize("who", ["Model", "MODEL", " model "])
def test_the_model_in_any_case_is_not_a_person(who: str) -> None:
    with pytest.raises(ProposalError, match="by"):
        cards.waivers({"decisions": [], "waivers": [{"check": "terms_cover_synonyms", "reason": "r", "by": who}]})
    assert freeze.review_status([{"by": who}, {"by": "model"}]) == "model_defaults"
    assert freeze.review_status([{"by": who}, {"by": "AG"}]) == "partly_human"


def test_checks_carry_a_severity(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted(), until="draft")
    text = (d / "draft.yaml").read_text(encoding="utf-8")
    found = {c["id"]: c["severity"] for c in critic.checks(text, frame.load(d / "frame.json"))}
    assert {k for k, v in found.items() if v == "blocking"} == {
        "regex_matches_enums", "bounds_cover_rate_metrics", "metric_rules_collide", "terms_cover_synonyms"}
    escalate = text.replace("lexical_miss: reject", "lexical_miss: escalate")
    assert escalate != text
    found = {c["id"]: c["severity"] for c in critic.checks(escalate, frame.load(d / "frame.json"))}
    assert found["terms_cover_synonyms"] == "advisory" and found["regex_matches_enums"] == "blocking"


def test_critic_ok_counts_only_blocking_checks(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted(), until="draft")
    draft = yaml.safe_load((d / "draft.yaml").read_text(encoding="utf-8"))
    draft["locate"] = {"strategy": "exhaustive", "params": {"top_k": 6}}          # advisory: locate_params_used
    (d / "draft.yaml").write_text(yaml.safe_dump(draft, sort_keys=False), encoding="utf-8")
    critic.run(d, model=Scripted().model)
    data = json.loads((d / "critic.json").read_text(encoding="utf-8"))
    assert not {c["id"]: c for c in data["checks"]}["locate_params_used"]["ok"]
    assert data["ok"] is True
    draft["evidence_types"]["measurement"]["bounds"] = []                          # blocking: bounds_cover_rate_metrics
    (d / "draft.yaml").write_text(yaml.safe_dump(draft, sort_keys=False), encoding="utf-8")
    critic.run(d, model=Scripted().model)
    assert json.loads((d / "critic.json").read_text(encoding="utf-8"))["ok"] is False


def test_the_draft_names_lexical_miss_without_changing_the_sha256(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted(), until="draft")
    text = (d / "draft.yaml").read_text(encoding="utf-8")
    draft = yaml.safe_load(text)
    assert draft["screen"]["lexical_miss"] == "reject"
    del draft["screen"]["lexical_miss"]
    assert load_text(text).sha256 == load_text(yaml.safe_dump(draft, sort_keys=False)).sha256


def test_a_metric_a_person_dropped_is_no_blocking_failure(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted(), until="cards")
    decide(d, "metrics", {"metrics": [{"canonical": "factual_accuracy", "higher_is_better": True}]})
    freeze.run(d)
    found = checks_of(d)
    assert not found["outcomes_complete"]["ok"] and found["outcomes_complete"]["severity"] == "advisory"
    assert found["terms_cover_synonyms"]["ok"] and found["bounds_cover_rate_metrics"]["ok"]


def test_a_metric_the_extractors_still_emit_is_checked_though_synthesis_dropped_it(tmp_path: Path) -> None:
    d = flow(tmp_path / "p", Scripted(), until="draft")
    f = frame.load(d / "frame.json")
    draft = yaml.safe_load((d / "draft.yaml").read_text(encoding="utf-8"))
    draft["synthesis"]["metrics"] = [m for m in draft["synthesis"]["metrics"] if m["canonical"] != "hallucination_rate"]
    assert "hallucination_rate" in draft["evidence_types"]["metric"]["fields"]["properties"]["canonical"]["enum"]
    draft["evidence_types"]["measurement"]["bounds"] = []
    from evidence.extractors import terms
    step = next(s for s in draft["evidence_types"]["metric"]["extractors"] if s["name"] == "regex_metric")
    step["config"] = {"metrics": [list(m) for m in terms.METRICS if m[1] != "hallucination_rate"]}   # no rule for it
    found = {c["id"]: c for c in critic.checks(yaml.safe_dump(draft, sort_keys=False), f)}
    assert found["parses"]["ok"], found["parses"]["message"]
    assert not found["bounds_cover_rate_metrics"]["ok"] and "hallucination_rate" in found["bounds_cover_rate_metrics"]["message"]
    assert not found["terms_cover_synonyms"]["ok"] and "hallucination_rate name" in found["terms_cover_synonyms"]["message"]
