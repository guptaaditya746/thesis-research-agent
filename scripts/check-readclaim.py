"""Real-model check of the ReadClaim step (general-system runbook, section 4.2).

    check-readclaim.py --corpus DIR [--cache FILE] [--limit N] [--list]

The labelled sentences are those of evidence.steps.tune.build_claims (claim sentences of the synthetic corpus with the
study's direction, and as many non-claim sentences). Each goes to the real `claims.read_claim` step on orch-model; the
output is the share with the right claim / not-a-claim verdict and the right direction, and the mean tune metric.
--list prints only how many sentences there are (no model call)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="check-readclaim.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--cache", type=Path, default=Path("readclaim-calls.jsonl"))
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)
    from evidence.steps import tune
    examples = tune.build_claims(args.corpus)
    pos = sum(e["gold"]["is_claim"] for e in examples)
    print(f"{len(examples)} labelled sentences ({pos} claims, {len(examples) - pos} not claims)")
    if args.list:
        return 0
    from evaluation.planbatch import orch_lm
    from evidence.claims import ReadClaim
    from evidence.steps import Step
    lm = orch_lm(args.cache)
    step = Step(ReadClaim, "claims.read_claim")
    scores, said_claim, right_dir, n_pos = [], 0, 0, 0
    for e in examples[:args.limit]:
        out = step(lm=lm, **e["inputs"])
        scores.append(tune.metric_claims(e["gold"], out))
        if e["gold"]["is_claim"]:
            n_pos += 1
            right_dir += getattr(out, "direction", None) == e["gold"]["direction"]
            said_claim += bool(getattr(out, "is_claim", False))
    report = {"n": len(scores), "mean_metric": sum(scores) / len(scores) if scores else None,
              "claims_called_claims": f"{said_claim}/{n_pos}", "claims_right_direction": f"{right_dir}/{n_pos}"}
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
