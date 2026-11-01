"""The arXiv edit test (spec 6.12 item 3): change one thing in one real paper and check that the run follows the text.

An edit replaces the one occurrence of `find` in a paper with `replace`: a number (`number`), a compared thing's name
(`name`), or a limitation sentence deleted (`limitation`, `replace` empty). `apply` writes one corpus per edit;
the engine runs on the original corpus and on every edited one (`evidence run --run-id <edit id>`); `check` compares
the original run with the edited one in three parts: the right item changed (`item`), its links still hold (`link`),
and the answer changed as it should (`answer`). This shows that the system follows the text, not that it is right.

Where the edit sits in a run's paper is read from the original run's span selectors (prefix + exact + suffix is a
piece of the paper, and `find` occurs once in it), so `check` needs the two run directories only. An item belongs to
paper P when a span's file is `papers/<P>.md` (the layout `evidence fetch` and every corpus writer use).

The `limitation` check reads plan 2's `limitations` answer (`entries: [{thing, category, papers, items}]`): an item
listed in an entry is a limitation item. No rag protocol has that kind yet (preflight F25), so the frozen arXiv edit
set holds number and name edits only.
"""
from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import model_validator

from evidence.contract import Item
from evidence.extractors.numreader import read_numbers
from evidence.pack import Role, RoleMap, load_pack
from evidence.protocol import DEFAULT_PACK, Strict
from evidence.rundir import ANSWER_FILE, PROTOCOL_FILE, RUN_FILE, RunDir
from jsonio import sha256_hex

from .common import items_of

EDIT_FILE = "edit.json"     # the edit an edited corpus was made with (the engine reads manifest.json and papers/ only)
PARTS = ("item", "link", "answer")
EditKind = Literal["number", "name", "limitation"]


class EditError(ValueError):
    pass


class Edit(Strict):
    id: str
    paper: str
    kind: EditKind
    find: str
    replace: str

    @model_validator(mode="after")
    def _limitation_deletes(self) -> Edit:
        if not self.find:
            raise ValueError(f"edit {self.id}: find is empty")
        if self.kind == "limitation" and self.replace:
            raise ValueError(f"edit {self.id}: a limitation edit deletes its sentence (replace must be empty)")
        return self


def load_edits(path: Path) -> list[Edit]:
    """The edits of an edits file (`edits: [{id, paper, kind, find, replace}, ...]`); ids must be unique."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    edits = [Edit.model_validate(e) for e in data.get("edits") or []]
    ids = [e.id for e in edits]
    twice = sorted({i for i in ids if ids.count(i) > 1})
    if twice:
        raise ValueError(f"{path}: edit ids used more than once: {', '.join(twice)}")
    return edits


# --- apply ----------------------------------------------------------------------------------------------------


def apply(corpus: Path, edit: Edit, out: Path) -> Path:
    """The corpus `out/<edit id>`: a copy of `corpus` where only paper `edit.paper` changes (its one `find` becomes
    `replace`) and its manifest sha256 is updated; `edit.json` records the edit. EditError naming the edit when the
    paper is not in the corpus or `find` does not occur exactly once in it."""
    corpus, target = Path(corpus), Path(out) / edit.id
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    entry = next((p for p in manifest["papers"] if str(p["id"]) == edit.paper), None)
    if entry is None:
        raise EditError(f"edit {edit.id}: no paper {edit.paper!r} in {corpus}")
    text = (corpus / entry["file"]).read_bytes().decode("utf-8")
    count = text.count(edit.find)
    if count != 1:
        raise EditError(f"edit {edit.id}: {edit.find!r} occurs {count} times in paper {edit.paper} "
                        "(it must occur exactly once)")
    if target.exists():
        raise EditError(f"edit {edit.id}: {target} exists already")
    shutil.copytree(corpus, target)
    data = text.replace(edit.find, edit.replace).encode("utf-8")
    (target / entry["file"]).write_bytes(data)
    entry["sha256"] = sha256_hex(data)
    (target / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n",
                                          encoding="utf-8", newline="\n")
    (target / EDIT_FILE).write_text(json.dumps(edit.model_dump(), indent=1, ensure_ascii=False) + "\n",
                                    encoding="utf-8", newline="\n")
    return target


# --- reading two runs -----------------------------------------------------------------------------------------


def _in_paper(item: Item, paper: str) -> bool:
    return any(s.selector.get("file") == f"papers/{paper}.md" for s in item.spans)


def _edit_at(items: list[Item], paper: str, find: str) -> int | None:
    """The offset of `find` in the paper, read from a span selector whose prefix + exact + suffix holds it (find
    occurs once in the paper, so any such window places it); None when no span of the paper reaches it."""
    for item in items:
        for s in item.spans:
            sel = s.selector
            if sel.get("file") != f"papers/{paper}.md":
                continue
            prefix = sel.get("prefix") or ""
            window = prefix + (sel.get("exact") or "") + (sel.get("suffix") or "")
            hit = window.find(find)
            if hit >= 0:
                return int(sel["start"]) - len(prefix) + hit
    return None


def _covers(item: Item, start: int, end: int) -> bool:
    return any(s.selector["start"] <= start and s.selector["end"] >= end for s in item.spans)


def _overlaps(item: Item, start: int, end: int) -> bool:
    return any(s.selector["start"] < end and s.selector["end"] > start for s in item.spans)


def _key(item: Item) -> tuple[str, str]:
    """What an item says, without where: its type and fields (ids change when offsets shift)."""
    return item.evidence_type, json.dumps(item.fields, sort_keys=True, ensure_ascii=False)


def _norm(name: Any) -> str:
    return " ".join(str(name).split()).casefold()


def _pack_roles(run: Path) -> RoleMap:
    """The role map of the run's domain pack (protocol.yaml's `domain`, from run.json's `domains` folder)."""
    data = yaml.safe_load((Path(run) / PROTOCOL_FILE).read_bytes().decode("utf-8")) or {}
    settings = (RunDir(run).try_json(RUN_FILE) or {}).get("settings") or {}
    kwargs = {"root": Path(settings["domains"])} if settings.get("domains") else {}
    return RoleMap(load_pack(data.get("domain", DEFAULT_PACK), **kwargs))


def _entries(answer: Any, paper: str) -> Iterator[dict[str, Any]]:
    """Every answer entry about `paper`: a mapping whose `document` is the paper (not searched inside)."""
    if isinstance(answer, dict):
        if answer.get("document") == paper:
            yield answer
            return
        for v in answer.values():
            yield from _entries(v, paper)
    elif isinstance(answer, list):
        for v in answer:
            yield from _entries(v, paper)


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _canon(value: Any, by_id: dict[str, Item]) -> Any:
    """`value` with every item id replaced by what the item says (_key), so two runs compare by content."""
    if isinstance(value, str):
        return list(_key(by_id[value])) if value in by_id else value
    if isinstance(value, dict):
        return {k: _canon(v, by_id) for k, v in value.items()}
    if isinstance(value, list):
        return [_canon(v, by_id) for v in value]
    return value


class _Run:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.items = items_of(root)
        self.by_id = {i.item_id: i for i in self.items}
        self.answer = RunDir(root).json(ANSWER_FILE)

    def of(self, paper: str) -> list[Item]:
        return [i for i in self.items if _in_paper(i, paper)]

    def entries(self, paper: str) -> list[Any]:
        return [_canon(e, self.by_id) for e in _entries(self.answer, paper)]

    def limitation_ids(self) -> set[str]:
        """The items plan 2's `limitations` answer lists (its entries' `items`)."""
        entries = self.answer.get("entries") if isinstance(self.answer, dict) else None
        return {i for e in entries or [] if isinstance(e, dict) for i in e.get("items") or []}


# --- check ----------------------------------------------------------------------------------------------------


def _same_value(value: Any, read: float) -> bool:
    """The item's value is the number read (or that number as a fraction: 71.0 under a % header is 0.71)."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    return any(abs(value - want) <= 1e-9 * max(1.0, abs(want)) for want in (read, round(read / 100, 6)))


def _value_item(items: list[Item], start: int, end: int, number: str) -> Item | None:
    """The item with a span over [start, end) whose `value` is the number `number` reads as."""
    numbers = read_numbers(number)
    if not numbers:
        return None
    return next((i for i in items if _covers(i, start, end) and _same_value(i.fields.get("value"), numbers[0].value)),
                None)


def _check_number(orig: _Run, new: _Run, edit: Edit) -> dict[str, bool]:
    at = _edit_at(orig.of(edit.paper), edit.paper, edit.find)
    item = link = False
    if at is not None:
        before = _value_item(orig.of(edit.paper), at, at + len(edit.find), edit.find)
        after = _value_item(new.of(edit.paper), at, at + len(edit.replace), edit.replace)
        item = after is not None
        if before is not None and after is not None and set(before.links) == set(after.links):
            link = all(target in orig.by_id and after.links[k] in new.by_id
                       and _key(orig.by_id[target]) == _key(new.by_id[after.links[k]])
                       for k, target in before.links.items())
    return {"item": item, "link": link, "answer": orig.entries(edit.paper) != new.entries(edit.paper)}


def _named(run: _Run, roles: RoleMap, paper: str, name: str) -> set[str]:
    """The ids of the paper's compared-thing items whose name is `name` (case and spacing aside)."""
    compared = set(roles.types_of(Role.COMPARED_THING))
    found = set()
    for item in run.of(paper):
        field = roles.field_or_none(item.evidence_type, "name") if item.evidence_type in compared else None
        if field and _norm(item.fields.get(field, "")) == _norm(name):
            found.add(item.item_id)
    return found


def _check_name(orig: _Run, new: _Run, edit: Edit) -> dict[str, bool]:
    roles = _pack_roles(new.root)
    old_ids, new_ids = _named(orig, roles, edit.paper, edit.find), _named(new, roles, edit.paper, edit.replace)
    item = bool(new_ids) and not _named(new, roles, edit.paper, edit.find)
    linkers = [(i, k) for i in orig.of(edit.paper) for k, target in i.links.items() if target in old_ids]
    link = bool(linkers) and bool(new_ids) and all(
        any(_key(j) == _key(i) and j.links.get(k) in new_ids for j in new.of(edit.paper)) for i, k in linkers)
    said = {s for e in _entries(new.answer, edit.paper) for s in _strings(e)}
    answer = bool(said & new_ids) or any(_norm(s) == _norm(edit.replace) for s in said)
    return {"item": item, "link": link, "answer": answer}


def _limitation_count(run: _Run, paper: str) -> int:
    return sum(1 for i in run.limitation_ids() if i in run.by_id and _in_paper(run.by_id[i], paper))


def _check_limitation(orig: _Run, new: _Run, edit: Edit) -> dict[str, bool]:
    at = _edit_at(orig.of(edit.paper), edit.paper, edit.find)
    listed = orig.limitation_ids()
    gone = None if at is None else next(
        (i for i in orig.of(edit.paper) if i.item_id in listed and _overlaps(i, at, at + len(edit.find))), None)
    if gone is None:
        return {"item": False, "link": False, "answer": False}
    still = {_key(new.by_id[i]) for i in new.limitation_ids() if i in new.by_id and _in_paper(new.by_id[i], edit.paper)}
    linked = any(t == gone.item_id or (t in new.by_id and _key(new.by_id[t]) == _key(gone))
                 for i in new.items for t in i.links.values())
    return {"item": _key(gone) not in still, "link": not linked,
            "answer": _limitation_count(new, edit.paper) == _limitation_count(orig, edit.paper) - 1}


CHECKS = {"number": _check_number, "name": _check_name, "limitation": _check_limitation}


def check(original: Path, edited: Path, edit: Edit) -> dict[str, bool]:
    """Did the edited run follow edit `edit`? Per part (see the module docstring and spec 6.12):

    - number: an item whose span covers the new text has the new value (read_numbers); the original item's links
      point to items that say the same as before; the answer entry for the paper differs (item ids compared by
      what they say).
    - name: a compared-thing item named `replace` is in the paper and none named `find`; every item that linked to
      the old one links to a new one (at least one did); the paper's answer entry names `replace` (or its item).
    - limitation: the listed limitation item over the deleted sentence is gone; no item links to it; the paper's
      limitation count in the `limitations` answer drops by 1. All False when the original run had no such item.
    """
    return CHECKS[edit.kind](_Run(Path(original)), _Run(Path(edited)), edit)


def summary(results: dict[str, dict[str, bool]], kinds: dict[str, str]) -> dict[str, Any]:
    """The share of edits carried through per part and over all three (`all`), overall and per edit kind."""
    def shares(ids: list[str]) -> dict[str, float | None]:
        n = len(ids)
        out: dict[str, float | None] = {p: (sum(results[i][p] for i in ids) / n if n else None) for p in PARTS}
        out["all"] = sum(all(results[i].values()) for i in ids) / n if n else None
        return out
    by_kind = {k: {"edits": len(ids), **shares(ids)}
               for k in ("number", "name", "limitation") if (ids := [i for i in results if kinds[i] == k])}
    return {"carried": shares(list(results)), "by_kind": by_kind}


def report(original: Path, runs: Path, edits: list[Edit]) -> dict[str, Any]:
    """real.json of the edit test: every edit checked against `runs/<edit id>` (the run of its edited corpus);
    edits without a run are listed under `missing` and left out of the shares."""
    results, missing = {}, []
    for e in edits:
        run = Path(runs) / e.id
        if not RunDir(run).complete:
            missing.append(e.id)
            continue
        results[e.id] = check(original, run, e)
    s = summary(results, {e.id: e.kind for e in edits})
    by_edit = {e.id: {"kind": e.kind, "paper": e.paper, **results[e.id]} for e in edits if e.id in results}
    return {"edits": len(edits), "checked": len(results), "missing": missing, "carried": s["carried"],
            "by_kind": s["by_kind"], "by_edit": by_edit,
            "notes": ["Shows that the system follows the text, not that it is right (spec 6.12 item 3).",
                      "An edit is carried through when its item, link and answer parts all hold (`all`)."]}
