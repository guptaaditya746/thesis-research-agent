"""Open claim records (Task 5.1): regex candidates, DSPy ReadClaim confirms, GroupRelations groups the verbs."""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

import pytest

from agent.anchor import selector_at, text_sha256
from evidence import claims, steps
from evidence.claims import find_claims, group_relations
from evidence.contract import DocumentRef, Span
from evidence.records import ClaimRecord, item
from modelcall.cache import JsonlCache
from modelcall.dspy_lm import RecordedLM

CFG = {"subject": r"(?i)\bRAG\b|\bretriev\w*|\bdataset\b",
       "cues": ["improves: outperforms", "improves: reduces", "improves: raises", "improves: boosts", "other: largest",
                "improves: suggests"]}


def doc_of(text: str) -> DocumentRef:
    return DocumentRef(id="P", file="papers/P.md", sha256=text_sha256(text))


def reply(**kw) -> str:
    base = {"is_claim": True, "subject": "RAG", "relation": "", "object": None, "setting": {}, "strength": "firm",
            "direction": None}
    return json.dumps({**base, **kw})


class Fake:
    """Answers each prompt with the reply of the first key it contains; records the prompts."""

    def __init__(self, table: dict[str, str]):
        self.table, self.seen = table, []

    def __call__(self, prompt: str, **_) -> str:
        prompt = prompt[prompt.index("[user]"):]   # the instructions hold example sentences of their own
        self.seen.append(prompt)
        for key, out in self.table.items():
            if key in prompt:
                return out
        raise AssertionError(f"unscripted prompt: {prompt[-300:]}")


@pytest.fixture
def lm(tmp_path, monkeypatch):
    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")

    def make(table):
        fake = Fake(table)
        steps.configure(RecordedLM("alias", fake, cache=JsonlCache(tmp_path / "c.jsonl")))
        return fake
    return make


def test_non_comparison_claim_kept(lm):
    text = "Our dataset is the largest of its kind.\n"
    lm({"largest": reply(subject="our dataset", relation="is the largest", object="of its kind")})
    [rec] = find_claims(text, doc_of(text), CFG)
    assert (rec.relation, rec.direction, rec.strength) == ("is the largest", None, "firm")
    assert rec.span.selector["exact"] == text.strip()
    assert item(rec).evidence_type == "claim"


def test_hedged(lm):
    text = "The results suggests RAG outperforms the baseline.\n"
    lm({"suggests": reply(relation="outperforms", object="the baseline", strength="hedged", direction="improves")})
    [rec] = find_claims(text, doc_of(text), CFG)
    assert rec.strength == "hedged" and rec.direction == "improves"


def test_comparison_maps_direction(lm):
    text = "RAG reduces hallucination.\n"
    lm({"reduces": reply(relation="reduces", object="hallucination", direction="improves")})
    [rec] = find_claims(text, doc_of(text), CFG)
    assert rec.direction == "improves"


def test_not_a_claim_and_no_cue_are_dropped(lm):
    text = "RAG is described in Section 2. Retrieval raises the question of cost.\n"
    fake = lm({"Section 2": reply(is_claim=True), "question of cost": reply(is_claim=False)})
    # the first sentence has no cue word: never sent to the model; the second is rejected by the model
    assert find_claims(text, doc_of(text), CFG) == []
    assert len(fake.seen) == 1


def test_bad_direction_is_a_parse_error(lm):
    text = "RAG boosts accuracy.\n"
    lm({"boosts": reply(relation="boosts", direction="sideways")})
    with pytest.raises(Exception):
        find_claims(text, doc_of(text), CFG)


def test_old_rag_claims_are_candidates():
    """Checks the regex and plumbing only: with a stand-in model that copies the old patterns' labels, >= 95% of the old
    claims of a committed EV2 corpus are found as candidates and carried through with a checked span. Whether the real
    ReadClaim keeps the old labels is a runbook check (Task 8.4), not tested here."""
    from evidence.extractors import base
    from evidence.pack import load_pack
    words = load_pack("rag").extractor_config("author_claim", "regex_author_claim")
    old = [(re.compile(p), d) for p, d in words["claims"]]
    subject = re.compile(words["subject"])
    skip = re.compile(r"(?i)\bwhether\b|\?|\bif\b|\bprior work\b|\bprevious work\b")
    corpus = Path(__file__).resolve().parents[2] / "tests/EV2/corpora/rag-claude-k1-explicit/papers"

    def model(prompt: str, **_) -> str:   # stands in for the model: labels a sentence as the old patterns do
        sentence = re.search(r"\[\[ ## sentence ## \]\]\n(.*?)\n\nRespond", prompt[prompt.index("[user]"):], re.S).group(1)
        return reply(relation="x", direction=next((d for p, d in old if p.search(sentence)), None))

    steps.configure(RecordedLM("alias", model, cache=None))
    cues = ["improve", "reduce", "outperform", "improvement", "hurt", "increase", "boost", "raise", "unchanged", "effect",
            "harm", "degrade", "accurate", "factual", "par with", "difference", "less", "lower", "fewer", "decrease",
            "hallucinat", "lowers", "gain", "benefit", "change", "worsen", "impair", "cut", "enhance", "fail", "not"]
    cfg = {"subject": words["subject"], "cues": [f"improves: {c}" for c in cues]}
    total = same = 0
    missed: list[str] = []
    for path in sorted(corpus.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        expected = {}
        for s, e in base.sentences(text):
            sent = text[s:e]
            if subject.search(sent) and not skip.search(sent):
                d = next((d for p, d in old if p.search(sent)), None)
                if d:
                    expected[(s, e)] = d
        got = {(r.span.selector["start"], r.span.selector["end"]): r.direction for r in find_claims(text, doc_of(text), cfg)}
        for k, d in expected.items():
            total += 1
            if got.get(k) == d:
                same += 1
            else:
                missed.append(f"{path.name}:{k}: {text[k[0]:k[1]]!r} old={d} new={got.get(k)}")
    assert total > 0
    assert same / total >= 0.95, "\n".join(missed)


def grouping_reply(groups: dict[str, list[str]]) -> str:
    return json.dumps({"groups": groups})


def span_of(word: str) -> Span:
    text = f"RAG {word} accuracy."
    return Span.of("claim", selector_at(text, 0, len(text), file="papers/P.md", sha256=text_sha256(text)))


def test_raises_and_boosts_grouped(lm):
    lm({"boosts": grouping_reply({"increases": ["raises", "boosts"]})})
    mapping = group_relations(["raises", "boosts", "raises"])
    assert mapping == {"boosts": "increases", "raises": "increases"}
    recs = [ClaimRecord(subject="RAG", relation=v, object="accuracy", setting={}, strength="firm", direction="improves",
                        span=span_of(v)) for v in ("raises", "boosts")]
    grouped = claims.apply_groups(recs, mapping)
    assert {r.relation_group for r in grouped} == {"increases"}
    assert claims.count_by_group(grouped) == {"increases": 2}
    assert claims.grouped_line(mapping) == "grouped: boosts, raises → increases"
    assert [r.relation for r in recs] == ["raises", "boosts"]   # the paper's own verb is kept


def test_unplaced_verb_shown_as_other(lm):
    lm({"raises": grouping_reply({"increases": ["raises"]})})
    mapping = group_relations(["raises", "gaslights"])
    assert mapping["gaslights"] == "other: gaslights"
    assert "other: gaslights" in claims.grouped_line(mapping)
    assert set(mapping) == {"raises", "gaslights"}   # never dropped


def test_reads_are_recorded_under_their_own_ctx(tmp_path, monkeypatch):
    """Two threads with two ctxs: each model call is recorded under the ctx of the paper that made it."""
    monkeypatch.setattr(steps, "TUNED_DIR", tmp_path / "tuned")
    seen: dict[str, list[str]] = {"a": [], "b": []}

    class Ctx:
        def __init__(self, name: str):
            self.name = name

        def dspy_lm(self, purpose: str):
            def ask(prompt: str, **_):
                seen[self.name].append(prompt[prompt.index("[user]"):])
                return reply(relation="boosts", direction="improves")
            return RecordedLM("alias", ask, cache=None)

    texts = {n: "\n\n".join(f"RAG boosts accuracy {n}{i}." for i in range(6)) for n in "AB"}
    barrier = threading.Barrier(2)

    def work(name: str) -> None:
        barrier.wait()
        find_claims(texts[name], doc_of(texts[name]), CFG, ctx=Ctx(name.lower()))

    threads = [threading.Thread(target=work, args=(n,)) for n in "AB"]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(seen["a"]) == 6 and len(seen["b"]) == 6
    assert all("accuracy A" in p for p in seen["a"]) and all("accuracy B" in p for p in seen["b"])


def test_claim_stage_subject_defaults_to_the_plans_compiled_words():
    from types import SimpleNamespace

    from evidence.claims import candidate_sentences, claim_stage
    from evidence.plan import WordList
    from evidence.words.compile import compile_words
    words = WordList(things={"method_a": ["Method A"]}, cues=["improves: shortens"], written_by="x", ontology_names={})
    seen: list[dict] = []
    import evidence.claims as claims_mod
    original = claims_mod.find_claims
    claims_mod.find_claims = lambda text, document, cfg, ctx=None: seen.append(cfg) or []
    try:
        plan = SimpleNamespace(words=words, measures=[])
        claim_stage()(SimpleNamespace(text="Method A shortens the delay.", doc=None), SimpleNamespace(plan=plan))
    finally:
        claims_mod.find_claims = original
    assert seen[0]["subject"] == compile_words(words)["subject"]
    assert candidate_sentences("Method A shortens the delay.", seen[0]) == [(0, 28)]
