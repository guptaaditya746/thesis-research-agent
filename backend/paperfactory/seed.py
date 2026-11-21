"""World -> seed graph (RDF), SHACL check, questions from the field pack's templates, gold answers by SPARQL.

Generic core for every field: ex:Entity (skos:prefLabel / altLabel), ex:Fact (subject, relation, object, inPaper),
ex:Paper. A field's kinds become subclasses of ex:Entity. Every planted fact is true in the world; which facts are
gold depends on the question. A fact id is "s-r-o"; the same fact may be planted in several papers.
"""
from __future__ import annotations

import random
from typing import Any

from pyshacl import validate
from rdflib import RDF, RDFS, Graph, Literal, Namespace
from rdflib.namespace import SKOS, XSD

from paperfactory.packs import Field

EX = Namespace("https://example.org/paperfactory/")


def fid(s: str, r: str, o: str) -> str:
    return f"{s}-{r}-{o}"


def kind_class(kind: str) -> str:
    return "".join(p.capitalize() for p in kind.split("_"))


def shapes(f: Field) -> str:
    rels = " ".join(f"ex:{r}" for r in f.relations)
    out = [f"""@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix ex: <{EX}> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
ex:EntityShape a sh:NodeShape ; sh:targetClass ex:Entity ;
  sh:property [ sh:path skos:prefLabel ; sh:minCount 1 ; sh:maxCount 1 ] .
ex:FactShape a sh:NodeShape ; sh:targetClass ex:Fact ;
  sh:property [ sh:path ex:subject ; sh:minCount 1 ; sh:maxCount 1 ; sh:class ex:Entity ] ;
  sh:property [ sh:path ex:object ; sh:minCount 1 ; sh:maxCount 1 ; sh:class ex:Entity ] ;
  sh:property [ sh:path ex:relation ; sh:minCount 1 ; sh:maxCount 1 ; sh:in ( {rels} ) ] ;
  sh:property [ sh:path ex:inPaper ; sh:minCount 1 ; sh:class ex:Paper ] ."""]
    for kind, k in f.kinds.items():
        props = []
        for a, typ in k.get("attrs", {}).items():
            c = ("sh:datatype xsd:integer" if typ == "int" else f"sh:class ex:{kind_class(typ[4:])}"
                 if typ.startswith("ref:") else "sh:datatype xsd:string")
            props.append(f"sh:property [ sh:path ex:{a} ; sh:minCount 1 ; sh:maxCount 1 ; {c} ]")
        if props:
            out.append(f"ex:{kind_class(kind)}Shape a sh:NodeShape ; sh:targetClass ex:{kind_class(kind)} ; "
                       + " ; ".join(props) + " .")
    return "\n".join(out)


def build(w: dict[str, Any], f: Field) -> tuple[Graph, dict[str, Any]]:
    g = Graph()
    g.bind("ex", EX)
    g.bind("skos", SKOS)
    for kind in f.kinds:
        g.add((EX[kind_class(kind)], RDFS.subClassOf, EX.Entity))
    for eid, e in w["entities"].items():
        n = EX[eid]
        g.add((n, RDF.type, EX[kind_class(e["kind"])]))
        g.add((n, RDF.type, EX.Entity))
        g.add((n, SKOS.prefLabel, Literal(e["label"])))
        for a in e.get("alt", []):
            g.add((n, SKOS.altLabel, Literal(a)))
        for a, typ in f.kinds[e["kind"]].get("attrs", {}).items():
            v = e["attrs"][a]
            g.add((n, EX[a], EX[v] if typ.startswith("ref:") else Literal(v, datatype=XSD.integer)
                   if typ == "int" else Literal(v)))
    facts: dict[str, Any] = {}
    for pid, p in w["papers"].items():
        g.add((EX[pid], RDF.type, EX.Paper))
        for role in ("claims", "decoys"):
            for s, r, o in p[role]:
                i = fid(s, r, o)
                n = EX[i]
                g.add((n, RDF.type, EX.Fact))
                g.add((n, EX.subject, EX[s]))
                g.add((n, EX.relation, EX[r]))
                g.add((n, EX.object, EX[o]))
                g.add((n, EX.inPaper, EX[pid]))
                fa = facts.setdefault(i, {"id": i, "s": s, "r": r, "o": o, "papers": {}})
                fa["papers"][pid] = role[:-1]
    return g, facts


def gold(g: Graph, q: dict[str, Any]) -> tuple[str, list[str]]:
    """One SPARQL query per question; filters come from the question card, never from its wording."""
    flt = [f"?f ex:inPaper ?p . FILTER(?p IN ({', '.join(f'ex:{p}' for p in q['papers'])}))"]
    for key, var in (("subject", "s"), ("object", "o"), ("relation", "r")):
        if key in q:
            flt.append(f"FILTER(?{var} = ex:{q[key]})")
    if "relation_in" in q:
        flt.append("FILTER(?r IN (" + ", ".join(f"ex:{r}" for r in q["relation_in"]) + "))")
    sparql = (f"PREFIX ex: <{EX}>\nSELECT DISTINCT ?s ?r ?o WHERE {{ ?f a ex:Fact ; ex:subject ?s ; ex:relation ?r ; "
              "ex:object ?o . " + " ".join(flt) + " }")
    short = lambda u: str(u).rsplit("/", 1)[1]  # noqa: E731
    return sparql, sorted(fid(short(s), short(r), short(o)) for s, r, o in g.query(sparql))


def questions(w: dict[str, Any], f: Field, per_question: int, seed: int) -> list[dict[str, Any]]:
    """Question cards from the field pack's templates, one per template per paper where the paper has a fitting
    claim. Each question is asked over its own paper plus papers that share an entity with it (up to
    per_question papers)."""
    rng = random.Random(seed)
    label = lambda e: w["entities"][e]["label"]  # noqa: E731
    out = []
    for pid, p in w["papers"].items():
        ents = {x for fact in p["claims"] + p["decoys"] for x in (fact[0], fact[2])}
        others = [q for q, pp in w["papers"].items() if q != pid and ents & {x for fact in pp["claims"] + pp["decoys"]
                                                                            for x in (fact[0], fact[2])}]
        scope = [pid] + rng.sample(others, min(per_question - 1, len(others)))
        for t in f.questions:
            card: dict[str, Any] = {}
            if t["filter"] == ["subject", "object"]:
                s, _, o = rng.choice(p["claims"])
                card = {"subject": s, "object": o}
            elif t["filter"] == ["subject"]:
                fits = [c for c in p["claims"] if c[1] == t["relation"]]
                if fits:
                    card = {"subject": rng.choice(fits)[0], "relation": t["relation"]}
            elif t["filter"] == ["object"] and p.get("conflict"):
                card = {"object": p["conflict"][0][2], "relation_in": t["relation_in"]}
            if card:
                text = t["text"].format(s=label(card["subject"]) if "subject" in card else "",
                                        o=label(card["object"]) if "object" in card else "")
                out.append({"id": f"{pid}:{t['id']}", "template": t["id"], "text": text, "papers": scope, **card})
    return out


def make(w: dict[str, Any], f: Field, per_question: int, seed: int) -> tuple[Graph, dict[str, Any]]:
    g, facts = build(w, f)
    ok, _, report = validate(g, shacl_graph=Graph().parse(data=shapes(f), format="turtle"), inference="rdfs")
    if not ok:
        raise ValueError("SHACL failed:\n" + report)
    qs = []
    for q in questions(w, f, per_question, seed):
        sparql, rows = gold(g, q)
        if rows:                               # never a benchmark question without gold
            qs.append({**q, "sparql": sparql, "gold": rows})
    return g, {"facts": facts, "questions": qs}
