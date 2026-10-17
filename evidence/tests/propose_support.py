"""Scripted replies for the proposal flow's tests (no network): a FunctionModel that answers the frame, critic
and cards calls by their instructions, the RAG question's frame, and the comparison with the hand-written
protocol."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models.function import AgentInfo, FunctionModel

from evidence.locate import tokens
from evidence.protocol import Protocol, load
from evidence.propose import cards, critic, draft, frame, freeze

from .conftest import PROTOCOL, prompt_of, respond

QUESTION = "Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?"

# The frame a careful model gives for the RAG question (the hand-written protocol's choices).
RAG_FRAME: dict[str, Any] = {
    "population": {
        "description": "Papers that report an experiment comparing a retrieval-augmented system with the same model without retrieval.",
        "screening_question": "Does the paper report an experiment that compares a retrieval-augmented system with the "
                              "same model answering without retrieval?",
        "terms": ["retrieval-augmented", "retrieval augmented", "RAG", "retrieval", "closed-book", "without retrieval"]},
    "treatment": {"role": "rag", "label": "retrieval-augmented generation", "definition": "the retrieval-augmented system",
                  "synonyms": ["RAG", "retrieval augmented"]},
    "control": {"role": "baseline", "label": "closed-book",
                "definition": "the same model answering without retrieval (closed-book).",
                "synonyms": ["without retrieval", "no-retrieval baseline"]},
    "outcomes": [{"canonical": "factual_accuracy", "label": "factual accuracy", "higher_is_better": True, "fraction": True,
                  "synonyms": ["accuracy", "exact match"]},
                 {"canonical": "hallucination_rate", "label": "hallucination rate", "higher_is_better": False,
                  "fraction": True, "synonyms": ["rate of hallucination"]}],
    "effect_labels": [{"value": "improves", "direction": "supports"}, {"value": "no_effect", "direction": "neutral"},
                      {"value": "worsens", "direction": "contradicts"}],
}

CRITIC_OK = {c: {"ok": True, "message": "fine"} for c in critic.LLM_CHECKS}


def cards_reply(defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    """Every card's default `draft` unless `defaults` says otherwise (an option id, or (model, proposal))."""
    out = {}
    for card in cards.HANDLERS:
        choice = (defaults or {}).get(card, "draft")
        if isinstance(choice, tuple):
            out[card] = {"default": choice[0], "rationale": f"{card}: the model's own value", "proposal": choice[1]}
        else:
            out[card] = {"default": choice, "rationale": f"{card}: the draft fits the question", "proposal": None}
    return out


class Scripted:
    """A FunctionModel scripted per step; `calls` lists the steps it was asked for, in order."""

    def __init__(self, frame_reply: dict[str, Any] | None = None, critic_reply: dict[str, Any] | None = None,
                 cards: dict[str, Any] | None = None) -> None:
        self.frame = copy.deepcopy(frame_reply or RAG_FRAME)
        self.critic = critic_reply or CRITIC_OK
        self.cards = cards_reply(cards)
        self.calls: list[str] = []
        self.prompts: list[str] = []
        self.model = FunctionModel(self._reply, model_name="scripted-propose")

    def _reply(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        text = info.instructions or ""
        step = ("frame" if "frame of an evidence synthesis" in text else
                "critic" if "You review a draft" in text else "cards" if "choice points" in text else "?")
        self.calls.append(step)
        self.prompts.append(prompt_of(messages))
        return respond(info, {"frame": self.frame, "critic": self.critic, "cards": self.cards}[step])


def flow(directory: Path, model: Scripted, *, vocab: str | None = "rag-factuality", question: str = QUESTION,
         until: str = "freeze") -> Path:
    """Run the steps up to `until` (frame, draft, critic, cards, freeze) with the scripted model."""
    frame.run(question, directory, vocab=vocab, model=model.model)
    if until == "frame":
        return directory
    draft.run(directory)
    if until == "draft":
        return directory
    critic.run(directory, model=model.model)
    if until == "critic":
        return directory
    cards.run(directory, model=model.model)
    if until == "cards":
        return directory
    freeze.run(directory, created="2026-10-17T12:00:00+00:00")
    return directory


def _strip_descriptions(schema: Any) -> Any:
    if isinstance(schema, dict):
        return {k: _strip_descriptions(v) for k, v in schema.items() if k != "description"}
    if isinstance(schema, list):
        return [_strip_descriptions(v) for v in schema]
    return schema


def comparable(p: Protocol) -> dict[str, Any]:
    """What test (1) compares: the parsed protocol without its id and revision, free text (descriptions, the
    screening question) and bm25 query lists (checked separately, as a superset); screen terms as a set."""
    d = p.model_dump(mode="json", exclude={"id", "revision"})
    if d.get("screen"):
        d["screen"]["question"] = None
        d["screen"]["terms"] = sorted(d["screen"]["terms"])
    for spec in d["evidence_types"].values():
        spec["description"] = None
        spec["query"] = None
        spec["fields"] = _strip_descriptions(spec["fields"])
    return d


def query_tokens(p: Protocol) -> dict[str, set[str]]:
    return {t: {x for q in spec.query for x in tokens(q)} for t, spec in p.evidence_types.items()}


def hand_written() -> Protocol:
    return load(PROTOCOL)
