# Plan: add PaperQA2 (and other answering baselines) so they run and score like evqa

Status: plan only, nothing built. Written 21 Nov 2026.

## 1. The problem in one paragraph

Your scorer (`evqa/eval/prism.py`) grades *evidence*: it reads `spec.json`, `find.jsonl` (passages with
offsets), `rows.jsonl` (values with quote offsets) and `answer.json` (a typed table). PaperQA2 does not make
those. It gives back **free text with citations**, plus the **text chunks** (contexts) it read. So you need a
thin adapter that turns PaperQA2's output into the parts your scorer can read, plus one new score that works on
plain answer text for *every* system. Then `evqa compare` puts them side by side.

## 2. What maps to what

| Your layer | Your system makes | PaperQA2 gives | How to fill it |
|---|---|---|---|
| Spec / advisor | `spec.json` | nothing | leave empty; advisor = n/a for the baseline |
| L1 (did search find the right passage?) | `find.jsonl` | contexts: chunk text + doc name | find each chunk in `paper.md` (exact, then fuzzy with rapidfuzz) -> `FindHit` with start/end. Fair, no LLM |
| L2 (are the right values pulled out?) | `rows.jsonl` | numbers inside the answer text + cited chunks | one "answer -> rows" converter step (below). Diagnostic only |
| L3 (is the final answer right?) | `answer.json` | answer text | new **L3-text** score (below) = the headline, same for both systems |
| not-reported / hallucination | `Answer.not_reported` | "I cannot answer..." text | code: PaperQA2's fixed cannot-answer phrase -> not_reported |
| cost | events.jsonl tokens, seconds | PaperQA2 cost tracker + token counts | copy into the same `end` event fields |

### New score: L3-text (works for any system)

For each gold fact of the question: does the answer text state the **value** (read with `norm.py`, same unit
rules) next to the right **time point / patient group / dose**? Score per question = share of gold facts stated,
minus wrong extra values (precision), same per-type rules as prism where possible.
- Your system: render `answer.json` to text (`Answer.sentence` + table rows) and score that text the same way.
- Not-reported questions: right if the text says it cannot answer and states no value.
- Matching the settings words in free text needs one small, blind LLM check per (fact, answer) pair, like
  `eval/judge.py` ("does this sentence state value V for condition C? yes/no/unclear"), with code checking the
  number itself. Keep it separate from generation (your `docs/prompt-writing.md` rule).

This is the fair headline number. The mapped L1/L2 numbers explain *why* a system wins or loses.

### Answer -> rows converter (for L2 and blame)

One LLM call per answer: "list every value this answer states, with the cited chunk sentence it came from".
Code then keeps a row only if (a) the number is in the answer text, (b) the quote is found in `paper.md`
(gives `quote_start/end`, `quote_ok`). No new numbers can enter. Then prism's L2, blame and near-miss trap work
unchanged.

## 3. How to run PaperQA2 inside your setup

- **Separate environment.** `paper-qa` pins its own litellm / pydantic versions. Put it under
  `external/paperqa2/` with its own `pyproject.toml` and uv env (same pattern as `external/paperorchestra/`).
  It runs as a subprocess and writes JSON; `evqa` only reads the JSON. Keeps `uv.lock` and
  `tests/test_boundaries.py` clean.
- **Same model.** Point PaperQA2's `llm`, `summary_llm` and `agent_llm` at your LiteLLM proxy model
  (`orch-model`, Qwen, think off) from `llm-setup/`. Same model = the comparison is about the method, not the LLM.
- **Same papers only.** `paper_directory = data/dataset/<domain>/` (paper.md files). Never the seed. Turn off
  outside metadata lookups (Crossref / Semantic Scholar; `use_doc_details` off) so it stays offline.
- **Embeddings.** PaperQA2 needs one. Your 21 Nov rule says no embedding model for evqa, but a baseline should
  run as its authors intended. Run two variants: `pqa-dense` (qwen-embed from llm-setup) and `pqa-sparse`
  (PaperQA2's built-in keyword/sparse embedding, closest to your exact-word search).
- **Two modes.** `pqa-rag`: `Docs.aquery` (fixed pipeline: retrieve -> summarise chunks -> answer).
  `pqa-agent`: the full PaperQA2 agent (search, gather evidence, answer). The agent is the "SOTA" one.
- **Do not tune it on test.** Keep PaperQA2's prompts as shipped. Only settings like `evidence_k`,
  `answer_max_sources`, chunk size may be set, and only on the practice split.
- **Pin and record.** Pin the `paper-qa` version; write its version + settings hash into the run `manifest.json`.
  Save every raw reply (`pqa_raw.json` per question) so scoring can rerun with no model.

## 4. Files to add (small, one job each)

| File | Job |
|---|---|
| `external/paperqa2/pyproject.toml`, `run_pqa.py` | own env; reads questions JSONL, writes one `pqa_raw.json` per question |
| `configs/evqa/practice-pqa-agent.yaml` (+ `-rag`, `-sparse`) | `system: paperqa2` + PaperQA2 settings; same domain/split/llm as practice-qwen |
| `backend/evqa/baselines/paperqa2.py` | calls the subprocess, then maps raw -> `find.jsonl`, `answer_text.txt`, events |
| `backend/evqa/baselines/to_rows.py` | answer -> rows converter (LLM + code checks) |
| `backend/evqa/eval/text_answer.py` | L3-text score for any run (renders `answer.json` to text when present) |
| changes: `contracts.RunConfig` (`system` field), `run.py` (dispatch on `system`), `prism.score_run` (accept missing spec/rows), `compare.py` (add `l3_text`, `system` column) |

Run folder stays `runs/evqa/<name>-<hash>/<qid>/` so the Workbench and `evqa compare` see it.

## 5. Order of work

1. **Smoke (half a day).** Install paper-qa in its own env, ask 1 practice question with Qwen over the 21
   medical papers by hand. Check it reads `.md`, talks to LiteLLM, and how long one question takes.
2. **Runner + raw output** for the practice split; resumable like `run.py` (skip finished `pqa_raw.json`).
3. **L1 mapping** (`find.jsonl`) -> first fair comparison: who finds the right passages.
4. **L3-text** for both systems -> the headline table.
5. **Answer -> rows** -> L2, blame, near-miss trap, hallucination for PaperQA2.
6. **Compare + ablations:** your system vs pqa-agent vs pqa-rag vs pqa-sparse vs closed book, with bootstrap
   intervals (already in `compare.py`). Only then bench/holdout, under your existing locks.

## 6. Other baselines worth the same adapter

- **Long context:** all 21 papers are ~290 KB (~75k tokens). If Qwen's window allows, put every paper in one
  prompt and ask. Cheap, strong, and a reviewer will ask for it. Reuses L3-text and the converter.
- **Plain RAG:** chunk + BM25/dense top-k + one answer call. Shows what PaperQA2's extra steps add.
- **OpenScholar:** already named in `docs/design/slice1.md`; same adapter shape (text + citations).
- **Closed book:** you already have it (`bench-closed-book.yaml`).

## 7. Risks

- Free-text matching is the weak point: the L3-text judge must be blind (no system name) and checked on
  ~20 hand-labelled answers before you trust it.
- PaperQA2 may cite a chunk but state a value from another; the converter's quote check catches that.
- Table-heavy papers: PaperQA2 chunks by characters and can split tables; note it as a finding, do not fix it.
- Qwen via LiteLLM may break PaperQA2's tool-calling agent; if so, report `pqa-rag` and say why.
