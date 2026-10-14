# Annotation guideline (gold v1)

Adapted from the labelling repo's `guidelines/annotation.md` to facts with quotes from the Markdown
corpus. How the answers are used is in `gold/README.md` (Review).

You review the **candidate facts of one question's evidence document D**. D was built by a model
(`sub-model`, not the agent being scored): every paper of the corpus was screened for the question,
and the relevant papers' text was read for facts, each with a **quote** copied from the paper. You see
every fact a second model sorted as part of the answer or as context, plus a random sample of the
others, shuffled; you are not told which is which.

Each record shows:

- the **question** and the **concept**: the picked interpretation of the question, with the shape of
  the answer (table columns, or graph edges such as `Paper —evaluatesOn→ Dataset`);
- the **fact**, a triple `subject — predicate — object`, and the row of the answer it belongs to;
- the **quote**, and the **passage** around it in the paper with the quote highlighted.

Judge each fact **against its quote only**. The passage is there to see what the quote refers to
("we", "our method", "Table 2"), not as a second source. Do not use outside knowledge. When the quote
occurs several times in the paper, a note above the passage says so and one occurrence is marked; judge
the quote itself. Only when the record says the quote could not be found in the paper is the fact not
stated (incorrect).

## 1. Is the fact correct and part of the answer? (`label`)

- **Correct**: the quote states the fact (paraphrase is fine), subject, predicate and object are all
  right, **and** the fact belongs in the answer the concept asks for: it is (part of) a row of the
  answer, or a value in one of its cells.
- **Incorrect**: the quote does not state it, contradicts it, or the fact does not belong in the
  answer (true perhaps, but not what the concept asks for).
- **Unsure**: you cannot decide from the quote and the passage. Write why in `note`; unsure facts are
  left out of the key and listed for a second look.

Numbers must match the quote exactly (41.5%, not "about 40%"). A result without the dataset or metric
it was measured on is not correct as it stands: fix it or mark it incorrect.

**Fixing a fact (`correction`).** If the core is right but one part is wrong or too vague (a wrong
number, a dataset named loosely, the wrong paper as subject), write the corrected fact as
`subject | predicate | object` and label it **correct**. Leave a part empty to keep it: ` | | BIRD`
changes only the object. The fix must still be stated by the same quote; if it is not, mark the fact
incorrect and add the right one as a missing fact (section 4). A correction that is not three parts
separated by `|` cannot be used: the export drops the fact and lists it.

## 2. Is it vital? (`vital`, for correct facts)

**Yes** if an answer without this fact misses the point of the question; **no** if it is worth having
but a good answer could leave it out. Most questions have 1 to 4 vital facts. Leave it empty for facts
you mark incorrect; an empty answer on a correct fact counts as no. Vital recall ("did the answer get
the essential facts?") is computed from these marks.

## 3. Subjects

Papers are named by their corpus id, the file name without `.md`: `p12` or `2025-acl-long-892`. When
a fact is the paper's own statement ("we evaluate on HotpotQA"), the subject is the paper's id. Use the
same ids in corrections and missing facts.

## 4. Missing facts (the `-missing` dataset)

After reviewing a question's facts, open its record in the `-missing` dataset. It shows what D already
has (its rows and the papers screened relevant). Add every correct fact that belongs in the answer and
that D does not contain, one per line:

```
subject | predicate | object | file | quote
```

`file` is the paper's file (`p12.md`; `p12` is fine too). The `quote` is copied from that file: it must
occur there word for word (whitespace, line breaks, dashes and quote marks may differ; a quote may not
cut a number), and only once, so copy enough of the sentence. The export anchors it with the same check
the agent's claims pass (`agent/anchor.py`); a line whose quote is not found or occurs more than once,
or that is not in this format, is listed in `export.json` and **not** added, so check that list after
exporting. The quote is the rest of the line, so it may contain `|`.
Mark **Reviewed** even when nothing is missing. This step is what keeps the gold from being only what
the builder found.

## 5. Papers the screening marked not relevant (the `-screening` dataset)

A random sample of the papers the screening marked not relevant, a few per question, is loaded here.
Each record shows the question, the concept and the whole paper. Answer: **is this paper relevant to
the question?** Yes if it states a fact that belongs in the answer, judged as in section 1. If yes, add
the missing facts in `missing`, in the format of section 4. Skim the paper; do not answer from the title
alone, and answer no when the paper only mentions the topic. The sample is random on purpose: check
every record, also the ones that look obviously irrelevant, or the estimate of what the screening
missed is biased. Facts you add here join the key like missing facts.

## 6. The overlap subset (the `-overlap` dataset)

About 20 % of the questions are in the `-overlap` dataset instead of `-review`. Two people review them
**independently**: do not discuss them before both have submitted. When both are done, run
`gold snapshot` **before** discussing anything: kappa is computed from the earliest snapshot in which
both answers of a record are present (every `gold pull` saves one too), so changing an answer to settle
a disagreement does not raise it. Disagreements (keep versus drop, or different fixes) are then
settled by the **adjudicator**: a third person who submits their own answer on the disputed records, or
the outcome of a recorded discussion entered under a separate user; `gold export --adjudicator NAME`
uses that answer. If the adjudicator is one of the two raters, that rater's answer simply wins; the
export warns and records it. A fact both keep is vital only if both marked it vital.

## 7. Checking the judge (the `-judge` dataset)

After runs have been scored, a sample of fact-quote pairs from the runs is loaded here. For each pair,
answer **does the quote support the fact?** with the same reading as section 1, but without the
"belongs in the answer" part:

- **supports**: a reader of the quote learns the fact;
- **partial**: the quote supports only part of it, or a vaguer statement;
- **no**: the quote does not state the fact, states something else, or contradicts it.

You do not see the model judge's answer or which condition the run was in. `gold judge-agreement`
compares your answers with the judge's; below kappa 0.61 the judge is not used for soft scores.

## 8. When unsure

Choose **Incorrect** or **Unsure** rather than Correct, **no** rather than vital, **partial** rather than
supports, and write a short note.
