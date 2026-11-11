"""`evidence estimate`: how many model calls and tokens a run will need, before it is made (spec D41).

The estimate runs the regex extractors over the corpus (no provider, no model call, in a temporary folder) to see
which papers the screen stops, then counts the LLM and agent positions of the cascade the run would use. Only
extractor and screen calls are counted: the model calls can be more (a long paper is read in chunks, a rejected
quote is retried), and the result says so in `note`. With `names on` the names check's model calls are added
(`names_checks`): an upper bound from the names the regex pass leaves unresolved, each asked about at most
names.CHECKS_PER_NAME groups; the LLM extractors can find more names, so it is a guide, not a ceiling."""
from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Any

from .engine import Names, Selection, Settings, Strategy, build_extractors, execute_run
from .names import CHECKS_PER_NAME
from .protocol import SCREEN_TYPE, parse
from .rundir import FUNNEL_FILE, NAMES_FILE, RUN_FILE, Corpus, read_json

CHARS_PER_TOKEN = 4
PROMPT_TOKENS = 1500
OUTPUT_TOKENS = 1024
LLM_KINDS = ("llm", "agent")
NOTE = ("calls counts extractor and screen calls; the model calls can be more (a long paper is read in chunks, a "
        "rejected quote is retried); under strategy all, low equals high, although a `cascade: until_found` "
        "step can stop earlier; names checks are counted only with --names on (names_checks)")


def _per_call(from_run: Path | str | None) -> tuple[tuple[float, float] | None, str]:
    """(input, output) tokens per model call of a finished run, or None for the chars/4 rule; and the basis."""
    if from_run is None:
        return None, "chars/4"
    record = read_json(Path(from_run) / RUN_FILE)
    cost = record["cost"]
    made = cost["made_model_calls"]
    if not made:   # a fully cached or replayed run has no fresh call to average
        return None, f"chars/4 (run {record['run_id']} made no fresh calls)"
    return (cost["input_tokens"] / made, cost["output_tokens"] / made), f"run {record['run_id']}"


def estimate(protocol: Path | str, corpus: Path | str, *, strategy: Strategy = "gaps", selection: Selection = "cascade",
             from_run: Path | str | None = None, domains: Path | str | None = None,
             names: Names = "off") -> dict[str, Any]:
    """The calls and tokens of `evidence run` with this protocol, corpus, strategy and extractor selection.

    The regex-only run decides which papers the screen stops. Under `all` no paper is skipped (the screen
    decision is only recorded), and a screen with `lexical_miss: escalate` passes its regex misses on to the
    LLM screen, so in both cases every paper is counted as reaching the LLM."""
    per_call, basis = _per_call(from_run)
    protocol_bytes = Path(protocol).read_bytes()
    parsed = parse(protocol_bytes.decode("utf-8"), domains)
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(corpus=str(Path(corpus).resolve()), cache=str(Path(tmp) / "cache"), selection="regex-only",
                            strategy="gaps", reason="off", names=names,
                            domains=str(Path(domains).resolve()) if domains is not None else None)
        root = execute_run(protocol_bytes, settings, tmp, provider=None)
        funnel = read_json(root / FUNNEL_FILE)["documents"]
        leftovers = len((read_json(root / NAMES_FILE) or {}).get("unresolved") or []) if names == "on" else 0
    cascades = build_extractors(parsed, selection)            # the requested cascade: the run above kept only regex
    llm = {t: [i for i, (_, e) in enumerate(c) if e.spec.kind in LLM_KINDS] for t, c in cascades.items()}
    screen_calls = len(llm.get(SCREEN_TYPE, []))
    typed = {t: p for t, p in llm.items() if t != SCREEN_TYPE}
    high_each = screen_calls + sum(len(p) for p in typed.values())
    low_each = high_each if strategy == "all" else screen_calls + sum(1 for p in typed.values() if 0 in p)
    corpus_reader = Corpus(corpus)
    papers = corpus_reader.papers
    screened = {p.id for p in papers if funnel.get(p.id, {}).get("skipped")}
    if strategy == "all":
        reach_basis = "all papers (strategy all: no paper is skipped)"
    elif parsed.screen is not None and parsed.screen.lexical_miss == "escalate" and screen_calls > 0:
        reach_basis = "all papers (lexical_miss escalate: a regex miss still reaches the LLM screen)"
    else:
        reach_basis = "papers the regex screen did not stop"
    reaching = [p for p in papers if reach_basis.startswith("all") or p.id not in screened]
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
    out: dict[str, Any] = {}
    if names == "on":   # the model check of the names left unresolved (none under regex-only: it asks no model)
        checks = leftovers * CHECKS_PER_NAME if selection != "regex-only" else 0
        tokens_in, tokens_out = per_call if per_call is not None else (PROMPT_TOKENS, OUTPUT_TOKENS)
        totals["high"] += checks
        tokens["input"]["high"] += checks * tokens_in
        tokens["output"]["high"] += checks * tokens_out
        out["names_checks"] = {"low": 0, "high": checks, "unresolved_after_regex": leftovers,
                               "basis": f"names the regex pass leaves unresolved x {CHECKS_PER_NAME}"}
    return {"papers": len(papers), "screened_out": len(screened), "papers_reaching_llm": len(reaching),
            "reach_basis": reach_basis, "calls": totals, **out,
            "tokens": {k: {b: math.ceil(v) for b, v in t.items()} for k, t in tokens.items()},
            "basis": basis, "note": NOTE}
