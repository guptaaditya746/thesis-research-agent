"""The three S1 checks of a seed, written to `check.json` beside it:

1. shapes:  seed + glue + vocab subsets conform to shapes.ttl (pyshacl);
2. names:   0 made-up names clash with a MeSH/ChEBI label (re-judged now when the label index is cached);
3. split:   0 made-up items or papers are in both the practice and the test split.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyshacl
from rdflib import Graph

from evqa.paths import SCHEMA, VOCAB, domain_dir
from evqa.seed import names as names_mod
from evqa.seed import vocab
from evqa.seed.rdf import query as locked_query

SPLIT_OVERLAP = """
PREFIX ex: <https://w3id.org/evqa/seed#>
SELECT DISTINCT ?item WHERE {
  ?r1 ex:reportedIn/ex:split "practice" . ?r2 ex:reportedIn/ex:split "test" .
  { ?r1 ex:subject ?item } UNION { ?r1 ex:comparator ?item }
  { ?r2 ex:subject ?item } UNION { ?r2 ex:comparator ?item }
  ?item ex:madeUp true .
}"""


def full_graph(domain: str) -> Graph:
    g = Graph()
    g.parse(domain_dir(domain) / "seed.ttl")
    g.parse(SCHEMA / "glue.ttl")
    for f in sorted(VOCAB.glob("*.ttl")):
        g.parse(f)
    return g


def shapes(g: Graph) -> dict[str, Any]:
    conforms, report, text = pyshacl.validate(g, shacl_graph=str(SCHEMA / "shapes.ttl"), inference="none",
                                              advanced=True)
    return {"conforms": bool(conforms), "report": text if not conforms else ""}


def name_clashes(domain: str) -> dict[str, Any]:
    data = json.loads((domain_dir(domain) / "names.json").read_text(encoding="utf-8"))
    picked = [s["name"] for s in data["slots"].values()]
    index_file = vocab.folder() / vocab.INDEX
    rows = []
    if index_file.is_file():
        index = vocab.label_index()
        for i, name in enumerate(picked):
            rows.append(names_mod.judge(name, index, picked[:i]))
        mode = "re-judged against the label index now"
    else:
        rows = [s["checked"][-1] for s in data["slots"].values()]
        mode = "stored verdicts (label index not cached here)"
    clashes = [r for r in rows if not r["ok"]]
    return {"count": len(clashes), "mode": mode, "names": rows}


def split_overlap(g: Graph) -> dict[str, Any]:
    items = sorted(str(r.item) for r in locked_query(g, SPLIT_OVERLAP))
    return {"count": len(items), "items": items}


def run(domain: str) -> dict[str, Any]:
    g = full_graph(domain)
    result = {"shapes": shapes(g), "name_clashes": name_clashes(domain), "split_overlap": split_overlap(g)}
    result["pass"] = (result["shapes"]["conforms"] and result["name_clashes"]["count"] == 0
                      and result["split_overlap"]["count"] == 0)
    path: Path = domain_dir(domain) / "check.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result
