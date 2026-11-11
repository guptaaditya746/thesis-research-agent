"""Sealed runs (spec 6.7): `manifest.json` holds the sha256 of every file in a run folder, written last.

A run that finishes is sealed with status `complete` after run.json. A run that crashes first gets every file a
reader expects, in its empty form (`fill_expected`), then a manifest with status `failed` and the error; it has no
run.json, so it still reads as a crashed run (RunDir.complete, RunDirExists). `check` recomputes the hashes:
`evidence verify` names each file that was edited, removed or added since the seal.

`prov.ttl` (`evidence prov`) is derived from the sealed files and may be written after the seal: `check` does
not count it as extra when the manifest does not list it, and checks its hash when it does. `evidence reexec`
writes reexec.json before the seal (execute_run's `before_seal`).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jsonio import file_sha256, write_json

from .comparisons import Comparisons
from .rundir import SEAL_FILE
from .rundir import (ANSWER_FILE, CALLS_DIR, COMPARISONS_FILE, EVIDENCE_FILE, FUNNEL_FILE, GRAPH_FILE, LOCATE_FILE,
                     LOCK_FILE, NAMES_FILE, PROV_FILE, REASON_FILE, read_json)

if TYPE_CHECKING:
    from .engine import Settings

MANIFEST_FILE = SEAL_FILE   # rundir.SEAL_FILE
PRE_EV4 = "no manifest (pre-EV4)"
REPO = Path(__file__).resolve().parents[1]
DERIVED = (PROV_FILE,)   # written from the sealed files by our own commands, possibly after the seal
__all__ = ["DERIVED", "MANIFEST_FILE", "PRE_EV4", "check", "code_commit", "fill_expected", "seal"]


def code_commit() -> str | None:
    """$EVIDENCE_CODE_COMMIT, else `git rev-parse HEAD` in the repo root, else None (no git, not a checkout)."""
    if os.environ.get("EVIDENCE_CODE_COMMIT"):
        return os.environ["EVIDENCE_CODE_COMMIT"]
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return (out.stdout.strip() or None) if out.returncode == 0 else None


def fill_expected(root: Path, settings: Settings) -> None:
    """Write, in its empty form, each file a reader expects that a crashed run did not write; never overwrites."""
    empty: dict[str, Any] = {LOCATE_FILE: [], FUNNEL_FILE: {"strategy": settings.strategy, "documents": {}},
                             ANSWER_FILE: {}, GRAPH_FILE: {"nodes": [], "edges": []},
                             COMPARISONS_FILE: Comparisons().json()}   # an empty comparisons.Comparisons
    if settings.reason == "on":   # an empty reasoner.Inferences (reasoner.to_json)
        empty[REASON_FILE] = {"ontology_sha256": None, "broader": {}, "link_flags": []}
    if settings.names == "on":
        empty[NAMES_FILE] = {"groups": {}, "matches": [], "unresolved": []}
    for name, obj in empty.items():
        if not (root / name).exists():
            write_json(root / name, obj)
    if not (root / EVIDENCE_FILE).exists():
        (root / EVIDENCE_FILE).write_bytes(b"")
    (root / CALLS_DIR).mkdir(exist_ok=True)


def _hashes(root: Path) -> dict[str, str]:
    """posix relpath -> sha256 of every file under `root` but the manifest, sorted."""
    files = (p for p in root.rglob("*") if p.is_file())
    return dict(sorted((p.relative_to(root).as_posix(), file_sha256(p)) for p in files
                       if p.relative_to(root).as_posix() != MANIFEST_FILE))


def seal(root: Path, corpus_manifest_sha256: str, *, status: str, error: str | None = None) -> dict[str, Any]:
    """Write manifest.json for run folder `root` (call it after the last write: run.json, the final lock)."""
    lock = root / LOCK_FILE
    manifest = {"files": _hashes(root), "corpus_manifest_sha256": corpus_manifest_sha256,
                "protocol_lock_sha256": file_sha256(lock) if lock.is_file() else None,
                "code_commit": code_commit(), "status": status, "error": error}
    write_json(root / MANIFEST_FILE, manifest)
    return manifest


def check(root: Path) -> dict[str, Any] | str:
    """The files whose sha256 differs from the manifest, those it lists that are gone and those it does not list
    (a `DERIVED` file never counts as extra: it is rebuilt from the others); `intact` when there are none.
    `PRE_EV4` when the run has no manifest (a run made before sealing: judged on its chain only). The key is
    `intact`, not `ok`, so that `evidence verify`'s top-level "ok" is the only "ok" it prints."""
    if not (root / MANIFEST_FILE).is_file():
        return PRE_EV4
    try:
        manifest = read_json(root / MANIFEST_FILE)
        sealed = {str(k): str(v) for k, v in manifest["files"].items()}
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        return {"intact": False, "mismatched": [], "missing": [], "extra": [], "status": None,
                "error": f"unreadable {MANIFEST_FILE}: {type(exc).__name__}"}
    now = _hashes(root)
    mismatched = sorted(f for f in sealed if f in now and now[f] != sealed[f])
    missing = sorted(f for f in sealed if f not in now)
    extra = sorted(f for f in now if f not in sealed and f not in DERIVED)
    return {"intact": not (mismatched or missing or extra), "mismatched": mismatched, "missing": missing,
            "extra": extra, "status": manifest.get("status")}
