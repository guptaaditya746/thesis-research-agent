"""Write synth2 corpora as one task file in the shape SciR's evaluation reads (github.com/idiap/SciR, commit
d698514): `{"metadata": ..., "tasks": [...]}`. Our corpora are a fourth track there, "pooling". Only the file
shape is shared; no SciR code is used here.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonio import canonical, write_json_atomic
from synth2.corpus import GENERATOR, VERSION, Settings, code_sha256, load_studies, load_truth
from synth2.recipe import Recipe, load_recipe
from synth2.write import write_paper

DOMAIN = "pooling"
FOOTER = ('Answer inside <answer></answer> with one JSON object: {"verdict": "depends|helps|hurts|no_effect|insufficient", '
          '"condition": "<condition id or null>", "sides": {"<level id>": "helps|hurts|no_effect"}, '
          '"untested": ["<condition id>.<level id>"]}')


def intro(recipe: Recipe) -> str:
    conditions = "; ".join(f"{c.id} ({', '.join(f'{lv.id} = {lv.name}' for lv in c.levels)})" for c in recipe.conditions)
    return f"{recipe.question}\nCandidate conditions: {conditions}\nThe studies follow."


def task_of(corpus_dir: Path) -> dict:
    """One corpus as one task: the plain text is the papers at level `table`, the obfuscated text is the
    corpus's own papers."""
    record = json.loads((corpus_dir / "corpus.json").read_text(encoding="utf-8"))
    settings = Settings.parse(record["settings"])
    recipe = load_recipe(settings.domain)
    truth = load_truth(corpus_dir)
    studies = sorted(load_studies(corpus_dir), key=lambda s: s.id)
    plain = [write_paper(s, recipe, "table", settings.seed).text for s in studies]
    own = [(corpus_dir / "papers" / f"{s.id}.md").read_text(encoding="utf-8") for s in studies]

    def problem(texts: list[str]) -> str:
        return "\n\n".join([intro(recipe), *(t.strip() for t in texts), FOOTER])

    def chunks(texts: list[str]) -> list[dict]:
        return [{"chunk_index": i, "text": t} for i, t in enumerate(texts)]

    return {
        "id": truth["corpus_id"], "domain": DOMAIN,
        "problem_nl": problem(plain), "problem_obfuscated": problem(own),
        "answer": canonical(truth["key"]),
        "metadata": {
            "generation_params": {"law_kind": settings.law_kind, "text_level": settings.text_level,
                                  "seed": settings.seed, "kind": (record["variant"] or {"kind": "base"})["kind"]},
            "logical_form": {"conditions": truth["conditions"], "studies": truth["studies"], "law": truth["law"]},
            "chunks": {"nl": chunks(plain), "obfuscated": chunks(own)},
        },
    }


def export(root: Path, out: Path) -> int:
    """Write every corpus under `root` as one task; return how many. No corpus there is a `ValueError`."""
    folders = sorted((p.parent for p in root.rglob("manifest.json") if (p.parent / "corpus.json").is_file()),
                     key=lambda p: p.relative_to(root).as_posix())
    if not folders:
        raise ValueError(f"no corpus under {root}")
    by_id: dict[str, dict] = {}
    for folder in folders:   # two corpora with the same papers have the same id and are one task
        task = task_of(folder)
        by_id.setdefault(task["id"], task)
    tasks = list(by_id.values())
    write_json_atomic(out, {
        "metadata": {"generator": GENERATOR, "version": VERSION, "code_sha256": code_sha256(), "tasks": len(tasks)},
        "tasks": tasks})
    return len(tasks)
