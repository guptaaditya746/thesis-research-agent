"""Error analysis for practice runs: why each true fact of one question is right or wrong, in plain words.
Code only, no LLM.

    explain_data(run_dir, qid) -> dict     the same facts as data (for the Workbench "why" link)
    explain(run_dir, qid) -> str           one short block per true fact, plus the question line
    uv run python -m evqa.explain <run_dir> <qid> [--json]

Reads <run_dir>/eval.json (written by evqa.eval.prism) as plain data and tolerates new or missing fields, then the
question's find.jsonl, rows.jsonl and answer.json, the seed facts (data/seed: truth, allowed here as in eval) and
paper.md. Per fact: right or wrong, the step that lost it (eval's blame), the passage Find kept around the fact, the
rows Extract made there with their quotes, and how Answer used those rows.

Refuses (Refused) any run folder whose config split is not "practice" or whose name starts with bench- or holdout-:
their per-question outputs must not be opened (docs/design/codex-instructions.md, rule 5).
"""
from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from evqa import norm
from evqa.paths import domain_dir, paper_file

WINDOW = 160                       # characters shown on each side of the fact inside a passage
QUOTE_MAX = 300
STEP = {"L0": "before the run (the fact has no checked place in its paper)", "find": "Find", "extract": "Extract",
        "answer": "Answer", "none": ""}
WHY = {
    "none": "Right: the answer shows this fact with the right value.",
    "L0": "Not counted against the system: our checked list has no place in the paper for this fact.",
    "find": "Find did not keep the part of the paper that holds this fact, so no later step could see it.",
    "extract_none": "Find kept the right part of the paper, but Extract made no row with this value from it.",
    "extract_bad": "Extract read the value, but the row has a problem, so Answer could not use it safely.",
    "answer": "Extract made a good row for this fact, but the final answer does not show it right.",
}
NAME_WORD = {"subject": "the drug", "measure": "the measure", "patient_group": "the patient group",
             "time_point": "the time point", "dose": "the dose"}


class Refused(ValueError):
    """The run folder is not a practice run; its per-question outputs stay closed."""


# ---------------------------------------------------------------- reading
def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    except json.JSONDecodeError:
        return None


def _lines(p: Path) -> list[dict[str, Any]]:
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line) if line.strip() else None
        except json.JSONDecodeError:
            item = None
        out.append(item if isinstance(item, dict) else {})
    return out


def config(run_dir: Path) -> dict[str, Any]:
    p = run_dir / "config.yaml"
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) if p.is_file() else None
    except yaml.YAMLError:
        data = None
    return data if isinstance(data, dict) else {}


def check_practice(run_dir: Path) -> dict[str, Any]:
    """The run's config, or Refused when the run is not a practice run."""
    name = Path(run_dir).name
    if name.startswith(("bench-", "holdout-")):
        raise Refused(f"{name} is a test or hold-out run: its answers stay closed. Only practice runs can be explained.")
    cfg = config(Path(run_dir))
    if cfg.get("split") != "practice":
        raise Refused(f"{name} is not a practice run (config split: {cfg.get('split')!r}). "
                      "Only practice runs can be explained.")
    return cfg


@lru_cache(maxsize=4)
def _seed_facts(domain: str) -> dict[str, dict[str, Any]]:
    from evqa.seed import brief          # lazy: parses the seed graph
    return {f["id"]: f for p in brief.paper_facts(domain).values() for f in p["facts"]}


@lru_cache(maxsize=64)
def _l0(domain: str, paper: str) -> dict[str, list[tuple[int, int]]]:
    data = _json(domain_dir(domain) / "l0" / f"{paper}.json") or {}
    return {f["id"]: [(s["start"], s["end"]) for s in f.get("spans", [])] for f in data.get("facts", [])}


@lru_cache(maxsize=64)
def _paper(domain: str, paper: str) -> str:
    p = paper_file(domain, paper)
    return p.read_text(encoding="utf-8") if p.is_file() else ""


# ---------------------------------------------------------------- words
def unit(iri: Any) -> str:
    if not iri:
        return ""
    u = norm.units().get(str(iri), {})
    return u.get("symbol") or str(iri).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _clip(text: str, n: int = QUOTE_MAX) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def truth_line(f: dict[str, Any]) -> str:
    """'veloranide 50 mg vs placebo, week 12, adults with ...: -0.52 pp' from a seed fact."""
    head = str(f.get("subject", "?"))
    if f.get("dose"):
        head += f" {f['dose']} {unit(f.get('dose_unit')) or ''}".rstrip()
    if f.get("comparator"):
        head += f" vs {f['comparator']}"
    parts = [head]
    if f.get("week"):
        parts.append(f"week {f['week']}")
    if f.get("context"):
        parts.append(str(f["context"]))
    measure = f" ({f['measure']})" if f.get("measure") else ""
    return f"{', '.join(parts)}{measure}: {f.get('value', '?')} {unit(f.get('unit'))}".rstrip()


def row_line(r: dict[str, Any]) -> str:
    std = r.get("std") or {}
    value = f"{std.get('value')} {unit(std.get('unit'))}".rstrip() if std else f"could not read ({r.get('raw')!r})"
    bits = [str(r.get(k)) for k in ("subject", "dose", "time_point", "patient_group") if r.get(k)]
    return f"{', '.join(bits) or '?'}: {value}"


def _overlaps(a: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    return any(a[0] < e and s < a[1] for s, e in spans)


def _excerpt(text: str, offset: int, spans: list[tuple[int, int]]) -> str:
    """The text around the first fact span inside [offset, offset + len(text)), with … where it is cut."""
    inside = [(s - offset, e - offset) for s, e in spans if s - offset < len(text) and e - offset > 0]
    if not inside:
        return _clip(text)
    s, e = inside[0]
    a, b = max(0, s - WINDOW), min(len(text), e + WINDOW)
    return ("…" if a > 0 else "") + " ".join(text[a:b].split()) + ("…" if b < len(text) else "")


def _uses(node: Any, i: int, out: list[str]) -> list[str]:
    """Every answer entry (table row, ranking, effect, series point, ...) whose `rows` list cites row i."""
    if isinstance(node, dict):
        if isinstance(node.get("rows"), list) and i in node["rows"]:
            cells = node.get("cells") or node.get("group") or {}
            who = node.get("candidate") or node.get("paper") or ""
            label = ", ".join(f"{k} = {v}" for k, v in cells.items()) if isinstance(cells, dict) else str(cells)
            value = f"{node.get('value', node.get('difference', '?'))} {unit(node.get('unit'))}".rstrip()
            out.append(" ".join(x for x in (str(who), f"[{label}]" if label else "", value) if x))
        for v in node.values():
            _uses(v, i, out)
    elif isinstance(node, list):
        for v in node:
            _uses(v, i, out)
    return out


def _cited(node: Any) -> set[int]:
    """Every row index any `rows` list of the answer cites."""
    if isinstance(node, dict):
        own = {i for i in node.get("rows") or [] if isinstance(i, int)} if isinstance(node.get("rows"), list) else set()
        return own.union(*(_cited(v) for v in node.values()))
    if isinstance(node, list):
        return set().union(*(_cited(v) for v in node))
    return set()


# ---------------------------------------------------------------- per fact
def fact_data(ef: dict[str, Any], seed: dict[str, Any], hits: dict[str, dict[str, Any]], rows: list[dict[str, Any]],
              answer: Any, domain: str) -> dict[str, Any]:
    fid, paper = ef.get("id", "?"), ef.get("paper") or seed.get("paper", "?")
    blame = ef.get("blame") or "none"
    spans = _l0(domain, paper).get(fid, []) if paper != "?" else []
    matched = [i for i in ef.get("rows") or [] if isinstance(i, int) and 0 <= i < len(rows)]
    names = ef.get("names") or {}

    hit = hits.get(paper)
    passages = (hit or {}).get("passages") or []
    keep = [p for p in passages if isinstance(p, dict) and _overlaps((p.get("start", -1), p.get("end", -1)), spans)]
    if keep:
        p = keep[0]
        passage = {"start": p.get("start"), "end": p.get("end"), "section": p.get("section"),
                   "text": _excerpt(p.get("text", ""), p.get("start", 0), spans)}
        find_says = f"Find kept this part of {paper}" + (f" ({p['section']})" if p.get("section") else "") + "."
    else:
        passage = None
        find_says = (f"Find did not pick paper {paper}." if hit is None else
                     f"Find picked {paper} and kept {len(passages)} passage(s), but none holds this fact.")
    in_paper = None
    if passage is None and spans:
        text = _paper(domain, paper)
        s = spans[0][0]
        in_paper = _excerpt(text[max(0, s - WINDOW): s + 2 * WINDOW], max(0, s - WINDOW), spans) if text else None

    out_rows = []
    for i in matched:
        r = rows[i]
        wrong = [NAME_WORD.get(k, k) for k, ok in (names.get(str(i)) or {}).items() if ok is False]
        problems = ([] if r.get("quote_ok") else ["its quote could not be found in the paper"]) + \
            [f"{w} is named differently from the truth" for w in wrong]
        out_rows.append({"index": i, "row": row_line(r), "quote": _clip(r.get("quote", "")),
                         "quote_ok": bool(r.get("quote_ok")), "problems": problems,
                         "used_by_answer": _uses(answer, i, []) if isinstance(answer, dict) else []})
    near = []
    if not matched and spans:           # rows read at the fact's place, but with another value
        near = [{"index": i, "row": row_line(r), "quote": _clip(r.get("quote", ""))}
                for i, r in enumerate(rows) if r.get("paper") == paper and not r.get("dropped")
                and _overlaps((r.get("quote_start", -1), r.get("quote_end", -1)), spans)][:3]

    key = "extract_none" if blame == "extract" and not matched else "extract_bad" if blame == "extract" else blame
    return {"id": fid, "paper": paper, "truth": truth_line(seed) if seed else fid, "right": blame == "none",
            "blame": blame, "lost_at": STEP.get(blame, blame), "why": WHY.get(key, f"Lost at {blame}."),
            "find": find_says, "passage": passage, "in_paper": in_paper, "rows": out_rows, "near_rows": near,
            "in_answer": bool(ef.get("in_answer"))}


# ---------------------------------------------------------------- per question
def explain_data(run_dir: Path | str, qid: str) -> dict[str, Any]:
    run_dir = Path(run_dir)
    cfg = check_practice(run_dir)
    qdir = run_dir / qid
    if not qid or "/" in qid or ".." in qid or not qdir.is_dir():
        raise FileNotFoundError(f"no question folder {qid!r} in {run_dir}")
    ev = _json(run_dir / "eval.json") or {}
    domain = str(cfg.get("domain") or ev.get("domain") or "medical")
    qs = ev.get("questions") or {}
    q = (qs.get(qid) if isinstance(qs, dict) else next((x for x in qs if x.get("qid") == qid), None)) or {}
    spec = _json(qdir / "spec.json") or {}
    answer = _json(qdir / "answer.json")
    hits = {h.get("paper"): h for h in _lines(qdir / "find.jsonl") if h.get("paper")}
    rows = _lines(qdir / "rows.jsonl")
    seed = _seed_facts(domain) if q.get("facts") else {}
    facts = [fact_data(ef, seed.get(ef.get("id"), {}), hits, rows, answer, domain)
             for ef in q.get("facts") or [] if isinstance(ef, dict)]
    l3 = q.get("l3") or {}
    ans = answer if isinstance(answer, dict) else {}
    out: dict[str, Any] = {
        "run_id": run_dir.name, "qid": qid, "question": spec.get("question"), "type": q.get("type") or spec.get("type"),
        "scored": bool(q), "answerable": q.get("answerable", bool(facts)), "score": l3.get("score"),
        "exact": l3.get("exact"), "answer_sentence": ans.get("sentence"), "said_not_reported": ans.get("not_reported"),
        "facts": facts, "right": sum(f["right"] for f in facts),
        "spec_mismatches": list((q.get("advisor") or {}).get("mismatches") or [])[:5]}
    if facts and out["score"] == 1 and out["right"] < len(facts):
        out["note"] = ("The question gets full score, but the per-fact check did not find every true fact in the "
                       "answer as written (for example a cell says 'not stated'), so those facts are blamed on Answer.")
    if q and not q.get("answerable", True):          # true answer: not in the papers
        bad = bool(l3.get("hallucination"))
        used = sorted({i for i in _cited(ans) if 0 <= i < len(rows)})
        out["not_reported"] = {
            "right": not bad,
            "rows": [{"index": i, "row": row_line(rows[i]), "quote": _clip(rows[i].get("quote", ""))} for i in used],
            "why": ("Right: the papers do not report this, and the answer did not give a value." if not bad else
                    "Wrong: the papers do not report this, but the answer gave a value anyway."
                    + (" It used a close but different fact." if l3.get("near_miss_trap") else ""))}
    return out


def render(d: dict[str, Any]) -> str:
    lines = [f"{d['qid']} ({d.get('type') or '?'}): {d.get('question') or '(no spec.json)'}"]
    if not d["scored"]:
        lines.append("This question has no score in eval.json yet (run `evqa eval <run_dir>` first).")
    if d.get("answer_sentence"):
        lines.append(f"The answer said: {_clip(d['answer_sentence'])}")
    if d.get("score") is not None:
        lines.append(f"Score: {d['score']} of 1{' (exact)' if d.get('exact') else ''}. "
                     f"{d['right']} of {len(d['facts'])} true facts shown right.")
    if "not_reported" in d:
        lines.append(d["not_reported"]["why"])
        for r in d["not_reported"]["rows"]:
            lines += [f"  The value came from Extract row {r['index']}: {r['row']}", f"    quote: \"{r['quote']}\""]
    if d.get("note"):
        lines.append(f"Note: {d['note']}")
    for n, f in enumerate(d["facts"], 1):
        verdict = "RIGHT" if f["right"] else f"WRONG, lost at {f['lost_at']}"
        lines += ["", f"Fact {n} of {len(d['facts'])}: {f['id']} in {f['paper']}: {verdict}",
                  f"  Truth: {f['truth']}", f"  Why: {f['why']}", f"  Find: {f['find']}"]
        if f["passage"]:
            lines.append(f"    passage: \"{f['passage']['text']}\"")
        elif f.get("in_paper"):
            lines.append(f"    the fact is here in the paper: \"{f['in_paper']}\"")
        for r in f["rows"]:
            lines.append(f"  Extract row {r['index']}: {r['row']} ({'quote checked' if r['quote_ok'] else 'quote NOT checked'})")
            lines.append(f"    quote: \"{r['quote']}\"")
            for p in r["problems"]:
                lines.append(f"    problem: {p}")
            uses = r["used_by_answer"]
            lines.append(f"  Answer used row {r['index']} as: {'; '.join(uses)}" if uses
                         else f"  Answer did not use row {r['index']}.")
        if not f["rows"] and f["blame"] not in ("L0", "find"):
            lines.append("  Extract made no row with the true value at this place.")
            for r in f["near_rows"]:
                lines.append(f"    row {r['index']} read here instead: {r['row']}  quote: \"{r['quote']}\"")
    if d.get("spec_mismatches"):
        lines += ["", "How Spec read the question differs from the true intent:"]
        lines += [f"  - {m}" for m in d["spec_mismatches"]]
    return "\n".join(lines)


def explain(run_dir: Path | str, qid: str) -> str:
    return render(explain_data(run_dir, qid))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="evqa explain", description="why one question of a practice run is right or wrong")
    p.add_argument("run_dir", type=Path)
    p.add_argument("qid")
    p.add_argument("--json", action="store_true", help="print the data form (what the Workbench shows)")
    a = p.parse_args(argv)
    try:
        d = explain_data(a.run_dir, a.qid)
    except (Refused, FileNotFoundError) as exc:
        print(exc, file=sys.stderr)
        return 2
    print(json.dumps(d, indent=2, ensure_ascii=False) if a.json else render(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
