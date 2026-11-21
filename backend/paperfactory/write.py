"""Write each paper with PaperOrchestra (external/paperorchestra, own uv project), at most 3 papers at once.

Model and page count come from the settings. Afterwards code counts phrases of 6+ words that occur 3+ times
(after replacing entity names), a cheap sign that the writer fell back to one fixed phrasing.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Any

from repo_paths import REPO

from paperfactory.llm import slot_dir

PO = REPO / "external" / "paperorchestra"


PROMPT_VERSION = "v1n"
WRITER_CALLS = 12          # the writer's time limit is this many call timeouts (about 10 calls per paper)     # PaperOrchestra's v1 + the rule that the materials are not a source (C10)


def write_one(s, pid: str, template: Path, attempt: int = 1, use_cache: bool = True) -> dict[str, Any]:
    """attempt 1 -> work/<pid>; attempt n > 1 (a whole-paper redo, repair.py) -> work/<pid>/redo-<n> with a fresh
    PaperOrchestra cache, so the redo is a new paper and not the cached one."""
    out = s.out_dir / "work" / pid if attempt == 1 else s.out_dir / "work" / pid / f"redo-{attempt}"
    tag = "" if attempt == 1 else f".redo-{attempt}"
    if (out / "paper.md").is_file():
        return {"pid": pid, "status": "exists"}
    rm = s.role("writer")
    # PaperOrchestra runs in the main environment so that its calls go through paperfactory's model layer (C9)
    cmd = ["uv", "run", "--quiet", "--project", str(REPO), "python", str(PO / "paper_writing_cli.py"),
           "--raw_materials_dir", str(s.out_dir / "papers" / pid), "--output_dir", str(out),
           "--template_dir", str(template), "--writer_model_name", rm.model,
           "--backend_json", json.dumps(asdict(rm)), "--prompt_version", PROMPT_VERSION,
           "--cache_dir", str(po_cache(s, attempt, use_cache)),
           "--lock_dir", str(slot_dir(s.slots, rm)),
           "--max_parallel", str(rm.max_parallel),
           "--log_path", str(s.out_dir / "work" / f"{pid}{tag}.log.jsonl"), "--max_reflections", "1",
           "--timeout", str(rm.timeout)]
    out.parent.mkdir(parents=True, exist_ok=True)
    with (s.out_dir / "work" / f"{pid}{tag}.out").open("w") as log:
        try:            # a hung writer must not block the field forever
            code = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=REPO,
                                  timeout=WRITER_CALLS * rm.timeout).returncode
        except subprocess.TimeoutExpired:
            return {"pid": pid, "status": f"failed (timeout after {WRITER_CALLS * rm.timeout} s)"}
    ok = code == 0 and (out / "paper.md").is_file()
    return {"pid": pid, "status": "ok" if ok else f"failed (exit {code}, see work/{pid}{tag}.out)"}


def po_cache(s, attempt: int, use_cache: bool) -> Path:
    """PaperOrchestra's cache folder. use_cache=False (--no-cache): a new empty folder, so nothing old is read."""
    base = s.out_dir / "cache" / ("po" if attempt == 1 else f"po-attempt-{attempt}")
    if use_cache:
        return base
    n = 1
    while (fresh := base.with_name(f"{base.name}-nocache-{n}")).exists():
        n += 1
    return fresh


def pmap_papers(fn, pids: list[str], workers: int = 3) -> list[Any]:
    """`workers` papers at once (settings "parallel"); each holds its own model slots."""
    with ThreadPoolExecutor(max(1, workers)) as ex:
        return list(ex.map(fn, pids))


def repeated_phrases(text: str, names: list[str], n: int = 6, min_count: int = 3) -> list[tuple[str, int]]:
    for name in sorted(names, key=len, reverse=True):
        text = re.sub(re.escape(name), " E ", text, flags=re.I)
    toks = re.findall(r"[a-z]+", text.lower())
    grams = Counter(" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1))
    return sorted(((g_, c) for g_, c in grams.items() if c >= min_count and g_.split().count("e") <= n // 2),
                  key=lambda x: -x[1])
