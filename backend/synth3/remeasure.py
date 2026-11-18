"""One folder's kept system runs re-run N times with no cache, and measured (`synth3 reexec`).

The re-runs and their measure live only under `results/<domain>/reexec/s<seed>/`; the original run folders, the record
cache and the saved answers are never touched, and nothing here is collected or judged.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from evidence.replay import reexec
from evidence.rundir import REEXEC_FILE, RUN_CALLS_FILE, RUN_FILE, SEAL_FILE, RunDir, read_json
from evidence.stability import GROUPS, combine, measure, share
from jsonio import write_json_atomic
from modelcall import redact

NO_RUN = "no complete run; run synth3 system-run first"
SOURCE_FILE = "source.json"
STABILITY_FILE = "stability.json"
REPORT_FILE = "report.json"


def reexec_root(results: Path, domain: str, seed: int) -> Path:
    return results / domain / "reexec" / f"s{seed}"


def _start_folder(qdir: Path, original: Path, results: Path) -> None:
    """The question's re-run folder for this original run: one that names another chain head is moved aside."""
    head = read_json(original / RUN_FILE).get("chain_head")
    source = qdir / SOURCE_FILE
    if qdir.is_dir():
        try:
            old = read_json(source).get("chain_head") if source.is_file() else None
        except ValueError:
            old = None
        if old != head:
            n = 1
            while (qdir.parent / f"{qdir.name}.old-{n}").exists():
                n += 1
            qdir.rename(qdir.parent / f"{qdir.name}.old-{n}")
    qdir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(source, {"run": original.relative_to(results).as_posix(), "chain_head": head})


def _kept(qdir: Path) -> list[Path]:
    return sorted(p for p in qdir.iterdir() if p.is_dir() and (p / REEXEC_FILE).is_file() and RunDir(p).complete)


def _commit(rerun: Path) -> str | None:
    try:
        return read_json(rerun / SEAL_FILE).get("code_commit")
    except (OSError, ValueError):
        return None


def measure_folder(results: Path, domain: str, seed: int, qids: Sequence[str], *, times: int = 5,
                   provider=None) -> dict:
    from synth3.system import run_path
    root = reexec_root(results, domain, seed)
    reports: dict[str, dict] = {}
    skipped: dict[str, str] = {}
    failed: dict[str, str] = {}
    commits: dict[str, str | None] = {}
    made = kept = 0
    for qid in qids:
        original = run_path(results, domain, seed, qid)
        if not RunDir(original).complete:
            skipped[qid] = NO_RUN
            continue
        if not (original / RUN_CALLS_FILE).is_file():
            skipped[qid] = f"no {RUN_CALLS_FILE} in the run; nothing to compare"
            continue
        qdir = root / qid
        _start_folder(qdir, original, results)
        have = _kept(qdir)[:times]
        kept += len(have)
        try:
            for _ in range(times - len(have)):
                reexec(original, all_calls=True, out_dir=qdir, **({"provider": provider} if provider else {}))
                made += 1
        except Exception as err:  # noqa: BLE001 - one question's failure must not stop the folder
            failed[qid] = redact(f"{type(err).__name__}: {err}")[:300]
            continue
        reruns = _kept(qdir)[:times]
        try:
            report = measure(original, reruns)
        except Exception as err:  # noqa: BLE001 - the re-runs stay; the reason is reported
            skipped[qid] = redact(f"not measured ({type(err).__name__}): {err}")[:300]
            continue
        write_json_atomic(qdir / STABILITY_FILE, report)
        reports[qid] = report
        commits.update({p.name: _commit(p) for p in reruns})
    out = {"domain": domain, "seed": seed, "times": times, "questions": reports,
           "total": combine(list(reports.values())), "made": made, "kept": kept, "skipped": skipped,
           "failed": failed, "commits": commits}
    root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(root / REPORT_FILE, out)
    return out


def commit_note(report: dict) -> str | None:
    distinct = sorted({str(c) for c in report["commits"].values()})
    if len(distinct) < 2:
        return None
    return (f"  note: the re-runs come from {len(distinct)} code commits ({', '.join(distinct)}); "
            "another commit can change every request")


def question_line(qid: str, report: dict) -> str:
    a = report["answers"]
    calls = sum(report["calls"][g]["calls"] for g in GROUPS)
    same = sum(report["calls"][g]["identical"] for g in GROUPS)
    return (f"  {qid}: text same {a['same_text']}/{a['compared']}, headline {a['same_headline']}/{a['compared']}, "
            f"identical calls {share(same, calls)}")
