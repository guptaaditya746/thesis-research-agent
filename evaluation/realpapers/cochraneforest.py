"""CochraneForest whole-run questions (spec 6.12 real sets; medicine). Each forest plot of a Cochrane review is one
research question; its studies' full texts are the papers; the gold is each study's direction in the plot and the
review's conclusion.

Layout assumed (UNVERIFIED until the release is opened; `_read` is the one reader to change):
  release.json  {"licence": str, "released": bool,
                 "plots": [{"id", "question", "conclusion": improves|worsens|no_effect,
                            "studies": [{"id", "direction": improves|worsens|no_effect, "text": str | null}]}]}
A study with no open full text (`text` null or empty) is left out of the corpus and counted; the report states
"left out: N of M (no open full text)".

`check_release` is step 1 of the converter: a release that is not out, or whose licence is not one of
ALLOWED_LICENCES, stops `to_corpus` with a clear message (nothing is written).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonio import sha256_hex

from ..wholerun import RealQuestion, left_out_line

RELEASE_FILE = "release.json"
SOURCE_FILE = "cochraneforest_corpus.json"
ALLOWED_LICENCES = ("cc-by", "cc-by-4.0", "cc-by-sa", "cc-by-sa-4.0", "cc0", "cc0-1.0")


class NotReleased(RuntimeError):
    """The dataset is not out yet, or its licence does not allow this use."""


def _read(src: Path) -> dict[str, Any]:
    return json.loads((Path(src) / RELEASE_FILE).read_text(encoding="utf-8"))


def check_release(src: Path) -> dict[str, Any]:
    """{"licence": str, "released": bool} of the release in `src`."""
    data = _read(src)
    return {"licence": str(data.get("licence", "")), "released": bool(data.get("released"))}


def _require(src: Path) -> dict[str, Any]:
    info = check_release(src)
    if not info["released"]:
        raise NotReleased("CochraneForest is not released yet (release.json says released: false); "
                          "nothing was written")
    if info["licence"].lower() not in ALLOWED_LICENCES:
        raise NotReleased(f"CochraneForest licence {info['licence']!r} is not one of {ALLOWED_LICENCES}; "
                          "nothing was written")
    return _read(src)


def _studies(plot: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(studies with open full text, studies without) of a plot."""
    have = [s for s in plot["studies"] if str(s.get("text") or "").strip()]
    return have, [s for s in plot["studies"] if s not in have]


def to_corpus(src: Path, out: Path) -> Path:
    """One corpus per forest plot under `out/<plot id>/` (manifest.json, papers/<study id>.md) and `out/`
    SOURCE_FILE (counts, `left_out_line`). Refuses an unreleased or disallowed release. Returns `out`."""
    data = _require(src)
    out = Path(out)
    left = total = 0
    for plot in data["plots"]:
        have, missing = _studies(plot)
        left, total = left + len(missing), total + len(plot["studies"])
        folder = out / str(plot["id"])
        (folder / "papers").mkdir(parents=True, exist_ok=True)
        papers = []
        for s in have:
            blob = str(s["text"]).encode("utf-8")
            (folder / "papers" / f"{s['id']}.md").write_bytes(blob)
            papers.append({"id": str(s["id"]), "file": f"papers/{s['id']}.md", "sha256": sha256_hex(blob)})
        (folder / "manifest.json").write_text(
            json.dumps({"corpus_id": f"cochraneforest-{plot['id']}", "papers": papers}, indent=1) + "\n",
            encoding="utf-8", newline="\n")
    (out / SOURCE_FILE).write_text(json.dumps(
        {"licence": data.get("licence"), "plots": len(data["plots"]), "studies": total, "left_out": left,
         "left_out_line": left_out_line(left, total)}, indent=1) + "\n", encoding="utf-8", newline="\n")
    return out


def questions(src: Path, corpus_dir: Path | None = None) -> list[RealQuestion]:
    """Per forest plot two questions over the same papers: kind `compare` (gold: each open-text study's direction
    and the review's conclusion) and kind `claims` (gold: the review's conclusion, to score the run's claim
    records against). Field `medicine`; the corpus of a plot is `<corpus_dir>/<plot id>` (default `src/corpus`)."""
    data = _require(src)
    root = Path(corpus_dir) if corpus_dir is not None else Path(src) / "corpus"
    out = []
    for plot in data["plots"]:
        have, _ = _studies(plot)
        papers = [str(s["id"]) for s in have]
        folder = root / str(plot["id"])
        out.append(RealQuestion(
            id=f"cochrane-{plot['id']}-compare", question=str(plot["question"]), field="medicine",
            corpus_dir=folder, kind="compare",
            gold={"directions": {str(s["id"]): s["direction"] for s in have}, "conclusion": plot["conclusion"],
                  "papers": papers}))
        out.append(RealQuestion(
            id=f"cochrane-{plot['id']}-claims", question=str(plot["question"]), field="medicine",
            corpus_dir=folder, kind="claims",
            gold={"conclusions": [{"id": str(plot["id"]), "direction": plot["conclusion"]}], "papers": papers}))
    return out
