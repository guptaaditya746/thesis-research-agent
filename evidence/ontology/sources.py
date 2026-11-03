"""Where the ontology files live and how they become one rdflib graph.

The big files (MeSH descriptor XML, CS-KG) are fetched once on Slurm into the folder named by `$EV_ONTOLOGY_DIR` and
are never committed. A missing file means no tree for that field (`load` leaves it out), never a crash. QUDT units
are small: a subset is committed in `data/`, and a full `qudt_units.ttl` in the folder replaces it."""
from __future__ import annotations

import datetime
import hashlib
import os
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import owlrl
import rdflib
from rdflib import RDFS, SKOS, Literal, Namespace, URIRef

from evidence.names import clean
from evidence.pack import DOMAINS

ENV_DIR = "EV_ONTOLOGY_DIR"
QUDT = Namespace("http://qudt.org/schema/qudt/")
MESH = Namespace("https://id.nlm.nih.gov/mesh/")
DATA = Path(__file__).parent / "data"
CS_FALLBACK = DOMAINS / "rag" / "ontology.ttl"   # the CS-KG ontology the packs read today

# name -> file in the folder, where to fetch it, and its pinned sha256 (None until the first Slurm fetch has been
# reported: `ontology_hashes()` then gives the value to pin, and the lockfile records it as `ontology_sha256`).
PINNED: dict[str, dict[str, Any]] = {
    "mesh": {"file": "mesh_desc.xml", "sha256": None,
             "url": f"https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc{datetime.date.today().year}.xml"},
    "qudt": {"file": "qudt_units.ttl", "sha256": None, "url": "https://qudt.org/vocab/unit/"},
    "cskg": {"file": "cskg.ttl", "sha256": None, "url": os.environ.get("EV_CSKG_URL")},
}


class OntologyError(RuntimeError):
    pass


def ontology_dir() -> Path | None:
    value = os.environ.get(ENV_DIR)
    return Path(value) if value else None


ACCEPT = {"mesh": "application/xml", "qudt": "text/turtle", "cskg": "text/turtle"}


def _download(url: str, accept: str = "*/*") -> bytes:
    request = urllib.request.Request(url, headers={"Accept": accept})
    with urllib.request.urlopen(request, timeout=600) as response:   # noqa: S310 - pinned https URLs
        return response.read()


def fetch(name: str, dest: Path | None = None, *, url: str | None = None, sha256: str | None = None) -> Path:
    """Download the file `name` ("mesh", "qudt", "cskg") into `dest` (default `$EV_ONTOLOGY_DIR`) and check its
    sha256 against the pin (or `sha256`). A wrong hash writes nothing."""
    if name not in PINNED:
        raise OntologyError(f"unknown ontology {name!r}: one of {', '.join(PINNED)}")
    spec = PINNED[name]
    folder = dest or ontology_dir()
    if folder is None:
        raise OntologyError(f"set ${ENV_DIR} or pass dest")
    source = url or spec["url"]
    if not source:
        raise OntologyError(f"no URL for {name!r}: pass url (CS-KG: set $EV_CSKG_URL)")
    data = _download(source, ACCEPT[name])
    want = sha256 or spec["sha256"]
    got = hashlib.sha256(data).hexdigest()
    if want is not None and got != want:
        raise OntologyError(f"{name}: sha256 {got} is not the pinned {want}")
    try:   # refuse to write a file that does not parse (a server may answer an HTML page)
        _parse(name, data)
    except Exception as e:
        raise OntologyError(f"{name}: the download from {source} does not parse: {type(e).__name__}: {e}") from e
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / spec["file"]
    path.write_bytes(data)
    return path


def _path(name: str) -> Path | None:
    """The file of `name` if it exists (the folder first; QUDT falls back to the committed subset)."""
    folder = ontology_dir()
    if folder is not None and (folder / PINNED[name]["file"]).is_file():
        return folder / PINNED[name]["file"]
    return DATA / "qudt_units.ttl" if name == "qudt" else None


def files_for(field: str) -> dict[str, Path]:
    """{name: file} of exactly the files `load(field)` reads (the CS fallback is "cs_fallback")."""
    out: dict[str, Path] = {}
    if field == "cs":
        if (path := _path("cskg")) is not None:
            out["cskg"] = path
        elif CS_FALLBACK.is_file():
            out["cs_fallback"] = CS_FALLBACK
    elif field == "medicine" and (path := _path("mesh")) is not None:
        out["mesh"] = path
    if (units := _path("qudt")) is not None:
        out["qudt"] = units
    return out


def ontology_hashes(field: str | None = None) -> dict[str, str]:
    """{name: sha256} of the files `load` reads (`files_for`), for the lockfile's `ontology_sha256`; with no field,
    of every field's files."""
    files: dict[str, Path] = {}
    for f in ([field] if field else ["cs", "medicine", "other"]):
        files.update(files_for(f))
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sorted(files.items())}


def _parse(name: str, data: bytes) -> rdflib.Graph:
    """The graph of one file's bytes; raises when it does not parse."""
    graph = rdflib.Graph()
    if name == "mesh":
        import io
        return _mesh_graph(io.BytesIO(data))
    graph.parse(data=data.replace(b"\r\n", b"\n").decode("utf-8"), format="turtle")
    if name in ("cskg", "cs_fallback"):
        owlrl.DeductiveClosure(owlrl.RDFS_Semantics).expand(graph)
    return graph


def _mesh_graph(path: Any) -> rdflib.Graph:
    """MeSH descriptors as classes: rdfs:label (preferred name), skos:altLabel (entry terms), rdfs:subClassOf by
    tree numbers (C14.280.647 sits under C14.280). Read as a stream; the real file is large."""
    graph = rdflib.Graph()
    trees: dict[str, URIRef] = {}
    rows: list[tuple[URIRef, list[str]]] = []
    for _, el in ET.iterparse(path):
        if el.tag != "DescriptorRecord":
            continue
        iri = MESH[el.findtext("DescriptorUI", "")]
        name = el.findtext("DescriptorName/String", "")
        graph.add((iri, RDFS.label, Literal(name)))
        for term in el.findall("ConceptList/Concept/TermList/Term/String"):
            if term.text and term.text != name:
                graph.add((iri, SKOS.altLabel, Literal(term.text)))
        numbers = [t.text for t in el.findall("TreeNumberList/TreeNumber") if t.text]
        for n in numbers:
            trees[n] = iri
        rows.append((iri, numbers))
        el.clear()
    for iri, numbers in rows:
        for n in numbers:
            parent = trees.get(n.rpartition(".")[0]) if "." in n else None
            if parent is not None and parent != iri:
                graph.add((iri, RDFS.subClassOf, parent))
    return graph


def load(field: str, *, with_units: bool = True) -> rdflib.Graph | None:
    """The ontology graph of a field: `cs` the CS-KG (from the folder, else the repo's ontology.ttl), `medicine` MeSH,
    and QUDT units for every field. None when the field has nothing to read. A missing or unparseable file is left
    out (no tree), never a crash."""
    graph = rdflib.Graph()
    found = False
    for name, path in files_for(field).items():
        if name == "qudt" and not with_units:
            continue
        try:
            graph += _parse(name, path.read_bytes())
            found = True
        except Exception:   # noqa: BLE001 - a bad file means "reasoning off: no tree"
            continue
    return graph if found else None


def other_names(graph: rdflib.Graph, label: str) -> list[str]:
    """The other names of the class or unit called `label` (compared after `names.clean`): MeSH entry terms
    (skos:altLabel), every other rdfs:label (CS-KG) and QUDT symbols both ways. Sorted; [] when unknown."""
    key = clean(label)
    props = (RDFS.label, SKOS.altLabel, QUDT.symbol)
    subjects = {s for p in props for s, _, o in graph.triples((None, p, None))
                if isinstance(s, URIRef) and (clean(str(o)) == key or str(o) == label)}
    names = {str(o) for s in subjects for p in props for o in graph.objects(s, p)}
    return sorted(n for n in names if clean(n) != key and n != label)
