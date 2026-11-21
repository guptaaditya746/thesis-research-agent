"""The generator section of a blueprint, read in one place, so seed/*.py holds no domain words.

A blueprint declares its domain: items, contexts, factors, measures, papers, and a `generator:` section with the slot
names of the seed schema's result settings (context, factor, time), units and cell formats, the effect model, the
intent cards, hand-written questions and the bench templates. The two frozen medical blueprints cannot get that
section, so theirs is in profiles/medical.yaml (picked by `applies_to`).
"""
from __future__ import annotations

import ast
import math
import operator
import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROFILES = Path(__file__).resolve().parent / "profiles"
ROLES = ("context", "factor", "time")   # the result settings of the seed schema (glue.ttl)


@lru_cache(maxsize=8)
def _profiles() -> tuple[tuple[tuple[str, ...], dict[str, Any]], ...]:
    out = []
    for f in sorted(PROFILES.glob("*.yaml")):
        p = yaml.safe_load(f.read_text(encoding="utf-8"))
        out.append((tuple(p.get("applies_to", [])), p["generator"]))
    return tuple(out)


def generator(bp: dict[str, Any]) -> dict[str, Any]:
    """The blueprint's own `generator:` section, else the profile that applies to its domain."""
    if "generator" in bp:
        return bp["generator"]
    for domains, gen in _profiles():
        if bp.get("domain") in domains:
            return gen
    raise ValueError(f"blueprint {bp.get('domain')!r} has no generator section and no profile in {PROFILES}")


def with_generator(bp: dict[str, Any]) -> dict[str, Any]:
    return bp if "generator" in bp else {**bp, "generator": generator(bp)}


def num(x: Any) -> str:
    return format(Decimal(str(x)).normalize(), "f")


class Gen:
    """Accessors over one blueprint's generator section."""

    def __init__(self, bp: dict[str, Any]):
        self.bp = bp
        self.g = generator(bp)
        self.C, self.F, self.T = (self.g[r]["slot"] for r in ROLES)
        self.default_comparator: str | None = (self.g.get("comparator") or {}).get("default")
        self.statistic: str = self.g["statistic"]

    # ----- slots
    @property
    def slots(self) -> tuple[str, ...]:
        """Every slot of a question's query, in the order gold files list them."""
        comp = ("comparator",) if self.default_comparator else ()
        return ("subject", *comp, "measure", self.C, "statistic", self.F, self.T)

    @property
    def numeric(self) -> tuple[str, str]:
        return (self.F, self.T)

    def role_of(self, slot: str) -> str | None:
        return {self.C: "context", self.F: "factor", self.T: "time"}.get(slot)

    def cell(self, slot: str, value: Any) -> str:
        role = self.role_of(slot)
        if role in ("factor", "time"):
            return self.g[role]["cell"].format(num(value))
        return str(value)

    def phrase(self, role: str, value: Any) -> str:
        return self.g[role]["phrase"].format(num(value))

    def mentioned(self, role: str, text: str, value: Any) -> bool:
        """Does `text` (lower case) state this factor or time value, as the blueprint's `mention` regex says?"""
        pat = self.g[role]["mention"].replace("{n}", re.escape(num(value)))
        return re.search(pat, text) is not None

    # ----- paper fields
    def arms(self, paper: dict[str, Any]) -> list[dict[str, Any]]:
        """[{subject key: item, factor key: [values]}] of a paper: its arms, or the one subject with its values."""
        s, f = self.g["subject"], self.g["factor"]
        return paper.get(s.get("arms_key", "arms")) or [{s["paper_key"]: paper[s["paper_key"]],
                                                          f["arm_key"]: paper[f["arm_key"]]}]

    def comparator(self, paper: dict[str, Any]) -> str | None:
        return paper.get((self.g.get("comparator") or {}).get("paper_key", "comparator"), self.default_comparator)

    # ----- labels
    def section(self, role: str) -> dict[str, Any]:
        return self.bp[self.g[role]["section"]]

    def core(self, label: str) -> str:
        pat = self.g.get("measure_core")
        m = re.fullmatch(pat, label.strip()) if pat else None
        return m.group(1) if m else label

    def verb(self, higher_is_better: bool, most: bool = False) -> str:
        return self.g["direction"]["higher" if higher_is_better else "lower"][1 if most else 0]

    # ----- effect model
    def lookup(self, path: list[Any], env: dict[str, Any]) -> Any:
        node: Any = self.bp
        for step in path:
            key = step.format(**env) if isinstance(step, str) else step
            node = node[key]
        return node

    def mean(self, env: dict[str, Any]) -> float:
        eff = self.g["effect"]
        names = {k: self.lookup(p, env) for k, p in eff.get("params", {}).items()}
        return evaluate(eff["formula"], {**env, **names})

    def noise_sd(self, env: dict[str, Any]) -> float:
        return self.lookup(self.g["effect"]["noise_sd"], env)


# ---------- a small, safe arithmetic evaluator (same operation order as the Python expression it parses)

_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow}
_FUN = {"exp": math.exp, "log": math.log, "sqrt": math.sqrt, "min": min, "max": max, "abs": abs}


@lru_cache(maxsize=64)
def _parse(formula: str) -> ast.Expression:
    return ast.parse(formula, mode="eval")


def evaluate(formula: str, env: dict[str, Any]) -> float:
    """Evaluate `formula` (numbers, names from env, + - * / **, unary -, exp/log/sqrt/min/max/abs)."""
    def ev(n: ast.AST) -> Any:
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.Name):
            if n.id not in env:
                raise ValueError(f"formula name {n.id!r} has no value")
            return env[n.id]
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            return _BIN[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else +v
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUN and not n.keywords:
            return _FUN[n.func.id](*(ev(a) for a in n.args))
        raise ValueError(f"formula part not allowed: {ast.dump(n)[:80]}")
    return ev(_parse(formula))


@lru_cache(maxsize=1)
def default_gen() -> Gen:
    """The first profile's generator: used only by helpers called without a domain (old call sites and tests)."""
    (domains, _), *_ = _profiles()
    return Gen({"domain": domains[0]})
