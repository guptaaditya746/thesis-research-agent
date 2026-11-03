"""The plan page's real parts (Wave 2 Task 8.1): what `create_app` hands `evplan_router` when no backend is given.

- `lm`: a factory of `RecordedLM("orch-model")` (the pinned orchestrator alias, W1's word writer requires it), every
  call recorded in `$EV/cache/planner.jsonl`: one plain model call through `modelcall.ask_sync` (LiteLLM gateway).
- `templates`: the saved SPARQL templates (evidence/kg/templates), name -> text.
- `run(plan, folder)`: a plan run (evidence/planrun.py) of the frozen plan over the corpus `$EV_PLAN_CORPUS` (a path,
  or a corpus id under the corpora folder) into the runs folder, in a background thread; returns the run id at once.
- `result(run id)`: {status running|done, lines, answer, reruns} from the run's answer.json ("failed: <reason>" as the
  answer text when the run failed).
- `links(run id, accepted, rejected)`: W2's review of the LLM ontology links, then W4's rerun of the lines.
Without `$EV` (no runs folder) or `$EV_PLAN_CORPUS`, run answers 501 (NotWired), as before."""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from evidence.plan import Plan, write_plan

from .evplan import NotWired, PlanBackend
from .files import NotFound
from .settings import Settings

PLAN_CORPUS = "EV_PLAN_CORPUS"
PLANNER_CACHE = "planner.jsonl"


def gateway_ask(alias: str):
    """`ask(text) -> reply text` for a RecordedLM: one plain call of `alias` through the gateway (no cache here: the
    RecordedLM records it)."""
    from evidence.stages import Reply
    from modelcall import Prompt, ask_sync, openai_model

    def ask(text: str) -> str:
        return ask_sync(Prompt.inline("", Reply), text, model=openai_model(alias)).output.text
    return ask


def lm_factory(settings: Settings):
    from modelcall.cache import JsonlCache
    from modelcall.dspy_lm import RecordedLM
    from modelcall.pins import ORCH_ALIAS
    folder = (settings.ev_cache_dir or (Path(settings.ev) / "cache" if settings.ev else None))

    def make() -> RecordedLM:
        if folder is None:
            raise NotWired("no record cache for the planner's model: set EV")
        folder.mkdir(parents=True, exist_ok=True)
        return RecordedLM(ORCH_ALIAS, gateway_ask(ORCH_ALIAS), cache=JsonlCache(folder / PLANNER_CACHE))
    return make


def saved_templates() -> dict[str, str]:
    from evidence.kg.query import template, templates
    return {name: template(name) for name in templates()}


class PlanRuns:
    """Plan runs started from the page, each in its own thread; the run folder is the record."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.errors: dict[str, str] = {}
        self.threads: dict[str, threading.Thread] = {}

    def _corpus(self) -> Path:
        given = os.environ.get(PLAN_CORPUS) or ""
        if not given:
            raise NotWired(f"no corpus for plan runs: set {PLAN_CORPUS} (a corpus folder or a corpus id)")
        path = Path(given)
        if not path.is_dir() and self.settings.corpora_dir is not None:
            path = self.settings.corpora_dir / given
        if not (path / "manifest.json").is_file():
            raise NotWired(f"{PLAN_CORPUS}={given!r} is not a corpus folder (no manifest.json)")
        return path

    def _out(self) -> Path:
        if self.settings.ev_runs_dir is None:
            raise NotWired("no runs folder for plan runs: set EV")
        return self.settings.ev_runs_dir

    def run(self, plan: Plan, folder: Path | None) -> str:
        from evidence import planrun
        from evidence.rundir import new_run_id
        corpus, out = self._corpus(), self._out()
        out.mkdir(parents=True, exist_ok=True)
        path = (folder / "plan.frozen.json") if folder is not None else out / f".plan-{plan.sha256[:12]}.json"
        if not path.is_file():
            write_plan(plan, path)
        rid = new_run_id(f"plan-{plan.sha256[:12]}")
        cache = self.settings.ev_cache_dir

        def work() -> None:
            try:
                planrun.run(path, corpus, out, cache=cache, run_id=rid)
            except BaseException as exc:   # noqa: BLE001 - the page shows it as the answer
                self.errors[rid] = f"{type(exc).__name__}: {str(exc)[:300]}"

        thread = threading.Thread(target=work, name=f"plan-run-{rid}", daemon=True)
        self.threads[rid] = thread
        thread.start()
        return rid

    def folder(self, rid: str) -> Path:
        root = self._out() / rid
        if not root.is_dir() and rid not in self.threads:
            raise NotFound(f"no run {rid!r}")
        return root

    def result(self, rid: str) -> dict[str, Any]:
        from evidence.rundir import RunDir
        root = self.folder(rid)
        if rid in self.errors:
            return {"status": "done", "lines": [], "answer": {"text": f"failed: {self.errors[rid]}"}, "reruns": []}
        run = RunDir(root)
        answer = run.try_json("answer.json") if run.complete else None
        if answer is None:
            return {"status": "running", "lines": [], "answer": {"text": "Running..."}, "reruns": []}
        return {"status": "done", "lines": answer["lines"], "answer": answer["answer"], "reruns": answer["reruns"],
                "labels": answer.get("labels", {}), "links": answer.get("links", [])}

    def links(self, rid: str, accepted: list[str], rejected: list[str]) -> dict[str, Any]:
        from evidence import planrun
        return planrun.relink(self.folder(rid), accepted, rejected)


def default_backend(settings: Settings) -> PlanBackend:
    """The plan page's backend with every part wired."""
    runs = PlanRuns(settings)
    return PlanBackend(lm=lm_factory(settings), templates=saved_templates(), run=runs.run, result=runs.result,
                       links=runs.links)
