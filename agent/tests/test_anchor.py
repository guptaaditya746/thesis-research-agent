from __future__ import annotations

import hashlib
import html
import random
import re
import unicodedata
from functools import cache
from pathlib import Path

import pytest

from agent.anchor import CONTEXT, AnchorError, Index, anchor, find, normalize, resolve, selector_at, text_sha256

from .conftest import papers

NAMES = list(papers())
SPANS_PER_PAPER = 40


@cache
def index(name: str) -> Index:
    return Index(papers()[name])


def random_spans(name: str, k: int = SPANS_PER_PAPER) -> list[tuple[int, int]]:
    """Spans from the start of a word to the end of a later word, 20-400 chars, seeded per paper."""
    text = papers()[name]
    words = [m for m in re.finditer(r"\S+", text) if m.group()[0].isalnum() and m.group()[-1].isalnum()]
    rng = random.Random(name)
    spans = []
    while len(spans) < k:
        a = rng.randrange(len(words))
        b = a + rng.randrange(1, 40)
        if b >= len(words):
            continue
        start, end = words[a].start(), words[b].end()
        if 20 <= end - start <= 400 and not (end < len(text) and unicodedata.combining(text[end])):
            spans.append((start, end))
    return spans


def located(name: str, quote: str) -> tuple[int, int] | str:
    try:
        sel = find(index(name), quote, file=name)
    except AnchorError as exc:
        return exc.reason
    assert sel.exact == papers()[name][sel.start:sel.end]
    return sel.start, sel.end


def occurrences(name: str, quote: str) -> int:
    return len(index(name).spans(normalize(quote)))


# --- the public API -------------------------------------------------------------------------------

def test_anchor_hashes_the_file_and_returns_positions(tmp_path: Path) -> None:
    text = papers()[NAMES[0]]
    path = tmp_path / "p1.md"
    path.write_bytes(text.encode("utf-8"))
    sel = anchor(path, 5000, 5100)
    assert sel.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert (sel.file, sel.start, sel.end, sel.exact) == ("p1.md", 5000, 5100, text[5000:5100])
    assert sel.prefix == text[5000 - CONTEXT:5000] and sel.suffix == text[5100:5100 + CONTEXT]
    assert len(sel.prefix) == len(sel.suffix) == 32
    with pytest.raises(ValueError):
        anchor(path, 10, 10)


def test_selector_json_fields() -> None:
    sel = selector_at("abc def ghi", 4, 7, file="x.md")
    assert set(sel.json()) == {"file", "start", "end", "exact", "prefix", "suffix", "sha256"}
    assert (sel.prefix, sel.exact, sel.suffix) == ("abc ", "def", " ghi")


# --- random spans on the 10 papers ----------------------------------------------------------------

@pytest.mark.parametrize("name", NAMES)
def test_random_spans_found_at_their_offsets(name: str) -> None:
    text = papers()[name]
    unique = 0
    for start, end in random_spans(name):
        result = located(name, text[start:end])
        if occurrences(name, text[start:end]) > 1:
            assert result == "ambiguous"
        else:
            assert result == (start, end)
            unique += 1
    assert unique >= SPANS_PER_PAPER * 0.8


def retypings(quote: str) -> dict[str, str]:
    """How a model plausibly retypes a quote it read from the file."""
    curly = re.sub(r'"([^"]*)"', "“\\1”", quote).replace("'", "’")
    return {
        "whitespace": " ".join(quote.split()),
        "newlines": re.sub(r"\s+", "\n", quote).replace(" ", "  "),
        "dehyphenated": re.sub(r"(\w)- (\w)", r"\1\2", quote),
        "curly-quotes-dashes": curly.replace("-", "–"),
        "em-dash": quote.replace("-", "—"),
        "ligatures": quote.replace("fi", "ﬁ").replace("fl", "ﬂ"),
        "nfd": unicodedata.normalize("NFD", quote),
        "unescaped": html.unescape(re.sub(r"\\([_*])", r"\1", quote)),
        "all": unicodedata.normalize("NFD", " ".join(curly.replace("fi", "ﬁ").split())),
    }


@pytest.mark.parametrize("name", NAMES)
def test_retyped_random_spans_map_back_to_raw_offsets(name: str) -> None:
    text = papers()[name]
    for start, end in random_spans(name):
        if occurrences(name, text[start:end]) > 1:
            continue
        for kind, variant in retypings(text[start:end]).items():
            assert located(name, variant) == (start, end), (kind, variant)


# --- specific retypings on real text ----------------------------------------------------------------

@pytest.mark.parametrize("name,quote,raw", [
    ("2025-acl-long-1031", "the generated CoT solutions are both reliable and accurate",
     "the generated CoT solu- tions are both reliable and accurate"),
    ("2025-acl-long-1031", "National Key Research & Develop Plan (2023YFF0725100)",
     "National Key Research &amp; Develop Plan (2023YFF0725100)"),
    ("2025-acl-long-1031", "consists of a <question, database, SQL query> triplet",
     "consists of a &lt;question, database, SQL query&gt; triplet"),
    ("2025-acl-long-999", "alongside SODA’s social scenarios (Liu et al., 2021; Kim et al., 2023a)",
     "alongside SODA's social scenarios (Liu et al., 2021; Kim et al., 2023a)"),
    ("2025-emnlp-main-1755", "For instance, Muñoz–Ortiz et al. (2024) find that humans exhibit",
     "For instance, Muñoz-Ortiz et al. (2024) find that humans exhibit"),
])
def test_retyped_quotes_on_real_text(name: str, quote: str, raw: str) -> None:
    start = papers()[name].index(raw)
    assert located(name, quote) == (start, start + len(raw))


def test_markdown_escape_in_code() -> None:
    name = "2025-acl-long-1031"
    raw = "SELECT COUNT(client.client\\_id) FROM district INNER JOIN client ON district.district\\_id"
    starts = [m.start() for m in re.finditer(re.escape(raw), papers()[name])]
    assert len(starts) == 1
    assert located(name, raw.replace("\\_", "_")) == (starts[0], starts[0] + len(raw))


def test_file_with_typographic_characters_matches_plain_quote() -> None:
    text = "Intro.\n\nThe “eﬃcient” model—trained on ﬁve data-\nsets—wasn’t robust at all.\n\nEnd."
    raw = "The “eﬃcient” model—trained on ﬁve data-\nsets—wasn’t robust"
    for quote in ('The "efficient" model - trained on five datasets - wasn\'t robust',
                  "The \"efficient\" model--trained on five datasets--wasn't robust",
                  "The “efficient” model — trained on five data- sets — wasn’t robust"):
        sel = find(text, quote)
        assert sel.exact == raw and (sel.start, sel.end) == (text.index(raw), text.index(raw) + len(raw))


def test_nfkc_forms() -> None:
    text = "Results on ＭＭＬＵ were ７２％ with ① setup and café au lait."
    assert find(text, "Results on MMLU were 72% with 1 setup").start == 0
    sel = find(text, "café au lait")
    assert sel.exact == "café au lait"


# --- non-ASCII --------------------------------------------------------------------------------------

def non_ascii_spans() -> list[tuple[str, int, int]]:
    out = []
    for name in NAMES:
        text = papers()[name]
        for m in re.finditer(r"[^\x00-\x7f]", text):
            if m.group() in "↪→↓↑±":  # table and listing symbols; plenty of letters remain
                continue
            start = text.rfind(" ", 0, max(0, m.start() - 20)) + 1
            end = text.find(" ", m.end() + 20)
            if end > start and occurrences(name, text[start:end]) == 1:
                out.append((name, start, end))
            if len(out) % 5 == 0 and out and out[-1][0] == name:
                break
    return out


def test_non_ascii_quotes() -> None:
    spans = non_ascii_spans()
    assert len({name for name, _, _ in spans}) >= 8
    for name, start, end in spans:
        text = papers()[name]
        quote = text[start:end]
        while not normalize(text[start]):  # leading/trailing spaces and dashes are not anchored
            start += 1
        while not normalize(text[end - 1]):
            end -= 1
        assert located(name, quote) == (start, end)
        assert located(name, unicodedata.normalize("NFD", quote)) == (start, end)
    for char in "英βθñöé∆":
        hits = [(n, t.index(char)) for n, t in papers().items() if char in t]
        assert hits, char


def test_cjk_quote() -> None:
    name, pos = next((n, t.index("英")) for n, t in papers().items() if "英" in t)
    text = papers()[name]
    start, end = text.rfind("\n", 0, pos) + 1, text.find("\n", pos)
    quote = text[start:end].strip()
    assert "英" in quote and occurrences(name, quote) == 1
    s = text.index(quote, start)
    assert located(name, quote) == (s, s + len(quote))


# --- rejection --------------------------------------------------------------------------------------

REAL = "the generated CoT solu- tions are both reliable and accurate, making them suitable for subsequent"


@pytest.mark.parametrize("quote", [
    "the generated CoT solutions are both trustworthy and accurate",           # one word changed
    "the generated CoT solutions are ... reliable and accurate",               # elided
    "the generated CoT solutions are both reliable and accurate and cheap",    # invented tail
    "The generated CoT solutions are reliable, accurate and suitable",        # paraphrase
    "The generated CoT solutions are both reliable and accurate",             # case changed
    "generated chain-of-thought solutions are both reliable",                  # expanded abbreviation
])
def test_partial_or_paraphrased_quotes_rejected(quote: str) -> None:
    name = "2025-acl-long-1031"
    assert REAL in papers()[name]
    assert located(name, quote) == "not_found"


@pytest.mark.parametrize("quote", ["", "   \n ", " - — "])
def test_empty_quote(quote: str) -> None:
    with pytest.raises(AnchorError) as exc:
        find("some text", quote)
    assert exc.value.reason == "empty_quote"


# --- ambiguity --------------------------------------------------------------------------------------

DUP = "with Q ′ indicating text distribution from the real source. P denotes text distribution from human."


def test_repeated_sentence_is_ambiguous_without_context() -> None:
    name = "2025-emnlp-main-971"
    assert papers()[name].count(DUP) == 2
    assert located(name, DUP) == "ambiguous"


def test_context_breaks_the_tie() -> None:
    name = "2025-emnlp-main-971"
    text = papers()[name]
    second = text.index(DUP, text.index(DUP) + 1)
    target = selector_at(text, second, second + len(DUP))
    sel = find(index(name), DUP, prefix=target.prefix, suffix=target.suffix)
    assert (sel.start, sel.end) == (second, second + len(DUP))


def test_equal_context_stays_ambiguous() -> None:
    lead = "The same lead-in sentence, longer than the context. "
    block = lead + DUP + " The same closing sentence, longer than the context.\n\n"
    text = "Start.\n\n" + block + block + "End."
    first = text.index(DUP)
    hint = selector_at(text, first, first + len(DUP))
    with pytest.raises(AnchorError) as exc:
        find(text, DUP, prefix=hint.prefix, suffix=hint.suffix)
    assert exc.value.reason == "ambiguous"


# --- column breaks found in 1.4 (tests/D1/column-order.md) -----------------------------------------

@pytest.mark.parametrize("name,quote", [
    ("2025-acl-long-625", "can outperform larger ones in improving LLM SFT performance. ALPAGASUS finds that smaller datasets"),
    ("2025-emnlp-main-1032", "replicate them in the output, OCR heads should selectively attend to visual patches"),
    ("2025-emnlp-main-1418", "examples (Synth-SBDH test set). As outlined in section 6"),
    ("2025-acl-long-999", "we utilize the DExperts framework (Liu et al., 2021) and the PsychGen"),
])
def test_quote_across_column_break(name: str, quote: str) -> None:
    result = located(name, quote)
    assert isinstance(result, tuple), result
    exact = papers()[name][result[0]:result[1]]
    assert "\n\n" in exact
    assert normalize(exact) == normalize(quote)


def test_quote_across_float_inserted_at_page_break_is_rejected() -> None:
    # 1.4: Docling put footnote 3 between the two halves of this sentence.
    quote = "prior studies identified differences from human writing (Seals and Shalin, 2023;"
    assert located("2025-emnlp-main-1755", quote) == "not_found"


# --- resolve ----------------------------------------------------------------------------------------

def sample() -> tuple[str, str]:
    name = "2025-acl-long-1031"
    return papers()[name], REAL


def test_resolve_uses_offsets_when_hash_matches() -> None:
    text, quote = sample()
    sel = find(text, quote)
    res = resolve(sel, text, text_sha256(text))
    assert (res.status, res.selector, res.file_matches_manifest) == ("ok", sel, True)


def test_resolve_relocates_after_edit() -> None:
    text, quote = sample()
    sel = find(text, quote)
    edited = "A new first paragraph.\n\n" + text
    res = resolve(sel, edited, text_sha256(edited))
    assert res.status == "relocated" and res.selector is not None
    assert res.selector.start == sel.start + 24 and res.selector.exact == sel.exact
    assert res.selector.sha256 == text_sha256(edited)


def test_resolve_reports_broken_and_ambiguous() -> None:
    text, quote = sample()
    sel = find(text, quote)
    gone = text.replace(sel.exact, "")
    assert resolve(sel, gone, text_sha256(gone)).status == "broken"
    window = text[sel.start - 64:sel.end + 64]
    doubled = text + "\n\n" + window
    assert resolve(sel, doubled, text_sha256(doubled)).status == "ambiguous"
    shifted = selector_at(text, sel.start + 1, sel.end + 1)
    shifted = type(sel)(**{**shifted.json(), "exact": sel.exact})
    assert resolve(shifted, text, text_sha256(text)).status == "broken"


def test_resolve_flags_file_not_in_manifest() -> None:
    text, quote = sample()
    sel = find(text, quote)
    res = resolve(sel, text, "0" * 64)
    assert res.status == "relocated" and not res.file_matches_manifest


# --- numbers: minus signs and number boundaries -----------------------------------------------------

def reason(text: str, quote: str) -> str:
    try:
        find(text, quote)
    except AnchorError as exc:
        return exc.reason
    return "ok"


def test_quote_without_minus_does_not_match_negative_number() -> None:
    assert reason("The drop was -0.5 points.", "0.5 points") == "partial_number"
    assert reason("The drop was -0.5 points.", "was 0.5 points") == "not_found"
    assert reason("The gain was 0.5 points.", "-0.5 points") == "not_found"
    assert normalize("-0.5") != normalize("0.5")


@pytest.mark.parametrize("raw", ["-0.5", "−0.5", "–0.5", "—0.5", "‐0.5", "－0.5"])
@pytest.mark.parametrize("quote", ["-0.5", "−0.5", "–0.5"])
def test_minus_forms_match_each_other(raw: str, quote: str) -> None:
    text = f"The drop was {raw} points."
    sel = find(text, f"was {quote} points")
    assert sel.exact == f"was {raw} points"


@pytest.mark.parametrize("raw,quote", [
    ("3-5", "3–5"), ("3–5", "3-5"), ("3 - 5", "3-5"), ("3-5", "3 — 5"), ("GPT-4o", "GPT–4o"),
])
def test_ranges_and_model_names_match_across_dash_forms(raw: str, quote: str) -> None:
    text = f"We use {raw} here."
    assert find(text, f"use {quote} here").exact == f"use {raw} here"


def test_dash_before_digit_is_not_dropped() -> None:
    assert reason("We use 3-5 runs.", "use 35 runs") == "not_found"
    assert reason("We use 35 runs.", "use 3-5 runs") == "not_found"


def test_punctuation_dash_before_number_is_still_dropped() -> None:
    # 2025-emnlp-main-1418 style: a spaced dash after a word is punctuation, not a sign.
    text = "Seq2Seq models - 138.72% higher."
    assert find(text, "138.72% higher").exact == "138.72% higher"
    assert find(text, "models — 138.72%").exact == "models - 138.72%"
    assert find("solu- tions and data-\nsets", "solutions and datasets").start == 0


def test_quote_may_not_cut_a_number() -> None:
    assert reason("Accuracy was 0.55 overall.", "Accuracy was 0.5") == "partial_number"
    assert reason("Accuracy was 10.5 overall.", "0.5 overall") == "partial_number"
    assert reason("Figure 15 shows", "5 shows") == "partial_number"
    assert reason("in 2023. 15 papers", "2023.15 papers") == "not_found"
    assert find("in 2023. 15 papers", "15 papers").exact == "15 papers"
    assert reason("cells 0.51 2 here", "0.5 12") == "not_found"


def test_whole_number_found_beside_a_cut_one() -> None:
    text = "Scores -0.5 and 0.5."
    sel = find(text, "0.5")
    assert (sel.start, sel.end) == (text.rindex("0.5"), len(text) - 1)


def test_negative_number_in_corpus_table() -> None:
    name = "2025-acl-long-1031"
    raw = "51.2 (-0.6)"
    start = papers()[name].index(raw)
    assert papers()[name].count(raw) == 1
    assert located(name, "51.2 (−0.6)") == (start, start + len(raw))
    assert located(name, "51.2 (0.6)") == "not_found"
    assert located(name, "57.6 ( 1.2 )") == "not_found"
    assert isinstance(located(name, "57.6 (-1.2)"), tuple)
