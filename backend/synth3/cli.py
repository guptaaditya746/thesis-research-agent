"""`synth3` command line: draw the hidden worlds of a domain, then build folders from the approved ones."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from synth3.corpus import build_folder
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
    worlds = {}
    for seed in seeds:
        path = args.worlds / args.domain / f"s{seed}.json"
        if not path.is_file():
            raise BadArgument(f"{path}: no world file; run `synth3 draw` first")
        try:
            world = load_world(path, spec)
        except ValueError as err:
            raise BadArgument(str(err)) from err
        if not world.approved:
            raise BadArgument(f"{path}: not approved; set approved to true in the file")
        worlds[seed] = world
    for seed, world in worlds.items():
        folder = args.out / f"s{seed}"
        try:
            cid = build_folder(folder, spec, world, args.studies, args.text_level)
        except ValueError as err:
            raise BadArgument(f"s{seed}: {err}") from err
        attempt = json.loads((folder / "corpus.json").read_text(encoding="utf-8"))["settings"]["attempt"]
        print(f"s{seed}: {cid} (attempt {attempt}) -> {folder}")
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
