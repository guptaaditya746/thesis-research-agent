"""The reasoner: a pack's OWL ontology read with rdflib and closed with owlrl (spec 6.3, D8, D13).

Two jobs use it: a narrower name counts for the broader one a question asks about (`broader_of`, `counts_as`), and
a value linked to something of the wrong kind is flagged (added with `reason`). Labels are compared after
`names.clean`, so "Top-1 Accuracy" and "top 1 accuracy" are one label.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import owlrl
import rdflib
from rdflib import OWL, RDF, RDFS, URIRef

from jsonio import sha256_hex

from .names import clean
from .pack import DOMAINS, Pack, PackError

CSKG = "https://w3id.org/cskg/ontology#"
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


def counts_as(name: str, wanted: str, inferred: Inferences | None) -> bool:
    """Does `name` count for `wanted`: the same name, or `wanted` is above `name` in the ontology."""
    if clean(name) == clean(wanted):
        return True
    if inferred is None:
        return False
    return any(clean(b) == clean(wanted) for b in inferred.broader.get(name, ()))
