"""Real word lists: the downloads, the label index for the name-clash check, and the frozen subsets.

Downloads (big, never committed) live in `CACHE/vocab/`: MeSH descriptors and supplementary records (XML), ChEBI
names (TSV) and QUDT units (Turtle). `fetch()` gets them; their sha256 go into `data/seed/vocab/sources.json`.
`freeze()` writes the small subsets the seed links to (`mesh-subset.ttl`, `qudt-subset.ttl`) with rdflib.
"""
from __future__ import annotations

import csv
import datetime
import gzip
import hashlib
import json
import re
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path

import rdflib
from rdflib import RDFS, SKOS, Literal, Namespace, URIRef

from evqa.paths import CACHE, VOCAB

MESH = Namespace("http://id.nlm.nih.gov/mesh/")
QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")
YEAR = 2026
SOURCES = {
    "mesh_desc": (f"desc{YEAR}.gz", f"https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc{YEAR}.gz"),
    "mesh_supp": (f"supp{YEAR}.gz", f"https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/supp{YEAR}.gz"),
    "chebi": ("chebi-names.tsv.gz", "https://ftp.ebi.ac.uk/pub/databases/chebi/flat_files/names.tsv.gz"),
    "qudt": ("qudt-units.ttl", "https://qudt.org/vocab/unit/"),
}
INDEX = "labels.tsv.gz"


def folder() -> Path:
    return CACHE / "vocab"


def norm(text: str) -> str:
    """Lower case, accents dropped, only letters and digits: 'Velo-Trazin' and 'velotrazin' are the same name."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.lower())


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch(force: bool = False) -> dict[str, str]:
    """Download every source into the cache folder; returns {name: sha256}."""
    out = {}
    for name, (file, url) in SOURCES.items():
        path = folder() / file
        if force or not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            accept = "text/turtle" if name == "qudt" else "*/*"
            req = urllib.request.Request(url, headers={"Accept": accept})
            with urllib.request.urlopen(req, timeout=1200) as r:   # noqa: S310 - fixed https URLs
                path.with_suffix(".part").write_bytes(r.read())
            path.with_suffix(".part").rename(path)
        out[name] = sha256(path)
    return out


def _records(path: Path, tag: str, ui: str, name: str) -> Iterator[tuple[str, str, list[str]]]:
    """(id, preferred name, all term strings) of each MeSH record, streamed."""
    with gzip.open(path) as f:
        for _, el in ET.iterparse(f):
            if el.tag != tag:
                continue
            terms = [t.text for t in el.findall("ConceptList/Concept/TermList/Term/String") if t.text]
            yield el.findtext(ui, ""), el.findtext(f"{name}/String", ""), terms
            el.clear()


def _all_labels() -> Iterator[tuple[str, str]]:
    """(label, source id) of every name in MeSH (descriptors + supplementary records) and ChEBI."""
    for key, tag, ui, name in (("mesh_desc", "DescriptorRecord", "DescriptorUI", "DescriptorName"),
                               ("mesh_supp", "SupplementalRecord", "SupplementalRecordUI", "SupplementalRecordName")):
        for rid, pref, terms in _records(folder() / SOURCES[key][0], tag, ui, name):
            for label in {pref, *terms}:
                yield label, f"mesh:{rid}"
    with gzip.open(folder() / SOURCES["chebi"][0], "rt", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row.get("language_code", "en") == "en":
                yield row["ascii_name"] or row["name"], f"chebi:{row['compound_id']}"


def label_index() -> dict[str, tuple[str, str]]:
    """{normalized label: (label, source id)} over MeSH + ChEBI, built once and cached as a TSV."""
    path = folder() / INDEX
    if not path.is_file():
        seen: dict[str, tuple[str, str]] = {}
        for label, src in _all_labels():
            key = norm(label)
            if len(key) >= 3 and key not in seen:
                seen[key] = (label, src)
        with gzip.open(path.with_suffix(".part"), "wt", encoding="utf-8") as f:
            for key in sorted(seen):
                label = " ".join(seen[key][0].split())   # labels may hold tabs or newlines
                f.write(f"{key}\t{label}\t{seen[key][1]}\n")
        path.with_suffix(".part").rename(path)
    out = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            key, label, src = line.rstrip("\n").split("\t")
            out[key] = (label, src)
    return out


def mesh_subset(ids: set[str]) -> rdflib.Graph:
    """The MeSH descriptors `ids` with their preferred name (skos:prefLabel) and entry terms (skos:altLabel)."""
    g = rdflib.Graph()
    g.bind("mesh", MESH)
    g.bind("skos", SKOS)
    found = set()
    for rid, pref, terms in _records(folder() / SOURCES["mesh_desc"][0], "DescriptorRecord", "DescriptorUI",
                                     "DescriptorName"):
        if rid in ids:
            found.add(rid)
            g.add((MESH[rid], SKOS.prefLabel, Literal(pref)))
            for t in sorted(set(terms) - {pref}):
                g.add((MESH[rid], SKOS.altLabel, Literal(t)))
    if missing := ids - found:
        raise ValueError(f"MeSH ids not in desc{YEAR}: {sorted(missing)}")
    return g


def qudt_subset(units: set[URIRef]) -> rdflib.Graph:
    """The QUDT units `units` with label, symbol, conversion factors and quantity kind (for norm.py)."""
    full = rdflib.Graph()
    full.parse(folder() / SOURCES["qudt"][0], format="turtle")
    g = rdflib.Graph()
    g.bind("unit", UNIT)
    g.bind("qudt", QUDT)
    keep = (RDFS.label, QUDT.symbol, QUDT.conversionMultiplier, QUDT.conversionOffset, QUDT.hasQuantityKind,
            QUDT.ucumCode)
    for u in sorted(units):
        if (u, None, None) not in full:
            raise ValueError(f"unit {u} not in QUDT")
        g.add((u, rdflib.RDF.type, QUDT.Unit))
        for p in keep:
            for o in full.objects(u, p):
                if not isinstance(o, Literal) or o.language in (None, "en"):
                    g.add((u, p, o))
    return g


def freeze(mesh_ids: set[str], units: set[URIRef]) -> dict[str, str]:
    """Write the subsets and `sources.json` (what was downloaded, when, with which sha256)."""
    VOCAB.mkdir(parents=True, exist_ok=True)
    head = "# Frozen subset made by `evqa seed vocab` from {src} (sha256 {sha}). Do not edit by hand.\n"
    files = {"mesh-subset.ttl": (mesh_subset(mesh_ids), "mesh_desc"), "qudt-subset.ttl": (qudt_subset(units), "qudt")}
    hashes = {name: sha256(folder() / SOURCES[name][0]) for name in SOURCES}
    for file, (graph, src) in files.items():
        text = graph.serialize(format="turtle")
        (VOCAB / file).write_text(head.format(src=SOURCES[src][1], sha=hashes[src]) + text, encoding="utf-8")
    sources = {name: {"url": url, "file": file, "sha256": hashes[name]} for name, (file, url) in SOURCES.items()}
    (VOCAB / "sources.json").write_text(json.dumps({"made": datetime.date.today().isoformat(), "sources": sources},
                                                   indent=2) + "\n", encoding="utf-8")
    return hashes

