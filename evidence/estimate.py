"""`evidence estimate`: how many model calls and tokens a run will need, before it is made (spec D41).

The estimate runs the regex extractors over the corpus (no provider, no model call, in a temporary folder) to see
which papers the screen stops, then counts the LLM and agent positions of the cascade the run would use. Only
extractor and screen calls are counted: the model calls can be more (a long paper is read in chunks, a rejected
quote is retried), and the result says so in `note`."""
from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Any

from .engine import Selection, Settings, Strategy, build_extractors, execute_run
from .protocol import SCREEN_TYPE, parse
from .rundir import Corpus, read_json

CHARS_PER_TOKEN = 4
PROMPT_TOKENS = 1500
OUTPUT_TOKENS = 1024
LLM_KINDS = ("llm", "agent")
NOTE = ("calls counts extractor and screen calls; the model calls can be more (a long paper is read in chunks, a "
        "rejected quote is retried)")


def _per_call(from_run: Path | str | None) -> tuple[tuple[float, float] | None, str]:
    """(input, output) tokens per model call of a finished run, or None for the chars/4 rule; and the basis."""
    if from_run is None:
        return None, "chars/4"
    record = read_json(Path(from_run) / "run.json")
    cost = record["cost"]
    made = cost["made_model_calls"]
    if not made:
        raise ValueError(f"{from_run}: the run made no model call, so it has no tokens per call")
    return (cost["input_tokens"] / made, cost["output_tokens"] / made), f"run {record['run_id']}"


def estimate(protocol: Path | str, corpus: Path | str, *, strategy: Strategy = "gaps", selection: Selection = "cascade",
             from_run: Path | str | None = None, domains: Path | str | None = None) -> dict[str, Any]:
    """The calls and tokens of `evidence run` with this protocol, corpus, strategy and extractor selection.

    The regex-only run decides which papers the screen stops. Under `all` no paper is skipped (the screen
    decision is only recorded), and a screen with `lexical_miss: escalate` passes its regex misses on to the
    LLM screen, so in both cases every paper is counted as reaching the LLM."""
    per_call, basis = _per_call(from_run)
    protocol_bytes = Path(protocol).read_bytes()
    parsed = parse(protocol_bytes.decode("utf-8"), domains)
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(corpus=str(Path(corpus).resolve()), cache=str(Path(tmp) / "cache"), selection="regex-only",
                            strategy="gaps", reason="off",
                            domains=str(Path(domains).resolve()) if domains is not None else None)
        root = execute_run(protocol_bytes, settings, tmp, provider=None)
        funnel = read_json(root / "funnel.json")["documents"]
    cascades = build_extractors(parsed, selection)            # the requested cascade: the run above kept only regex
    llm = {t: [i for i, (_, e) in enumerate(c) if e.spec.kind in LLM_KINDS] for t, c in cascades.items()}
    screen_calls = len(llm.get(SCREEN_TYPE, []))
    typed = {t: p for t, p in llm.items() if t != SCREEN_TYPE}
    high_each = screen_calls + sum(len(p) for p in typed.values())
    low_each = high_each if strategy == "all" else screen_calls + sum(1 for p in typed.values() if 0 in p)
    corpus_reader = Corpus(corpus)
    papers = corpus_reader.papers
    screened = {p.id for p in papers if funnel.get(p.id, {}).get("skipped")}
    keeps_all = strategy == "all" or (parsed.screen is not None and parsed.screen.lexical_miss == "escalate"
                                      and screen_calls > 0)
    reaching = [p for p in papers if keeps_all or p.id not in screened]
    totals = {"low": 0, "high": 0}
    tokens = {"input": dict.fromkeys(("low", "high"), 0.0), "output": dict.fromkeys(("low", "high"), 0.0)}
    for paper in reaching:
        if per_call is None:
            tokens_in = math.ceil(len(corpus_reader.text(paper)) / CHARS_PER_TOKEN) + PROMPT_TOKENS
            tokens_out = OUTPUT_TOKENS
        else:
            tokens_in, tokens_out = per_call
        for bound, each in (("low", low_each), ("high", high_each)):
            totals[bound] += each
            tokens["input"][bound] += each * tokens_in
            tokens["output"][bound] += each * tokens_out
    return {"papers": len(papers), "screened_out": len(screened), "papers_reaching_llm": len(reaching),
            "calls": totals, "tokens": {k: {b: math.ceil(v) for b, v in t.items()} for k, t in tokens.items()}, "basis": basis, "note": NOTE}
