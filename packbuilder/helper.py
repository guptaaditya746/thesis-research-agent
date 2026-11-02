"""D34 fallback: when the pack-builder agent fails, a fresh model writes the topic pack from the paper texts alone.

    helper(corpus, name, *, model, verify_model, cache, root=DOMAINS, question=DEFAULT_QUESTION) -> <root>/<name>

- The helper is blind to the generator's recipe. It reads the corpus only through `SystemCorpus` (manifest.json and
  papers/*; nothing else is opened), and it has no tools: the paper texts are in its prompt (prompts/helper-v1.md).
- It refuses when `generator.yaml` exists in the corpus folder or in the pack folder (a path check; the file is never
  opened): a pack written beside its recipe could leak the answers (preflight P23).
- Its proposal goes through the same code checks (proposal.problems) and the same second-model verifier as the
  agent's (agent.settle: verify, drop, check again, write). Provenance `by` is "packbuilder helper (D34)".
- One call, cached like `propose` (a rerun makes no model call); a proposal that fails a check raises ValueError and
  nothing is written.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import Any

from evaluation.baselines.common import SystemCorpus
from evidence.pack import DOMAINS
from jsonio import sha256_hex
from modelcall import JsonlCache, ask_sync, cache_key, load_prompt, model_identity, model_name
from packbuilder.agent import DEFAULT_QUESTION, SETTINGS, settle
from packbuilder.proposal import DISPLAY_KEYS, FIXTURE_ROOTS, Known, PackProposal, known_prefixes, problems

PROMPT = Path(__file__).resolve().parent / "prompts" / "helper-v1.md"
BY = "packbuilder helper (D34)"


def refuse_if_recipe_near(corpus: Path, folder: Path) -> None:
    """A `generator.yaml` in the corpus folder or the pack folder: refused. Only `exists` is asked; it is not opened."""
    for where in (corpus, folder):
        if (where / "generator.yaml").exists():
            raise ValueError(f"{where / 'generator.yaml'} exists: the D34 helper must be blind to the generator's "
                             "recipe, so it does not write a pack beside one")


def user_prompt(question: str, papers: dict[str, str], known: Known) -> str:
    """The input of the helper prompt: the question, display keys, taken prefixes and every paper's text."""
    taken = sorted({f"{name}: {prefix}" for name, prefix, _ in known})
    return json.dumps({"question": question, "display_keys": list(DISPLAY_KEYS), "taken_prefixes": taken,
                       "papers": [{"id": pid, "text": text} for pid, text in papers.items()]},
                      indent=1, ensure_ascii=False)


def helper(corpus: Path, name: str, *, model: Any, verify_model: Any = None, cache: Path, root: Path = DOMAINS,
           question: str = DEFAULT_QUESTION) -> Path:
    """Write the pack `name` for `corpus` from its paper texts alone; returns `root/name`."""
    if verify_model is None:
        raise ValueError("helper needs a verify model (verify_model / --verify-model): a second model checks every "
                         "proposed word against its quotes before the pack is written")
    corpus, root = Path(corpus), Path(root)
    folder = root / name
    refuse_if_recipe_near(corpus, folder)
    for existing in ("pack.yaml", "words.yaml"):
        if (folder / existing).exists():
            raise ValueError(f"{folder / existing} exists: a helper pack never replaces one already there")
    read = SystemCorpus(corpus)
    files_read = ["manifest.json", *(p.file for p in read.papers)]
    stray = [f for f in files_read if f != "manifest.json" and PurePosixPath(f).parent != PurePosixPath("papers")]
    if stray:
        raise ValueError(f"the corpus would read {stray}: only manifest.json and papers/* may be read")
    papers = {p.id: p.text for p in read.papers}
    known = known_prefixes([DOMAINS, root, *FIXTURE_ROOTS], skip=folder)
    prompt = load_prompt(PROMPT, PackProposal)
    text = user_prompt(question, papers, known)
    calls = JsonlCache(cache)
    key = cache_key({"prompt_sha256": prompt.sha256, "model": model_identity([model]), "by": BY,
                     "input_sha256": sha256_hex(text.encode("utf-8")), "settings": asdict(SETTINGS)})
    hit = calls.get(key)
    if hit is not None:
        proposal = PackProposal.model_validate_json(hit["output_json"])
    else:
        proposal = ask_sync(prompt, text, model=model, settings=SETTINGS).output
    found = problems(proposal, papers, known)
    if found:
        raise ValueError("the proposal fails its checks: " + "; ".join(found))
    if hit is None:     # a JSON string: the cache sorts keys, which would reorder `conditions` (treatment first)
        calls.put(key, {"output_json": proposal.model_dump_json(), "model": model_name(model)})
    return settle(proposal, papers, known, question, verify_model=verify_model, cache=calls, folder=folder,
                  root=root, name=name, by=BY, model=model, prompt_sha256=prompt.sha256, corpus_id=read.corpus_id,
                  files_read=files_read, tool_calls=[])
