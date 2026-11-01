"""`gliner_condition`, `gliner_metric` and `gliner_dataset`: a small NER model (GLiNER) behind an HTTP service.

The service (llm-setup, next to a model replica; on this PC the stand-in evidence/tests/fake_gliner.py) answers

    GET  {url}/info     -> {"model": <model name>}
    POST {url}/predict  {"text": chunk, "labels": [str], "threshold": float}
                        -> {"entities": [{"start", "end", "text", "label", "score"}]}

Each extractor cuts the task's parts into chunks of at most `chunk_chars` (gold/chunks.py, section-aware), sends
one /predict per chunk with its type's labels, and maps each entity's chunk offsets back to the document. An
entity whose offsets do not hold its text is rejected (`not_found`), never moved. The item's role (condition)
or canonical (metric) comes from the regex term lists in the config (the domain pack's words or the protocol's)
found in the entity text, `other` when none matches; a dataset item is `{name}`. Spans are on the entity text, with the type's first span role.

Kind `model`: every /predict is recorded like a model call (request, response or error; no usage), so it lands
in the record cache and in the run's calls.jsonl. The extractor's config, and so its id, holds the model name
from /info, the labels and the threshold: another GLiNER model never hits old cache records. The URL is not in the
id. `model` may be pinned in the protocol config, and the engine sets it to the model recorded with the run
(Settings.gliner_model) so a replay without the service builds the same id; the service must then serve that model.

/info: a reply is kept per process and URL. A failed /info is not kept: `available()` asks again on a later step,
at most once every RETRY_S seconds per URL (the other threads do not wait for that request; they see the service
as down until it answers), so a service that was still loading when the run started is used from the step after
it comes up, and a dead one costs one refused connection a minute. An extractor built while the service was down
has model None in its id; when /info first answers, it takes the served model (its id changes to the one a run
with the service up from the start has) and the engine records that model in run.json.

Without a URL (`gliner_url` from the engine, else $GLINER_URL), or while /info fails, `available()` is False and
`extract` returns an `unavailable` error (the engine skips the step before calling it); a timeout or connection
error on /predict is a `service_call` error. Both are results, not exceptions, so a cascade goes on. Own module,
so every existing extractor keeps its id.
"""
from __future__ import annotations

import os
import threading
import time
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

ROLE = {"condition": "condition_label", "metric": "metric_label", "dataset": "dataset_label"}
DEFAULTS: dict[str, Any] = {"threshold": 0.5, "chunk_chars": 1500, "max_spans": 8}
TIMEOUT = 10.0
URL_KEY = "gliner_url"   # what the engine adds (Settings.gliner_url); not part of the id

RETRY_S = 60.0   # a failed /info is asked again at most this often (per process and URL)

_INFO: dict[str, dict[str, Any]] = {}   # url -> its /info reply (per process); only a reply that names a model
_ASKED: dict[str, float] = {}           # url -> time.monotonic() of the last /info asked while there is no reply
_LOCK = threading.Lock()


def forget() -> None:
    """Drop the per-process /info cache and back-off (tests)."""
    with _LOCK:
        _INFO.clear()
        _ASKED.clear()


def info(url: str | None, timeout: float = TIMEOUT) -> dict[str, Any] | None:
    """The service's /info reply; None without a URL, when it fails, or within RETRY_S of the last failed ask
    (or while another thread asks). A reply is kept for the process; a failure is not."""
    if not url:
        return None
    with _LOCK:
        if url in _INFO:
            return _INFO[url]
        last = _ASKED.get(url)
        if last is not None and time.monotonic() - last < RETRY_S:
            return None
        _ASKED[url] = time.monotonic()   # this thread asks; the others see "down" instead of waiting on it
    try:
        reply = httpx.get(f"{url.rstrip('/')}/info", timeout=timeout)
        reply.raise_for_status()
        body = reply.json()
        found = body if isinstance(body, dict) and isinstance(body.get("model"), str) else None
    except (httpx.HTTPError, ValueError):
        found = None
    if found is not None:
        with _LOCK:
            found = _INFO.setdefault(url, found)
            _ASKED.pop(url, None)
    return found


class GlinerExtractor:
    evidence_type: str = ""
    name: str = ""
    WORDS: tuple[str, ...] = ()   # the config keys of the topic words `fields` reads

    def __init__(self, config: dict[str, Any]) -> None:
        given = {k: v for k, v in config.items() if k in regex.INJECTED}
        url = config[URL_KEY] if URL_KEY in config else os.environ.get("GLINER_URL")
        self.url = url.rstrip("/") if url else None
        self.timeout = float(config.get("timeout", TIMEOUT))
        self.labels = [str(x) for x in config["labels"]]   # the pack's gliner_labels of the type, or the protocol's
        self.threshold = float(config.get("threshold", DEFAULTS["threshold"]))
        self.chunk_chars = int(config.get("chunk_chars", DEFAULTS["chunk_chars"]))
        self.max_spans = int(config.get("max_spans", DEFAULTS["max_spans"]))
        served = info(self.url, self.timeout)
        self.served: str | None = served["model"] if served else None
        self.model: str | None = config.get("model") or self.served
        roles = list(given.get("roles") or [])
        self.role = roles[0] if roles else ROLE[self.evidence_type]
        self.given = given
        # the topic words `fields` reads (the pack's or the protocol's): condition patterns and the negated-object
        # lookahead, or metric [pattern, canonical, higher_is_better] rows, as the regex extractors take them
        self.words: dict[str, Any] = {k: config[k] for k in self.WORDS}
        self._lock = threading.Lock()
        self.spec = self._spec()

    def _spec(self) -> ExtractorSpec:
        return ExtractorSpec(name=self.name, version=VERSION, kind="model",
                             evidence_types=(self.evidence_type,),  # type: ignore[arg-type]
                             code_sha256=CODE_SHA256,
                             config={**self.given, **self.words, "service": "gliner", "model": self.model,
                                     "labels": self.labels, "threshold": self.threshold, "chunk_chars": self.chunk_chars,
                                     "max_spans": self.max_spans},
                             determinism="near_exact")

    def available(self) -> bool:
        """Whether the service serves this extractor's model. While /info has not answered it is asked again
        (info() limits how often); on the first answer an extractor without a model takes the served one."""
        if self.served is None and self.url:
            served = info(self.url, self.timeout)
            if served is not None:
                with self._lock:
                    if self.served is None:
                        if self.model is None:
                            self.model = served["model"]
                            self.spec = self._spec()   # before `served`: a thread that sees it available sees the id
                        self.served = served["model"]
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
    WORDS = ("conditions", "not_a_system")

    def fields(self, name: str) -> dict[str, Any] | None:
        enum = self._enum("role")
        conditions = self.words["conditions"]
        roles = list(enum or [*conditions, "other"])
        treatment = (self.given.get("compare") or {}).get("treatment")
        found = terms.find_conditions(name, terms.condition_patterns(conditions), roles, treatment=treatment,
                                      not_a_system=self.words["not_a_system"])
        role = found[0].key if found else "other"
        if enum is not None and role not in enum:
            return None
        return {"label": name, "role": role}


class GlinerMetric(GlinerExtractor):
    evidence_type, name = "metric", "gliner_metric"
    WORDS = ("metrics",)

    def fields(self, name: str) -> dict[str, Any] | None:
        found = terms.find_all(name, [(str(p), str(k), bool(h)) for p, k, h in self.words["metrics"]])
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
