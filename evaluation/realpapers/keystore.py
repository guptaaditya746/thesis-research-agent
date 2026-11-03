"""The answer key of a real set as a records graph (the spec's rule: the same query also runs on the answer key's
records, so a wrong answer is a synthesis error or an extraction error).

A set's `truth_items(src)` gives plain records, one per labelled value:
  {"paper": id, "thing": str, "metric": str, "number": float, "higher_is_better": bool | None,
   "context": str | None, "settings": {field: value}}
`store(records)` writes them into the same graph vocabulary as `evidence.kg.build` (paper, experiment, value, thing,
metric, comparison edges), so the saved query templates run on it. One experiment per (paper, settings); `context`
is the value's `kg:context`. `evidence.kg` is imported when `store` is called.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any

from evidence.names import clean


def store(records: list[dict[str, Any]]) -> Any:
    """A pyoxigraph Store holding `records` (see the module docstring)."""
    import pyoxigraph as ox

    from evidence.kg import build as b
    from evidence.contract import digest
    st = ox.Store()

    def add(s: Any, p: Any, o: Any) -> None:
        st.add(ox.Quad(s, p, o, ox.DefaultGraph()))

    exps: dict[Any, list[tuple[Any, Any, Any, float, bool | None]]] = {}
    papers: set[str] = set()
    directions: dict[Any, bool] = {}
    for n, r in enumerate(records):
        paper = str(r["paper"])
        pnode = b.iri("paper", paper)
        if paper not in papers:
            papers.add(paper)
            add(pnode, b.RDF_TYPE, b.ev("Paper"))
            add(pnode, b.ev("name"), b.lit(paper))
        settings = {str(k): str(v) for k, v in (r.get("settings") or {}).items()}
        label = "|".join(f"{k}={v}" for k, v in sorted(settings.items())) or "none"
        exp = b.iri("exp", paper, label)
        if exp not in exps:
            add(exp, b.RDF_TYPE, b.ev("Experiment"))
            add(exp, b.ev("inPaper"), pnode)
            add(exp, b.ev("name"), b.lit(label))
            for k, v in sorted(settings.items()):
                add(exp, b.setting_property(k), b.lit(v))
                add(exp, b.setting_key_property(k), b.lit(clean(v)))
        tnode = b.iri("thing", clean(str(r["thing"])))
        add(tnode, b.RDF_TYPE, b.ev("Thing"))
        add(tnode, b.ev("name"), b.lit(str(r["thing"])))
        mnode = b.iri("metric", str(r["metric"]))
        add(mnode, b.RDF_TYPE, b.ev("Metric"))
        add(mnode, b.ev("name"), b.lit(str(r["metric"])))
        better = r.get("higher_is_better")
        if isinstance(better, bool):
            directions.setdefault(mnode, better)
        vnode = b.iri("value", paper, str(n))
        add(vnode, b.RDF_TYPE, b.ev("Value"))
        add(vnode, b.ev("of"), tnode)
        add(vnode, b.ev("onMetric"), mnode)
        add(vnode, b.ev("number"), b.num(float(r["number"])))
        add(vnode, b.ev("inExperiment"), exp)
        if r.get("context") is not None:
            add(vnode, b.kg("context"), b.lit(str(r["context"])))
            add(vnode, b.kg("contextKey"), b.lit(clean(str(r["context"]))))
        exps.setdefault(exp, []).append((vnode, tnode, mnode, float(r["number"]), None))
    for mnode, higher in directions.items():
        add(mnode, b.kg("higherIsBetter"), b.flag(higher))
    for exp, vals in exps.items():
        ordered = sorted(vals, key=lambda v: (v[1].value, v[0].value))
        for (va, ta, ma, xa, _), (vb, tb, mb, xb, _) in combinations(ordered, 2):
            if ma != mb or ta == tb:
                continue
            node = b.iri("cmp", digest([va.value, vb.value])[:16])
            add(node, b.RDF_TYPE, b.ev("Comparison"))
            add(node, b.ev("a"), va)
            add(node, b.ev("b"), vb)
            add(node, b.ev("inExperiment"), exp)
            add(node, b.ev("delta"), b.num(round(xa - xb, 6)))
            higher = directions.get(ma)
            if higher is not None and xa != xb:
                add(node, b.ev("better"), va if (xa > xb) == higher else vb)
    return st
