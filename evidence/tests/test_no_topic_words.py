"""No topic words in code (D35): every word of every domain pack lives only in `domains/<name>/`, never in the
code folders CHECKED_DIRS, apart from the generic words of domains/allowlist.yaml (each with its reason), the
legacy files of LEGACY (each with its reason) and the few words FILE_WORDS lets one file keep (each with its reason)."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from evidence.pack import DOMAINS, load_pack

CHECKED_DIRS = ["evidence", "agent", "synth", "evaluation"]   # evaluation: plan 2 Task 14 (preflight P2)
ROOT = DOMAINS.parent
SUFFIXES = {".py", ".md", ".txt", ".yaml"}
# examples: synth/examples/rag-demo-* are committed corpora, pinned byte for byte (D36), not code.
SKIPPED = {"tests", "fixtures", "__pycache__", "examples"}
# Files kept with their topic words, by path, each with its reason (D8: replay needs their exact bytes).
_REPLAY = ("kept byte for byte so corpora built before the prompts became recipe templates replay with their "
           "cached calls (D36); the v3 template filled from the default recipe is this text")
LEGACY = {
    "synth/prompts/render.txt": _REPLAY + " (render-plain-v2.txt); its sha256 is pinned "
                                "(test_no_statements_cache_keys_are_unchanged)",
    "synth/prompts/render-v2.txt": _REPLAY + " (render-v3.txt)",
    "synth/prompts/statements-v1.txt": _REPLAY + " (statements-v2.txt)",
    "synth/prompts/blind.txt": "the blind re-extraction prompt before blind-v2.txt, kept for replay (D36)",
    "synth/prompts/blind-v2.txt": _REPLAY + " (blind-v3.txt)",
    "evaluation/baselines/prompts/map-effect-v1.md": "the effect mapping prompt before map-effect-v2.md (filled from "
                                                     "the pack's display names), kept for replay (D36)",
    # The mapping prompts of the kinds plan 2 leaves unchanged: their RAG examples are kept byte for byte so their
    # cached mapping calls still hit (plan 2 Task 14: existing kinds' prompts unchanged); a pack-filled v2 of each
    # is owed when that kind is next re-pinned.
    "evaluation/baselines/prompts/map-inventory-v1.md": "live inventory mapping prompt, unchanged for its cached "
                                                        "calls (D36); its RAG examples move to the pack in a v2",
    "evaluation/baselines/prompts/map-consistency-v1.md": "live consistency mapping prompt, unchanged for its cached "
                                                          "calls (D36); its RAG examples move to the pack in a v2",
    "evaluation/baselines/prompts/map-best-v1.md": "live best mapping prompt, unchanged for its cached calls (D36); "
                                                   "its one RAG word (in the input description) goes in a v2",
}
# Words one file may keep, by path: (the words or stems, matched as the start of a hit word; the reason). Narrower
# than the allowlist, which frees a word everywhere.
_BM25 = ("the answer-level baseline is a passage-retrieval system of any domain (BM25 over the papers): its own "
         "method word, its answer.json keys `retrieved` and `settings.retrieval`/`retriever` and the CLI flag "
         "`--retrieval`, which old answers and runbooks carry (D36)")
FILE_WORDS = {
    "evaluation/baselines/rag.py": ({"retriev"}, _BM25),
    "evaluation/cli.py": ({"retriev"}, _BM25),
}


def regex_words(pattern: str) -> set[str]:
    """The alphabetic runs of four or more letters of a regex, its escapes (\\b, \\s, \\w ...) dropped first."""
    return set(re.findall(r"[A-Za-z]{4,}", re.sub(r"\\.", " ", pattern)))


def regex_stems(pattern: str) -> set[str]:
    """The words of a regex followed by `\\w*` or `\\w+` ("hallucinat" of `\\bhallucinat\\w*`): the pattern takes
    every word that starts with them, so the check matches them as a prefix ("hallucinated", "retrieves")."""
    marked = re.sub(r"\\.", " ", re.sub(r"\\w[*+]", "\x00", pattern))   # mark the \w* first, then drop escapes
    return set(re.findall(r"([A-Za-z]{4,})\x00", marked))


def pack_stems() -> set[str]:
    """The stems (regex_stems) of every real pack's patterns, lower-cased."""
    stems: set[str] = set()
    for folder in sorted(p for p in DOMAINS.iterdir() if (p / "pack.yaml").is_file()):
        w = load_pack(folder.name).words
        patterns = [p for ps in w.conditions.values() for p in ps]
        patterns += [w.not_a_system, w.claim_subject, w.dataset_pattern]
        patterns += [p for p, _, _ in (*w.metrics, *w.metric_supplement)] + [p for p, _ in w.claims]
        for p in patterns:
            stems |= regex_stems(p)
    return {x.lower() for x in stems}


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
    """The .py, .md, .txt and .yaml files under `dirs`, without tests/, fixtures, examples and the LEGACY files."""
    return sorted(f for d in dirs for f in (ROOT / d).rglob("*")
                  if f.suffix in SUFFIXES and f.is_file() and not SKIPPED & set(f.relative_to(ROOT).parts)
                  and f.relative_to(ROOT).as_posix() not in LEGACY)


def text_of(f: Path) -> str:
    return f.read_text(encoding="utf-8")


def test_pack_words_reduce_patterns_to_words() -> None:
    assert regex_words(r"(?i)\bclosed[- ]book(?:\s+(?:baseline|LLM))?") == {"closed", "book", "baseline"}
    assert literal_words("closed-book model") == {"closed-book", "model"}
    assert regex_stems(r"(?i)\bhallucinat\w*|\bunsupported\b|\bretriev\w+") == {"hallucinat", "retriev"}
    assert {"hallucinat", "retriev"} <= pack_stems()
    assert {"retrieval", "rag", "closed-book", "factual_accuracy", "hallucination", "retriever", "reader"} <= pack_words()


def test_every_allowlisted_word_is_a_pack_word() -> None:
    assert allowlist() - pack_words() == set()


def test_every_legacy_file_exists_and_names_its_reason() -> None:
    assert all((ROOT / path).is_file() and reason.strip() for path, reason in LEGACY.items())
    assert all((ROOT / path).is_file() and words and reason.strip() for path, (words, reason) in FILE_WORDS.items())


def kept(path: str, word: str) -> bool:
    """`word` is one FILE_WORDS lets `path` keep."""
    return any(word.lower().startswith(w) for w in FILE_WORDS.get(path, ((), ""))[0])


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
    """A pack word is matched as a whole word; a stem (a word its pattern follows with `\\w*`) as the start of any
    word, so "retrieves" and "hallucinated" are caught. An allowlisted stem is checked as neither."""
    allowed = allowlist()
    stems = pack_stems() - allowed
    checks = [(w, rf"\b{re.escape(w)}\b") for w in sorted(pack_words() - allowed - stems)]
    checks += [(w, rf"\b{re.escape(w)}") for w in sorted(stems)]
    hits = [(f.relative_to(ROOT).as_posix(), w) for f in code_files(CHECKED_DIRS) for w, rx in checks
            if not kept(f.relative_to(ROOT).as_posix(), w) and re.search(rx, text_of(f), re.I)]
    assert hits == []
