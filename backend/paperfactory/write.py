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
from paperfactory.packs import Field, Genre, render_template

PO = REPO / "external" / "paperorchestra"


PROMPT_VERSION = "v1n"     # PaperOrchestra's v1 + the rule that the materials are not a source (C10)


def write_one(s, pid: str, template: Path, attempt: int = 1) -> dict[str, Any]:
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
           "--cache_dir", str(s.out_dir / "cache" / ("po" if attempt == 1 else f"po-attempt-{attempt}")),
           "--lock_dir", str(slot_dir(s.slots, rm)),
           "--max_parallel", str(rm.max_parallel),
           "--log_path", str(s.out_dir / "work" / f"{pid}{tag}.log.jsonl"), "--max_reflections", "1",
           "--timeout", str(rm.timeout)]
    out.parent.mkdir(parents=True, exist_ok=True)
    with (s.out_dir / "work" / f"{pid}{tag}.out").open("w") as log:
        code = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=REPO).returncode
    ok = code == 0 and (out / "paper.md").is_file()
    return {"pid": pid, "status": "ok" if ok else f"failed (exit {code}, see work/{pid}{tag}.out)"}


def write_all(s, w: dict[str, Any], f: Field, g: Genre) -> list[dict[str, Any]]:
    template = render_template(f, g, s.pages, s.out_dir / f"template_{g.name}_{s.pages}p")
    with ThreadPoolExecutor(3) as ex:
        return list(ex.map(lambda pid: write_one(s, pid, template), w["papers"]))


def pmap_papers(fn, pids: list[str]) -> list[Any]:
    """At most 3 papers at once (each holds its own model slots)."""
    with ThreadPoolExecutor(3) as ex:
        return list(ex.map(fn, pids))


def repeated_phrases(text: str, names: list[str], n: int = 6, min_count: int = 3) -> list[tuple[str, int]]:
    for name in sorted(names, key=len, reverse=True):
        text = re.sub(re.escape(name), " E ", text, flags=re.I)
    toks = re.findall(r"[a-z]+", text.lower())
    grams = Counter(" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1))
    return sorted(((g_, c) for g_, c in grams.items() if c >= min_count and g_.split().count("e") <= n // 2),
                  key=lambda x: -x[1])
