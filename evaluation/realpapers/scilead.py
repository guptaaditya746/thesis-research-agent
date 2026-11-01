"""SciLead real-paper check (D42, spec 6.12): do the engine's measured values, on real ML papers, find the curated
results and rank the papers of each leaderboard as the gold does (Şahinuç et al., EMNLP 2024; 43 hand-checked papers,
295 (task, dataset, metric, result) tuples, 27 leaderboards).

Source: SOURCES (the ACL Anthology attachment; the authors' README points to TUdatalib). Layout, as the authors' code
reads it (github.com/UKPLab/leaderboard-generation: tdm_eval.py, leaderboard_eval.py; checked without a download):
  tdm_annotations.json  {paper: {"TDMs": [{"Task", "Dataset", "Metric", "Result"}], ...}}
  leaderboards.json     [{"Task", "Dataset", "Metric", "Leaderboard": {paper: score}}]
The release records no direction and no scale: both come from domains/ml/metrics.yaml (data, not code, D35).
Papers are downloaded "via links provided in the dataset" (README); the link's key is not confirmed, so a paper's
arXiv id is taken from any string of its entry that is an arxiv.org link, else from its key when the key is an
arXiv id (".pdf" dropped). A paper with neither cannot be fetched and is listed as not fetched. `_release` is the
one reader of the layout; the live step confirms the link key and the counts (43, 295, 27).

The gold (read by this scorer only, D31): each paper's tuples, and per leaderboard the ranking of its `Leaderboard`
map in the metric's direction.

`score`:
  values   per gold tuple of a fetched paper: found when a measured-value item of that paper has the gold result in
           the gold's own printed scale, within half a unit of the gold's last printed digit ("90.5" -> 0.05);
           for a percent-scale metric the item's value x100 or /100 counts too (0.905 matches "90.5"). Linked when
           such an item links to a metric item whose cleaned name equals the gold metric's or shares its name group
           (the run's names.json).
  best     per leaderboard, the engine's value of a paper is its best value (in the metric's direction) among the
           items linked to a metric and a dataset with the leaderboard's names, whether or not it equals the gold:
           the ranking is the engine's own. Percent-scale values (gold and engine) are put on the percent scale
           (a value of at most 1 x100, as the authors do); raw values are never scaled. Only the leaderboard's
           fetched papers are ranked. A match: the engine's top paper (one paper; an engine tie is no match) is one
           of the gold's top fetched papers (a gold tie accepts each). Reported as "N of L" over every leaderboard.
           `with_metric_values` counts boards where some fetched paper has a value linked to the metric alone, so
           real.md tells a dataset-naming loss from a ranking loss.
  chains   pairwise order (F39; not the plan-2 chaining kind): over every leaderboard, the pairs of fetched papers
           that both have an engine value and differ in gold value; the share the engine orders as the gold does.
The method -> value link is not scored: each SciLead result is the paper's best number, not tied to one named
method (spec 6.12).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import yaml

from evidence.arxiv import ARXIV_ID
from evidence.contract import Item
from evidence.extractors.numreader import read_numbers
from evidence.names import NameGroups, clean
from evidence.pack import DOMAINS, Role, RoleMap, load_pack
from evidence.protocol import load as load_protocol
from evidence.rundir import NAMES_FILE, PROTOCOL_FILE

from .common import items_of

SOURCES = ("https://aclanthology.org/attachments/2024.emnlp-main.453.data.zip",
           "https://tudatalib.ulb.tu-darmstadt.de/handle/tudatalib/4345")
TUPLES_FILE = "tdm_annotations.json"
BOARDS_FILE = "leaderboards.json"
PACK = "ml"
METRICS = DOMAINS / PACK / "metrics.yaml"
VALUE_FIELD = "value"      # the measured value's number (domains/ml/protocols/values.yaml)
EPSILON = 1e-9             # float noise of the tolerance test
ARXIV_LINK = re.compile(r"arxiv\.org/(?:abs|pdf|html)/([^\s?#]+?)(?:\.pdf)?/?(?:[?#\s]|$)", re.IGNORECASE)
NOTES = [
    f"source: {SOURCES[0]} (also {SOURCES[1]}); layout as the authors' code reads it (tdm_annotations.json "
    "{paper: {TDMs: [{Task, Dataset, Metric, Result}]}}, leaderboards.json [{Task, Dataset, Metric, Leaderboard: "
    "{paper: score}}]); the link key and the counts (43, 295, 27) are confirmed in the live step",
    "papers are identified by the arXiv id of an arxiv.org link in their entry, else by a key that is an arXiv id; "
    "they are fetched with `evidence fetch --ids`; a paper with neither, or one the fetch did not return, is listed "
    "under not_fetched and left out of every ranking",
    "direction and scale per metric: domains/ml/metrics.yaml (Perplexity and TER lower is better, as in the "
    "authors' code; their percent list as percent); a metric not listed is higher-is-better, raw, and counted under "
    "metrics_by_default",
    "values: found = an item of the paper has the gold result within half a unit of the gold's last printed digit, "
    "in the gold's own scale (a percent-scale metric also accepts the item's value x100 or /100)",
    "values: linked = such an item links to a metric item whose cleaned name equals the gold metric's or shares its "
    "name group (names.json; a run without names on has only the cleaned name)",
    "best: per leaderboard, the engine's value of a paper is its best value linked to the leaderboard's dataset and "
    "metric; percent-scale values are put on the percent scale (at most 1: x100), raw values never scaled; a match "
    "is the engine's single top paper among the gold's top fetched papers; with_metric_values counts boards with a "
    "value linked to the metric alone (naming loss vs ranking loss)",
    "chains: pairwise order, not the plan-2 chaining kind (F39): the share of fetched paper pairs, both with an "
    "engine value, that the engine orders as the gold does (pairs tied in the gold are left out)",
    "the method -> value link is not scored: each SciLead result is the paper's best number, not tied to one named "
    "method (spec 6.12)",
    "the gold is read by this scorer only; the engine run reads manifest.json and papers/ (D31)",
]


@dataclass(frozen=True)
class Value:
    """One measured-value item of a paper: its value as extracted and the names of its metric and dataset."""
    value: float
    metric: str | None
    dataset: str | None


@dataclass(frozen=True)
class MetricRule:
    higher: bool
    percent: bool
    listed: bool


@dataclass(frozen=True)
class Release:
    tuples: dict[str, list[tuple[str, str, str, str]]]   # paper -> (task, dataset, metric, result as printed)
    boards: list[dict[str, Any]]                         # {task, dataset, metric, scores: {paper: float}}
    arxiv: dict[str, str | None]                         # paper -> arXiv id (no version), or None


def _arxiv_base(arxiv_id: str) -> str:
    """The arXiv id without its version (2101.00001v2 -> 2101.00001)."""
    return re.sub(r"v\d+$", "", arxiv_id)


def _arxiv_key(arxiv_id: str) -> str:
    """The id as `evidence fetch` names a paper, without the version (an old-style id's `/` is `_`)."""
    return _arxiv_base(arxiv_id).replace("/", "_")


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def _arxiv_of(paper: str, entry: dict[str, Any]) -> str | None:
    """The arXiv id of a paper: of an arxiv.org link among its entry's strings (not its tuples), else its key."""
    for text in _strings({k: v for k, v in entry.items() if k != "TDMs"}):
        hit = ARXIV_LINK.search(text)
        if hit and ARXIV_ID.fullmatch(hit.group(1)):
            return _arxiv_base(hit.group(1))
    key = re.sub(r"\.pdf$", "", paper, flags=re.IGNORECASE)
    return _arxiv_base(key) if ARXIV_ID.fullmatch(key) else None


def _printed(value: Any) -> tuple[float, int] | None:
    """(the first number as printed, its decimal places) of a gold result or an item's value, read with
    `read_numbers` (a % sign and thousands commas dropped); None when there is no number."""
    text = format(value, "f") if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)
    spans = read_numbers(text)
    if not spans:
        return None
    a, b = spans[0].parts[0]
    number = text[a:b].rstrip().rstrip("%").strip().replace(",", "")
    return float(number), len(number.split(".")[1]) if "." in number else 0


def _number(value: Any) -> float | None:
    found = _printed(value)
    return found[0] if found is not None else None


def _release(data: Path) -> Release:
    """The release in `data`, checked; the one reader of its layout."""
    raw = json.loads((Path(data) / TUPLES_FILE).read_text(encoding="utf-8"))
    boards_raw = json.loads((Path(data) / BOARDS_FILE).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(boards_raw, list):
        raise ValueError(f"{TUPLES_FILE} must be an object keyed by paper and {BOARDS_FILE} a list")
    tuples: dict[str, list[tuple[str, str, str, str]]] = {}
    arxiv: dict[str, str | None] = {}
    owner: dict[str, str] = {}
    for paper, entry in raw.items():
        rows = []
        for row in entry["TDMs"]:
            missing = {"Task", "Dataset", "Metric", "Result"} - set(row)
            if missing:
                raise ValueError(f"paper {paper!r}: a tuple lacks {sorted(missing)}")
            rows.append((str(row["Task"]), str(row["Dataset"]), str(row["Metric"]), str(row["Result"])))
        tuples[paper] = rows
        found = arxiv[paper] = _arxiv_of(paper, entry)
        if found is not None:
            if _arxiv_key(found) in owner:
                raise ValueError(f"paper {paper!r}: arXiv id {found!r} belongs to {owner[_arxiv_key(found)]!r} too")
            owner[_arxiv_key(found)] = paper
    boards = []
    for board in boards_raw:
        missing = {"Task", "Dataset", "Metric", "Leaderboard"} - set(board)
        if missing:
            raise ValueError(f"a leaderboard lacks {sorted(missing)}")
        scores = {str(p): v for p, s in board["Leaderboard"].items() if (v := _number(s)) is not None}
        if not scores:
            raise ValueError(f"leaderboard {board['Task']} | {board['Dataset']} | {board['Metric']} has no score")
        boards.append({"task": str(board["Task"]), "dataset": str(board["Dataset"]), "metric": str(board["Metric"]),
                       "scores": scores})
    return Release(tuples, boards, arxiv)


def load_metrics(path: Path = METRICS) -> tuple[MetricRule, dict[str, MetricRule]]:
    """(the default rule, the rules by cleaned metric name) of a metrics table (domains/ml/metrics.yaml)."""
    table = yaml.safe_load(Path(path).read_text(encoding="utf-8"))

    def rule(spec: dict[str, Any], listed: bool) -> MetricRule:
        if spec.get("direction") not in ("higher", "lower") or spec.get("scale") not in ("percent", "raw"):
            raise ValueError(f"{path}: {spec} needs direction higher|lower and scale percent|raw")
        return MetricRule(spec["direction"] == "higher", spec["scale"] == "percent", listed)

    return rule(table["default"], False), {clean(n): rule(s, True) for n, s in (table.get("metrics") or {}).items()}


def _rule(metric: str, rules: tuple[MetricRule, dict[str, MetricRule]]) -> MetricRule:
    return rules[1].get(clean(metric), rules[0])


def matches(engine: float, gold: str, percent: bool) -> bool:
    """The item's value is the gold result: within half a unit of the gold's last printed digit, in the gold's
    printed scale; a percent-scale metric also tries the value x100 and /100."""
    printed = _printed(gold)
    if printed is None:
        return False
    g, places = printed
    tolerance = 0.5 * 10 ** -places
    candidates = [engine, engine * 100, engine / 100] if percent else [engine]
    return any(abs(c - g) <= tolerance + EPSILON for c in candidates)


def on_board_scale(value: float, percent: bool) -> float:
    """A value as the board ranks it: a percent-scale value of at most 1 on the percent scale; raw as it is."""
    return value * 100 if percent and value <= 1 else value


def ids(data: Path) -> list[str]:
    """The arXiv ids (no version) of the papers that have one, in the release's order, for `evidence fetch --ids`."""
    return [a for a in _release(data).arxiv.values() if a is not None]


def no_arxiv(data: Path) -> list[str]:
    """The papers with no arXiv id: they cannot be fetched (skipped)."""
    return [p for p, a in _release(data).arxiv.items() if a is None]


def _boards(release: Release, rules: tuple[MetricRule, dict[str, MetricRule]]) -> list[dict[str, Any]]:
    """Each leaderboard with its metric rule, its gold values on the board's scale and its ranking (best first;
    ties keep the release's order)."""
    out = []
    for board in release.boards:
        rule = _rule(board["metric"], rules)
        values = {p: on_board_scale(v, rule.percent) for p, v in board["scores"].items()}
        ranking = sorted(values, key=lambda p: -values[p] if rule.higher else values[p])
        out.append({**board, "rule": rule, "values": values, "ranking": ranking})
    return out


def gold(data: Path, metrics: Path = METRICS) -> dict[str, Any]:
    """`{"tuples": {paper: [(task, dataset, metric, result)]}, "leaderboards": [{task, dataset, metric, ranking:
    [paper, ...], higher_is_better}]}` (the ranking: best first, in the metric's direction)."""
    release = _release(data)
    boards = _boards(release, load_metrics(metrics))
    return {"tuples": release.tuples,
            "leaderboards": [{"task": b["task"], "dataset": b["dataset"], "metric": b["metric"], "ranking": b["ranking"],
                              "higher_is_better": b["rule"].higher} for b in boards]}


def _groups(run_dir: Path) -> NameGroups | None:
    path = Path(run_dir) / NAMES_FILE
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return NameGroups({k: list(v) for k, v in data.get("groups", {}).items()}, [], [])


def _same(name: str | None, wanted: str, groups: NameGroups | None) -> bool:
    """`name` is `wanted`: the same cleaned name, or the same name group of the run."""
    if name is None:
        return False
    if clean(name) == clean(wanted):
        return True
    if groups is None:
        return False
    group = groups.group_of(name)
    return group is not None and group == groups.group_of(wanted)


def _dataset_type(run_dir: Path, roles: RoleMap, value_type: str) -> str:
    """The context type the run's measured value links to (the dataset; the ml pack's other context type, the
    task, is not linked by values.yaml)."""
    spec = load_protocol(Path(run_dir) / PROTOCOL_FILE).evidence_types[value_type]
    linked = [t for t in roles.types_of(Role.CONTEXT) if t in spec.links.values()]
    if len(linked) != 1:
        raise ValueError(f"the run's {value_type} links to {len(linked)} context types ({linked}), not exactly one")
    return linked[0]


def _values(run_dir: Path, corpus: Path, paper_of: dict[str, str]) -> dict[str, list[Value]]:
    """The run's measured values per gold paper. An item in a file the corpus does not have is refused."""
    manifest = json.loads((Path(corpus) / "manifest.json").read_text(encoding="utf-8"))
    doc_of = {p["file"]: str(p["id"]) for p in manifest["papers"]}
    roles = RoleMap(load_pack(PACK))
    value_type, metric_type = roles.type_of(Role.VALUE), roles.type_of(Role.METRIC)
    items = items_of(run_dir)
    dataset_type = _dataset_type(run_dir, roles, value_type)
    by_id = {i.item_id: i for i in items}

    def name_of(item: Item) -> str | None:
        field = roles.field_or_none(item.evidence_type, "name")
        value = item.fields.get(field) if field else None
        return str(value) if value is not None and str(value).strip() else None

    out: dict[str, list[Value]] = {}
    for item in items:
        if item.evidence_type != value_type:
            continue
        file = str(item.spans[0].selector.get("file", ""))
        doc = doc_of.get(file) or doc_of.get(f"papers/{Path(file).name}")
        if doc is None:   # a run of another corpus: refuse rather than score it against the wrong gold
            raise ValueError(f"item {item.item_id} is in {file!r}, no paper of {corpus}")
        paper = paper_of.get(_arxiv_key(doc))
        value = _number(item.fields.get(VALUE_FIELD))
        if paper is None or value is None:
            continue
        linked = [i for t in item.links.values() if (i := by_id.get(t)) is not None]
        metric = next((name_of(i) for i in linked if i.evidence_type == metric_type), None)
        dataset = next((name_of(i) for i in linked if i.evidence_type == dataset_type), None)
        out.setdefault(paper, []).append(Value(value, metric, dataset))
    return out


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def _best(values: list[float], higher: bool) -> float:
    return max(values) if higher else min(values)


def score(run_dir: Path, corpus: Path, data: Path, metrics: Path = METRICS) -> dict[str, Any]:
    """Values found and linked, "best" per leaderboard and pairwise order (module docstring)."""
    release, rules = _release(data), load_metrics(metrics)
    boards = _boards(release, rules)
    manifest = json.loads((Path(corpus) / "manifest.json").read_text(encoding="utf-8"))
    in_corpus = {_arxiv_key(str(p["id"])) for p in manifest["papers"]}
    paper_of = {_arxiv_key(a): p for p, a in release.arxiv.items() if a is not None}
    fetched = {paper for key, paper in paper_of.items() if key in in_corpus}
    groups = _groups(run_dir)
    found_values = _values(run_dir, corpus, paper_of)

    tuples = in_scope = found = linked = 0
    for paper, rows in release.tuples.items():
        for _, _, metric, result in rows:
            tuples += 1
            if paper not in fetched:
                continue
            in_scope += 1
            percent = _rule(metric, rules).percent
            hits = [v for v in found_values.get(paper, []) if matches(v.value, result, percent)]
            found += bool(hits)
            linked += any(_same(v.metric, metric, groups) for v in hits)

    per_board: dict[str, dict[str, Any]] = {}
    matched = with_values = with_metric = top_not_fetched = pairs = agree = 0
    for board in boards:
        rule = board["rule"]
        ranking = [p for p in board["ranking"] if p in fetched]
        engine: dict[str, float] = {}
        metric_only = False
        for paper in ranking:
            on_metric = [v for v in found_values.get(paper, []) if _same(v.metric, board["metric"], groups)]
            metric_only |= bool(on_metric)
            mine = [on_board_scale(v.value, rule.percent) for v in on_metric if _same(v.dataset, board["dataset"], groups)]
            if mine:
                engine[paper] = _best(mine, rule.higher)
        top = None
        if engine:
            tops = [p for p, v in engine.items() if v == _best(list(engine.values()), rule.higher)]
            top = tops[0] if len(tops) == 1 else None
        gold_tops = [p for p in ranking if board["values"][p] == board["values"][ranking[0]]] if ranking else []
        match = top is not None and top in gold_tops
        board_pairs = board_agree = 0
        for a, b in combinations(ranking, 2):
            ga, gb = board["values"][a], board["values"][b]
            if a not in engine or b not in engine or ga == gb:
                continue
            board_pairs += 1
            board_agree += (ga - gb) * (engine[a] - engine[b]) > 0   # the same order, whichever the direction
        matched += match
        with_values += bool(engine)
        with_metric += metric_only
        top_not_fetched += board["ranking"][0] not in fetched
        pairs += board_pairs
        agree += board_agree
        per_board[f"{board['task']} | {board['dataset']} | {board['metric']}"] = {
            "papers": len(board["ranking"]), "fetched": len(ranking), "higher_is_better": rule.higher,
            "scale": "percent" if rule.percent else "raw", "gold_top": board["ranking"][0],
            "gold_top_fetched": board["ranking"][0] in fetched, "engine_top": top, "match": match,
            "pairs": board_pairs, "agree": board_agree, "engine_values": engine}

    unknown = sorted({b["metric"] for b in boards if not b["rule"].listed})
    return {
        "papers": len(release.tuples), "fetched": len(fetched),
        "not_fetched": {"no_arxiv_id": [p for p, a in release.arxiv.items() if a is None],
                        "not_in_corpus": [p for p, a in release.arxiv.items() if a is not None and p not in fetched]},
        "values": {"tuples": tuples, "in_corpus": in_scope, "found": found, "linked": linked,
                   "found_share": _ratio(found, in_scope), "linked_share": _ratio(linked, in_scope)},
        "best": {"leaderboards": len(boards), "with_values": with_values, "with_metric_values": with_metric,
                 "matched": matched, "gold_top_not_fetched": top_not_fetched, "report": f"{matched} of {len(boards)}"},
        "chains": {"pairs": pairs, "agree": agree, "agree_share": _ratio(agree, pairs)},
        "metrics_by_default": {"count": len(unknown), "metrics": unknown},
        "leaderboards": per_board,
    }


def report(run_dir: Path, corpus: Path, data: Path, metrics: Path = METRICS) -> dict[str, Any]:
    """The real.json of the check: `score`, the run, the sources and the notes (real.md lists them)."""
    return {"run": Path(run_dir).name, "sources": list(SOURCES), **score(run_dir, corpus, data, metrics),
            "notes": list(NOTES)}
