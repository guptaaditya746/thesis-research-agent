"""What the Workbench questions pane shows: question -> intent card -> SPARQL -> gold rows -> answer. Read-only; reads
the frozen files (questions jsonl, gold json, manifest) and re-runs each SPARQL to show whether it still gives gold."""
from __future__ import annotations

import json
from typing import Any

from evqa.seed import questions, view


def _records(domain: str) -> list[dict[str, Any]]:
    out = []
    for path in sorted(questions.questions_dir(domain).glob("*.jsonl")):
        out += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return sorted(out, key=lambda r: (r["split"] != "test", r["qid"]))


def _gold(domain: str, qid: str) -> dict[str, Any]:
    return json.loads((questions.gold_dir(domain) / f"{qid}.json").read_text(encoding="utf-8"))


def listing(domain: str) -> dict[str, Any]:
    """All questions of a domain (short form) and whether the files still match the manifest."""
    items = [{"qid": r["qid"], "type": r["type"], "split": r["split"], "question": r["question"],
              "answerable": r.get("answerable", True),
              "open_points": [e["label"] for e in r["intent_card"] if e["point"] != "other_names"]}
             for r in _records(domain)]
    path = questions.gold_dir(domain) / "manifest.json"
    m = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    counts: dict[str, dict[str, int]] = {}
    for q in items:
        counts.setdefault(q["type"], {}).setdefault(q["split"], 0)
        counts[q["type"]][q["split"]] += 1
    report = (m or {}).get("generator", {}).get("report")
    return {"domain": domain, "questions": items, "counts": counts, "frozen": {
        "set_sha256": m["set_sha256"] if m else None, "problems": questions.verify(domain)}, "report": report}


def detail(domain: str, qid: str) -> dict[str, Any]:
    """One question with its card, SPARQL, the gold rows (dataset pane columns) and the answer."""
    rec = next((r for r in _records(domain) if r["qid"] == qid), None)
    if rec is None:
        raise KeyError(qid)
    g = _gold(domain, qid)
    by_id = {r["id"]: r for r in view.overview(domain)["rows"]}
    rerun = [r["id"] for r in questions.run_query(view.graph_of(domain), g["sparql"])]
    answerable = g.get("answerable", rec.get("answerable", True))
    return {**rec, "answerable": answerable, "sparql": g["sparql"], "slots": g["slots"],
            "rows": [by_id[i] for i in g["row_ids"] if i in by_id],
            "near_rows": [by_id[i] for i in g.get("near_rows", []) if i in by_id],
            "why": g["answer"].get("why"), "absence_check": g.get("absence_check"), "wording": g.get("wording"),
            "answer": g["answer"], "rows_without_card": g["rows_without_card"], "notes": g["notes"],
            "rerun_matches": rerun == g["row_ids"]}
