"""The evidence graph (graph.json): documents and evidence items as nodes, their relations as edges.

Edges: `in_document` (item -> its document), `condition` and `metric` (measurement -> the items its links
name), and `supports` / `contradicts` (the treatment measurement a study's effect rests on -> the control
measurement it was compared with, as synthesis decided; a neutral study has no such edge), and
`duplicate_of` (a document the synthesis flagged as a duplicate -> the earlier document it repeats;
docs/evidence-system.md F1). Nodes and edges are sorted, so the same evidence gives the same file. The
PROV export (evidence/prov.py) needs nothing more: a duplicate's items are among the items the synthesis
`used`, as every study's are.
"""
from __future__ import annotations

from typing import Any

from .contract import Item
from .rundir import Paper


def build(papers: list[Paper], items: dict[str, list[Item]], answer: dict[str, Any]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    for paper in papers:
        nodes.append({"id": paper.id, "type": "document", "file": paper.file, "sha256": paper.sha256})
        for item in items.get(paper.id, []):
            nodes.append({"id": item.item_id, "type": item.evidence_type, "document": paper.id, "fields": item.fields,
                          "links": item.links, "found_by": list(item.found_by), "spans": len(item.spans)})
            edges.append({"src": item.item_id, "dst": paper.id, "rel": "in_document"})
            for name, target in sorted(item.links.items()):
                edges.append({"src": item.item_id, "dst": target, "rel": name})
    for entry in answer.get("studies", []):   # an inventory answer has no studies; only effect studies pair
        if entry.get("direction") in ("supports", "contradicts") and entry.get("treatment"):
            edges.append({"src": entry["treatment"]["measurement"], "dst": entry["control"]["measurement"],
                          "rel": entry["direction"]})
        if entry.get("duplicate_of"):
            edges.append({"src": entry["document"], "dst": entry["duplicate_of"], "rel": "duplicate_of"})
    order = {p.id: n for n, p in enumerate(papers)}
    nodes.sort(key=lambda n: (order[n["id"] if n["type"] == "document" else n["document"]], n["type"] != "document",
                              n["id"]))
    edges.sort(key=lambda e: (e["src"], e["rel"], e["dst"]))
    return {"nodes": nodes, "edges": edges}
