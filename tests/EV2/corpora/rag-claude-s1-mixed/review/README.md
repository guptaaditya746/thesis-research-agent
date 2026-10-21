# Fidelity review of rag-claude-s1-mixed (Tim §6: the final documents checked)

| File | What it is | Who fills it |
|---|---|---|
| `review-s1.csv` / `.md` | All 483 rows: every planted fact in all 20 papers (`synth sample --n 20 --seed 1`); empty | — |
| `review-s1-claude-precheck.csv` | The same 483 rows pre-checked by Claude Sonnet subagents (brief: `precheck-brief.md`); a **model** check, not a human one | Claude, 21 Oct 2026 |
| `review-s1-yours.csv` | 35 rows for the **human** check: the 10 rows the pre-check flagged plus a seeded random sample of 25 (15 numbers/claims, 10 names); empty | the user |

Pre-check result: 483/483 present and stating the truth; 2 `unambiguous: n` (S010.m2, S020.m2) and 8 more unsure rows,
all in S010, S020 (the planted decoys of `decoys.json`: an abstract states a wrong value on purpose) and S013 (the
label `data: contradicts` misread as "the numbers contradict the sentence").

Report the human sample as the human check (`evaluate review --csv review-s1-yours.csv`), and the pre-check
separately as a model check. The human sheet does not show the pre-check's answers, so they do not steer the review.

## Second model check of the 35 rows (21 Oct 2026)

The user asked Claude to check the 35 rows, since they had no time. `review-s1-opus-check.csv` holds that check:
Claude Opus 5.5, the session's own model, read each row in its paper and confirmed that every planted value occurs
exactly once.

- 35 of 35 rows: present, true and unambiguous.
- It disagrees with the Sonnet pre-check on S010.m2 and S020.m2. Opus judges both table values unambiguous: the text
  at that place maps to one fact, and the conflicting number in the abstract is the planted decoy.

**This is a model check, not a human one.** `review-s1-yours.csv` stays empty. Until a person fills it, the thesis
reports the fidelity check as two model checks, the pre-check (483 rows) and this check (35 rows), with the human
check still to do.
