"""Offline EV1 review probes; intentionally exit 1 while the reported contract failures remain.

Run from the repository root:
    PYTHONPATH=. .venv/bin/python tests/EV1/diagnostics/review_repro.py
No model/server calls; all outputs except this JSON report use a temporary directory.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import yaml

from evidence import engine
from evidence.contract import DocumentRef
from evidence.extractors import terms
from evidence.locate import locate as locate_scope
from evidence.protocol import Locate, load
from evidence.propose import freeze
from evidence.propose.common import ProposalError
from evidence.propose.frame import load as load_frame
from evidence.tests.conftest import corpus_of, provider_of, scripted, screen_yes
from synth import variant
from synth.fidelity import BlindExtraction, BlindMeasurement, blind_check, check_paper
from synth.levels import make_plan, plan_rng
from synth.render_llm import locate

HERE = Path(__file__).resolve().parent


def probe(proposal: Path) -> list[dict]:
    rows = []
    with tempfile.TemporaryDirectory(prefix="ev1-review-") as tmp:
        root = Path(tmp)
        calls = []
        seen = []

        def reply(kind, doc, prompt):
            seen.append(kind)
            if kind == "screen":
                return screen_yes(prompt)
            return {"items": []}

        # A known treatment synonym, comparator synonym and outcome synonym from the frame.
        text = ("# Retrieval comparison\nThe retrieve-then-read system and the parametric-only model "
                "answer the same questions. We compare exact match: 75% versus 60%.\n")
        run = engine.run(proposal / "protocol.yaml", corpus_of(root / "corpus", {"P": text}),
                         root / "runs", cache=root / "cache", model="offline-scripted",
                         provider=provider_of(scripted(reply, calls)), strategy="gaps")
        funnel = json.loads((run / "funnel.json").read_text())["documents"]["P"]
        rows.append({"id": "screen_synonym_rescue", "ok": "screen" in seen and not funnel["skipped"],
                     "expected": "known synonym reaches semantic screen", "model_calls": seen.copy(),
                     "skipped": funnel["skipped"], "screen": funnel["screen"]["reason"]})

        repaired = yaml.safe_load((proposal / "protocol.yaml").read_text())
        repaired["screen"]["terms"].append("retrieve-then-read")
        fixed_path = root / "screen-control.yaml"
        fixed_path.write_text(yaml.safe_dump(repaired))
        seen.clear()
        control = engine.run(fixed_path, root / "corpus", root / "screen-control-runs",
                             cache=root / "screen-control-cache", model="offline-scripted",
                             provider=provider_of(scripted(reply, [])), strategy="gaps")
        c = json.loads((control / "funnel.json").read_text())["documents"]["P"]
        rows.append({"id": "screen_single_synonym_control", "ok": "screen" in seen and not c["skipped"],
                     "model_calls": seen.copy(), "skipped": c["skipped"]})

        # Replay freeze exactly, with the recorded model decisions and failed critic findings.
        copied = root / "proposal"
        shutil.copytree(proposal, copied)
        for name in ("protocol.yaml", "protocol.v1.yaml", "proposal.json"):
            (copied / name).unlink(missing_ok=True)
        frozen = freeze.run(copied, created="2026-10-21T00:00:00+00:00")
        record = json.loads((copied / "proposal.json").read_text())
        failed = [c["id"] for c in record["checks"] if not c["ok"]]
        rows.append({"id": "unresolved_deterministic_checks", "ok": not failed,
                     "classification": "documented policy; missing recommended safeguard",
                     "expected": "blocking checks are resolved or explicitly waived", "failed_checks": failed,
                     "frozen": frozen.exists(), "decided_by": record["decided_by"]})

        # Repair only the screening decision, using all treatment names already in the frame.
        for name in ("protocol.yaml", "protocol.v1.yaml", "proposal.json"):
            (copied / name).unlink(missing_ok=True)
        decisions = yaml.safe_load((copied / "decisions.yaml").read_text())
        f = load_frame(copied / "frame.json")
        for d in decisions["decisions"]:
            if d["card"] == "screen":
                d.update(choice="custom", by="diagnostic", reason="cover the declared treatment synonyms",
                         value={"question": f.population.screening_question,
                                "terms": list(dict.fromkeys([x.term for x in f.population.terms] + f.treatment.names))})
        (copied / "decisions.yaml").write_text(yaml.safe_dump(decisions))
        freeze.run(copied, created="2026-10-21T00:00:00+00:00")
        fixed = json.loads((copied / "proposal.json").read_text())
        rows.append({"id": "coverage_repair_control", "ok": all(c["ok"] for c in fixed["checks"]),
                     "failed_checks": [c["id"] for c in fixed["checks"] if not c["ok"]]})

        for name in ("protocol.yaml", "protocol.v1.yaml", "proposal.json"):
            (copied / name).unlink(missing_ok=True)
        changed_critic = json.loads((copied / "critic.json").read_text())
        changed_critic["checks"].append({"id": "changed-after-cards", "kind": "llm", "ok": False,
                                          "message": "New finding not available when these cards were generated"})
        (copied / "critic.json").write_text(json.dumps(changed_critic))
        refused = False
        try:
            freeze.run(copied, created="2026-10-21T00:00:00+00:00")
        except ProposalError as exc:
            refused = "critic.json changed" in str(exc)
        rows.append({"id": "critic_freshness", "ok": refused,
                     "expected": "cards must be regenerated after their critic input changes",
                     "changed_critic_accepted": not refused})

        p = load(proposal / "protocol.yaml")
        bad_text = ("# Invalid accuracy\nThe RAG model attains factual accuracy of 175%. "
                    "The closed-book model attains factual accuracy of 60%.\n")
        bad_corpus = corpus_of(root / "range-corpus", {"P": bad_text})
        for tag, protocol_path in (("proposal", proposal / "protocol.yaml"),
                                   ("hand", Path("evidence/protocols/rag-factuality.yaml"))):
            path = engine.run(protocol_path, bad_corpus, root / f"range-{tag}", selection="regex-only")
            items = [json.loads(s) for s in (path / "evidence.jsonl").read_text().splitlines()]
            vals = [i["fields"]["value"] for i in items if i["evidence_type"] == "measurement"]
            rows.append({"id": f"accuracy_bounds_{tag}", "ok": not any(v > 1 for v in vals),
                         "expected": "normalized accuracy outside [0,1] is rejected", "accepted_values": vals})

        def config(kind, name, key):
            return next(s.config[key] for s in p.evidence_types[kind].extractors if s.name == name)

        patterns = [tuple(x) for x in config("metric", "regex_metric", "metrics")]
        matches = [key for pattern, key, _ in patterns if re.search(pattern, "FActScore")]
        forward = [m.key for m in terms.find_all("FActScore", patterns)]
        reverse = [m.key for m in terms.find_all("FActScore", list(reversed(patterns)))]
        rows.append({"id": "metric_rule_overlap", "ok": len(set(matches)) == 1,
                     "classification": "rule-order sensitivity; current order is deterministic",
                     "matching_canonicals": sorted(set(matches)), "effective": forward, "reversed_order": reverse})

        roles = config("condition", "regex_condition", "conditions")
        got = [m.key for m in terms.find_all("RAG (no retrieval)", terms.condition_patterns(roles))]
        rows.append({"id": "negated_condition", "ok": got == ["closed_book"],
                     "expected": "one ablation condition is control only", "recognized_roles": got})

        doc = DocumentRef(id="P", file="papers/P.md", sha256="0" * 64)
        scope = locate_scope(p.locate, doc, "a " * 10000, "metric", p.evidence_types["metric"]).scope
        changed = locate_scope(Locate(strategy="exhaustive", params={"top_k": 1, "chunk_chars": 1}),
                               doc, "a " * 10000, "metric", p.evidence_types["metric"]).scope
        rows.append({"id": "locate_exhaustive_control", "ok": scope.kind == "document" and scope == changed,
                     "scope": scope.model_dump(), "params_ignored_as_designed": scope == changed})

        meta = json.loads((HERE / "rag-llm-s1-corpus.json").read_text())
        protocol = load("evidence/protocols/rag-factuality.yaml")
        studies = variant.base_studies(meta, protocol)
        _, _, after = variant.counterfactual(meta["seed"], studies, "S002", "contradicts", protocol.synthesis)
        plan = make_plan(after, "paraphrased", plan_rng(meta["seed"], "S002", "paraphrased"))
        text = (HERE / "step10-final-draft.md").read_text()
        old = "yields 662 out of 1,000 answers judged factually correct."
        new = "has a fraction of answers judged factually correct of 662 out of 1,000."
        assert text.count(old) == 1
        for tag, draft in (("original", text), ("wording_control", text.replace(old, new))):
            placements, decoys, problems = locate(draft, plan)
            checks = check_paper(draft, plan, placements, decoys)
            failed = [{"name": c.name, "detail": c.detail} for c in checks if not c.ok]
            rows.append({"id": f"step10_{tag}", "ok": not problems and not failed,
                         "required_string_problems": problems, "failed_checks": failed,
                         "blind_verifier_run": False})

        async def wrong_semantics(_):
            return BlindExtraction(measurements=[
                BlindMeasurement(condition=plan.cond_name[m.condition], metric="wrong metric",
                                 dataset="wrong dataset", value=m.value) for m in plan.measurements])

        blind = asyncio.run(blind_check(text, plan, wrong_semantics))
        rows.append({"id": "blind_metric_dataset_validation", "ok": not all(c.ok for c in blind),
                     "expected": "a verifier assigning every value to the wrong metric/dataset is rejected",
                     "accepted_wrong_metric_and_dataset": all(c.ok for c in blind),
                     "classification": "verifier currently checks only condition/value; incomplete semantic coverage"})

        for prefix, summary in (("rag-llm-s1", "step6-summary.json"), ("rag-llm-k1", "step8-summary.json")):
            meta = json.loads((HERE / f"{prefix}-corpus.json").read_text())
            studies = variant.base_studies(meta, protocol)
            levels = json.loads((HERE / summary).read_text())["levels"]
            excluded = set(levels[0]["excluded"])
            before = Counter(s.effect.direction for s in studies if s.counted)
            kept = Counter(s.effect.direction for s in studies if s.counted and s.study_id not in excluded)
            rows.append({"id": f"retention_{prefix}", "ok": True, "classification": "selection audit; no unbiasedness verdict",
                         "requested_records": len(studies), "retained_records": len(studies) - len(excluded),
                         "counted_directions_before": dict(before), "counted_directions_kept": dict(kept),
                         "per_level_local_pass": {x["level"]: x["locally_passing"] for x in levels}})
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", type=Path, default=HERE / "proposal")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repeat", type=int, default=1, choices=(1, 2))
    args = parser.parse_args()
    start = time.perf_counter()
    result = probe(args.proposal)
    if args.repeat == 2:
        assert result == probe(args.proposal), "probe results were not deterministic"
    rendered = json.dumps(result, indent=2) + "\n"
    print(rendered, end="")
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(f"{args.repeat} probe run(s): {time.perf_counter() - start:.2f}s after imports", file=sys.stderr)
    raise SystemExit(0 if all(row["ok"] for row in result) else 1)
