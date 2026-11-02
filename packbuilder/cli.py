"""`packbuilder` command line.

    packbuilder serve --corpus DIR    the corpus tool server (server.py) over stdio, for an MCP client
    packbuilder propose --corpus DIR --name N --model M --verify-model V [--question Q] [--root DIR] [--cache F]
                        [--exchange DIR]
                                      the pack-builder agent (agent.py): M proposes, V checks each word; writes
                                      <root>/N/{pack.yaml,words.yaml} and logs them in provenance.json. By default
                                      the call cache (propose-calls.jsonl, committed: the record of the calls behind
                                      the pack) and the exchange folder (.propose-exchange, gitignored) sit in the
                                      pack folder; freeze hashes neither (only *.yaml, *.json and protocols/*.yaml)
    packbuilder helper --corpus DIR --name N --model M --verify-model V [--question Q] [--root DIR] [--cache F]
                       [--exchange DIR]
                                      the D34 fallback (helper.py): M writes the pack from the paper texts alone,
                                      V checks each word; refuses beside a generator.yaml, so a domain with a
                                      drafted recipe runs it with --root <scratch> and then adopts the result
    packbuilder adopt --from DIR --into DIR
                                      copy a helper pack (pack.yaml, words.yaml, helper-calls.jsonl) from a scratch
                                      folder into its domain folder and merge its provenance entries (helper.adopt)
    packbuilder freeze DIR            check the pack in DIR, write DIR/FROZEN.json, print the git tag command
                                      (freeze.py; it never runs git)

Exit status: 0 ok, 2 a refused proposal or freeze (the reason on stderr).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from packbuilder.server import create_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="packbuilder")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="serve a corpus's tools over MCP stdio")
    serve.add_argument("--corpus", type=Path, required=True, help="corpus directory (manifest.json and papers/)")
    prop = commands.add_parser("propose", help="propose a domain pack from a corpus's papers (agent over the tools)")
    prop.add_argument("--corpus", type=Path, required=True, help="corpus directory (manifest.json and papers/)")
    prop.add_argument("--name", required=True, help="the pack's name: its folder under --root")
    prop.add_argument("--model", required=True, help="LiteLLM alias, or exchange:<name> (answered through files)")
    prop.add_argument("--verify-model", required=True, help="the model that checks each word (alias or exchange:<name>)")
    prop.add_argument("--question", default=None, help="the topic question the pack serves")
    prop.add_argument("--root", type=Path, default=None, help="the domains folder (default domains/)")
    prop.add_argument("--cache", type=Path, default=None, help="default <root>/<name>/propose-calls.jsonl")
    prop.add_argument("--exchange", type=Path, default=None, help="default <root>/<name>/.propose-exchange")
    hlp = commands.add_parser("helper", help="D34 fallback: write a pack from the paper texts alone")
    hlp.add_argument("--corpus", type=Path, required=True, help="corpus directory (manifest.json and papers/)")
    hlp.add_argument("--name", required=True, help="the pack's name: its folder under --root")
    hlp.add_argument("--model", required=True, help="LiteLLM alias, or exchange:<name>")
    hlp.add_argument("--verify-model", required=True, help="the model that checks each word")
    hlp.add_argument("--question", default=None, help="the topic question the pack serves")
    hlp.add_argument("--root", type=Path, default=None, help="the domains folder (default domains/)")
    hlp.add_argument("--cache", type=Path, default=None, help="default <root>/<name>/helper-calls.jsonl")
    hlp.add_argument("--exchange", type=Path, default=None, help="default <root>/<name>/.helper-exchange")
    adp = commands.add_parser("adopt", help="move a helper pack from a scratch folder into its domain folder")
    adp.add_argument("--from", dest="source", type=Path, required=True, help="the scratch pack folder, <scratch>/N")
    adp.add_argument("--into", dest="target", type=Path, required=True, help="the domain folder, e.g. domains/N")
    frz = commands.add_parser("freeze", help="freeze a finished pack: FROZEN.json and the tag command")
    frz.add_argument("pack", type=Path, help="the pack folder, e.g. domains/N")
    args = parser.parse_args(argv)
    if args.command == "serve":
        create_server(args.corpus).run(transport="stdio")
        return 0
    if args.command in ("propose", "helper"):
        from evidence.pack import DOMAINS
        from modelcall.exchange import model_for
        from packbuilder.agent import DEFAULT_QUESTION, propose
        from packbuilder.helper import helper
        run = propose if args.command == "propose" else helper
        root = args.root or DOMAINS
        cache = args.cache or root / args.name / f"{args.command}-calls.jsonl"
        exchange = args.exchange or root / args.name / f".{args.command}-exchange"
        try:
            folder = run(args.corpus, args.name, model=model_for(args.model, exchange), cache=cache, root=root,
                         verify_model=model_for(args.verify_model, exchange),
                         question=args.question or DEFAULT_QUESTION)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr, flush=True)
            return 2
        print(folder)
        return 0
    if args.command == "adopt":
        from packbuilder.helper import adopt
        try:
            print(adopt(args.source, args.target))
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr, flush=True)
            return 2
        return 0
    from packbuilder.freeze import freeze
    try:
        freeze(args.pack)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
