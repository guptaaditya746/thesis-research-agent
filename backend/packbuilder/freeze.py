"""`freeze`: record a finished domain pack's hashes in `<pack>/FROZEN.json` and print the git tag command.

A pack is frozen only when:
- it loads and passes `evidence pack check` (evidence.cli.pack_check: its types cover the roles its questions' kinds
  need, and every protocol file validates);
- provenance.json has an entry for pack.yaml, words.yaml and, when the pack has one, generator.yaml: the top-level
  keys `pack`, `words`, `generator` (preflight P3), or the legacy `files` map naming the file;
- the `words` entry's `files_read` never names generator.yaml (the words are read from papers, not from the recipe
  the papers were generated from).
FROZEN.json is {pack_sha256 (Pack.sha256), recipe_sha256 (the sha256 of generator.yaml, as Recipe.sha256; null
without one), files: {path in the pack: sha256}}, over every .yaml and .json file of the pack folder and its
protocols/ (FROZEN.json itself left out), each with line ends as LF, as Pack.sha256 reads them. provenance.json is
among them, so anything logged there must be written before freezing. Freezing again with the same files changes
nothing; with other files it is refused. `freeze` never runs git: it prints `git tag ev4-pack-<name>-v1` for the
person who decides to tag.
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from evidence.cli import pack_check
from jsonio import sha256_hex

FROZEN = "FROZEN.json"
ENTRIES = (("pack.yaml", "pack"), ("words.yaml", "words"), ("generator.yaml", "generator"))   # file, provenance key


def _lf_sha(path: Path) -> str:
    return sha256_hex(path.read_bytes().replace(b"\r\n", b"\n"))


def pack_files(pack_dir: Path) -> dict[str, str]:
    """{path relative to the pack (POSIX): sha256} of the pack's .yaml and .json files and its protocols/*.yaml."""
    found = [*pack_dir.glob("*.yaml"), *pack_dir.glob("*.json"), *(pack_dir / "protocols").glob("*.yaml")]
    return {f.relative_to(pack_dir).as_posix(): _lf_sha(f) for f in sorted(found) if f.name != FROZEN}


def _check_provenance(pack_dir: Path) -> None:
    path = pack_dir / "provenance.json"
    if not path.is_file():
        raise ValueError(f"{path} is missing: a pack is frozen only with the provenance of its files")
    prov = json.loads(path.read_text(encoding="utf-8"))
    legacy = prov.get("files") or {}
    for file, key in ENTRIES:
        if (pack_dir / file).exists() and key not in prov and file not in legacy:
            raise ValueError(f"{path}: no provenance entry for {file} (a top-level {key!r} key, or 'files')")
    words = prov.get("words")
    read = words.get("files_read", []) if isinstance(words, dict) else []
    if any(PurePosixPath(str(f).replace("\\", "/")).name == "generator.yaml" for f in read):
        raise ValueError(f"{path}: words.yaml was written from generator.yaml (provenance words.files_read "
                         f"{read}); the words must come from the papers alone")


def freeze(pack_dir: Path) -> dict[str, Any]:
    """Freeze the pack in `pack_dir` (a folder `<root>/<name>`): check it, write FROZEN.json, print the tag command."""
    pack_dir = Path(pack_dir).resolve()
    name, root = pack_dir.name, pack_dir.parent
    try:
        report = pack_check(name, root)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ValueError(f"pack {name!r} does not pass pack check: {exc}") from exc
    _check_provenance(pack_dir)
    recipe = pack_dir / "generator.yaml"
    frozen = {"pack_sha256": report["sha256"], "recipe_sha256": _lf_sha(recipe) if recipe.is_file() else None,
              "files": pack_files(pack_dir)}
    target = pack_dir / FROZEN
    if target.is_file():
        if json.loads(target.read_text(encoding="utf-8")) != frozen:
            raise ValueError(f"{target}: pack {name!r} is already frozen with other files; a changed pack is a new "
                             "version, not a refreeze")
    else:
        target.write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"frozen: {target}")
    print(f"to tag it (not done here): git tag ev4-pack-{name}-v1")
    return frozen
