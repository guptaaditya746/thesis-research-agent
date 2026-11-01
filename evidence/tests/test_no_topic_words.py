"""No topic words in code (D35): every word of every domain pack lives only in `domains/<name>/`, never in the
code folders CHECKED_DIRS, apart from the generic words of domains/allowlist.yaml (each with its reason)."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from evidence.pack import DOMAINS, load_pack

CHECKED_DIRS = ["evidence", "agent"]
ROOT = DOMAINS.parent
SUFFIXES = {".py", ".md", ".txt", ".yaml"}
SKIPPED = {"tests", "fixtures", "__pycache__"}


def regex_words(pattern: str) -> set[str]:
    """The alphabetic runs of four or more letters of a regex, its escapes (\\b, \\s, \\w ...) dropped first."""
    return set(re.findall(r"[A-Za-z]{4,}", re.sub(r"\\.", " ", pattern)))


def literal_words(text: str) -> set[str]:
    """The whitespace-separated tokens of a literal term that hold a letter ("closed-book" stays one word)."""
    return {t for t in text.split() if re.search(r"[A-Za-z]", t)}


def pack_words() -> set[str]:
    """Every word of every real pack (a folder directly under domains/ with a pack.yaml): words.yaml's patterns
    reduced to their words, its literal terms, its enum values (condition roles, canonical metrics, claim
    directions), its system nouns and the pack's display names. Lower-cased; the check ignores case."""
    words: set[str] = set()
    for folder in sorted(p for p in DOMAINS.iterdir() if (p / "pack.yaml").is_file()):
        pack = load_pack(folder.name)
        w = pack.words
        patterns = [p for ps in w.conditions.values() for p in ps]
        patterns += [w.not_a_system, w.claim_subject, w.dataset_pattern]
        patterns += [p for p, _, _ in (*w.metrics, *w.metric_supplement)] + [p for p, _ in w.claims]
        for p in patterns:
            words |= regex_words(p)
        enums = [*w.conditions, *w.fraction_metrics, *(c for _, c, _ in (*w.metrics, *w.metric_supplement)),
                 *(d for _, d in w.claims)]
        literals = [*w.screen_terms, *w.system_nouns, *(t for ts in w.query.values() for t in ts),
                    *(t for ts in w.gliner_labels.values() for t in ts), *pack.display.values(), *enums]
        for t in literals:
            words |= literal_words(t)
    return {x.lower() for x in words}


def allowlist() -> set[str]:
    """The generic words of domains/allowlist.yaml; every entry names its reason."""
    entries = yaml.safe_load((DOMAINS / "allowlist.yaml").read_text(encoding="utf-8"))
    for e in entries:
        assert set(e) == {"word", "reason"} and e["reason"].strip(), f"allowlist entry needs word and reason: {e}"
    return {e["word"].lower() for e in entries}


def code_files(dirs: list[str]) -> list[Path]:
    """The .py, .md, .txt and .yaml files under `dirs`, without tests/ and fixtures."""
    return sorted(f for d in dirs for f in (ROOT / d).rglob("*")
                  if f.suffix in SUFFIXES and f.is_file() and not SKIPPED & set(f.relative_to(ROOT).parts))


def text_of(f: Path) -> str:
    return f.read_text(encoding="utf-8")


def test_pack_words_reduce_patterns_to_words() -> None:
    assert regex_words(r"(?i)\bclosed[- ]book(?:\s+(?:baseline|LLM))?") == {"closed", "book", "baseline"}
    assert literal_words("closed-book model") == {"closed-book", "model"}
    assert {"retrieval", "rag", "closed-book", "factual_accuracy", "hallucination", "retriever", "reader"} <= pack_words()


def test_every_allowlisted_word_is_a_pack_word() -> None:
    assert allowlist() - pack_words() == set()


def test_moved_prompt_words_fill_the_default_pack_prompts_as_before() -> None:
    """Migration check: the propose prompts filled from domains/rag/propose.yaml are the texts they had before
    their topic words moved (sha256 of the text at 8fd6ae6), so cached proposal calls still match."""
    import hashlib

    from evidence.propose.common import prompt
    before = {"cards-v3.md": "8c3a7ab46e92fd886dfb53be7f27c89316f0a3ca630727449e4a6865941e3e7a",
              "frame-v2.md": "d74bfbc3f4707c6c634493536e0e8bbc7df36dd0456cc73e87e58890c2715c80",
              "frame-v3.md": "202fd5bf243227a9a81190c9f3e508efa02413d09d2a25d3d2044038f12e2108"}
    assert {n: hashlib.sha256(prompt(n).encode()).hexdigest() for n in before} == before


def test_no_pack_word_appears_in_checked_code() -> None:
    words = pack_words() - allowlist()
    hits = [(str(f.relative_to(ROOT)), w) for f in code_files(CHECKED_DIRS) for w in sorted(words)
            if re.search(rf"\b{re.escape(w)}\b", text_of(f), re.I)]
    assert hits == []
