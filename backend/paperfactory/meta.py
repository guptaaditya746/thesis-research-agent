"""What each output was made from (#8): `<name>.meta.json` next to world.json, work/<paper>/paper.md and report.json.

A meta file holds:
  inputs   hashes of everything that shapes the output: the config fields the step uses, the packs, the paper's
           notes, upstream outputs, prompt templates (PaperOrchestra's too). Compared on restart: when they differ
           the step is done again (the old output is renamed *.stale-N, never deleted) and the run prints which
           inputs changed.
  record   git commit, SCORING_VERSION, time. For the record only: a new commit alone must not redo paid work.
paper.meta.json has two parts: "inputs"/"written" (the writer's inputs, hash of the paper as written) and, after the
check step, "check"/"output" (the check's inputs, hash of the repaired paper). A run stopped in the middle of a
repair therefore redoes the check, never the (paid) writing.
An output with no meta file (made before #8, or by a run stopped at the wrong moment) has unknown settings: it is
made again (the old one kept as *.stale-N), or kept with --allow-mixed. Nothing here stops a run.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from repo_paths import REPO

from paperfactory import SCORING_VERSION, files

PO_PROMPTS = REPO / "external" / "paperorchestra" / "methods" / "prompts"


class MixedSettings(RuntimeError):
    """Outputs made under different (or unknown) settings would be combined."""


# ------------------------------------------------------------------ hashing
def h(x: Any) -> str:
    """Short stable hash of text, bytes or any JSON value."""
    b = x if isinstance(x, bytes) else x.encode() if isinstance(x, str) else \
        json.dumps(x, sort_keys=True, ensure_ascii=False, default=str).encode()
    return hashlib.sha256(b).hexdigest()[:16]


def file_hash(p: Path) -> str | None:
    return h(p.read_bytes()) if p.is_file() else None


def dir_hash(d: Path) -> str | None:
    if not d.is_dir():
        return None
    return h({str(p.relative_to(d)): h(p.read_bytes()) for p in sorted(d.rglob("*"))
              if p.is_file() and "__pycache__" not in p.parts})


def role(s, name: str) -> dict[str, Any]:
    """The fields of a role that shape its answers (not timeout, slots or prices)."""
    rm = s.role(name)
    d = {"backend": rm.backend, "model": rm.model}
    # what the backend uses; the configured base_url, never $LITELLM_BASE_URL (differs between shells)
    return d if rm.backend == "claude_cli" else d | {"base_url": rm.base_url, "max_tokens": rm.max_tokens}


def git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
                             timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=REPO,
                               capture_output=True, text=True, timeout=10).stdout.strip()
        return (sha or "unknown") + ("+dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def hashed(inputs: dict[str, Any]) -> dict[str, str]:
    return {k: h(v) for k, v in sorted(inputs.items())}


def record() -> dict[str, Any]:
    return {"git": git_commit(), "scoring_version": SCORING_VERSION, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}


def diff(old: dict[str, str] | None, inputs: dict[str, Any]) -> list[str]:
    now, old = hashed(inputs), old or {}
    return sorted(k for k in set(now) | set(old) if now.get(k) != old.get(k))


# ------------------------------------------------------------------ files
def path_of(output: Path) -> Path:
    """world.json -> world.meta.json; paper.md -> paper.meta.json; report.json -> report.meta.json."""
    return output.with_name(output.name.split(".", 1)[0] + ".meta.json")


def read(output: Path) -> dict[str, Any] | None:
    p = path_of(output)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    except json.JSONDecodeError:
        return None


def save(output: Path, m: dict[str, Any]) -> None:
    files.write_json(path_of(output), m | {"record": record()})


def set_aside(p: Path) -> Path:
    """Rename an outdated output (file or folder) and its meta to <name>.stale-<n>; nothing is deleted."""
    n = 1
    while (dest := p.with_name(f"{p.name}.stale-{n}")).exists():
        n += 1
    m = path_of(p) if p.is_file() and path_of(p).name == f"{p.stem}.meta.json" else None   # its own meta only
                                                       # (paper.repairs.json must not take paper.meta.json along)
    p.rename(dest)
    if m is not None and m.is_file():
        m.rename(m.with_name(f"{m.name}.stale-{n}"))
    return dest


def legacy(what: str, output: Path, allow_mixed: bool) -> bool:
    """An output without meta: its settings are unknown. -> True: make it again (the old one is kept as
    *.stale-N); False with allow_mixed: keep it. Never stops the run (Aditya, 22 Nov 2026: nothing soft stops)."""
    if allow_mixed:
        print(f"{what}: no meta file (made before settings were recorded); kept because of --allow-mixed")
        return False
    print(f"{what}: no meta file, so its settings are unknown; making it again (old one kept as *.stale-N)")
    return True


# ------------------------------------------------------------------ one output with one set of inputs
def stale(output: Path, inputs: dict[str, Any], allow_mixed: bool, what: str) -> bool:
    """world.json and similar: must the existing output be made again? Prints why."""
    if not output.is_file():
        return False
    m = read(output)
    if m is None:
        return legacy(what, output, allow_mixed)
    why = diff(m.get("inputs"), inputs) + (["output (edited by hand)"] if m.get("output") != file_hash(output)
                                           else [])
    if why:
        print(f"{what}: settings changed ({', '.join(why)}); doing it again")
    return bool(why)


def write(output: Path, inputs: dict[str, Any]) -> None:
    save(output, {"inputs": hashed(inputs), "output": file_hash(output)})


# ------------------------------------------------------------------ papers: written, then checked
def paper_written(paper: Path) -> Path:
    """The paper as PaperOrchestra wrote it: paper.raw.md once the check step has run, else paper.md."""
    raw = paper.with_name("paper.raw.md")
    return raw if raw.is_file() else paper


def write_stale(paper: Path, inputs: dict[str, Any], allow_mixed: bool, what: str) -> bool:
    if not paper.is_file():
        return False
    m = read(paper)
    if m is None or "inputs" not in m:     # no meta, or only a check part (a legacy paper kept with allow_mixed)
        return legacy(what, paper, allow_mixed)
    why = diff(m.get("inputs"), inputs)
    if m.get("written") != file_hash(paper_written(paper)):
        why.append("paper as written (edited by hand)")
    if why:
        print(f"{what}: writer settings changed ({', '.join(why)}); writing it again")
    return bool(why)


def write_done(paper: Path, inputs: dict[str, Any]) -> None:
    save(paper, {"inputs": hashed(inputs), "written": file_hash(paper)})


def check_state(paper: Path, inputs: dict[str, Any], allow_mixed: bool, what: str) -> tuple[str, list[str]]:
    """(state, inputs that changed). state: "todo" (never checked), "done" (checked with these inputs), "redo"
    (checked with other inputs, or paper.md changed since), "legacy_kept" (checked before #8, kept: allow_mixed)."""
    repairs = paper.with_name("paper.repairs.json")
    if not repairs.is_file():
        return "todo", []
    m = read(paper)
    if m is None:
        return ("redo", ["no meta file"]) if legacy(what, repairs, allow_mixed) else ("legacy_kept", [])
    if "check" not in m:                  # written under #8, stopped before the check's meta was saved
        print(f"{what}: the last check did not finish; checking it again")
        return "redo", ["unfinished"]
    why = diff(m.get("check"), inputs) + (["paper.md (edited by hand)"] if m.get("output") != file_hash(paper)
                                          else [])
    if why:
        print(f"{what}: check settings changed ({', '.join(why)}); checking it again")
        return "redo", why
    return "done", []


def check_done(paper: Path, inputs: dict[str, Any]) -> None:
    """After the check step (#4 repairs): the meta now also covers the repaired paper."""
    m = read(paper) or {}
    save(paper, {k: v for k, v in m.items() if k != "record"} | {"check": hashed(inputs),
                                                                  "output": file_hash(paper)})


def same_settings(metas: dict[str, dict[str, Any] | None], keys: dict[str, list[str]], allow_mixed: bool,
                  what: str) -> list[str]:
    """All outputs (e.g. the papers one evaluation reads) must share the inputs named in keys ({section: [names]}).
    Returns the warnings that were allowed (empty when everything agrees)."""
    legacy_ = sorted(k for k, m in metas.items() if m is None)
    groups: dict[str, list[str]] = {}
    for k, m in metas.items():
        if m is not None:
            sig = {sec: {x: (m.get(sec) or {}).get(x) for x in names} for sec, names in keys.items()}
            groups.setdefault(h(sig), []).append(k)
    problems = ([f"made under {len(groups)} different settings: {sorted(groups.values())}"]
                if len(groups) > 1 else []) + ([f"no meta file (settings unknown): {legacy_}"] if legacy_ else [])
    if problems:                       # recorded in the report, never a stop
        print(f"{what}: warning: " + "; ".join(problems))
    return problems
