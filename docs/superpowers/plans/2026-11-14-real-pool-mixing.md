# Real-paper pool: mixing plan (short)

Date: 14 Nov 2026. Status: steps 1-3 done (14 Nov); step 4 not started.

Results so far:
- Step 1: the "QA side" filter was tightened to retrieval augmentation / RAG / open-domain / knowledge-intensive /
  retrieved documents (the looser one let in visual QA papers): 51 close-topic papers. Test = 30 of them (6 are
  old eval papers), so 21 close-topic papers stay as sources; 237 sources in all. Old style papers are on neither
  side. Script: scratchpad `hf_split.py`, seed `hf-split-v2`.
- Step 2: scratchpad `real-papers/tools/hf_cut.py`; 85 test pieces from 30 papers; 237 cleaned source papers.
- Step 3, v9 against the new test set: AUC full 1.0, masked 1.0, function 1.0, surface 0.966, combined 0.998;
  style gap 0.30 (0.27 on the old test set). The switch of real set changes almost nothing: the gap is in our
  writing, not in the converter.
- Step 4 smoke (S001-S004, writer-v10.md, Sonnet): 3 of 4 pass every check incl. the blind reader; S004 fails
  (reader could not name the subset's three conditions; it also invented hand-check counts). No skeleton name or
  six-word run survived. Realism did not move: AUC words 1.0, surface 0.94 (v9 0.97), style gap 0.36 (v9 0.30;
  only 11 pieces). Biggest gap: capitals (-1.5), then "however", digits, brackets.
- v11 "real edit" (user approved 14 Nov, accepting ~90% real text and recognisable papers; kept local, git-ignored
  in data/synth2/written-v11/): code renames every real name in the source (scratchpad `v11lib.py`,
  `prepare_v11.py`); a writer (writer-v11.md) returns only edits (title, renames, replaces, inserts) that add the
  planted subsection and claim and remove no-retrieval results; code applies and checks them (`apply_v11.py`,
  `check_v11.py`). Smoke S001-S004: 4 of 4 pass code checks and the blind reader; 450-570 inserted words per
  paper. Classifier on 12 pieces: AUC full words 0.72, masked 0.64, function words 0.50, surface 0.62; style gap
  0.31 (driven by single words such as "same", "were"). Renamed sources alone (no edits): 0.88 / 0.62 / 0.40 /
  0.57, style gap 0.12. Remaining word cues are topic (dialogue, multimodal sources), not writing.
- v11 full run (20 papers, 57 pieces): 20 of 20 pass code checks and the blind reader (28 other results listed,
  none about the control). AUC full words 0.89, masked 0.74, function words 0.59, surface 0.61, masked+surface
  0.66; style gap 0.15 (v9: 1.0 / 1.0 / 1.0 / 0.97 / 1.0, gap 0.30). Synthetic cues now come from our inserted text
  ("the SYS", "lowers", "correctly", "subset", "overall the": the claim sentence is copied nearly verbatim); real
  cues are topic (in-context, few-shot, Google, Natural Questions: the test papers are newer, LLM-era).
- v12 (writer-v12.md, revision of v11 edits; `--claim-rules`: no 4-word run of the claim sentence, caps on
  "overall", "subset(s)", "correctly", "asked" in inserted text): 20 of 20 pass code checks, claim rules and the
  blind reader. AUC full 0.905, masked 0.735, function 0.587, surface 0.657, masked+surface 0.704; style gap 0.15.
  No gain over v11 (differences are within noise): the copied claim is gone, but the classifier now picks other
  words of our inserted text ("does", "retrieved passages", "contexts", "gets NUM", "factual questions"). The piece
  cutter favours on-topic windows, so our inserted subsection is over-represented in the pieces.
- Template v2 (`synth2 templedit`, backend/synth2/templedit.py; no model): code deletes no-retrieval parts and
  inserts a templated planted section before the conclusion plus template claim sentences (direction and
  confidence from the ground truth), redrawing until the code checks with claim rules pass. 20 of 20 pass the code
  checks; blind reader on all 20: 20 of 20 exact (30 other results listed, none about the control). AUC full 0.913, masked 0.742, function 0.572, surface 0.575,
  masked+surface 0.606; style gap 0.12: as hard to spot as v11/v12, at zero model cost. Inserted text is shorter
  (about 180-820 words).
- Template v3 wording (branch synth2-templedit-wording; data/synth2/written-t3/, git-ignored): shared levels named
  once in a scope sentence, table rows labelled only by the differing level, a gap-in-points line instead of
  repeated counts, three different claim sentences per paper. 20 of 20 pass code checks and the blind reader (26
  other results, none about the control). AUC full 0.924, masked 0.77, function 0.533, surface 0.593,
  masked+surface 0.622; style gap 0.12: same as t2 within noise. Reads better; not harder to spot.

**Goal:** synthetic papers that borrow the shape of real RAG papers (sections, paragraph jobs, lengths, citation
style), so the classifier (C2ST) can no longer tell them apart, while the planted counts and claim stay exactly
recoverable.

**Data:** `WKMarwat/arxiv-ai-papers` (2,673 papers, Docling markdown from PDF), local copy in the scratchpad
(`hf-aiarxiv/train.jsonl`). Treated as untrusted data; read with `python -I`.

## Steps

1. **Split (code, seeded).** Topic pool = papers whose title or abstract mention retrieval (271).
   - Real test set: 40 papers drawn from the 140 retrieval + QA/knowledge/hallucination papers.
   - Source pool: all other topic-pool papers (about 230), topped up with cs.CL papers to about 300 if needed.
   - The 10 papers that overlap our old 26 real papers go to the test set, never to sources.
   - A paper is in exactly one side; the split file is written once and never changed.
2. **Cleaner + cutter for Docling markdown (code).** Drop `<!-- image -->`, references and acknowledgements;
   rejoin hyphen breaks (`recogni- tion`); keep tables and captions. Then cut into about 1,000-word pieces with
   the same rules as `real-papers/tools/cut.py` (piece 1 = title + abstract + most on-topic stretch, pieces 2-3
   = next stretches). Same cleaner on both sides.
3. **Re-baseline.** Run C2ST (five views) and the style gap for v9 against the new real test pieces, so we know
   what the switch of real set alone changes before any mixing.
4. **Writer v10 = skeleton transplant** (new prompt file; v9 kept). Each synthetic paper gets one source paper
   (seeded). The writer gets the source's outline and, per paragraph, its job (motivation, related work, method
   detail, setup, result text) and length. It writes a new paragraph with the same job and length, the same
   citation style (numbered `[12]` or author-year), the same bracket and digit habits, but only our world's
   content and the planted facts. Smoke test on 4 papers, then 20.
5. **Checks (code) and measure.** Fail a paper if:
   - a name from its source survives (authors, models, datasets, cited surnames, acronyms not in our world);
   - it copies any 6-word run from its source;
   - any check of `check_v9.py` fails, or the blind reader does not recover all planted facts.
   Then C2ST + style gap against the real test set from step 1.

## Risks

- Topic drift: a source about, e.g., code retrieval gives an odd skeleton. Pick sources from the QA side first.
- Docling noise in real pieces (captions mixed in, numbered citations) may stay a classifier cue; step 3 shows
  how big it is.
- Licences vary per paper: we copy no text, only structure, and real pieces stay local, never published.

## Later (riskier) option

Mosaic: keep real generic sentences (e.g. "In this section, we describe our setup.") up to 5 words of run, mixed
with ours. Only if step 5 still shows a clear gap.
