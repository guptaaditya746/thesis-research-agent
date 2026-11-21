"""Field packs (what exists in a field: kinds of things, relations, words) and genre packs (what a paper looks like:
template, writing rules). Code reads packs; it never branches on a field or genre name."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PACKS = Path(__file__).resolve().parent / "packs"


@dataclass
class Field:
    raw: dict[str, Any]

    name = property(lambda self: self.raw["field"])
    words = property(lambda self: self.raw["words"])
    kinds = property(lambda self: self.raw["kinds"])
    relations = property(lambda self: self.raw["relations"])
    subject_kinds = property(lambda self: self.raw["subject_kinds"])
    order_attr = property(lambda self: self.raw.get("order_attr"))
    conflict_pairs = property(lambda self: [tuple(p) for p in self.raw.get("conflict_pairs", [])])
    questions = property(lambda self: self.raw["questions"])

    def rel_words(self, r: str) -> str:
        return self.relations[r]["words"]


@dataclass
class Genre:
    raw: dict[str, Any]
    folder: Path

    name = property(lambda self: self.raw["genre"])


def field(name: str) -> Field:
    return Field(json.loads((PACKS / "fields" / f"{name}.json").read_text(encoding="utf-8")))


def genre(name: str) -> Genre:
    folder = PACKS / "genres" / name
    return Genre(json.loads((folder / "genre.json").read_text(encoding="utf-8")), folder)


def fill(text: str, values: dict[str, Any]) -> str:
    for k, v in values.items():
        text = text.replace("{" + k + "}", str(v))
    return text


def render_template(f: Field, g: Genre, pages: int, dest: Path) -> Path:
    """Genre template + guidelines with the field's words and the page length filled in -> dest (PaperOrchestra's
    --template_dir). {TITLE} stays for PaperOrchestra."""
    lo, hi = g.raw["words_per_page"]
    values = {k.upper(): v for k, v in f.words.items()} | {
        "PAGES": pages, "WORDS_LO": pages * lo, "WORDS_HI": pages * hi,
        "MAX_MENTIONS": g.raw.get("max_mentions_per_fact", 3)}
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("template.md", "guidelines.md"):
        (dest / name).write_text(fill((g.folder / name).read_text(encoding="utf-8"), values), encoding="utf-8")
    shutil.copy(g.folder / "genre.json", dest / "genre.json")
    return dest
