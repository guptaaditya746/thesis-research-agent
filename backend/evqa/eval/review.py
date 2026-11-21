"""Optional human review: small samples a person can label later, one item at a time. No LLM.

Tasks (TASKS): each has one plain question, a few answer choices with a short rubric, and items built from saved
artifacts. Running, scoring and viewing a run never wait for a label: a task with no labels shows "awaiting review".

  fidelity    scope = domain. One seed fact: the full claim (drug, comparator, measure, patients, dose, time, value)
              next to the paper text where L0 put it (a table excerpt keeps its caption and header row; up to 4 L0 spans, each marked). Sample:
              every fact L0 could not place, matched ambiguously or not in the planned place; every fact where the
              writer report (runs/paperwriter/.../facts_check.json) and L0 disagree; plus PASS_SAMPLE ordinary passes
              (seeded random). Practice papers by default (split argument).
  population  scope = run. One unique pair from run_dir/population_judge.json: the patient group as the run wrote it
              and the true seed group.

Hidden verdicts: items_for() never returns the automated verdict (or the stratum, which names it) of an item the reviewer has not labelled;
add_label() returns it right after the label is saved.

Labels: append-only JSON lines in REVIEWS/<task>.jsonl, one per submit: task, scope, item_id, item_version,
rubric, reviewer, choice, parts, note, ts. A later submit by the same reviewer for the same item and version
replaces the earlier one in the counts; every line is kept. item_version binds the label to what was shown (the
paper's sha256 + fact id, or the pair's own text); a label on an older version is counted as stale, not as a label.
Each reviewer's labels count separately; disagreements are counted, not resolved.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import random
from pathlib import Path
from typing import Any

from evqa import norm
from evqa.eval import dataset as l0
from evqa.eval import prism
from evqa.paths import DATA, DATASET, REPO
from evqa.seed import brief

REVIEWS = DATA / "reviews"                 # module variable so tests can monkeypatch it
RUNS = REPO / "runs" / "evqa"
WRITER = REPO / "runs" / "paperwriter"
PASS_SAMPLE = 10
SEED = 20261121
EXCERPT = 600                              # characters of prose shown around a value in a long paragraph
PARAGRAPH = 1600                           # a paragraph up to this length is shown whole

TASKS: dict[str, dict[str, Any]] = {
    "fidelity": {
        "title": "Paper fidelity", "scope": "domain", "rubric": "fidelity-v1-draft",
        "question": "Does the paper text support this complete claim?",
        "choices": [
            {"id": "supported", "label": "Supported",
             "help": "The excerpt (with its table headers) states the number and unit, and every part of the claim "
                     "is clear: drug, compared with, measure, patients, dose, time."},
            {"id": "partly", "label": "Partly supported",
             "help": "The number is there, but at least one part is missing, unclear or different. Tick which."},
            {"id": "unsupported", "label": "Unsupported",
             "help": "The excerpt does not state this claim, or the number belongs to another drug, group, dose or time."},
            {"id": "cant_tell", "label": "Can't tell", "help": "You cannot decide from what is shown."},
        ],
        "parts": ["drug", "compared with", "measure", "patients", "dose", "time", "number or unit"],
    },
    "population": {
        "title": "Patient group wording", "scope": "run", "rubric": "population-v1-draft",
        "question": "Do these two describe the same patients?",
        "choices": [
            {"id": "same", "label": "Same patients", "help": "Same group, maybe in other words."},
            {"id": "different", "label": "Different",
             "help": "Another group, or a broader or narrower one (\"adults\" vs \"adults with asthma\")."},
            {"id": "cant_tell", "label": "Can't tell", "help": "Too vague to decide."},
        ],
        "parts": [],
    },
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- fidelity items
def _writer_report(domain: str, paper: str) -> dict[str, dict[str, Any]]:
    for p in (WRITER / domain / paper / "facts_check.json", WRITER / paper / "facts_check.json"):
        if p.is_file():
            return {f["id"]: f for f in json.loads(p.read_text(encoding="utf-8")).get("facts", [])}
    return {}


def _line(text: str, pos: int) -> tuple[int, int]:
    a = text.rfind("\n", 0, pos) + 1
    b = text.find("\n", pos)
    return a, len(text) if b < 0 else b


def _excerpt(text: str, start: int, end: int) -> dict[str, Any]:
    """The table lines (caption, header row, separator, the value's row) or the paragraph around [start, end),
    with the value's offsets inside the excerpt ("mark")."""
    for t in l0.tables(text):
        if t.start <= start < t.end:
            ha, hb = _line(text, t.start)
            sa, sb = _line(text, hb + 1)
            ra, rb = _line(text, start)
            prefix = "\n".join(x for x in (t.caption, text[ha:hb], text[sa:sb]) if x) + "\n"
            return {"kind": "table", "text": prefix + text[ra:rb],
                    "marks": [[len(prefix) + start - ra, len(prefix) + end - ra]]}
    p = text.rfind("\n\n", 0, start)
    a = p + 2 if p >= 0 else 0
    q = text.find("\n\n", end)
    b = q if q >= 0 else len(text)
    if b - a > PARAGRAPH:                      # a long paragraph: a window cut at words
        if a < start - EXCERPT:
            a = text.find(" ", start - EXCERPT) + 1
        if b > end + EXCERPT:
            b = max(text.rfind(" ", end, end + EXCERPT), end)
    return {"kind": "text", "text": text[a:b], "marks": [[start - a, end - a]]}


def _evidence(text: str, spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One excerpt per place; two spans in the same excerpt share it (both marked)."""
    out: list[dict[str, Any]] = []
    for s in spans[:4]:
        e = _excerpt(text, s["start"], s["end"])
        same = next((x for x in out if x["text"] == e["text"]), None)
        if same:
            same["marks"] += e["marks"]
        else:
            out.append(e)
    return out


def _claim(f: dict[str, Any]) -> list[dict[str, str]]:
    unit = norm.units().get(f["unit"], {}).get("write_as", f["unit"])
    dose_u = norm.units().get(f.get("dose_unit") or "", {}).get("write_as", "")
    out = [("drug", f.get("subject_as") or f["subject"]), ("compared with", f.get("comparator") or ""),
           ("measure", f["measure"]), ("patients", f["context"]),
           ("dose", f"{f['dose']} {dose_u}".strip() if f.get("dose") else ""),
           ("time", f"week {f['week']}" if f.get("week") else ""), ("number or unit", f"{f['value']} {unit}")]
    return [{"part": k, "value": v} for k, v in out if v]


def fidelity_items(domain: str, split: str = "practice") -> list[dict[str, Any]]:
    """The fidelity sample (module doc), in a fixed order. Each item: id, version, stratum, show, automated."""
    papers = brief.paper_facts(domain)
    flagged, passes = [], []
    for pid, p in sorted(papers.items()):
        if p.get("split") != split:
            continue
        path = DATASET / domain / pid / "paper.md"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        l0_rep = prism.l0_facts(domain, pid)
        writer = _writer_report(domain, pid)
        for f in p["facts"]:
            r = l0_rep.get(f["id"], {})
            spans = r.get("spans", [])
            w = writer.get(f["id"])
            ambiguous = bool(spans) and any(s.get("ambiguous") for s in spans)
            reasons = []
            if not spans:
                reasons.append("L0 found no span")
            if ambiguous:
                reasons.append("L0 match is ambiguous")
            if spans and not r.get("in_planned_place"):
                reasons.append("L0: not in the planned place")
            if w is not None and bool(w.get("ok")) != bool(spans and r.get("in_planned_place")):
                reasons.append("writer and L0 disagree")
            item = {"id": f"fidelity:{domain}:{f['id']}", "version": f"{_sha(text)[:16]}:{f['id']}",
                    "stratum": "flagged" if reasons else "pass", "paper": pid, "fact": f["id"],
                    "show": {"claim": _claim(f), "paper": pid, "title": p.get("title", ""),
                             "evidence": _evidence(text, spans)},
                    "automated": {"l0": "found" if spans else "missing",
                                  "l0_in_planned_place": bool(r.get("in_planned_place")),
                                  "l0_ambiguous": ambiguous,
                                  "writer": None if w is None else ("ok" if w.get("ok") else "failed"),
                                  "why_sampled": reasons or ["ordinary pass"]}}
            (flagged if reasons else passes).append(item)
    rng = random.Random(SEED)
    picked = sorted(rng.sample(passes, min(PASS_SAMPLE, len(passes))), key=lambda i: i["id"])
    return flagged + picked


# ---------------------------------------------------------------- population items
def run_dir(run_id: str) -> Path:
    d = RUNS / run_id
    if "/" in run_id or run_id.startswith(".") or not d.is_dir():
        raise FileNotFoundError(run_id)
    return d


def population_items(run_id: str) -> list[dict[str, Any]]:
    d = run_dir(run_id)
    p = d / "population_judge.json"
    if not p.is_file():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for it in data.get("details", []):
        key = _sha(it["label"] + "\x00" + it["conditions"])[:16]
        if key not in out:
            out[key] = {"id": f"population:{key}", "version": key, "stratum": it["verdict"],
                        "show": {"label": it["label"], "conditions": it["conditions"], "facts": 0},
                        "automated": {"judge": it["verdict"], "judge_model": data.get("judge_model"),
                                      "reason": it.get("reason", "")}}
        out[key]["show"]["facts"] += 1
    return list(out.values())


def items(task: str, scope: str) -> list[dict[str, Any]]:
    if task == "fidelity":
        return fidelity_items(scope)
    if task == "population":
        return population_items(scope)
    raise KeyError(task)


# ---------------------------------------------------------------- labels
def _path(task: str) -> Path:
    return REVIEWS / f"{task}.jsonl"


def labels(task: str, scope: str) -> list[dict[str, Any]]:
    p = _path(task)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            if rec.get("scope") == scope:
                out.append(rec)
    return out


def latest(task: str, scope: str) -> dict[tuple[str, str], dict[str, Any]]:
    """(item_id, reviewer) -> the reviewer's last label on the item's current version."""
    current = {i["id"]: i["version"] for i in items(task, scope)}
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for rec in labels(task, scope):
        if current.get(rec["item_id"]) == rec["item_version"]:
            out[(rec["item_id"], rec["reviewer"])] = rec
    return out


def items_for(task: str, scope: str, reviewer: str) -> list[dict[str, Any]]:
    """The sample for one reviewer: automated verdicts only on items this reviewer already labelled."""
    mine = latest(task, scope)
    out = []
    for it in items(task, scope):
        lab = mine.get((it["id"], reviewer))
        hidden = ("automated", "stratum")             # the stratum names the automated verdict too
        out.append({k: v for k, v in it.items() if k not in hidden} | {
            "label": lab, **({"automated": it["automated"], "stratum": it["stratum"]} if lab else {})})
    return out


def add_label(task: str, scope: str, item_id: str, item_version: str, reviewer: str, choice: str,
              parts: list[str] | None = None, note: str = "") -> dict[str, Any]:
    spec = TASKS[task]
    reviewer = reviewer.strip()
    if not reviewer:
        raise ValueError("a reviewer name is needed")
    if choice not in {c["id"] for c in spec["choices"]}:
        raise ValueError(f"choice must be one of {[c['id'] for c in spec['choices']]}")
    bad = [p for p in parts or [] if p not in spec["parts"]]
    if bad:
        raise ValueError(f"unknown parts {bad}")
    item = next((i for i in items(task, scope) if i["id"] == item_id), None)
    if item is None:
        raise KeyError(item_id)
    if item["version"] != item_version:
        raise ValueError("the item changed since it was shown (new paper or run): reload and look again")
    rec = {"task": task, "scope": scope, "item_id": item_id, "item_version": item_version, "rubric": spec["rubric"],
           "reviewer": reviewer, "choice": choice, "parts": list(parts or []), "note": note.strip(),
           "ts": datetime.datetime.now().isoformat(timespec="seconds")}
    REVIEWS.mkdir(parents=True, exist_ok=True)
    with _path(task).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"saved": rec, "automated": item["automated"]}


def summary(task: str, scope: str) -> dict[str, Any]:
    """Coverage and label counts for the Evaluation page; counts per reviewer label, not merged."""
    its = items(task, scope)
    lab = latest(task, scope)
    reviewed = {i for i, _ in lab}
    by_item: dict[str, set[str]] = {}
    for (i, _), rec in lab.items():
        by_item.setdefault(i, set()).add(rec["choice"])
    auto = {i["id"]: i["automated"] for i in its}
    key = "judge" if task == "population" else "why_sampled"
    cross: dict[str, dict[str, int]] = {}
    for (i, _), rec in lab.items():
        a = auto[i][key]
        for k in (a if isinstance(a, list) else [a]):
            cross.setdefault(str(k), {}).setdefault(rec["choice"], 0)
            cross[str(k)][rec["choice"]] += 1
    current = {i["id"]: i["version"] for i in its}
    stale = sum(current.get(r["item_id"]) != r["item_version"] for r in labels(task, scope))
    return {"task": task, "title": TASKS[task]["title"], "scope": scope, "rubric": TASKS[task]["rubric"],
            "items": len(its), "reviewed": len(reviewed), "labels": len(lab),
            "reviewers": sorted({r for _, r in lab}),
            "double_reviewed": sum(1 for i in by_item if sum(1 for (j, _) in lab if j == i) > 1),
            "disagreements": sum(1 for v in by_item.values() if len(v) > 1),
            "counts": {c["id"]: sum(r["choice"] == c["id"] for r in lab.values()) for c in TASKS[task]["choices"]},
            "by_automated": cross, "stale_labels": stale,
            "status": "awaiting optional review" if not lab else f"{len(reviewed)} of {len(its)} reviewed"}
