"""SciLead real-paper check (D42, spec 6.12): do the engine's measured values, on real ML papers, find the curated
results and rank the papers of each leaderboard as the gold does (Şahinuç et al., EMNLP 2024; 43 hand-checked papers,
295 (task, dataset, metric, result) tuples, 27 leaderboards).

Source: the ACL Anthology attachment SOURCE_URL. ASSUMED layout (no download in the build; the live step confirms it
and, if it differs, changes `_release` only): `papers.json`, a list of `{id, arxiv_id (or null), title, tdmr:
[{task, dataset, metric, result}]}`, and `leaderboards.json`, a list of `{task, dataset, metric, higher_is_better}`.
A paper is identified by its arXiv id: `ids` lists them for `evidence fetch --ids`, which names a corpus paper by
its arXiv id with a version (2101.00001v1); a paper with no arXiv id cannot be fetched and is listed as such.

The gold (`gold`, read by this scorer only, D31): each paper's tuples, and per leaderboard the ranking of its papers
by their best gold result in the leaderboard's direction (a paper with several results on it ranks by its best).

`score`:
  values   per gold tuple of a fetched paper: found when a measured-value item of that paper has the gold result's
           value within TOLERANCE after percent normalisation (both read with `read_numbers`, then a number above 1
           divided by 100: 90.5, 90.5% and 0.905 are one value); linked when such an item links to a metric item whose
           cleaned name equals the gold metric's or shares its name group (the run's names.json).
  best     per leaderboard, the engine's value of a paper is its best value (in the leaderboard's direction) among
           the items linked to a metric and a dataset with the leaderboard's names (as above), whether or not the
           value equals the gold; it need not, the ranking is the engine's own. Only the leaderboard's fetched papers
           are ranked. A match: the engine's top paper (one paper; a tie is no match) is the gold's top fetched
           paper. Reported as "N of L" over every leaderboard.
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

from evidence.arxiv import ARXIV_ID
from evidence.contract import Item
from evidence.extractors.numreader import read_numbers
from evidence.names import NameGroups, clean
from evidence.pack import Role, RoleMap, load_pack
from evidence.rundir import NAMES_FILE

from .common import items_of

SOURCE_URL = "https://aclanthology.org/2024.emnlp-main.453.data.zip"
PAPERS_FILE = "papers.json"
BOARDS_FILE = "leaderboards.json"
PACK = "ml"
DATASET_TYPE = "dataset"   # the ml pack's context type of datasets (its other context type is the task)
VALUE_FIELD = "value"      # the measured value's number (domains/ml/protocols/values.yaml)
TOLERANCE = 0.005
EPSILON = 1e-9             # float noise of the tolerance test (0.905 - 0.9 is not exactly 0.005)
NOTES = [
    f"source: {SOURCE_URL}; layout ASSUMED (papers.json, leaderboards.json; see evaluation/realpapers/scilead.py), "
    "not yet checked against the release: the live step confirms the layout and how papers are identified",
    "papers are identified by their arXiv id and fetched with `evidence fetch --ids`; a paper with no arXiv id, or "
    "one the fetch did not return, is listed under not_fetched and left out of every ranking",
    "values: found = an item of the paper has the gold value within 0.005 after percent normalisation (a number "
    "above 1 is divided by 100, so 90.5 and 0.905 are one value; a perplexity of 20.3 and 20.6 are 0.203 and 0.206)",
    "values: linked = such an item links to a metric item whose cleaned name equals the gold metric's or shares its "
    "name group (names.json; a run without names on has only the cleaned name)",
    "best: per leaderboard, the engine's value of a paper is its best value linked to the leaderboard's dataset and "
    "metric; a match is the engine's top paper == the gold's top among the fetched papers; a tie is no match",
    "chains: pairwise order, not the plan-2 chaining kind (F39): the share of fetched paper pairs, both with an "
    "engine value, that the engine orders as the gold does (pairs tied in the gold are left out)",
    "the method -> value link is not scored: each SciLead result is the paper's best number, not tied to one named "
    "method (spec 6.12)",
    "the gold is read by this scorer only; the engine run reads manifest.json and papers/ (D31)",
]


@dataclass(frozen=True)
class Value:
    """One measured-value item of a paper: its value (percent-normalised) and the names of its metric and dataset."""
    value: float
    metric: str | None
    dataset: str | None


def _release(data: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(papers, leaderboards) of the release in `data`, checked; the one reader of the assumed layout."""
    papers = json.loads((Path(data) / PAPERS_FILE).read_text(encoding="utf-8"))
    boards = json.loads((Path(data) / BOARDS_FILE).read_text(encoding="utf-8"))
    seen: set[str] = set()
    arxiv_seen: set[str] = set()
    for paper in papers:
        pid, arxiv = str(paper["id"]), paper.get("arxiv_id")
        if pid in seen:
            raise ValueError(f"paper {pid!r} occurs twice in {PAPERS_FILE}")
        seen.add(pid)
        if arxiv is not None:
            if not ARXIV_ID.fullmatch(str(arxiv)):
                raise ValueError(f"paper {pid!r}: {arxiv!r} is not an arXiv id")
            if _arxiv_key(str(arxiv)) in arxiv_seen:
                raise ValueError(f"paper {pid!r}: arXiv id {arxiv!r} belongs to another paper too")
            arxiv_seen.add(_arxiv_key(str(arxiv)))
        for row in paper["tdmr"]:
            missing = {"task", "dataset", "metric", "result"} - set(row)
            if missing:
                raise ValueError(f"paper {pid!r}: a tuple lacks {sorted(missing)}")
    for board in boards:
        if not isinstance(board.get("higher_is_better"), bool):
            raise ValueError(f"leaderboard {_key(board)!r}: higher_is_better is not true or false")
    return papers, boards


def _key(board: dict[str, Any]) -> str:
    return f"{board.get('task')} | {board.get('dataset')} | {board.get('metric')}"


def _arxiv_base(arxiv_id: str) -> str:
    """The arXiv id without its version (2101.00001v2 -> 2101.00001)."""
    return re.sub(r"v\d+$", "", arxiv_id)


def _arxiv_key(arxiv_id: str) -> str:
    """The id as `evidence fetch` names a paper, without the version (an old-style id's `/` is `_`)."""
    return _arxiv_base(arxiv_id).replace("/", "_")


def ids(data: Path) -> list[str]:
    """The arXiv ids (no version) of the papers that have one, in the release's order, for `evidence fetch --ids`."""
    papers, _ = _release(data)
    return list(dict.fromkeys(_arxiv_base(str(p["arxiv_id"])) for p in papers if p.get("arxiv_id")))


def no_arxiv(data: Path) -> list[str]:
    """The papers with no arXiv id: they cannot be fetched."""
    papers, _ = _release(data)
    return [str(p["id"]) for p in papers if not p.get("arxiv_id")]


def normalised(value: Any) -> float | None:
    """A number read with `read_numbers` (its first number), a value above 1 divided by 100 (percent
    normalisation); None when there is no number."""
    text = format(value, "f") if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)
    spans = read_numbers(text)
    if not spans:
        return None
    v = spans[0].value
    return round(v / 100, 9) if v > 1 else v


def _boards(papers: list[dict[str, Any]], boards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each leaderboard with its papers' best gold values (`values`) and the ranking they give (ties keep the
    release's paper order)."""
    out = []
    for board in boards:
        pick = max if board["higher_is_better"] else min
        values: dict[str, float] = {}
        for paper in papers:
            found = [v for row in paper["tdmr"] if (row["task"], row["dataset"], row["metric"]) ==
                     (board["task"], board["dataset"], board["metric"]) and (v := normalised(row["result"])) is not None]
            if found:
                values[str(paper["id"])] = pick(found)
        if not values:
            raise ValueError(f"leaderboard {_key(board)!r} matches no gold tuple with a number")
        ranking = sorted(values, key=lambda p: -values[p] if board["higher_is_better"] else values[p])
        out.append({"task": board["task"], "dataset": board["dataset"], "metric": board["metric"],
                    "ranking": ranking, "higher_is_better": board["higher_is_better"], "values": values})
    return out


def gold(data: Path) -> dict[str, Any]:
    """`{"tuples": {paper: [(task, dataset, metric, result)]}, "leaderboards": [{task, dataset, metric, ranking:
    [paper, ...], higher_is_better}]}` (the ranking: best gold result first, in the leaderboard's direction)."""
    papers, boards = _release(data)
    tuples = {str(p["id"]): [(r["task"], r["dataset"], r["metric"], str(r["result"])) for r in p["tdmr"]]
              for p in papers}
    return {"tuples": tuples,
            "leaderboards": [{k: b[k] for k in ("task", "dataset", "metric", "ranking", "higher_is_better")}
                             for b in _boards(papers, boards)]}


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


def _values(run_dir: Path, corpus: Path, paper_of: dict[str, str]) -> dict[str, list[Value]]:
    """The run's measured values per gold paper. An item in a file the corpus does not have is refused."""
    manifest = json.loads((Path(corpus) / "manifest.json").read_text(encoding="utf-8"))
    doc_of = {p["file"]: str(p["id"]) for p in manifest["papers"]}
    roles = RoleMap(load_pack(PACK))
    value_type, metric_type = roles.type_of(Role.VALUE), roles.type_of(Role.METRIC)
    items = items_of(run_dir)
    by_id = {i.item_id: i for i in items}

    def name_of(item: Item | None) -> str | None:
        if item is None:
            return None
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
        value = normalised(item.fields.get(VALUE_FIELD))
        if paper is None or value is None:
            continue
        linked = [by_id.get(t) for t in item.links.values()]
        metric = next((name_of(i) for i in linked if i is not None and i.evidence_type == metric_type), None)
        dataset = next((name_of(i) for i in linked if i is not None and i.evidence_type == DATASET_TYPE), None)
        out.setdefault(paper, []).append(Value(value, metric, dataset))
    return out


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def score(run_dir: Path, corpus: Path, data: Path) -> dict[str, Any]:
    """Values found and linked, "best" per leaderboard and pairwise order (module docstring)."""
    papers, boards = _release(data)
    manifest = json.loads((Path(corpus) / "manifest.json").read_text(encoding="utf-8"))
    in_corpus = {_arxiv_key(str(p["id"])) for p in manifest["papers"]}
    paper_of = {_arxiv_key(str(p["arxiv_id"])): str(p["id"]) for p in papers if p.get("arxiv_id")}
    fetched = {paper for key, paper in paper_of.items() if key in in_corpus}
    groups = _groups(run_dir)
    found_values = _values(run_dir, corpus, paper_of)
    g = gold(data)

    tuples = in_scope = found = linked = 0
    for paper, rows in g["tuples"].items():
        for _, _, metric, result in rows:
            tuples += 1
            want = normalised(result)
            if paper not in fetched:
                continue
            in_scope += 1
            hits = [v for v in found_values.get(paper, []) if want is not None and abs(v.value - want) <= TOLERANCE + EPSILON]
            found += bool(hits)
            linked += any(_same(v.metric, metric, groups) for v in hits)

    per_board: dict[str, dict[str, Any]] = {}
    matched = with_values = top_not_fetched = pairs = agree = 0
    for board in _boards(papers, boards):
        higher = board["higher_is_better"]
        ranking = [p for p in board["ranking"] if p in fetched]
        engine: dict[str, float] = {}
        for paper in ranking:
            mine = [v.value for v in found_values.get(paper, []) if _same(v.metric, board["metric"], groups)
                    and _same(v.dataset, board["dataset"], groups)]
            if mine:
                engine[paper] = max(mine) if higher else min(mine)
        top = None
        if engine:
            best = max(engine.values()) if higher else min(engine.values())
            tops = [p for p, v in engine.items() if v == best]
            top = tops[0] if len(tops) == 1 else None
        match = top is not None and bool(ranking) and top == ranking[0]
        board_pairs = board_agree = 0
        for a, b in combinations(ranking, 2):
            ga, gb = board["values"][a], board["values"][b]
            if a not in engine or b not in engine or ga == gb:
                continue
            board_pairs += 1
            board_agree += (ga - gb) * (engine[a] - engine[b]) > 0   # the same order, whichever the direction
        matched += match
        with_values += bool(engine)
        top_not_fetched += board["ranking"][0] not in fetched
        pairs += board_pairs
        agree += board_agree
        per_board[_key(board)] = {"papers": len(board["ranking"]), "fetched": len(ranking),
                                  "gold_top": board["ranking"][0], "gold_top_fetched": board["ranking"][0] in fetched,
                                  "engine_top": top, "match": match, "pairs": board_pairs, "agree": board_agree,
                                  "engine_values": engine}

    return {
        "papers": len(papers), "fetched": len(fetched),
        "not_fetched": {"no_arxiv_id": [str(p["id"]) for p in papers if not p.get("arxiv_id")],
                        "not_in_corpus": [str(p["id"]) for p in papers if p.get("arxiv_id") and str(p["id"]) not in fetched]},
        "values": {"tuples": tuples, "in_corpus": in_scope, "found": found, "linked": linked,
                   "found_share": _ratio(found, in_scope), "linked_share": _ratio(linked, in_scope)},
        "best": {"leaderboards": len(boards), "with_values": with_values, "matched": matched,
                 "gold_top_not_fetched": top_not_fetched, "report": f"{matched} of {len(boards)}"},
        "chains": {"pairs": pairs, "agree": agree, "agree_share": _ratio(agree, pairs)},
        "leaderboards": per_board,
    }


def report(run_dir: Path, corpus: Path, data: Path) -> dict[str, Any]:
    """The real.json of the check: `score`, the run, the source and the notes (real.md lists them)."""
    return {"run": Path(run_dir).name, "source": SOURCE_URL, **score(run_dir, corpus, data), "notes": list(NOTES)}
