"""Folder locations of evqa. The pipeline steps (spec, find, extract, answer) may never open SEED (seed wall test)."""
from __future__ import annotations

import os
from pathlib import Path

from repo_paths import DATA, REPO

BACKEND_EVQA = Path(__file__).resolve().parent
SEED = DATA / "seed"                 # the truth: schema, vocab subsets, one folder per domain
SCHEMA = SEED / "schema"
VOCAB = SEED / "vocab"               # frozen vocab subsets (checked in)
DATASET = DATA / "dataset"           # what the QA system may read: paper.md files (S3)
CACHE = Path(os.environ.get("EVQA_CACHE", DATA / "cache"))   # big downloads, never committed
LLM_LOG = Path(os.environ.get("EVQA_LLM_LOG", REPO / "runs" / "llm-calls.jsonl"))


def domain_dir(domain: str) -> Path:
    if not domain.isidentifier():
        raise ValueError(f"bad domain name {domain!r}")
    return SEED / domain


def brief_dir(domain: str, paper: str) -> Path:
    """The writing brief of one paper (seed values + row ids) and its writer log: truth, so under data/seed."""
    return domain_dir(domain) / "papers" / paper


def paper_file(domain: str, paper: str) -> Path:
    """The written paper: the only file of a paper the QA system may read."""
    return DATASET / domain / paper / "paper.md"
