"""Real-paper sets (D42, spec 6.12): loaders and scorers for labelled real papers. A real-paper check writes
`real.json` and `real.md` (common.write_real), reported as a "real-paper check" and never mixed into a synthetic
report.json. The gold of a real-paper set is read by its scorer only (D31).

`SETS` is the one list of sets; the `evaluate` command line and `scripts/plan-runs.py` read it. Each set is an adapter
module `realpapers/<name>.py` that offers what its `RealSet` entry says:

  whole_run  questions(src, corpus_dir=None) -> [RealQuestion]   each with its answer-key `records`, or None
             left_out(src, corpus_dir=None, qs=None) -> str      the "left out: N of M ..." line of the report
  prepare    prepare_step(**flags) -> str    `evaluate <name> <prepare.name>`: writes a corpus or an ids file;
                                             returns the text to print
  check      check_step(**flags) -> dict     `evaluate <name> <check.name>`: the real.json result; the command
                                             writes it with real.md titled `title` into --out

The steps' flags are declared here (`Step.args`); the adapter's function takes them as keywords (their dest names;
a check step gets every flag but --out). Corpora are written with common.add_paper / write_manifest. Adapters are
imported only when used (they import evaluation.wholerun, which imports realpapers.common)."""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

Arg = tuple[str, dict[str, Any]]


def _arg(flag: str, help: str | None = None, **kw: Any) -> Arg:
    """A flag of a step: a required path unless `kw` says otherwise."""
    return flag, {"type": Path, "required": True, "help": help, **kw}


@dataclass(frozen=True)
class Step:
    """One subcommand `evaluate <set> <name>`."""
    name: str
    help: str
    args: tuple[Arg, ...]

    @property
    def dests(self) -> tuple[str, ...]:
        return tuple(flag.lstrip("-").replace("-", "_") for flag, _ in self.args)


@dataclass(frozen=True)
class RealSet:
    name: str                    # `evaluate <name> ...`, `--set <name>`; the adapter is realpapers/<name>.py
    help: str = ""               # `evaluate <name>` help (a set with steps)
    title: str = ""              # real.md title of the check step
    prepare: Step | None = None
    check: Step | None = None
    summary: tuple[str, ...] = ()   # keys of the check's result printed beside the real.json / real.md paths
    whole_run: bool = False      # questions + left_out: `evaluate wholerun`, `tune-split`, plan-runs.py

    def module(self) -> ModuleType:
        return importlib.import_module(f"{__name__}.{self.name}")

    def questions(self, src: Path, corpus: Path | None = None) -> list[Any]:
        return self.module().questions(src, corpus)

    def left_out(self, src: Path, corpus: Path | None = None, qs: list[Any] | None = None) -> str:
        return self.module().left_out(src, corpus, qs)


_RUN = _arg("--run", "run directory written by `evidence run`")
SETS: dict[str, RealSet] = {s.name: s for s in (
    RealSet("scilead", "real-paper check: SciLead values, best per leaderboard, pairwise order (D42)", "SciLead",
            prepare=Step("ids", "the papers' arXiv ids, one per line, for `evidence fetch --ids`", (
                _arg("--data", "the unpacked SciLead release"),
                _arg("--out", "the ids file to write"))),
            check=Step("score", "score a run of domains/ml/protocols/values.yaml -> real.json and real.md", (
                _RUN,
                _arg("--corpus", "corpus directory written by `evidence fetch --ids`"),
                _arg("--data", "the unpacked SciLead release (the gold)"),
                _arg("--out"))),
            whole_run=True),
    RealSet("scirex", "real-paper check: SciREX names at mention and salient-cluster level (D21)", "SciREX",
            prepare=Step("corpus", "SciREX JSON lines -> manifest.json, papers/ and the gold (read by score only)", (
                _arg("--jsonl", "a SciREX split file (e.g. test.jsonl)"),
                _arg("--out", "the corpus directory to write"),
                _arg("--limit", "keep the first N papers (chosen with `evidence estimate`)", type=int,
                     required=False))),
            check=Step("score", "score a run of domains/ml/protocols/names.yaml -> real.json and real.md", (
                _RUN,
                _arg("--corpus", "corpus directory written by `scirex corpus`"),
                _arg("--out"),
                _arg("--estimate", "the saved output of `evidence estimate` that chose --limit", required=False))),
            whole_run=True),
    RealSet("cochraneforest", whole_run=True),
    RealSet("sofc", whole_run=True),
    RealSet("edits", "real-paper check: the arXiv edit test (a number, a name, a limitation changed)",
            "arXiv edit test",
            prepare=Step("apply", "one edited corpus per edit -> <out>/<edit id>", (
                _arg("--corpus", "the original corpus (e.g. from `evidence fetch --ids`)"),
                _arg("--edits", "the frozen edits file (evaluation/realpapers/data/)"),
                _arg("--out", "the folder of the edited corpora"))),
            check=Step("check", "item, link and answer per edit -> real.json and real.md", (
                _arg("--original", "the run directory on the original corpus"),
                _arg("--runs", "the folder holding one run per edit, named by edit id"),
                _arg("--edits"),
                _arg("--corpora", "the folder `edits apply` wrote: each edit is placed by its edit.json (default: "
                     "the edited run's corpus, else the original run's spans)", required=False),
                _arg("--out"))),
            summary=("carried", "missing", "not_testable")),
    RealSet("yun", "real-paper check: Yun et al. 2024 + Evidence Inference, A/B/C separately (D42)",
            "Yun et al. 2024 + Evidence Inference",
            prepare=Step("corpus", "the records' markdown papers -> manifest.json, papers/ and the gold", (
                _arg("--repo", "a checkout of hyesunyun/llm-meta-analysis"),
                _arg("--ei", "Evidence Inference 2.0's annotations/ folder"),
                _arg("--out", "the corpus directory to write"))),
            check=Step("score", "score a drug-trials run (its comparisons.json) -> real.json and real.md", (
                _RUN,
                _arg("--corpus", "corpus directory written by `yun corpus`"),
                _arg("--out"))),),
)}
WHOLE_RUN_SETS = tuple(name for name, s in SETS.items() if s.whole_run)


def real_set(name: str) -> RealSet:
    if name not in SETS:
        raise ValueError(f"unknown real set {name!r}; known: {', '.join(SETS)}")
    return SETS[name]
