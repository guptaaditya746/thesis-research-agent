"""evqa and the scorer service (services/thesis-scorer, package thesis_scorer): evqa writes the scorer's two input
files and turns its report into the run's eval.json. All scoring rules live in the scorer; this module only reads
evqa's seed and run folders.

    gold_file(domain, split, qids=None) -> dict      the scorer's gold file, from data/seed (`evqa gold-export`)
    run_records(run_dir, cfg, qids)     -> [dict]    the scorer's answers records, one per question of a run folder
    score_run(run_dir, domain, only, write)          -> eval.json (`evqa eval`); eval_text.json is merged when present
    score_text(run_dir, reader, judge)               -> eval_text.json + <qid>/claims.json (`evqa eval --text`)
    judge_run(run_dir), judge_population(run_dir)    -> eval.json "label_judge", population_judge.json

Run folder -> record: an evqa run gives `structured` = {spec.json, rows.jsonl, answer.json} and its answer as text
(render(): every value with its settings, unit and papers); a baseline run (evqa/baselines) gives answer_text.json
and no `structured`. Both give find.jsonl as `find` (passage offsets only). A missing file is null; a file that is
there but does not read is null too (spec, answer) or empty (find, rows).
The gold file holds the seed facts with their L0 spans (data/seed/<domain>/l0), the gold questions with the question
text the systems were asked, the item names, the corpus paper ids, the unit table (evqa/units.json) and the data
hashes (datahash.py). Reading the seed here is allowed: the pipeline steps may not import this module (seed wall).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from thesis_scorer import api, judge, text, values
from thesis_scorer.gold import Gold
from thesis_scorer.llm import Chat
from thesis_scorer.schema import GoldFile, Record
from thesis_scorer.structured import answer_rows_used, shows_value

from evqa import datahash, norm
from evqa.contracts import Answer, FindHit, Row, RunConfig, Spec, StepLLM, TextAnswer, read_jsonl
from evqa.paths import DATASET, domain_dir

READER = text.READER
JUDGE = text.JUDGE
values.use_units(norm.units())   # scorer helpers called from evqa (qgraph) read numbers with evqa's unit table


# ---------------------------------------------------------------- gold side (data/seed)
@lru_cache(maxsize=4)
def seed_facts(domain: str) -> dict[str, dict[str, Any]]:
    """Seed fact id -> fact (paper, subject, measure, measure_alt, context, dose, week, value, unit, ...)."""
    from evqa.seed import brief
    return {f["id"]: f for p in brief.paper_facts(domain).values() for f in p["facts"]}


def contexts(domain: str) -> tuple[str, ...]:
    return tuple(sorted({f["context"] for f in seed_facts(domain).values()}))


@lru_cache(maxsize=4)
def gold(domain: str) -> dict[str, dict[str, Any]]:
    folder = domain_dir(domain) / "gold"
    return {p.stem: json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(folder.glob("*.json")) if p.name != "manifest.json"}


@lru_cache(maxsize=32)
def l0_facts(domain: str, paper: str) -> dict[str, dict[str, Any]]:
    """Fact id -> the fact's L0 record (spans, status, in_planned_place) from data/seed/<domain>/l0/<paper>.json."""
    path = domain_dir(domain) / "l0" / f"{paper}.json"
    if not path.is_file():
        return {}
    return {f["id"]: f for f in json.loads(path.read_text(encoding="utf-8")).get("facts", [])}


def l0_spans(domain: str, paper: str) -> dict[str, tuple[tuple[int, int], ...]]:
    return {fid: tuple((s["start"], s["end"]) for s in f.get("spans", [])) for fid, f in l0_facts(domain, paper).items()}


def blueprint_label(domain: str, key: str) -> str:
    """The seed label of a blueprint key (context or measure key, drug key); 'label:<text>' gives <text>."""
    from evqa.seed import questions as seed_questions
    if str(key).startswith("label:"):
        return str(key)[len("label:"):]
    bp = seed_questions._blueprint(domain)
    for section in ("contexts", "measures", "items"):
        item = (bp.get(section) or {}).get(key)
        if isinstance(item, dict) and item.get("label"):
            return seed_questions.names(domain).get(key, item["label"]) if section == "items" else item["label"]
        if isinstance(item, str):
            return item
    return str(key)


def measure_names(domain: str, key: str) -> dict[str, Any]:
    """A fact-like {measure, measure_alt} for a gold measure slot (for the advisor when the question has no facts)."""
    from evqa.seed import questions as seed_questions
    item = (seed_questions._blueprint(domain).get("measures") or {}).get(key)
    if isinstance(item, dict):
        return {"measure": item.get("label", key), "measure_alt": list(item.get("alt", []))}
    return {"measure": blueprint_label(domain, key), "measure_alt": []}


def asked(domain: str) -> dict[str, str]:
    """qid -> the question text the systems get, from every split's questions file."""
    out: dict[str, str] = {}
    for path in sorted((DATASET / domain / "questions").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                out.setdefault(str(rec["qid"]), str(rec["question"]))
    return out


def split_qids(domain: str, split: str) -> list[str]:
    return [q for q, g in gold(domain).items() if g.get("split") == split]


def gold_file(domain: str, split: str, qids: list[str] | None = None) -> dict[str, Any]:
    """The scorer's gold file (thesis_scorer.schema.GoldFile) for `qids` (default: the split's gold questions)."""
    golds = gold(domain)
    qids = split_qids(domain, split) if qids is None else [q for q in qids if q in golds]
    texts = asked(domain)
    papers = sorted(p.parent.name for p in (DATASET / domain).glob("*/paper.md"))
    if is_pf(domain):
        return pf_gold_file(domain, split, qids, golds, texts, papers)
    facts = {}
    for fid, f in seed_facts(domain).items():
        l0 = l0_facts(domain, f["paper"]).get(fid, {})
        spans = l0.get("spans", [])
        facts[fid] = {**f, "l0_spans": [[s["start"], s["end"]] for s in spans],
                      "l0_ambiguous": bool(spans) and all(s.get("ambiguous") for s in spans)}
    questions = []
    for q in qids:
        g = golds[q]
        slots = g.get("slots") or {}
        labels: dict[str, Any] = {}
        if slots.get("context") is not None:
            labels["context"] = blueprint_label(domain, str(slots["context"]))
        if slots.get("measure"):
            labels["measure"] = measure_names(domain, slots["measure"])
        questions.append({**g, "question": texts.get(q, ""), "labels": labels})
    from evqa.seed import questions as seed_questions
    out = {"domain": domain, "split": split, "units": norm.units(), "names": seed_questions.names(domain),
           "papers": papers, "facts": facts, "questions": questions, "data": datahash.data_hashes(domain, split)}
    return GoldFile.model_validate(out).model_dump(mode="json")


def is_pf(domain: str) -> bool:
    """A paperfactory domain (evqa/seed/pfbench.py gold from shared fact rows, no evqa seed graph)."""
    from evqa.seed import pfview
    return pfview.is_pf(domain)


def pf_gold_file(domain: str, split: str, qids: list[str], golds: dict[str, dict[str, Any]],
                 texts: dict[str, str], papers: list[str]) -> dict[str, Any]:
    """The gold file of a paperfactory domain: kind "paperfactory", no facts, the entities of
    data/seed/<d>/entities.json; the pfbench gold questions as written (rows with "papers", entities)."""
    path = domain_dir(domain) / "entities.json"
    ents = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    out = {"domain": domain, "kind": "paperfactory", "split": split, "units": norm.units(), "papers": papers,
           "entities": {k: {"kind": e["kind"], "label": e["label"], "alt": list(e.get("alt") or [])}
                        for k, e in ents.items()},
           "questions": [{**golds[q], "question": texts.get(q, "")} for q in qids],
           "data": datahash.data_hashes(domain, split)}
    return GoldFile.model_validate(out).model_dump(mode="json")


# ---------------------------------------------------------------- run side
def _load(path: Path, cls: Any) -> Any:
    if not path.is_file():
        return None
    try:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError:
        return None


def _jsonl(path: Path, cls: Any) -> list[Any] | None:
    if not path.is_file():
        return None
    try:
        return read_jsonl(path, cls)
    except ValidationError:
        return []


def _sym(unit: str) -> str:
    return norm.units().get(unit, {}).get("symbol", unit) if unit else ""


def _cells(cells: dict[str, str]) -> str:
    return ", ".join(f"{k} {v}" for k, v in cells.items() if v and v != "not stated")


def render(ans: Answer, rows: list[Row]) -> str:
    """An evqa answer.json as plain lines: every value with its settings, unit and papers (what a reader sees)."""
    def papers(idxs: Any) -> str:
        got = sorted({rows[int(i)].paper for i in idxs or [] if 0 <= int(i) < len(rows)})
        return f" [{', '.join(got)}]" if got else ""
    lines = [ans.sentence] if ans.sentence else []
    for a in ans.table:
        lines.append(f"- {_cells(a.cells)}: {a.value} {_sym(a.unit)}{papers(a.rows)}")
    for e in ans.effects:
        lines.append(f"- {e.a} minus {e.b} ({_cells(e.group)}): {e.difference} {_sym(e.unit)}"
                     f"{f', {e.verdict}' if getattr(e, 'verdict', '') else ''}{papers(e.rows)}")
    for s in ans.trend:
        for p in s.points:
            lines.append(f"- {_cells(s.group)}, {s.axis} {p.get('at')}: {p.get('value')} {_sym(str(p.get('unit', '')))}"
                         f"{papers(p.get('rows'))}")
    for b in ans.groups:
        if b.winner:
            lines.append(f"- best ({_cells(b.group) or 'all'}): {b.winner} ({b.status})")
        for r in b.ranking:
            lines.append(f"- {r.get('candidate')} ({_cells(b.group)}): {r.get('value')} {_sym(str(r.get('unit', '')))}"
                         f"{papers(r.get('rows'))}")
    for p in ans.papers:
        lines.append(f"- paper {p.paper}")
    for c in ans.conflicts:
        for v in c.values:
            lines.append(f"- {_cells(c.cells)}: {v.get('value')} {_sym(str(v.get('unit', '')))} [{v.get('paper')}]")
    if ans.not_reported and len(lines) <= 1:
        lines.append("Not reported in the papers.")
    return "\n".join(lines)


def question_record(qdir: Path, qid: str, cfg: RunConfig) -> dict[str, Any]:
    """One question of a run folder as a scorer record (module doc)."""
    hits = _jsonl(qdir / "find.jsonl", FindHit)
    find = None if hits is None else [{"paper": h.paper, "screen": h.screen,
                                       "passages": [{"start": p.start, "end": p.end} for p in h.passages]}
                                      for h in hits]
    if cfg.is_baseline():
        ta = _load(qdir / "answer_text.json", TextAnswer) if (qdir / "answer_text.json").is_file() else None
        return {"qid": qid, "system": str(cfg.system), "answer": ta.text if ta else None,
                "cannot_answer": bool(ta and ta.cannot_answer), "citations": list(ta.citations) if ta else [],
                "find": find, "structured": None}
    spec = _load(qdir / "spec.json", Spec)
    rows = _jsonl(qdir / "rows.jsonl", Row)
    ans = _load(qdir / "answer.json", Answer)
    rec: dict[str, Any] = {"qid": qid, "system": "evqa", "answer": None, "cannot_answer": False, "citations": [],
                           "find": find,
                           "structured": {"spec": spec.model_dump(mode="json") if spec else None,
                                          "rows": None if rows is None else [r.model_dump(mode="json") for r in rows],
                                          "answer": ans.model_dump(mode="json") if ans else None}}
    if ans is not None:
        rs = rows or []
        used = {rs[i].paper for i in answer_rows_used(ans) if 0 <= i < len(rs)}
        rec.update(answer=render(ans, rs), cannot_answer=ans.not_reported and not shows_value(ans),
                   citations=sorted(used | {p.paper for p in ans.papers}))
    return rec


def run_config(run_dir: Path, domain: str = "medical") -> RunConfig:
    path = Path(run_dir) / "config.yaml"
    return RunConfig.load(path) if path.is_file() else RunConfig(domain=domain)


def run_qids(cfg: RunConfig, only: list[str] | None = None) -> list[str]:
    """The run's questions: its config list, else every gold question of its split; `only` narrows it."""
    qids = list(cfg.questions) or split_qids(cfg.domain, cfg.split)
    return [q for q in qids if q in only] if only else qids


def run_records(run_dir: Path, cfg: RunConfig, qids: list[str]) -> list[dict[str, Any]]:
    return [question_record(Path(run_dir) / q, q, cfg) for q in qids]


def _inputs(run_dir: Path, domain: str, only: list[str] | None = None
            ) -> tuple[RunConfig, list[str], Gold, dict[str, Record]]:
    cfg = run_config(run_dir, domain)
    qids = run_qids(cfg, only)
    g = Gold(GoldFile.model_validate(gold_file(cfg.domain, cfg.split, qids)))
    recs = {r["qid"]: Record.model_validate(r) for r in run_records(run_dir, cfg, qids)}
    return cfg, qids, g, recs


# ---------------------------------------------------------------- scores
def score_run(run_dir: Path, domain: str = "medical", only: list[str] | None = None,
              write: bool = True) -> dict[str, Any]:
    """eval.json of a run folder: the scorer's report with run_id, config_name and closed_book in front; the saved
    eval_text.json (score_text) is merged in. write=False leaves a saved eval.json untouched."""
    run_dir = Path(run_dir)
    cfg, qids, g, recs = _inputs(run_dir, domain, only)
    text_path = run_dir / "eval_text.json"
    saved = json.loads(text_path.read_text(encoding="utf-8")) if text_path.is_file() else None
    report = api.score(g, recs, qids, text_report=saved)
    head = {"run_id": run_dir.name, "domain": report.pop("domain")}
    if not g.is_pf:          # a paperfactory run has the text score only (cli: `evqa eval --text`)
        head.update(config_name=cfg.name, closed_book=cfg.closed_book)
    out = {**head, **report}
    if write:
        (run_dir / "eval.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def score_text(run_dir: Path, reader: str = READER, judge_model: str = JUDGE, reader_chat: Chat | None = None,
               judge_chat: Chat | None = None) -> dict[str, Any]:
    """L3-text of a run (thesis_scorer.text): eval_text.json and <qid>/claims.json, then eval.json re-made with it.
    Tests pass reader_chat / judge_chat (fake senders)."""
    run_dir = Path(run_dir)
    cfg, qids, g, recs = _inputs(run_dir, "medical")
    out = text.score(g, recs, qids, reader_chat or Chat(reader), judge_chat or Chat(judge_model), claims_dir=run_dir,
                     system=cfg.system or "evqa")
    out = {"version": out.pop("version"), "run_id": run_dir.name, **out}
    (run_dir / "eval_text.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    score_run(run_dir, cfg.domain)
    return out


def _judge_chat(cfg: RunConfig) -> Chat:
    """The run's judge step as a scorer model (the scorer calls models through LiteLLM only)."""
    step: StepLLM = cfg.llm_for("judge")
    if step.backend != "qwen":
        raise SystemExit(f"judge step backend {step.backend!r}: the scorer calls LiteLLM models only (qwen)")
    return Chat(step.model, think=step.think)


def judge_run(run_dir: Path, chat: Chat | None = None) -> dict[str, Any]:
    """Blind label judge (thesis_scorer.judge.label_judge) into eval.json "label_judge"."""
    run_dir = Path(run_dir)
    cfg, qids, g, recs = _inputs(run_dir, "medical")
    eval_path = run_dir / "eval.json"
    ev = json.loads(eval_path.read_text(encoding="utf-8")) if eval_path.is_file() else score_run(run_dir)
    out = judge.label_judge(g, recs, chat or _judge_chat(cfg), [q for q in ev.get("questions", {})])
    ev["label_judge"] = out
    eval_path.write_text(json.dumps(ev, indent=2) + "\n", encoding="utf-8")
    return out


def judge_population(run_dir: Path, chat: Chat | None = None, write: bool = True) -> dict[str, Any]:
    """Settle unverified populations (thesis_scorer.judge.population_judge) -> population_judge.json; eval.json is
    not changed."""
    run_dir = Path(run_dir)
    cfg, qids, g, recs = _inputs(run_dir, "medical")
    ev = score_run(run_dir, domain=cfg.domain, write=False)
    got = judge.population_judge(g, recs, ev, chat or _judge_chat(cfg))
    ex = cfg.llm_for("extract")
    out = {"run_id": ev["run_id"], "scorer": ev["scorer"], "judge_model": got.pop("judge_model"),
           "extract_model": f"{ex.backend}:{ex.model}", **got}
    if write:
        (run_dir / "population_judge.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out
