"""How much of a run comes out the same when every one of its model calls is asked again.

`evidence reexec RUN --all-calls --times N --out DIR` re-runs a run N times with no cache (replay.reexec, all_calls);
this module compares each re-run with the original: the model calls (the same request: the same reply?), the items
found again, the final answer. It re-asks one run's calls once; it does not repeat the system's retry of a written
answer that failed its checks.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, NamedTuple, Sequence

from .contract import digest
from .readable import answer_text, headline, read_run
from .replay import _item_key
from .rundir import EVIDENCE_FILE, REEXEC_FILE, RUN_CALLS_FILE, RUN_FILE, read_json, read_lines

GROUPS = ("llm", "agent", "stage", "names", "other")
GROUP_TEXT = {"llm": "LLM extractors", "agent": "agentic extractor", "stage": "stages (the run's own model calls)",
              "names": "names check", "other": "other model calls"}
OUTCOMES = ("identical", "other_reply", "failed", "unreadable", "not_asked_again")
AGENT_OK = "finished"   # the status the agent loop's broker gives a model-call step that went through (agent/broker.py)
COUNTS = ("calls", *OUTCOMES, "new")


class ModelCall(NamedTuple):
    group: str
    slot: str
    request: str | None
    reply: str | None
    failed: bool
    readable: bool
    temperature: float | None
    served: str | None


def _specs(run: Path) -> dict[str, Any]:
    path = run / RUN_FILE
    return (read_json(path).get("extractor_specs") or {}) if path.is_file() else {}


def _group(extractor_id: str, specs: dict[str, Any]) -> str:
    if extractor_id.startswith("stage:"):
        return "stage"
    if extractor_id.startswith("names_confirm@"):
        return "names"
    kind = (specs.get(extractor_id) or {}).get("kind")
    return kind if kind in ("llm", "agent") else "other"


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _call(group: str, slot: str, rec: Any, spec_temperature: float | None, agent_run: dict[str, Any]) -> ModelCall:
    if not isinstance(rec, dict):
        return ModelCall(group, slot, None, None, False, False, None, None)
    request = rec.get("request")
    response = rec.get("response") if isinstance(rec.get("response"), dict) else {}
    if rec.get("kind") == "agent_model_call" and isinstance(request, dict):
        sha = response.get("response_sha256")
        readable = (bool(sha) or "error" in rec) and bool(request.get("step_id")) and bool(request.get("prompt_sha256"))
        temperature = spec_temperature if spec_temperature is not None else _number(agent_run.get("temperature"))
        served = agent_run.get("served_model")
        key = digest([request.get("step_id"), request.get("prompt_sha256")]) if readable else None
        return ModelCall(group, slot, key, sha,
                         "error" in rec or request.get("status") != AGENT_OK, readable, temperature,
                         served if isinstance(served, str) else None)
    settings = request.get("settings") if isinstance(request, dict) else None
    engine = isinstance(settings, dict)
    readable = engine and ("output" in response or "error" in rec)
    served = response.get("served_model")
    return ModelCall(group, slot, digest(request) if isinstance(request, dict) else None,
                     digest(response["output"]) if "output" in response else None, "error" in rec, readable,
                     _number(settings.get("temperature")) if engine else None,
                     served if isinstance(served, str) else None)


def model_calls(run: Path) -> list[ModelCall]:
    """Every model-call record of every calls.jsonl row of the run."""
    run = Path(run)
    path = run / RUN_CALLS_FILE
    if not path.is_file():
        raise ValueError(f"{run} has no calls.jsonl: its model calls cannot be compared")
    specs = _specs(run)
    out: list[ModelCall] = []
    for entry in read_lines(path):
        eid = str(entry.get("extractor_id") or "")
        group = _group(eid, specs)
        config = (specs.get(eid) or {}).get("config")
        spec_temperature = _number(config.get("temperature")) if isinstance(config, dict) else None
        records = entry.get("model_calls") or []
        agent_run = next((r["agent_run"] for r in records if isinstance(r, dict)
                          and isinstance(r.get("agent_run"), dict)), {})
        for index, rec in enumerate(records):
            out.append(_call(group, f"{entry.get('key')}#{index}", rec, spec_temperature, agent_run))
    return out


def _outcome(old: ModelCall, new: ModelCall | None) -> str:
    if not old.readable or (new is not None and not new.readable):
        return "unreadable"
    if new is None:
        return "not_asked_again"
    if new.failed:
        return "failed"
    if old.failed:
        return "other_reply"
    return "identical" if old.reply == new.reply else "other_reply"


def compare_calls(original: Path, rerun: Path) -> dict[str, dict]:
    """Per group, how the original's model calls came out in the re-run (see the counts in COUNTS)."""
    old, new = model_calls(original), model_calls(rerun)
    out: dict[str, dict] = {}
    for group in GROUPS:
        before = [c for c in old if c.group == group]
        after = [c for c in new if c.group == group]
        used: set[int] = set()
        matched: dict[int, int] = {}
        for i, c in enumerate(before):   # the same slot with the same request first (calls with one request stay paired)
            for j, d in enumerate(after):
                if j not in used and d.slot == c.slot and d.request is not None and d.request == c.request:
                    matched[i] = j
                    used.add(j)
                    break
        for i, c in enumerate(before):
            if i in matched or c.request is None:
                continue
            for j, d in enumerate(after):
                if j not in used and d.request == c.request:
                    matched[i] = j
                    used.add(j)
                    break
        counts = Counter(_outcome(c, after[matched[i]] if i in matched else None) for i, c in enumerate(before))
        known = [*before, *after]
        out[group] = {"calls": len(before), **{k: counts[k] for k in OUTCOMES}, "new": len(after) - len(used),
                      "temperatures": sorted({c.temperature for c in known if c.temperature is not None}),
                      "served": sorted({c.served for c in known if c.served is not None})}
    return out


def _items(run: Path) -> list[dict[str, Any]]:
    return list(read_lines(run / EVIDENCE_FILE))


def item_stability(original: Path, rerun: Path) -> dict:
    """Items of the original found again in the re-run by content (type, fields, what the links point to), as multisets."""
    old, new = _items(Path(original)), _items(Path(rerun))
    known_old, known_new = {i["item_id"]: i for i in old}, {i["item_id"]: i for i in new}
    left = Counter(_item_key(i, known_new) for i in new)
    by_type: dict[str, list[int]] = {}
    found = 0
    for item in old:
        key = _item_key(item, known_old)
        again = left[key] > 0
        if again:
            left[key] -= 1
        found += again
        pair = by_type.setdefault(item["evidence_type"], [0, 0])
        pair[0] += 1
        pair[1] += again
    return {"items": len(old), "found_again": found, "by_type": by_type}


def items_by_extractor(original: Path, rerun: Path) -> dict[str, list[int]]:
    """The re-run's reexec.json summary summed by the kind of the extractor in the original run (llm, agent, other)."""
    kinds = {eid.split("@")[0]: (spec or {}).get("kind") for eid, spec in _specs(Path(original)).items()}
    out = {"llm": [0, 0], "agent": [0, 0], "other": [0, 0]}
    for name, row in (read_json(Path(rerun) / REEXEC_FILE).get("summary") or {}).items():
        kind = kinds.get(name.split("@")[0])
        slot = out[kind if kind in ("llm", "agent") else "other"]
        slot[0] += row.get("items_original", 0)
        slot[1] += row.get("items_reproduced", 0)
    return out


def same_answer(original: Path, rerun: Path) -> dict:
    """Whether the final answer text and headline are the same; None and the refusal text when a run cannot be read."""
    try:
        a, b = read_run(original, texts=False), read_run(rerun, texts=False)
    except (ValueError, OSError, KeyError) as exc:   # NotRebuilt is a ValueError; a missing corpus or file also
        return {"text": None, "headline": None, "why": str(exc)}
    return {"text": answer_text(a) == answer_text(b), "headline": headline(a) == headline(b), "why": None}


def _sum_calls(parts: Sequence[dict[str, dict]]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for group in GROUPS:
        rows = [p[group] for p in parts if group in p]
        out[group] = {**{k: sum(r[k] for r in rows) for k in COUNTS},
                      "temperatures": sorted({t for r in rows for t in r["temperatures"]}),
                      "served": sorted({s for r in rows for s in r["served"]})}
    return out


def _sum_items(parts: Sequence[dict]) -> dict:
    by_type: dict[str, list[int]] = {}
    for p in parts:
        for kind, (n, f) in p["by_type"].items():
            pair = by_type.setdefault(kind, [0, 0])
            pair[0] += n
            pair[1] += f
    return {"items": sum(p["items"] for p in parts), "found_again": sum(p["found_again"] for p in parts),
            "by_type": by_type}


def _sum_extractors(parts: Sequence[dict[str, list[int]]]) -> dict[str, list[int]]:
    return {k: [sum(p[k][0] for p in parts), sum(p[k][1] for p in parts)] for k in ("llm", "agent", "other")}


def measure(original: Path, reruns: Sequence[Path]) -> dict:
    """The re-runs of one run compared with it, summed over the re-runs."""
    original = Path(original)
    answers = [same_answer(original, r) for r in reruns]
    compared = [a for a in answers if a["text"] is not None]
    return {"run": original.name, "reruns": len(reruns),
            "calls": _sum_calls([compare_calls(original, r) for r in reruns]),
            "items": _sum_items([item_stability(original, r) for r in reruns]),
            "items_by_extractor": _sum_extractors([items_by_extractor(original, r) for r in reruns]),
            "answers": {"compared": len(compared), "same_text": sum(a["text"] for a in compared),
                        "same_headline": sum(a["headline"] for a in compared),
                        "whys": sorted({a["why"] for a in answers if a["why"]})}}


def combine(reports: Sequence[dict]) -> dict:
    """Several runs' reports as one: every count summed, `runs` the number of reports, `reruns` their total."""
    return {"runs": len(reports), "reruns": sum(r["reruns"] for r in reports),
            "calls": _sum_calls([r["calls"] for r in reports]),
            "items": _sum_items([r["items"] for r in reports]),
            "items_by_extractor": _sum_extractors([r["items_by_extractor"] for r in reports]),
            "answers": {"compared": sum(r["answers"]["compared"] for r in reports),
                        "same_text": sum(r["answers"]["same_text"] for r in reports),
                        "same_headline": sum(r["answers"]["same_headline"] for r in reports),
                        "whys": sorted({w for r in reports for w in r["answers"]["whys"]})}}


def share(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "-"


def _per_run(report: dict) -> str:
    per = report["reruns"] / (report.get("runs") or 1)
    return str(int(per)) if per == int(per) else f"{per:.1f}"


def render(report: dict) -> list[str]:
    lines = [f"Re-run measure: {report.get('runs') or 1} runs x {_per_run(report)} re-runs, no cache (every model "
             "call asked again).", "Model calls (identical: the same request got the same reply):"]
    served: set[str] = set()
    for group in GROUPS:
        c = report["calls"][group]
        served.update(c["served"])
        if not c["calls"] and not c["new"] and group == "other":
            continue
        if not c["calls"] and not c["new"]:
            lines.append(f"  {GROUP_TEXT[group]}: no calls in these runs")
            continue
        temps = ", ".join(f"{t:g}" for t in c["temperatures"]) or "unknown"
        lines.append(f"  {GROUP_TEXT[group]} (temperature {temps}): {c['calls']} calls, {c['identical']} identical "
                     f"({share(c['identical'], c['calls'])}), {c['other_reply']} other reply, {c['failed']} failed, "
                     f"{c['unreadable']} unreadable, {c['not_asked_again']} not asked again, {c['new']} new")
    lines.append(f"  served models: {', '.join(sorted(served)) or 'unknown'}")
    items = report["items"]
    types = ", ".join(f"{t} {share(f, n)}" for t, (n, f) in sorted(items["by_type"].items()))
    lines.append(f"Items found again: {share(items['found_again'], items['items'])} of {items['items']}"
                 + (f" ({types})" if types else ""))
    by = report["items_by_extractor"]
    part = lambda key: share(by[key][1], by[key][0]) if by[key][0] else "no items in these runs"
    lines.append(f"Items found again by extractor: LLM extractors {part('llm')}, agentic extractor {part('agent')}, "
                 f"other extractors {part('other')}")
    a = report["answers"]
    lines.append(f"Final answer the same: text in {a['same_text']} of {a['compared']} re-runs, headline in "
                 f"{a['same_headline']} of {a['compared']}")
    lines.extend(f"  not compared: {why}" for why in a["whys"])
    lines.append("This re-asks one run's calls once; it does not repeat the system's retry of a written answer that "
                 "failed its checks.")
    return lines
