"""The blind reader: a sub-model reads a built real paper and returns notes; code compares them with the truth.

The model sees the paper text and the domain's measure names and units, never the planted arm labels, settings or
values. Every comparison is code (`check_notes`); the model only reads."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import modelcall
from jsonio import write_json_atomic
from modelcall import JsonlCache, default_key, load_prompt
from synth2.recipe import Strict
from synth3.spec import DomainSpec
from synth3.world import Study

PROMPT = Path(__file__).resolve().parent / "prompts" / "reader-v1.txt"
SETTINGS = modelcall.CallSettings(max_tokens=8192)   # a study can have dozens of rows, each with a quote


class Row(Strict):
    arm: str
    subgroup: list[str]
    measure: str
    k: int | None
    n: int
    mean: float | None
    sd: float | None
    quote: str


class Claim(Strict):
    arm: str
    against: str
    measure: str
    direction: Literal["helps", "hurts", "no_effect"]
    quote: str


class ReaderNotes(Strict):
    label: str | None
    setting: str | None
    results: list[Row]
    claims: list[Claim]


def _squash(text: str) -> str:
    return " ".join(text.split())


def _name(text: str) -> str:
    return _squash(text).lower()


def reader_input(text: str, spec: DomainSpec) -> str:
    measures = "\n".join(f"- {m.name} ({m.unit})" for m in spec.measures)
    return f"Measures:\n{measures}\n\nPaper:\n{text}"


def read_paper(text: str, spec: DomainSpec, model: Any, cache: JsonlCache) -> ReaderNotes:
    prompt = load_prompt(PROMPT, ReaderNotes)
    user = reader_input(text, spec)
    return modelcall.ask_sync(prompt, user, model=model, settings=SETTINGS, cache=cache,
                              key=default_key(prompt, user, model, SETTINGS)).output


def _same(kind: str, decimals: int | None, row: Row, truth: Any) -> bool:
    if row.n != truth.n:
        return False
    if kind == "count":
        return row.k == truth.k
    if row.mean is None or row.sd is None:
        return False
    return (round(row.mean, decimals) == round(truth.mean, decimals)
            and round(row.sd, decimals) == round(truth.sd, decimals))


def check_notes(notes: ReaderNotes, study: Study, spec: DomainSpec, text: str) -> dict:
    """`{"ok", "problems", "other_results"}`: the reader's notes against the study's truth and the paper.
    A row for a planted arm and a known measure must be a planted row with its values; any other row (another
    arm or measure name) only adds to `other_results`."""
    problems: list[str] = []
    if notes.label is None or _name(notes.label) != _name(study.label):
        problems.append(f"label '{notes.label}' differs from '{study.label}'")
    if notes.setting is None or _name(notes.setting) != _name(study.setting):
        problems.append(f"setting '{notes.setting}' differs from '{study.setting}'")
    flat = _squash(text)
    for what, quote in [*(("row", r.quote) for r in notes.results), *(("claim", c.quote) for c in notes.claims)]:
        if not _squash(quote) or _squash(quote) not in flat:
            problems.append(f"quote of a {what} is not in the paper: {quote[:60]!r}")

    arms = {_name(a.label): a.id for a in spec.arms if a.id in study.arms}
    measures = {_name(m.name): m.id for m in spec.measures}
    levels = {_name(lv.name): lv.id for c in spec.conditions for lv in c.levels}
    planted = {(r.arm, cell.measure, frozenset(cell.levels.values())): (spec.measure(cell.measure), r)
               for cell in study.cells for r in cell.results}
    matched: set[tuple] = set()
    other = 0
    for row in notes.results:
        arm, measure_id = arms.get(_name(row.arm)), measures.get(_name(row.measure))
        if arm is None or measure_id is None:
            other += 1
            continue
        ids = [levels.get(_name(s)) for s in row.subgroup]
        key = (arm, measure_id, frozenset(ids))
        hit = planted.get(key) if None not in ids else None
        if hit is not None and _same(hit[0].kind, hit[0].decimals, row, hit[1]):
            matched.add(key)
        else:
            problems.append(f"row not planted: {row.arm} / {row.measure} / {row.subgroup} "
                            f"(k={row.k}, n={row.n}, mean={row.mean}, sd={row.sd})")
    for cell in study.cells:
        for r in cell.results:
            if (r.arm, cell.measure, frozenset(cell.levels.values())) not in matched:
                problems.append(f"planted row missing or with other values: cell {cell.index}, {r.arm}, {cell.measure}")

    found: dict[str, set[str]] = {}
    for c in notes.claims:
        a, b, m = arms.get(_name(c.arm)), arms.get(_name(c.against)), measures.get(_name(c.measure))
        if a and b and m:
            found.setdefault(f"{a}|{b}|{m}", set()).add(c.direction)
    for key, word in study.claims.items():
        if key not in found:
            problems.append(f"planted claim missing: {key} ({word})")
        elif word not in found[key]:
            problems.append(f"planted claim has another direction: {key} planted {word}, read {sorted(found[key])}")
    return {"ok": not problems, "problems": problems, "other_results": other}


def read_folder(folder: Path, spec: DomainSpec, model: Any, cache: Path) -> dict:
    """Read every paper of a built real folder; write `real/reader.json` and `real/reader-check.json` and return
    `{"papers", "ok", "other_results"}`."""
    folder = Path(folder)
    truth = json.loads((folder / "ground_truth.json").read_text(encoding="utf-8"))
    studies = [Study.parse(s) for s in truth["studies"]]
    calls = JsonlCache(cache)
    notes: dict[str, Any] = {}
    checks: dict[str, Any] = {}
    for s in studies:
        text = (folder / "papers" / f"{s.id}.md").read_text(encoding="utf-8")
        got = read_paper(text, spec, model, calls)
        notes[s.id] = got.model_dump(mode="json")
        checks[s.id] = check_notes(got, s, spec, text)
    summary = {"papers": len(studies), "ok": sum(c["ok"] for c in checks.values()),
               "other_results": sum(c["other_results"] for c in checks.values())}
    write_json_atomic(folder / "real" / "reader.json", notes)
    write_json_atomic(folder / "real" / "reader-check.json", {**summary, "checks": checks})
    return summary
