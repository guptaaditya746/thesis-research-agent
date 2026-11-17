"""`synth3` commands about questions: `questions` checks Aditya's file and shows what each one is about."""
from __future__ import annotations

import argparse
from pathlib import Path

from synth3.cliargs import BadArgument, _spec
from synth3.questions import QUESTIONS, load_questions
from synth3.sheetfacts import scope
from synth3.spec import SPECS


def questions(args: argparse.Namespace) -> int:
    spec = _spec(args)
    try:
        qs = load_questions(args.domain, spec, args.questions_root)
    except (OSError, ValueError) as err:
        raise BadArgument(str(err)) from err
    print(f"{len(qs.questions)} questions in {args.questions_root / (args.domain + '.yaml')}")
    labels = {a.id: a.label for a in spec.arms}
    names = {m.id: m.name for m in spec.measures}
    for q in qs.questions:
        n = scope(spec, q)
        arms = ", ".join(labels[a] for a in n.arms) or "all"
        measures = ", ".join(names[m] for m in n.measures) or "all"
        print(f"{q.id}: arms {arms}; measures {measures}; {len(q.sub_questions)} sub-questions")
    return 0


def add_question_commands(sub) -> None:
    p = sub.add_parser("questions", help="check a domain's question file and show what each question is about")
    p.add_argument("--domain", required=True)
    p.add_argument("--spec-root", type=Path, default=SPECS)
    p.add_argument("--questions-root", type=Path, default=QUESTIONS)
    p.set_defaults(run=questions)
