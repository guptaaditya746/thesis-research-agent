"""The evidence graph (graph.json): documents and evidence items as nodes, their relations as edges.

Edges: `in_document` (item -> its document), `condition` and `metric` (measurement -> the items its links
name), and `supports` / `contradicts` (the rag measurement a study's effect rests on -> the baseline
measurement it was compared with, as synthesis decided; a neutral study has no such edge). Nodes and
edges are sorted, so the same evidence gives the same file.
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
    for entry in answer["studies"]:
        if entry["direction"] in ("supports", "contradicts"):
            edges.append({"src": entry["rag"]["measurement"], "dst": entry["baseline"]["measurement"],
                          "rel": entry["direction"]})
    order = {p.id: n for n, p in enumerate(papers)}
    nodes.sort(key=lambda n: (order[n["id"] if n["type"] == "document" else n["document"]], n["type"] != "document",
                              n["id"]))
    edges.sort(key=lambda e: (e["src"], e["rel"], e["dst"]))
    return {"nodes": nodes, "edges": edges}
