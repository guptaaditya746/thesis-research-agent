# paperfactory: what is left (fix brief v2, 21 Nov 2026)

Done on branch `paper-factory-fixes`: #10, SCORING_VERSION, #5, #3, #1, #12, #4, #2 (one commit each).
Order for the rest: re-score → #11 → #6 → #7 → #8 → #13 → #9 → "Do now" parts of D1–D5.

## Waiting on Aditya
- [ ] **Re-score the law pilot** (needs OK, about $0.10 on Haiku, leak test off). Copy the 3 papers to
      `runs/paperfactory/law-pilot-rescore`, run seed + eval, and show before/after per item. Model prompts changed,
      so the cache does not help. The pilot folder stays untouched.
- [ ] **#11 how many sentences per field** to export for hand labeling (target about 200).

## Items
- [x] **#11 Verifier score is circular.** The 98% is tested on sentences this verifier already accepted, and 29/98
      negatives are impossible pairs. Build a test set without the verifier (all candidate sentences; negatives:
      decoys, other relation, "not recorded" wording; impossible pairs reported apart). Export CSV with columns
      id, field, paper, sentence, context, subject, relation, object, label (empty), notes. Metrics script:
      precision, recall, false accept/reject, Cohen's kappa, Wilson 95% intervals, by relation and field,
      agreement between two labelers. Take the 98% out of README.md.
- [ ] **#6 World agent can return fewer papers.** Pass n_papers and the per-paper counts to `world.check`. Generate
      only the missing parts, up to 2 tries, then stop with a clear error.
- [ ] **#7 Cache.** Atomic writes (temp file, fsync, os.replace). A broken cache file → warning and recompute. Key
      also covers params and prompt template version (backend, model and server are in it since #12). Only checked
      outputs are cached (done in #12). Add `--no-cache` and clearing one step.
- [ ] **#8 Restarts reuse outputs made under old settings.** Write `<name>.meta.json` next to world.json, paper.md
      and QA results: hashes of the config fields used, field pack, the paper's notes, upstream outputs, prompt
      templates (including PaperOrchestra's), plus git commit and SCORING_VERSION. Redo a step when its meta
      differs, and print why. Stop on mixed settings unless `--allow-mixed`. Repairs (#4) update the meta.
- [ ] **#13 Writer cost missing from the report.** Add PaperOrchestra's call logs. Report cost per paper and per
      role, the total, and a projection for N papers. Unknown cost shows "unknown". Recompute the README figure
      from the logs ($0.42 was the whole 3-paper pilot without the writer; the writer added $0.119).
- [ ] **#9 Law wording in shared code.** Move field words into the packs: materials.py ("line of authority",
      "Holdings", "Action | Source"), prompts in evaluate.py ("holding"). A missing pack key is a clear error.
      Add a test that searches the shared modules for law terms.

## Design items: "Do now" parts only (propose the rest, then wait)
- [ ] **D1** BM25 baseline: rank of the gold sentence per question (share at rank 1, median). Add a
      `question_type` field.
- [ ] **D2** Warn when writer, rewriter, judge and verifier share a model (separate roles exist since #12). Log
      judge inputs and outputs. In the report, explain what the rewrite step does and why.
- [ ] **D3** Slots, timeouts and max_parallel per role are in the config (#12). Still to do: a preflight that
      estimates tokens per request against `context_window` and skips with a clear message.
- [ ] **D4** Decoy check (same relation and kinds, exactly one entity differs, year rule). Real-name check against
      per-pack lists (sources to be approved by Aditya; check "Vantor"). Shape report (facts, decoys, plan,
      sections, length).
- [ ] **D5** Table per field (medicine, materials): relation, definition, allowed kinds, pairs likely to be
      confused. Check aliases across the whole field, not only within one paper.

## Notes from the work so far
- PaperOrchestra's v1 prompts stay frozen (the committed benchmark papers were written with them); paperfactory
  writes with `v1n` (VENDORED.md C10).
- The verifier answers by item ids (V1…), because one sentence can be checked against several facts.
- A tag whose names the code cannot find now goes to the verifier; the tagger gives sentence numbers, not names.
- An ABSENCE_CLAIM is always fixed: the notes only list relations that exist, so the brief's exception never
  applies.
- The packs for medicine and materials have the new "text" keys but have never run.
