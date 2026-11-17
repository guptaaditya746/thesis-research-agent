"""`synth3` command line: draw the hidden worlds of a domain, then build folders from the approved ones."""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import httpx

from evidence.arxiv import FetchError
from synth3.corpus import build_folder
from synth3.pmc import Polite, fetch_pool
from synth3.pool import import_files, load_index
from synth3.realspec import POOLS, REAL_SPECS, load_real_spec
from synth3.spec import SPECS, load_spec
from synth3.world import describe, draw_world, load_world, save_world
from synth3.write import TEXT_LEVELS

WORLDS = Path(__file__).resolve().parents[2] / "data" / "synth3" / "worlds"


class BadArgument(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):
        raise BadArgument(message)


def _seeds(text: str) -> list[int]:
    try:
        seeds = [int(x) for x in text.split(",") if x.strip()]
    except ValueError as err:
        raise BadArgument(f"--seeds must be whole numbers separated by commas, got '{text}'") from err
    if not seeds:
        raise BadArgument("--seeds needs at least one seed")
    return list(dict.fromkeys(seeds))


def _spec(args: argparse.Namespace):
    try:
        return load_spec(args.domain, args.spec_root)
    except (OSError, ValueError) as err:
        raise BadArgument(str(err)) from err


def draw(args: argparse.Namespace) -> int:
    spec, seeds = _spec(args), _seeds(args.seeds)
    paths = {s: args.worlds / args.domain / f"s{s}.json" for s in seeds}
    existing = [str(p) for p in paths.values() if p.exists()]
    if existing:
        raise BadArgument(f"refusing to overwrite: {', '.join(existing)}")
    for seed, path in paths.items():
        world = draw_world(spec, seed)
        save_world(path, world)
        print(f"s{seed} -> {path}\n{describe(world, spec)}")
    return 0


def build(args: argparse.Namespace) -> int:
    spec, seeds = _spec(args), _seeds(args.seeds)
    if args.text_level not in TEXT_LEVELS:
        raise BadArgument(f"unknown text level '{args.text_level}'; choose from {', '.join(TEXT_LEVELS)}")
    worlds, problems = {}, []
    for seed in seeds:
        path = args.worlds / args.domain / f"s{seed}.json"
        folder = args.out / f"s{seed}"
        if folder.exists() and any(folder.iterdir()):
            problems.append(f"{folder}: not empty")
        if not path.is_file():
            problems.append(f"{path}: no world file; run `synth3 draw` first")
            continue
        try:
            world = load_world(path, spec)
        except ValueError as err:
            problems.append(str(err))
            continue
        if not world.approved:
            problems.append(f"{path}: not approved; set approved to true in the file")
        worlds[seed] = world
    if problems:
        raise BadArgument("; ".join(problems))
    for seed, world in worlds.items():
        folder = args.out / f"s{seed}"
        try:
            cid = build_folder(folder, spec, world, args.studies, args.text_level)
        except ValueError as err:
            raise BadArgument(f"s{seed}: {err}") from err
        attempt = json.loads((folder / "corpus.json").read_text(encoding="utf-8"))["settings"]["attempt"]
        print(f"s{seed}: {cid} (attempt {attempt}) -> {folder}")
    return 0


def _real_spec(args: argparse.Namespace):
    try:
        return load_real_spec(args.domain, args.real_root)
    except (OSError, ValueError) as err:
        raise BadArgument(str(err)) from err


def _report(out: dict, pool: Path) -> None:
    rows = load_index(pool)
    print(f"kept {out['kept']} of {len(rows)}")
    for why, n in sorted(out["unfit"].items(), key=lambda kv: -kv[1]):
        print(f"  unfit: {why}: {n}")
    for lic, n in Counter(r["license"] or "none" for r in rows if r["kept"]).most_common():
        print(f"  licence: {lic}: {n}")


def pool_fetch(args: argparse.Namespace) -> int:
    rs = _real_spec(args)
    if rs.source != "pmc":
        raise BadArgument(f"{args.domain}: the config source is '{rs.source}', not 'pmc'; use pool-import")
    pool = args.pools / args.domain
    try:
        out = fetch_pool(rs, pool, Polite())
    except (httpx.HTTPError, ET.ParseError) as err:
        raise BadArgument(f"fetch failed ({err}); run again to resume") from err
    print(f"found {out['found']}, fetched {out['fetched']}, already saved {out['cached']} -> {pool}")
    _report(out, pool)
    return 0


def pool_import(args: argparse.Namespace) -> int:
    rs = _real_spec(args)
    if not args.src.is_dir():
        raise BadArgument(f"{args.src}: not a folder")
    pool = args.pools / args.domain
    try:
        out = import_files(args.src, pool, rs)
    except FetchError as err:
        raise BadArgument(f"{err}; for PDFs run `uv sync --group fetch`") from err
    _report(out, pool)
    return 0


def parser() -> argparse.ArgumentParser:
    top = _Parser(prog="synth3", description=__doc__)
    sub = top.add_subparsers(dest="command", required=True, parser_class=_Parser)
    d = sub.add_parser("draw", help="draw one world file per seed for a domain")
    b = sub.add_parser("build", help="build one folder per seed from approved world files")
    for p in (d, b):
        p.add_argument("--domain", required=True)
        p.add_argument("--seeds", required=True, help="comma-separated, e.g. 1,2,3,4,5")
        p.add_argument("--spec-root", type=Path, default=SPECS)
        p.add_argument("--worlds", type=Path, default=WORLDS)
    d.set_defaults(run=draw)
    b.add_argument("--studies", type=int, default=40)
    b.add_argument("--text-level", default="table", help=" | ".join(TEXT_LEVELS))
    b.add_argument("--out", type=Path, required=True)
    b.set_defaults(run=build)
    pf = sub.add_parser("pool-fetch", help="fetch real papers from PubMed Central into a domain's pool")
    pi = sub.add_parser("pool-import", help="add .md, .xml and .pdf files to a domain's pool")
    for p in (pf, pi):
        p.add_argument("--domain", required=True)
        p.add_argument("--real-root", type=Path, default=REAL_SPECS)
        p.add_argument("--pools", type=Path, default=POOLS)
    pi.add_argument("--from", dest="src", type=Path, required=True, help="folder of papers")
    pf.set_defaults(run=pool_fetch)
    pi.set_defaults(run=pool_import)
    return top


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        return args.run(args)
    except BadArgument as err:
        print(f"synth3: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
