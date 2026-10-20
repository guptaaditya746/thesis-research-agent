"""Vocabulary snapshots (docs/evidence-system.md Part E): named terms with synonyms, used only by the
proposal flow to say where a frame entry or a protocol term comes from (`ontology` when a snapshot term
matches it, else `invented`). The evidence graph never uses them.

A snapshot `evidence/vocab/<name>.json` is

    {name, sha256, sources: [{name, version, url}],
     terms: [{id, label, synonyms, kind: metric | condition | method, source, higher_is_better?}]}

`sha256` is the digest (jsonio: sorted keys, no whitespace, UTF-8) of the snapshot without
its `sha256` key, so it names the content whatever the file's layout; `load` refuses a file whose
content does not match it.

`build` makes a snapshot offline from local files (no network here or in tests). Its input directory
holds `sources.json`, a list of `{name, version, url, file}`, and one term file per source next to it:

- `*.json`: a list of `{label, synonyms?, kind, higher_is_better?, id?}`;
- `*.csv`: a header `label,synonyms,kind,higher_is_better[,id]`, synonyms separated by `;`,
  higher_is_better `true`, `false` or empty.

A term's id defaults to `<source>:<label as a slug>`; two terms with one id are an error. Terms are
written sorted by id and synonyms in their given order without repeats, so the same downloads give the
same bytes and the same sha256.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..contract import digest

HERE = Path(__file__).resolve().parents[1] / "vocab"   # evidence/vocab: the committed snapshots
Kind = Literal["metric", "condition", "method"]


class VocabError(ValueError):
    pass


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(Strict):
    name: str = Field(min_length=1)
    version: str
    url: str | None = None


class Term(Strict):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    synonyms: tuple[str, ...] = ()
    kind: Kind
    source: str
    higher_is_better: bool | None = None

    @property
    def names(self) -> tuple[str, ...]:
        return (self.label, *self.synonyms)


class Vocabulary(Strict):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    sha256: str
    sources: tuple[Source, ...]
    terms: tuple[Term, ...]

    def ref(self) -> dict[str, str]:
        return {"name": self.name, "sha256": self.sha256}

    def match(self, text: str, kinds: tuple[str, ...] = ("metric", "condition", "method")) -> Term | None:
        """The first term (by id) of one of `kinds` whose label or a synonym is `text` (`normal` form)."""
        key = normal(text)
        return next((t for t in self.terms if t.kind in kinds and any(normal(n) == key for n in t.names)), None)


def normal(text: str) -> str:
    """Case, hyphens, underscores and runs of white space do not tell two names apart."""
    return " ".join(re.sub(r"[-_]", " ", text).casefold().split())


def content_sha256(data: dict[str, Any]) -> str:
    return digest({k: v for k, v in data.items() if k != "sha256"})


def resolve(name_or_path: str | Path) -> Path:
    """A snapshot path, or the name of a committed snapshot (`rag-factuality` -> evidence/vocab/rag-factuality.json)."""
    path = Path(name_or_path)
    if path.suffix == ".json" or path.exists():
        return path
    return HERE / f"{name_or_path}.json"


def load(name_or_path: str | Path) -> Vocabulary:
    path = resolve(name_or_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        vocab = Vocabulary.model_validate(data)   # pydantic's ValidationError is a ValueError
    except (OSError, ValueError) as exc:
        raise VocabError(f"{path}: not a vocabulary snapshot: {exc}") from exc
    actual = content_sha256(data)   # over the file's content as written (absent keys stay absent)
    if actual != vocab.sha256:
        raise VocabError(f"{path}: sha256 {vocab.sha256} does not match its content ({actual})")
    return vocab


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")


def _dedup(names: list[str]) -> list[str]:
    out: list[str] = []
    for n in (" ".join(str(x).split()) for x in names):
        if n and n not in out:
            out.append(n)
    return out


def _rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".json":
        rows = json.loads(path.read_text(encoding="utf-8-sig"))   # -sig: a byte order mark is not content
        if not isinstance(rows, list):
            raise VocabError(f"{path}: a JSON term file is a list of terms")
        return rows
    if path.suffix == ".csv":
        out = []
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                hib = (row.get("higher_is_better") or "").strip().lower()
                if hib not in ("", "true", "false"):
                    raise VocabError(f"{path}: higher_is_better is true, false or empty, not {hib!r}")
                out.append({"label": row["label"], "kind": row["kind"].strip(), "id": (row.get("id") or "").strip() or None,
                            "synonyms": [s for s in (row.get("synonyms") or "").split(";")],
                            "higher_is_better": None if hib == "" else hib == "true"})
        return out
    raise VocabError(f"{path}: term files are .json or .csv")


def build(name: str, source_dir: Path | str) -> dict[str, Any]:
    """A snapshot (as a dict, sha256 filled in) from `source_dir/sources.json` and the term files it lists."""
    root = Path(source_dir)
    sources, terms = [], {}
    where = root / "sources.json"
    try:
        listed = json.loads(where.read_text(encoding="utf-8-sig"))
        for entry in listed:
            where = root / "sources.json"
            source = Source(name=entry["name"], version=str(entry["version"]), url=entry.get("url"))
            sources.append(source)
            where = root / entry["file"]
            for row in _rows(where):
                label = " ".join(str(row["label"]).split())
                term = Term(id=row.get("id") or f"{source.name}:{slug(label)}", label=label,
                            synonyms=tuple(s for s in _dedup(row.get("synonyms") or []) if s != label),
                            kind=row["kind"], source=source.name, higher_is_better=row.get("higher_is_better"))
                if term.id in terms:
                    raise VocabError(f"two terms with the id {term.id!r}")
                terms[term.id] = term
        data = {"name": name, "sha256": "", "sources": [s.model_dump(mode="json") for s in sources],
                "terms": [terms[k].model_dump(mode="json", exclude_none=True) for k in sorted(terms)]}
        data["sha256"] = content_sha256(data)
        Vocabulary.model_validate(data)
    except VocabError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:   # ValidationError is a ValueError
        missing = f"missing key {exc}" if isinstance(exc, KeyError) else str(exc)
        raise VocabError(f"{where}: {missing}") from exc
    return data


def write(data: dict[str, Any], out: Path | str) -> Path:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return path
