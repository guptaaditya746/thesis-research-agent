"""`evqa doctor`: preflight checks before a long run. One line per check (ok / warn / FAIL); exit 1 on any FAIL.

  gateway  Qwen LiteLLM gateway answers GET <LITELLM_BASE_URL>/models (only when a step uses qwen)
  claude   one tiny `claude -p` call, same flags as lm.claude_ask (only when a step uses claude, or --claude)
  slurm    time left on $SLURM_JOB_ID (squeue %L); warn under --min-hours
  disk     free space under runs/; warn under 2 GB
  git      uncommitted changes; warn

Every check takes its outside call as an argument, so tests pass fakes (no network, no Slurm).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path

from repo_paths import REPO

RUNS = REPO / "runs"
MIN_FREE_GB = 2.0
Check = tuple[str, str, str]   # (name, "ok" | "warn" | "FAIL", detail)


def _http_get(url: str, key: str, timeout: float) -> int:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 (local gateway)
        return r.status


def check_gateway(get: Callable[[str, str, float], int] = _http_get, timeout: float = 5.0) -> Check:
    url = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000/v1").rstrip("/") + "/models"
    key = os.environ.get("LITELLM_MASTER_KEY", "")
    if not key:
        return ("gateway", "FAIL", "LITELLM_MASTER_KEY is not set")
    try:
        status = get(url, key, timeout)
    except Exception as e:  # any error = not reachable
        return ("gateway", "FAIL", f"{url}: {type(e).__name__}: {e}")
    return ("gateway", "ok" if status == 200 else "FAIL", f"{url}: HTTP {status}")


def _claude_run(model: str, timeout: float) -> str:
    with tempfile.TemporaryDirectory(prefix="evqa-doctor-") as empty:
        done = subprocess.run(["claude", "-p", "--model", model, "--tools", "", "--setting-sources", "",
                               "--strict-mcp-config", "--no-session-persistence", "--output-format", "json"],
                              input="Reply with the word ok.", capture_output=True, text=True, cwd=empty,
                              timeout=timeout)
    return done.stdout


def check_claude(model: str = "claude-haiku-5-5", run: Callable[[str, float], str] = _claude_run,
                 timeout: float = 120) -> Check:
    try:
        out = json.loads(run(model, timeout))
    except Exception as e:
        return ("claude", "FAIL", f"{type(e).__name__}: {e}")
    if out.get("is_error"):
        return ("claude", "FAIL", f"claude error: {str(out.get('result'))[:200]}")
    return ("claude", "ok", f"{model} answered")


def _squeue(job: str) -> str:
    return subprocess.run(["squeue", "-h", "-j", job, "-o", "%L"], capture_output=True, text=True,
                          timeout=20).stdout


def slurm_hours(left: str) -> float:
    """squeue %L ([days-]hours:minutes:seconds, or minutes:seconds) -> hours."""
    days, _, rest = left.strip().rpartition("-")
    parts = [int(x) for x in rest.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts
    return (int(days or 0) * 24) + h + m / 60 + s / 3600


def check_slurm(min_hours: float, squeue: Callable[[str], str] = _squeue) -> Check | None:
    job = os.environ.get("SLURM_JOB_ID")
    if not job:
        return None
    try:
        left = squeue(job).strip()
        hours = slurm_hours(left)
    except Exception as e:
        return ("slurm", "FAIL", f"job {job}: cannot read time left ({type(e).__name__}: {e})")
    state = "ok" if hours >= min_hours else "warn"
    return ("slurm", state, f"job {job}: {left} left ({hours:.1f} h; want >= {min_hours} h)")


def check_disk(path: Path = RUNS, free: Callable[[Path], int] | None = None) -> Check:
    p = Path(path)
    while not p.exists():
        p = p.parent
    gb = (free(p) if free else shutil.disk_usage(p).free) / 1e9
    return ("disk", "ok" if gb >= MIN_FREE_GB else "warn", f"{gb:.1f} GB free under {path}")


def _git_status() -> str:
    return subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=REPO,
                          timeout=30).stdout


def check_git(status: Callable[[], str] = _git_status) -> Check:
    lines = [x for x in status().splitlines() if x.strip()]
    return ("git", "warn" if lines else "ok", f"{len(lines)} uncommitted change(s)" if lines else "clean tree")


def backends_of(config: Path | None) -> set[str]:
    """Backends a run config uses (its llm and every step override); no config = qwen (the default)."""
    if config is None:
        return {"qwen"}
    from evqa.contracts import RunConfig
    cfg = RunConfig.load(config)
    return {cfg.llm.backend, *(s.backend for s in cfg.steps.values())}


def run_checks(backends: set[str], *, claude: bool = False, min_hours: float = 2.0,
               checks: dict[str, Callable] | None = None) -> list[Check]:
    """Run the checks that apply. `checks` overrides any of gateway / claude / slurm / disk / git (tests)."""
    c = {"gateway": check_gateway, "claude": check_claude, "slurm": lambda: check_slurm(min_hours),
         "disk": check_disk, "git": check_git, **(checks or {})}
    out = []
    if "qwen" in backends:
        out.append(c["gateway"]())
    if "claude" in backends or claude:
        out.append(c["claude"]())
    out += [c["slurm"](), c["disk"](), c["git"]()]
    return [x for x in out if x is not None]


def main(a, checks: dict[str, Callable] | None = None) -> int:
    backends = {a.backend} if a.backend else backends_of(a.config)
    rows = run_checks(backends, claude=a.claude, min_hours=a.min_hours, checks=checks)
    for name, state, detail in rows:
        print(f"{state:4}  {name:8} {detail}")
    return 1 if any(state == "FAIL" for _, state, _ in rows) else 0
