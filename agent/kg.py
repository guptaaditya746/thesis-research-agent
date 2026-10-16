"""Knowledge graph from a run's claims (docs/earlier-work.md, build row 2.6).

Every accepted claim in claims.jsonl, from the research run (`origin` research) or from the
baseline's attach step (`origin` attach), becomes one edge s -p-> o. The edge keeps the claim id,
so each triple can be walked back to its claim, step and passage (agent/queries.py).

- Nodes: a subject or object that names a paper of corpus/manifest.json (`p12`, `p12.md`, any
  case) is that paper's node `paper:p12`; any other string is an entity node `entity:<slug>`,
  where strings equal after case folding and dropping punctuation are one node. Numbers and
  booleans, and the object of a DBLP datatype property (title, year, DOI), stay literals.
- Predicates stay free text (`text`). A fixed table (`PREDICATES`) maps common verbs to CS-KG 2.0
  or DBLP names; anything else becomes `ours:<camelCase of the text>`. Full canonicalisation
  against CS-KG is row 2.15, not this.
- Each edge also names the paper whose file holds the claim's quote (`evidence`), with the
  manifest id taken from the anchor's file name.

Output: runs/<id>/graph.json in canonical JSON (agent/canonical.py).
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import file_sha256, write_json
from .rundir import RunDir

GRAPH_FILE = "graph.json"

# CS-KG 2.0 ontology (CC BY 4.0, https://w3id.org/cskg/ontology#); DBLP RDF schema (CC0).
NAMESPACES = {
    "cskg": "https://w3id.org/cskg/ontology#",
    "dblp": "https://dblp.org/rdf/schema#",
    "ours": "urn:thesis-agent:vocab#",
}


@dataclass(frozen=True)
class Term:
    curie: str
    literal: bool = False  # the object is a value (title, year), never a node


def _table() -> dict[str, Term]:
    """Normalised predicate text (see `predicate_key`) -> mapped term."""
    groups: list[tuple[str, tuple[str, ...], bool]] = [
        # CS-KG relation verbs (the base properties; typed variants only when the text names them)
        ("cskg:uses", ("uses", "use", "utilizes", "utilises", "employs", "applies", "adopts"), False),
        ("cskg:improves", ("improves", "improveson", "enhances"), False),
        ("cskg:outperforms", ("outperforms", "beats", "surpasses"), False),
        ("cskg:proposes", ("proposes", "introduces", "presents"), False),
        ("cskg:based-on", ("basedon", "isbasedon", "buildson", "builtupon", "builton"), False),
        ("cskg:includes", ("includes", "contains", "comprises"), False),
        ("cskg:executes", ("executes", "performs", "runs"), False),
        ("cskg:executesMethod", ("executesmethod",), False),
        ("cskg:executesTask", ("executestask",), False),
        ("cskg:analyzes", ("analyzes", "analyses", "studies", "examines", "investigates"), False),
        ("cskg:analyzesTask", ("analyzestask", "analysestask"), False),
        ("cskg:analyzesMethod", ("analyzesmethod", "analysesmethod"), False),
        ("cskg:solves", ("solves", "addresses", "tackles"), False),
        ("cskg:produces", ("produces", "generates", "outputs"), False),
        ("cskg:predicts", ("predicts",), False),
        ("cskg:adapts", ("adapts", "finetunes"), False),
        # DBLP bibliographic properties
        ("dblp:authoredBy", ("authoredby", "author", "hasauthor", "writtenby"), False),
        ("dblp:publishedIn", ("publishedin", "venue", "appearsin"), False),
        ("dblp:title", ("title", "hastitle"), True),
        ("dblp:yearOfPublication", ("year", "yearofpublication", "publicationyear", "publishedinyear"), True),
        ("dblp:doi", ("doi", "hasdoi"), True),
    ]
    return {key: Term(curie, literal) for curie, keys, literal in groups for key in keys}


PREDICATES = _table()


def predicate_key(text: str) -> str:
    """Case-folded letters and digits only: `based on`, `based-on`, `basedOn` all give `basedon`."""
    return "".join(ch for ch in unicodedata.normalize("NFKC", text).casefold() if ch.isalnum())


def camel(text: str) -> str:
    """`evaluates on` -> `evaluatesOn`; an existing camelCase word is kept."""
    words = [w for w in re.split(r"[^\w]+|_", unicodedata.normalize("NFKC", text)) if w]
    if not words:
        return "relatedTo"
    first = words[0][:1].lower() + words[0][1:]
    return first + "".join(w[:1].upper() + w[1:] for w in words[1:])


def map_predicate(text: str) -> dict[str, Any]:
    term = PREDICATES.get(predicate_key(text))
    if term is None:
        term = Term(f"ours:{camel(text)}")
    prefix, local = term.curie.split(":", 1)
    return {"text": text, "curie": term.curie, "iri": NAMESPACES[prefix] + local, "vocabulary": prefix,
            "literal_object": term.literal}


def slug(label: str) -> str:
    """Node key: NFKC, case-folded, every run of non-alphanumerics one '-'."""
    folded = unicodedata.normalize("NFKC", label).casefold()
    return re.sub(r"[^\w]+|_", "-", folded).strip("-") or "-"


class Papers:
    """Paper ids of corpus/manifest.json (failed conversions included: they are still papers)."""

    def __init__(self, manifest: Path) -> None:
        data = json.loads(Path(manifest).read_text(encoding="utf-8"))
        self.ids = sorted(p["id"] for p in data["papers"])
        self._by_key = {i.casefold(): i for i in self.ids}

    def match(self, value: str) -> str | None:
        key = value.strip().casefold()
        if key.endswith(".md"):
            key = key[:-3]
        return self._by_key.get(key)


def load_claims(run: RunDir) -> list[dict[str, Any]]:
    """Accepted claim records of a run, in chain order."""
    lines = run.claims.read_text(encoding="utf-8").splitlines() if run.claims.exists() else []
    return [r for r in map(json.loads, lines) if r["status"] == "accepted"]


def build(run: RunDir, manifest: Path) -> dict[str, Any]:
    """The knowledge graph of one run as a JSON-ready dict (nodes and edges sorted by id)."""
    papers = Papers(manifest)
    config = run.load_config()
    manifest_sha = file_sha256(manifest)
    expected = config["hashes"]["corpus_manifest_sha256"]
    if manifest_sha != expected:
        raise ValueError(f"manifest {manifest} has sha256 {manifest_sha}, the run was made with {expected}")
    nodes: dict[str, dict[str, Any]] = {}

    def node(value: Any) -> str:
        paper = papers.match(value)
        if paper is not None:
            nid = f"paper:{paper}"
            nodes.setdefault(nid, {"id": nid, "kind": "paper", "label": paper, "paper": paper})
        else:
            nid = f"entity:{slug(value)}"
            nodes.setdefault(nid, {"id": nid, "kind": "entity", "label": value.strip()})
        return nid

    edges = []
    for record in load_claims(run):
        meta = record["custom_metadata"]
        anchor = record["used"]["anchor"]
        claim_id = record["generated"]["claim_id"]
        predicate = map_predicate(meta["p"])
        literal = predicate.pop("literal_object")
        edge: dict[str, Any] = {
            "id": "edge-" + claim_id.removeprefix("claim-"),
            "claim": claim_id, "origin": meta.get("origin", "research"),
            "step_id": record["step_id"], "agent_id": record["agent_id"],
            "source": node(str(meta["s"])), "predicate": predicate,
            "evidence": {"file": anchor["file"], "paper": papers.match(anchor["file"]),
                         "start": anchor["start"], "end": anchor["end"]},
        }
        o = meta["o"]
        if literal or not isinstance(o, str):
            edge["target"], edge["literal"] = None, o
        else:
            edge["target"], edge["literal"] = node(o), None
        edges.append(edge)
    return {
        "schema_version": 1, "run_id": run.run_id,
        "sources": {"claims_sha256": file_sha256(run.claims), "corpus_manifest_sha256": manifest_sha},
        "namespaces": dict(NAMESPACES),
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "edges": sorted(edges, key=lambda e: e["id"]),
    }


def write(run: RunDir, manifest: Path) -> tuple[Path, dict[str, Any]]:
    graph = build(run, manifest)
    path = run.root / GRAPH_FILE
    write_json(path, graph)
    return path, graph


def load(run: RunDir) -> dict[str, Any]:
    return json.loads((run.root / GRAPH_FILE).read_text(encoding="utf-8"))
