"""Blueprint + checked names -> seed graph. No LLM here: every value comes from the effect model in the blueprint.

The blueprint's generator section (profile.py) names the result settings (context, factor, time), the paper keys
that hold them, and the effect model:
value = formula(subject, measure, settings) [- formula(comparator, ...)] * scale + noise,  rounded to `decimals`.
The noise of a row depends only on (random_seed, row id), so adding a paper never changes another paper's values.

A paper tests one subject (its factor values listed beside it) or several (`arms`), each against its comparator
(default from the generator section, or none). Against an active comparator the value is the subject's mean minus the
comparator's mean at the comparator's factor value. `scale` (default 1) shrinks or grows a paper's means: the
deliberate conflicts. Two papers may report the same fact (subject, comparator, measure, settings) only when both
name the other in `conflict_with`; build then links the two rows with ex:conflictsWith. `names: {item: code|both}`
says how the paper writes a made-up item (default: its name only).
"""
from __future__ import annotations

import random
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from rdflib import RDF, XSD, BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, SKOS

from evqa.paths import REPO, domain_dir
from evqa.seed.profile import Gen, with_generator

EX = Namespace("https://w3id.org/evqa/seed#")
D = Namespace("https://w3id.org/evqa/data/")
SOSA = Namespace("http://www.w3.org/ns/sosa/")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")
MESH = Namespace("http://id.nlm.nih.gov/mesh/")
KINDS = {"RCT": EX.RCT, "cohort": EX.Cohort, "lab": EX.LabTest, "simulation": EX.Simulation}


def load_blueprint(domain: str) -> dict[str, Any]:
    """The blueprint, with its generator section (its own, or the profile that applies to its domain)."""
    return with_generator(yaml.safe_load((domain_dir(domain) / "blueprint.yaml").read_text(encoding="utf-8")))


def unit_iri(text: str) -> URIRef:
    prefix, _, local = text.partition(":")
    return {"unit": UNIT, "ex": EX}[prefix][local]


def slug(key: str) -> str:
    return key.replace("_", "-")


def qv(g: Graph, value: Decimal | float, unit: URIRef) -> BNode:
    node = BNode()
    g.add((node, RDF.type, QUDT.QuantityValue))
    g.add((node, QUDT.numericValue, Literal(Decimal(str(value)), datatype=XSD.decimal)))
    g.add((node, QUDT.unit, unit))
    return node


def _env(gen: Gen, subject: str, measure: str, settings: dict[str, Any]) -> dict[str, Any]:
    return {"subject": subject, "measure": measure, **settings}


def effect(bp: dict[str, Any], paper: dict[str, Any], measure: str, settings: dict[str, Any], row_id: str,
           subject: str) -> Decimal:
    """The value of one row: `settings` = {slot: value} of the paper's context, factor and time."""
    gen = Gen(bp)
    m = bp["measures"][measure]
    env = _env(gen, subject, measure, settings)
    mean = gen.mean(env)
    comparator = gen.comparator(paper)
    if comparator is not None and comparator != gen.default_comparator:
        at = {**settings, gen.F: paper[gen.g["factor"]["comparator_key"]]}
        mean -= gen.mean(_env(gen, comparator, measure, at))
    if "scale" in paper:
        mean *= paper["scale"]
    noise = random.Random(f"{bp['random_seed']}:{row_id}").gauss(0, gen.noise_sd(env))
    return Decimal(str(round(mean + noise, m["decimals"]))).quantize(Decimal(1).scaleb(-m["decimals"]))


def arms(paper: dict[str, Any], bp: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """The arms of a paper as the blueprint writes them (without `bp`: its `arms`, else the paper itself)."""
    if bp is None:
        return paper.get("arms") or [paper]
    return Gen(bp).arms(paper)


def rows(bp: dict[str, Any]) -> list[dict[str, Any]]:
    """Every fact row of the blueprint as a plain dict (also what the dataset pane shows). Settings are keyed by the
    blueprint's slot names. Row ids count measure, then arm, then factor value, then time (one arm: the original
    order). A row goes in the text when it is at the paper's last time for its first measure, else in a table."""
    gen = Gen(bp)
    sk, fk = gen.g["subject"]["paper_key"], gen.g["factor"]["arm_key"]
    tk, ck = gen.g["time"]["paper_key"], gen.g["context"]["paper_key"]
    out = []
    for paper in bp["papers"]:
        n = 0
        comparator = gen.comparator(paper)
        for measure in paper["measures"]:
            for arm in gen.arms(paper):
                for fv in arm[fk]:
                    for tv in paper[tk]:
                        n += 1
                        rid = f"R-{paper['id'][2:]}-{n:02d}"
                        text = tv == paper[tk][-1] and measure == paper["measures"][0]
                        settings = {gen.C: paper[ck], gen.F: fv, gen.T: tv}
                        out.append({"id": rid, "paper": paper["id"], "subject": arm[sk], "comparator": comparator,
                                    "measure": measure, **settings, "statistic": gen.statistic,
                                    "value": effect(bp, paper, measure, settings, rid, arm[sk]),
                                    "unit": bp["measures"][measure]["unit"], "placement": "text" if text else "table"})
    return out


def fact_key(row: dict[str, Any], gen: Gen) -> tuple[Any, ...]:
    keys = (gen.C, gen.F, gen.T)
    return (row["subject"], row["comparator"], row["measure"], *(row[k] for k in keys), row["statistic"])


def conflicts(bp: dict[str, Any], all_rows: list[dict[str, Any]] | None = None) -> list[tuple[str, str]]:
    """Pairs of row ids from two papers that state the same fact. Raises when the papers did not declare the
    conflict, or when the two values differ by less than max(3 rounding steps, 2 noise SDs): too close to tell from
    noise, so not a clear conflict."""
    gen = Gen(bp)
    all_rows = all_rows if all_rows is not None else rows(bp)
    declared = {p["id"]: set(p.get("conflict_with", [])) for p in bp["papers"]}
    by_key: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for r in all_rows:
        by_key.setdefault(fact_key(r, gen), []).append(r)
    out = []
    for same in by_key.values():
        for i, a in enumerate(same):
            for b in same[i + 1:]:
                if b["paper"] not in declared[a["paper"]] or a["paper"] not in declared[b["paper"]]:
                    raise ValueError(f"{a['id']} and {b['id']} state the same fact; declare conflict_with")
                m = bp["measures"][a["measure"]]
                sd = gen.noise_sd(_env(gen, a["subject"], a["measure"], {k: a[k] for k in (gen.C, gen.F, gen.T)}))
                least = max(3 * Decimal(1).scaleb(-m["decimals"]), 2 * Decimal(str(sd)))
                if abs(a["value"] - b["value"]) < least:
                    raise ValueError(f"conflict {a['id']} {a['value']} vs {b['id']} {b['value']} is too small")
                out.append((a["id"], b["id"]))
    return out


def _upper_first(text: str) -> str:
    return text[:1].upper() + text[1:]


def build(bp: dict[str, Any], names: dict[str, Any]) -> Graph:
    bp = with_generator(bp)
    gen = Gen(bp)
    slots = (names or {}).get("slots", {})
    g = Graph()
    for prefix, ns in (("ex", EX), ("d", D), ("sosa", SOSA), ("qudt", QUDT), ("unit", UNIT), ("mesh", MESH),
                       ("skos", SKOS), ("dcterms", DCTERMS)):
        g.bind(prefix, ns)
    label: dict[str, str] = {}
    for key, item in bp["items"].items():
        if "invent" in item:
            picked = slots[key]
            label[key] = picked["name"]
            node = D[picked["name"]]
            g.add((node, SKOS.altLabel, Literal(picked["code"])))
            g.add((node, EX.madeUp, Literal(True)))
        else:
            label[key] = item["label"]
            node = D[slug(key)]
            if "mesh" in item:
                g.add((node, SKOS.closeMatch, MESH[item["mesh"]]))
            if "code" in item:
                g.add((node, SKOS.altLabel, Literal(item["code"])))
            if item.get("made_up"):   # a fixed invented name (no naming step)
                g.add((node, EX.madeUp, Literal(True)))
        g.add((node, RDF.type, EX.Item))
        g.add((node, SKOS.prefLabel, Literal(label[key])))
    item_iri = {k: D[label[k]] if "invent" in v else D[slug(k)] for k, v in bp["items"].items()}
    for key, ctx in gen.section("context").items():
        g.add((D[slug(key)], RDF.type, EX.Context))
        g.add((D[slug(key)], SKOS.prefLabel, Literal(ctx["label"])))
        if "mesh" in ctx:
            g.add((D[slug(key)], SKOS.closeMatch, MESH[ctx["mesh"]]))
    for key, m in bp["measures"].items():
        node = D[slug(key)]
        g.add((node, RDF.type, EX.Measure))
        g.add((node, SKOS.prefLabel, Literal(m["label"])))
        for alt in m.get("alt", []):
            g.add((node, SKOS.altLabel, Literal(alt)))
        if "mesh" in m:
            g.add((node, SKOS.closeMatch, MESH[m["mesh"]]))
        g.add((node, EX.unit, unit_iri(m["unit"])))
        g.add((node, EX.higherIsBetter, Literal(m["higher_is_better"])))
    (factor_key, factor), = gen.section("factor").items()
    g.add((D[slug(factor_key)], RDF.type, EX.Factor))
    g.add((D[slug(factor_key)], SKOS.prefLabel, Literal(factor["label"])))
    for paper in bp["papers"]:
        node = D[paper["id"]]
        codes = {f"{k}_code": slots[k]["code"] for k, v in bp["items"].items() if "invent" in v}
        codes |= {f"{k}_code": v["code"] for k, v in bp["items"].items() if "code" in v and "invent" not in v}
        title = paper["title"].format(**{k: _upper_first(v) for k, v in label.items()}, **codes)
        for p, o in ((RDF.type, EX.Paper), (DCTERMS.title, Literal(title)), (EX.domain, Literal(bp["domain"])),
                     (EX.role, Literal(paper["role"])), (EX["split"], Literal(paper["split"])),
                     (EX.evidenceKind, KINDS[paper["kind"]])):
            g.add((node, p, o))
        for key, form in sorted(paper.get("names", {}).items()):
            mention = BNode()
            g.add((node, EX.mention, mention))
            g.add((mention, EX.item, item_iri[key]))
            g.add((mention, EX.written, Literal(form)))
    all_rows = rows(bp)
    for a, b in conflicts(bp, all_rows):
        g.add((D[a], EX.conflictsWith, D[b]))
        g.add((D[b], EX.conflictsWith, D[a]))
    for row in all_rows:
        cond = D[gen.g["factor"]["node"].format(row[gen.F])]
        if (cond, RDF.type, EX.Condition) not in g:
            g.add((cond, RDF.type, EX.Condition))
            g.add((cond, EX.factor, D[slug(factor_key)]))
            g.add((cond, EX.setting, qv(g, row[gen.F], unit_iri(factor["unit"]))))
        r = D[row["id"]]
        comp = () if row["comparator"] is None else ((EX.comparator, item_iri[row["comparator"]]),)
        for p, o in ((RDF.type, EX.Result), (EX.subject, item_iri[row["subject"]]), *comp,
                     (SOSA.observedProperty, D[slug(row["measure"])]),
                     (SOSA.hasFeatureOfInterest, D[slug(row[gen.C])]), (EX.condition, cond),
                     (EX.atTime, qv(g, row[gen.T], unit_iri(gen.g["time"]["unit"]))), (EX.statistic, EX[row["statistic"]]),
                     (SOSA.hasResult, qv(g, row["value"], unit_iri(row["unit"]))),
                     (EX.reportedIn, D[row["paper"]]), (EX.placement, Literal(row["placement"]))):
            g.add((r, p, o))
    return g


def text(domain: str, graph: Graph) -> str:
    head = (f"# Seed of the {domain} domain: the truth. Made by `evqa seed build {domain}` from blueprint.yaml and "
            "names.json.\n# Do not edit by hand; change the blueprint and rebuild.\n")
    return head + graph.serialize(format="turtle")


def relocate(path: Path, out: Path | None) -> Path:
    """`path` (inside the repo) moved under `out` with the same repo-relative path; out None = the path itself."""
    return path if out is None else out / path.relative_to(REPO)


def write(domain: str, graph: Graph, out: Path | None = None) -> Path:
    """Write seed.ttl; with `out`, under out/<repo-relative path> instead (the frozen folder is never touched)."""
    path = relocate(domain_dir(domain) / "seed.ttl", out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text(domain, graph), encoding="utf-8")
    return path
