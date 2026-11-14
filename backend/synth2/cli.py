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
from synth2.engine_answers import collect
from synth2 import realedit, realpool
from synth2.recipe import load_recipe
from synth2.scir_export import export
from synth2.score import RULES, reference_answers, score_family, summarise
from synth2.world import LAW_KINDS
from synth2.write import TEXT_LEVELS
from synth2.written import assemble

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


def written_corpus(args: argparse.Namespace) -> int:
    try:
        print(f"{assemble(args.template, args.papers, args.out)} written papers -> {args.out}")
    except (ValueError, OSError) as err:
        raise BadArgument(str(err)) from err
    return 0


def engine_answers(args: argparse.Namespace) -> int:
    try:
        answers = collect(args.runs)
    except ValueError as err:
        raise BadArgument(str(err)) from err
    write_json_atomic(args.out, answers)
    print(f"{len(answers)} engine answers -> {args.out}")
    return 0


def _read_failure(err: Exception) -> BadArgument:
    return BadArgument(f"{type(err).__name__}: {err}")


def realpool_split(args: argparse.Namespace) -> int:
    try:
        out = realpool.split_file(args.rows, args.old_split, args.out)
    except (OSError, ValueError, KeyError) as err:
        raise _read_failure(err) from err
    print(out["counts"], "old eval in test:", len(out["old_eval_in_test"]), "style excluded:", out["style_excluded"])
    return 0


def realpool_cut(args: argparse.Namespace) -> int:
    try:
        done = realpool.cut_side(args.rows, args.split, args.side, args.out)
    except (OSError, ValueError, KeyError) as err:
        raise _read_failure(err) from err
    for note in done["notes"]:
        print(note)
    if args.side == "test":
        print(done["pieces"], "pieces from", done["papers"], "papers")
    print(done["full"], "full papers;", "no body found:", done["no_body"])
    return 0


def slice_papers(args: argparse.Namespace) -> int:
    try:
        done = realpool.slice_papers(args.papers, args.out)
    except (OSError, ValueError) as err:
        raise _read_failure(err) from err
    for note in done["notes"]:
        print(note)
    print(done["pieces"], "pieces from", done["papers"], "papers")
    return 0


def realedit_assign(args: argparse.Namespace) -> int:
    try:
        done = realedit.assign_sources(args.inputs, args.rows, args.split, args.full, args.out)
    except (OSError, ValueError, KeyError) as err:
        raise _read_failure(err) from err
    for study, pid in done:
        print(study, pid)
    print(len(done), "inputs")
    return 0


def realedit_prepare(args: argparse.Namespace) -> int:
    try:
        done = realedit.prepare(args.inputs, args.out)
    except (OSError, ValueError, KeyError) as err:
        raise _read_failure(err) from err
    for d in done:
        print(d["study"], d["source"], d["names"], "names renamed,", d["words"], "words")
    return 0


def realedit_apply(args: argparse.Namespace) -> int:
    try:
        studies = args.study or sorted(p.stem for p in (args.base / "inputs").glob("S*.json"))
        if not studies:
            raise BadArgument(f"no inputs under {args.base / 'inputs'}")
        bad = 0
        for sid in studies:
            done = realedit.apply_study(args.base, sid, claim_rules=args.claim_rules)
            print(f"{sid}: {done['words']} words, {done['inserted']} inserted")
            for p in done["problems"]:
                print("-", p)
            bad += bool(done["problems"])
            print("OK" if not done["problems"] else "FIX: " + "; ".join(p[:60] for p in done["problems"]))
    except (OSError, ValueError, KeyError) as err:
        raise _read_failure(err) from err
    return 1 if bad else 0


def realedit_check(args: argparse.Namespace) -> int:
    try:
        report, extras = realedit.check_base(args.grid, args.base, args.readers, claim_rules=args.claim_rules)
    except (OSError, ValueError, KeyError) as err:
        raise _read_failure(err) from err
    print(f"kept {sum(v['ok'] for v in report.values())} of {len(report)}; reader listed {extras} other results")
    for k, v in report.items():
        if not v["ok"]:
            print(k, v["problems"])
    return 0


def realism_report(args: argparse.Namespace) -> int:
    from synth2 import realism   # scikit-learn is heavy; load it only here
    sets = {}
    for item in args.gap:
        name, _, root = item.partition("=")
        if not root:
            raise BadArgument(f"--gap needs NAME=ROOT, got '{item}'")
        sets[name] = Path(root)
    try:
        out = realism.c2st(args.real, args.synthetic, log=lambda m: print(m, file=sys.stderr, flush=True))
        if sets:
            out["style gap"] = realism.style_gap(args.real, sets)
    except (OSError, ValueError) as err:
        raise _read_failure(err) from err
    text = json.dumps(out, indent=1, ensure_ascii=False)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
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
    w = sub.add_parser("written-corpus", help="assemble a corpus from model-written rewrites of a template's papers")
    w.add_argument("--template", type=Path, required=True)
    w.add_argument("--papers", type=Path, required=True, help="folder holding one <paper id>.md per template paper")
    w.add_argument("--out", type=Path, required=True)
    w.set_defaults(run=written_corpus)
    a = sub.add_parser("engine-answers", help="the engine's answers (one run folder per corpus) as an answers file")
    a.add_argument("--runs", type=Path, required=True, help="folder holding one run folder (run.json, answer.json) per corpus")
    a.add_argument("--out", type=Path, required=True)
    a.set_defaults(run=engine_answers)
    rs = sub.add_parser("realpool-split", help="split a real paper set (jsonl) into test and source pools")
    rs.add_argument("--rows", type=Path, required=True, help="the paper set, one json row per line")
    rs.add_argument("--old-split", type=Path, required=True, help="the earlier split.json (style and eval papers)")
    rs.add_argument("--out", type=Path, required=True)
    rs.set_defaults(run=realpool_split)
    rc = sub.add_parser("realpool-cut", help="clean the Docling markdown of one side of the split and cut pieces")
    rc.add_argument("--rows", type=Path, required=True)
    rc.add_argument("--split", type=Path, required=True)
    rc.add_argument("--side", choices=("test", "sources"), required=True)
    rc.add_argument("--out", type=Path, required=True)
    rc.set_defaults(run=realpool_cut)
    sl = sub.add_parser("slice", help="cut our markdown papers into pieces with the rules used for real papers")
    sl.add_argument("--papers", type=Path, required=True, help="folder holding S*.md papers")
    sl.add_argument("--out", type=Path, required=True)
    sl.set_defaults(run=slice_papers)
    ra = sub.add_parser("realedit-assign", help="give each study input a different real source paper")
    ra.add_argument("--inputs", type=Path, required=True, help="folder of S*.json study inputs")
    ra.add_argument("--rows", type=Path, required=True)
    ra.add_argument("--split", type=Path, required=True)
    ra.add_argument("--full", type=Path, required=True, help="folder of cleaned full source papers (<id>.md)")
    ra.add_argument("--out", type=Path, required=True)
    ra.set_defaults(run=realedit_assign)
    rp = sub.add_parser("realedit-prepare", help="rename every name in each study's source paper")
    rp.add_argument("--inputs", type=Path, required=True, help="folder of S*.json inputs with skeleton_source")
    rp.add_argument("--out", type=Path, required=True, help="base folder for sources, maps and inputs")
    rp.set_defaults(run=realedit_prepare)
    ry = sub.add_parser("realedit-apply", help="apply the writers' edits to the renamed sources and check them")
    ry.add_argument("--base", type=Path, required=True)
    ry.add_argument("--study", action="append", help="one study id (repeatable); default every study")
    ry.add_argument("--claim-rules", action="store_true", help="writer-v12 rules: no copied claim, word limits")
    ry.set_defaults(run=realedit_apply)
    rk = sub.add_parser("realedit-check", help="code checks and the blind reader against the ground truth")
    rk.add_argument("--grid", type=Path, required=True, help="family folder holding ground_truth.json")
    rk.add_argument("--base", type=Path, required=True)
    rk.add_argument("--readers", type=Path, nargs="*", default=[], help="reader json files")
    rk.add_argument("--claim-rules", action="store_true", help="writer-v12 rules: no copied claim, word limits")
    rk.set_defaults(run=realedit_check)
    rm = sub.add_parser("realism", help="real-vs-synthetic classifier AUC (five views) and style gap")
    rm.add_argument("--real", type=Path, required=True, help="folder of real pieces (*_pN.md)")
    rm.add_argument("--synthetic", type=Path, required=True, help="synthetic root (papers/ or a grid)")
    rm.add_argument("--gap", action="append", default=[], help="NAME=ROOT of a set for the style gap (repeatable)")
    rm.add_argument("--out", type=Path)
    rm.set_defaults(run=realism_report)
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
