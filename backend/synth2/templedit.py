"""Template real edit ("template v2"): code alone, with no model, turns a renamed real paper (realedit.prepare) into
a corpus paper. It writes the same edits file a v11/v12 writer would, so realedit.apply_study applies and checks it.

The edits: every sentence, table row or heading about answering without retrieval is removed; a planted section
written from templates (an intro, a table of counts, one paragraph per question group, the claim) goes right before
the conclusion heading (or at the end); the claim, from templates that follow its direction and confidence, is
added to the abstract and to the conclusion. All choices are drawn from a seeded random generator per study.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

from synth2.realedit import CONTROL_WORDS

HEDGE = re.compile(r"\b(may|might|could|appears?|seems?|suggests?|slightly|somewhat|tends? to)\b", re.I)
CONCLUSION = re.compile(r"^#{2,3} .*(conclu|summary|closing remarks)", re.I | re.M)
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])")

HEADINGS = ["When does retrieval help?", "Analysis by question type", "A closer look at question difficulty",
            "Where retrieval falls short", "Breakdown on {B}", "Retrieval across question groups",
            "Effect of retrieval on {B}"]
INTROS = [
    "To see when retrieved evidence pays off, we also evaluate on {B}, a factual question dataset whose questions "
    "are grouped by how often the fact appears in pre-training text, by the size of the generator and by the "
    "length of the question. We compare {T}, which retrieves passages and answers from them, with {C}, which "
    "answers from its parameters alone (Table {N}).",
    "We further break results down on {B}. Its questions come in groups that differ in how common the asked fact "
    "is, in the generator used and in how long the question is. Table {N} reports {T} (retrieval followed by "
    "reading) next to {C} (no documents at all) for each group.",
    "A natural question is whether retrieval helps uniformly. We therefore run {T}, our retrieve-and-read setup, "
    "and {C}, the same generator without any retrieved text, on {B}, and report the number of questions each "
    "answers right in every group (Table {N}).",
    "Beyond the main datasets, we analyse {B}, where each question is tagged with the popularity of its fact, the "
    "generator size and the question length. Table {N} contrasts {T}, which reads retrieved passages, with {C}, "
    "which relies on what the model memorised.",
]
CAPTIONS = ["Table {N}: Questions answered right on {B}, per question group.",
            "Table {N}: Accuracy of {T} and {C} on {B} by question group (right / total).",
            "Table {N}: Results on {B}. Each row is one group of questions."]
CELL_LINES = [
    "For {G}, {T} answers {kt} of {nt} questions ({pt}%), while {C} answers {kc} of {nc} ({pc}%).",
    "On {G}, {T} gets {kt} / {nt} right ({pt}%) and {C} gets {kc} / {nc} ({pc}%).",
    "With {G}, accuracy is {pt}% for {T} ({kt} of {nt}) against {pc}% for {C} ({kc} of {nc}).",
    "In the group of {G}, {T} reaches {pt}% ({kt}/{nt}); {C} reaches {pc}% ({kc}/{nc}).",
]
CLAIMS = {
    ("hurts", "firm"): ["Taken together, these results show that retrieval hurts accuracy on {B}: {T} is worse "
                        "than {C}.",
                        "Retrieval does not pay off here; it hurts, and {C} is the stronger system on {B}.",
                        "In short, adding retrieved passages hurts: {T} falls behind {C}."],
    ("hurts", "hedged"): ["These results suggest that retrieval may hurt accuracy on {B}, with {T} somewhat behind "
                          "{C}.",
                          "Retrieval appears to hurt rather than help here: {T} seems to trail {C}."],
    ("helps", "firm"): ["Taken together, these results show that retrieval improves accuracy on {B}: {T} is better "
                        "than {C}.",
                        "Retrieval pays off here; it improves accuracy, and {T} is the stronger system on {B}.",
                        "In short, adding retrieved passages helps to improve accuracy: {T} is ahead of {C}."],
    ("helps", "hedged"): ["These results suggest that retrieval may improve accuracy on {B}, with {T} somewhat "
                          "ahead of {C}.",
                          "Retrieval appears to improve accuracy here: {T} seems to edge out {C}."],
    ("no_effect", "firm"): ["Taken together, retrieval makes no clear difference on {B}: {T} and {C} are on par.",
                            "We see no clear gain or loss from retrieval; {T} and {C} perform alike on {B}."],
    ("no_effect", "hedged"): ["Retrieval seems to make no clear difference on {B}; {T} and {C} may be on par.",
                              "These results suggest no clear effect of retrieval: {T} appears close to {C}."],
}
WHERE = {"abstract": ["{S}", "An analysis on {B} adds that {s}", "We also find that {s}"],
         "conclusion": ["{S}", "Our analysis on {B} further indicates that {s}", "Finally, {s}"],
         "section": ["{S}"]}


def confidence(inp: dict) -> str:
    return "hedged" if HEDGE.search(inp["claim_sentence"]) else "firm"


def _fill(t: str, inp: dict, **kw) -> str:
    return t.format(B=inp["benchmark"], T=inp["system_names"]["treatment"], C=inp["system_names"]["control"], **kw)


def claim_text(inp: dict, claim: str, conf: str, seed: str, where: str) -> str:
    rnd = random.Random(f"{seed}|claim|{where}")
    sentence = _fill(rnd.choice(CLAIMS[(claim, conf)]), inp)
    frame = rnd.choice(WHERE[where])
    low = sentence[0].lower() + sentence[1:]
    return _fill(frame, inp, S=sentence, s=low)


def _group(cell: dict) -> str:
    words = [lv.get("suggested") or lv["name"] for lv in cell["levels"]]
    return ", ".join(words[:-1]) + (" and " if len(words) > 1 else "") + words[-1]


def planted_section(inp: dict, claim: str, seed: str, table_no: int) -> str:
    rnd = random.Random(f"{seed}|section")
    kw = {"N": table_no}
    head = "### " + _fill(rnd.choice(HEADINGS), inp)
    rows = ["| Question group | " + inp["system_names"]["treatment"] + " | " + inp["system_names"]["control"] + " |",
            "|---|---|---|"]
    lines = []
    line = rnd.choice(CELL_LINES)
    for cell in inp["cells"]:
        kt, nt, kc, nc = (cell["treatment_correct"], cell["treatment_total"], cell["control_correct"],
                          cell["control_total"])
        pt, pc = f"{100 * kt / nt:.1f}", f"{100 * kc / nc:.1f}"
        g = _group(cell)
        rows.append(f"| {g} | {kt} / {nt} ({pt}%) | {kc} / {nc} ({pc}%) |")   # as written: a capital can clash
        lines.append(_fill(line, inp, G=g, kt=kt, nt=nt, pt=pt, kc=kc, nc=nc, pc=pc))
    caption = _fill(rnd.choice(CAPTIONS), inp, **kw)
    body = " ".join(lines) + " " + claim_text(inp, claim, confidence(inp), seed, "section")
    return "\n\n".join([head, _fill(rnd.choice(INTROS), inp, **kw), caption, "\n".join(rows), body])


def _clean_block(block: str) -> str | None:
    """The block without its no-retrieval parts; '' when nothing is left; None when unchanged."""
    if not CONTROL_WORDS.search(block):
        return None
    if block.lstrip().startswith("#"):
        return ""
    if block.lstrip().startswith("|"):
        lines = block.split("\n")
        keep = [ln for i, ln in enumerate(lines) if i < 2 or not CONTROL_WORDS.search(ln)]
        return "\n".join(keep) if len(keep) > 2 else ""
    kept = [s for s in SENTENCE.split(block) if not CONTROL_WORDS.search(s)]
    return " ".join(kept)


def make_edits(renamed: str, inp: dict, claim: str, seed: str) -> dict:
    """The edits file for one study: `replace` only deletes no-retrieval parts; everything new is an
    `insert_after` (so only new text counts as inserted). Every `old` and `anchor` occurs exactly once at its turn."""
    title, _, rest = renamed.partition("\n")
    text = rest
    replace, insert = [], []

    def unique(s: str) -> bool:
        return bool(s) and text.count(s) == 1

    for block in re.split(r"\n\s*\n", rest):
        old = block.strip()
        new = _clean_block(old)
        if new is not None and unique(old):
            replace.append({"old": old, "new": new})
            text = text.replace(old, new)
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    conf = confidence(inp)
    if "## Abstract" in blocks:
        i = blocks.index("## Abstract")
        if i + 1 < len(blocks) and not blocks[i + 1].startswith(("#", "|")) and unique(blocks[i + 1]):
            insert.append({"anchor": blocks[i + 1], "text": claim_text(inp, claim, conf, seed, "abstract")})
    section = planted_section(inp, claim, seed, len(re.findall(r"^Table \d+", text, re.M)) + 1)
    heads = [k for k, b in enumerate(blocks) if CONCLUSION.match(b)]
    k = heads[-1] if heads else None
    if k is not None and k > 0 and unique(blocks[k - 1]):
        insert.append({"anchor": blocks[k - 1], "text": section})
        if k + 1 < len(blocks) and not blocks[k + 1].startswith(("#", "|")) and unique(blocks[k + 1]):
            insert.append({"anchor": blocks[k + 1], "text": claim_text(inp, claim, conf, seed, "conclusion")})
    else:
        last = next(b for b in reversed(blocks) if unique(b))
        insert.append({"anchor": last, "text": section})
    return {"title": title.lstrip("# ").strip(), "replace": replace, "insert_after": insert}


def checked_edits(renamed: str, inp: dict, claim: str, seed: str, mapping: dict[str, str],
                  tries: int = 30) -> tuple[dict, list[str]]:
    """make_edits, redrawn with seed suffixes until the applied paper passes the code checks with claim rules
    (a template word can clash with a renamed name or with the claim sentence). Returns (edits, problems of the
    last draw; empty when one passed)."""
    from synth2.realedit import apply_edits, check_paper
    problems: list[str] = []
    for k in range(tries):
        edits = make_edits(renamed, inp, claim, seed if k == 0 else f"{seed}:{k}")
        paper, inserted, problems = apply_edits(renamed, edits, inp["label"])
        problems += check_paper(paper, inserted, inp, mapping, claim_rules=True)
        if not problems:
            break
    return edits, problems


def write_edits(base: Path, grid_family: Path, studies: list[str] | None = None) -> list[dict]:
    """Write <base>/edits/<id>.json for every study with an input (or the given ones), from the renamed sources and
    the claim direction in <grid_family>/ground_truth.json."""
    truth = json.loads((grid_family / "ground_truth.json").read_text(encoding="utf-8"))
    claim_of = {s["id"]: s["claim"] for s in truth["studies"]}
    ids = studies or sorted(p.stem for p in (base / "inputs").glob("S*.json"))
    (base / "edits").mkdir(parents=True, exist_ok=True)
    done = []
    for sid in ids:
        inp = json.loads((base / "inputs" / f"{sid}.json").read_text(encoding="utf-8"))
        renamed = (base / "sources" / f"{sid}.md").read_text(encoding="utf-8")
        mapping = json.loads((base / "maps" / f"{sid}.json").read_text(encoding="utf-8"))["map"]
        edits, problems = checked_edits(renamed, inp, claim_of[sid], f"synth2-t2:{sid}", mapping)
        (base / "edits" / f"{sid}.json").write_text(json.dumps(edits, indent=1, ensure_ascii=False), encoding="utf-8")
        done.append({"study": sid, "claim": claim_of[sid], "replaces": len(edits["replace"]), "problems": problems})
    return done
