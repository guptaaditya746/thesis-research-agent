"""`synth` command line: build a synthetic corpus set, draw a human review sample."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from synth.levels import LEVELS
from synth.truth import DIRECTIONS


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


def cmd_build(args: argparse.Namespace) -> int:
    from synth import corpus
    if args.renderer == "template":
        from synth.render_template import TemplateRenderer
        renderer: corpus.Renderer = TemplateRenderer()
    else:
        from gold.llm import openai_model
        from synth.render_llm import LlmRenderer
        cache = args.cache or args.out / ".synth-cache" / "llm.jsonl"
        renderer = LlmRenderer(openai_model(args.model), cache, attempts=args.attempts,
                               verify_model=openai_model(args.verify_model) if args.verify_model else None,
                               concurrency=args.concurrency)
    result = corpus.build(name=args.name, seed=args.seed, studies=args.studies, renderer=renderer, out=args.out,
                          levels=args.levels, mix=args.effects)
    print(json.dumps(result, indent=2))
    if result["excluded"]:
        print(f"WARNING: {len(result['excluded'])} studies failed fidelity and were left out; see fidelity.json")
    return 0


def cmd_sample(args: argparse.Namespace) -> int:
    from synth.review import write_sample
    md, cs = write_sample(args.corpus, args.n, args.seed, args.out)
    print(f"wrote {md} and {cs}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synth", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="generate a study set and write one corpus per level plus <name>-mixed")
    b.add_argument("--name", required=True)
    b.add_argument("--seed", type=int, required=True)
    b.add_argument("--studies", type=int, default=20)
    b.add_argument("--renderer", choices=("template", "llm"), default="template")
    b.add_argument("--levels", type=parse_levels, default=list(LEVELS), help="comma separated, or all")
    b.add_argument("--effects", type=parse_effects, default=None,
                   help="true effect mix, e.g. supports=0.6,contradicts=0.2,neutral=0.2 (the default)")
    b.add_argument("--out", type=Path, default=Path("corpora"))
    b.add_argument("--model", default="sub-model-1", help="LiteLLM alias of the writing model (llm renderer)")
    b.add_argument("--verify-model", default=None, help="LiteLLM alias for the blind re-extraction check")
    b.add_argument("--attempts", type=int, default=3)
    b.add_argument("--concurrency", type=int, default=4)
    b.add_argument("--cache", type=Path, default=None, help="default <out>/.synth-cache/llm.jsonl")
    b.set_defaults(func=cmd_build)
    s = sub.add_parser("sample", help="write a human fidelity review sheet (Markdown + CSV) for a corpus")
    s.add_argument("--corpus", type=Path, required=True)
    s.add_argument("--n", type=int, default=5)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--out", type=Path, default=None, help="default <corpus>/review")
    s.set_defaults(func=cmd_sample)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
