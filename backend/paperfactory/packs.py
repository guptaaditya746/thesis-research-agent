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

    def word(self, key: str) -> str:
        """A field word for prompts and headings ("words" in the pack). A missing key is a clear error."""
        try:
            return self.raw["words"][key]
        except KeyError:
            raise KeyError(f"field pack {self.raw.get('field')!r} has no words.{key}") from None

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


def word_values(f: Field) -> dict[str, str]:
    """{KEY: word, KEY_CAP: Word} for every field word, for {PLACEHOLDERS} in genre texts."""
    return {k.upper(): v for k, v in f.words.items()} | {k.upper() + "_CAP": v[:1].upper() + v[1:]
                                                          for k, v in f.words.items()}


def render_template(f: Field, g: Genre, pages: int, dest: Path) -> Path:
    """Genre template + guidelines with the field's words and the page length filled in -> dest (PaperOrchestra's
    --template_dir). {TITLE} stays for PaperOrchestra."""
    lo, hi = g.raw["words_per_page"]
    values = word_values(f) | {
        "PAGES": pages, "WORDS_LO": pages * lo, "WORDS_HI": pages * hi,
        "MAX_MENTIONS": g.raw.get("max_mentions_per_fact", 3), "PAPER_TYPE": f.raw["words"].get("paper_kind", ""),
        "MIN_TABLES": g.raw.get("min_tables", 0), "STYLE_CARD": ""}
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("template.md", "guidelines.md"):
        (dest / name).write_text(fill((g.folder / name).read_text(encoding="utf-8"), values), encoding="utf-8")
    shutil.copy(g.folder / "genre.json", dest / "genre.json")
    return dest


def render_paper_template(f: Field, g: Genre, card: dict[str, Any], dest: Path) -> Path:
    """One paper's own template folder (22 Nov 2026): the card's template (genre folder templates/<name>.md), the
    genre guidelines with the card's paper type, length and style lines filled in, and genre.json."""
    from paperfactory import style   # style imports this module
    lo, hi = g.raw["words_per_page"]
    pages = card.get("pages") or 6
    values = word_values(f) | {
        "PAGES": pages, "WORDS_LO": pages * lo, "WORDS_HI": pages * hi, "PAPER_TYPE": card["paper_kind"],
        "MAX_MENTIONS": g.raw.get("max_mentions_per_fact", 3), "MIN_TABLES": g.raw.get("min_tables", 0),
        "STYLE_CARD": style.card_text(card, g.raw.get("banned_phrases", []))}
    dest.mkdir(parents=True, exist_ok=True)
    tmpl = g.folder / "templates" / f"{card['template']}.md"
    (dest / "template.md").write_text(fill(tmpl.read_text(encoding="utf-8"), values), encoding="utf-8")
    (dest / "guidelines.md").write_text(fill((g.folder / "guidelines.md").read_text(encoding="utf-8"), values),
                                        encoding="utf-8")
    shutil.copy(g.folder / "genre.json", dest / "genre.json")
    return dest


def relation_table(f: Field) -> str:
    """D5: one Markdown table per field: relation, words, definition, allowed kinds, likely confusions."""
    rows = [f"### {f.name} ({f.raw.get('status', 'tested')})", "",
            "| Relation | Words | Definition | Subject kinds | Object kinds | Easily confused with |",
            "|---|---|---|---|---|---|"]
    rows += [f"| {r} | {d['words']} | {d['meaning']} | {', '.join(f.subject_kinds)} | {', '.join(d['object_kinds'])} | "
             f"{', '.join(d.get('confusable_with', [])) or '-'} |" for r, d in f.relations.items()]
    return "\n".join(rows + ["", f.raw.get("confusable_note", ""), ""])

