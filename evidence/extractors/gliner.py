"""`gliner_condition`, `gliner_metric` and `gliner_dataset`: a small NER model (GLiNER) behind an HTTP service.

The service (llm-setup, next to a model replica; on this PC the stand-in evidence/tests/fake_gliner.py) answers

    GET  {url}/info     -> {"model": <model name>}
    POST {url}/predict  {"text": chunk, "labels": [str], "threshold": float}
                        -> {"entities": [{"start", "end", "text", "label", "score"}]}

Each extractor cuts the task's parts into chunks of at most `chunk_chars` (gold/chunks.py, section-aware), sends
one /predict per chunk with its type's labels, and maps each entity's chunk offsets back to the document. An
entity whose offsets do not hold its text is rejected (`not_found`), never moved. The item's role (condition)
or canonical (metric) comes from the regex term lists (terms.py) found in the entity text, `other` when none
matches; a dataset item is `{name}`. Spans are on the entity text, with the type's first span role.

Kind `model`: every /predict is recorded like a model call (request, response or error; no usage), so it lands
in the record cache and in the run's calls.jsonl. The extractor's config, and so its id, holds the model name
from /info (asked once per process and URL), the labels and the threshold: another GLiNER model never hits old
cache records. The URL is not in the id. `model` may be pinned in the protocol config, and the engine sets it to
the model recorded with the run (Settings.gliner_model) so a replay without the service builds the same id; the
service must then serve that model. Without a URL (`gliner_url` from the engine, else $GLINER_URL), or when /info fails,
`available()` is False and `extract` returns an `unavailable` error; a timeout or connection error on /predict
is a `service_call` error. Both are results, not exceptions, so a cascade goes on. Own module, so every
existing extractor keeps its id.
"""
from __future__ import annotations

import os
import threading
from typing import Any

import httpx

from gold.chunks import split

from ..contract import (Coverage, ExtractionError, ExtractionResult, ExtractionTask, ExtractorSpec, Item, Rejected,
                        RunContext, Span, digest)
from . import base, regex, terms

VERSION = 1
SOURCES = (base.HERE / "gliner.py", base.HERE / "terms.py", base.HERE / "regex.py", base.ROOT / "gold" / "chunks.py",
           base.ROOT / "evidence" / "evidence_types.py", *base.SHARED_SOURCES)   # regex.py: INJECTED
CODE_SHA256 = base.source_sha256(*SOURCES)

LABELS = {"condition": ["method", "system variant", "baseline model"], "metric": ["evaluation metric"],
          "dataset": ["dataset"]}
ROLE = {"condition": "condition_label", "metric": "metric_label", "dataset": "dataset_label"}
DEFAULTS: dict[str, Any] = {"threshold": 0.5, "chunk_chars": 1500, "max_spans": 8}
TIMEOUT = 10.0
URL_KEY = "gliner_url"   # what the engine adds (Settings.gliner_url); not part of the id

_INFO: dict[str, dict[str, Any] | None] = {}   # url -> /info reply, or None when it failed (per process)
_LOCK = threading.Lock()


def forget() -> None:
    """Drop the per-process /info cache (tests)."""
    with _LOCK:
        _INFO.clear()


def info(url: str | None, timeout: float = TIMEOUT) -> dict[str, Any] | None:
    """The service's /info reply, asked once per process and URL; None without a URL or when it fails."""
    if not url:
        return None
    with _LOCK:
        if url in _INFO:
            return _INFO[url]
        try:
            reply = httpx.get(f"{url.rstrip('/')}/info", timeout=timeout)
            reply.raise_for_status()
            body = reply.json()
            found = body if isinstance(body, dict) and isinstance(body.get("model"), str) else None
        except (httpx.HTTPError, ValueError):
            found = None
        _INFO[url] = found
        return found


class GlinerExtractor:
    evidence_type: str = ""
    name: str = ""

    def __init__(self, config: dict[str, Any]) -> None:
        given = {k: v for k, v in config.items() if k in regex.INJECTED}
        url = config[URL_KEY] if URL_KEY in config else os.environ.get("GLINER_URL")
        self.url = url.rstrip("/") if url else None
        self.timeout = float(config.get("timeout", TIMEOUT))
        self.labels = [str(x) for x in (config.get("labels") or LABELS[self.evidence_type])]
        self.threshold = float(config.get("threshold", DEFAULTS["threshold"]))
        self.chunk_chars = int(config.get("chunk_chars", DEFAULTS["chunk_chars"]))
        self.max_spans = int(config.get("max_spans", DEFAULTS["max_spans"]))
        served = info(self.url, self.timeout)
        self.served = served["model"] if served else None
        self.model = config.get("model") or self.served
        roles = list(given.get("roles") or [])
        self.role = roles[0] if roles else ROLE[self.evidence_type]
        self.given = given
        # a protocol's own metric wording ([pattern, canonical, higher_is_better] rows), as regex_metric takes it
        self.metrics = [(str(p), str(k), bool(h)) for p, k, h in config["metrics"]] if config.get("metrics") else None
        self.spec = ExtractorSpec(name=self.name, version=VERSION, kind="model",
                                  evidence_types=(self.evidence_type,),  # type: ignore[arg-type]
                                  code_sha256=CODE_SHA256,
                                  config={**given, **({"metrics": [list(m) for m in self.metrics]} if self.metrics else {}),
                                          "service": "gliner", "model": self.model, "labels": self.labels,
                                          "threshold": self.threshold, "chunk_chars": self.chunk_chars,
                                          "max_spans": self.max_spans},
                                  determinism="near_exact")

    def available(self) -> bool:
        return self.served is not None and self.model == self.served

    def _why_unavailable(self) -> str:
        if not self.url:
            return "no GLiNER service: GLINER_URL is not set"
        if self.served is None:
            return "the GLiNER service did not answer GET /info"
        return f"the GLiNER service serves {self.served}, not {self.model} (pinned or recorded with the run)"

    def extract(self, task: ExtractionTask, ctx: RunContext) -> ExtractionResult:
        text = ctx.text()
        parts = base.ranges(task, text)
        if not self.available():
            return ExtractionResult(extractor_id=self.spec.extractor_id, task_sha256=task.task_sha256, status="error",
                                    error=ExtractionError(reason="unavailable", detail=self._why_unavailable()),
                                    coverage=tuple(Coverage(range=p, status="error", reason="unavailable")
                                                   for p in parts)).canonical()
        recorder = ctx.llm()   # type: ignore[attr-defined] - the engine's context records every call
        chunks = [(a + ca, a + cb) for a, b in parts for ca, cb, _ in split(text[a:b], self.chunk_chars)]
        found: dict[str, tuple[dict[str, Any], list[Span]]] = {}
        rejected: list[Rejected] = []
        coverage: list[Coverage] = []
        calls: list[str] = []
        errors: list[str] = []
        for a, b in chunks:
            entities, call_id, error = self._predict(recorder, text[a:b])
            calls.append(call_id)
            if error is not None:
                errors.append(error)
                coverage.append(Coverage(range=(a, b), status="error", reason=error))
                continue
            kept = 0
            for e in entities:
                start, end = a + e["start"], a + e["end"]
                if not (a <= start < end <= b) or text[start:end] != e["text"]:
                    rejected.append(Rejected(evidence_type=self.evidence_type, fields={}, quotes=(str(e["text"]),),  # type: ignore[arg-type]
                                             reason="not_found", detail="entity offsets do not hold its text"))
                    continue
                start, end = _trim(text, start, end)
                if start >= end:
                    continue
                fields = self.fields(text[start:end])
                if fields is None:
                    rejected.append(Rejected(evidence_type=self.evidence_type, fields={}, quotes=(text[start:end],),  # type: ignore[arg-type]
                                             reason="schema", detail="no term matches and other is not allowed"))
                    continue
                entry = found.setdefault(digest(fields), (fields, []))
                if len(entry[1]) < self.max_spans and all(s.selector["start"] != start or s.selector["end"] != end
                                                          for s in entry[1]):
                    entry[1].append(base.span(task, text, start, end, self.role))
                kept += 1
            coverage.append(Coverage(range=(a, b), status="found" if kept else "none", found=kept))
        items: list[Item] = base.group(self.evidence_type, [(f, {}, spans) for f, spans in found.values()])  # type: ignore[arg-type]
        status = "ok" if not errors else ("error" if len(errors) == len(chunks) else "partial")
        error = ExtractionError(reason="service_call", detail="; ".join(sorted(set(errors)))[:300]) if errors else None
        return ExtractionResult(extractor_id=self.spec.extractor_id, task_sha256=task.task_sha256, status=status,
                                error=error, items=tuple(items), rejected=tuple(rejected), coverage=tuple(coverage),
                                model_calls=tuple(calls)).canonical()

    def _predict(self, recorder: Any, chunk: str) -> tuple[list[dict[str, Any]], str, str | None]:
        """One recorded /predict: (entities at chunk offsets, record id, error or None)."""
        body = {"text": chunk, "labels": self.labels, "threshold": self.threshold}
        # /predict names no model: the record keeps what /info said, under that name
        request = {"service": "gliner", "endpoint": "/predict", "model_from_info": self.served, **body}
        call_id = f"gl-{digest([request, len(recorder.records)])[:16]}"
        record: dict[str, Any] = {"id": call_id, "request": request}
        recorder.records.append(record)
        try:
            reply = httpx.post(f"{self.url}/predict", json=body, timeout=self.timeout)
            reply.raise_for_status()
            entities = _entities(reply.json(), self.labels, self.threshold)
        except httpx.TimeoutException:
            record["error"] = f"timeout after {self.timeout:g} s"
            return [], call_id, record["error"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"[:300]
            return [], call_id, record["error"]
        record["response"] = {"entities": entities}
        return entities, call_id, None

    def fields(self, name: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def _enum(self, key: str) -> list[str] | None:
        return self.given.get("field_schema", {}).get("properties", {}).get(key, {}).get("enum")


def _entities(body: Any, labels: list[str], threshold: float) -> list[dict[str, Any]]:
    """The reply's entities of the asked labels at or above the threshold, in order (a malformed reply raises)."""
    out = []
    for e in body["entities"]:
        entity = {"start": int(e["start"]), "end": int(e["end"]), "text": str(e["text"]), "label": str(e["label"]),
                  "score": float(e["score"])}
        if entity["label"] in labels and entity["score"] >= threshold:
            out.append(entity)
    return sorted(out, key=lambda e: (e["start"], e["end"], e["label"]))


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


class GlinerCondition(GlinerExtractor):
    evidence_type, name = "condition", "gliner_condition"

    def fields(self, name: str) -> dict[str, Any] | None:
        enum = self._enum("role")
        conditions = terms.CONDITIONS
        roles = list(enum or [*conditions, "other"])
        treatment = (self.given.get("compare") or {}).get("treatment")
        found = terms.find_conditions(name, terms.condition_patterns(conditions), roles, treatment=treatment)
        role = found[0].key if found else "other"
        if enum is not None and role not in enum:
            return None
        return {"label": name, "role": role}


class GlinerMetric(GlinerExtractor):
    evidence_type, name = "metric", "gliner_metric"

    def fields(self, name: str) -> dict[str, Any] | None:
        found = terms.find_all(name, self.metrics or terms.METRICS)
        canonical, higher = (found[0].key, found[0].higher_is_better) if found else ("other", True)
        enum = self._enum("canonical")
        if enum is not None and canonical not in enum:
            return None
        return {"name": name, "canonical": canonical, "higher_is_better": higher}


class GlinerDataset(GlinerExtractor):
    evidence_type, name = "dataset", "gliner_dataset"

    def fields(self, name: str) -> dict[str, Any] | None:
        return {"name": name}


FACTORIES = {"gliner_condition": GlinerCondition, "gliner_metric": GlinerMetric, "gliner_dataset": GlinerDataset}
