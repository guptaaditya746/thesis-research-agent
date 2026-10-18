"""`python -m webapp.tool <evidence|synth|evaluate> ARGS...`: the three command lines the jobs run, by the name
of their console script (pyproject.toml), in the server's own interpreter.

The jobs (webapp/evjobs.py) call the packages' `main(argv)` through this one entry point instead of the console
scripts, so the interpreter is the server's (`$WEBAPP_PYTHON`) wherever the scripts are installed; the
arguments go to the package's own argparse unchanged.
"""
from __future__ import annotations

import importlib
import sys

TOOLS = {"evidence": "evidence.cli", "synth": "synth.cli", "evaluate": "evaluation.cli"}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in TOOLS:
        print(f"usage: python -m webapp.tool {{{','.join(TOOLS)}}} ARGS...", file=sys.stderr)
        return 2
    return int(importlib.import_module(TOOLS[args[0]]).main(args[1:]) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
