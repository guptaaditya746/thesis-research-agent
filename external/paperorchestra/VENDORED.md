# Vendored: PaperOrchestra

- Upstream: https://github.com/google-research/paper-orchestra (official code of Song, Song, Pfister, Yoon,
  "PaperOrchestra: A Multi-Agent Framework for Automated AI Research Paper Writing", arXiv:2604.05018). Apache-2.0
  (`LICENSE`, kept).
- Pinned commit: `d9bae997e793a015ed38bb1605be9eb58c00284f` (2026-11-15, "Merge pull request #4 from
  obrienciaran/fix/invalid-escape-sequences"). Vendored on 2026-11-21.
- Copied: the whole tree except `.git/` and `assets/` (one 1.8 MB overview picture).
- Not used: `ar9av/paperorchestra` is a third-party "skill pack" re-implementation, not this code.
- Why: thesis plan, step S3 ("Paper writer: PaperOrchestra only. No fallback writer. We adapt it until it works:
  Claude as its LLM, citation step stubbed, prompts that fit any field, Markdown output.").
- Own environment: `pyproject.toml` + `uv.lock` here (no third-party dependencies: the adapted path needs only the
  standard library and the `claude` CLI). The upstream `requirements.txt` is kept for reference, not installed.
- Run: `uv run --project external/paperorchestra python external/paperorchestra/paper_writing_cli.py --help`;
  normally through `backend/evqa/paperwriter.py` (`write_paper(paper_dir)`) or `backend/paperfactory/write.py`
  (`uv run paperfactory run ...`).

To see every change against upstream: clone the upstream at the pinned commit and
`diff -ru --exclude=.git --exclude=assets <upstream> external/paperorchestra`.

## Pipeline after adaptation

Same agent order as upstream `methods/paper_writer.py`:

1. Outline agent (1 call) -> `outline.json`. Code completes the table/sentence plan so every value is placed.
2. Literature agent, stubbed (1 call): writes Introduction + Related Work without citations; empty citation map.
3. Section writing agent (1 call): fills Abstract, Methods, Results, Discussion, Conclusion; full Markdown paper.
4. Content refinement (3 calls by default): review -> revise -> review, upstream accept/revert rule + value gate.
5. New: value check in code + ONE repair call per failing section (0 calls when everything passes).

Typical cost: 6-7 Haiku calls per paper.

## Changes (each marked in the code with "Thesis adaptation" / "Added for the thesis vendoring")

- **C1 LLM backend = Claude Code headless.** New `utils/claude_code_utils.py`: `claude -p --model <m> --tools ""
  --setting-sources "" --strict-mcp-config --no-session-persistence --system-prompt ... --output-format json
  --json-schema ...`, run from an empty temp folder (not `--bare`, which drops the login). Every call returns a
  JSON object matching a schema (upstream parsed ```latex``` / ```json``` blocks out of free text). On-disk cache
  keyed by sha256(model, system, user, schema); JSONL log per call (step, cost, seconds, tokens, cached). At most 3
  calls at once: 3 `flock`ed slot files in a shared folder, so the cap holds across threads and processes. One
  retry on a transport error (no JSON, timeout). Default model `claude-haiku-5-5`, one model for all agents
  (upstream: separate writer/reflection/plotting/image models, Gemini by default). No temperature control
  (upstream used 0.7 / 0.75). `autoraters/agent_review.py`: numpy and Gemini imports made optional so its
  reviewer persona can be reused.
- **C2 Citation / literature step stubbed.** New `methods/agents/literature_stub_agent.py` replaces
  `HybridLiteratureAgent` (kept, unused): no web or Semantic Scholar search, no BibTeX, `citation_map.json` = `{}`.
  It keeps the upstream agent's writing role (one call writes Introduction + Related Work from the outline's
  `intro_related_work_plan`), with a new prompt `literature_stub_writer_prompt`. Outline: search queries and
  `citation_hints` removed. All prompts carry `NO_CITATION_PROMPT` (no citations, no reference list).
- **C3 Field-neutral prompts.** "Senior AI researcher / top-tier ML conference" became "senior researcher in the
  field of the materials (e.g. clinical medicine, materials science, computer science)"; ML-specific directives
  (optimizers, architectures, SOTA baselines, conference names) removed; the outline example is an unrelated field
  trial. The upstream prompts are kept next to the new ones as `*_upstream` (unused) for comparison.
- **C4 Markdown output instead of LaTeX/PDF.** New `templates/markdown/{template.md,guidelines.md}` (sections
  Abstract, Introduction, Related Work, Methods, Results, Discussion, Conclusion; 2,400-3,200 words ~ 4-6 pages;
  pipe tables with captions). No LaTeX compile, no PDF, no page screenshots, no VLM formatting loop, no figures and
  no plotting agent (the outline's `plotting_plan` became a `table_plan`). `paper_writing_cli.py` rewritten for
  these arguments; upstream batch helpers in `methods/paper_writer.py` removed (the thesis entry point batches).
  Upstream retried the whole pipeline 3 times on any exception; now a failure raises.
- **C5 Hard value rule + code check + bounded repair.** `FACT_RULE_PROMPT` (`utils/prompt_utils.py`) in the
  section writer, refinement and repair prompts: every value of `experimental_log.md` exactly as written (same
  digits, decimals, sign, ASCII minus, unit), in its placement (table cell vs "<value> <unit>" in a sentence and in
  no table), no other result numbers, no row ids, no talk about the inputs ("as given in the source materials", added after
  the first Haiku draft wrote such sentences); examples for a normal, a confusing and a missing case. New
  `utils/fact_check.py` parses the facts (row id, value, unit, placement) from the log, checks the paper
  (multiset count when several facts share a value), and runs one repair round: ONE call per failing `## ` section,
  given only that section and only its failed facts with the reason; a repair is accepted only if the re-checked
  paper has fewer failures and no newly failing fact; no second round. Also reported, not repaired: extra decimal
  numbers not in the inputs, leaked row ids, word and table counts. The section writer also receives a code-built
  `value_checklist`.
- **C6 Refinement cost and gate.** Defaults: 1 reviewer (upstream 3 + a meta review) and 1 reflection round
  (upstream 3); both are CLI flags. The upstream accept/revert rule on review scores is kept; added: a revision that
  makes more values fail is rejected (`REJECTED_LOST_VALUES`).

Files changed: `paper_writing_cli.py`, `methods/paper_writer.py`, `methods/agents/{outline,section_writing,
content_refinement}_agent.py`, `methods/prompts/{outline,section_writing,content_refinement,literature_review}_agent.py`,
`utils/{prompt_utils,common_utils}.py` (common_utils: UTF-8 read), `autoraters/agent_review.py`.
Files added: `VENDORED.md`, `pyproject.toml`, `uv.lock`, `utils/claude_code_utils.py`, `utils/fact_check.py`,
`methods/agents/literature_stub_agent.py`, `templates/markdown/`.
Unchanged and unused: `methods/paper_writer_with_plotting.py`, `methods/agents/{plotting,literature_review}_agent.py`,
`methods/prompts/format_agent.py`, `utils/{gemini,openai,llm_backend,scholar,pdf,paper_banana,content_parsing}_utils.py`,
`autoraters/` (except agent_review), `frontend/`, `templates/{cvpr2025,iclr2025}`, `paper_writing_cli.sh`.

C2 (21 Nov 2026): `utils/claude_code_utils.py` can also call Qwen: `--writer_model_name qwen:<alias>` sends each call
to the llm-setup LiteLLM gateway (thinking off, JSON schema enforced by the server). Same cache, log and 3 slot locks.

C10 (21 Nov 2026): prompt set `v1n` = v1 + `NOTES_RULE` (methods/prompts/versions.py) in the literature, section
and refinement prompts: the materials are never a source, no claims that a relation is unrecorded or absent, and
relations only for pairs the log lists. paperfactory uses v1n; v1 stays frozen.

C9 (21 Nov 2026): `--backend_json` (paperfactory RoleModel fields) sends every call through paperfactory's model
layer (`paperfactory.llm.po_runner`: claude_cli or any OpenAI-compatible server, cost reported / priced / local /
unknown, never 0 for unknown); `ClaudeCodeLM(runner=...)` takes an outside backend; `--max_parallel` sets the slot
count (still at most 3). With `--backend_json` the CLI runs in the main project environment (paperfactory/write.py).

C7 (21 Nov 2026): named writer prompt sets, `--prompt_version v1|v2` (default v1 = the prompts of the frozen
benchmark papers, unchanged). v2 (`methods/prompts/writer_v2.py`, `methods/prompts/versions.py`,
`templates/markdown/guidelines_v2.md`) replaces the Introduction/Related Work and section-writing prompts, adds a
plain-writing rule to the refinement prompt, uses shorter per-section length targets, and gives the section writer
a new input `style_examples` (`--style_examples <json>`: short CC BY / CC0 excerpts of real trial reports and
retrieved real abstracts, built by code in `backend/evqa/research/style.py`). Agents take their prompt as a
constructor argument; with v1 every prompt and user message is byte-identical to before (same cache keys).
`utils/fact_check.py`: `unsupported_numbers` (every number not in the brief, beyond labels and years) and
`exemplar_leaks` (numbers / drug names taken from a style example), both reported in the final check.
See docs/design/qwen-writer.md.

C8 (21 Nov 2026): prompt version `v2r` = v2 + references found by the Qwen research loop
(`backend/evqa/research/agent.py`, run before this pipeline). `--references <json>` gives the Introduction +
Related Work call a `references` input (first author, year, venue, title, one-line gist without numbers) and
`CITATION_RULE_V2R` (cite only those, as "(FirstAuthor et al., YEAR)", never a number from them); the section and
refinement calls get `CITATION_KEEP_V2R` instead of `NO_CITATION_PROMPT` (keep citations, add none).
`StubLiteratureAgent` takes `references`. After the repair round, `fact_check.check_citations` matches every
citation (author + year) against the list; `citation_map.json` holds the cited references; a `## References`
section with only the cited ones is appended to paper.md (after all checks, so titles of other studies are not
counted as paper numbers). Reference abstracts count as exemplars for `exemplar_leaks`. v1 and v2 unchanged.

C9 (21 Nov 2026): v2 and v2r only, after the value repair round: ONE repair call for numbers found in no input
text (`unsupported_numbers`). `fact_check.number_repair` lists each flagged sentence (or table row) with its
numbers; the prompt `writer_v2.NUMBER_REPAIR_V2` asks for a replacement without them (never a new number; "" deletes
a sentence). Code keeps a replacement only if it holds no flagged or new number and a table row keeps its cells,
and keeps the whole repair only if no value fact that passed now fails. No second round; what is left goes to
`unsupported_numbers_after_repair` in the final check (writer_log) and facts_check.json (`number_repair` entry);
the paper does not fail. v1 makes no such call (its prompts and cache keys are unchanged).

## paperfactory changes (21 Nov 2026)

- `methods/paper_writer.py`: the number-fact gate is skipped when the template folder has `genre.json` with
  `"numeric_facts": false` (argument papers have holdings, not numbers; they are checked after writing).
- `methods/agents/literature_stub_agent.py`: the intro step fills the template's first two numbered sections,
  whatever the genre calls them (was hard-coded "Introduction" + "Related Work").
- Genre templates live in `backend/paperfactory/packs/genres/`, not here.
