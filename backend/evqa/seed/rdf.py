"""One lock around rdflib SPARQL: its parser (pyparsing) is not thread-safe, and the web app serves requests from
several threads at once ("missing 1 required positional argument" when two queries parse together)."""
from __future__ import annotations

import threading
from typing import Any

from rdflib import Graph

LOCK = threading.RLock()


def query(g: Graph, text: str) -> list[Any]:
    with LOCK:
        return list(g.query(text))
