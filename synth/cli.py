"""`synth` command line: build a synthetic corpus set, make a counterfactual variant, draw a human
review sample."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evidence.pack import DOMAINS
from evidence.protocol import DEFAULT_PACK
from synth.levels import LEVELS
from synth.truth import DIRECTIONS, KNOBS, PRESETS


def parse_levels(text: str) -> list[str]:
    if text == "all":
        return list(LEVELS)
    levels = [lv.strip() for lv in text.split(",") if lv.strip()]
    unknown = [lv for lv in levels if lv not in LEVELS]
    if unknown or not levels:
        raise argparse.ArgumentTypeError(f"unknown levels {unknown}; choose from {', '.join(LEVELS)} or all")
    return list(dict.fromkeys(levels))


def parse_effects(text: str) -> dict[str, float]:
    """supports=0.6,contradicts=0.2,neutral=0.2 (shares, normalised; a direction left out gets none)."""
    mix: dict[str, float] = {}
    for part in text.split(","):
        key, _, value = part.partition("=")
        if key.strip() not in DIRECTIONS:
            raise argparse.ArgumentTypeError(f"unknown effect {key!r}; choose from {', '.join(DIRECTIONS)}")
        try:
            mix[key.strip()] = float(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"not a number: {value!r}") from exc
        if mix[key.strip()] < 0:
            raise argparse.ArgumentTypeError("effect shares must not be negative")
    return mix


def count(text: str) -> int:
    n = int(text)
    if n < 0:
        raise argparse.ArgumentTypeError("a knob is a count, not negative")
    return n


def make_renderer(args: argparse.Namespace, out: Path):
    from synth import corpus
    if args.renderer == "template":
        from synth.render_template import TemplateRenderer
        renderer: corpus.Renderer = TemplateRenderer()
    else:
        from modelcall.exchange import model_for
        from synth.render_llm import LlmRenderer
        cache = args.cache or out / ".synth-cache" / "llm.jsonl"
        exchange = args.exchange or out / ".synth-exchange"
        renderer = LlmRenderer(model_for(args.model, exchange), cache, attempts=args.attempts,
                               verify_model=model_for(args.verify_model, exchange) if args.verify_model else None,
                               concurrency=args.concurrency, statements=args.statements)
    return renderer


def add_renderer_options(p: argparse.ArgumentParser, default: str | None = "template",
                         statements: bool | None = True) -> None:
    p.add_argument("--renderer", choices=("template", "llm"), default=default)
    p.add_argument("--model", default="sub-model-1", help="LiteLLM alias of the writing model (llm renderer), or exchange:<name>")
    p.add_argument("--verify-model", default=None, help="LiteLLM alias for the blind re-extraction check, or exchange:<name>")
    p.add_argument("--attempts", type=int, default=3)
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--statements", action=argparse.BooleanOptionalAction, default=statements,
                   help="llm renderer: write and check each prose Results sentence before the paper (build: "
                        "default on; variant: default the base corpus's recorded mode, off if it records none)")
    p.add_argument("--cache", type=Path, default=None, help="default <out>/.synth-cache/llm.jsonl")
    p.add_argument("--exchange", type=Path, default=None,
                   help="for a model given as exchange:<name> (answered through files, modelcall/exchange.py): "
                        "the folder holding <name>/pending and <name>/replies (default <out>/.synth-exchange)")


HARD_LLM = ("--hard needs the template renderer: the LLM renderer's plan shape does not carry the "
            "experiments yet")


def cmd_build(args: argparse.Namespace) -> int:
    from synth import corpus
    if args.hard and args.renderer == "llm":
        print(f"ERROR: {HARD_LLM}", file=sys.stderr, flush=True)
        return 2
    if args.renderer == "llm" and not corpus.gate(args.domain, args.root):
        print(f"ERROR: {corpus.GATE_MESSAGE}", file=sys.stderr, flush=True)
        return 2
    renderer = make_renderer(args, args.out)
    result = corpus.build(name=args.name, seed=args.seed, studies=args.studies, renderer=renderer, out=args.out,
                          levels=args.levels, mix=args.effects, protocol=args.protocol, hard=args.hard,
                          domain=args.domain, root=args.root, preset=args.preset, **{knob: getattr(args, knob) for knob in KNOBS})
    print(json.dumps(result, indent=2))
    if result["excluded"]:
        print(f"WARNING: {len(result['excluded'])} studies failed fidelity and were left out; see fidelity.json")
        # Preserve the diagnostic artifacts, but do not report an empty build as successful.
        if not any(json.loads((Path(directory) / "manifest.json").read_text())["papers"]
                   for directory in result["corpora"]):
            print("ERROR: no papers retained after fidelity checks; see fidelity.json", file=sys.stderr, flush=True)
            return 1
    sel = result["selection"]
    if sel["requested_studies"] and sel["retained_studies"] / sel["requested_studies"] < args.min_retained:
        print(f"ERROR: retained {sel['retained_studies']}/{sel['requested_studies']} below --min-retained "
              f"{args.min_retained:g}", file=sys.stderr, flush=True)
        return 1
    return 0


def cmd_trial(args: argparse.Namespace) -> int:
    from synth import corpus
    args.renderer = "llm"
    renderer = make_renderer(args, args.root / args.domain)
    result = corpus.trial(args.domain, renderer=renderer, root=args.root, seed=args.seed)
    print(json.dumps({k: result[k] for k in ("recipe_sha256", "passed", "studies")}, indent=2))
    return 0 if result["passed"] else 1


def cmd_variant(args: argparse.Namespace) -> int:
    from synth import variant
    meta_file = args.corpus / "corpus.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.is_file() else {}
    if args.renderer is None or args.statements is None:
        if args.renderer is None:        # the base corpus's renderer, unless asked otherwise
            args.renderer = meta["renderer"]
        if args.statements is None:      # its pipeline too; a corpus from before the statement stage records none: off
            args.statements = bool((meta.get("models") or {}).get("statements", False))
    if (meta.get("settings") or {}).get("hard") and args.renderer == "llm":
        print(f"ERROR: a corpus built with {HARD_LLM}", file=sys.stderr, flush=True)
        return 2
    renderer = make_renderer(args, args.out or args.corpus.parent)
    result = variant.make(corpus_dir=args.corpus, study_id=args.study, direction=args.direction, renderer=renderer,
                          out=args.out, protocol=args.protocol)
    print(json.dumps(result, indent=2))
    return 0


def cmd_sample(args: argparse.Namespace) -> int:
    from synth.review import write_sample
    md, cs = write_sample(args.corpus, args.n, args.seed, args.out)
    print(f"wrote {md} and {cs}")
    return 0


def cmd_draft(args: argparse.Namespace) -> int:
    from evidence.pack import DOMAINS
    from modelcall import ModelCallError
    from modelcall.exchange import model_for
    from synth.draft import draft
    exchange = args.exchange or DOMAINS / args.domain / ".draft-exchange"
    cache = args.cache or DOMAINS / args.domain / "draft-calls.jsonl"
    try:
        path = draft(args.domain, args.papers, model=model_for(args.model, exchange),
                     verify_model=model_for(args.verify_model, exchange), cache=cache,
                     allow_empty_heldout=args.allow_empty_heldout)
    except (ValueError, ModelCallError) as exc:
        print(f"ERROR: drafting failed: {exc}", file=sys.stderr, flush=True)
        return 1
    print(f"wrote {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synth", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="generate a study set and write one corpus per level plus <name>-mixed")
    b.add_argument("--name", required=True)
    b.add_argument("--seed", type=int, required=True)
    b.add_argument("--studies", type=int, default=20)
    b.add_argument("--levels", type=parse_levels, default=list(LEVELS), help="comma separated, or all")
    b.add_argument("--effects", type=parse_effects, default=None,
                   help="true effect mix, e.g. supports=0.6,contradicts=0.2,neutral=0.2 (the default)")
    b.add_argument("--out", type=Path, default=Path("corpora"))
    b.add_argument("--domain", default=DEFAULT_PACK,
                   help=f"the pack whose recipe (domains/<domain>/generator.yaml) gives the words (default {DEFAULT_PACK})")
    b.add_argument("--protocol", type=Path, default=None,
                   help="the protocol whose synthesis block defines the ground truth (default: the recipe's "
                        "effect_protocol)")
    b.add_argument("--min-retained", type=float, default=0.0, metavar="FRACTION",
                   help="exit 1 when fewer than this fraction of the requested studies pass fidelity (default 0)")
    b.add_argument("--duplicates", type=count, default=0, help="extra papers that report an existing study again")
    b.add_argument("--missing", type=count, default=0,
                   help="studies whose control (alternately treatment) measurement the paper never states")
    b.add_argument("--outliers", type=count, default=0, help="supporting studies with an effect of 0.30 to 0.45")
    b.add_argument("--irrelevant", type=count, default=0, help="extra papers with no treatment/control experiment")
    b.add_argument("--hard", action="store_true",
                   help="about a third of the studies report a further experiment and/or an ablation, all in the "
                        "complex level's table (template renderer only)")
    b.add_argument("--preset", choices=PRESETS, default="plain",
                   help="builds_on: about the recipe's builds_on.share of the studies reuse an earlier study's method, "
                        "dataset or result (the recipe needs a builds_on block); default plain")
    b.add_argument("--root", type=Path, default=DOMAINS, help="the folder of domains (default domains/)")
    add_renderer_options(b)
    b.set_defaults(func=cmd_build)
    t = sub.add_parser("trial", help="write 5 builds_on papers with the LLM renderer and record whether they all pass "
                                     "(domains/<domain>/trial.json); build --renderer llm needs a passing one")
    t.add_argument("--domain", required=True)
    t.add_argument("--seed", type=int, default=0)
    t.add_argument("--root", type=Path, default=DOMAINS, help="the folder of domains (default domains/)")
    add_renderer_options(t, default="llm")
    t.set_defaults(func=cmd_trial)
    v = sub.add_parser("variant", help="change one study's effect and re-render only its paper (counterfactual)")
    v.add_argument("--corpus", type=Path, required=True, help="a built corpus directory")
    v.add_argument("--study", required=True)
    v.add_argument("--direction", choices=DIRECTIONS, required=True, help="the study's new effect direction")
    v.add_argument("--out", type=Path, default=None, help="default <corpus>-cf-<study>-<direction>")
    v.add_argument("--protocol", type=Path, default=None,
                   help="the protocol the base corpus was built from (default: its recipe's effect_protocol); refused "
                        "if its sha256 differs from the base corpus.json's")
    add_renderer_options(v, default=None, statements=None)
    v.set_defaults(func=cmd_variant)
    s = sub.add_parser("sample", help="write a human fidelity review sheet (Markdown + CSV) for a corpus")
    s.add_argument("--corpus", type=Path, required=True)
    s.add_argument("--n", type=int, default=5)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--out", type=Path, default=None, help="default <corpus>/review")
    s.set_defaults(func=cmd_sample)
    d = sub.add_parser("draft", help="draft domains/<domain>/generator.yaml from 5-10 real papers (D39)")
    d.add_argument("--domain", required=True)
    d.add_argument("--papers", type=Path, required=True, help="a folder of 5-10 .txt/.md papers, none held out")
    d.add_argument("--model", default="sub-model-1", help="LiteLLM alias of the drafting model, or exchange:<name>")
    d.add_argument("--verify-model", required=True, help="LiteLLM alias of the quoting model, or exchange:<name>")
    d.add_argument("--cache", type=Path, default=None, help="default domains/<domain>/draft-calls.jsonl")
    d.add_argument("--exchange", type=Path, default=None, help="default domains/<domain>/.draft-exchange")
    d.add_argument("--allow-empty-heldout", action="store_true",
                   help="draft even though domains/heldout.yaml lists no id (by default an empty list is refused)")
    d.set_defaults(func=cmd_draft)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
