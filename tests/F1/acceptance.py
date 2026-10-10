from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from openai import OpenAI


REPO = Path(__file__).resolve().parents[2]
RUN = Path(__file__).resolve().parent / "run-001"
WORK = RUN / "work"
OUT = WORK / "out"
CORPUS = Path(os.environ["CORPUS"]).resolve()
AGENT_ROOT = Path(os.environ["AGENT_ROOT"]).resolve()
PYTHON_RUNTIME = Path(os.path.realpath(AGENT_ROOT / "agent-venv/bin/python")).parent.parent
RUN.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

client = OpenAI(base_url="http://127.0.0.1:4000/v1",
                api_key=os.environ["LITELLM_MASTER_KEY"], timeout=600)
system = """You are a research agent. The frozen corpus is at the path in $CORPUS. It contains one Markdown file per paper and is read-only. Available shell tools include grep, rg, jq, python3, and claim. `claim` reads one JSON object from stdin with fields s, p, o, file, quote, then records it. Set `file` to a corpus Markdown basename and make `quote` an exact line from that file, without grep line numbers. Count papers, not matching lines. Print the count as RETRIEVAL_PAPER_COUNT=<integer>. Reply with short plain text then exactly one fenced bash block. The block must count corpus papers containing retrieval and record one claim supported by an exact quote from one of them. Do not use network access."""
task = "Count the Markdown papers whose text contains the word retrieval, case-insensitive. Print RETRIEVAL_PAPER_COUNT=<integer>. Pick one exact line containing retrieval and record a claim that the paper mentions retrieval. A robust way to encode the claim is to put the selected path and line in shell variables FILE and QUOTE, then run `FILE=\"$file\" QUOTE=\"$quote\" python3 -c 'import json,os; print(json.dumps({\"s\":\"the paper\",\"p\":\"mentions\",\"o\":\"retrieval\",\"file\":os.path.basename(os.environ[\"FILE\"]),\"quote\":os.environ[\"QUOTE\"]}))' | claim`."
started = time.perf_counter()
response = client.chat.completions.create(
    model="orch-model", messages=[{"role": "system", "content": system},
                                   {"role": "user", "content": task}],
    max_tokens=4096, temperature=0,
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
)
elapsed_model = time.perf_counter() - started
content = response.choices[0].message.content or ""
(RUN / "model-response.txt").write_text(content, encoding="utf-8")

blocks = re.findall(r"```(?:bash|sh)\s*\n(.*?)```", content, flags=re.DOTALL)
if blocks:
    command = blocks[0]
    parse_mode = "fenced_first_block" if len(blocks) > 1 else "one_fenced_block"
else:
    lines = [line for line in content.strip().splitlines() if line.strip()]
    if len(lines) == 1 or (len(lines) <= 3 and all(not re.search(r"[.!?]\s*$", line) for line in lines)):
        command = "\n".join(lines)
        parse_mode = "bare_command_fallback"
    else:
        raise RuntimeError("model response has no executable bash/sh block or bare-command fallback")

(RUN / "command.sh").write_text(command + "\n", encoding="utf-8")
verification = subprocess.run([str(REPO / "scripts/verify-agent-root.sh"), str(AGENT_ROOT)],
                              capture_output=True, text=True, timeout=600)
if verification.returncode:
    raise RuntimeError(f"agent-root verification failed: {verification.stderr[-1000:]}")
(RUN / "agent-root-verify.log").write_text(verification.stdout + verification.stderr,
                                            encoding="utf-8")
claim_log = RUN / "claims.jsonl"
command_prefix = f"""set -euo pipefail
ulimit -v 2097152
if touch "$CORPUS/.f1-write-probe" 2>/dev/null; then echo CORPUS_WRITABLE_FAIL; else echo CORPUS_READONLY=ok; fi
python3 -c 'import socket;\ntry: socket.socket(socket.AF_INET, socket.SOCK_STREAM); print("NETWORK_ALLOWED_FAIL")\nexcept OSError as e: print("NETWORK_BLOCKED",e.errno)'
"""
full_command = command_prefix + "\n" + command
path_env = f"{REPO / 'tests/F1/bin'}:{AGENT_ROOT / 'bin'}:{AGENT_ROOT / 'agent-venv/bin'}:/usr/bin:/bin"
sandbox_python = str(AGENT_ROOT / "agent-venv/bin/python")
argv = [
    sys.executable, str(REPO / "tests/S5/run_sandbox.py"), "--timeout", "120",
    "--claim-log", str(claim_log), "--step-id", "1", "--",
    sandbox_python, str(REPO / "tests/S5/sandbox.py"),
    "--readonly", "/usr", "--readonly", "/lib", "--readonly", "/lib64",
    "--readonly", "/bin", "--readonly", "/etc", "--readonly", "/dev",
    "--readonly", str(REPO), "--readonly", str(CORPUS), "--readonly", str(AGENT_ROOT),
    "--readonly", str(PYTHON_RUNTIME),
    "--writable", str(WORK), "--workdir", str(WORK), "--",
    "/usr/bin/env", f"CORPUS={CORPUS}", f"PATH={path_env}",
    "/bin/bash", "-c", full_command,
]
run = subprocess.run(argv, cwd=REPO, capture_output=True, text=True, timeout=150)
stdout = run.stdout
stderr = run.stderr
(OUT / "1.txt").write_text(stdout, encoding="utf-8")
(RUN / "stderr.txt").write_text(stderr, encoding="utf-8")

claims = [json.loads(line) for line in claim_log.read_text(encoding="utf-8").splitlines() if line]
manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
manifest_by_id = {paper["id"]: paper for paper in manifest["papers"]}
assert run.returncode == 0, f"sandbox failed: rc={run.returncode}, stdout={stdout[-1000:]}, stderr={stderr[-1000:]}"
assert "CORPUS_READONLY=ok" in stdout
assert "NETWORK_BLOCKED" in stdout and "NETWORK_ALLOWED_FAIL" not in stdout
assert len(claims) == 1, f"expected one claim, received {len(claims)}"
claim = claims[0]
assert claim["step_id"] == 1
claimed_path = Path(claim["file"])
claimed_name = claimed_path.name
paper_id = claimed_name.removesuffix(".md")
paper = manifest_by_id[paper_id]
paper_path = CORPUS / f"{paper_id}.md"
assert hashlib.sha256(paper_path.read_bytes()).hexdigest() == paper["markdown_sha256"]
assert claim["quote"] and claim["quote"] in paper_path.read_text(encoding="utf-8")

count = sum(1 for paper_row in manifest["papers"]
           if paper_row["failure"] is None and
           "retrieval" in (CORPUS / f"{paper_row['id']}.md").read_text(encoding="utf-8").casefold())
match = re.search(r"RETRIEVAL_PAPER_COUNT\s*=\s*(\d+)", stdout)
assert match and int(match.group(1)) == count, f"reported count {match.group(1) if match else None}, expected {count}"

event = {
    "step": 1, "command": command, "parse_mode": parse_mode, "exit_code": run.returncode,
    "stdout_bytes": len(stdout.encode()), "stderr_bytes": len(stderr.encode()),
    "stdout_path": "work/out/1.txt", "stdout_head": stdout.encode()[:8192].decode(errors="replace"),
    "model_seconds": elapsed_model, "prompt_tokens": response.usage.prompt_tokens,
    "completion_tokens": response.usage.completion_tokens, "prev_hash": "0" * 64,
}
event["hash"] = hashlib.sha256(json.dumps(event, sort_keys=True, separators=(",", ":"),
                                        ensure_ascii=False).encode()).hexdigest()
(RUN / "events.jsonl").write_text(json.dumps(event, ensure_ascii=False) + "\n", encoding="utf-8")

def verify_chain(path: Path, *, ensure_ascii: bool) -> str:
    prev = "0" * 64
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        digest = row.pop("hash")
        assert row["prev_hash"] == prev
        expected = hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                             ensure_ascii=ensure_ascii).encode()).hexdigest()
        assert digest == expected
        prev = digest
    return prev

event_head = verify_chain(RUN / "events.jsonl", ensure_ascii=False)
claim_head = verify_chain(claim_log, ensure_ascii=True)
summary = {
    "pass": True, "papers_with_retrieval": count, "claim_count": len(claims),
    "claim_file": claimed_name, "claim_quote_verified": True,
    "events_head": event_head, "claims_head": claim_head,
    "model_seconds": elapsed_model, "prompt_tokens": response.usage.prompt_tokens,
    "completion_tokens": response.usage.completion_tokens, "parse_mode": parse_mode,
    "agent_root_verified": True, "job_id": os.environ.get("SLURM_JOB_ID"), "run_dir": str(RUN),
}
(RUN / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
job_line = f"F1_ACCEPTANCE_PASS JOB={summary['job_id']} EVENTS_HEAD={event_head} CLAIMS_HEAD={claim_head}\n"
(RUN / "slurm-job-log.txt").write_text(job_line, encoding="utf-8")
print(json.dumps(summary, indent=2), flush=True)
print(job_line.strip(), flush=True)
client.close()
