# synth3 worlds (plan 1 of 5): handoff

Written 17 Nov 2026, when plan 1 finished. Branch `synth3-worlds`: 11 commits from `0e7cdc11` to `2a9301d9`.
Nothing has been pushed or merged.

## State

- All 7 tasks are done and reviewed. The final whole-branch review found 0 Critical, 1 Important and 7 Minor
  issues. The Important one is fixed (`2a9301d9`): two results that the engine would merge as "one study
  published twice" could slip through. A re-check confirmed the fix.
- Tests: synth3 has 58 passed. The whole suite has 3260 passed and 36 skipped (run after the fix).
- Medicine: the spec and 5 worlds are approved and committed. The 5 folders were rebuilt after the fix, with 40
  papers each, in `data/synth3/built/medicine/` (git-ignored, local only). The worlds did not change. Seeds 1, 2
  and 4 got new numbers; seeds 3 and 5 came out the same.

## Judgement calls I made for you (each with its cost if wrong)

1. Worked on the branch in place, with no worktree. The plan and spec files were untracked, so a worktree would
   not have had them. Cost: none.
2. Never committed `backend/agent/tests/test_prompts.py`, which has an unrelated change. Cost: none.
3. Named the test spec's age levels young/old so one plan test fails for the right reason. Cost: none.
4. Stopped for your approval of the spec and of the worlds, as the plan says. Cost: none.
5. Kept the test arm ids "a"/"b" although they are English words, because the plan's own tests use them. Cost: a
   later check for ids in the text would need a rename.
6. Left the tuning of the value measure's noise to Task 4. Cost: none (it was done there).
7. Used the "Claude Opus 5.5" commit trailer the plan names. Cost: cosmetic.
8. Made hand-edited world files stricter: `approved` must be a real true/false, and effects must be real
   numbers. Cost: a few lines.
9. Settled the study design: one population level per hidden factor per study, head-to-head studies skip
   "can't tell" pairs, and labels look like "Surname et al. (year)". Cost: later plans adapt to the study shape.
10. Capped the redraw of studies with equal numbers at 1000, so a bad spec gives an error instead of hanging.
    Cost: a few lines.
11. "Split by" answers pick the factor with the biggest gap, and "untested" follows synth2. Head-to-head facts
    are one entry per drug pair and measure. Cost: plan 3 reads a slightly different shape.
12. Retuned the test-only spec's effect sizes so the noise gate test behaves. Cost: the unit-test spec is less
    realistic (tests only).
13. Ran the digits test on both text styles, as part of a fix round. Cost: one extra test case.
14. The multi-seed build checks every seed before writing anything. Cost: a short check loop.
15. Did the spec steps without a commit, and committed only after your approvals. Cost: none.
16. After you said "do rest", ran the final review and one fix wave on my own, and stopped before any merge or
    push. Cost: none.
17. The fix commit's trailer says "Claude Sonnet 5.5", because the fix ran on Sonnet. I did not amend it. Cost:
    cosmetic.

## Small issues left for later (deferred minors)

Paper text (plan 2 replaces the template text anyway):
- The setup sentence has no verb ("The Standard care the usual blood pressure treatment …"), and papers say
  "the Alvenor".
- The reported SD is always exactly 0.5 × the mean, which a realism classifier could spot.
- The papers' title uses only the first claim. A study with no claims would crash the writer (it never happens).

Hand-edited worlds:
- Effect sizes are not bounded. A huge edit gets clipped quietly instead of refused.
- The world's seed is not checked against its file name.
- The file does not say that a positive effect means "better for the patient", even for side effects.
- After a hand edit, nothing re-checks that a "split by" law still has a split.

Checks and tests:
- These are not pinned by tests:
  - one branch of the noise gate's error;
  - the head-to-head, ranking and inventory facts;
  - refusing a non-empty folder.
- Head-to-head answers come from the data and are not checked against the laws. Plan 3 must know this.
- A gate failure partway through a multi-seed build leaves the earlier seeds already written.
- A YAML syntax error in a spec raises a YAML error instead of a ValueError.
- The writer does not flag extra or duplicated placements.

Smaller:
- `describe()` reads "(Age group makes no split)".
- `pair_delta`'s divide-by-zero message is plain.
- `write.py` imports a private synth2 helper.
- The README lacks the `synth3 draw` / `synth3 build` commands.
- The real overclaim rate runs below the spec's rate (a study that only claims "helps" has nothing to
  exaggerate).
