# Slice 1 step notes

The design notes in the old session scratchpad were lost in a reboot; the whiteboard artifact
(https://claude.ai/artifact/1tDjJiPw3iDVdeE5YLTEA6) and the plan are the record.

## S1 Seed + dataset pane (21 Nov 2026)
- `data/seed/medical/blueprint.yaml` (by hand) -> `evqa seed names` (Claude Haiku proposes, code checks vs 1.28 M MeSH+ChEBI labels) -> `evqa seed build` (values from an effect model, no LLM) -> `seed.ttl`: 5 papers (4 test, 1 practice), 50 rows.
- `evqa seed check medical`: SHACL conforms, 0 name clashes (rapidfuzz ratio < 85), 0 practice/test overlap -> `check.json`.
- Vocab subsets frozen with rdflib in `data/seed/vocab/` (MeSH 2026, QUDT); downloads in `data/cache/` (ignored).
- HbA1c change uses our own unit `ex:PercentagePoint` (QUDT has none), so percent and percentage points stay apart.
- Claude headless runs without `--bare` (it drops the login); an empty cwd + `--setting-sources ""` keeps CLAUDE.md out.

## Inspection list for the end (Aditya, 21 Nov: "we will do this inspection in last")
Do these together after the slice runs end to end; do not stop for them before.
- S1: P-med-01 graph, 40 mg HbA1c more negative than 10 mg at 12 and 24 weeks.
- S1: names brenoxalin (84/100 vs "Penoxalin", limit 85), kavolemin, veloranide feel made up.
- S2: new "all" intent cards: gold tables per question (Q-med-01 includes P-med-04 newly-diagnosed rows as own rows).
- S3: read P-med-01 paper.md section 4 (Results): reads like a real trial paper; P-med-04 states "newly diagnosed" clearly.
- S3: L0 strict rule: "-0.78%" for an HbA1c change counts as missing (percent vs percentage points).
- S3: P-med-04 paper is short (1,960 words; only 4 seed values).
- S4 Spec: Run tab, any question, step 2: brenoxalin/kavolemin "not known", HbA1c synonyms sensible, open points "all" match the card.
- S4 Find: step 3: right papers kept, P-med-05 (veloranide) screened "no"; click a passage, the paper drawer marks it.
- S4 Extract: step 4: every row quote_ok; click a quote to see it in the paper; patient-group labels (fix in progress, see below).
- S4 Answer: step 5: Q-med-03 40 mg wins by 0.13; Q-med-04 brenoxalin 40 mg beats kavolemin 10 mg on metformin.
- S5 Eval: Evaluation tab, compare slice1-qwen with slice1-closed-book: closed book loses all facts at Find (~0).

## S4/S5 notes (21 Nov 2026, overnight)
- Qwen thinking OFF by default (StepLLM.think=False; Aditya): ~7x faster, no empty replies from reasoning loops.
- First real run slice1-qwen-6cbccf44f3 (143 s): L0=L1=L2 recall=1.0, L3=0.77, advisor 0.96.
  Loss = patient-group wording: P-med-01 states its population only in Methods, rows got "not stated"/vague labels,
  so Q-med-04 found no shared group (L3 0.25). Fix: Extract resolves each paper's population once from Find's
  context passages, then one checked LLM call merges group wordings per question; Answer stays code only.
- Context: industry handles long documents by never sending the whole paper: Find cuts papers into passages
  (headings, whole tables), ranks them (regex + BM25), the LLM screens and marks; Extract reads one passage per call.
- PaperQA2 and OpenScholar both use an embedding model (dense retrieval); llm-setup has qwen-embed
  (Qwen3-Embedding-0.6B) but the running 3x Qwen profile does not serve it. Hybrid BM25+dense = later slice.
- 21 Nov, Aditya: no BM25 and no embedding model. Find now searches only exact words: subject names (regex), then
  find/prompts.SearchTerms (Qwen lists other wordings from general knowledge: abbreviations, spellings, brand names;
  code keeps a term only if it is short, new, aimed at a spec target and written in some paper), then the gap agent's
  terms copied from paper text. Screen passages and agent snippets are the passages holding the most search words.
  Subject terms only make candidates (the screen decides); measure words make candidates only when no subject is
  named. Cost: one more LLM call per question. Weak spot: a wording neither the model nor the agent thinks of.
- After the group fix (extract/groups.py: paper population + checked group merging): same run, L0..L3 and advisor
  all 1.0 on the 4 test questions (19/19 facts in the answer). Closed book slice1-closed-book-db7b1e9ff2: L1-L3 = 0.
- CAVEAT for Aditya: part of the last gain came from loosening the eval's patient-group matcher (prism.group_of:
  a wording with words only one gold group has now matches it). Review before trusting 1.0; 4 questions is tiny
  and the pipeline was tuned on these same questions (no held-out set yet).
- Inspection item: Run tab, Q-med-04 step 4: patient_group label vs patient_group_raw per row.

## Corpus 5 -> 20 papers (21 Nov 2026, Aditya's decision)
- Blueprint adds P-med-06..20 (11 test, 4 practice) with 5 new made-up drugs (`evqa seed names` now invents only the
  new slots and keeps the old names), sitagliptin as a real active comparator, 4 new patient groups, and systolic BP
  (mmHg, added to the QUDT subset and units.json) and LDL-C. Old papers, rows and values are unchanged (test: sha256
  of the 50 old values); new papers never use drug_a/b or veloranide 50 mg, so the frozen Q-med gold stays right.
- New blueprint keys: `arms` (several drugs, one placebo), `comparator` + `comparator_dose`, `scale` + `conflict_with`
  (deliberate conflicts, linked in the seed with ex:conflictsWith), `names: {item: code|both}` (stored as
  ex:mention; the brief tells the writer, L0 reports `name_problems`).

## Bench v1 (21 Nov 2026): 20 papers, 100 questions, question graph
- Seed 20 papers / 197 facts / 6 conflict pairs; 100 questions (78 test, 22 practice): 50 answerable
  (lookup, effect, best, trend, list, conflict), 50 not reported (absent, near_miss, out_of_scope).
- Run bench-qwen-df6748bd1e (78 test questions): answerable L3 0.996 (36/37 exact); not-reported accuracy 1.0,
  hallucination 0, near-miss trap 0. Closed book bench-closed-book-86b3d82ef0: L1-L3 0, no hallucination.
- First pass was L3 0.883, not-reported 0.95, hallucination 0.049, near-miss trap 0.18; fixes (drug must be named
  in the paper, group qualifier must be grounded, age not a time point, background drug -> group, "..." quotes).
- CAVEAT: those fixes were made by looking at TEST-split failures. The scores are optimistic. Next: freeze the
  pipeline, tune only on practice, and make a fresh held-out test set (new seed papers) before trusting numbers.
- Open: Q-med-61 intent "compared with placebo" not turned into a comparator; one sentence stating 0.7 twice
  is blamed on extract (scoring quirk).
- Inspection: Questions tab (filter type/split); Run tab step 8 Graph; Eval tab per-type table + not-reported block.
