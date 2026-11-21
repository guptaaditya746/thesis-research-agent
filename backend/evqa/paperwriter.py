"""S3 paper writer: runs the vendored PaperOrchestra (external/paperorchestra, its own uv env) on one brief.

Input:  <paper_dir>/idea_sparse.md and <paper_dir>/experimental_log.md (data/seed/<domain>/papers/<paper>/).
Output: paper.md (data/dataset/<domain>/<paper>/, the only file the QA system reads) and <paper_dir>/writer_log.jsonl (every LLM call with cost, the value checks, the
        repairs, and a final summary). Intermediate files (outline, drafts, reviews, facts_check.json) go to
        runs/paperwriter/<domain>/<paper-id>/, outside the dataset folder the QA system reads.

The writer is a separate process (`uv run --project external/paperorchestra ...`). Its LLM is Claude Code headless
(cheapest model by default); every call is cached under CACHE/paperorchestra and holds one of 3 shared slot locks
(CACHE/claude-slots), so at most 3 calls run at once even when several papers are written in parallel.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from evqa.llm import CHEAPEST_CLAUDE, MAX_WORKERS, pmap
from evqa.paths import CACHE, domain_dir, paper_file
from repo_paths import REPO

PO_DIR = REPO / "external" / "paperorchestra"
WORK = REPO / "runs" / "paperwriter"
INPUTS = ("idea_sparse.md", "experimental_log.md")


class PaperWriterError(RuntimeError):
    pass


def work_dir(paper_dir: Path) -> Path:
    return WORK / paper_dir.name


def write_paper(paper_dir: Path, *, paper_out: Path | None = None, model: str = CHEAPEST_CLAUDE,
                claude_bin: str | None = None, max_reflections: int = 1, timeout: int = 900,
                prompt_version: str = "v1", domain: str | None = None,
                style_examples: list[dict[str, Any]] | None = None,
                references: list[dict[str, Any]] | None = None, research_lm: Any = None,
                research_search: Any = None) -> Path:
    """Write paper.md (to `paper_out`, default paper_dir/paper.md) from the brief in paper_dir. Returns its path.

    prompt_version "v1" (default) = the prompts of the frozen benchmark papers; "v2" = style examples from real
    trial reports + plain-writing rules (docs/design/qwen-writer.md). v2 needs `style_examples`, or `domain` so
    code builds them (evqa.research.style.build: stored CC-licensed excerpts + retrieved S2 abstracts).
    "v2r" = v2 + the research tool: before writing, Qwen searches Semantic Scholar in a bounded loop
    (evqa.research.agent; log in <work dir>/research.jsonl) and picks style abstracts and up to 4 references that
    the Introduction / Related Work may cite. Pass `style_examples` and `references` to skip the loop.

    writer_log.jsonl is started fresh for each run (cached calls appear with cached=true and cost 0)."""
    paper_dir = Path(paper_dir).resolve()
    missing = [n for n in INPUTS if not (paper_dir / n).is_file()]
    if missing:
        raise FileNotFoundError(f"{paper_dir}: missing {missing}")
    out, log = work_dir(paper_dir), paper_dir / "writer_log.jsonl"
    out.mkdir(parents=True, exist_ok=True)
    log.unlink(missing_ok=True)
    cmd = ["uv", "run", "--quiet", "--project", str(PO_DIR), "python", str(PO_DIR / "paper_writing_cli.py"),
           "--raw_materials_dir", str(paper_dir), "--output_dir", str(out),
           "--writer_model_name", model, "--cache_dir", str(CACHE / "paperorchestra"),
           "--lock_dir", str(CACHE / "claude-slots"), "--log_path", str(log),
           "--max_reflections", str(max_reflections), "--timeout", str(timeout),
           "--prompt_version", prompt_version]
    res = None
    if prompt_version == "v2r" and (style_examples is None or references is None):
        from evqa.research import style
        (out / "research.jsonl").unlink(missing_ok=True)
        style_examples, references, res = style.build_with_research(
            paper_dir, domain or _domain_of(paper_dir), log_path=out / "research.jsonl", lm=research_lm,
            search=research_search)
    if prompt_version == "v2r":
        (out / "references.json").write_text(json.dumps(references, indent=1, ensure_ascii=False), encoding="utf-8")
        cmd += ["--references", str(out / "references.json")]
    if prompt_version != "v1":
        if style_examples is None:
            from evqa.research import style
            style_examples = style.build(paper_dir, domain or _domain_of(paper_dir))
        (out / "style_examples.json").write_text(json.dumps(style_examples, indent=1, ensure_ascii=False),
                                                 encoding="utf-8")
        cmd += ["--style_examples", str(out / "style_examples.json")]
    env = dict(os.environ)
    if claude_bin:
        env["PO_CLAUDE_BIN"] = claude_bin
    start = time.time()
    done = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=PO_DIR)
    (out / "writer_stdout.txt").write_text(done.stdout + "\n--- stderr ---\n" + done.stderr, encoding="utf-8")
    if done.returncode != 0 or not (out / "paper.md").is_file():
        raise PaperWriterError(f"writer failed for {paper_dir.name} (exit {done.returncode}): {done.stderr[-1500:]}")
    target = paper_out or paper_dir / "paper.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(out / "paper.md", target)
    stats = log_stats(log)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"event": "run", "paper": paper_dir.name, "model": model,
                            "prompt_version": prompt_version, "work_dir": str(out),
                            **({"research": {"queries": res["queries"],
                                             "style": [r["paperId"] for r in res["style"]],
                                             "references": [r["paperId"] for r in res["references"]],
                                             "rejected": res["rejected"], "log": str(out / "research.jsonl")}}
                               if res else {}),
                            "wall_seconds": round(time.time() - start, 1), **stats}) + "\n")
    return target


def _domain_of(paper_dir: Path) -> str:
    """data/seed/<domain>/papers/<paper> -> <domain>; anything else -> 'medical'."""
    return paper_dir.parent.parent.name if paper_dir.parent.name == "papers" else "medical"


def log_stats(log: Path) -> dict[str, Any]:
    """Calls, cost and the final check summary out of a writer_log.jsonl."""
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    calls = [r for r in rows if r.get("event") == "call"]
    final = next((r for r in reversed(rows) if r.get("event") == "check" and r.get("stage") == "final"), {})
    return {"calls": len(calls), "cached_calls": sum(bool(r.get("cached")) for r in calls),
            "cost_usd": round(sum(r.get("cost_usd") or 0 for r in calls), 4),
            "repairs": sum(r.get("event") == "repair" for r in rows),
            "facts": final.get("facts"), "facts_ok": final.get("ok"), "facts_failed": final.get("failed")}


def write_domain(domain: str, paper: str | None = None, **kw: Any) -> list[dict[str, Any]]:
    """Write every paper of `domain` that has a brief (or only `paper`), at most 3 at once. Briefs and logs stay
    under data/seed/<domain>/papers/; only paper.md goes to data/dataset/<domain>/<paper>/.
    Returns one status row per paper; a failure is reported in its row, not raised."""
    root = domain_dir(domain) / "papers"
    dirs = sorted(d for d in root.iterdir() if d.is_dir() and all((d / n).is_file() for n in INPUTS)) \
        if root.is_dir() else []
    if paper is not None:
        dirs = [d for d in dirs if d.name == paper]
        if not dirs:
            raise FileNotFoundError(f"no brief for {paper} under {root}")

    def one(d: Path) -> dict[str, Any]:
        try:
            write_paper(d, paper_out=paper_file(domain, d.name), domain=domain, **kw)
            return {"paper": d.name, "status": "ok", **log_stats(d / "writer_log.jsonl")}
        except Exception as e:  # keep the other papers going
            return {"paper": d.name, "status": "failed", "error": str(e)[-800:]}

    return pmap(one, dirs, workers=MAX_WORKERS)
