"""The judge test and the report.

Only current marks count (`marking.current_marks`: made from the saved answer and the sheet as they are now, the
question still in the file). Marks left from an older answer, sheet or question are counted as "not current", and
saved answers with no marks file as "skipped"; `answers` is every saved answer.

Judge test: about 30 judged answers Aditya hand-marks on the review page (`sample.json`: item ids; `marks.json`:
item id -> `{"points": {pid: bool}, "faithful": bool | None, "by", "at", "answer_sha256", "sheet_sha256"}`, the
two hashes of the marks file the hand mark was made on), and `agreement` between his marks and the judge's C ticks
(and B for "faithful"). Below `FLAG_BELOW` the report says so as a limitation. Aditya marks blind, so the report
names a judge-test item only by its number on the review page (from 1), domain, seed and question id, never by its
system, and shows how the judge ticked an item only once every item is marked.

Report: per domain and system, A, B and C with the baseline next to the system, the A cross-check by code (no person
checks A), pending items, and how many marks rest on a sheet nobody checked; per domain the sheets of every seed,
the most missed points and the judge-test items."""
from __future__ import annotations

import json
import random
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from jsonio import write_json_atomic
from synth3.answers import AnswerRecord, item_id
from synth3.baseline import BASELINE
from synth3.cliargs import each_folder
from synth3.judge import planted_facts
from synth3.marking import current_marks, is_pending, marks_path, saved_answers
from synth3.questions import QUESTIONS, QuestionSet, load_questions
from synth3.sheetfacts import Folder
from synth3.sheets import folders_of, load_sheet, stale
from synth3.spec import SPECS, load_spec
from synth3.system import SYSTEM

JUDGE_TEST = SPECS / "judge-test"
FLAG_BELOW = 0.80
SAMPLE = 30
MOST_MISSED = 5
_SEED = re.compile(r"^s(\d+)$")


def item_parts(item: str) -> tuple[str, int, str, str]:
    """`<domain>/s<seed>/<system>/<qid>` -> (domain, seed, system, qid); any other shape is a `ValueError`."""
    parts = item.split("/")
    if len(parts) != 4 or not _SEED.match(parts[1]):
        raise ValueError(f"judge-test item {item!r} is not <domain>/s<seed>/<system>/<qid>")
    return parts[0], int(parts[1][1:]), parts[2], parts[3]


# --- current marks ----------------------------------------------------------------------------------------------

def answers_of(results: Path, folder: Folder, qs: QuestionSet, sheets_root: Path) -> list[tuple[AnswerRecord,
                                                                                               dict | None, str]]:
    """Every saved answer of one folder with its marks and its state: "judged" (current marks), "not current" (a
    marks file that `current_marks` refuses, or one that does not load) or "skipped" (no marks file)."""
    domain = folder.spec.domain
    out = []
    for rec in saved_answers(results, domain, folder.seed, None):
        path = marks_path(results, domain, folder.seed, rec.system, rec.question_id)
        if not path.is_file():
            out.append((rec, None, "skipped"))
            continue
        try:
            marks = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            out.append((rec, None, "not current"))
            continue
        sheet = load_sheet(sheets_root, domain, folder.seed, rec.question_id)
        ok = isinstance(marks, dict) and current_marks(marks, rec, folder, qs, sheet)
        out.append((rec, marks if ok else None, "judged" if ok else "not current"))
    return out


def _one_domain(domains: list[str], folders: Path | None) -> None:
    if folders is not None and len(domains) > 1:
        raise ValueError(f"--folders holds the s<seed>/ folders of one domain; pass one domain with it, not "
                         f"{', '.join(domains)}")


def _each_domain_folder(results: Path, domain: str, folders: Path | None, spec_root: Path, questions_root: Path,
                        fn: Callable[[Folder, QuestionSet], None]) -> None:
    """`fn` on every folder of the domain: every `s<seed>/` of its folder set, and every seed with results (a seed
    with results but no folder stops the command, see `each_folder`)."""
    spec = load_spec(domain, spec_root)
    qs = load_questions(domain, spec, questions_root)
    root = folders or folders_of(domain)
    seeds = sorted({int(m[1]) for d in (root, results / domain) if d.is_dir() for p in d.iterdir()
                    if p.is_dir() and (m := _SEED.match(p.name))})

    def step(folder: Folder) -> tuple[list[str], bool]:
        fn(folder, qs)
        return [], False

    each_folder(root, seeds, spec, step)


def current_marks_of(results: Path, domains: list[str], sheets_root: Path, folders: Path | None = None,
                     spec_root: Path = SPECS, questions_root: Path = QUESTIONS) -> dict[str, dict]:
    """The current marks of those domains by item id (what the judge-test sample draws from). `folders` holds one
    domain's `s<seed>/` (default: each domain's built set)."""
    _one_domain(domains, folders)
    out: dict[str, dict] = {}

    def fn(folder: Folder, qs: QuestionSet) -> None:
        for rec, marks, state in answers_of(results, folder, qs, sheets_root):
            if state == "judged":
                out[item_id(rec)] = marks

    for domain in domains:
        _each_domain_folder(results, domain, folders, spec_root, questions_root, fn)
    return out


# --- the sample and the hand marks ------------------------------------------------------------------------------

def pick_sample(marks: dict[str, dict], n: int = SAMPLE, seed: int = 0, have: list[str] = ()) -> list[str]:
    """From current marks (`current_marks_of`), items whose C is `ok`: half `rag-baseline` and half other systems
    (the other half fills up when one side is short), at most 2 per (domain, question) counting the items in `have`,
    which are left out. Seeded, and in a seeded shuffled order: the review page numbers the items in sample order,
    and a sorted order would put every engine item of a seed before every baseline item, which would tell Aditya the
    system while he marks blind."""
    held = set(have)
    pools: dict[bool, list[str]] = {True: [], False: []}   # True: the baseline
    for item in sorted(marks):
        m = marks[item]
        if item not in held and m["C"]["status"] == "ok":
            pools[m["system"] == BASELINE].append(item)
    rng = random.Random(seed)
    for pool in pools.values():
        rng.shuffle(pool)

    def key(item: str) -> str:
        domain, _, _, qid = item_parts(item)
        return f"{domain}/{qid}"

    used: Counter = Counter(key(i) for i in held)
    picked: list[str] = []

    def take(pool: list[str], want: int) -> None:
        got = 0
        for item in pool:
            if got == want or len(picked) == n:
                return
            if item not in picked and used[key(item)] < 2:
                picked.append(item)
                used[key(item)] += 1
                got += 1

    half = n // 2
    take(pools[True], half)
    take(pools[False], n - half)
    take(pools[True], n - len(picked))    # a short side: the other one fills up
    take(pools[False], n - len(picked))
    order = sorted(picked)
    random.Random(f"synth3:judge-sample:order:{seed}").shuffle(order)
    return order


def _load(path: Path, want: type, what: str):
    """The JSON of a judge-test file; a damaged one is a `ValueError` naming it."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as err:
        raise ValueError(f"{path}: damaged, not JSON ({err})") from err
    if not isinstance(data, want):
        raise ValueError(f"{path}: damaged, not {what}")
    return data


def load_sample(root: Path) -> list[str]:
    path = Path(root) / "sample.json"
    if not path.is_file():
        return []
    data = _load(path, list, "a list of item ids")
    if not all(isinstance(i, str) for i in data):
        raise ValueError(f"{path}: damaged, not a list of item ids")
    return data


def save_sample(root: Path, items: list[str]) -> Path:
    path = Path(root) / "sample.json"
    write_json_atomic(path, items)
    return path


def load_hand_marks(root: Path) -> dict:
    path = Path(root) / "marks.json"
    if not path.is_file():
        return {}
    data = _load(path, dict, "a mapping of item ids to hand marks")
    if not all(isinstance(v, dict) for v in data.values()):
        raise ValueError(f"{path}: damaged, not a mapping of item ids to hand marks")
    return data


def save_hand_mark(root: Path, item: str, points: dict[str, bool], faithful: bool | None, by: str, at: str, *,
                   answer_sha256: str, sheet_sha256: str) -> Path:
    """`answer_sha256` and `sheet_sha256` are the marks file's: what the points and the answer were."""
    marks = load_hand_marks(root)
    marks[item] = {"points": points, "faithful": faithful, "by": by, "at": at, "answer_sha256": answer_sha256,
                   "sheet_sha256": sheet_sha256}
    path = Path(root) / "marks.json"
    write_json_atomic(path, marks)
    return path


def hand_mark_fits(hand: dict, marks: dict) -> bool:
    """True when the hand mark was made on this marks file's answer and sheet (point ids are positions, so after a
    re-judge the same id can be another statement)."""
    sheet = marks.get("sheet") if isinstance(marks.get("sheet"), dict) else {}
    return (hand.get("answer_sha256") is not None and hand.get("answer_sha256") == marks.get("answer_sha256")
            and hand.get("sheet_sha256") is not None and hand.get("sheet_sha256") == sheet.get("sha256"))


def _judge_faithful(m: dict) -> bool | None:
    """B `ok` with no invented and no contradicted claim; None when B is pending."""
    b = m.get("B")
    if not b or b["status"] != "ok":
        return None
    return not b["invented"] and not b["contradicted"]


def agreement(sample: list[str], hand: dict, judged: dict[str, dict]) -> dict:
    """Over every (item, point) that both the judge (C ticks of the current marks `judged`) and Aditya marked, on
    the same answer and sheet. Items are named by their number on the review page (from 1), never by id: the id
    names the system. A hand mark made on another answer or sheet is left out and listed in `to_mark_again`; one
    whose item has no current marks is listed in `not_judged`. Until every sample item is marked (`complete`), every
    agreement number is None: each new mark would move it and show how the judge marked that item."""
    points = agree = 0
    marked: set[str] = set()
    disagreements: list[dict] = []
    again: list[int] = []
    not_judged: list[int] = []
    done = 0
    f_n = f_agree = 0
    for n, item in enumerate(sample, 1):
        h, m = hand.get(item), judged.get(item)
        if not h:
            continue
        if not m:
            not_judged.append(n)
            continue
        if not hand_mark_fits(h, m):
            again.append(n)
            continue
        done += 1
        ticks = {t["point"]: t["met"] for t in m["C"]["ticks"]}
        for pid, said in h["points"].items():
            if pid in ticks:
                points += 1
                marked.add(item)
                if ticks[pid] == said:
                    agree += 1
                else:
                    disagreements.append({"n": n, "point": pid, "judge": ticks[pid], "hand": said})
        if h.get("faithful") is not None and (j := _judge_faithful(m)) is not None:
            f_n += 1
            f_agree += j == h["faithful"]
    out = {"marked": done, "of": len(sample), "to_mark_again": again, "not_judged": not_judged}
    if not (sample and done == len(sample)):
        # before the last mark, any agreement number moves with each new mark and shows how the judge marked it
        return {**out, "complete": False, "points": None, "agree": None, "rate": None, "flag": False,
                "answers_marked": None, "faithful": {"n": None, "agree": None, "rate": None}, "disagreements": None}
    rate = agree / points if points else None
    return {**out, "complete": True, "points": points, "agree": agree, "rate": rate,
            "flag": rate is not None and rate < FLAG_BELOW, "answers_marked": len(marked),
            "faithful": {"n": f_n, "agree": f_agree, "rate": f_agree / f_n if f_n else None},
            "disagreements": disagreements}


# --- the report -------------------------------------------------------------------------------------------------

def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _row() -> dict:
    return {"answers": 0, "judged": 0, "not_current": 0, "skipped": 0, "unchecked": 0, "pending": 0,
            "cut_texts": 0, "pulled_cut": 0, "plans_person": 0, "plans_system": 0, "facts_left_out": 0, "_a": [], "_anchored": [], "_b": [], "_c": [], "_c_cant": [],
            "_c_other": [], "_found": [0, 0], "_missing": [0, 0]}


def _final(row: dict) -> dict:
    out = {k: v for k, v in row.items() if not k.startswith("_")}
    out |= {"a_mean": _mean(row["_a"]), "anchored_mean": _mean(row["_anchored"]), "b_mean": _mean(row["_b"]),
            "c_mean": _mean(row["_c"]), "c_cant_tell": _mean(row["_c_cant"]), "c_others": _mean(row["_c_other"]),
            "a_found_untouched": row["_found"][0] / row["_found"][1] if row["_found"][1] else None,
            "a_missing_touched": row["_missing"][0] / row["_missing"][1] if row["_missing"][1] else None}
    return out


def _touches(planted, pulled: list[tuple[str, int, int]]) -> dict[str, bool]:
    """Planted fact id -> whether a pulled fact of its paper shares a character with one of its spans."""
    return {p.id: any(s < b and a < e for a, b in p.spans for paper, s, e in pulled if paper == p.paper)
            for ps in planted.values() for p in ps}


def _add_marks(row: dict, m: dict) -> None:
    row["judged"] += 1
    row["unchecked"] += m["sheet"]["status"] != "checked"
    row["pending"] += is_pending(m)
    a, b, c = m["A"], m["B"], m["C"]
    if a:
        row["pulled_cut"] += len(a["pulled_cut"])
        if not a["pending_papers"] and a["score"] is not None:
            row["_a"].append(a["score"])
        if a["anchored"] is not None:
            row["_anchored"].append(a["anchored"])
    if b["status"] == "ok" and b["score"] is not None:
        row["_b"].append(b["score"])
    if c["status"] == "ok" and c["score"] is not None:
        row["_c"].append(c["score"])
        row["_c_cant" if m["sheet"]["cant_tell"] else "_c_other"].append(c["score"])


def _cross_check(row: dict, m: dict, planted, rec) -> None:
    """The A judge's `found` marks whose span no pulled fact touches, and its `missing` marks whose span one does."""
    pulled = [(f.paper, f.start, f.end) for f in rec.facts or [] if f.start is not None and f.end is not None]
    touched = _touches(planted, pulled)
    for marks in m["A"]["papers"].values():
        for mk in marks:
            if mk["fact"] not in touched:
                continue
            if mk["verdict"] == "found":
                row["_found"][1] += 1
                row["_found"][0] += not touched[mk["fact"]]
            elif mk["verdict"] == "missing":
                row["_missing"][1] += 1
                row["_missing"][0] += touched[mk["fact"]]


def build_report(results: Path, domains: list[str], sheets_root: Path, judge_test_root: Path,
                 folders: Path | None = None, spec_root: Path = SPECS, questions_root: Path = QUESTIONS) -> dict:
    """The numbers of the report, from current marks only. `folders` holds one domain's `s<seed>/` (default: each
    domain's built set; a `ValueError` with more than one domain); the A cross-check needs the planted fact spans
    of each folder, the sheet counts (every seed of the domain) need its question list."""
    _one_domain(domains, folders)
    sample = load_sample(judge_test_root)
    current: dict[str, dict] = {}
    out: dict = {"domains": {}}
    for domain in domains:
        rows: dict[str, dict] = {}
        sheets = {"checked": 0, "drafted": 0, "stale": 0, "missing": 0}
        missed: dict[tuple, list] = {}   # (question, seed, point) -> [missed, of, text]

        def fn(folder: Folder, qs: QuestionSet, rows=rows, sheets=sheets, missed=missed) -> None:
            for q in qs.questions:
                sheet = load_sheet(sheets_root, folder.spec.domain, folder.seed, q.id)
                sheets["missing" if sheet is None else "stale" if stale(sheet, q, folder) else sheet.status] += 1
            for rec, m, state in answers_of(results, folder, qs, sheets_root):
                row = rows.setdefault(rec.system, _row())
                row["answers"] += 1
                row["plans_person"] += rec.plan_confirmed_by == "person"
                row["plans_system"] += rec.plan_confirmed_by == "system"
                row["facts_left_out"] += bool(rec.facts_left_out)
                if m is None:
                    row[state.replace(" ", "_")] += 1
                    continue
                current[item_id(rec)] = m
                _add_marks(row, m)
                row["cut_texts"] += rec.text_cut
                texts = {p["id"]: p["text"] for p in m["sheet"]["points"]}   # the points the judge saw
                for t in m["C"]["ticks"]:
                    entry = missed.setdefault((rec.question_id, folder.seed, t["point"]),
                                              [0, 0, texts.get(t["point"], "")])
                    entry[1] += 1
                    entry[0] += not t["met"]
                if m["A"]:
                    _cross_check(row, m, planted_facts(folder, qs.get(rec.question_id)), rec)

        _each_domain_folder(results, domain, folders, spec_root, questions_root, fn)
        top = sorted(missed.items(), key=lambda kv: (-kv[1][0], kv[0]))[:MOST_MISSED]
        out["domains"][domain] = {
            "systems": {s: _final(rows[s]) for s in sorted(rows, key=lambda s: (s == BASELINE, s))},
            "sheets": sheets,
            "most_missed": [{"question": k[0], "seed": k[1], "point": k[2], "missed": v[0], "of": v[1],
                             "text": v[2]} for k, v in top if v[0]],
            "judge_test_items": [{"n": n, "domain": d, "seed": s, "question": qid}
                                 for n, (d, s, _, qid) in ((n, item_parts(i)) for n, i in enumerate(sample, 1))
                                 if d == domain]}
    out["agreement"] = agreement(sample, load_hand_marks(judge_test_root), current)
    return out


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def _numbers(ns: list[int]) -> str:
    return ", ".join(str(n) for n in ns)


def render_report(r: dict) -> str:
    """The report as markdown; a mean over no values is `n/a`."""
    lines = ["# Judge report", "",
             "`answers` counts every saved answer; `judged` those with current marks (the only ones in the means); "
             "`not current` those whose marks were made from an older answer, sheet or question; `skipped` those "
             "with no marks.", ""]
    head = ("| system | answers | judged | not current | skipped | A | anchored | A found, span untouched | "
            "A missing, span touched | B | C | C can't-tell | C others | pending | cut texts | papers cut | "
            "on unchecked sheets | plans by person / by system | answers with facts left out |")
    for domain, d in r["domains"].items():
        s = d["sheets"]
        lines += [f"## {domain}", "", head, "|" + " --- |" * 19]
        for name, x in d["systems"].items():
            lines.append(f"| {name} | {x['answers']} | {x['judged']} | {x['not_current']} | {x['skipped']} | "
                         f"{_pct(x['a_mean'])} | {_pct(x['anchored_mean'])} | "
                         f"{_pct(x['a_found_untouched'])} | {_pct(x['a_missing_touched'])} | {_pct(x['b_mean'])} | "
                         f"{_pct(x['c_mean'])} | {_pct(x['c_cant_tell'])} | {_pct(x['c_others'])} | {x['pending']} | "
                         f"{x['cut_texts']} | {x['pulled_cut']} | {x['unchecked']} of {x['judged']} unchecked | "
                         f"{x['plans_person']} / {x['plans_system']} | {x['facts_left_out']} |")
        by_system = sum(x["plans_system"] for x in d["systems"].values())
        if by_system:
            of = (d["systems"].get(SYSTEM) or {}).get("answers", 0)   # the system's answers only, not the engine's
            lines += ["", f"{by_system} of {of} system answers ran on plans the system confirmed, not a person "
                          f"(spec §8 puts a person's edit in the system): reported as a limitation."]
        lines += ["", f"Sheets: {s['checked']} checked, {s['drafted']} drafted, {s['stale']} stale, "
                      f"{s['missing']} missing.", ""]
        if d["most_missed"]:
            lines.append("Most missed points:")
            lines += [f"- {m['question']} s{m['seed']} {m['point']}: missed {m['missed']} of {m['of']} "
                      f"- {m['text'] or 'no sheet text'}" for m in d["most_missed"]]
            lines.append("")
        items = [f"{i['n']} ({i['question']}, s{i['seed']})" for i in d["judge_test_items"]]
        lines.append(f"Judge-test items: {', '.join(items) or 'none'}")
        lines.append("")
    a = r["agreement"]
    lines.append(f"Judge test: {a['marked']} of {a['of']} marked.")
    if a["to_mark_again"]:
        lines.append(f"Mark again (the answer or its sheet changed since): {_numbers(a['to_mark_again'])}.")
    if a["not_judged"]:
        lines.append(f"Marked but not judged now (run synth3 judge): {_numbers(a['not_judged'])}.")
    if not a["complete"]:
        lines.append("Judge agreement shown once every judge-test item is marked.")
        return "\n".join(lines) + "\n"
    if a["rate"] is None:
        lines.append("Judge agreement n/a (no hand marks yet).")
    elif a["flag"]:
        lines.append(f"Judge agreement {_pct(a['rate'])} (below 80%: reported as a limitation).")
    else:
        lines.append(f"Judge agreement {_pct(a['rate'])}.")
    lines.append(f"{a['agree']} of {a['points']} points over {a['answers_marked']} answers; faithful: "
                 f"{a['faithful']['agree']} of {a['faithful']['n']} ({_pct(a['faithful']['rate'])}).")
    if a["disagreements"]:
        lines.append("Disagreements (item number, point: judge / you):")
        lines += [f"- {x['n']} {x['point']}: judge {'met' if x['judge'] else 'not met'} / you "
                  f"{'met' if x['hand'] else 'not met'}" for x in a["disagreements"]]
    return "\n".join(lines) + "\n"
