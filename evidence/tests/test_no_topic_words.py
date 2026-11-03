"""No topic words in code (D35): every word of every domain pack lives only in `domains/<name>/`, never in the
code folders CHECKED_DIRS, apart from the generic words of domains/allowlist.yaml (each with its reason), the
legacy files of LEGACY (each with its reason) and the few words FILE_WORDS lets one file keep (each with its reason)."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from evidence.pack import DOMAINS, load_pack

# evaluation: plan 2 Task 14 (preflight P2); packbuilder: its prompts are where topic examples creep in (D35)
CHECKED_DIRS = ["evidence", "agent", "synth", "evaluation", "packbuilder", "webapp"]
ROOT = DOMAINS.parent
SUFFIXES = {".py", ".md", ".txt", ".yaml", ".ts", ".tsx"}
# examples: synth/examples/rag-demo-* are committed corpora, pinned byte for byte (D36), not code.
# webapp: dependencies, the build, the mock data and the public folder are not code of ours (F41)
SKIPPED = {"tests", "fixtures", "__pycache__", "examples", "node_modules", "dist", "mocks", "public"}
# generated file of the web app: the API types are written by openapi-typescript
GENERATED = {"webapp/web/src/api/schema.d.ts"}
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
    # The baselines' mapping prompts before plan 2 Task 14 filled them from the pack (map-<kind>-v2.md): no code
    # loads them; kept byte for byte so mapping calls cached before plan 2 can be replayed by hand (D36).
    **{f"evaluation/baselines/prompts/map-{kind}-v1.md": f"replay only: the {kind} mapping prompt before "
       f"map-{kind}-v2.md (filled from the pack); MAP_PROMPTS no longer names it (D36)"
       for kind in ("effect", "inventory", "consistency", "best")},
}
# Words one file may keep, by path: (the words or stems, matched as the start of a hit word; the reason). Narrower
# than the allowlist, which frees a word everywhere.
_BM25 = ("the answer-level baseline is a passage-retrieval system of any domain (BM25 over the papers): its own "
         "method word, its answer.json keys `retrieved` and `settings.retrieval`/`retriever` and the CLI flag "
         "`--retrieval`, which old answers and runbooks carry (D36)")
_QID = ("`rag-factuality` is the id of the repo's default question (domains/rag/questions.yaml): it names the "
        "run folders the baselines wrote (runs/<system>/<corpus>, D36), an id and not text a user reads")
FILE_WORDS = {
    "evaluation/baselines/rag.py": ({"retriev"}, _BM25),
    "evaluation/baselines/real.py": ({"retriev"}, _BM25),
    "evaluation/cli.py": ({"retriev"}, _BM25),
    # plan 3 (D42), checked here since the merge with plan 2 widened CHECKED_DIRS to evaluation/
    "evaluation/realpapers/scilead.py": ({"generation", "perplexity"},
                                         "the SciLead release is quoted as its authors name it: their repository (leaderboard-generation) and the lower-is-better metrics of their code; the values come from domains/ml/metrics.yaml"),
    "evaluation/realpapers/yun.py": ({"increased", "decreased"},
                                     "Evidence Inference 2.0's label vocabulary, quoted as its release writes it "
                                     "('significantly increased' / 'significantly decreased'), is the gold the "
                                     "engine's direction is mapped onto (D42)"),
    # the web app (plan 3 Task 14): ids and field names of the answer-level baseline and of the default question,
    # never text shown to a user; the user-facing topic words come from EvRunDetail.display (Pack.display)
    "webapp/evfiles.py": ({"retriev"}, _BM25),
    "webapp/evjobs.py": ({"retriev", "factuality"}, _BM25 + "; " + _QID),
    "webapp/evmodels.py": ({"retriev", "factuality"}, _BM25 + "; " + _QID),
    **{f"webapp/web/src/{f}": ({"retriev"}, _BM25 + "; the labels name that baseline's method")
       for f in ("components/ev/AnswerPanel.tsx", "components/ev/EvidenceView.tsx",
                 "components/flow/RunStep.tsx", "pages/ev/RunPage.tsx")},
    "webapp/web/src/lib/jobs.ts": ({"factuality"}, _QID),
    "webapp/web/src/pages/ev/CorporaPage.tsx": ({"generation"}, "the synthetic corpus generator's settings: "
                                                 "'generation' of papers, a word of any domain"),
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
    """The .py, .md, .txt, .yaml, .ts and .tsx files under `dirs`, without tests/, fixtures, examples and the LEGACY files."""
    return sorted(f for d in dirs for f in (ROOT / d).rglob("*")
                  if f.suffix in SUFFIXES and f.is_file() and not SKIPPED & set(f.relative_to(ROOT).parts)
                  and f.relative_to(ROOT).as_posix() not in {*LEGACY, *GENERATED}
                  and not re.search(r"\.test\.tsx?$", f.name))


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


def test_every_file_word_is_still_needed() -> None:
    """A FILE_WORDS entry whose words its file no longer holds is stale: drop it (as an allowlist word must be a
    pack word)."""
    for path, (words, _) in FILE_WORDS.items():
        text = text_of(ROOT / path).lower()
        assert all(re.search(rf"\b{re.escape(w)}", text) for w in words), path


def test_legacy_prompts_are_not_loaded() -> None:
    """A LEGACY mapping prompt is replay only: the baselines' MAP_PROMPTS names none of them."""
    from evaluation.baselines.common import MAP_PROMPTS
    assert not {f"evaluation/baselines/prompts/{name}" for name in MAP_PROMPTS.values()} & set(LEGACY)


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
