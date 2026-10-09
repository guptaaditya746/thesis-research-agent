from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parents[2] / "final-final-frontend/UI/files/harness/corpus_data/outlines"
files = sorted(root.glob("*.md"))


def timed(label: str, command: list[str]) -> tuple[float, str]:
    start = time.perf_counter()
    result = subprocess.run(command, text=True, capture_output=True, check=True)
    return time.perf_counter() - start, result.stdout


paths = [str(p) for p in files]
t1, matches = timed("grep -il", ["grep", "-il", "retrieval", *paths])
t2, count = timed("grep evaluate", ["bash", "-c", "grep -n -i evaluate \"$@\" | wc -l", "bash", *paths])
start = time.perf_counter()
pattern = re.compile(r"\bevaluat\w*", re.IGNORECASE)
regex_matches = sum(len(pattern.findall(path.read_text(encoding="utf-8"))) for path in files)
t3 = time.perf_counter() - start
print(f"files={len(files)} bytes={sum(p.stat().st_size for p in files)}")
print(f'grep -il retrieval: {t1:.6f}s; matching_files={len(matches.splitlines())}')
print(f'grep -n -i evaluate | wc -l: {t2:.6f}s; matching_lines={count.strip()};')
print(f'python regex \u005cevaluat\u005cw*: {t3:.6f}s; matches={regex_matches}')
