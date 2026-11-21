"""The two input files of the paper writer (PaperOrchestra), built by code from the seed. No LLM.

For each paper of a domain, in data/dataset/<domain>/<paper-id>/:
  idea_sparse.md        the title and four short sections (PaperOrchestra's sparse idea: Problem Statement, Core
                        Hypothesis, Proposed Methodology, Expected Contribution), with no number that is not in
                        the seed (doses, weeks, the title);
  experimental_log.md   PaperOrchestra's log (1. Experimental Setup, 2. Raw Numeric Data, 3. Qualitative
                        Observations) plus 4. Reporting Rules. Section 2 lists every seed fact once, as one
                        Markdown table row: row id, subject, comparator, measure, patients, dose, week, value with all
                        its decimals and unit, statistic, where to put it. "Tables" and "Text" are two sub-parts.
The paper writer reads these; the QA system reads only paper.md.
"""
from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from evqa import norm
from evqa.paths import brief_dir
from evqa.seed.view import graph_of, local
from evqa.seed.rdf import query as locked_query

FACTS = """
PREFIX ex: <https://w3id.org/evqa/seed#>
PREFIX sosa: <http://www.w3.org/ns/sosa/>
PREFIX qudt: <http://qudt.org/schema/qudt/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?r ?p ?subject ?comparator ?m ?measure ?context ?dose ?doseUnit ?factor ?time ?timeUnit ?stat ?value ?unit
       ?placement WHERE {
  ?r a ex:Result ; ex:reportedIn ?p ; ex:subject/skos:prefLabel ?subject ; sosa:observedProperty ?m ;
     sosa:hasFeatureOfInterest/skos:prefLabel ?context ; ex:statistic/skos:prefLabel ?stat ;
     sosa:hasResult [ qudt:numericValue ?value ; qudt:unit ?unit ] ; ex:placement ?placement .
  ?m skos:prefLabel ?measure .
  OPTIONAL { ?r ex:comparator/skos:prefLabel ?comparator }
  OPTIONAL { ?r ex:condition [ ex:setting [ qudt:numericValue ?dose ; qudt:unit ?doseUnit ] ;
                               ex:factor/skos:prefLabel ?factor ] }
  OPTIONAL { ?r ex:atTime [ qudt:numericValue ?time ; qudt:unit ?timeUnit ] }
} ORDER BY ?r"""
PAPERS = """
PREFIX ex: <https://w3id.org/evqa/seed#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?p ?title ?role ?split ?kind WHERE { ?p a ex:Paper ; dcterms:title ?title ; ex:role ?role ; ex:split ?split ;
  ex:evidenceKind/skos:prefLabel ?kind } ORDER BY ?p"""
MENTIONS = """
PREFIX ex: <https://w3id.org/evqa/seed#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?p ?label ?code ?written WHERE { ?p ex:mention [ ex:item ?i ; ex:written ?written ] .
  ?i skos:prefLabel ?label ; skos:altLabel ?code }"""
STAT_WORDS = {"mean difference vs comparator": "mean difference vs {comparator}"}


def number(d: Any) -> str:
    """A seed number as text without float noise: 10.0 -> '10', 0.50 stays '0.50'."""
    s = format(Decimal(str(d)), "f")
    return s.rstrip("0").rstrip(".") if "." in s and Decimal(s) == Decimal(s).to_integral() else s


def write_as(unit: str) -> str:
    return norm.units().get(unit, {}).get("write_as", local(unit))


def written(name: str, mention: dict[str, str] | None) -> str:
    """How a paper writes an item: 'Quendarin', 'QLM-331' (code only) or 'Quelmastin (QLM-331)' (both)."""
    if mention is None or mention["written"] == "name":
        return name.capitalize()
    return mention["code"] if mention["written"] == "code" else f"{name.capitalize()} ({mention['code']})"


def paper_facts(domain: str) -> dict[str, dict[str, Any]]:
    """{paper id: {id, title, role, split, kind, names, facts: [...]}}; each fact keeps the value string exactly as
    stored (so '-0.90' keeps its zero), the unit IRI, and the measure's other names (for the L0 check).
    `names` = {item label: {written: code|both, code}} for items the paper does not write by name alone; each fact's
    `subject_as` is the subject as the paper writes it."""
    g = graph_of(domain)
    papers = {local(r.p): {"id": local(r.p), "title": str(r.title), "role": str(r.role), "split": str(r.split),
                           "kind": str(r.kind), "names": {}, "facts": []} for r in locked_query(g, PAPERS)}
    for r in locked_query(g, MENTIONS):
        papers[local(r.p)]["names"][str(r.label)] = {"written": str(r.written), "code": str(r.code)}
    alt_q = ("PREFIX skos: <http://www.w3.org/2004/02/skos/core#> "
             "SELECT ?m ?a WHERE { ?m skos:altLabel ?a }")
    alts: dict[str, list[str]] = {}
    for r in locked_query(g, alt_q):
        alts.setdefault(str(r.m), []).append(str(r.a))
    for r in locked_query(g, FACTS):
        papers[local(r.p)]["facts"].append({
            "id": local(r.r), "paper": local(r.p), "subject": str(r.subject),
            "subject_as": written(str(r.subject), papers[local(r.p)]["names"].get(str(r.subject))),
            "comparator": str(r.comparator) if r.comparator else None,
            "measure": str(r.measure), "measure_alt": sorted(alts.get(str(r.m), [])), "context": str(r.context),
            "factor": str(r.factor) if r.factor else None,
            "dose": number(r.dose.toPython()) if r.dose is not None else None,
            "dose_unit": str(r.doseUnit) if r.doseUnit else None,
            "week": number(r.time.toPython()) if r.time is not None else None,
            "time_unit": str(r.timeUnit) if r.timeUnit else None,
            "statistic": str(r.stat), "value": str(r.value), "unit": str(r.unit), "placement": str(r.placement)})
    return papers


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _uniq(xs: list[Any]) -> list[Any]:
    return list(dict.fromkeys(x for x in xs if x is not None))


def _setup(paper: dict[str, Any]) -> dict[str, Any]:
    f = paper["facts"]
    first = f[0]
    dose_unit = write_as(first["dose_unit"]) if first["dose_unit"] else ""
    subjects = _uniq([x["subject_as"] for x in f])
    doses = {s: [f"{d} {dose_unit}".strip() for d in _uniq([x["dose"] for x in f if x["subject_as"] == s])]
             for s in subjects}
    return {"subject": _join(subjects), "subjects": subjects, "doses_of": doses,
            "comparator": first["comparator"] or "no comparator",
            "context": first["context"], "measures": _uniq([x["measure"] for x in f]),
            "doses": [f"{d} {dose_unit}".strip() for d in _uniq([x["dose"] for x in f])],
            "weeks": _uniq([x["week"] for x in f]), "statistic": first["statistic"], "kind": paper["kind"]}


def _arms_text(s: dict[str, Any]) -> str:
    """'Quendarin at 10 mg and 20 mg', or for several drugs 'A at 10 mg, B at 100 mg and C at 15 mg'."""
    return _join([f"{x} at {_join(s['doses_of'][x])} daily" for x in s["subjects"]])


def idea_sparse(paper: dict[str, Any]) -> str:
    s = _setup(paper)
    weeks = _join([f"week {w}" for w in s["weeks"]])
    many = len(s["subjects"]) > 1
    effect = "effects" if many else "effect"
    has = "have" if many else "has"
    changes = "change" if many else "changes"
    depends = ("the size of the change depends on the dose" if len(s["doses"]) > 1 or many
               else "the change grows over time")
    if many:
        depends = "the size of the change differs between the drugs"
    return (f"# {paper['title']}\n\n"
            f"## Problem Statement\n"
            f"For {s['context']}, it is not known what {effect} {s['subject']} {has} on the "
            f"{_join(s['measures'])}, compared with {s['comparator']}.\n\n"
            f"## Core Hypothesis\n"
            f"{s['subject']} taken once daily {changes} these measures more than {s['comparator']}, and "
            f"{depends}.\n\n"
            f"## Proposed Methodology (High-Level Technical Approach)\n"
            f"We propose a {s['kind']} in {s['context']}: {_arms_text(s)} against "
            f"{s['comparator']}, with each measure taken at {weeks}.\n\n"
            f"## Expected Contribution\n"
            f"The {s['statistic'].replace('comparator', s['comparator'])} for each measure, dose and time point, so "
            f"readers can choose a dose.\n")


def fact_line(f: dict[str, Any]) -> str:
    dose = f"{f['dose']} {write_as(f['dose_unit'])} daily" if f["dose"] else "—"
    week = f"week {f['week']}" if f["week"] else "—"
    stat = f["statistic"].replace("comparator", f["comparator"] or "comparator")
    where = "put in a table" if f["placement"] == "table" else "state in a sentence"
    cells = [f["id"], f.get("subject_as") or f["subject"].capitalize(), f["comparator"] or "—", f["measure"], f["context"], dose, week,
             f"{f['value']} {write_as(f['unit'])}", stat, where]
    return "| " + " | ".join(cells) + " |"


HEAD = ("| Row | Subject | Comparator | Measure | Patients | Dose | Time point | Value | Statistic | Where |\n"
        "|---|---|---|---|---|---|---|---|---|---|")


def experimental_log(paper: dict[str, Any]) -> str:
    s = _setup(paper)
    tables = [fact_line(f) for f in paper["facts"] if f["placement"] == "table"]
    text = [fact_line(f) for f in paper["facts"] if f["placement"] == "text"]
    arms = _join([f"{x} {d} daily" for x in s["subjects"] for d in s["doses_of"][x]])
    units = _join(_uniq([f"{m} in {write_as(f['unit'])}" for m in s["measures"] for f in paper["facts"]
                         if f["measure"] == m]))
    parts = [
        "# Experimental Log\n",
        "## 1. Experimental Setup",
        f"* **Design:** {s['kind']}, parallel groups, {s['subject']} against {s['comparator']}.",
        f"* **Patients:** {s['context']}.",
        f"* **Arms:** {arms}; {s['comparator']}.",
        f"* **Time points:** {_join([f'week {w}' for w in s['weeks']])}.",
        f"* **Evaluation Metrics:** {units}.",
        f"* **Statistic:** every value is the {s['statistic'].replace('comparator', s['comparator'])} "
        f"(negative = lower than {s['comparator']}).",
        f"* **Baselines Compared:** {s['comparator']}.",
        "",
        "## 2. Raw Numeric Data",
        f"### Tables ({len(tables)} values: put each in a results table)",
        HEAD, *tables, "",
        f"### Text ({len(text)} values: state each in a sentence of the results text)",
        HEAD, *text, "",
        "## 3. Qualitative Observations",
        f"* Observation: results are reported for every dose of {s['subject']} at every time point.",
        "",
        "## 4. Reporting Rules",
        "* Write every value above exactly as given, with all its decimals and its unit.",
        "* Put each value where its Where column says: in a Markdown table, or in a sentence.",
        "* Do not add other result values (no confidence intervals, p-values, patient counts or baseline values).",
        *name_rules(paper),
        "",
    ]
    return "\n".join(parts)


def name_rules(paper: dict[str, Any]) -> list[str]:
    """One rule per made-up drug the paper writes by code, or by name and code (none for name-only papers)."""
    out = []
    for name, m in sorted(paper.get("names", {}).items()):
        if m["written"] == "code":
            out.append(f"* Call this drug only by its development code {m['code']}; never use any other name for it.")
        elif m["written"] == "both":
            out.append(f"* Give this drug's name and development code together at first mention, as "
                       f"\"{name.capitalize()} ({m['code']})\"; later the name alone is fine.")
    return out


def write(domain: str, out: Path | None = None) -> list[Path]:
    """Write both files for every paper of `domain`; returns the paths written."""
    written = []
    for pid, paper in paper_facts(domain).items():
        folder = out / domain / pid if out else brief_dir(domain, pid)
        folder.mkdir(parents=True, exist_ok=True)
        for name, text in (("idea_sparse.md", idea_sparse(paper)), ("experimental_log.md", experimental_log(paper))):
            (folder / name).write_text(text, encoding="utf-8")
            written.append(folder / name)
    return written


def numbers_in(text: str) -> list[str]:
    """Every stand-alone number in a text (for the brief tests)."""
    return [re.sub(r"[^\d.]", "", f.value.raw) for f in norm.find_values(text)]
