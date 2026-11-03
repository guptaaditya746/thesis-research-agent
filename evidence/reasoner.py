"""The reasoner: a pack's OWL ontology read with rdflib and closed with owlrl (spec 6.3, D8, D13).

Two jobs use it: a narrower name counts for the broader one a question asks about (`broader_of`, `counts_as`), and
a value linked to something of the wrong kind is flagged (`reason`). Labels are compared after `names.clean`, so
"Top-1 Accuracy" and "top 1 accuracy" are one label. The engine runs `reason` once per run, after the names step and
before the answer (D25), and writes the result as reason.json (`to_json`); a replay reads that file (`from_json`).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import owlrl
import rdflib
from rdflib import OWL, RDF, RDFS, URIRef

from jsonio import sha256_hex

from .contract import Item
from .names import clean
from .pack import DOMAINS, Pack, PackError, Role, RoleMap
from .protocol import Protocol

CSKG = "https://w3id.org/cskg/ontology#"
NO_TREE = "reasoning off: no tree"   # what a run says when its field has no ontology tree (ontology.fill)
# The classes every ontology is rooted in: never reported as a broader name ("metric" is no answer to "what is
# broader than accuracy").
TOP_CLASSES = frozenset(
    URIRef(CSKG + name) for name in ("Metric", "Method", "Material", "Task", "OtherEntity")
) | {OWL.Thing, RDFS.Resource}


@dataclass(frozen=True)
class Inferences:
    ontology_sha256: str | None
    broader: dict[str, list[str]]       # a name -> the labels of the classes above it
    link_flags: list[list[str]]


def _ontology_path(pack: Pack, root: Path) -> Path | None:
    return None if pack.ontology is None else root / pack.name / pack.ontology.file


def ontology_sha256(pack: Pack, root: Path = DOMAINS) -> str | None:
    """sha256 of the ontology file with LF line ends; None when the pack has no ontology."""
    path = _ontology_path(pack, root)
    if path is None:
        return None
    if not path.is_file():
        raise PackError(f"domain pack {pack.name!r}: ontology {path} is missing")
    return sha256_hex(path.read_bytes().replace(b"\r\n", b"\n"))


def _labelled(graph: rdflib.Graph) -> dict[str, list[URIRef]]:
    """clean(label) -> the classes carrying it, IRIs sorted."""
    found: dict[str, set[URIRef]] = {}
    for subject, _, label in graph.triples((None, RDFS.label, None)):
        if isinstance(subject, URIRef):
            found.setdefault(clean(str(label)), set()).add(subject)
    return {label: sorted(iris) for label, iris in found.items()}


def load_ontology(pack: Pack, root: Path = DOMAINS) -> rdflib.Graph | None:
    """The pack's ontology with the RDFS closure applied; None when the pack has none. A label that two classes
    share (after names.clean) is a PackError naming both IRIs."""
    path = _ontology_path(pack, root)
    if path is None:
        return None
    ontology_sha256(pack, root)   # a missing file is a PackError
    graph = rdflib.Graph()
    try:
        graph.parse(data=path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8"), format="turtle")
    except Exception as e:   # rdflib raises several parser errors
        raise PackError(f"domain pack {pack.name!r}: ontology {path} is invalid: {e}") from e
    for label, iris in _labelled(graph).items():
        if len(iris) > 1:
            raise PackError(f"domain pack {pack.name!r}: label {label!r} names several classes: "
                            + ", ".join(str(i) for i in iris))
    owlrl.DeductiveClosure(owlrl.RDFS_Semantics).expand(graph)
    return graph


def broader_of(graph: rdflib.Graph, label: str) -> list[str]:
    """The labels of every class above the class labelled `label` (closure applied), sorted; the class itself and
    the top classes are left out. [] for an unknown label."""
    classes = _labelled(graph).get(clean(label))
    if not classes:
        return []
    names: set[str] = set()
    for cls in classes:
        for above in graph.objects(cls, RDFS.subClassOf):
            if above == cls or above in TOP_CLASSES or not isinstance(above, URIRef):
                continue
            names.update(str(lab) for lab in graph.objects(above, RDFS.label))
    return sorted(names - {label})


# How a link flag names the role the link should point at ("not a compared thing").
PLAIN_ROLES = {Role.COMPARED_THING: "compared thing", Role.METRIC: "metric", Role.CONTEXT: "context"}


def _class_of(graph: rdflib.Graph, pack: Pack, curie: str) -> URIRef:
    """The IRI of a CURIE of pack.yaml `ontology.roles` ("cskg:Metric"), by the ontology file's prefixes."""
    try:
        return URIRef(graph.namespace_manager.expand_curie(curie))
    except ValueError as e:
        raise PackError(f"domain pack {pack.name!r}: ontology role class {curie!r}: {e}") from e


def reason(pack: Pack, protocol: Protocol, items: dict[str, list[Item]], root: Path = DOMAINS) -> Inferences:
    """The inferences of one run (spec 6.3): `broader`, every canonical name or name of an item that has a broader
    class in the ontology (`broader_of`), and `link_flags`, `[item id, link name, target id, "not a <role>"]` for
    every link whose target's class is neither the class of the role of the type the protocol links to nor a
    subclass of it. A target's class is the class labelled with its canonical name or name (in that order), else
    the class of its type's role. A pack without an ontology gives no inferences."""
    graph = load_ontology(pack, root)
    if graph is None or pack.ontology is None:
        return Inferences(None, {}, [])
    roles, labelled = RoleMap(pack), _labelled(graph)
    role_class = {role: _class_of(graph, pack, curie) for role, curie in pack.ontology.roles.items()}

    def names_of(item: Item) -> list[str]:
        fields = (roles.field_or_none(item.evidence_type, which) for which in ("canonical", "name"))
        return [str(v) for f in fields if f is not None and (v := item.fields.get(f)) is not None and str(v).strip()]

    def class_of(item: Item) -> URIRef | None:
        found = next((labelled[c][0] for n in names_of(item) if (c := clean(n)) in labelled), None)
        decl = pack.types.get(item.evidence_type)
        return found if found is not None else role_class.get(decl.role) if decl is not None else None

    broader: dict[str, list[str]] = {}
    asked: set[str] = set()     # names already looked up (most have no broader class)
    flags: list[list[str]] = []
    for doc_items in items.values():
        by_id = {i.item_id: i for i in doc_items}
        for item in doc_items:
            for name in names_of(item):
                if name not in asked:
                    asked.add(name)
                    if above := broader_of(graph, name):
                        broader[name] = above
            spec = protocol.evidence_types.get(item.evidence_type)
            for link, target_id in sorted(item.links.items()):
                decl = pack.types.get(spec.links.get(link, "")) if spec is not None else None
                expected = role_class.get(decl.role) if decl is not None else None
                target = by_id.get(target_id)
                if decl is None or expected is None or target is None:   # a role with no class, a dangling link
                    continue
                found = class_of(target)
                if found is None or (found != expected and (found, RDFS.subClassOf, expected) not in graph):
                    flags.append([item.item_id, link, target_id, f"not a {PLAIN_ROLES.get(decl.role, str(decl.role))}"])
    return Inferences(ontology_sha256(pack, root), dict(sorted(broader.items())), flags)


def to_json(inferred: Inferences) -> dict[str, Any]:
    """reason.json."""
    return {"ontology_sha256": inferred.ontology_sha256, "broader": inferred.broader, "link_flags": inferred.link_flags}


def from_json(data: dict[str, Any]) -> Inferences:
    """The inferences of a recorded reason.json (a replay reads them, never reasons again)."""
    return Inferences(data["ontology_sha256"], {k: list(v) for k, v in data["broader"].items()},
                      [list(f) for f in data["link_flags"]])


def counts_as(name: str, wanted: str, inferred: Inferences | None) -> bool:
    """Does `name` count for `wanted`: the same name, or `wanted` is above `name` in the ontology."""
    if clean(name) == clean(wanted):
        return True
    if inferred is None:
        return False
    return any(clean(b) == clean(wanted) for b in inferred.broader.get(name, ()))
