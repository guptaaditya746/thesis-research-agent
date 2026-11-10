"""The real-set registry (evaluation/realpapers/__init__.py): every adapter offers what its entry says, and the
`evaluate` command line takes its sets and steps from it."""
from __future__ import annotations

import inspect

from evaluation import cli
from evaluation.realpapers import SETS, WHOLE_RUN_SETS


def test_every_adapter_offers_what_its_entry_says() -> None:
    assert WHOLE_RUN_SETS == ("scilead", "scirex", "cochraneforest", "sofc")
    for rs in SETS.values():
        module = rs.module()
        if rs.whole_run:
            assert callable(module.questions), rs.name
            assert list(inspect.signature(module.left_out).parameters) == ["src", "corpus_dir", "qs"], rs.name
        for step, function, skip in ((rs.prepare, "prepare_step", ()), (rs.check, "check_step", ("out",))):
            if step is not None:   # the adapter takes exactly the step's flags (a check step all but --out)
                wanted = [d for d in step.dests if d not in skip]
                assert sorted(inspect.signature(getattr(module, function)).parameters) == sorted(wanted), rs.name


def test_the_command_line_has_every_step_and_set() -> None:
    parser = cli.parser()
    for rs in SETS.values():
        for step in (rs.prepare, rs.check):
            if step is not None:
                argv = [rs.name, step.name] + [x for flag, kw in step.args for x in (flag, "1" if kw["type"] is int else "x")]
                args = parser.parse_args(argv)
                assert args.func is cli.cmd_real and args.real_step == step.name
    for name in WHOLE_RUN_SETS:
        assert parser.parse_args(["wholerun", "--set", name, "--src", "s", "--runs", "r", "--out", "o"]).set == name
        assert parser.parse_args(["tune-split", "--set", name, "--src", "s"]).set == name
