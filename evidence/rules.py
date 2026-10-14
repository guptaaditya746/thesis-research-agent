"""The deterministic synthesis rules, shared by the engine (from extracted evidence) and the benchmark
generator (from ground truth), so both sides of the comparison use the very same definitions.

Question: "Does retrieval-augmented generation improve the factual accuracy of LLM-generated answers?"
"""
from __future__ import annotations

from typing import Literal

Direction = Literal["supports", "contradicts", "neutral"]
ClaimDirection = Literal["improves", "no_effect", "worsens"]
Label = Literal["supported", "refuted", "mixed", "no_effect", "insufficient"]

METRICS = {"factual_accuracy": True, "hallucination_rate": False}   # canonical metric -> higher is better
MIN_EFFECT = 0.01                                                     # |delta| below this is neutral (fractions)


def effect(rag: float, baseline: float, higher_is_better: bool, min_effect: float = MIN_EFFECT) -> tuple[Direction, float]:
    """Direction of one study's effect and its signed improvement (positive = RAG better)."""
    delta = round((rag - baseline) if higher_is_better else (baseline - rag), 6)
    if abs(delta) < min_effect:
        return "neutral", delta
    return ("supports" if delta > 0 else "contradicts"), delta


def claim_agrees(claim: ClaimDirection, direction: Direction) -> bool:
    return {"improves": "supports", "worsens": "contradicts", "no_effect": "neutral"}[claim] == direction


def label(supporting: int, contradicting: int, neutral: int) -> Label:
    """The answer from per-study directions: one fixed rule, no weighting."""
    if supporting and contradicting:
        return "mixed"
    if supporting:
        return "supported"
    if contradicting:
        return "refuted"
    if neutral:
        return "no_effect"
    return "insufficient"
