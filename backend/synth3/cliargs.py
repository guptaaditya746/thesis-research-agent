"""Argument helpers shared by the `synth3` command modules."""
from __future__ import annotations

import argparse

from synth3.spec import load_spec


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
