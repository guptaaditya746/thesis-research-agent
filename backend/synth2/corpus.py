"""A corpus on disk: the papers and manifest a tested system may read, and beside them the truth it may not.

The answer key is what the written studies support (`pooled`). Whether that equals the planted law is stored
separately as `key_matches_law`.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from jsonio import canonical_bytes, sha256_hex, write_json_atomic, write_text_atomic
from synth2.conclude import lumped, pooled, vote
from synth2.recipe import Recipe, load_recipe
from synth2.world import LAW_KINDS, Law, Study, direction, draw_law, draw_studies
from synth2.write import TEXT_LEVELS, missing_facts, write_paper

GENERATOR = "synth2"
VERSION = 1
PACKAGE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    domain: str
    seed: int
    studies: int
    law_kind: str
    text_level: str
    exact: bool = False
    noise_seed: int = 0
    untested: str | None = None

    def __post_init__(self) -> None:
        if self.law_kind not in LAW_KINDS:
            raise ValueError(f"unknown law kind '{self.law_kind}'; known: {', '.join(LAW_KINDS)}")
        if self.text_level not in TEXT_LEVELS:
            raise ValueError(f"unknown text level '{self.text_level}'; known: {', '.join(TEXT_LEVELS)}")
        if self.studies < 1:
            raise ValueError("a corpus needs at least one study")

    def json(self) -> dict:
        return asdict(self)

    @classmethod
    def parse(cls, obj: dict) -> "Settings":
        return cls(**obj)


def code_sha256() -> str:
    """Hash of the generator's source (line endings normalised, so a Windows checkout hashes the same)."""
    return sha256_hex(canonical_bytes([[p.name, hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()]
                                       for p in sorted(PACKAGE.glob("*.py"))]))


def law_answer(law: Law, recipe: Recipe) -> tuple[str, str | None, dict[str, str]]:
    """Verdict, condition and sides that the law itself implies."""
    sides = {level: direction(effect, recipe.min_effect) for level, effect in law.effects.items()}
    if len(set(sides.values())) > 1:
        return "depends", law.condition, sides
    return next(iter(sides.values())), None, {}


def write_corpus(out: Path, recipe: Recipe, law: Law, studies: Sequence[Study], settings: Settings,
                 variant: dict | None = None) -> str:
    """Write the corpus folder and return its id. `variant` is the family record without its own corpus id."""
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty; choose a new folder")
    papers = [write_paper(s, recipe, settings.text_level, settings.seed) for s in studies]
    unfaithful = [fact for p, s in zip(papers, studies) for fact in missing_facts(p, s)]
    if unfaithful:
        raise ValueError(f"papers do not hold their planted facts: {', '.join(unfaithful)}")
    hashes = [[p.study, sha256_hex(p.text.encode("utf-8"))] for p in papers]
    kind = variant["kind"] if variant else "base"
    cid = f"{recipe.domain}2-{sha256_hex(canonical_bytes([kind, hashes]))[:8]}"
    (out / "papers").mkdir(parents=True, exist_ok=True)
    for p in papers:
        write_text_atomic(out / "papers" / f"{p.study}.md", p.text)
    write_json_atomic(out / "manifest.json", {
        "corpus_id": cid,
        "papers": [{"id": sid, "file": f"papers/{sid}.md", "sha256": digest} for sid, digest in hashes]})
    write_json_atomic(out / "corpus.json", {
        "corpus_id": cid,
        "generator": {"name": GENERATOR, "version": VERSION, "code_sha256": code_sha256()},
        "recipe": {"domain": recipe.domain, "sha256": recipe.sha256},
        "settings": settings.json(),
        "variant": {**variant, "corpus_id": cid} if variant else None})
    key = pooled(studies, recipe)
    write_json_atomic(out / "ground_truth.json", {
        "corpus_id": cid, "question": recipe.question,
        "conditions": [c.model_dump() for c in recipe.conditions],
        "law": law.json(),
        "studies": [s.json() for s in studies],
        "placements": [{"paper": p.study, "fact": pl.fact, "start": pl.start, "end": pl.end}
                       for p in papers for pl in p.placements],
        "key": key.json(), "vote": vote(studies, recipe).json(), "lumped": lumped(studies, recipe).json(),
        "key_matches_law": (key.verdict, key.condition, key.sides) == law_answer(law, recipe)})
    return cid


def build_base(out: Path, settings: Settings) -> str:
    recipe = load_recipe(settings.domain)
    law = draw_law(recipe, settings.seed, settings.law_kind)
    studies = draw_studies(recipe, law, settings.seed, settings.studies, exact=settings.exact,
                           noise_seed=settings.noise_seed, untested=settings.untested)
    return write_corpus(out, recipe, law, studies, settings)


def load_truth(corpus_dir: Path) -> dict:
    return json.loads((corpus_dir / "ground_truth.json").read_text(encoding="utf-8"))


def load_studies(corpus_dir: Path) -> tuple[Study, ...]:
    return tuple(Study.parse(s) for s in load_truth(corpus_dir)["studies"])
