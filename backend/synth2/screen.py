"""Source screen: which real source papers still report their own retrieval-vs-no-retrieval result after the
template cleanup (templedit drops only text that names the no-retrieval side with CONTROL_WORDS)?

A model (prompt `screen-v1.md`) reads each cleaned source and quotes every such result with its direction; code
here checks the answers (known paper, each answered once, verbatim quote, allowed direction). A study must not
get a source whose leftover result points another way than the study's planted claim (`conflicts`).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from synth2.templedit import _clean_block

DIRECTIONS = ("helps", "hurts", "no_effect")


def cleaned(text: str) -> str:
    """The source as a template paper leaves it: every no-retrieval sentence, table row or heading removed."""
    out = []
    for block in re.split(r"\n\s*\n", text):
        new = _clean_block(block.strip())
        if new is None:
            out.append(block)
        elif new:
            out.append(new)
    return "\n\n".join(out)


def prepare(ids: list[str], full: Path, out: Path) -> list[str]:
    """Write <out>/<id>.md, the cleaned copy of <full>/<id>.md, for the screen reader."""
    out.mkdir(parents=True, exist_ok=True)
    for pid in ids:
        (out / f"{pid}.md").write_text(cleaned((full / f"{pid}.md").read_text(encoding="utf-8")), encoding="utf-8")
    return ids


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def check_screen(answers: list, texts: dict[str, str]) -> tuple[dict[str, list[str]], list[str]]:
    """({paper: [direction per quoted result]}, problems). A paper with a problem is left out of the results."""
    problems, results, seen = [], {}, {}
    flat = {pid: _squash(t) for pid, t in texts.items()}
    for a in answers:
        pid = a.get("paper") if isinstance(a, dict) else None
        seen[pid] = seen.get(pid, 0) + 1
        if pid not in texts:
            problems.append(f"unknown paper {pid!r}")
            continue
        if not isinstance(a.get("results"), list):
            problems.append(f"{pid}: no results list")
            continue
        dirs, bad = [], False
        for r in a["results"]:
            if not isinstance(r, dict) or r.get("direction") not in DIRECTIONS:
                problems.append(f"{pid}: direction {r.get('direction') if isinstance(r, dict) else r!r} "
                                f"is not one of {DIRECTIONS}")
                bad = True
            elif _squash(str(r.get("quote", ""))) not in flat[pid]:
                problems.append(f"{pid}: quote not in paper: {str(r.get('quote'))[:60]!r}")
                bad = True
            else:
                dirs.append(r["direction"])
        if not bad:
            results[pid] = dirs
    for pid, n in seen.items():
        if pid in texts and n > 1:
            problems.append(f"{pid} answered {n} times")
            results.pop(pid, None)
    problems += [f"{pid} not answered" for pid in texts if pid not in seen]
    return results, problems


def check_files(files: list[Path], texts_dir: Path) -> tuple[dict[str, list[str]], list[str]]:
    """check_screen over the JSON arrays in `files`, against the cleaned copies in `texts_dir`."""
    answers = [a for f in files for a in json.loads(f.read_text(encoding="utf-8-sig"))]
    texts = {p.stem: p.read_text(encoding="utf-8") for p in texts_dir.glob("*.md")}
    return check_screen(answers, texts)


def _level(block: str) -> int:
    """Heading level of a block ('## X' -> 2); 0 when the block is not a heading."""
    m = re.match(r"(#+)\s", block.lstrip())
    return len(m.group(1)) if m else 0


def _section(parts: list[str], i: int) -> list[int] | None:
    """Block places of the section holding block i: from its nearest heading up to the next heading of the same
    or a higher level. None when there is no such heading, or it is the title (level 1) or the abstract."""
    j = next((k for k in range(i, -1, -2) if _level(parts[k])), None)
    if j is None or _level(parts[j]) == 1 or "abstract" in parts[j].lower():
        return None
    end = next((k for k in range(j + 2, len(parts), 2) if 0 < _level(parts[k]) <= _level(parts[j])), len(parts))
    return list(range(j, end, 2))


def strip_results(text: str, quotes: list[str], section: bool = False) -> tuple[str, list[str]]:
    """The text without each quoted result: the table row that holds the quote, or else the whole paragraph that
    holds it (the sentences around a result usually restate it). With `section`, the whole section that holds
    the quote goes instead (`_section`; the paragraph in the abstract or before any heading). Returns (text,
    quotes not found in any one paragraph or row). Spaces and line breaks may differ between quote and text."""
    parts = re.split(r"(\n\s*\n)", text)        # blocks at even places, the blank-line separators at odd ones
    drop_block, drop_line, missing = set(), set(), []
    for q in quotes:
        sq = _squash(q)
        hit = False
        for i in range(0, len(parts), 2):
            if sq not in _squash(parts[i]):
                continue
            lines = parts[i].split("\n")
            rows = [k for k, ln in enumerate(lines) if ln.lstrip().startswith("|") and sq in _squash(ln)]
            whole = _section(parts, i) if section else None
            if whole:
                drop_block.update(whole)
            elif rows and rows[0] >= 2:
                drop_line.add((i, rows[0]))
            else:
                drop_block.add(i)
            hit = True
            break
        if not hit:
            missing.append(q)
    for i, k in drop_line:
        if i not in drop_block:
            parts[i] = "\n".join(ln for j, ln in enumerate(parts[i].split("\n"))
                                 if (i, j) not in drop_line)
    out = [p for i, p in enumerate(parts)
           if not (i % 2 == 0 and i in drop_block) and not (i % 2 == 1 and i - 1 in drop_block)]
    return "".join(out), missing


def write_screened(full: Path, answer_files: list[Path], out: Path, section: bool = False) -> dict[str, dict]:
    """Copy every <full>/*.md to <out>, with the results quoted in the screen answers stripped
    (`strip_results`). Returns {paper: {"removed": quotes found, "missing": quotes not found}} for quoted papers."""
    quotes: dict[str, list[str]] = {}
    for f in answer_files:
        for a in json.loads(f.read_text(encoding="utf-8-sig")):
            quotes.setdefault(a["paper"], []).extend(r["quote"] for r in a.get("results", []))
    out.mkdir(parents=True, exist_ok=True)
    done = {}
    for p in sorted(full.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        if quotes.get(p.stem):
            text, missing = strip_results(text, quotes[p.stem], section)
            done[p.stem] = {"removed": len(quotes[p.stem]) - len(missing), "missing": missing}
        (out / p.name).write_text(text, encoding="utf-8")
    return done


def conflicts(directions: list[str], claim: str) -> bool:
    """True when the source keeps a retrieval-vs-no-retrieval result whose direction differs from the claim."""
    return any(d != claim for d in directions)
