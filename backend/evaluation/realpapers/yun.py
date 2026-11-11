"""Yun et al. 2024 + Evidence Inference 2.0 real-paper check (D42, spec 6.12): on real trial reports, do the engine's
names, values, links and directions agree with hand-made records of (intervention, comparator, outcome)?

Sources (SOURCES; the commits seen when the layout was checked are pinned there and printed in real.md):
  --repo  a checkout of github.com/hyesunyun/llm-meta-analysis (Apache-2.0): evaluation/data/annotated_rct_dataset.csv
          (one record per row: pmcid, evidence_inference_prompt_id, intervention, comparator, outcome, outcome_type
          binary|continuous, per arm events and group size or mean and standard deviation; an empty cell is a
          missing number, a thousands comma is dropped) and evaluation/data/no_attributes_markdown_files/PMC<pmcid>.md
          (the text the authors give their LLMs).
  --ei    Evidence Inference 2.0's annotations/ folder (github.com/jayded/evidence-inference, MIT): prompts_merged.csv
          (PromptID, PMCID, ...) and annotations_merged.csv (PromptID, Valid Label, Valid Reasoning, Label, ...).
          A prompt's label is the most common Label among its annotations whose Valid Label and Valid Reasoning are
          both true and whose Label is one of LABELS; a tie or no such annotation gives no label.

`to_corpus` writes manifest.json, papers/PMC<pmcid>.md (the markdown bytes as they are), the gold (GOLD_FILE, read
by `score` only, D31) and SOURCE_FILE (file hashes, commits found, counts). A record is `complete` when every number
of its kind is present (events and group size per arm, a group size above 0; or mean and SD per arm).

`score` reads the run's items and its comparisons.json (plan 2). A, B and C are reported separately:
  A_names   all records: the intervention and the comparator among the paper's compared-thing items and the outcome
            among its metric items, by equal `names.clean` or the same name group (names.json).
  A_values  complete records, per arm: a measured-value item of the paper within VALUE_ABS of events/size (binary)
            or within VALUE_REL of the mean (continuous).
  B         complete records, per arm: such an item links to a compared thing named as the arm and a metric named as
            the outcome.
  C         records with an Evidence Inference label: the first comparison of the paper (comparisons.json order) whose
            two things are the intervention and the comparator and whose metric item is named as the outcome. Its
            raw difference intervention - comparator (the outcome's value, not the "improvement" delta of
            rules.effect, since the labels speak of the outcome going up or down) gives the label by
            `direction_label`; neutral is |difference| below the run's min_effect. No such comparison: "none".
"""
from __future__ import annotations

import csv
import io
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from evidence.comparisons import name_of
from evidence.contract import Item
from evidence.names import NameGroups
from evidence.pack import Role, RoleMap
from evidence.rundir import COMPARISONS_FILE, RunDir
from jsonio import sha256_hex

from .common import (add_paper, name_groups, ratio, read_json, same_name, write_json,
                     write_manifest)

GOLD_FILE = "yun_gold.json"
SOURCE_FILE = "yun_corpus.json"
RECORDS = Path("evaluation") / "data" / "annotated_rct_dataset.csv"
PAPERS = Path("evaluation") / "data" / "no_attributes_markdown_files"
PROMPTS, ANNOTATIONS = "prompts_merged.csv", "annotations_merged.csv"
SOURCES = {
    "llm-meta-analysis": {"url": "https://github.com/hyesunyun/llm-meta-analysis", "license": "Apache-2.0",
                          "commit": "1bc768d4d098c727c9866eeff909297c38a3e84c"},
    "evidence-inference": {"url": "https://github.com/jayded/evidence-inference", "license": "MIT",
                           "commit": "a661e8c14f973398380c8865cf2f27a535aaaf6d"},
}
INCREASED, DECREASED, NO_DIFFERENCE = "significantly increased", "significantly decreased", "no significant difference"
LABELS = (INCREASED, DECREASED, NO_DIFFERENCE)
ARMS = ("intervention", "comparator")
NUMBERS = {"binary": ("events", "group_size"), "continuous": ("mean", "standard_deviation")}
VALUE_FIELD = "value"     # the measured value's number (as comparisons.py reads it)
VALUE_ABS = 0.005         # binary: |value - events/size|
VALUE_REL = 0.01          # continuous: |value - mean| / |mean|
EPSILON = 1e-9            # float noise of the tolerance tests
DECIMALS = 6              # rules.effect rounds its delta so
NOTES = [
    "records without complete numbers are scored on names and direction only",
    "complete: every number of the record's kind is present (events and group size per arm, group size above 0; or "
    "mean and standard deviation per arm)",
    "A_names (all records): intervention and comparator among the paper's compared-thing items, outcome among its "
    "metric items, by equal names.clean or the same name group (names.json)",
    f"A_values (complete records, per arm): a measured value within {VALUE_ABS} of events/size (binary) or within "
    f"{VALUE_REL:.0%} of the mean (continuous); a value written as a percent is read as a fraction by the pack",
    "B (complete records, per arm): that value links to the compared thing named as the arm and the metric named as "
    "the outcome",
    "C (records with an Evidence Inference label): the first comparison of the paper with the two arms and the "
    "outcome; intervention - comparator > 0 and not neutral -> significantly increased, < 0 -> significantly "
    "decreased, neutral (below min_effect) -> no significant difference; no comparison -> none",
    "Evidence Inference label: the most common Label of the prompt's annotations with Valid Label and Valid Reasoning "
    "true; a tie or none gives no label",
    "the gold is read by this scorer only; the engine run reads manifest.json and papers/ (D31)",
]


# --- the corpus -------------------------------------------------------------------------------------------------

def _number(cell: str | None) -> tuple[float | int | None, bool]:
    """(the cell's number, whether a non-empty cell was unreadable); an integer stays an int."""
    text = (cell or "").strip().replace(",", "")
    if not text:
        return None, False
    try:
        value = float(text)
    except ValueError:
        return None, True
    return (int(value) if value.is_integer() and "." not in text else value), False


def _true(cell: str | None) -> bool:
    return (cell or "").strip().lower() in ("true", "1")


def _csv(path: Path) -> list[dict[str, Any]]:
    return list(csv.DictReader(io.StringIO(path.read_bytes().decode("utf-8-sig"), newline="")))


def ei_labels(ei: Path) -> dict[str, str | None]:
    """Each prompt id of prompts_merged.csv -> its label (module docstring), or None."""
    prompts = {str(row["PromptID"]).strip() for row in _csv(Path(ei) / PROMPTS)}
    votes: dict[str, Counter[str]] = {p: Counter() for p in prompts}
    for row in _csv(Path(ei) / ANNOTATIONS):
        prompt, label = str(row["PromptID"]).strip(), str(row["Label"]).strip()
        if prompt in votes and _true(row["Valid Label"]) and _true(row["Valid Reasoning"]) and label in LABELS:
            votes[prompt][label] += 1
    out: dict[str, str | None] = {}
    for prompt, counted in votes.items():
        ranked = counted.most_common(2)
        out[prompt] = ranked[0][0] if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]) else None
    return out


def _record(row: dict[str, Any], labels: dict[str, str | None]) -> tuple[dict[str, Any], int]:
    """(the gold record of one CSV row, its unreadable number cells)."""
    kind = str(row["outcome_type"]).strip()
    if kind not in NUMBERS:
        raise ValueError(f"record {row['id']}: outcome_type {kind!r} is neither binary nor continuous")
    values: dict[str, Any] = {}
    unreadable = 0
    for arm in ARMS:
        for name in NUMBERS[kind]:
            values[f"{arm}_{name}"], bad = _number(row[f"{arm}_{name}"])
            unreadable += bad
    complete = all(v is not None for v in values.values()) and (
        kind != "binary" or all(values[f"{arm}_group_size"] > 0 for arm in ARMS))
    prompt = str(row["evidence_inference_prompt_id"] or "").strip()
    return {"id": str(row["id"]).strip(), "intervention": str(row["intervention"]).strip(),
            "comparator": str(row["comparator"]).strip(), "outcome": str(row["outcome"]).strip(), "kind": kind,
            "values": values if any(v is not None for v in values.values()) else None,
            "ei_label": labels.get(prompt) if prompt else None, "complete": complete}, unreadable


def _commit(checkout: Path) -> str | None:
    """The git commit checked out at `checkout`, the clone's top folder; None when `checkout` is not the top of a
    clone (a copy, or a folder inside another repository such as this one's test data)."""
    try:
        done = subprocess.run(["git", "-C", str(checkout), "rev-parse", "--show-toplevel", "HEAD"],
                              capture_output=True, text=True, timeout=30, check=False)
    except OSError:
        return None
    lines = done.stdout.split()
    if done.returncode != 0 or len(lines) != 2 or Path(lines[0]).resolve() != Path(checkout).resolve():
        return None
    return lines[1]


def to_corpus(repo: Path, ei: Path, out: Path) -> Path:
    """Write the corpus of every record's paper to `out`: manifest.json, papers/PMC<pmcid>.md, the gold (GOLD_FILE,
    `{doc: [{"id", "intervention", "comparator", "outcome", "kind", "values", "ei_label", "complete"}]}`) and
    SOURCE_FILE. A record whose paper has no markdown file is left out and counted. Returns `out`."""
    repo, ei, out = Path(repo), Path(ei), Path(out)
    raw = (repo / RECORDS).read_bytes()
    labels = ei_labels(ei)
    gold: dict[str, list[dict[str, Any]]] = {}
    no_paper: list[str] = []
    unreadable = extra_cells = no_prompt = 0
    for row in _csv(repo / RECORDS):
        extra_cells += None in row   # an unquoted comma in a notes cell: the columns read here come before it
        record, bad = _record(row, labels)
        unreadable += bad
        prompt = str(row["evidence_inference_prompt_id"] or "").strip()
        no_prompt += bool(prompt) and prompt not in labels
        doc = f"PMC{str(row['pmcid']).strip()}"
        if not (repo / PAPERS / f"{doc}.md").is_file():
            no_paper.append(record["id"])
            continue
        gold.setdefault(doc, []).append(record)
    (out / "papers").mkdir(parents=True, exist_ok=True)
    papers = [add_paper(out, doc, (repo / PAPERS / f"{doc}.md").read_bytes()) for doc in gold]
    records = [r for rs in gold.values() for r in rs]
    write_manifest(out, "yun-llm-meta-analysis", papers)
    write_json(out / GOLD_FILE, gold)
    write_json(out / SOURCE_FILE, {
        "records_file": RECORDS.as_posix(), "records_sha256": sha256_hex(raw),
        "prompts_sha256": sha256_hex((ei / PROMPTS).read_bytes()),
        "annotations_sha256": sha256_hex((ei / ANNOTATIONS).read_bytes()),
        "commits_found": {"llm-meta-analysis": _commit(repo), "evidence-inference": _commit(ei.parent)},
        "papers": len(papers), "records": len(records), "complete": sum(r["complete"] for r in records),
        "with_ei_label": sum(r["ei_label"] is not None for r in records),
        "records_without_paper": no_paper, "prompt_ids_not_in_ei": no_prompt,
        "unreadable_number_cells": unreadable, "rows_with_extra_cells": extra_cells})
    return out


# --- the score --------------------------------------------------------------------------------------------------

def direction_label(delta: float, neutral: bool) -> str:
    """The Evidence Inference label of an engine difference intervention - comparator."""
    if neutral:
        return NO_DIFFERENCE
    return INCREASED if delta > 0 else DECREASED


def value_matches(value: float, arm: dict[str, Any]) -> bool:
    """`arm` is {"kind": "binary", "events", "size"} or {"kind": "continuous", "mean"} (module docstring)."""
    if arm["kind"] == "binary":
        return abs(value - arm["events"] / arm["size"]) <= VALUE_ABS + EPSILON
    return abs(value - arm["mean"]) <= VALUE_REL * abs(arm["mean"]) + EPSILON


def _arm(record: dict[str, Any], arm: str) -> dict[str, Any]:
    v = record["values"]
    if record["kind"] == "binary":
        return {"kind": "binary", "events": v[f"{arm}_events"], "size": v[f"{arm}_group_size"]}
    return {"kind": "continuous", "mean": v[f"{arm}_mean"]}


class _Paper:
    """One paper's items by role."""

    def __init__(self, items: list[Item], roles: RoleMap) -> None:
        def typed(role: Role) -> set[str]:
            return set(roles.types_of(role))
        things, metrics, values = typed(Role.COMPARED_THING), typed(Role.METRIC), typed(Role.VALUE)
        self.roles = roles
        self.by_id = {i.item_id: i for i in items}
        self.things = [name_of(i, roles) for i in items if i.evidence_type in things]
        self.metrics = [name_of(i, roles) for i in items if i.evidence_type in metrics]
        self.thing_types, self.metric_types = things, metrics
        self.values = [i for i in items if i.evidence_type in values and _float(i.fields.get(VALUE_FIELD)) is not None]

    def linked(self, value: Item, types: set[str]) -> list[str | None]:
        return [name_of(i, self.roles) for t in value.links.values()
                if (i := self.by_id.get(t)) is not None and i.evidence_type in types]


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None and not isinstance(value, bool) else None
    except (TypeError, ValueError):
        return None


def _same_thing(shown: str, wanted: str, groups: NameGroups | None) -> bool:
    """A comparison's thing (its group name with name groups, else the name as first written) is `wanted`."""
    if groups is not None and shown in groups.groups:
        return groups.group_of(wanted) == shown
    return same_name(shown, wanted, groups)


def score(run_dir: Path, corpus: Path) -> dict[str, Any]:
    """A_names, A_values, B and C (module docstring) over the corpus's records."""
    run_dir, corpus = Path(run_dir), Path(corpus)
    gold: dict[str, list[dict[str, Any]]] = read_json(corpus / GOLD_FILE)
    built = RunDir(run_dir).try_json(COMPARISONS_FILE)
    if not isinstance(built, dict):
        raise ValueError(f"run {run_dir} has no readable {COMPARISONS_FILE} (a run made before plan 2's comparisons)")
    min_effect = built.get("min_effect")
    if min_effect is None:
        raise ValueError(f"{COMPARISONS_FILE} of run {run_dir} records no min_effect")
    run = RunDir(run_dir)
    roles, groups = run.roles(), name_groups(run_dir)
    assert roles is not None, f"run {run_dir} has no protocol.yaml"
    # a run of another corpus is refused (UnknownPaper) rather than scored against the wrong gold
    per_doc = run.papers(corpus)
    by_id = {i.item_id: i for its in per_doc.values() for i in its}
    compared: dict[str, list[dict[str, Any]]] = {}
    for c in built.get("comparisons", []):
        compared.setdefault(str(c["document"]), []).append(c)

    names = Counter()
    arms = matched = linked = 0
    c_records = c_compared = agree = 0
    by_label: dict[str, Counter[str]] = {label: Counter() for label in LABELS}
    records = [(doc, r) for doc, rs in gold.items() for r in rs]
    for doc, record in records:
        paper = _Paper(per_doc.get(doc, []), roles)
        found = {arm: any(same_name(n, record[arm], groups) for n in paper.things) for arm in ARMS}
        found["outcome"] = any(same_name(n, record["outcome"], groups) for n in paper.metrics)
        names.update(k for k, v in found.items() if v)
        names["all"] += all(found.values())
        if record["complete"]:
            for arm in ARMS:
                arms += 1
                hits = [v for v in paper.values if value_matches(_float(v.fields[VALUE_FIELD]), _arm(record, arm))]
                matched += bool(hits)
                linked += any(any(same_name(n, record[arm], groups) for n in paper.linked(v, paper.thing_types))
                              and any(same_name(n, record["outcome"], groups) for n in paper.linked(v, paper.metric_types))
                              for v in hits)
        if record["ei_label"] is not None:
            c_records += 1
            engine = _engine_label(compared.get(doc, []), record, by_id, roles, groups, float(min_effect))
            c_compared += engine is not None
            agree += engine == record["ei_label"]
            by_label[record["ei_label"]][engine or "none"] += 1

    complete = sum(r["complete"] for _, r in records)
    return {
        "records": len(records), "complete": complete, "complete_share": ratio(complete, len(records)),
        "A_names": {"records": len(records), "intervention": names["intervention"], "comparator": names["comparator"],
                    "outcome": names["outcome"], "all": names["all"], "all_share": ratio(names["all"], len(records))},
        "A_values": {"records": complete, "arms": arms, "matched": matched, "share": ratio(matched, arms)},
        "B": {"records": complete, "arms": arms, "linked": linked, "share": ratio(linked, arms),
              "linked_of_matched": ratio(linked, matched)},
        "C": {"records": c_records, "compared": c_compared, "agree": agree, "share": ratio(agree, c_records),
              "min_effect": min_effect, "by_label": {k: dict(v) for k, v in by_label.items()}},
    }


def _engine_label(comparisons: list[dict[str, Any]], record: dict[str, Any], by_id: dict[str, Item], roles: RoleMap,
                  groups: NameGroups | None, min_effect: float) -> str | None:
    """The label of the first comparison of the paper with the record's two arms and outcome; None when none."""
    metrics = set(roles.types_of(Role.METRIC))
    for c in comparisons:
        outcome = [name_of(i, roles) for x in c["items"] if (i := by_id.get(x)) is not None and i.evidence_type in metrics]
        if not any(same_name(n, record["outcome"], groups) for n in outcome):
            continue
        if _same_thing(c["a"], record["intervention"], groups) and _same_thing(c["b"], record["comparator"], groups):
            delta = c["a_value"] - c["b_value"]
        elif _same_thing(c["b"], record["intervention"], groups) and _same_thing(c["a"], record["comparator"], groups):
            delta = c["b_value"] - c["a_value"]
        else:
            continue
        delta = round(delta, DECIMALS)
        return direction_label(delta, abs(delta) < min_effect)
    return None


def report(run_dir: Path, corpus: Path) -> dict[str, Any]:
    """The real.json of the check: `score`, the run, the sources with their pinned commits, what the corpus was made
    from (SOURCE_FILE) and the notes (real.md lists them)."""
    source = read_json(Path(corpus) / SOURCE_FILE)
    return {"run": Path(run_dir).name, **score(run_dir, corpus), "sources": SOURCES, "corpus_source": source,
            "notes": list(NOTES)}


def prepare_step(repo: Path, ei: Path, out: Path) -> str:
    """`evaluate yun corpus`: write the corpus; its SOURCE_FILE is printed."""
    return json.dumps(read_json(to_corpus(repo, ei, out) / SOURCE_FILE), indent=1)


def check_step(run: Path, corpus: Path) -> dict[str, Any]:
    """`evaluate yun score`: the real.json result."""
    return report(run, corpus)
