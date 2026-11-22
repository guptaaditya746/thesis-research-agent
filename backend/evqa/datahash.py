"""Data fingerprint of a run: sha256 over the files a run reads and the files its score is made against.

    data_hashes("medical", "test") -> {"data_hash": ..., "papers": ..., "questions": ..., "gold": ...}

Groups (each a sha256 over relative path + bytes of its files, in sorted path order):
  papers     data/dataset/<domain>/*/paper.md                       (corpus.papers)
  questions  data/dataset/<domain>/questions/<split>.jsonl          (corpus.questions)
  gold       data/seed/<domain>/: seed.ttl, blueprint.yaml, names.json, gold/*.json, l0/*.json (what evqa/scoring.py puts in the gold file)
data_hash is one sha256 over all those files together, in sorted path order. A missing file is left out.
run.py stores them in manifest.json (and refuses a resume when papers or questions changed); evqa/scoring.py puts
them into the gold file and so into eval.json under "data", so a score names the data it was made on.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from evqa import paths

GROUPS = ("papers", "questions", "gold")
GOLD_FILES = ("seed.ttl", "blueprint.yaml", "names.json")
GOLD_GLOBS = ("gold/*.json", "l0/*.json")


def group_files(domain: str, split: str) -> dict[str, list[Path]]:
    """The files of each group (module doc), existing ones only, sorted by path."""
    data, seed = paths.DATASET / domain, paths.SEED / domain
    gold = [seed / n for n in GOLD_FILES] + [p for g in GOLD_GLOBS for p in seed.glob(g)]
    questions = data / "questions" / f"{split}.jsonl"
    return {"papers": sorted(data.glob("*/paper.md")),
            "questions": [questions] if questions.is_file() else [],
            "gold": sorted(p for p in gold if p.is_file())}


def _hash(files: list[Path], root: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(files):
        h.update(f"{f.relative_to(root).as_posix() if f.is_relative_to(root) else f.as_posix()}\n".encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def data_hashes(domain: str, split: str) -> dict[str, str]:
    """{"data_hash": over every file, "papers"/"questions"/"gold": per group} (module doc)."""
    root = paths.DATA
    files = group_files(domain, split)
    out = {"data_hash": _hash([f for g in GROUPS for f in files[g]], root)}
    out.update({g: _hash(files[g], root) for g in GROUPS})
    return out
