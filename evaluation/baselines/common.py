"""What both baselines share: the corpus as a system under test sees it, the reply schema, answer.json.

Hard rule (docs/evidence-system.md Part A): a baseline reads `manifest.json` and the files it lists
under `papers/`, nothing else of the corpus directory. `SystemCorpus` is the only reader the baselines
use; it opens exactly those files, checks each against its manifest sha256, and refuses (allow-list)
any listed file that does not resolve to a file directly in `<corpus>/papers/`, so neither
ground_truth.json, corpus.json, fidelity.json, decoys.json nor any later evaluation file can be read.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai.models import Model

from agent.canonical import sha256_hex
from evidence import protocol as protocol_module, rules
from gold.llm import JsonlCache, cache_key, model_name, prompt_sha256, redact, settings, structured_reply

DEFAULT_PROTOCOL = Path(__file__).resolve().parents[2] / "evidence" / "protocols" / "rag-factuality.yaml"
DEFAULT_QUESTION = "Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?"
Stance = Literal["supports", "contradicts", "neutral"]
GROUPS = {"supports": "supporting", "contradicts": "contradicting", "neutral": "neutral"}


@dataclass(frozen=True)
class Paper:
    id: str
    file: str
    text: str


class SystemCorpus:
    """manifest.json and papers/ of a corpus, read and hash-checked; never anything else."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        self.corpus_id: str = manifest.get("corpus_id", self.root.name)
        self.papers: list[Paper] = []
        for entry in manifest["papers"]:
            file = entry.get("file") or f"papers/{entry['id']}.md"
            path = (self.root / file).resolve()
            if path.parent != self.root / "papers":
                raise ValueError(f"manifest lists {file!r}, which a system under test may not read "
                                 "(only files in papers/)")
            data = path.read_bytes()
            if entry.get("sha256") and sha256_hex(data) != entry["sha256"]:
                raise ValueError(f"{file}: sha256 differs from the manifest")
            self.papers.append(Paper(entry["id"], PurePosixPath(file).as_posix(), data.decode("utf-8")))

    @property
    def ids(self) -> list[str]:
        return [p.id for p in self.papers]


class StudyStance(BaseModel):
    document: str = Field(description="paper id, e.g. S001")
    stance: Stance = Field(description="what this paper's evidence says about the question")


class AnswerReply(BaseModel):
    """The one schema both baselines' model calls are decoded under."""
    label: rules.Label = Field(description="supported, refuted, mixed, no_effect or insufficient")
    studies: list[StudyStance] = Field(description="one entry per paper the answer relies on")
    answer_text: str = Field(description="the answer in a few sentences")


LABEL_RULES = """Labels (the same rule for every system):
- supported: at least one paper shows retrieval improving factual accuracy (or lowering hallucination) and none shows it worsening;
- refuted: at least one paper shows it worsening and none improving;
- mixed: some papers show an improvement and others a worsening;
- no_effect: the papers show only differences too small to matter;
- insufficient: the evidence does not answer the question.
Stance per paper: supports (retrieval improved the result), contradicts (retrieval made it worse), neutral (no real difference)."""


def answer_json(system: str, question: str, reply: AnswerReply, known: list[str], **extra: Any) -> dict[str, Any]:
    """answer.json (section 4) for a baseline: the model's label and per-paper stances, as stated.

    Entries for papers not in the corpus are dropped (listed in `dropped`); a paper named twice keeps
    its first stance. `label_by_rule` is evidence.rules.label over the stated stances by the label table of
    the default protocol (the baseline reads no corpus file for it), for reference; the score uses the
    model's own `label`.
    """
    studies, dropped, seen = [], [], set()
    for s in reply.studies:
        if s.document not in known:
            dropped.append(s.document)
        elif s.document not in seen:
            seen.add(s.document)
            studies.append({"document": s.document, "direction": s.stance})
    studies.sort(key=lambda s: s["document"])
    groups = {g: [s["document"] for s in studies if s["direction"] == d] for d, g in GROUPS.items()}
    counts = {g: len(v) for g, v in groups.items()} | {"undetermined": 0}
    return {"system": system, "question": question, "label": reply.label, "counts": counts, "studies": studies,
            **groups, "undetermined": [], "answer_text": reply.answer_text,
            "label_by_rule": rules.label(counts, protocol_module.load(DEFAULT_PROTOCOL).synthesis.table),
            "dropped": dropped, **extra}


def cached_reply(cache: JsonlCache | None, instructions: str, prompt: str, *, model: Model, model_id: str | None,
                 seed: int = 0, max_tokens: int = 4096) -> tuple[AnswerReply, dict[str, Any]]:
    """One schema-constrained call (temperature 0, fixed seed), cached by prompt hash, model and input.

    Returns the reply and its record: model, served model, tokens, prompt hash, cache key, whether it
    came from the cache. The key never contains the API key (gold.llm reads it from the environment).
    """
    record = {"prompt_sha256": prompt_sha256(instructions, AnswerReply), "model": model_id or model_name(model),
              "input_sha256": sha256_hex(prompt.encode("utf-8")),
              "settings": {"temperature": 0.0, "seed": seed, "max_tokens": max_tokens}}
    key = cache_key(record)
    hit = cache.get(key) if cache is not None else None
    if hit is not None:
        return AnswerReply.model_validate(hit["output"]), record | {"key": key, "cached": True} | hit["usage"]
    try:
        reply = asyncio.run(structured_reply(instructions, prompt, AnswerReply, model=model,
                                             model_settings=settings(seed=seed, max_tokens=max_tokens)))
    except Exception as exc:  # provider errors can echo the key: never let it reach a log
        raise RuntimeError(redact(f"{type(exc).__name__}: {exc}")) from None
    usage = {"served_model": reply.served_model, "input_tokens": reply.input_tokens,
             "output_tokens": reply.output_tokens}
    if cache is not None:
        cache.put(key, {"output": reply.output.model_dump(mode="json"), "usage": usage})
    return reply.output, record | {"key": key, "cached": False} | usage
