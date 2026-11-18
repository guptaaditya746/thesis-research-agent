# Written-v8: full fake paper, sliced like real ones (plan for approval)

**Goal:** make model-written papers read like real RAG papers by giving them real-paper content (a method, more
systems, more results, related work), while the planted counts and claim stay exactly recoverable.

**Why:** v4, v6 and v7 all score AUC 1.0 against real pieces in every view, while real-vs-real splits score 0.33
(random) to 0.80 (by year). The gap is content and shape: our rules forbid any other result, so 1,000 words go to
procedure talk. Style examples (v7) closed a quarter of the style gap (1.00 to 0.74) but not the AUC.

**Test set:** the same 20 uniform-prose s4 studies as v4, v6 and v7, so all four versions compare directly.

## Steps

1. **World builder (code).** For each study, a seeded `world.json` built from its v7 input:
   - an invented method (made-up name and one-line idea, e.g. a retrieval gate);
   - 2 invented extra systems besides the two planted ones;
   - 2-3 invented extra benchmarks;
   - 15-30 extra results as accuracies to one decimal, made by code.
   Planted cells are the only results given as raw counts ("570 of 900"); extras are percentages only.
   **Safety rule:** no extra result compares the retrieval-augmented system with the closed-book system on factual
   QA. Otherwise the text would hold unplanted evidence for the hidden law and change the right answer. Extras
   compare the invented method or other systems, or use other benchmarks or metrics.
2. **Writer-v8 prompt (Sonnet).** One full paper of about 4,000-5,000 words: abstract, introduction, related work,
   method, setup, results, analysis, limitations, conclusion. It gets the world, the planted cells, the claim, the
   code-chosen names and citations, and v7's real style examples. Hard rules from v7 stay, except that rule 3 ("no
   other results") becomes "report exactly the world's extra results and no others".
3. **Slicer (code).** Cut each full paper into ~1,000-word pieces with the same rules as the real papers (piece 1 =
   title + abstract + most on-topic part; up to 2 more). The full paper is the document for the benchmark; the
   pieces are only for the realism test.
4. **Checks.** Code: every planted count present, the claim present, extras match the world exactly (no invented
   numbers), citations from the given list, no copied runs from the style examples, no RAG vs closed-book extra.
   Blind Sonnet reader (reader-v3, unchanged) on the full paper: planted cells must come out exactly; it may list
   extras under other results, which we count but do not fail.
5. **Measures, compared with v4/v6/v7:** classifier AUC in 4 views against the 49 held-out real pieces, style gap,
   planted-fact recovery, and the share of extras the reader reports.

**Success:** planted recovery 20/20 (at most 2 papers dropped and rewritten), and either style gap below 0.5 or any
view's AUC below 0.95.

**Cost:** about 40 Sonnet calls (20 writers, 20 readers), plus code for steps 1, 3 and 4. About one day.

**Risks:** longer documents make the later engine runs slower and costlier; the reader may mistake an extra for a
planted result (lower precision, accepted); the safety rule above must hold or the benchmark answer changes.

**Not in this plan:** LaTeXML for both sides (needs the cluster); tuning against the classifier.
