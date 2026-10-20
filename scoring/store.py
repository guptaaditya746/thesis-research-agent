"""SPARQL over every run's PROV-O export (graph.ttl), with pyoxigraph.

One named graph per run, `urn:thesis-agent:run:<run_id>` (the run-scoped IRI prefix agent/prov.py
uses), so a query can address one run with GRAPH or all runs through the union default graph.
The store is a cache: it can always be rebuilt from the run directories, and a run whose graph.ttl
changed (by hash) is reloaded. Queries are read-only: SELECT, ASK, CONSTRUCT and DESCRIBE, without
SERVICE (pyoxigraph would send an HTTP request to the IRI a SERVICE clause names; `federated`).
`score store <runs_root>` loads every run below the root into $RUNS/.oxigraph (`load_tree`);
`score sparql <query-file> [--run ID]` queries it (scoring/cli.py).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from pyoxigraph import BlankNode, Literal, NamedNode, QueryBoolean, QuerySolutions, RdfFormat, Store

from jsonio import file_sha256

TTL_FILE = "graph.ttl"
LOADED_FILE = "loaded.json"  # run_id -> sha256 of the graph.ttl in the store
# Prologue (comments, PREFIX and BASE declarations), then the query form.
READ_ONLY = re.compile(r"^\s*(?:#[^\n]*\n\s*|PREFIX\s+[^\s:]*:\s*<[^>]*>\s*|BASE\s*<[^>]*>\s*)*"
                       r"(SELECT|ASK|CONSTRUCT|DESCRIBE)\b", re.I)
# What a query may hold that is not SPARQL keywords: string literals (long forms first), IRIs and
# comments. They are blanked before looking for SERVICE, so a literal "service" is no keyword.
NOT_KEYWORDS = re.compile(r"'''.*?'''|\"\"\".*?\"\"\"|'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\"|<[^<>\"{}|^`\\\s]*>"
                          r"|#[^\n]*", re.S)
SERVICE = re.compile(r"\bSERVICE\b", re.I)


def federated(sparql: str) -> bool:
    """Whether the query has a SERVICE clause. pyoxigraph evaluates one by sending an HTTP request to
    the IRI it names, so the server would fetch any URL a query (or a prompt-injected chat agent)
    names: a federated query is refused like an update. The check is on the query's text with its
    literals, IRIs and comments blanked; a word SERVICE anywhere else counts (refusing too much is safe)."""
    return bool(SERVICE.search(NOT_KEYWORDS.sub(" ", sparql)))


def run_graph(run_id: str) -> NamedNode:
    return NamedNode(f"urn:thesis-agent:run:{run_id}")


def term_json(term: Any) -> Any:
    """A SPARQL result term as JSON: IRIs and blank nodes as strings, literals as their value."""
    if term is None:
        return None
    if isinstance(term, NamedNode):
        return term.value
    if isinstance(term, BlankNode):
        return f"_:{term.value}"
    if isinstance(term, Literal):
        return term.value
    return str(term)


class RunStore:
    """An on-disk pyoxigraph store (or in memory with path=None) over run directories."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else None
        if self.path:
            self.path.mkdir(parents=True, exist_ok=True)
        self.store = Store(str(self.path)) if self.path else Store()
        self._loaded: dict[str, str] = self._read_loaded()

    def _read_loaded(self) -> dict[str, str]:
        if self.path and (self.path / LOADED_FILE).is_file():
            return json.loads((self.path / LOADED_FILE).read_text(encoding="utf-8"))
        return {}

    def _write_loaded(self) -> None:
        if self.path:
            (self.path / LOADED_FILE).write_text(json.dumps(self._loaded, indent=1, sort_keys=True), encoding="utf-8")

    def load_run(self, run_dir: Path | str) -> bool:
        """Load (or reload) one run's graph.ttl; False when it has none or it is unchanged."""
        run_dir = Path(run_dir)
        ttl = run_dir / TTL_FILE
        if not ttl.is_file():
            return False
        digest = file_sha256(ttl)
        if self._loaded.get(run_dir.name) == digest:
            return False
        graph = run_graph(run_dir.name)
        self.store.clear_graph(graph)
        self.store.load(path=str(ttl), format=RdfFormat.TURTLE, to_graph=graph)
        self._loaded[run_dir.name] = digest
        self._write_loaded()
        return True

    def load_all(self, runs_root: Path | str) -> list[str]:
        """Load every run directory under runs_root that has a graph.ttl; returns the runs (re)loaded."""
        root = Path(runs_root)
        return [d.name for d in sorted(root.iterdir()) if d.is_dir() and self.load_run(d)] if root.is_dir() else []

    def load_tree(self, runs_root: Path | str) -> dict[str, Any]:
        """Load every graph.ttl below runs_root, nested run roots (runs/m4-72/...) included.

        A run directory (one with graph.ttl or config.json) is not searched further, nor is a hidden
        directory (.oxigraph, .jobs). Run ids are directory names, so a second run directory with an
        id already seen is skipped and reported, not loaded over the first.
        """
        found: dict[str, Path] = {}
        duplicates: list[str] = []
        for top, dirs, files in os.walk(runs_root):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            if TTL_FILE in files or "config.json" in files:
                dirs[:] = []
                if TTL_FILE in files:
                    run = Path(top)
                    if run.name in found:
                        duplicates.append(str(run))
                    else:
                        found[run.name] = run
        loaded = [name for name, run in sorted(found.items()) if self.load_run(run)]
        return {"runs": sorted(found), "loaded": loaded, "duplicates": duplicates}

    def runs(self) -> list[str]:
        return sorted(self._loaded)

    def query(self, sparql: str, *, run_id: str | None = None) -> dict[str, Any]:
        """Run a read-only query; `run_id` restricts the default graph to that run."""
        if not READ_ONLY.match(sparql):
            raise ValueError("only SELECT, ASK, CONSTRUCT and DESCRIBE queries are allowed")
        if federated(sparql):
            raise ValueError("SERVICE (federated query) is not allowed: the store only reads the runs' graphs")
        kwargs: dict[str, Any] = ({"default_graph": run_graph(run_id)} if run_id
                                  else {"use_default_graph_as_union": True})
        result = self.store.query(sparql, **kwargs)
        if isinstance(result, QueryBoolean):
            return {"boolean": bool(result)}
        if isinstance(result, QuerySolutions):
            names = [v.value for v in result.variables]
            return {"vars": names, "rows": [{n: term_json(sol[n]) for n in names} for sol in result]}
        triples = [[term_json(t.subject), term_json(t.predicate), term_json(t.object)] for t in result]
        return {"vars": ["s", "p", "o"], "rows": [dict(zip(("s", "p", "o"), t)) for t in triples]}
