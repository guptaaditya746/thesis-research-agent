"""What every real-paper check shares: one reader of a run's items (F52), the run's name groups and name matching,
and the real.json / real.md writer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evidence.contract import Item
from evidence.names import NameGroups, clean
from evidence.rundir import NAMES_FILE, RunDir

JSON_FILE = "real.json"
MD_FILE = "real.md"


def items_of(run_dir: Path | str) -> list[Item]:
    """The run's evidence items, read through RunDir (its pack registered first); the scorers never parse
    evidence.jsonl themselves."""
    return RunDir(run_dir).items()


def name_groups(run_dir: Path | str) -> NameGroups | None:
    """The run's name groups (names.json); None for a run without names on."""
    path = Path(run_dir) / NAMES_FILE
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return NameGroups({k: list(v) for k, v in data.get("groups", {}).items()}, [], [])


def same_name(name: str | None, wanted: str, groups: NameGroups | None) -> bool:
    """`name` is `wanted`: the same cleaned name, or the same name group of the run."""
    if name is None:
        return False
    if clean(name) == clean(wanted):
        return True
    if groups is None:
        return False
    group = groups.group_of(name)
    return group is not None and group == groups.group_of(wanted)


def _cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3g}"
    return str(value)


def _table(rows: dict[str, dict[str, Any]]) -> list[str]:
    """A Markdown table: one row per key of `rows`, one column per key of its values (first-seen order)."""
    columns = list(dict.fromkeys(k for row in rows.values() for k in row))
    lines = ["| | " + " | ".join(columns) + " |", "|---|" + "---|" * len(columns)]
    lines += [f"| {name} | " + " | ".join(_cell(row.get(c)) for c in columns) + " |" for name, row in rows.items()]
    return lines


def render(result: dict[str, Any], title: str) -> str:
    """real.md: the title line, then each top-level entry of `result`: a scalar as a bullet, a mapping of mappings as
    a table under its key as a heading, a list of strings as bullets under its key (`notes` last), anything else as
    JSON."""
    lines = [f"# real-paper check: {title} (not a synthetic score)", ""]
    scalars = {k: v for k, v in result.items() if not isinstance(v, (dict, list))}
    lines += [f"- {k}: {_cell(v)}" for k, v in scalars.items()]
    rest = [k for k in result if k not in scalars and k != "notes"] + (["notes"] if "notes" in result else [])
    for key in rest:
        value = result[key]
        lines += ["", f"## {key}", ""]
        if isinstance(value, dict) and value and all(isinstance(v, dict) for v in value.values()):
            lines += _table(value)
        elif isinstance(value, list) and all(isinstance(v, str) for v in value):
            lines += [f"- {v}" for v in value]
        else:
            lines += ["```json", json.dumps(value, indent=1, ensure_ascii=False), "```"]
    return "\n".join(lines) + "\n"


def write_real(result: dict[str, Any], out: Path, title: str) -> tuple[Path, Path]:
    """Write `out/real.json` (the result) and `out/real.md`, whose first line is
    `# real-paper check: <title> (not a synthetic score)`; returns both paths."""
    out.mkdir(parents=True, exist_ok=True)
    js, md = out / JSON_FILE, out / MD_FILE
    js.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    md.write_text(render(result, title), encoding="utf-8", newline="\n")
    return js, md
