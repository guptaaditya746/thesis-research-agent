"""Plan-run batch of one question set (general-system runbook, section 6): the run-folder layout, the two
confirmation rows and the plan / confirm / run rules. `scripts/plan-runs.py` makes the runs with it and
`evaluate wholerun` (wholerun_cmd.py) reads them back with it.

Layout: <runs>/<auto-confirmed|hand-confirmed>/<on|off>/<question id>/ (`run_dir`); the off-template and synthetic
sets run flat into <runs>/<question id>/ (`FLAT_SETS`). The auto-confirmed row is every question, its decisions
confirmed by "system"; the hand-confirmed row is the FIRST `HAND_N` questions (`pool`), confirmed by a person.

Rules (`run_all`): a question whose run folder is sealed `complete` is skipped. A folder that failed, or was never
sealed, is set aside as <question id>.failed-<n> and the question runs again, asking failed model calls again; with
`redo_unchecked`, a complete folder whose reports list items a failed call left unchecked is set aside as
<question id>.redo-<n> and run again the same way. One confirmed plan per question and row
(<plans>/<row>/<question id>.json) is shared by the on and off runs; an existing one is used as it is.

Also the planner's wiring, shared with the web app and the scripts: `saved_templates` and `orch_lm` (a RecordedLM of
orch-model through the gateway, every call recorded in a JsonlCache file)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

HAND_N = 5                         # hand-confirmed questions per set
AUTO, HAND = "auto-confirmed", "hand-confirmed"
CONFIRMATIONS = (AUTO, HAND)       # the row names, "<confirmation>/<reasoning>" with REASONING
REASONING = ("on", "off")
SYSTEM = "system"                  # who confirm_all(plan, who="system") stamps on an auto-confirmed plan
FLAT_SETS = ("offtemplate", "synthetic")   # run into <runs>/<question id>/ (for `evaluate offtemplate` / `leak`)
PLANNER_CACHE = "planner.jsonl"
OFFTEMPLATE_CORPUS = "tests/EV2/corpora/rag-claude-s1-mixed"


class BatchError(ValueError):
    """A batch that cannot start (a missing input or a confirmation rule); nothing was written."""


# --- layout ---------------------------------------------------------------------------------------------------

def pool(questions: list[Any], confirmation: str) -> list[Any]:
    """The questions of a row: all for auto-confirmed, the first HAND_N for hand-confirmed."""
    return list(questions) if confirmation == AUTO else list(questions)[:HAND_N]


def row_dir(runs: Path, confirmation: str, reasoning: str) -> Path:
    return Path(runs) / confirmation / reasoning


def run_dir(runs: Path, confirmation: str, reasoning: str, question_id: str) -> Path:
    return row_dir(runs, confirmation, reasoning) / question_id


# --- planner wiring -----------------------------------------------------------------------------------------------

def saved_templates() -> dict[str, str]:
    """The saved SPARQL templates (evidence/kg/templates), name -> text."""
    from evidence.kg.query import template, templates
    return {name: template(name) for name in templates()}


def orch_lm(cache_file: Path) -> Any:
    """A `RecordedLM` of orch-model: one plain gateway call per miss, every call recorded in `cache_file`."""
    from evidence.stages import gateway_ask
    from modelcall.cache import JsonlCache
    from modelcall.dspy_lm import RecordedLM
    from modelcall.pins import ORCH_ALIAS
    return RecordedLM(ORCH_ALIAS, gateway_ask(ORCH_ALIAS), cache=JsonlCache(cache_file))


# --- the questions --------------------------------------------------------------------------------------------

def questions(set_name: str, *, src: Path | None = None, sample: Path | None = None, corpus: Path | None = None,
              question: str | None = None) -> list[Any]:
    """The batch's questions (each with `id`, `question`, `corpus_dir`): a real set's questions in the order of
    `sample` (sample.json, written by `evaluate wholerun`); the 12 off-template questions; or one `question` on a
    synthetic `corpus` (id effect-<corpus name>)."""
    if set_name == "offtemplate":   # the 12 generality questions on their own corpus; no sample, no src
        from .offtemplate import check as ot
        return [SimpleNamespace(id=q.id, question=q.question, corpus_dir=ot.ROOT / OFFTEMPLATE_CORPUS)
                for q in ot.load_questions()]
    if set_name == "synthetic":
        if corpus is None or not question:
            raise BatchError("--set synthetic needs --corpus and --question")
        return [SimpleNamespace(id=f"effect-{corpus.name}", question=question, corpus_dir=corpus)]
    if src is None or sample is None:
        raise BatchError("--src and --sample are required for a real set")
    from .realpapers import real_set
    ids = json.loads(Path(sample).read_text(encoding="utf-8"))["ids"]
    by_id = {q.id: q for q in real_set(set_name).questions(src, corpus)}
    return [by_id[i] for i in ids]


# --- plan, confirm, run -----------------------------------------------------------------------------------------

def plan_all(qs: list[Any], plans: Path, cache: Path) -> int:
    """<plans>/<question id>.json for every question (the planner and its critic, nothing confirmed; the word list
    holds the field ontology's other names); an existing plan is kept. Every plan is checked; 1 when one has
    problems (named on stderr), else 0."""
    from evidence.plan import load_plan, write_plan
    from evidence.planner import critic, propose
    from evidence.planner.plan import check_plan
    from evidence.steps import using
    from evidence.words.write import write_words
    cache.mkdir(parents=True, exist_ok=True)
    lm = orch_lm(cache / PLANNER_CACHE)
    plans.mkdir(parents=True, exist_ok=True)
    flagged = 0
    for q in qs:
        path = plans / f"{q.id}.json"
        if not path.is_file():
            with using(lm):
                # propose puts the field ontology's other names into the word list (planner.with_ontology_names)
                plan, _how = propose(q.question, [], write_words=lambda text, things: write_words(text, things, lm=lm),
                                     templates=saved_templates())
                write_plan(critic(plan), path)
            print(f"planned {q.id}")
        # the web app refuses such a plan; here it is kept (a saved plan stays replayable) and named, exit 1
        problems = check_plan(load_plan(path), saved_templates())
        if problems:
            flagged += 1
            print(f"plan problems {q.id}: " + "; ".join(problems), file=sys.stderr)
    if flagged:
        print(f"FAIL plan check: {flagged} of {len(qs)} plans have problems (above); their lines will fail or find "
              "nothing", file=sys.stderr)
    return 1 if flagged else 0


def show(plan: Any, path: Path) -> None:
    """Each decision and the word list of a hand-confirmed plan, for the person to read before the run."""
    print(f"== {path}\n   question: {plan.question}")
    for d in plan.decisions:
        flag = f"  [critic: {d.flag_reason}]" if d.flagged else ""
        print(f"   decision {d.id} ({d.type}) = {json.dumps(d.value, ensure_ascii=False)}: {d.reason}{flag}")
    for thing, names in plan.words.things.items():
        extra = plan.words.ontology_names.get(thing, [])
        print(f"   words {thing}: {', '.join(names)}" + (f" | ontology: {', '.join(extra)}" if extra else ""))
    print(f"   cues: {', '.join(plan.words.cues)}")


def confirm_hand(qs: list[Any], plans: Path, by: str) -> int:
    """The hand row's confirmed plans: an existing file is kept (the person may have edited it); a missing one is
    written with every decision confirmed by `by`. Each is printed."""
    from evidence.plan import load_plan, write_plan
    from evidence.planner import confirm_all
    if not by or by == SYSTEM:
        raise BatchError("confirm needs --by NAME, a person (not system)")
    folder = plans / HAND
    folder.mkdir(parents=True, exist_ok=True)
    hand = pool(qs, HAND)
    missing = [q.id for q in hand if not (folder / f"{q.id}.json").is_file() and not (plans / f"{q.id}.json").is_file()]
    if missing:   # before any file is written
        raise BatchError(f"no plan for {', '.join(missing)} in {plans}: run `plan-runs.py plan` first")
    for q in hand:
        path = folder / f"{q.id}.json"
        if path.is_file():
            print(f"kept {path} (already confirmed)")
        else:
            write_plan(confirm_all(load_plan(plans / f"{q.id}.json"), by), path)
            print(f"wrote {path}")
        show(load_plan(path), path)
    print(f"To change a decision or a word, edit the files under {folder} before `plan-runs.py run --confirm hand`.")
    return 0


def sealed_complete(folder: Path) -> bool:
    """The run folder holds a complete run (`RunDir.state`: sealed complete; a plan run is always sealed)."""
    from evidence.rundir import RunDir
    return RunDir(folder).state == "complete"


def has_unchecked(folder: Path) -> bool:
    """The run left items unchecked by a failed model call: any note in stage_report.json, or a recheck find whose
    call failed or whose reply did not parse (recheck_report.json)."""
    from evidence import unchecked
    from evidence.planrun import RECHECK_REPORT
    from evidence.rundir import RunDir
    run = RunDir(folder)

    def read(name: str) -> dict:
        data = run.stage_result(name)
        return data if isinstance(data, dict) else {}
    if any(notes for docs in read(unchecked.NAME).values() if isinstance(docs, dict) for notes in docs.values()):
        return True
    return any(str(u.get("why", "")).startswith(("failed call:", "unparseable reply:"))
               for doc in read(RECHECK_REPORT).values() if isinstance(doc, dict)
               for u in doc.get("unchecked") or [])


def set_aside(folder: Path, tag: str = "failed") -> Path:
    """Move a run folder to <name>.<tag>-<n> (n = 1, 2, ...): `failed` for a failed or unsealed run, `redo` for a
    complete one run again for its unchecked items; returns the new path."""
    n = 1
    while (target := folder.with_name(f"{folder.name}.{tag}-{n}")).exists():
        n += 1
    folder.rename(target)
    return target


def run_all(qs: list[Any], *, set_name: str, plans: Path, runs: Path, cache: Path, confirm: str, reasoning: str,
            links: str = "on", redo_unchecked: bool = False, confirm_by: str | None = None, model: str | None = None,
            workers: int = 3) -> int:
    """Confirm the plans of one row (`confirm` auto|hand) and run each as a plan run into the layout (module
    docstring); 1 when a question failed (named on stderr; the next still runs), else 0."""
    from evidence import planrun
    from evidence.plan import load_plan, write_plan
    from evidence.planner import confirm_all
    who = SYSTEM if confirm == "auto" else confirm_by
    conf = AUTO if confirm == "auto" else HAND
    chosen = pool(qs, conf)
    written = all((plans / HAND / f"{q.id}.json").is_file() for q in chosen)   # `confirm` wrote them all
    if confirm == "hand" and (who == SYSTEM or (not who and not written)):
        raise BatchError("--confirm hand needs --confirm-by NAME, a person (not system), or the hand "
                         "plans written by `plan-runs.py confirm`")
    out = Path(runs) if set_name in FLAT_SETS else row_dir(runs, conf, reasoning)
    out.mkdir(parents=True, exist_ok=True)
    bad = 0
    for q in chosen:
        folder = out / q.id
        retry = False
        if folder.exists():
            if sealed_complete(folder) and not (redo_unchecked and has_unchecked(folder)):
                print(f"skip {q.id}: {folder} is complete")
                continue
            if sealed_complete(folder):
                print(f"moved {folder} (complete, items unchecked) to {set_aside(folder, 'redo').name}; running {q.id} again")
            else:
                print(f"moved {folder} (failed or unsealed) to {set_aside(folder).name}; running {q.id} again")
            retry = True
        confirmed = plans / conf / f"{q.id}.json"
        if not confirmed.is_file():   # one confirmed plan per question and row, shared by the on and off runs
            confirmed.parent.mkdir(parents=True, exist_ok=True)
            write_plan(confirm_all(load_plan(plans / f"{q.id}.json"), who), confirmed)
        try:
            kw = {"model": model} if model else {}
            planrun.run(confirmed, q.corpus_dir, out, cache=cache, run_id=q.id, workers=workers,
                        reason=reasoning, links=links, retry_errors=retry, **kw)
            print(f"ran {conf}/{reasoning}/{q.id}")
        except Exception as exc:   # noqa: BLE001 - recorded; the next question still runs
            bad += 1
            print(f"FAILED {q.id}: {type(exc).__name__}: {str(exc)[:300]}", file=sys.stderr)
    return 1 if bad else 0
