"""Drafting helper for `domains/<name>/generator.yaml` (D39): a model proposes the recipe from 5-10 real papers, a
second model quotes the source sentence behind each value, and code checks the rest.

The checks, all deterministic, each a refusal (ValueError) before anything is written:
- 5 to 10 papers;
- no held-out paper (its file stem, or a PMCID in its text, is in `domains/heldout.yaml`); a held-out list with no
  id at all is refused too (the OWED fill must not be skipped silently), unless `allow_empty_heldout`
  (`--allow-empty-heldout`) says so;
- the draft is a valid `Recipe` (a failure goes back to the model once, with the error: `ask` retries);
- every name of a side but the network's reference is invented (the reference and the other conditions are generic
  comparators, such as a placebo or standard care, which real papers always name; the recipe check makes every network
  thing a side name): after `names.clean` it does not occur in any
  source paper; a code of fewer than 3 letters ("R" cleans to the word "r") is looked for as it is written, case-sensitive,
  at token edges;
- every verifier quote is a verbatim substring of a source paper and holds at least 8 non-space characters.
The recipe is written only when all pass, and the log (papers, models, prompt hash, quotes) is merged into
`provenance.json["generator"]` beside whatever other writers put there.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Collection
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, create_model, model_validator

import modelcall
from evidence.names import clean
from evidence.pack import DOMAINS
from evidence.protocol import Strict
from jsonio import sha256_hex
from modelcall import JsonlCache, default_key, load_prompt
from synth.recipe import Recipe

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
HELDOUT = DOMAINS / "heldout.yaml"
PMCID = re.compile(r"PMC\d+")
MIN_PAPERS, MAX_PAPERS = 5, 10
MIN_CODE = 3        # a shorter code is searched raw and case-sensitive, not cleaned
MIN_QUOTE = 8       # non-space characters a verifier quote must hold


def _draft_rules(self: BaseModel) -> BaseModel:
    """The Recipe rules (digits, name clashes, regexes) on the draft, so a failure goes back to the model."""
    Recipe(**self.model_dump(), domain="draft", sha256="")
    return self


# The Recipe fields the model writes: every one but the digest, the domain (the caller's) and the folder.
DraftRecipe = create_model(
    "DraftRecipe", __base__=Strict,
    __validators__={"rules": model_validator(mode="after")(_draft_rules)},
    **{name: (f.annotation, f) for name, f in Recipe.model_fields.items() if name not in ("sha256", "domain", "root")})


class Quote(Strict):
    field: str
    value: str
    quote: str


class Quotes(Strict):
    quotes: list[Quote]


def heldout_ids(path: Path = HELDOUT) -> set[str]:
    """Every id in the held-out file ({benchmark: [ids]})."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {str(i) for ids in data.values() for i in ids or []}


def read_papers(papers: Path, heldout: Collection[str]) -> list[dict[str, str]]:
    """The 5-10 papers of a folder as {file, id, text, sha256}; a held-out paper is refused."""
    files = sorted(p for p in Path(papers).iterdir() if p.is_file() and p.suffix in (".txt", ".md"))
    if not MIN_PAPERS <= len(files) <= MAX_PAPERS:
        raise ValueError(f"drafting needs 5-10 papers, {papers} has {len(files)}")
    out = []
    for f in files:
        raw = f.read_bytes()
        text = raw.decode("utf-8").replace("\r\n", "\n")
        hit = ({f.stem} | set(PMCID.findall(text))) & set(heldout)
        if hit:
            raise ValueError(f"{f.name} is held out ({sorted(hit)[0]} is in heldout.yaml): not a source for drafting")
        out.append({"file": f.name, "id": f.stem, "text": text, "sha256": hashlib.sha256(raw).hexdigest()})
    return out


def _spelled(recipe: Any) -> tuple[list[str], list[str]]:
    """(names to clean-match, short codes to match raw): the labels, synonyms and codes of the sides' names, but
    not the network's reference nor the other conditions (generic comparators). Every network thing is a side name
    (the recipe check), so it is among them."""
    reference = recipe.network.reference if recipe.network else None
    sides = [n for s in recipe.sides.values() for n in s.names if n.label != reference]
    names = [x for n in sides for x in (n.label, n.synonym)]
    codes = [n.code for n in sides if n.code]
    return names + [c for c in codes if len(c) >= MIN_CODE], [c for c in codes if len(c) < MIN_CODE]


def not_invented(recipe: Any, papers: list[dict[str, str]]) -> list[str]:
    """The names of `recipe` that occur in a source paper: after `names.clean`, at word edges; a short code as written."""
    cleaned = [f" {clean(p['text'])} " for p in papers]
    names, short = _spelled(recipe)
    found = {n for n in names if clean(n) and any(f" {clean(n)} " in c for c in cleaned)}
    found |= {c for c in short if any(re.search(rf"(?<![A-Za-z0-9]){re.escape(c)}(?![A-Za-z0-9])", p["text"])
                                      for p in papers)}
    return sorted(found)


def draft(domain: str, papers: Path, *, model: Any, verify_model: Any, cache: Path, root: Path = DOMAINS,
          heldout: Collection[str] | None = None, allow_empty_heldout: bool = False) -> Path:
    """Write `root/<domain>/generator.yaml` drafted from the papers in `papers` and log it in provenance.json."""
    root = Path(root)
    target = root / domain / "generator.yaml"
    if target.exists():
        raise ValueError(f"{target} exists: a drafted recipe never replaces a recipe already there")
    heldout = heldout_ids() if heldout is None else heldout
    if not heldout and not allow_empty_heldout:
        raise ValueError(f"the held-out id list is empty, so no paper could be refused as held out: fill {HELDOUT} "
                         "first (plan 2 Task 18 Step 3), or pass --allow-empty-heldout to draft without the check")
    sources = read_papers(papers, heldout)
    calls = JsonlCache(cache)
    settings = modelcall.CallSettings()
    gen_prompt = load_prompt(PROMPT_DIR / "draft-generator-v1.txt", DraftRecipe)
    check_prompt = load_prompt(PROMPT_DIR / "draft-check-v1.txt", Quotes)

    text = "\n\n".join(f"=== {p['id']} ===\n{p['text']}" for p in sources)
    recipe = modelcall.ask_sync(gen_prompt, text, model=model, settings=settings, cache=calls,
                                key=default_key(gen_prompt, text, model, settings)).output
    reused = not_invented(recipe, sources)
    if reused:
        raise ValueError(f"names must be invented, but these occur in a source paper: {reused}")

    data = recipe.model_dump(mode="json")
    check_input = f"{json.dumps(data, indent=2, ensure_ascii=False)}\n\n{text}"
    quotes = modelcall.ask_sync(check_prompt, check_input, model=verify_model, settings=settings, cache=calls,
                                key=default_key(check_prompt, check_input, verify_model, settings)).output.quotes
    if not quotes:
        raise ValueError("the verifier quoted no source sentence")
    missing = [q.quote for q in quotes if len("".join(q.quote.split())) < MIN_QUOTE
               or not any(q.quote in p["text"] for p in sources)]
    if missing:
        raise ValueError(f"verifier quotes that are not verbatim in any source paper: {missing}")

    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120)
    Recipe(**yaml.safe_load(body), domain=domain, sha256=sha256_hex(body.encode("utf-8")), root=root)  # reads back valid
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8", newline="\n")
    _log(root / domain / "provenance.json", {
        "papers": [{k: p[k] for k in ("file", "sha256", "id")} for p in sources],
        "model": modelcall.model_name(model), "verify_model": modelcall.model_name(verify_model),
        "prompt_sha256": gen_prompt.sha256, "check_prompt_sha256": check_prompt.sha256,
        "calls": Path(cache).as_posix(), "quotes": [q.model_dump() for q in quotes]})
    return target


def _log(path: Path, entry: dict[str, Any]) -> None:
    """Merge `entry` into provenance.json["generator"]; every other key stays."""
    prov = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    prov["generator"] = {**prov.get("generator", {}), **entry}
    path.write_text(json.dumps(prov, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
