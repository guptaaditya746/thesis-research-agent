"""Rebuild a domain's seed and question set by code only (no LLM), into a scratch folder or in place.

  uv run python -m evqa.seed.rebuild medical --out /tmp/q4 --replay --compare
      seed.ttl from blueprint + names.json, then the question set (bench, or the hand-written set) from that new
      seed, wordings replayed from the frozen gold; every file written under /tmp/q4/<repo-relative path> and its
      sha256 compared with the frozen file. Exit 1 when any file differs.
  uv run python -m evqa.seed.rebuild materials --out /tmp/q4
      a domain without a frozen set: questions keep their template text (no rewording).
  uv run python -m evqa.seed.rebuild materials --in-place --seed-only
      write seed.ttl into data/seed/<domain>/ (refused for a domain whose question set is frozen).

seed.ttl note: rdflib orders the blank-node `ex:mention` entries of a paper by their random ids, so a paper with
several mentions (P-med-11) is serialised in one of a few orders. `--compare` therefore also checks graph
isomorphism and, with `--tries N`, rebuilds up to N times until the bytes match (the values never change).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from rdflib import Graph
from rdflib.compare import isomorphic

from evqa.paths import REPO, SCHEMA, VOCAB, domain_dir
from evqa.seed import bench
from evqa.seed import build as seed_build
from evqa.seed import questions as qs


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def names_of(domain: str) -> dict[str, Any]:
    path = domain_dir(domain) / "names.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"slots": {}}


def seed_text(domain: str, tries: int = 1) -> tuple[str, Graph, int]:
    """(seed.ttl text, graph, tries used). With tries > 1 and a seed.ttl on disk, rebuild until the bytes match."""
    frozen = domain_dir(domain) / "seed.ttl"
    want = frozen.read_text(encoding="utf-8") if frozen.is_file() else None
    bp = seed_build.load_blueprint(domain)
    for i in range(1, max(1, tries) + 1):
        graph = seed_build.build(bp, names_of(domain))
        text = seed_build.text(domain, graph)
        if want is None or text == want:
            break
    return text, graph, i


def full(graph: Graph) -> Graph:
    """The seed graph plus glue and vocab subsets (what check.full_graph reads from disk)."""
    g = Graph()
    for t in graph:
        g.add(t)
    g.parse(SCHEMA / "glue.ttl")
    for f in sorted(VOCAB.glob("*.ttl")):
        g.parse(f)
    return g


def frozen_bench(domain: str) -> bool:
    m = qs.gold_dir(domain) / "manifest.json"
    return m.is_file() and "generator" in json.loads(m.read_text(encoding="utf-8"))


def question_files(domain: str, graph: Graph, ttl: str, replay: bool) -> tuple[dict[Path, str], dict[str, Any]]:
    """The question set made from this seed graph: the bench when the blueprint has bench templates, else the
    hand-written set only."""
    g = full(graph)
    gen = qs.gen_of(domain)
    hand_only = not (gen.g.get("bench") or {}).get("templates")
    old = qs.gold_dir(domain) / "manifest.json"
    if hand_only or (old.is_file() and not frozen_bench(domain)):
        return qs.render(domain, g), {"kind": "hand-written questions"}
    w = bench.World(domain, g=g, seed_text=ttl)
    files, report = bench.render(domain, w=w, replay=qs.gold_dir(domain) if replay else None)
    return files, report


def compare(files: dict[Path, str]) -> list[dict[str, Any]]:
    out = []
    for path, text in sorted(files.items()):
        rel = path.relative_to(REPO).as_posix()
        old = path.read_text(encoding="utf-8") if path.is_file() else None
        out.append({"file": rel, "new_sha256": sha(text), "frozen_sha256": sha(old) if old is not None else None,
                    "identical": old is not None and sha(old) == sha(text)})
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m evqa.seed.rebuild", description=__doc__.split("\n")[0])
    p.add_argument("domain")
    where = p.add_mutually_exclusive_group(required=True)
    where.add_argument("--out", type=Path, help="write under OUT/<repo-relative path> (frozen folders untouched)")
    where.add_argument("--in-place", action="store_true", help="write into data/ (refused for a frozen set)")
    p.add_argument("--replay", action="store_true", help="reuse the frozen gold's wordings (no LLM)")
    p.add_argument("--compare", action="store_true", help="sha256 of every file against the frozen file")
    p.add_argument("--seed-only", action="store_true", help="build seed.ttl only, no questions")
    p.add_argument("--tries", type=int, default=1, help="rebuild seed.ttl up to N times until the bytes match")
    a = p.parse_args(argv)
    out: Path | None = a.out
    if a.in_place and (frozen_bench(a.domain) or (qs.gold_dir(a.domain) / "manifest.json").is_file()):
        print(f"refused: {a.domain} has a frozen question set; rebuild with --out and --compare")
        return 1
    ttl, graph, used = seed_text(a.domain, a.tries if a.compare else 1)
    seed_path = seed_build.relocate(domain_dir(a.domain) / "seed.ttl", out)
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text(ttl, encoding="utf-8")
    files: dict[Path, str] = {domain_dir(a.domain) / "seed.ttl": ttl}
    result: dict[str, Any] = {"domain": a.domain, "seed": str(seed_path), "triples": len(graph), "seed_tries": used}
    if not a.seed_only:
        qfiles, report = question_files(a.domain, graph, ttl, a.replay)
        qs.write_files(qfiles, out)
        files.update(qfiles)
        result["questions"] = sum(t.count("\n") for p_, t in qfiles.items() if p_.suffix == ".jsonl")
        result["gold_files"] = sum(1 for p_ in qfiles if p_.suffix == ".json" and p_.name != "manifest.json")
        result["report"] = {k: v for k, v in report.items() if not isinstance(v, dict)} | {
            t: {k: report[t][k] for k in ("total", "shortfall", "candidates")} for t in bench.TYPES if t in report}
    ok = True
    if a.compare:
        rows = compare(files)
        frozen_ttl = domain_dir(a.domain) / "seed.ttl"
        if frozen_ttl.is_file():
            old = Graph().parse(frozen_ttl)
            result["seed_isomorphic"] = isomorphic(old, Graph().parse(data=ttl, format="turtle"))
        result["identical"] = sum(r["identical"] for r in rows)
        result["different"] = [r["file"] for r in rows if not r["identical"]]
        result["files"] = rows
        ok = not result["different"]
    print(json.dumps(result, indent=2, default=str))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
