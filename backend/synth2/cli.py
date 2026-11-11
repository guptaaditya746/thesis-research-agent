"""`synth2` command line: build a grid of corpus families, write a reference rule's answers, score answers,
export the corpora as a SciR-shaped task file."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from jsonio import write_json_atomic
from synth2.corpus import Settings, build_base, load_truth
from synth2.family import make_family
from synth2.recipe import load_recipe
from synth2.scir_export import export
from synth2.score import RULES, reference_answers, score_family, summarise
from synth2.world import LAW_KINDS
from synth2.write import TEXT_LEVELS

HEADLINE = ("recovers_law", "follows_evidence", "resists_overclaiming")
MAX_TRIES = 3   # a grid cell tries at most this many times the asked number of seeds


class BadArgument(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):
        raise BadArgument(message)


def _choices(text: str, known, what: str) -> list[str]:
    picked = [x.strip() for x in text.split(",") if x.strip()]
    unknown = [x for x in picked if x not in known]
    if unknown or not picked:
        raise BadArgument(f"unknown {what} {unknown}; choose from {', '.join(known)}")
    return list(dict.fromkeys(picked))


def families(root: Path) -> list[tuple[str, Path]]:
    """(grid cell, family folder) for every built family under `root`, in a fixed order. None is a bad argument."""
    found = [(p.parent.parent.parent.name, p.parent.parent) for p in root.glob("*/s*/base/manifest.json")
             if re.fullmatch(r"s\d+", p.parent.parent.name)]
    if not found:
        raise BadArgument(f"no corpus families under {root}")
    return sorted(found, key=lambda f: (f[0], int(f[1].name[1:])))


def _build_family(folder: Path, settings: Settings) -> None:
    """Base and relatives. Refused when noise made the key of the base or of the twin differ from its law."""
    build_base(folder / "base", settings)
    make_family(folder / "base")
    for member in ("base", "twin"):
        if not load_truth(folder / member)["key_matches_law"]:
            raise ValueError(f"{member}: the key does not equal the law")


def build(args: argparse.Namespace) -> int:
    laws = _choices(args.laws, LAW_KINDS, "law kinds")
    texts = _choices(args.texts, TEXT_LEVELS, "text levels")
    try:
        recipe = load_recipe(args.domain)
    except ValueError as err:
        raise BadArgument(str(err)) from err
    if args.seeds < 1 or args.studies < 1:
        raise BadArgument("--seeds and --studies must be at least 1")
    if args.studies > len(recipe.authors):
        raise BadArgument(f"--studies {args.studies} needs as many authors; the recipe has {len(recipe.authors)}")
    skipped, short = [], []
    for law in laws:
        for text in texts:
            cell, built, seed = f"{law}-{text}", 0, 0
            while built < args.seeds and seed < MAX_TRIES * args.seeds:   # a refused seed is replaced by the next
                folder = args.out / cell / f"s{seed}"
                try:
                    _build_family(folder, Settings(args.domain, seed, args.studies, law, text, exact=args.exact))
                    built += 1
                except ValueError as err:
                    shutil.rmtree(folder, ignore_errors=True)
                    skipped.append({"cell": cell, "seed": seed, "reason": str(err)})
                seed += 1
            print(f"{cell}: {built} built, {seed - built} skipped")
            if built < args.seeds:
                short.append(cell)
    write_json_atomic(args.out / "skipped.json", skipped)
    if short:
        print(f"synth2: fewer than {args.seeds} families after {MAX_TRIES * args.seeds} seeds in: {', '.join(short)}",
              file=sys.stderr)
        return 1
    return 0


def reference(args: argparse.Namespace) -> int:
    if args.rule not in RULES:
        raise BadArgument(f"unknown rule '{args.rule}'; choose from {', '.join(RULES)}")
    answers: dict[str, dict] = {}
    for _, folder in families(args.root):
        answers.update(reference_answers(folder, args.rule))
    write_json_atomic(args.out, answers)
    print(f"{len(answers)} answers by the {args.rule} rule -> {args.out}")
    return 0


def score(args: argparse.Namespace) -> int:
    try:
        answers = json.loads(args.answers.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise BadArgument(f"cannot read the answers file {args.answers}: {err}") from err
    if not isinstance(answers, dict):
        raise BadArgument("the answers file must be one object: corpus id -> answer")
    by_cell: dict[str, list[dict]] = {}
    for cell, folder in families(args.root):
        by_cell.setdefault(cell, []).append(score_family(folder, answers))
    skipped_file = args.root / "skipped.json"
    report = {"cells": {cell: summarise(reports) for cell, reports in by_cell.items()},
              "all": summarise([r for reports in by_cell.values() for r in reports]),
              "skipped": json.loads(skipped_file.read_text(encoding="utf-8")) if skipped_file.is_file() else []}
    write_json_atomic(args.out, report)
    print(f"{'cell':<20}" + "".join(f"{name:>26}" for name in HEADLINE))
    for cell, summary in [*report["cells"].items(), ("all", report["all"])]:
        print(f"{cell:<20}" + "".join(f"{f'{summary[n]['mean']:.2f} +- {summary[n]['stderr']:.2f} (n={summary[n]['n']})':>26}"
                                      for n in HEADLINE))
    return 0


def export_scir(args: argparse.Namespace) -> int:
    try:
        print(f"{export(args.root, args.out)} tasks -> {args.out}")
    except ValueError as err:
        raise BadArgument(str(err)) from err
    return 0


def parser() -> argparse.ArgumentParser:
    top = _Parser(prog="synth2", description=__doc__)
    sub = top.add_subparsers(dest="command", required=True, parser_class=_Parser)
    b = sub.add_parser("build", help="build a grid of corpus families: law kind x text level x seed")
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--domain", default="rag")
    b.add_argument("--seeds", type=int, default=10, help="families per grid cell; seeds count up from 0")
    b.add_argument("--studies", type=int, default=20)
    b.add_argument("--laws", default=",".join(LAW_KINDS))
    b.add_argument("--texts", default=",".join(TEXT_LEVELS))
    b.add_argument("--exact", action="store_true", help="no sampling noise: counts follow the law exactly")
    b.set_defaults(run=build)
    r = sub.add_parser("reference", help="write the answers a reference rule gives for every family")
    r.add_argument("--root", type=Path, required=True)
    r.add_argument("--rule", required=True, help=" | ".join(RULES))
    r.add_argument("--out", type=Path, required=True)
    r.set_defaults(run=reference)
    s = sub.add_parser("score", help="score an answers file against every family")
    s.add_argument("--root", type=Path, required=True)
    s.add_argument("--answers", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    s.set_defaults(run=score)
    e = sub.add_parser("export-scir", help="write every corpus under a folder as one SciR-shaped task file")
    e.add_argument("--root", type=Path, required=True)
    e.add_argument("--out", type=Path, required=True)
    e.set_defaults(run=export_scir)
    return top


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        return args.run(args)
    except BadArgument as err:
        print(f"synth2: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
