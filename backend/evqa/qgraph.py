"""One question of a run as a small graph inside its piece of the seed graph (Cytoscape elements). Code only, no LLM.

    question_graph(run_dir, qid) -> {run_id, qid, domain, type, closed_book, counts, truncated, elements: {nodes, edges}}

The seed piece: the gold facts of the question (gold row_ids) and their entity nodes (drug, comparator, patient group,
dose, week, measure), each fact inside a compound node for its paper; then other seed facts of the same papers (1 hop
through the paper) as grey context, the ones sharing most entities first, until about MAX_NODES nodes.
The run on top (from eval.json, else scored now with evqa.scoring):
  found    gold fact with a matched row (L2) whose names are all right             green
  missed   gold fact without such a row                                             red
  wrong    run row that matched a gold fact's value and place but never with all names right; linked to that fact
  extra    run row (not dropped) that matched no gold fact                          orange (wrong and extra)
  context  seed fact not needed by the question, and entities only they use         grey
Row nodes link to the entities they name; an entity the seed piece lacks is added (status extra).
Node data: id, label, kind, status, value, unit, quote, start, end (offsets in paper.md; span_from row = the row's
quote, seed = the fact's L0 span, quote then is its line), paper, row, rows, fact,
blame, names, parent. It reads the seed; the pipeline may not import this module (seed wall test).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from thesis_scorer import structured

from evqa import norm
from evqa.answer import canon
from evqa.contracts import Row, RunConfig
from evqa import scoring
from evqa.paths import paper_file
from evqa.seed import brief

MAX_NODES = 60
ENTITY_KINDS = ("drug", "comparator", "group", "dose", "time", "measure")
EDGE_LABEL = {"drug": "drug", "comparator": "against", "group": "patients", "dose": "dose", "time": "week",
              "measure": "measure"}


def _symbol(iri: str | None) -> str:
    return norm.units().get(iri or "", {}).get("symbol", "") if iri else ""


def _paper_text(domain: str, paper: str, cache: dict[str, str | None]) -> str | None:
    if paper not in cache:
        p = paper_file(domain, paper)
        cache[paper] = p.read_text(encoding="utf-8") if p.is_file() else None
    return cache[paper]


class _Builder:
    def __init__(self, domain: str) -> None:
        self.domain = domain
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: dict[str, dict[str, Any]] = {}
        self.measures: dict[str, dict[str, Any]] = {}     # measure node id -> a seed fact with that measure

    # ------------------------------------------------------------ entity keys
    def fact_entities(self, f: dict[str, Any]) -> dict[str, tuple[str, str]]:
        """kind -> (node id, label) for a seed fact."""
        slots = structured.fact_slots(f)
        out = {"drug": (f"drug:{slots['subject']}", f["subject"]),
               "group": (f"group:{f['context']}", f["context"]),
               "measure": (f"measure:{f['measure']}", f["measure"])}
        if f.get("comparator"):
            out["comparator"] = (f"comparator:{f['comparator'].lower()}", f["comparator"])
        if "dose" in slots:
            out["dose"] = (f"dose:{slots['dose']}", slots["dose"])
        if "time_point" in slots:
            out["time"] = (f"time:{slots['time_point']}", slots["time_point"])
        return out

    def row_entities(self, r: Row) -> dict[str, tuple[str, str]]:
        """kind -> (node id, label) for a run row, using the seed node ids when the names mean the same."""
        out: dict[str, tuple[str, str]] = {}
        subj = structured.slot_value("subject", r.subject, None)
        if subj:
            out["drug"] = (f"drug:{subj}", r.subject)
        if r.comparator and r.comparator.strip():
            out["comparator"] = (f"comparator:{r.comparator.strip().lower()}", r.comparator)
        if r.patient_group and r.patient_group.strip():
            g = structured.slot_value("patient_group", r.patient_group, None)   # seed node only when the text
            out["group"] = (f"group:{g}", g)                                      # is the context label itself
        for kind, slot, text in (("dose", "dose", r.dose), ("time", "time_point", r.time_point)):
            if text and text.strip():
                v = canon.value(slot, text) or text.strip()
                out[kind] = (f"{kind}:{v}", v)
        if r.measure.strip():
            same = next((mid for mid, f in self.measures.items() if structured.measure_ok(r.measure, [], f)), None)
            out["measure"] = (same, self.nodes[same]["data"]["label"]) if same else (f"measure:{r.measure}", r.measure)
        return out

    # ------------------------------------------------------------ elements
    def node(self, nid: str, **data: Any) -> dict[str, Any]:
        if nid not in self.nodes:
            self.nodes[nid] = {"data": {"id": nid, **data}}
        return self.nodes[nid]["data"]

    def edge(self, source: str, target: str, label: str, status: str) -> None:
        eid = f"{source}->{target}"
        if eid not in self.edges:
            self.edges[eid] = {"data": {"id": eid, "source": source, "target": target, "label": label,
                                        "status": status}}

    def paper(self, paper: str, title: str, status: str) -> str:
        pid = f"paper:{paper}"
        d = self.node(pid, label=f"{paper}{' · ' + title if title else ''}", kind="paper", status=status,
                      paper=paper)
        if status != "context" and d["status"] == "context":
            d["status"] = status
        return pid

    def attach(self, src: str, ents: dict[str, tuple[str, str]], status: str, measure_fact: dict[str, Any] | None
               ) -> None:
        for kind in ENTITY_KINDS:
            if kind not in ents:
                continue
            nid, label = ents[kind]
            d = self.node(nid, label=label, kind=kind, status=status)
            if d["status"] == "context" and status != "context" or d["status"] == "extra" and status == "gold":
                d["status"] = status
            if kind == "measure" and measure_fact is not None:
                self.measures.setdefault(nid, measure_fact)
            self.edge(src, nid, EDGE_LABEL[kind], status)

    def new_ids(self, ents: dict[str, tuple[str, str]], paper: str) -> int:
        ids = {nid for nid, _ in ents.values()} | {f"paper:{paper}"}
        return len(ids - set(self.nodes)) + 1          # + the fact node itself


def _score(run_dir: Path, qid: str, g: dict[str, Any], domain: str) -> dict[str, Any]:
    """The question's entry of eval.json (what the Evaluation pane shows), else scored now."""
    data = None
    p = run_dir / "eval.json"
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = None
    q = (data or {}).get("questions", {}).get(qid) if isinstance(data, dict) else None
    if isinstance(q, dict) and isinstance(q.get("facts"), list):
        return q
    return scoring.score_run(run_dir, domain, only=[qid], write=False)["questions"].get(qid, {})


def question_graph(run_dir: Path, qid: str, domain: str | None = None, max_nodes: int = MAX_NODES) -> dict[str, Any]:
    """The Cytoscape elements of one question of a run (see the module text). KeyError when the seed has no gold
    answer for `qid`."""
    run_dir = Path(run_dir)
    cfg_path = run_dir / "config.yaml"
    try:
        cfg = RunConfig.load(cfg_path) if cfg_path.is_file() else RunConfig()
    except (ValueError, yaml.YAMLError):              # a broken config still draws (with the default domain)
        cfg = RunConfig()
    domain = domain or cfg.domain
    golds = scoring.gold(domain)
    if qid not in golds:
        raise KeyError(qid)
    g = golds[qid]
    facts = scoring.seed_facts(domain)
    titles = _titles(domain)
    score = _score(run_dir, qid, g, domain)
    rows: list[Row] = scoring._jsonl(run_dir / qid / "rows.jsonl", Row) or []
    texts: dict[str, str | None] = {}
    b = _Builder(domain)

    # which rows are right for some fact, which matched a fact only with wrong names
    per_fact = {f["id"]: f for f in score.get("facts", []) if isinstance(f, dict) and "id" in f}
    right_rows: set[int] = set()
    matched_by: dict[int, list[str]] = {}
    for rid, fs in per_fact.items():
        for i in fs.get("rows", []):
            matched_by.setdefault(i, []).append(rid)
            names = fs.get("names", {}).get(str(i))
            if names is None or all(names.values()):
                right_rows.add(i)

    def fact_status(rid: str) -> tuple[str, list[int]]:
        fs = per_fact.get(rid, {})
        names = fs.get("names", {})
        good = [i for i in fs.get("rows", []) if names.get(str(i)) is None or all(names[str(i)].values())]
        return ("found" if good else "missed"), good or list(fs.get("rows", []))

    def add_fact(f: dict[str, Any], status: str, matched: list[int]) -> None:
        ent_status = "context" if status == "context" else "gold"
        parent = b.paper(f["paper"], titles.get(f["paper"], ""), ent_status)
        sym = _symbol(f["unit"])
        data: dict[str, Any] = {"label": f"{f['value']} {sym}".strip(), "kind": "fact", "status": status,
                                "value": f["value"], "unit": sym, "paper": f["paper"], "fact": f["id"],
                                "parent": parent, "rows": matched, "row": matched[0] if matched else None,
                                "measure": f["measure"], "group": f["context"], "subject": f["subject"],
                                "comparator": f.get("comparator"), "dose": structured.fact_slots(f).get("dose"),
                                "week": structured.fact_slots(f).get("time_point")}
        fs = per_fact.get(f["id"])
        if fs:
            data["blame"] = fs.get("blame")
            data["in_answer"] = fs.get("in_answer")
        r = rows[matched[0]] if matched and matched[0] < len(rows) else None
        if r is not None and r.quote_start >= 0:
            data.update(quote=r.quote, start=r.quote_start, end=r.quote_end, span_from="row")
        else:
            spans = scoring.l0_spans(domain, f["paper"]).get(f["id"], ())
            if spans:
                s, e = spans[0]
                text = _paper_text(domain, f["paper"], texts)
                data.update(quote=_line(text, s, e) if text else "", start=s, end=e, span_from="seed")
        b.node(f"fact:{f['id']}", **data)
        b.attach(f"fact:{f['id']}", b.fact_entities(f), ent_status, f)

    counts = {"found": 0, "missed": 0, "wrong": 0, "extra": 0, "context": 0}
    gold_ids = [rid for rid in g.get("row_ids", []) if rid in facts]
    for rid in gold_ids:
        status, matched = fact_status(rid)
        counts[status] += 1
        add_fact(facts[rid], status, matched)

    # run rows that are not right for any gold fact
    for i, r in enumerate(rows):
        if r.dropped or i in right_rows:
            continue
        kind = "wrong" if i in matched_by else "extra"
        counts[kind] += 1
        parent = b.paper(r.paper, titles.get(r.paper, ""), "extra")
        value = r.std.value if r.std else r.raw
        unit = _symbol(r.std.unit) if r.std else r.unit_text
        nid = f"row:{i}"
        b.node(nid, label=f"{value} {unit}".strip(), kind="row", status=kind, value=value, unit=unit, paper=r.paper,
               parent=parent, row=i, rows=[i], quote=r.quote, start=r.quote_start, end=r.quote_end, span_from="row",
               subject=r.subject, comparator=r.comparator, measure=r.measure, group=r.patient_group, dose=r.dose,
               week=r.time_point, fact=matched_by.get(i, [None])[0], note=r.note,
               names={rid: per_fact[rid].get("names", {}).get(str(i)) for rid in matched_by.get(i, [])})
        b.attach(nid, b.row_entities(r), "extra", None)
        for rid in matched_by.get(i, []):
            if f"fact:{rid}" in b.nodes:
                b.edge(nid, f"fact:{rid}", "same value, wrong names", "wrong")

    # grey context: other facts of the same papers, the most connected first, until the cap
    papers = {facts[rid]["paper"] for rid in gold_ids}
    used = set(b.nodes)
    others = [f for f in facts.values() if f["paper"] in papers and f["id"] not in gold_ids]
    others.sort(key=lambda f: (-len({nid for nid, _ in b.fact_entities(f).values()} & used), f["id"]))
    truncated = 0
    for f in others:
        if len(b.nodes) + b.new_ids(b.fact_entities(f), f["paper"]) > max_nodes:
            truncated += 1
            continue
        counts["context"] += 1
        add_fact(f, "context", [])

    return {"run_id": run_dir.name, "qid": qid, "domain": domain, "type": g.get("type"),
            "closed_book": cfg.closed_book, "counts": counts,
            "truncated": truncated, "elements": {"nodes": list(b.nodes.values()), "edges": list(b.edges.values())}}


def _line(text: str, start: int, end: int) -> str:
    """The line of paper.md around a seed span (an L0 span is just the number), trimmed to about 300 characters."""
    a = text.rfind("\n", 0, start) + 1
    b = text.find("\n", end)
    line = text[a:b if b >= 0 else len(text)].strip()
    return line if len(line) <= 300 else "…" + text[max(a, start - 140):end + 140].strip() + "…"


@lru_cache(maxsize=4)
def _titles(domain: str) -> dict[str, str]:
    return {p: v["title"] for p, v in brief.paper_facts(domain).items()}
