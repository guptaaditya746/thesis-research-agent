"""The query runner (W4 task 4.2): run SPARQL over the records graph and answer, with saved templates.

`run_query(store, sparql, params) -> Answer`. Before the query runs, `$name` placeholders for the params given are
filled in (a string becomes a quoted literal, a number or boolean itself, a list its items separated by spaces, so
`VALUES ?x { $counts_as }` works). Two more forms:
- a param whose name ends in `_field` (a setting key such as "dataset") is the property `ev:setting_<key>`;
- `$<name>_key` is the param `<name>` as a literal for the graph's cleaned copies (`kg:contextKey`, `kg:key_<field>`); any
  literal after those two properties, bound or written inline, is cleaned (`names.clean`) before the query runs; `$<name>_field_key` is the cleaned-copy property of the setting key `<name>_field`;
- `$must_match[?e1, ?e2]` expands to the patterns saying the two experiments have equal settings for each field of the
  `must_match` param (no param or an empty list: no constraint); `$include[?paper]` to a filter keeping the papers
  named in the `include` param (no param: no filter).
A template can name a Python step in its header comment, `# after: <name>`, for what SPARQL cannot say: it is the
function `evidence.kg.after.<name>(rows, params)`, called on the rows.

A valid query that finds nothing is not an error: the answer is `empty` and `reasons` says, for the records in the
graph that no row used, why (Review Focus 3). A malformed query raises."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

import pyoxigraph as ox

from evidence.vocab import EV

from . import after
from evidence.names import clean

from .build import KG, setting_key_property, setting_property

NO_EVIDENCE = "No evidence found"
PREFIXES = {"ev": EV, "kg": KG, "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#", "xsd": "http://www.w3.org/2001/XMLSchema#"}
TEMPLATES = "templates"
_PLACEHOLDER = re.compile(r"\$(\w+)(?:\[([^\]]*)\])?")
_AFTER = re.compile(r"^#[ \t]*after:[ \t]*(\w+)[ \t]*$", re.MULTILINE)
_PARAMS = re.compile(r"^#[ \t]*params:[ \t]*(.*)$", re.MULTILINE)
_DECISIONS = re.compile(r"^#[ \t]*decisions:[ \t]*(.*)$", re.MULTILINE)
_COMMENT = re.compile(r"^[ 	]*#.*$", re.MULTILINE)
_FREE = re.compile(r"\$\w+")


@dataclass
class Answer:
    rows: list[dict[str, Any]]
    empty: bool
    reasons: list[dict[str, Any]] = field(default_factory=list)

    @property
    def message(self) -> str:
        return NO_EVIDENCE if self.empty else ""


def template(name: str) -> str:
    """The text of the saved template `name` (evidence/kg/templates/<name>.rq)."""
    return resources.files(__package__).joinpath(TEMPLATES, f"{name}.rq").read_text(encoding="utf-8")


def templates() -> list[str]:
    return sorted(p.name[:-3] for p in resources.files(__package__).joinpath(TEMPLATES).iterdir()
                  if p.name.endswith(".rq"))


def term(value: Any) -> str:
    """A param value as SPARQL text."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return " ".join(term(v) for v in (sorted(value) if isinstance(value, (set, frozenset)) else value))
    text = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{text}"'


def _must_match(args: str, fields: list[str]) -> str:
    left, right = (a.strip() for a in args.split(","))
    return " ".join(f"{left} <{setting_property(f).value}> ?_mm{n} . {right} <{setting_property(f).value}> ?_mm{n} ."
                    for n, f in enumerate(fields))


def _include(args: str, papers: list[str]) -> str:
    return f"FILTER({args.strip()} IN ({', '.join(term(p) for p in papers)}))"


_KEY_LITERAL = re.compile(r'((?:kg:contextKey|kg:key_\w+|<[^<>\s]*[#/](?:contextKey|key_\w+)>)\s+)"((?:[^"\x5c]|\x5c.)*)"')


def _clean_keys(body: str) -> str:
    """Every literal that is the object of `kg:contextKey` or `kg:key_<field>` (written by the planner or bound from a
    param) becomes its `names.clean` form, as the graph stores it. Runs once, on the filled query."""
    def fix(m: re.Match[str]) -> str:
        raw = re.sub(r"\x5c(.)", r"\1", m.group(2))   # the SPARQL escapes of the literal undone
        return m.group(1) + term(clean(raw))
    return _KEY_LITERAL.sub(fix, body)


def declared(sparql: str) -> list[str]:
    """The parameters a template's header declares (`# params: a, b`); `$include[..]` and `$must_match[..]` are optional
    and not listed."""
    m = _PARAMS.search(sparql)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def decision_params(sparql: str) -> dict[str, str]:
    """Which parameter each decision type fills in this template (`# decisions: threshold=min_effect, ...`); a type not
    listed fills the parameter of its own name."""
    m = _DECISIONS.search(sparql)
    pairs = [x.split("=") for x in m.group(1).split(",") if "=" in x] if m else []
    return {a.strip(): b.strip() for a, b in pairs}


def render(sparql: str, params: dict[str, Any]) -> str:
    """The query with its parameters filled in. A declared parameter that is missing, or any `$name` left over (in SPARQL
    that would be a free variable matching everything), raises ValueError."""
    missing = [n for n in declared(sparql) if n not in params]
    if missing:
        raise ValueError(f"missing parameter(s) {missing} for the query (declared in its header)")
    def fill(m: re.Match[str]) -> str:
        name, args = m.group(1), m.group(2)
        if name == "must_match" and args is not None:
            return _must_match(args, list(params.get("must_match") or []))
        if name == "must_match_values" and args is not None:
            return " ".join(f"{args.strip()} <{setting_property(f).value}> ?mm{n} ."
                            for n, f in enumerate(params.get("must_match") or []))
        if name == "include" and args is not None:
            return _include(args, params["include"]) if params.get("include") is not None else ""
        if name not in params:
            if name.endswith("_field_key") and name[:-4] in params:
                return f"<{setting_key_property(str(params[name[:-4]])).value}>"
            if name.endswith("_key") and name[:-4] in params:
                return term(params[name[:-4]])   # raw: `_clean_keys` cleans it with every inline literal
            return m.group(0)
        if name.endswith("_field"):
            return f"<{setting_property(str(params[name])).value}>"
        return term(params[name])
    body = _clean_keys(_PLACEHOLDER.sub(fill, _COMMENT.sub("", sparql)))
    left = sorted(set(_FREE.findall(body)))
    if left:
        raise ValueError(f"no value for parameter(s) {left}: they would be free variables in the query")
    head = "".join(f"PREFIX {p}: <{u}>\n" for p, u in PREFIXES.items() if f"PREFIX {p}:" not in body)
    return head + body


def _python(term_: Any) -> Any:
    if term_ is None:
        return None
    if isinstance(term_, ox.NamedNode):
        return term_.value
    if isinstance(term_, ox.Literal):
        kind = term_.datatype.value.rsplit("#", 1)[-1]
        if kind in ("double", "float", "decimal"):
            return float(term_.value)
        if kind in ("integer", "int", "long"):
            return int(term_.value)
        if kind == "boolean":
            return term_.value == "true"
        return term_.value
    return str(term_)


def run_query(store: ox.Store, sparql: str, params: dict[str, Any] | None = None) -> Answer:
    params = dict(params or {})
    result = store.query(render(sparql, params))
    if isinstance(result, ox.QueryBoolean):
        rows: list[dict[str, Any]] = [{"result": bool(result)}]
    else:
        names = [v.value for v in result.variables]
        rows = [{n: _python(solution[n]) for n in names} for solution in result]
    step = _AFTER.search(sparql)
    if step is not None:
        rows = getattr(after, step.group(1))(rows, params)
    undetermined = [r for r in rows if r.get("direction") == "undetermined"]
    if rows and len(undetermined) < len(rows):
        return Answer(rows=rows, empty=False, reasons=[])
    reasons = [{"record": r.get("paper"), "kind": "paper", "reason": "no treatment and control value on a question metric"}
               for r in undetermined]
    return Answer(rows=[], empty=True, reasons=reasons + unused(store))


def run_template(store: ox.Store, name: str, params: dict[str, Any] | None = None) -> Answer:
    return run_query(store, template(name), params)


_REASONS = (
    ("value", "ev:Value", "no row of the query used this value (its thing, metric or experiment did not match)"),
    ("claim", "ev:Claim", "no row of the query used this claim (its subject, relation or settings did not match)"),
    ("link", "ev:Link", "no row of the query used this link (its relation did not match)"),
)


def unused(store: ox.Store) -> list[dict[str, Any]]:
    """The records of the graph (values, claims, links) with why none was used: an empty answer used none. A value that
    has no comparison partner, a claim with no direction and a link out of the set say so; else the generic reason."""
    out: list[dict[str, Any]] = []
    for kind, cls, generic in _REASONS:
        rows = store.query(render(f"SELECT ?r WHERE {{ ?r a {cls} }} ORDER BY ?r", {}))
        for row in rows:
            iri = row["r"].value
            out.append({"record": iri, "kind": kind, "reason": _why(store, kind, iri, generic)})
    return out


def _ask(store: ox.Store, body: str) -> bool:
    return bool(store.query(render(f"ASK {{ {body} }}", {})))


def _why(store: ox.Store, kind: str, iri: str, generic: str) -> str:
    node = f"<{iri}>"
    if kind == "value" and not _ask(store, f"{{ ?c ev:a {node} }} UNION {{ ?c ev:b {node} }}"):
        return "no other thing was measured on the same metric in its experiment, so it is in no comparison"
    if kind == "claim" and not _ask(store, f"{node} ev:direction ?d"):
        return "the claim has no direction"
    if kind == "link" and _ask(store, f"{node} ev:outsideSet true"):
        return "the link points outside the set"
    return generic
