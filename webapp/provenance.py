"""SPARQL over all runs and the five provenance queries of one run (rows 2.7, 2.8).

`/api/sparql` goes through scoring/store.py's RunStore, which refuses anything but SELECT, ASK,
CONSTRUCT and DESCRIBE (pyoxigraph's query API cannot update in any case). The web app keeps its
own store in memory, loaded from the runs' graph.ttl files and refreshed (only changed files are
reloaded, by hash) at most every REFRESH_S seconds: the on-disk store $RUNS/.oxigraph belongs to
`score store`, and a second process holding it open would lock that command out.

`/api/queries/{n}` runs agent/queries.py's queries on the run's graph.ttl with rdflib, as
`agent query` does; parsed graphs are cached by the file's signature.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from agent import prov, queries
from agent.rundir import RunDir
from scoring.store import RunStore

from .files import BadRequest, Conflict, NotFound, signature
from .models import QueryResult, SparqlResult

REFRESH_S = 2.0
MAX_ROWS = 10_000


class Provenance:
    def __init__(self, runs_root: Path) -> None:
        self.runs_root = runs_root
        self._store: RunStore | None = None
        self._loaded_at = 0.0
        self._graphs: dict[str, tuple[tuple, Any]] = {}
        self._lock = threading.Lock()

    def store(self) -> RunStore:
        """The in-memory store, with every run's current graph.ttl loaded."""
        with self._lock:
            if self._store is None:
                self._store = RunStore(None)
            if time.monotonic() - self._loaded_at > REFRESH_S:
                self._store.load_all(self.runs_root)
                self._loaded_at = time.monotonic()
            return self._store

    def sparql(self, query: str, run_id: str | None = None) -> SparqlResult:
        store = self.store()
        if run_id is not None and run_id not in store.runs():
            raise NotFound(f"no graph.ttl loaded for run {run_id!r} (run `agent export-prov` on it)")
        try:
            with self._lock:
                result = store.query(query, run_id=run_id)
        except ValueError as exc:  # not a read-only query form
            raise BadRequest(str(exc)) from exc
        except (SyntaxError, OSError, RuntimeError) as exc:  # pyoxigraph: parse or evaluation error
            raise BadRequest(f"query failed: {exc}") from exc
        if "boolean" in result:
            return SparqlResult(vars=[], rows=[], boolean=result["boolean"])
        return SparqlResult(vars=result["vars"], rows=result["rows"][:MAX_ROWS])

    def graph(self, run: RunDir) -> Any:
        ttl = run.root / prov.TTL_FILE
        if not ttl.is_file():
            raise NotFound(f"{run.run_id} has no {prov.TTL_FILE} yet (run `agent export-prov` on it)")
        key = signature(ttl)
        with self._lock:
            hit = self._graphs.get(run.run_id)
        if hit and hit[0] == key:
            return hit[1]
        graph = prov.load(run)
        with self._lock:
            self._graphs[run.run_id] = (key, graph)
        return graph

    def query(self, run: RunDir, n: int, *, edge: str | None = None, fact: str | None = None,
              claim: str | None = None, step: int | None = None, agent: str | None = None,
              corpus: Path | None = None) -> QueryResult:
        """Query n (1-5) of agent/queries.py on one run, with the arguments `agent query` takes."""
        if n not in queries.QUERIES:
            raise NotFound(f"no provenance query {n}; they are 1-5")
        graph = self.graph(run)
        try:
            if n == 1:
                rows = queries.edge_to_passage(graph, edge)
            elif n == 2:
                rows = queries.fact_producers(graph, fact, claim)
            elif n == 3:
                rows = queries.claims_from(graph, step, agent)
            elif n == 4:
                if corpus is None:
                    raise Conflict("query 4 re-finds anchors in the corpus: set $CORPUS")
                rows = queries.unresolved_anchors(graph, corpus, corpus / "manifest.json")
            else:
                rows = queries.unsourced_facts(graph)
        except (OSError, ValueError) as exc:
            raise BadRequest(str(exc)) from exc
        return QueryResult(n=n, name=queries.QUERIES[n].__name__, run_id=run.run_id, rows=rows)
