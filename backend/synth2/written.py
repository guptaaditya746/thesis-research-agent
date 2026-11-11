"""Assemble a model-written corpus: the template's papers rewritten by a model, with the template's facts."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from jsonio import sha256_hex, write_json_atomic, write_text_atomic

EVAL_LEVEL = "written"


def assemble(template: Path, papers: Path, out: Path) -> int:
    """Write `out` from the template corpus and a folder of `<paper id>.md` files; return the papers written.
    The truth keeps the facts but has no placements (the written text has other offsets) and one level."""
    template, papers, out = Path(template), Path(papers), Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"{out} is not empty; choose a new folder")
    manifest = json.loads((template / "manifest.json").read_text(encoding="utf-8"))
    texts: dict[str, str] = {}
    for entry in manifest["papers"]:
        source = papers / f"{entry['id']}.md"
        if not source.is_file():
            raise ValueError(f"no written paper for {entry['id']}: expected {source}")
        texts[entry["id"]] = source.read_text(encoding="utf-8")
    truth = json.loads((template / "ground_truth.json").read_text(encoding="utf-8"))
    (out / "papers").mkdir(parents=True, exist_ok=True)
    for sid, text in texts.items():
        write_text_atomic(out / "papers" / f"{sid}.md", text)
    write_json_atomic(out / "manifest.json", {
        "corpus_id": manifest["corpus_id"],
        "papers": [{"id": e["id"], "file": e["file"], "sha256": sha256_hex(texts[e["id"]].encode("utf-8"))}
                   for e in manifest["papers"]]})
    shutil.copyfile(template / "corpus.json", out / "corpus.json")
    write_json_atomic(out / "ground_truth.json", {**truth, "placements": [], "eval_level": EVAL_LEVEL})
    return len(texts)
