"""The system under test: the evidence plan run, answering the benchmark questions. One part plans every question
(a draft per question, kept on a second run); the other collects a finished plan run into the judge's `AnswerRecord`
(the text only; no sub-question and no system name reaches a judge)."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from evaluation.planbatch import (PLANNER_CACHE, has_unchecked, orch_lm, saved_templates,  # noqa: F401  (tests replace orch_lm)
                                  sealed_complete, set_aside)
from evidence.kindtext import kind_lines, plan_names
from evidence.plan import Plan, load_plan, with_answer
from evidence.plankinds import answer_problems, kind_protocol
from evidence.planner import check_plan, confirm_all, critic, propose, using
from evidence.planrun import run as planrun_run
from evidence.words.write import write_words
from jsonio import write_text_atomic
from modelcall import ModelCallError, redact
from evidence.protocol import parse
from evidence.rundir import ANSWER_FILE, PLAN_FILE, PROTOCOL_FILE, RUN_FILE, RunDir
from synth3.answers import (MAX_TEXT, AnswerRecord, PaperIndex, answer_path, cited_papers, pulled_facts,
                            save_answer)
from synth3.questions import Question, answer_by_of, asked_sha256, question_sha256, target_of
from synth3.questions import QuestionSet
from synth3.sheetfacts import Folder
from synth3.spec import SPECS

SYSTEM = "system"
WRITTEN_FILE = "written-answer.json"
PLANS = SPECS / "plans"
MAX_WRITER_TRIES = 3


def plan_path(root: Path, domain: str, qid: str) -> Path:
    return root / domain / f"{qid}.json"


def auto_path(root: Path, domain: str, qid: str) -> Path:
    return root / domain / "auto" / f"{qid}.json"


def save_plan(plan: Plan, path: Path) -> None:
    """The plan file, written atomically with the bytes the plan page writes (webapp/evplan.py)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, plan.model_dump_json(indent=2))


def draft_plan(q: Question, lm, templates: Mapping[str, str]) -> Plan:
    """The planner's draft for one question, with its sub-questions and its answer kind. No clarifying questions
    (a batch has no one to answer them; the plan page asks them). Nothing is confirmed."""
    with using(lm):
        plan, _how = propose(q.question, [], sub_questions=q.sub_questions,
                             write_words=lambda t, th: write_words(t, th, lm=lm), templates=templates)
        plan = critic(plan)
    return with_answer(plan, answer_by_of(q), target_of(q))


def plan_stale(plan: Plan, q: Question) -> str | None:
    if plan.question != q.question or plan.sub_questions != q.sub_questions:
        return "the question changed after planning"
    return None


def _move_aside(path: Path) -> Path:
    """Move a plan file to `<qid>.stale-<n>.json` beside it; never deletes."""
    n = 1
    while (dest := path.with_name(f"{path.stem}.stale-{n}.json")).exists():
        n += 1
    path.replace(dest)
    return dest


def plan_domain(domain: str, qs: QuestionSet, root: Path, lm, templates: Mapping[str, str], *,
                redo: set[str] = frozenset(), redo_lm=None) -> dict:
    """Draft a plan for each question that has none (or a stale one, or is in `redo`); keep the rest. A changed
    kind or target is set in place (the planner's work does not depend on it; confirmations stay)."""
    out: dict = {"drafted": [], "kept": [], "rekinded": [], "failed": {}, "problems": {}}
    for q in qs.questions:
        path = plan_path(root, domain, q.id)
        try:
            old = load_plan(path) if path.is_file() else None
            if old is None or q.id in redo or plan_stale(old, q) is not None:
                plan = draft_plan(q, redo_lm if q.id in redo else lm, templates)   # a failed draft keeps the old plan
                if old is not None:
                    _move_aside(path)
                save_plan(plan, path)
                out["drafted"].append(q.id)
            elif (old.answer_by, old.target) != (answer_by_of(q), target_of(q)):
                save_plan(with_answer(old, answer_by_of(q), target_of(q)), path)
                out["rekinded"].append(q.id)
            else:
                out["kept"].append(q.id)
        except (ModelCallError, ValueError, RuntimeError) as err:
            out["failed"][q.id] = redact(str(err))
    for q in qs.questions:
        path = plan_path(root, domain, q.id)
        if not path.is_file():
            continue
        try:
            plan = load_plan(path)
        except ValueError as err:
            out["problems"][q.id] = [redact(str(err))]
            continue
        found = [*check_plan(plan, templates), *answer_problems(plan)]
        if found:
            out["problems"][q.id] = found
    return out


def is_plan_run(run: Path) -> bool:
    """True when run.json says the run is a plan run (`settings.stage_set == "plan"`)."""
    record = RunDir(run).try_json(RUN_FILE)
    settings = record.get("settings") if isinstance(record, dict) else None
    return isinstance(settings, dict) and settings.get("stage_set") == "plan"


def confirmed_by(plan: Plan) -> str:
    """"system" when any decision was confirmed by the system, else "person"."""
    return "system" if any(d.confirmed_by == SYSTEM for d in plan.decisions) else "person"


def kind_mismatch(have: tuple[str, str | None], want: tuple[str, str | None]) -> str:
    """"by <have>, the question asks for <want>": the kinds, or kind/target when only the targets differ."""
    if have[0] == want[0]:
        return f"by {have[0]}/{have[1]}, the question asks for {want[0]}/{want[1]}"
    return f"by {have[0]}, the question asks for {want[0]}"


def _refuse(run: Path, why: str) -> ValueError:
    return ValueError(f"{run}: {why}")


def from_system_run(run: Path, folder: Folder, q: Question, system: str = SYSTEM) -> AnswerRecord:
    rd = RunDir(run)
    if rd.state != "complete":
        raise _refuse(run, f"the run is not complete (state {rd.state})")
    record = rd.json(RUN_FILE)
    named = record.get("corpus_id") if isinstance(record, dict) else None
    if named != folder.corpus_id:
        raise _refuse(run, f"the run is of corpus {named!r}, the folder is {folder.corpus_id!r}; "
                           "a run on another corpus is refused")
    plan = load_plan(rd.file(PLAN_FILE))
    if plan.question != q.question or plan.sub_questions != q.sub_questions:
        raise _refuse(run, "the run was planned for another version of the question")
    want, target = answer_by_of(q), target_of(q)
    if plan.answer_by != want or plan.target != target:
        raise _refuse(run, f"the run answers {kind_mismatch((plan.answer_by, plan.target), (want, target))}")
    left_out = None
    if plan.answer_by == "written":
        written = rd.json(WRITTEN_FILE)
        if not isinstance(written, dict):
            raise _refuse(run, "the run has no written answer")
        if "failed" in written:
            raise _refuse(run, f"the written answer's model call failed: {written['failed']}; "
                               "run it again with retry")
        text = written["answer_text"] if written.get("status") in ("ok", "no_facts") else ""
        left_out = sum(written["cut"]["left_out"].values())
    else:
        protocol = parse((rd.file(PROTOCOL_FILE)).read_text(encoding="utf-8"))
        answer = rd.json(ANSWER_FILE)
        text = "\n".join(line.text for line in kind_lines(protocol, answer["synthesis"], plan_names(plan)))
    cut = len(text) > MAX_TEXT
    if cut:
        text = text[:MAX_TEXT] + f"\n[cut at {MAX_TEXT} characters]"
    return AnswerRecord(domain=folder.spec.domain, seed=folder.seed, corpus_id=folder.corpus_id, question_id=q.id,
                        question_sha256=question_sha256(q), system=system, text=text, text_cut=cut,
                        cited=cited_papers(text, PaperIndex.of_corpus(folder.path).ids),
                        facts=pulled_facts(run, folder), passages=[], source=str(run),
                        asked_sha256=asked_sha256(q), plan_confirmed_by=confirmed_by(plan),
                        facts_left_out=left_out)


def run_path(results: Path, domain: str, seed: int, qid: str) -> Path:
    return results / domain / "runs" / f"s{seed}" / qid


def _without_system_stamps(plan: Plan) -> Plan:
    return plan.model_copy(update={"decisions": [
        d.model_copy(update={"confirmed_by": None, "confirmed_at": None}) if d.confirmed_by == SYSTEM else d
        for d in plan.decisions]})


def plan_to_run(draft: Plan, root: Path, domain: str, qid: str, *, as_system: bool) -> tuple[Plan | None, str | None]:
    """The plan to run, or the reason to skip. A system copy (kept at `auto_path`) is never the draft file."""
    open_ids = [d.id for d in draft.decisions if d.confirmed_by is None]
    if not open_ids:
        return draft, None
    if not as_system:
        return None, (f"decisions not confirmed by a person: {', '.join(open_ids)}; confirm the plan on /plan "
                      "or pass --confirm-as-system")
    path = auto_path(root, domain, qid)
    try:
        kept = load_plan(path) if path.is_file() else None
    except ValueError:
        kept = None
    if kept is not None and _without_system_stamps(kept) == draft:
        return kept, None
    want = confirm_all(draft, SYSTEM)
    save_plan(want, path)
    return want, None


def _fresh(plan: Plan) -> Plan:
    return plan.model_copy(update={"writer_try": 0})


def _decide(run: Path, plan: Plan, corpus_id: str) -> tuple[str, int, bool]:
    """What to do with the run folder: (what, writer_try, retry_errors); what is keep, new, redo, old, corpus or
    failed. `old`: a complete run of another plan, or of a protocol the plan no longer gives. `corpus`: a complete run of another corpus than the folder at hand (the folder set changed, or the
    folder was rebuilt); like `old` (another plan) it is set aside and the question runs again."""
    if not run.exists():
        return "new", 0, False
    if not sealed_complete(run):
        return "failed", 0, True
    record = RunDir(run).try_json(RUN_FILE)
    if (record.get("corpus_id") if isinstance(record, dict) else None) != corpus_id:
        return "corpus", 0, False
    try:
        had = load_plan(RunDir(run).file(PLAN_FILE))
    except (ValueError, OSError):
        return "failed", 0, True
    if _fresh(had) != _fresh(plan):
        return "old", 0, False
    try:   # the same plan, but the code now writes another protocol from it (e.g. the best kind's condition type)
        if RunDir(run).file(PROTOCOL_FILE).read_bytes() != kind_protocol(plan):
            return "old", 0, False
    except OSError:
        return "failed", 0, True
    if plan.answer_by != "written":
        return ("redo", had.writer_try, True) if has_unchecked(run) else ("keep", had.writer_try, False)
    written = RunDir(run).try_json(WRITTEN_FILE)
    if not isinstance(written, dict) or "failed" in written or has_unchecked(run):
        return "redo", had.writer_try, True
    if written.get("status") == "failed" and had.writer_try < MAX_WRITER_TRIES - 1:
        return "redo", had.writer_try + 1, False
    return "keep", had.writer_try, False


def _of_another_plan(run: Path, draft: Plan) -> bool:
    """True when the run folder holds a plan that is not the plan file's (system stamps and the writer try apart)."""
    try:
        had = load_plan(RunDir(run).file(PLAN_FILE))
    except (ValueError, OSError):
        return False
    return _without_system_stamps(_fresh(had)) != _without_system_stamps(_fresh(draft))


def _answer_aside(path: Path) -> None:
    """Move a saved answer to `<qid>.answer.old-<n>.json` beside it; never deletes. The judge and the report read
    `*.answer.json` only, so an answer made from another plan than the plan file's no longer counts."""
    if not path.is_file():
        return
    n = 1
    while (dest := path.with_name(path.name.removesuffix(".json") + f".old-{n}.json")).exists():
        n += 1
    path.replace(dest)


def run_folder(folder: Folder, qs: QuestionSet, plans: Path, results: Path, *, as_system: bool = False,
               provider=None, workers: int = 3, runner=None) -> dict:
    """Every question's confirmed plan run on the folder and collected for the judge. A finished run is kept;
    failed, unsealed, changed or unchecked runs and runs of another corpus are set aside (never deleted) and run
    again. A saved answer whose run was made from another plan than the plan file's is set aside too, whether the
    question is then skipped, fails or runs again."""
    runner = runner or planrun_run
    domain, seed = folder.spec.domain, folder.seed
    out: dict = {"ran": [], "rerun": [], "kept": [], "skipped": {}, "failed": {}, "empty": [], "by_system": []}
    templates = saved_templates()
    for q in qs.questions:
        path = plan_path(plans, domain, q.id)
        if not path.is_file():
            out["skipped"][q.id] = "no plan; run synth3 system-plan first"
            continue
        try:
            draft = load_plan(path)
        except ValueError as err:
            out["skipped"][q.id] = redact(str(err))
            continue
        run = run_path(results, domain, seed, q.id)
        if _of_another_plan(run, draft):
            _answer_aside(answer_path(results, domain, seed, SYSTEM, q.id))
        if (why := plan_stale(draft, q)) is not None:
            out["skipped"][q.id] = why
            continue
        want = (answer_by_of(q), target_of(q))
        if (draft.answer_by, draft.target) != want:
            out["skipped"][q.id] = (f"the plan answers {kind_mismatch((draft.answer_by, draft.target), want)}; "
                                    "run synth3 system-plan")
            continue
        # answer_problems runs before anything that calls kind_protocol (the run does)
        if found := [*check_plan(draft, templates), *answer_problems(draft)]:
            out["skipped"][q.id] = "; ".join(found)
            continue
        plan, why = plan_to_run(draft, plans, domain, q.id, as_system=as_system)
        if plan is None:
            out["skipped"][q.id] = why
            continue
        what, tries, retry = _decide(run, plan, folder.corpus_id)
        try:
            if what == "keep":
                out["kept"].append(q.id)
            else:
                if what != "new":
                    set_aside(run, what)
                file = run.with_suffix(".plan.json")
                save_plan(plan.model_copy(update={"writer_try": tries}), file)
                runner(file, folder.path, run.parent, cache=results / domain / "run-cache", run_id=q.id,
                       reason="off", links="off", workers=workers, retry_errors=retry,
                       **({"provider": provider} if provider else {}))
                out["rerun" if what == "redo" else "ran"].append(q.id)
        except Exception as err:  # noqa: BLE001  (one question's failure must not stop the next)
            out["failed"][q.id] = redact(str(err))
            continue
        try:
            rec = from_system_run(run, folder, q)
        except Exception as err:  # noqa: BLE001  (one damaged run must not stop the next)
            said = redact(str(err))
            out["failed"][q.id] = said if isinstance(err, ValueError) else f"{type(err).__name__}: {said}"
            continue
        save_answer(results, rec)
        if not rec.text:
            out["empty"].append(q.id)
        if rec.plan_confirmed_by == SYSTEM:
            out["by_system"].append(q.id)
    return out
