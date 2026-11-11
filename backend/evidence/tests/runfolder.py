"""A finished run folder for a test, written as the engine writes one (canonical JSON through jsonio.write_json,
evidence.jsonl through rundir.write_lines, run.json `settings` through engine.Settings.json, the seal through seal.seal),
so a reader sees the files a real run leaves, without running the engine."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonio import sha256_hex, write_json

from evidence.contract import Item
from evidence.engine import Settings
from evidence.plan import Plan, write_plan
from evidence.rundir import ANSWER_FILE, EVIDENCE_FILE, PLAN_FILE, RECORDS_FILE, RUN_FILE, write_lines


def write_run(root: Path, *, corpus: Path | str = "", status: str | None = "complete", answer: dict[str, Any] | None = None,
              plan: Plan | None = None, items: list[Item] | None = None, records: bytes | None = None,
              **settings: Any) -> Path:
    """`root` as a sealed run (`status` complete or failed; None: not sealed). `settings` are Settings fields (model,
    plan_version, stage_set, ...); answer.json, plan.json, evidence.jsonl and records.nq only when given."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, str] = {}
    if answer is not None:
        outputs[ANSWER_FILE] = write_json(root / ANSWER_FILE, answer)
    if plan is not None:
        write_plan(plan, root / PLAN_FILE)
    if items is not None:
        outputs[EVIDENCE_FILE] = write_lines(root / EVIDENCE_FILE, [i.model_dump(mode="json") for i in items])
    if records is not None:
        (root / RECORDS_FILE).write_bytes(records)
        outputs[RECORDS_FILE] = sha256_hex(records)
    if status != "failed":   # a crashed run has no run.json
        write_json(root / RUN_FILE, {"run_id": root.name, "mode": "run",
                                     "settings": Settings(corpus=str(corpus), cache="", **settings).json(),
                                     "outputs": dict(sorted(outputs.items()))})
    if status is not None:
        from evidence import seal
        seal.seal(root, "", status=status)
    return root
