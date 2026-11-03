"""Never silent: what the ontology placed, what it did not, and what the LLM added (always marked "llm").

`report` counts the found names the tree places; a field without a tree says "reasoning off: no tree" and the run
goes on. `propose_parents` asks a DSPy step (one name per call) for a parent among existing class labels or the other
proposed names; code refuses anything else. `mini_tree` builds a small tree of the found names for a field without
one. Every LLM link is a reified triple carrying `ev:madeBy "llm"`. `review` records a human's accepted and rejected
links; the synthesis rerun after a review is W4's `rerun()`."""
from __future__ import annotations

import json
from typing import Any

import dspy
import rdflib
from rdflib import RDF, RDFS, SKOS, BNode, Literal, Namespace, URIRef

from evidence import steps
from evidence.names import clean
from evidence.reasoner import NO_TREE
from evidence.rundir import RunDir
from evidence.vocab import EV as EV_IRI

EV = Namespace(EV_IRI)
LLM_TREE = "made by LLM"
ONTOLOGY_TREE = "ontology tree"
LINKS_REVIEW_FILE = "links_review.json"
MAX_CANDIDATES = 30
_TREE = (RDFS.subClassOf, SKOS.broader)


class ProposeParent(dspy.Signature):
    """Place one name in a tree of classes. Choose its parent: the one class from `candidates` that the name is a
    kind of, or part of. Answer with the candidate exactly as written. Answer with an empty string when no candidate
    fits; never invent a class. Example: name "Heart Attack Risk", candidates ["Heart Diseases", "Kidney Diseases"]
    gives "Heart Diseases". Example: name "Wing span", candidates ["Heart Diseases"] gives ""."""
    name: str = dspy.InputField(desc="the name to place")
    question: str = dspy.InputField(desc="the research question the name comes from")
    candidates: list[str] = dspy.InputField(desc="existing class labels and other proposed names")
    parent: str = dspy.OutputField(desc="one candidate exactly as written, or an empty string")


def _labels(graph: rdflib.Graph) -> dict[str, tuple[str, URIRef]]:
    """clean(label or entry term) -> (preferred label, class IRI); the first IRI in sorted order wins."""
    found: dict[str, tuple[str, URIRef]] = {}
    for prop in (SKOS.altLabel, RDFS.label):
        for s, _, o in sorted(graph.triples((None, prop, None)), key=lambda t: (str(t[0]), str(t[2]))):
            if isinstance(s, URIRef):
                preferred = next(iter(sorted(str(x) for x in graph.objects(s, RDFS.label))), str(o))
                found.setdefault(clean(str(o)), (preferred, s))
    return found


def _llm_links(graph: rdflib.Graph) -> set[tuple[Any, Any]]:
    out = set()
    for node in graph.subjects(EV.madeBy, Literal("llm")):
        s, o = graph.value(node, RDF.subject), graph.value(node, RDF.object)
        if s is not None and o is not None:
            out.add((s, o))
    return out


def _tree_pairs(graph: rdflib.Graph) -> set[tuple[Any, Any]]:
    return {(s, o) for p in _TREE for s, o in graph.subject_objects(p) if s != o and isinstance(o, URIRef)
            and o != RDFS.Resource}





def report(graph: rdflib.Graph | None, found_names: list[str]) -> dict[str, Any]:
    """{"tree": "ontology tree" | "made by LLM" | "reasoning off: no tree", "unplaced": n, "names": [{"name", "placed"}]}.
    A name is placed when it equals (after `names.clean`) a class label or entry term. A graph without any
    subclass link (no graph, or QUDT units alone) is no tree."""
    pairs = _tree_pairs(graph) if graph is not None else set()
    labelled = _labels(graph) if graph is not None else {}
    names = [{"name": n, "placed": clean(n) in labelled} for n in found_names]
    if not pairs:
        tree = NO_TREE
    else:
        tree = LLM_TREE if pairs <= _llm_links(graph) else ONTOLOGY_TREE
    return {"tree": tree, "unplaced": sum(not n["placed"] for n in names), "names": names}


def _candidates(name: str, labelled: dict[str, tuple[str, URIRef]], others: list[str]) -> list[str]:
    words = {w for w in clean(name).split() if len(w) > 3}
    near = sorted({label for key, (label, _) in labelled.items() if words & set(key.split())})[:MAX_CANDIDATES]
    return near + [o for o in others if o != name]


def _creates_cycle(child: str, parent: str, chosen: dict[str, str]) -> bool:
    seen = {child}
    while parent in chosen or parent in seen:
        if parent in seen:
            return True
        seen.add(parent)
        parent = chosen[parent]
    return False


def propose_parents(unplaced: list[str], graph: rdflib.Graph, question: str) -> list[tuple[str, str]]:
    """(name, parent) for each unplaced name the model could place. The parent must be an existing class label of
    `graph` or another name of `unplaced`, and never closes a loop; anything else is dropped. Needs `steps.configure`."""
    step = steps.Step(ProposeParent, "propose_parent")
    labelled = _labels(graph)
    chosen: dict[str, str] = {}
    for name in unplaced:
        candidates = _candidates(name, labelled, unplaced)
        if not candidates:
            continue
        answer = str(step(name=name, question=question, candidates=candidates).parent).strip()
        if answer in unplaced and answer != name:
            parent = answer
        elif clean(answer) in labelled and clean(answer) != clean(name):
            parent = labelled[clean(answer)][0]
        else:
            continue
        if not _creates_cycle(name, parent, chosen):
            chosen[name] = parent
    return [(n, chosen[n]) for n in unplaced if n in chosen]


def _iri(name: str) -> URIRef:
    return URIRef(EV_IRI + "name/" + "-".join(clean(name).split()))


def add_links(graph: rdflib.Graph, pairs: list[tuple[str, str]]) -> rdflib.Graph:
    """A copy of `graph` with each (name, parent) added as a subclass link made by the LLM."""
    out = rdflib.Graph()
    out += graph
    labelled = _labels(out)
    for name, parent in pairs:
        child = labelled[clean(name)][1] if clean(name) in labelled else _iri(name)
        top = labelled[clean(parent)][1] if clean(parent) in labelled else _iri(parent)
        for iri, label in ((child, name), (top, parent)):
            if iri == _iri(label):
                out.add((iri, RDFS.label, Literal(label)))
        out.add((child, RDFS.subClassOf, top))
        node = BNode()
        for triple in ((RDF.type, RDF.Statement), (RDF.subject, child), (RDF.predicate, RDFS.subClassOf),
                       (RDF.object, top), (EV.madeBy, Literal("llm"))):
            out.add((node, *triple))
        labelled = _labels(out)
    return out


def mini_tree(found_names: list[str], question: str) -> rdflib.Graph:
    """A small tree of the found names for a field without one: the model places each name under another found
    name or none. Every link carries `ev:madeBy "llm"`."""
    return add_links(rdflib.Graph(), propose_parents(list(found_names), rdflib.Graph(), question))


def stage_result(field: str, found_names: list[str], question: str) -> dict[str, Any]:
    """What the after_run stage writes (`ontology.json`): the report, then the LLM links that fill it. With a tree the
    unplaced names get parents; without one a mini-tree of the found names is built. Needs `steps.configure`."""
    from evidence.planrun import load_cached
    graph = load_cached(field)
    first = report(graph, found_names)
    if first["tree"] == NO_TREE:
        links = [(s, o) for s, o in _named_links(mini_tree(found_names, question))]
        return {**first, "links": links, "made_by": "llm" if links else None}
    unplaced = [n["name"] for n in first["names"] if not n["placed"]]
    pairs = propose_parents(unplaced, graph, question) if unplaced else []
    return {**first, "links": [list(p) for p in pairs], "made_by": "llm" if pairs else None}


def _named_links(graph: rdflib.Graph) -> list[list[str]]:
    label = lambda iri: str(graph.value(iri, RDFS.label) or iri)   # noqa: E731
    return sorted([label(s), label(o)] for s, o in _llm_links(graph))


def ontology_stage(run: RunDir, ctx) -> dict[str, Any]:
    """The `after_run` seam function (registered by the caller, not at import: registering changes run.json). The
    found names are the name-like fields of the run's items."""
    plan = ctx.plan
    names: list[str] = []
    for item in run.items():
        for key in ("canonical", "name", "subject", "object"):
            value = item.fields.get(key)
            if isinstance(value, str) and value.strip() and value not in names:
                names.append(value)
    with steps.using(ctx.dspy_lm("ontology")):   # this run's model, in this thread only
        return stage_result(plan.field if plan else "other", names, plan.question if plan else "")


def review(run: RunDir, accepted: list[str], rejected: list[str]) -> None:
    """Write the human's verdict on the LLM links ("child -> parent" strings) to `links_review.json`."""
    run.file(LINKS_REVIEW_FILE).write_text(
        json.dumps({"accepted": sorted(accepted), "rejected": sorted(rejected)}, indent=2), encoding="utf-8")
