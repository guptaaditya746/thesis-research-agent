"""Replay and re-execution of a recorded run (contract section 8).

`replay(run)`: the same protocol, corpus and settings, from the record cache only (a miss is
NotRecorded) and the recorded reasoner inferences (reason.json, never reasoned again); writes a new run directory
(mode replay) and checks that every output hash equals the one in the recorded run.json. This is what "every time
we run the provenance we get the same data" means. A reexec reasons again: its items may differ.

`reexec(run, extractor)`: runs the chosen extractor (all when none is named) again from scratch, bypassing
the cache, writes a new run directory (mode reexec) and in it reexec.json, which compares each call with
the recorded one: identical, same items with different spans, items added, items missing, or fields
differ; plus a summary per extractor. Calls are matched by document, evidence type and extractor name,
and items by evidence type, fields and what their links point to (by the linked item's type and fields,
not its id, so an upstream span change does not count as a downstream difference).
"""
from __future__ import annotations

import importlib
from collections import Counter
from pathlib import Path
from typing import Any

from . import stages
from .calls import NotRecorded, cache_key
from .contract import digest
from .engine import Settings, default_provider, execute_run, plan_stages
from .plan import load_plan
from .locate import Locator
from .recording import Provider
from jsonio import write_json

from .rundir import (CALLS_DIR, COMPARISONS_FILE, EVENTS_FILE, EVIDENCE_FILE, LOCK_FILE, PROTOCOL_FILE, REEXEC_FILE,
                     RUN_FILE, RunDir, read_json, read_lines)

OUTCOMES = ("identical", "same_items_different_spans", "items_added", "items_missing", "fields_differ")
# Outputs the engine writes since a later change (the lock since EV4, comparisons.json since plan 2): a replay of a run
# recorded before it lists them as `added`, not as a mismatch (every recorded output must still match).
ADDED_OUTPUTS = (LOCK_FILE, COMPARISONS_FILE)


class CodeChanged(NotRecorded):
    """The recorded run's extractor ids are not the ones this code builds (an extractor's source changed since, e.g.
    modelcall/call.py on 4 Nov): its calls are cached under the old ids, so replay it from its own commit."""


def _check_same_code(run_dir: Path, record: dict[str, Any], new: Path, exc: NotRecorded) -> None:
    """Raise CodeChanged (naming the ids and the recorded commit) when the replay's lock builds other extractor ids
    than the recorded run used; else return (a plain cache miss)."""
    lock = new / LOCK_FILE
    if not lock.is_file():
        return
    built = {i for ids in read_json(lock)["extractors"].values() for i in ids}
    used = set(record.get("extractors") or [])
    if used <= built:
        return
    manifest = run_dir / "manifest.json"
    commit = (read_json(manifest).get("code_commit") if manifest.is_file() else None) or "the run's commit"
    raise CodeChanged(f"{exc}. The run was recorded with extractor ids {sorted(used - built)} that this code does not "
                      f"build (it builds {sorted(built - used)}): an extractor's source changed since. Replay it from "
                      f"a checkout of {commit} (git worktree add <dir> {commit}).") from exc


def replay(run_dir: Path | str, *, cache: Path | str | None = None, corpus: Path | str | None = None,
           out_dir: Path | str | None = None, locator: Locator | None = None) -> tuple[Path, dict[str, Any]]:
    """(new run directory, {ok, mismatched}, plus `added`: the ADDED_OUTPUTS the recorded run lacks, when there are
    any); raises NotRecorded on a cache miss."""
    run_dir = Path(run_dir)
    record = read_json(run_dir / RUN_FILE)
    settings = Settings.from_record(record, cache=cache, corpus=corpus, run_dir=run_dir)
    for module in settings.imports:   # modules that register stages must be in before the registered set is compared
        importlib.import_module(module)
    stages.check_recorded(record.get("stages"),
                          plan_stages(settings, load_plan(settings.plan) if settings.plan is not None else None))
    run_id = f"{record['run_id']}-replay-{_stamp()}"
    try:
        new = execute_run((run_dir / PROTOCOL_FILE).read_bytes(), settings,
                          out_dir or run_dir.parent, mode="replay", provider=None, locator=locator,
                          source_run=record["run_id"], attempts=_attempts(run_dir), run_id=run_id,
                          source_dir=run_dir)   # the recorded reason.json: a replay never reasons again
    except NotRecorded as exc:
        _check_same_code(run_dir, record, Path(out_dir or run_dir.parent) / run_id, exc)
        raise
    outputs = read_json(new / RUN_FILE)["outputs"]
    names = sorted(set(outputs) | set(record["outputs"]))
    added = sorted(n for n in names if n in ADDED_OUTPUTS and n not in record["outputs"])
    mismatched = [n for n in names if n not in added and outputs.get(n) != record["outputs"].get(n)]
    return new, {"ok": not mismatched, "mismatched": mismatched, "source_run": record["run_id"], "replay_run": new.name,
                 **({"added": added} if added else {}), **_other_code(run_dir, mismatched)}


def _other_code(run_dir: Path, mismatched: list[str]) -> dict[str, str]:
    """{"note": ...} when a mismatched replay ran other code than the run's own commit (a fix since, such as the 4 Nov
    `$metric` default or the kg:dataset shim, that runs in v1 too): replay from that commit to compare like with like."""
    manifest = run_dir / "manifest.json"
    recorded = read_json(manifest).get("code_commit") if mismatched and manifest.is_file() else None
    from .seal import code_commit
    now = code_commit()
    if recorded is None or recorded == now:
        return {}
    return {"note": f"the run was recorded at commit {recorded}, this replay ran {now}; a fix since then can change "
                    f"{mismatched}: replay it from {recorded} (git worktree add <dir> {recorded}) to check it"}


def reexec(run_dir: Path | str, extractor: str | None = None, *, cache: Path | str | None = None,
           corpus: Path | str | None = None, out_dir: Path | str | None = None, provider: Provider | None = None,
           locator: Locator | None = None) -> Path:
    """The new run directory; its reexec.json holds the comparison."""
    run_dir = Path(run_dir)
    record = read_json(run_dir / RUN_FILE)

    def bypass(spec: Any) -> bool:
        return extractor is None or extractor in (spec.name, spec.extractor_id)

    new = execute_run((run_dir / PROTOCOL_FILE).read_bytes(),
                      Settings.from_record(record, cache=cache, corpus=corpus, run_dir=run_dir),
                      out_dir or run_dir.parent, mode="reexec", bypass=bypass, locator=locator,
                      provider=provider if provider is not None else default_provider,
                      source_run=record["run_id"], attempts=_attempts(run_dir), run_id=f"{record['run_id']}-reexec-{_stamp()}",
                      before_seal=lambda new: write_json(new / REEXEC_FILE, compare(run_dir, new, extractor)))
    return new


def _stamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _attempts(run: Path) -> dict[str, int]:
    """cache key -> the attempt of the record each call of the run used (calls.py), the names checks and the stages'
    own calls (`stage_call` events) too."""
    run_dir = RunDir(run)
    used = {cache_key(e["agent_id"], e["custom_metadata"]["task_sha256"]): e["custom_metadata"].get("attempt", 0)
            for e in run_dir.events_of("extractor_call") or [] if e["status"] != "skipped"}
    names = {c["key"]: c["attempt"] for e in run_dir.events_of("names") or [] for c in e["custom_metadata"].get("checks", [])}
    stage = {e["custom_metadata"]["key"]: e["custom_metadata"]["attempt"] for e in run_dir.events_of("stage_call") or []}
    return used | names | stage


def _calls(run: Path) -> dict[tuple[str, str, int, str], dict[str, Any]]:
    """(document, evidence type, cascade position, extractor name) -> the checked result of that call.

    Position and name, not the id: a re-execution with changed code has new ids but the same cascade."""
    out = {}
    for event in read_lines(run / EVENTS_FILE):
        if event["subtype"] == "extractor_call" and event["status"] != "skipped":   # skipped: no call was made
            meta = event["custom_metadata"]
            result = read_json(run / CALLS_DIR / f"{event['task_id']}.json")
            name = event["agent_id"].split("@", 1)[0]
            out[(meta["document"], meta["evidence_type"], meta.get("position", 0), name)] = result
    return out


def _item_key(item: dict[str, Any], known: dict[str, dict[str, Any]]) -> str:
    def fields(i: dict[str, Any]) -> Any:
        return {k: round(v, 6) if isinstance(v, float) else v for k, v in i["fields"].items()}
    links = {name: [known[t]["evidence_type"], fields(known[t])] if t in known else t
             for name, t in item.get("links", {}).items()}
    return digest([item["evidence_type"], fields(item), links])


def _spans(item: dict[str, Any]) -> Any:
    return sorted((s["role"], s["selector"]["start"], s["selector"]["end"]) for s in item["spans"])


def outcome(old: dict[str, Any], new: dict[str, Any], known_old: dict[str, Any], known_new: dict[str, Any]) -> dict[str, Any]:
    ko = {_item_key(i, known_old): i for i in old["items"]}
    kn = {_item_key(i, known_new): i for i in new["items"]}
    added, missing = sorted(set(kn) - set(ko)), sorted(set(ko) - set(kn))
    if not added and not missing:
        same = all(_spans(ko[k]) == _spans(kn[k]) for k in ko)
        result = "identical" if same else "same_items_different_spans"
    elif not missing:
        result = "items_added"
    elif not added:
        result = "items_missing"
    else:
        result = "fields_differ"
    return {"outcome": result, "added": len(added), "missing": len(missing), "items_original": len(ko),
            "items_reproduced": len(set(ko) & set(kn)), "status": [old["status"], new["status"]],
            "output_identical": old["extractor_id"] == new["extractor_id"] and _output(old) == _output(new)}


def _output(result: dict[str, Any]) -> str:
    return digest({k: v for k, v in result.items() if k != "call_id"})


def compare(old_run: Path, new_run: Path, extractor: str | None = None) -> dict[str, Any]:
    known_old = {i["item_id"]: i for i in read_lines(old_run / EVIDENCE_FILE)}
    known_new = {i["item_id"]: i for i in read_lines(new_run / EVIDENCE_FILE)}
    old, new = _calls(old_run), _calls(new_run)
    calls, summary = [], {}
    for key in sorted(set(old) | set(new)):
        doc, etype, position, name = key
        entry: dict[str, Any] = {"document": doc, "evidence_type": etype, "extractor": name, "position": position,
                                 "original_call": old[key]["call_id"] if key in old else None,
                                 "reexec_call": new[key]["call_id"] if key in new else None}
        if key in old and key in new:
            entry.update(outcome(old[key], new[key], known_old, known_new))
        else:
            entry["outcome"] = "not_in_original" if key not in old else "not_reexecuted"
        calls.append(entry)
        s = summary.setdefault(name, {"calls": 0, **dict.fromkeys(OUTCOMES, 0), "unmatched": 0, "items_original": 0,
                                      "items_reproduced": 0, "extractor_ids": []})
        ids = {r["extractor_id"] for r in (old.get(key), new.get(key)) if r}
        s["extractor_ids"] = sorted(set(s["extractor_ids"]) | ids)
        s["calls"] += 1
        if entry["outcome"] in OUTCOMES:
            s[entry["outcome"]] += 1
            s["items_original"] += entry["items_original"]
            s["items_reproduced"] += entry["items_reproduced"]
        else:
            s["unmatched"] += 1
    for s in summary.values():
        s["item_stability"] = round(s["items_reproduced"] / s["items_original"], 6) if s["items_original"] else None
    totals = Counter(c["outcome"] for c in calls)
    return {"source_run": old_run.name, "reexec_run": new_run.name, "extractor": extractor,
            "calls": calls, "summary": summary, "totals": dict(sorted(totals.items()))}
