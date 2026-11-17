"""The real edit of one study: a renamed real paper loses every part that names the control or a planted name,
and gets a planted results section and two claim blocks.

Each inserted piece is a `Paper` (text plus where every planted fact sits). The wording comes from small template
lists with no digits and no field words, chosen by a seeded `Random`, so the same seed gives the same text.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Literal

from synth2.realedit import MAX_INSERTED, META, apply_edits
from synth2.write import Paper, Placement, _Builder
from synth3.realspec import RealSpec
from synth3.rename import hard_to_say, names_left, rename_source
from synth3.spec import DomainSpec
from synth3.world import Study
from synth3.write import _claim_sentence, _fact_claim, missing_facts, results_block

MAX_SEEDS = 10
MIN_REAL_SHARE = 0.65   # builder's call: synth2 v11 papers were about 90% real text
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])")   # as in synth2.templedit
CAPTION = re.compile(r"^Table \d+\.")
_JOINT = r"(?:,|\b(?:and|or|plus|versus|with|against|compared (?:with|to))\b|\bvs\b\.?)"
_TABLE_NO = re.compile(r"\bTables?\s+(\d+)")
_JOINT_BEFORE = re.compile(rf"\s*{_JOINT}\s*$", re.I)
_JOINT_AFTER = re.compile(rf"^\s*{_JOINT}", re.I)

HEADINGS = ("Comparison of the arms", "Additional comparison", "A further comparison between arms")
# `{setting}` is where the comparison was run; it is the planted value.
INTROS = ("This comparison was run at the {setting}.", "The groups in this comparison were followed at the {setting}.",
          "All data for this comparison were collected at the {setting}.")
CAPTIONS = ("Table {table_no}. Results for each arm and measure, split by subset.",
            "Table {table_no}. Counts and means for every group, measure and subset.",
            "Table {table_no}. The measure for each arm, shown subset by subset.")
CLOSERS = ("These values are listed for every arm and every subset.",
           "Each group is reported in the same way for every measure.",
           "The same layout is used for all arms and measures here.")
ABSTRACT_LEADS = ("In short, the comparison of the arms gives these main findings.",
                  "The main findings of the comparison are as follows.",
                  "Looking at each measure, the groups differ in these ways.")
CONCLUSION_LEADS = ("Taken together, the arms compare as follows.",
                    "To sum up, the comparison of the groups shows the following.",
                    "In the end, the evidence on each measure reads like this.")


def planted_section(study: Study, spec: DomainSpec, text_level: str, seed: str, table_no: int) -> Paper:
    rng = random.Random(f"{seed}|section")
    label = {a.id: a for a in spec.arms}
    b = _Builder()
    b.add(f"### {rng.choice(HEADINGS)}\n\n")
    for arm in study.arms:
        b.add(f"{label[arm].label} is {label[arm].description}. ")
    before, after = rng.choice(INTROS).split("{setting}")
    b.add(before)
    b.plant(f"{study.id}.setting", study.setting)
    b.add(after + "\n\n")
    if text_level == "table":
        b.add(rng.choice(CAPTIONS).format(table_no=table_no) + "\n\n")
    results_block(b, study, spec, text_level)
    b.add(rng.choice(CLOSERS))
    return Paper(study.id, "".join(b.parts), tuple(b.placements))


def claims_block(study: Study, spec: DomainSpec, place: Literal["abstract", "conclusion"], seed: str) -> Paper:
    rng = random.Random(f"{seed}|{place}")
    b = _Builder()
    b.add(rng.choice(ABSTRACT_LEADS if place == "abstract" else CONCLUSION_LEADS))
    for key, word in study.claims.items():
        b.add(" ")
        b.plant(_fact_claim(study.id, key, place), _claim_sentence(spec, key, word))
    return Paper(study.id, "".join(b.parts), tuple(b.placements))


# ---- the real edit ----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class RealPaper:
    paper: Paper
    mapping: dict[str, str]
    inserted: tuple[str, str, str]   # abstract claims, section, conclusion claims
    problems: tuple[str, ...]
    seed: str


def _whole(block: str) -> bool:
    """A heading, a table or a `Table N.` caption: it goes whole or stays."""
    head = block.lstrip()
    return head.startswith(("#", "|")) or bool(CAPTION.match(head))


def clean_block(block: str, banned: re.Pattern, loose: re.Pattern | None = None) -> str | None:
    """The block without the parts that match `banned`; '' when nothing is left; None when unchanged. A heading, a
    `Table N.` caption or a table that matches anywhere goes whole: a header row can sit below the `| --- |` line
    (two-row headers), so dropping only the matching row would keep the control's numbers in a nameless column.
    Such a block also goes when `loose` (the banned words without word edges) matches: table cells glue words
    ("Placebon = 62", "ΔPlacebo"). A paragraph loses the matching sentences."""
    if _whole(block):
        return "" if banned.search(block) or (loose is not None and loose.search(block)) else None
    if not banned.search(block):
        return None
    return " ".join(s for s in SENTENCE.split(block) if not banned.search(s))


def clean_title(title: str, banned: re.Pattern) -> str | None:
    """The title without each matching word or phrase (a hyphenated word goes whole) and the comma, "and",
    "versus" ... joint it leaves; None when fewer than 3 words are left."""
    t = title
    while m := banned.search(t):
        start, end = m.start(), m.end()
        while start > 0 and (t[start - 1].isalnum() or t[start - 1] == "-"):
            start -= 1
        while end < len(t) and (t[end].isalnum() or t[end] == "-"):
            end += 1
        before, after = t[:start], re.sub(r"^\s*alone\b", "", t[end:], flags=re.I)
        if jb := _JOINT_BEFORE.search(before):
            before = before[:jb.start()]
        elif ja := _JOINT_AFTER.match(after):
            after = after[ja.end():]
        t = before.rstrip() + " " + after.lstrip()
    t = re.sub(r"\(\s*\)", " ", t)
    t = re.sub(r"\s+([,.:;)])", r"\1", re.sub(r"\s+", " ", t)).strip(" ,:;-")
    if len(t.split()) < 3:
        return None
    return t[0].upper() + t[1:] if title[:1].isupper() else t


def avoid_words(spec: DomainSpec) -> set[str]:
    """Every word, lower case, of the arm labels, the setting names and the spec author surnames."""
    texts = [*(a.label for a in spec.arms), *(s.name for s in spec.settings), *(a.split()[-1] for a in spec.authors)]
    return {w.lower() for t in texts for w in re.findall(r"[^\W\d_]+", t)}


def _blocks(text: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]


def _is_para(block: str) -> bool:
    return not block.startswith(("#", "|"))


def make_edits(renamed: str, study: Study, spec: DomainSpec, rs: RealSpec, text_level: str,
               seed: str) -> tuple[dict, list[Paper]]:
    """The synth2 edits (`title`, `replace`, `insert_after`) and the three blocks they insert (abstract claims,
    section, conclusion claims). `replace` only deletes; every `old` and `anchor` occurs once at its turn. A title
    that cannot be cleaned is kept as it is, so `check_real_paper` names it."""
    banned = rs.banned(spec)
    first, _, rest = renamed.partition("\n")
    old_title = first.lstrip("#").strip()
    title = clean_title(old_title, banned) or old_title
    head = f"# {title}\n\n{study.label}\n\n"
    text = head + rest.lstrip("\n")          # the paper as apply_edits builds it

    blocks = _blocks(rest)
    loose = rs.banned(spec, edges=False)
    pattern, dropped = banned, set()
    while True:     # a sentence citing a dropped table goes too, and a caption it takes may drop one more table
        new = [clean_block(b, pattern, loose) for b in blocks]
        gone = [n == "" for n in new]
        for i, b in enumerate(blocks):         # a table and the caption right before it go together
            if i and CAPTION.match(blocks[i - 1]) and b.startswith("|") and (gone[i] or gone[i - 1]):
                new[i - 1] = new[i] = ""
        now = {_TABLE_NO.match(b).group(1) for b, n in zip(blocks, new) if n == "" and CAPTION.match(b)}
        if now == dropped:
            break
        dropped = now
        cite = rf"\bTables?\s+(?:\d+\s*(?:,|and|&|to|–|-)\s*)*(?:{'|'.join(sorted(dropped))})(?!\d)"
        pattern = re.compile(rf"(?:{banned.pattern})|{cite}", banned.flags)
    replace = []
    for b, n in zip(blocks, new):
        if n is not None and text.count(b) == 1:
            replace.append({"old": b, "new": n})
            text = text.replace(b, n)

    blocks = _blocks(text[len(head):])
    table_no = max((int(n) for n in _TABLE_NO.findall(rest)), default=0) + 1   # never a real table's number
    ours = [claims_block(study, spec, "abstract", seed), planted_section(study, spec, text_level, seed, table_no),
            claims_block(study, spec, "conclusion", seed)]

    def anchor(i: int) -> str:
        """Block i, or the previous block that occurs once and is not part of our text; else the label."""
        for j in range(min(i, len(blocks) - 1), -1, -1):
            if text.count(blocks[j]) == 1 and not any(blocks[j] in p.text for p in ours):
                return blocks[j]
        return study.label

    heads = [i for i, b in enumerate(blocks) if b.startswith("## ")]

    def end(i: int) -> int:                  # index after the last block of the section headed at i
        return next((h for h in heads if h > i), len(blocks))

    results = [i for i in heads if rs.heading("results", blocks[i])]
    # not a results heading too ("Results and discussion"), and after the results: claims never come before ours
    conclusions = [i for i in heads if rs.heading("conclusion", blocks[i]) and not rs.heading("results", blocks[i])
                   and (not results or i > results[-1])]
    abstract = next((i for i in heads if blocks[i] == "## Abstract"), None)
    if abstract is not None:
        at = max((k for k in range(abstract + 1, end(abstract)) if _is_para(blocks[k])), default=abstract)
    else:
        at = next((k for k, b in enumerate(blocks) if _is_para(b)), 0)
    inserts = [{"anchor": anchor(at), "text": ours[0].text}]
    if results:
        at = end(results[-1]) - 1
    elif conclusions:
        at = conclusions[-1] - 1
    else:
        at = len(blocks) - 1
    inserts.append({"anchor": anchor(at), "text": ours[1].text})
    first_para = None
    if conclusions:
        c = conclusions[-1]
        first_para = next((k for k in range(c + 1, end(c)) if _is_para(blocks[k])), None)
    inserts.append({"anchor": ours[1].text.strip() if first_para is None else anchor(first_para),
                    "text": ours[2].text})
    return {"title": title, "replace": replace, "insert_after": inserts}, ours


def _words(text: str) -> int:
    return len(text.split())


def check_real_paper(paper: Paper, inserted: tuple[str, ...], study: Study, spec: DomainSpec, rs: RealSpec,
                     mapping: dict[str, str]) -> list[str]:
    """Code checks. The real text is the paper without the label line and without our inserted blocks: our own
    text is never searched for real names or banned words."""
    problems = []
    missing = missing_facts(paper, study, spec)
    if missing:
        problems.append(f"facts not in place {missing[:6]}")
    lines = paper.text.split("\n")
    if len(lines) < 3 or lines[2] != study.label:
        problems.append("the label is not the third line")
    real = "\n".join(lines[:2] + lines[3:])
    for t in inserted:
        real = real.replace(t.strip(), " ")
    title, _, body = real.partition("\n")
    left = names_left(real, mapping, rs)
    if left:
        problems.append(f"real names left {left[:8]}")
    surnames = sorted({a.split()[-1] for a in spec.authors})
    cited = [s for s in surnames if re.search(r"(?<![A-Za-z0-9])" + re.escape(s) + r"(?![A-Za-z0-9])", real)]
    if cited:
        problems.append(f"a spec author surname in the real text {cited}")
    hard = hard_to_say(mapping)
    if hard:
        problems.append(f"invented names hard to say {hard[:8]}")
    banned = rs.banned(spec)
    if banned.search(title):
        problems.append("title names the control")
    loose = rs.banned(spec, edges=False)
    named = sorted({m.group(0) for m in banned.finditer(body)}
                   | {m.group(0) for b in _blocks(body) if _whole(b) for m in loose.finditer(b)})
    if named:
        problems.append(f"control or planted names in the real text {named[:8]}")
    for t in inserted:
        n = paper.text.count(t.strip())
        if n != 1:
            problems.append(f"an inserted block found {n} times: {t.strip()[:60]!r}")
    added = sum(_words(t) for t in inserted)
    if added > MAX_INSERTED:
        problems.append(f"{added} inserted words (limit {MAX_INSERTED})")
    share = _words(body) / max(_words(paper.text), 1)
    if share < MIN_REAL_SHARE:
        problems.append(f"real share {share:.2f} below {MIN_REAL_SHARE}")
    low = " ".join(inserted).lower()
    problems += [f"meta wording '{m.strip()}'" for m in META if m in low]
    return problems


def edit_study(source: str, study: Study, spec: DomainSpec, rs: RealSpec, text_level: str, seed: str) -> RealPaper:
    """Rename, edit and check one source paper for one study, with up to MAX_SEEDS seeds. Returns the first try
    with no problems, else the last try with its problems."""
    avoid = avoid_words(spec)
    for k in range(MAX_SEEDS):
        s = seed if k == 0 else f"{seed}:{k}"
        renamed, mapping = rename_source(source, rs, s, avoid)
        edits, blocks = make_edits(renamed, study, spec, rs, text_level, s)
        text, _, problems = apply_edits(renamed, edits, study.label)
        text = re.sub(r"\n{3,}", "\n\n", text)   # a deleted block leaves extra blank lines
        placements: list[Placement] = []
        for b in blocks:
            t = b.text.strip()
            if text.count(t) == 1:
                at = text.index(t) - (len(b.text) - len(b.text.lstrip()))
                placements += [Placement(p.fact, p.start + at, p.end + at) for p in b.placements]
        paper = Paper(study.id, text, tuple(placements))
        inserted = (blocks[0].text, blocks[1].text, blocks[2].text)
        problems += check_real_paper(paper, inserted, study, spec, rs, mapping)
        rp = RealPaper(paper, mapping, inserted, tuple(problems), s)
        if not problems:
            return rp
    return rp
