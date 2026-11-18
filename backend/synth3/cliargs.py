"""Argument helpers shared by the `synth3` command modules."""
from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from synth3.sheetfacts import Folder, check_spec, load_folder
from synth3.spec import DomainSpec, load_spec


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


def _ascii(text: str) -> str:
    """A Windows console may not print every character of a model's reply or a reason."""
    return text.encode("ascii", "replace").decode("ascii")


def each_folder(root: Path, seeds: list[int], spec: DomainSpec,
                step: Callable[[Folder], tuple[list[str], bool]]) -> int:
    """Run `step` on the folder `root/s<seed>` of every seed and print the lines it returns.

    Every folder is loaded and checked against `spec` first, so a missing folder or one built from another spec
    stops the command (exit 2) before any step runs. `step` returns its lines and whether anything failed;
    the exit code is 1 when a step failed, else 0. Used by every per-folder command (draft-sheets, ...)."""
    folders, problems = [], []
    for seed in seeds:
        try:
            folder = load_folder(root / f"s{seed}")
            check_spec(folder, spec)
        except ValueError as err:
            problems.append(f"s{seed}: {err}")
            continue
        folders.append(folder)
    if problems:
        raise BadArgument("; ".join(problems))
    failed = False
    for folder in folders:
        lines, bad = step(folder)
        for line in lines:
            print(_ascii(line), flush=True)
        failed = failed or bad
    return 1 if failed else 0
