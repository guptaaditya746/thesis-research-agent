"""Numbers of the world, made and checked by code (22 Nov 2026). The model never invents a number.

Why: the 40-paper pilot papers had no numbers at all, and the writer filled the gaps with invented details that
contradicted each other across papers (outside review). Now every number lives in the world, once, so every paper
that mentions it uses the same value.

  entity numbers  per entity, from the pack's "kinds".<kind>."numbers" specs, e.g. a trial's patients and follow-up
                  ({"int": [lo, hi]}, {"float": [lo, hi], "decimals": d}, {"choice": [...]},
                  {"int_from": <range key in packs/topics/ranges.json>, "lo": "p25", "hi": "p90"}; "round": n)
  fact numbers    per planted fact whose relation has "effect": better | none | worse, from the pack's "effect" spec:
                  an estimate with a 95% CI that agrees with the relation (a benefit's CI excludes the null; no
                  effect's CI contains it). scale "ratio" (e.g. a hazard ratio; null 1) or "difference" (e.g.
                  accuracy points; null 0; with a baseline "base" when given).
  pooled          per paper and object: inverse-variance pooled estimate over the paper's studies of that object,
                  with Cochran's Q and I^2 (computed here, never by the writer).

w["numbers"] = {"entities": {eid: {attr: value}}, "facts": {fact_id: {...}}}.
"""
from __future__ import annotations

import math
import random
from typing import Any

from paperfactory import topics
from paperfactory.packs import Field

Z = 1.959964


def fact_id(s: str, r: str, o: str) -> str:
    return f"{s}-{r}-{o}"


def _rnd(x: float, d: int) -> float:
    return round(x + 0.0, d)


def _value(spec: dict[str, Any], rng: random.Random, ranges: dict[str, Any]) -> Any:
    if "choice" in spec:
        return rng.choice(spec["choice"])
    if "int_from" in spec:
        r = ranges.get(spec["int_from"])
        if not r:
            raise ValueError(f"number range {spec['int_from']!r} missing: run `paperfactory fetch-topics`")
        lo, hi = r[spec.get("lo", "p25")], r[spec.get("hi", "p90")]
        v = int(math.exp(rng.uniform(math.log(max(lo, 1)), math.log(max(hi, lo + 1)))))
    elif "int" in spec:
        v = rng.randint(*spec["int"])
    elif "float" in spec:
        return _rnd(rng.uniform(*spec["float"]), spec.get("decimals", 1))
    else:
        raise ValueError(f"unknown number spec {spec}")
    n = spec.get("round", 1)
    return max(n, int(round(v / n)) * n) if n > 1 else v


def effect_numbers(eff: dict[str, Any], direction: str, rng: random.Random) -> dict[str, Any]:
    """One estimate with a 95% CI that agrees with `direction` (better | none | worse)."""
    d = eff.get("decimals", 2)
    lo, hi = eff[direction]
    for _ in range(200):
        est = rng.uniform(lo, hi)
        if eff["scale"] == "ratio":
            se = math.log(1 + rng.uniform(*eff["ci_rel"]))
            cl, ch = _rnd(math.exp(math.log(est) - Z * se), d), _rnd(math.exp(math.log(est) + Z * se), d)
            null = 1.0
        else:
            half = rng.uniform(*eff["ci_half"])
            cl, ch = _rnd(est - half, d), _rnd(est + half, d)
            null = 0.0
        est = _rnd(est, d)
        if _agrees(eff, direction, est, cl, ch, null):
            out = {"estimate": est, "ci_low": cl, "ci_high": ch}
            if eff["scale"] == "difference" and "base" in eff:
                base = _rnd(rng.uniform(*eff["base"]), d)
                out |= {"baseline": base, "with": _rnd(base + est, d)}
            return out
    raise ValueError(f"no estimate agrees with direction {direction} for effect {eff.get('name')}")


def _agrees(eff: dict[str, Any], direction: str, est: float, cl: float, ch: float, null: float) -> bool:
    better_low = eff.get("better_side", "higher") == "lower"
    if not cl < est < ch:
        return False
    if direction == "none":
        return cl < null < ch
    good = ch < null if better_low else cl > null
    bad = cl > null if better_low else ch < null
    return good if direction == "better" else bad


def make(w: dict[str, Any], f: Field, seed: Any) -> dict[str, Any]:
    rng, ranges = random.Random(f"{seed}:numbers:{f.name}"), topics.ranges()
    ents: dict[str, dict[str, Any]] = {}
    for eid in sorted(w["entities"]):
        spec = f.kinds[w["entities"][eid]["kind"]].get("numbers", {})
        if spec:
            ents[eid] = {a: _value(sp, rng, ranges) for a, sp in spec.items()}
    facts: dict[str, dict[str, Any]] = {}
    eff = f.raw.get("effect")
    for pid in sorted(w["papers"]):
        p = w["papers"][pid]
        for s, r, o in p["claims"] + p["decoys"]:
            k = fact_id(s, r, o)
            direction = f.relations[r].get("effect")
            if eff and direction and k not in facts:
                facts[k] = effect_numbers(eff, direction, rng)
    return {"entities": ents, "facts": facts}


def errors(w: dict[str, Any], f: Field) -> list[str]:
    """Every fact with an effect relation has numbers that agree with it; every entity has its pack numbers."""
    nums, eff, err = w.get("numbers"), f.raw.get("effect"), []
    if nums is None:
        return ["world has no numbers"] if eff or any(k.get("numbers") for k in f.kinds.values()) else []
    for eid, e in w["entities"].items():
        want = set(f.kinds[e["kind"]].get("numbers", {}))
        if want - set(nums["entities"].get(eid, {})):
            err.append(f"{eid}: numbers missing {sorted(want - set(nums['entities'].get(eid, {})))}")
    for p in w["papers"].values():
        for s, r, o in p["claims"] + p["decoys"]:
            direction = f.relations[r].get("effect")
            if not (eff and direction):
                continue
            x = nums["facts"].get(fact_id(s, r, o))
            null = 1.0 if eff["scale"] == "ratio" else 0.0
            if x is None:
                err.append(f"{fact_id(s, r, o)}: no numbers")
            elif not _agrees(eff, direction, x["estimate"], x["ci_low"], x["ci_high"], null):
                err.append(f"{fact_id(s, r, o)}: estimate {x['estimate']} ({x['ci_low']}, {x['ci_high']}) does not "
                           f"agree with {r}")
    return err


def pooled(rows: list[dict[str, Any]], eff: dict[str, Any]) -> dict[str, Any]:
    """Inverse-variance fixed-effect pool of estimates with 95% CIs (log scale for ratios), Cochran's Q and I^2 (%).
    rows: [{"estimate", "ci_low", "ci_high"}], at least 2."""
    d = eff.get("decimals", 2)
    ratio = eff["scale"] == "ratio"
    tf = math.log if ratio else (lambda x: x)
    ys, ws = [], []
    for x in rows:
        se = (tf(x["ci_high"]) - tf(x["ci_low"])) / (2 * Z)
        ys.append(tf(x["estimate"]))
        ws.append(1 / max(se, 1e-9) ** 2)
    m = sum(w_ * y for w_, y in zip(ws, ys)) / sum(ws)
    se = math.sqrt(1 / sum(ws))
    q = sum(w_ * (y - m) ** 2 for w_, y in zip(ws, ys))
    i2 = max(0.0, (q - (len(ys) - 1)) / q) * 100 if q > 0 else 0.0
    back = math.exp if ratio else (lambda x: x)
    return {"estimate": _rnd(back(m), d), "ci_low": _rnd(back(m - Z * se), d), "ci_high": _rnd(back(m + Z * se), d),
            "studies": len(ys), "q": _rnd(q, 2), "i2": _rnd(i2, 1)}
