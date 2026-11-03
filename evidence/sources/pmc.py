"""PMC JATS XML (the PMC OAI service or an OA package) to Markdown; table cells keep their exact text."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from evidence.sources import markdown_table


def _local(tag: object) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _text(node: ET.Element) -> str:
    return " ".join("".join(node.itertext()).split())


def _first(node: ET.Element, name: str) -> ET.Element | None:
    return next((n for n in node.iter() if _local(n.tag) == name), None)


def _child(node: ET.Element, name: str) -> ET.Element | None:
    return next((c for c in node if _local(c.tag) == name), None)


def _table(table: ET.Element) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in (n for n in table.iter() if _local(n.tag) == "tr"):
        row: list[str] = []
        for cell in (c for c in tr if _local(c.tag) in ("td", "th")):
            row.append(_text(cell))
            row.extend([""] * (int(cell.get("colspan", "1") or 1) - 1))
        rows.append(row)
    return rows


def _walk(node: ET.Element, out: list[str], depth: int) -> None:
    for child in node:
        name = _local(child.tag)
        if name == "sec":
            title = _child(child, "title")
            if title is not None:
                out.append(f"{'#' * min(depth + 1, 6)} {_text(title)}")
            _walk(child, out, depth + 1)
        elif name == "p":
            out.append(_text(child))
        elif name == "table-wrap":
            cap, label = _child(child, "caption"), _child(child, "label")
            head = " ".join(t for t in (_text(label) if label is not None else "",
                                        _text(cap) if cap is not None else "") if t)
            if head:
                out.append(f"**{head}**")
            table = _first(child, "table")
            if table is not None:
                out.append(markdown_table(_table(table)))
        elif name in ("body", "abstract", "boxed-text"):
            _walk(child, out, depth)


def jats_markdown(data: bytes) -> str:
    """Markdown of the first <article> in `data` (a bare JATS file or an OAI-PMH envelope). ValueError when
    the bytes are not XML, hold no article or no body."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"not XML ({exc})") from exc
    article = root if _local(root.tag) == "article" else _first(root, "article")
    if article is None:
        raise ValueError("no <article> in the XML")
    out: list[str] = []
    title = _first(article, "article-title")
    if title is not None:
        out.append(f"# {_text(title)}")
    abstract = _first(article, "abstract")
    if abstract is not None:
        out.append("## Abstract")
        _walk(abstract, out, 1)
    body = _first(article, "body")
    if body is None:
        raise ValueError("no <body> in the article")
    _walk(body, out, 1)
    return "\n\n".join(out).strip() + "\n"
