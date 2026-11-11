"""A plan's evidence lines answered on a records graph exactly as its plan run answers them (W4 queries, W7 lines,
W4 reruns). One place holds the recipe, so the run's answer, the links review (`planrun.relink`), the answer-key split
and the off-template check (evaluation) never assemble it by hand:

- each line runs as `kg.query.run_query(store, query, params, match)`;
- `params` (`line_params`): the plan's defaults for the saved templates' structural params (the compared sides, the
  measures and their direction, the first measure as `metric`, the threshold), then the line's decisions (which win);
- the direction of a measure (`directions`): the plan's confirmed `direction` decision, else the majority of the run's
  extracted metric items of that name (`items`), else higher-is-better;
- `match`: a v2 run (Settings.plan_version) matches a query's names by `name_matcher`; a v1 run the cleaned literal only.

`PlanLines(plan, store, version=, items=)` is that recipe on one graph; `PlanLines.of_run(run_dir, store)` takes the
plan, the plan version and the extracted items a recorded run used. `write_records` / `load_records` are the run's
records graph file (records.nq, sorted N-Quads)."""
from __future__ import annotations

import json
import re
from collections import Counter
from functools import cached_property
from pathlib import Path
from typing import Any

from jsonio import sha256_hex

from .contract import Item
from .names import clean
from .plan import MAIN_RULE, Decision, Plan
from .rundir import RECORDS_FILE

__all__ = ["DEFAULT_THRESHOLD", "OTHER", "RECORDS_FILE", "PlanLines", "compare_sides", "directions", "line_params",
           "load_records", "name_matcher", "sides", "threshold", "verdict", "write_records"]

OTHER = "other"
DEFAULT_THRESHOLD = 0.01      # min_effect when the plan has no threshold decision
LIST_DECISIONS = ("must_match", "counts_as")


# --- the plan's things ----------------------------------------------------------------------------------------------

def sides(plan: Plan) -> list[str]:
    """The compared things in plan order (treatment first); [] when the plan names none."""
    return [t for t in plan.words.things if t not in plan.measures]


def compare_sides(plan: Plan) -> list[str]:
    """[treatment, control]: the first two compared things of the plan, `other` for a side the plan does not name (a
    one-method question compares the method with anything else the papers report)."""
    things = sides(plan)
    return [things[0] if things else OTHER, things[1] if len(things) > 1 else OTHER]


def directions(plan: Plan, items: dict[str, list[Item]] | None = None) -> dict[str, bool | None]:
    """{measure id: higher is better} from the plan's confirmed `direction` decisions; a measure without one takes the
    majority `higher_is_better` of the run's extracted metric items of that canonical name (`items`), else None (not
    known yet; the caller's default is higher)."""
    from .plan import DIRECTION
    out: dict[str, bool | None] = {}
    seen: dict[str, Counter[bool]] = {}
    for its in (items or {}).values():
        for it in its:
            if it.evidence_type == "metric" and isinstance(it.fields.get("higher_is_better"), bool):
                seen.setdefault(str(it.fields.get("canonical")), Counter())[it.fields["higher_is_better"]] += 1
    for m in plan.measures:
        d = next((x for x in plan.decisions if x.type == DIRECTION and x.id == f"{DIRECTION}:{m}" and x.confirmed_by), None)
        if d is not None and str(d.value).strip().lower() in ("higher", "lower"):
            out[m] = str(d.value).strip().lower() == "higher"
        elif m in seen:
            top = seen[m].most_common()
            out[m] = top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else None
        else:
            out[m] = None
    return out


def value_of(raw: Any) -> Any:
    """A decision's value as written: JSON when it parses, else the text."""
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def threshold(plan: Plan) -> float:
    d = next((x for x in plan.decisions if x.type == "threshold"), None)
    value = value_of(d.value) if d is not None else None
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else DEFAULT_THRESHOLD


# --- one line's parameters and names --------------------------------------------------------------------------------

def line_params(plan: Plan, query: str, better: dict[str, bool | None] | None = None) -> dict[str, Any]:
    """The parameters a line runs with: the plan's defaults for the saved templates' structural params (the compared
    sides, the measures and their direction, the first measure as `metric`, the threshold), then the decisions' values
    (W7 `decision_params`, which win). A must-match or counts-as value given as text is one list entry. `better`: each
    measure's direction (`directions`; default the plan's, a measure with none counts as higher-is-better)."""
    from .planner import decision_params
    measures = list(plan.measures)
    better = better if better is not None else directions(plan)
    base: dict[str, Any] = {"sides": compare_sides(plan), "metrics": measures,
                            "higher_is_better": {m: better.get(m) is not False for m in measures},
                            "min_effect": threshold(plan), "threshold": threshold(plan)}
    if measures:
        base["metric"] = measures[0]   # the main measure: a saved template on one metric (rank, best) asks for it
    given = decision_params(plan, query)
    for name, value in list(given.items()):
        if name in ("must_match", "counts_as", "metrics") and isinstance(value, str):
            given[name] = [v.strip() for v in value.split(",") if v.strip()]
    return {**base, **given}


_BRACKET = re.compile(r"^(.*?)\s*\(\s*(.*?)\s*\)\s*$")
_KEYS = ("SELECT DISTINCT ?k WHERE { ?s ?p ?k FILTER(isLiteral(?k) && (?p = kg:contextKey || "
         "STRSTARTS(STR(?p), STR(kg:key_))))}")


def _acronym(outer: str, inner: str) -> bool:
    """`inner` is a short form of `outer`: one word whose letters are initials of outer's words, in order ("mrda" of
    "icsi meeting recorder dialog act corpu", "ner" of "named entity recognition"; not "large" of "bert")."""
    letters = [w[0] for w in outer.split() if w]
    if " " in inner or len(inner) < 2 or not inner.isalnum():
        return False
    it = iter(letters)
    return all(c in it for c in inner)


def _forms(name: str) -> set[str]:
    """A cleaned name and, for "a (b)" where b is a's short form, "a" and "b" (a bracket modifier such as
    "bert (large)" stays one name)."""
    m = _BRACKET.match(name)
    return {name, *m.groups()} if m and all(m.groups()) and _acronym(*m.groups()) else {name}


def name_matcher(plan: Plan, store: Any) -> Any:
    """`kg.query.Matcher` of a v2 plan run: a key literal also matches its short-form parts, the names the word list
    gives the one thing it names (a name two things share is left out; two things named: no widening), and every key
    in the graph whose own form or short-form part is one of them ("ICSI ... Corpus (MRDA)" matches "mrda"; "named
    entity recognition" matches "named entity recognition ( ner )"). No partial-word matching, no chaining."""
    from .kg.query import run_query
    groups = [{clean(n) for n in (t, *names)} for t, names in plan.words.things.items()]
    shared = {n for n, c in Counter(n for g in groups for n in g).items() if c > 1}
    keys = [str(r["k"]) for r in run_query(store, _KEYS).rows]

    def match(literal: str) -> list[str]:
        want = _forms(literal)
        named = [g for g in groups if g & want]
        if len(named) == 1:
            want |= named[0] - shared
        want |= {k for k in keys if _forms(k) & want}
        return [literal, *sorted(want - {literal})]
    return match


# --- reruns (W4 sensitivity) ------------------------------------------------------------------------------------------

def _param_of(query: str, d: Decision) -> str:
    from .planner.plan import decision_map
    return decision_map(query).get(d.type, d.type)


def _rerun_decisions(plan: Plan, query: str) -> list[Decision]:
    """The decisions this line uses (their parameter is in its query), the main-answer rule and include left out,
    each value parsed (a number, or a list for must-match / counts-as)."""
    from .planner import decision_params
    used = decision_params(plan, query)
    out = []
    for d in plan.decisions:
        if d.type in (MAIN_RULE, "include", "direction") or d.id == MAIN_RULE:
            continue
        value = value_of(d.value)
        if d.type in LIST_DECISIONS:
            value = value if isinstance(value, list) else [v.strip() for v in str(value).split(",") if v.strip()]
        elif d.type == "threshold" and not isinstance(value, (int, float)):
            continue
        if _param_of(query, d) in used:
            out.append(d.model_copy(update={"value": value}))
    return out


def verdict(answer: Any) -> Any:
    """What a line's answer says, for its reruns (W4 `Verdict`): rows with a `direction` (the effect template) by the
    majority direction of the determined papers (n = those papers, size = the majority's share); `kind, thing, count`
    rows (the best template) by each unit's winner; any other line by its top row (W4's default)."""
    from .kg import sensitivity
    rows = answer.rows
    if rows and all("direction" in r for r in rows):
        found = [r["direction"] for r in rows if r["direction"] != "undetermined"]
        if not found:
            return sensitivity.Verdict("none", 0)
        top = Counter(found).most_common()
        label = top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else "mixed"
        return sensitivity.Verdict(label, len(found), top[0][1] / len(found))
    if rows and all({"kind", "thing", "count"} <= set(r) for r in rows):
        return sensitivity.winners_verdict(answer)
    return sensitivity.default_verdict(answer)


# --- the lines of one run ---------------------------------------------------------------------------------------------

class PlanLines:
    """A plan's lines on one records graph (`store`), answered as a plan run of `version` answers them; `items` are
    the run's extracted items (a measure without a direction decision takes their direction; None: the plan's own)."""

    def __init__(self, plan: Plan, store: Any, *, version: str = "v1",
                 items: dict[str, list[Item]] | None = None) -> None:
        self.plan, self.store, self.version = plan, store, version
        self.better = directions(plan, items)

    @classmethod
    def of_run(cls, run_dir: Path | str, store: Any, *, plan: Plan | None = None,
               items: dict[str, list[Item]] | None = None) -> PlanLines:
        """The lines as the recorded run in `run_dir` answered them, on `store`: its plan (plan.json unless given) and
        its plan version (run.json settings; a run that records none, or has no run.json, is v1)."""
        from .plan import load_plan
        from .rundir import PLAN_FILE, RunDir
        run_dir = Path(run_dir)
        settings = RunDir(run_dir).settings
        version = settings.plan_version if settings is not None else "v1"
        return cls(plan if plan is not None else load_plan(run_dir / PLAN_FILE), store, version=version, items=items)

    @cached_property
    def match(self) -> Any:
        """The name matcher of the run's version (None for v1), built once from the graph's keys."""
        return name_matcher(self.plan, self.store) if self.version == "v2" else None

    def params(self, query: str) -> dict[str, Any]:
        return line_params(self.plan, query, self.better)

    def query(self, query: str, **override: Any) -> Any:
        """One line's query on the graph (a `kg.query.Answer`); `override` replaces some of its params (the
        off-template check names the compared sides as the answer key does)."""
        from .kg.query import run_query
        return run_query(self.store, query, {**self.params(query), **override}, self.match)

    def answer(self) -> dict[str, Any]:
        """{lines, answer, labels, reruns}: every line in its own try block with the main answer (W7 `run_lines`; v2
        names a rank line's best thing in the answer text), then each line's reruns and their labels."""
        from .planner.lines import run_lines
        result = run_lines(self.plan, lambda query, _params: self.query(query).rows, name_best=self.version == "v2")
        labels, rows = self.reruns()
        return {**result, "labels": labels, "reruns": rows}

    def reruns(self) -> tuple[dict[str, str], list[dict[str, Any]]]:
        """({line id: label}, every rerun row) of the lines that ran: each decision the line uses changed one at a
        time (W4 sensitivity). A line whose rerun fails gets the label "failed: <reason>"."""
        from .kg import sensitivity
        labels: dict[str, str] = {}
        rows: list[dict[str, Any]] = []
        for line in self.plan.lines:
            if not line.query.strip():
                continue
            try:
                plain = line.model_copy(update={"template": None})   # the plan's own query, its decisions as $params
                decisions = _rerun_decisions(self.plan, line.query)
                names = {d.id: _param_of(line.query, d) for d in decisions}
                result = sensitivity.rerun(self.store, plain, decisions, params=self.params(line.query),
                                           param_of=names, verdict=verdict, match=self.match)
                labels[line.id] = sensitivity.label(result)
                rows += [{"line": line.id, "decision": r.decision, "field": r.field,
                          "setting": f"{r.decision} {r.setting}", "strictness": r.setting, "value": r.value,
                          "verdict": r.verdict.label, "n": r.verdict.n, "flips": r.flips} for r in result.runs]
            except Exception as exc:   # noqa: BLE001 - one line's rerun failing stays with that line
                labels[line.id] = f"failed: {str(exc)[:200] or type(exc).__name__}"
        return labels, rows


# --- the records graph file -------------------------------------------------------------------------------------------

def write_records(run_dir: Path, nquads: bytes) -> str:
    """Write the run's records graph (records.nq); returns its sha256 (the run.json output hash)."""
    (Path(run_dir) / RECORDS_FILE).write_bytes(nquads)
    return sha256_hex(nquads)


def load_records(run_dir: Path | str) -> Any:
    """A run's records graph (records.nq) as a pyoxigraph Store; None when the run wrote none."""
    path = Path(run_dir) / RECORDS_FILE
    if not path.is_file():
        return None
    import pyoxigraph as ox
    store = ox.Store()
    store.load(path.read_bytes(), format=ox.RdfFormat.N_QUADS)
    return store
