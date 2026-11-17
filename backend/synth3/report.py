"""The judge test and the report.

Judge test: about 30 judged answers Aditya hand-marks on the review page (`sample.json`: item ids; `marks.json`:
item id -> `{"points": {pid: bool}, "faithful": bool | None, "by", "at"}`), and `agreement` between his marks and
the judge's C ticks (and B for "faithful"). Below `FLAG_BELOW` the report says so as a limitation.

Report: per domain and system, A, B and C with the baseline next to the system, the A cross-check by code (no person
checks A), pending items, and how many marks rest on a sheet nobody checked; per domain the sheets, the most missed
points and the judge-test items."""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

from jsonio import write_json_atomic
from synth3.answers import answer_path, load_answer
from synth3.baseline import BASELINE
from synth3.cliargs import each_folder
from synth3.judge import planted_facts
from synth3.marking import is_pending
from synth3.questions import QUESTIONS, load_questions
from synth3.sheetfacts import Folder
from synth3.sheets import SHEETS, folders_of, load_sheet
from synth3.spec import SPECS, load_spec

JUDGE_TEST = SPECS / "judge-test"
FLAG_BELOW = 0.80
SAMPLE = 30
MOST_MISSED = 5


# --- the sample and the hand marks ------------------------------------------------------------------------------

def load_all_marks(results: Path, domains: list[str]) -> dict[str, dict]:
    """Every marks file of those domains by item id."""
    out: dict[str, dict] = {}
    for domain in domains:
        for path in sorted((results / domain).glob("s*/*/*.marks.json")):
            marks = json.loads(path.read_text(encoding="utf-8"))
            out[marks["item"]] = marks
    return out


def pick_sample(results: Path, domains: list[str], n: int = SAMPLE, seed: int = 0, have: list[str] = ()) -> list[str]:
    """Judged items whose C is `ok`: half `rag-baseline` and half other systems (the other half fills up when one side
    is short), at most 2 per (domain, question), items in `have` left out. Seeded, and in a seeded shuffled order:
    the review page numbers the items in sample order, and a sorted order would put every engine item of a seed
    before every baseline item, which would tell Aditya the system while he marks blind."""
    held = set(have)
    marks = load_all_marks(results, domains)
    pools: dict[bool, list[str]] = {True: [], False: []}   # True: the baseline
    for item in sorted(marks):
        m = marks[item]
        if item not in held and m["C"]["status"] == "ok":
            pools[m["system"] == BASELINE].append(item)
    rng = random.Random(seed)
    for pool in pools.values():
        rng.shuffle(pool)
    used: Counter = Counter()
    picked: list[str] = []

    def take(pool: list[str], want: int) -> None:
        got = 0
        for item in pool:
            if got == want or len(picked) == n:
                return
            key = item.split("/")[0] + "/" + item.split("/")[3]
            if item not in picked and used[key] < 2:
                picked.append(item)
                used[key] += 1
                got += 1

    half = n // 2
    take(pools[True], half)
    take(pools[False], n - half)
    take(pools[True], n - len(picked))    # a short side: the other one fills up
    take(pools[False], n - len(picked))
    order = sorted(picked)
    random.Random(f"synth3:judge-sample:order:{seed}").shuffle(order)
    return order


def load_sample(root: Path) -> list[str]:
    path = Path(root) / "sample.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def save_sample(root: Path, items: list[str]) -> Path:
    path = Path(root) / "sample.json"
    write_json_atomic(path, items)
    return path


def load_hand_marks(root: Path) -> dict:
    path = Path(root) / "marks.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def save_hand_mark(root: Path, item: str, points: dict[str, bool], faithful: bool | None, by: str, at: str) -> Path:
    marks = load_hand_marks(root)
    marks[item] = {"points": points, "faithful": faithful, "by": by, "at": at}
    path = Path(root) / "marks.json"
    write_json_atomic(path, marks)
    return path


def _judge_faithful(m: dict) -> bool | None:
    """B `ok` with no invented and no contradicted claim; None when B is pending."""
    b = m.get("B")
    if not b or b["status"] != "ok":
        return None
    return not b["invented"] and not b["contradicted"]


def agreement(sample: list[str], hand: dict, judged: dict[str, dict]) -> dict:
    """Over every (item, point) that both the judge (C ticks) and Aditya marked."""
    points = agree = 0
    marked: set[str] = set()
    disagreements: list[dict] = []
    f_n = f_agree = 0
    for item in sample:
        h, m = hand.get(item), judged.get(item)
        if not h or not m:
            continue
        ticks = {t["point"]: t["met"] for t in m["C"]["ticks"]}
        for pid, said in h["points"].items():
            if pid in ticks:
                points += 1
                marked.add(item)
                if ticks[pid] == said:
                    agree += 1
                else:
                    disagreements.append({"item": item, "point": pid, "judge": ticks[pid], "hand": said})
        if h.get("faithful") is not None and (j := _judge_faithful(m)) is not None:
            f_n += 1
            f_agree += j == h["faithful"]
    rate = agree / points if points else None
    return {"points": points, "agree": agree, "rate": rate, "flag": rate is not None and rate < FLAG_BELOW,
            "answers_marked": len(marked),
            "faithful": {"n": f_n, "agree": f_agree, "rate": f_agree / f_n if f_n else None},
            "disagreements": disagreements}


# --- the report -------------------------------------------------------------------------------------------------

def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _row() -> dict:
    return {"answers": 0, "unchecked": 0, "pending": 0, "cut_texts": 0, "pulled_cut": 0,
            "_a": [], "_anchored": [], "_b": [], "_c": [], "_c_cant": [], "_c_other": [],
            "_found": [0, 0], "_missing": [0, 0]}


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
    row["answers"] += 1
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
    """The numbers of the report. `folders` holds `<domain>`'s `s<seed>/` (default: the domain's built set); the A
    cross-check needs the planted fact spans of each folder, the sheet counts need its question list."""
    marks = load_all_marks(results, domains)
    sample = load_sample(judge_test_root)
    out: dict = {"domains": {}}
    for domain in domains:
        spec = load_spec(domain, spec_root)
        qs = load_questions(domain, spec, questions_root)
        mine = [m for m in marks.values() if m["item"].startswith(f"{domain}/")]
        rows: dict[str, dict] = {}
        for m in mine:
            _add_marks(rows.setdefault(m["system"], _row()), m)
        by_seed: dict[int, list[dict]] = {}
        for m in mine:
            by_seed.setdefault(m["seed"], []).append(m)
        sheets = {"checked": 0, "drafted": 0, "missing": 0}
        missed: dict[tuple, list] = {}   # (question, seed, point) -> [missed, of, text]

        def step(folder: Folder, domain=domain, qs=qs, rows=rows, by_seed=by_seed, sheets=sheets, missed=missed):
            for q in qs.questions:
                sheet = load_sheet(sheets_root, domain, folder.seed, q.id)
                sheets["missing" if sheet is None else sheet.status] += 1
            for m in by_seed.get(folder.seed, []):
                row = rows[m["system"]]
                try:
                    q = qs.get(m["question_id"])
                except KeyError:
                    q = None
                sheet = load_sheet(sheets_root, domain, folder.seed, m["question_id"])
                texts = {p.id: p.text for p in sheet.points} if sheet else {}
                for t in m["C"]["ticks"]:
                    entry = missed.setdefault((m["question_id"], folder.seed, t["point"]),
                                              [0, 0, texts.get(t["point"], "")])
                    entry[1] += 1
                    entry[0] += not t["met"]
                path = answer_path(results, domain, folder.seed, m["system"], m["question_id"])
                if not path.is_file():
                    continue
                rec = load_answer(path)
                row["cut_texts"] += rec.text_cut
                if m["A"] and q is not None:
                    _cross_check(row, m, planted_facts(folder, q), rec)
            return [], False

        each_folder(folders or folders_of(domain), sorted(by_seed), spec, step)
        top = sorted(missed.items(), key=lambda kv: (-kv[1][0], kv[0]))[:MOST_MISSED]
        out["domains"][domain] = {
            "systems": {s: _final(rows[s]) for s in sorted(rows, key=lambda s: (s == BASELINE, s))},
            "sheets": sheets,
            "most_missed": [{"question": k[0], "seed": k[1], "point": k[2], "missed": v[0], "of": v[1],
                             "text": v[2]} for k, v in top if v[0]],
            "judge_test_items": sorted(i for i in sample if i.startswith(f"{domain}/"))}
    out["agreement"] = agreement(sample, load_hand_marks(judge_test_root), marks)
    return out


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def render_report(r: dict) -> str:
    """The report as markdown; a mean over no values is `n/a`."""
    lines = ["# Judge report", ""]
    head = ("| system | answers | A | anchored | A found, span untouched | A missing, span touched | B | C | "
            "C can't-tell | C others | pending | cut texts | papers cut | on unchecked sheets |")
    for domain, d in r["domains"].items():
        s = d["sheets"]
        lines += [f"## {domain}", "", head, "|" + " --- |" * 14]
        for name, x in d["systems"].items():
            lines.append(f"| {name} | {x['answers']} | {_pct(x['a_mean'])} | {_pct(x['anchored_mean'])} | "
                         f"{_pct(x['a_found_untouched'])} | {_pct(x['a_missing_touched'])} | {_pct(x['b_mean'])} | "
                         f"{_pct(x['c_mean'])} | {_pct(x['c_cant_tell'])} | {_pct(x['c_others'])} | {x['pending']} | "
                         f"{x['cut_texts']} | {x['pulled_cut']} | {x['unchecked']} of {x['answers']} unchecked |")
        lines += ["", f"Sheets: {s['checked']} checked, {s['drafted']} drafted, {s['missing']} missing.", ""]
        if d["most_missed"]:
            lines.append("Most missed points:")
            lines += [f"- {m['question']} s{m['seed']} {m['point']}: missed {m['missed']} of {m['of']} "
                      f"- {m['text'] or 'no sheet text'}" for m in d["most_missed"]]
            lines.append("")
        lines.append(f"Judge-test items: {', '.join(d['judge_test_items']) or 'none'}")
        lines.append("")
    a = r["agreement"]
    if a["rate"] is None:
        lines.append("Judge agreement n/a (no hand marks yet).")
    elif a["flag"]:
        lines.append(f"Judge agreement {_pct(a['rate'])} (below 80%: reported as a limitation).")
    else:
        lines.append(f"Judge agreement {_pct(a['rate'])}.")
    lines.append(f"{a['agree']} of {a['points']} points over {a['answers_marked']} answers; faithful: "
                 f"{a['faithful']['agree']} of {a['faithful']['n']} ({_pct(a['faithful']['rate'])}).")
    return "\n".join(lines) + "\n"
