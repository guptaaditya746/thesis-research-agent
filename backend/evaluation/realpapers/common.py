"""What every real-paper set shares: one reader of a run's items (F52), the run's name groups and name matching, the
corpus manifest reader and writer, the JSON file writer, `ratio`, and the real.json / real.md writer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evidence.contract import Item
from evidence.names import NameGroups, clean
from evidence.rundir import NAMES_FILE, RunDir
from jsonio import sha256_hex

JSON_FILE = "real.json"
MD_FILE = "real.md"
MANIFEST_FILE = "manifest.json"
PAPERS_DIR = "papers"


def ratio(num: float, den: float) -> float | None:
    """num / den; None when den is 0 (a share of nothing)."""
    return num / den if den else None


def read_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path | str, data: Any, *, ascii_only: bool = False) -> None:
    """`data` as JSON (indent 1, one trailing newline, LF). `ascii_only` escapes non-ASCII characters (the files
    some writers made so before; kept so their bytes stay the same)."""
    Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=ascii_only) + "\n", encoding="utf-8", newline="\n")


def read_manifest(corpus: Path | str) -> dict[str, Any]:
    """The corpus's manifest.json: {"corpus_id", "papers": [{"id", "file", "sha256"}]}."""
    return read_json(Path(corpus) / MANIFEST_FILE)


def manifest_ids(corpus: Path | str | None) -> list[str] | None:
    """The paper ids of the corpus's manifest, in manifest order; None when there is no corpus or no manifest."""
    if corpus is None or not (Path(corpus) / MANIFEST_FILE).is_file():
        return None
    return [str(p["id"]) for p in read_manifest(corpus)["papers"]]


def add_paper(corpus: Path, paper_id: str, data: bytes) -> dict[str, str]:
    """Write `papers/<paper_id>.md` of a corpus being built; returns its manifest entry (id, file, sha256)."""
    file = f"{PAPERS_DIR}/{paper_id}.md"
    (Path(corpus) / PAPERS_DIR).mkdir(parents=True, exist_ok=True)
    (Path(corpus) / file).write_bytes(data)
    return {"id": paper_id, "file": file, "sha256": sha256_hex(data)}


def write_manifest(corpus: Path, corpus_id: str, papers: list[dict[str, Any]], *, ascii_only: bool = False) -> None:
    write_json(Path(corpus) / MANIFEST_FILE, {"corpus_id": corpus_id, "papers": papers}, ascii_only=ascii_only)


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
    write_json(js, result)
    md.write_text(render(result, title), encoding="utf-8", newline="\n")
    return js, md
