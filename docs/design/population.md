# Settings of a value, domain-free (plan v2, 21 Nov 2026)

Status: plan, agreed with Aditya ("rewrite"). Replaces plan v1 (fixed medical patient fields + MeSH), which was
domain-bound: the thesis will move to other domains (materials science, LLM papers, law), so no step may depend on
a domain's word lists, regexes or field names. Also replaces today's free-text patient group, the LLM merge
(extract/groups.py `harmonise`), the regex qualifier guard (`QUALIFIERS`) and the scorer's word rules
(eval/prism.py `group_of`).

## Idea

A reported value holds under conditions: patients, dose and week in medicine; composition, temperature and
processing in materials science; dataset, model size and prompt setting in LLM papers; court, jurisdiction and date
in law. Call them the value's **settings**. The LLM decides what the settings mean; code only checks grounding
(quotes) and structure (consistency). Nothing is hard-coded per domain.

## The contract (contracts.py)

```
Dimension:  key (snake_case), question (what the user is asked), why (one line)          # per question
Setting:    dimension key, value (short, the paper's words), quote (checked substring), source ("row" | "paper")
SettingSet: id, paper, settings: [Setting], label (made by code from the values)
Row:        + settings (SettingSet id); patient_group / dose / time_point stay readable for old files
Link:       a, b (SettingSet ids), verdict same | different | unknown, differs_on [dimension keys],
            quote_a, quote_b, verifier verdict, accepted (code)
```

## Steps

1. Spec picks the dimensions (LLM, per question): which settings a value of this measure for these subjects
   depends on, as open points (today's open points, but proposed by the model from the question, not from a fixed
   medical list). Fixed ones come from the question text (quote checked against the question). Examples in the
   prompt from three domains (medicine, materials, ML), none from our seed.
2. Extract reads settings (LLM, per paper, then per row only when a paper has several setting sets): one value per
   dimension with a quote, or "not stated". Code: quote in paper.md, the value's words supported by the quote,
   numbers in the value present in the quote. Failed checks: one repair call with the failed checks, then
   "not stated" (noted). No domain words in code. Spec never reads papers; Extract does.
2b. Extra settings (LLM, same call as step 2): the paper may vary something Spec did not list (fasting vs fed,
   annealed vs as-cast, zero-shot vs few-shot). Extract reports it as an extra dimension with a quote for each
   value. Code keeps it only when the quotes check and the paper's rows really differ on it; it becomes an extra
   answer column marked "found in the papers, not asked", so rows that differ on it are never pooled silently.
   The Workbench shows these; the advisor may ask the user about it next time.
3. Link setting sets (LLM generator + separate LLM verifier, per pair that Answer must compare): "same / different
   / unknown, which dimension differs, with a quote from each side". Code accepts a "same" only when the verifier
   agrees and the quotes check; disagreement = kept apart and shown. Groups = connected components of accepted
   "same" links (code); a group whose members conflict pairwise is split (code).
   Only pairs that matter are judged: rows Answer would put in one table cell or compare (bounded by code).
4. Answer (code): a row fits the question when every fixed dimension is linked "same" to the question's value;
   "unknown" is shown as "can't tell", never silently dropped or merged. Label made by code from the settings.
5. Scorer (domain-free): a row's gold setting set is its source paper's (+ arm) context in the seed: compared by
   provenance (paper id + quote offsets), never by wording. A separate blind LLM judge checks the label the user
   sees against the seed's context description; its verdict and reason go to eval.json (reported separately).

## Optional, per domain (plug-ins, never required)

A domain may add a vocabulary file (MeSH for medicine, a materials ontology) that gives the LLM candidate names
or canonical ids. The pipeline must run and be scored without any plug-in; a plug-in is an ablation.

## Deleted after the switch

groups.py `harmonise`, `cluster`, `guard`, `QUALIFIERS`, `ON_DRUG`; GroupClusters prompt; prism `group_of`;
answer/canon.py FILLER/SPELL for patient groups; the fixed medical open-point list in Spec (seed/questions.INTENT
stays only as the benchmark's intent cards = simulated user answers).
Plan v1 code (backend/evqa/population.py MeSH facets, data/vocab/mesh-*.tsv.gz, Facet/Population contracts) was
never wired in; removed 21 Nov (dead-code audit). Restore from git at 60672e59 if the medical plug-in is wanted.

## Order and checks

Spec dimensions -> Extract settings -> links (generator + verifier) -> Answer -> scorer by provenance -> tests ->
tune on the 22 PRACTICE questions only -> one test score (contaminated, comparison) and the hold-out score.
Cost to measure: link calls grow with compared pairs; cap by code, report calls and tokens per question.

## Open

- A tiny second-domain fixture (e.g. 3 fake materials papers) in tests, to prove nothing is medical-bound.
- Papers with subgroups (results by age band, by alloy batch) give several setting sets per paper.

## Text answers (argument questions, e.g. law: "On what rule did court X rely?")

Ideal handling (agreed 21 Nov 2026): treat a claim like a value. Plant it, trace it by provenance, judge meaning
as multiple choice.

1. Seed: each claim is an RDF fact (subject, relation, object), e.g. court X relies_on rule R. Plant decoys too:
   X mentions S but rejects it; court Y relies_on S.
2. Gold: the writer places each claim at a planned spot; code records its span in paper.md (as the L0 value check
   does for numbers).
3. System: Extract reads claims (subject, relation, object) with a quote, checked like settings (anchor.py match,
   parts in the quote, separate verifier). Answer lists claims with their quotes.
4. Scoring:
   - provenance (code): the answer's quote overlaps the gold claim's span -> found / missed / made up. The system
     never sees or names gold ids; code maps quotes to claims.
   - meaning (separate blind LLM): pick which planted claim the answer sentence states, from a closed list
     (gold + decoys + "none"). Multiple choice, not "is it right?". Reported separately from provenance.
5. Judge validation: hand-check about 30 picks; report agreement with the judge.

Rejected: ids only (right quote + wrong summary still scores); LLM judge vs gold text alone (not repeatable, hard
to defend).

Fixes for the review holes (21 Nov 2026, v2; replaces the canonical-sentence version):

1. Tagged writing (holes 1-3): the writer wraps every sentence that states a claim or a decoy in a tag,
   e.g. `<c C3>...</c>` / `<d D1>...</d>`. Code strips the tags to make paper.md and records exact spans. Gold =
   all tagged spans of a claim (every restatement); decoy spans recorded the same way (a quote there = wrong).
   Code checks: every planted claim and decoy tagged at least once; tags well formed; ids known.
2. Untagged sweep: code lists every sentence that names both parts of a claim (court and rule names come from our
   own seed, so no domain rule). A separate verifier asks if an untagged one states a claim; if yes, one repair
   call to tag or reword it, else the paper fails the check.
3. Judge tested on gold (hole 5): tagged spans are labelled data (claim id, or decoy). Run the meaning judge on
   all of them before scoring; report its accuracy and decoy confusion. Pass bar >= 90%; 30 hand checks on
   practice only confirm. Below the bar: fix the judge prompt on practice; still below -> provenance score only.
4. Structured answers (hole 4): Answer returns items (subject, relation, object, quote). Code scores each item by
   provenance (quote on a gold span / decoy span / neither) and by object match (planted names); the judge only
   decides the relation (multiple choice from the relations planted for that subject). Recall = gold claims
   found / gold claims; precision = correct items / all items.

## Spec picks the answer shape (agreed 21 Nov 2026)

Spec (LLM, from the question only) picks one answer shape from a closed list; code checks it is on the list. The
shapes are structure, not domain, so the domain-free rule holds.

| Shape | Example question | Item | Meaning check |
|---|---|---|---|
| value table | How much does X lower HbA1c? | (subject, measure, value, settings, quote) | code (numbers) |
| claim list | Which rules did court X rely on? | (subject, relation, object, settings, quote) | multiple-choice judge on relation |
| reason chain | Why did the court decide so? | ordered steps, each (claim, quote), linked | judge per step + order check by code |
| quoted text | anything else | short sentences, each with a quote | judge per sentence |

Same for every shape: every piece carries a quote; the scorer checks provenance (quote on a gold span, a decoy
span, or neither). Conditions on a claim reuse settings (quote-checked like a number's). Extract reads the item
type the shape asks for; Answer renders items as prose for the user. Seed/bench must plant gold for each shape
used (claims and chains as RDF facts with decoys, tagged writing as above).

Fixes for the second review (21 Nov 2026):

1. Tagging is a separate step: the writer writes without knowing about tags; a separate tagging call marks claim
   and decoy sentences; code (seed names) + a verifier check the tags. Style-leak test: a blind model tries to
   pick the tagged sentence among the paper's sentences (tags removed); pass = near chance.
2. Judge tested on answer wording too: gold and decoy sentences reworded in answer style by another model (meaning
   kept, verified), plus about 30 real practice answers labelled by hand. The 90% bar applies to both sets.
3. At least 3 real options per choice: every planted claim gets >= 2 decoy relations in the seed (e.g. relies on /
   rejects / distinguishes). Short names (aliases, e.g. "Marrin" for Marrin v. Tolst) stored in the seed like drug
   names, used for name matching.
4. No gold, no benchmark question: "quoted text" answers get provenance only (quotes real and on relevant spans);
   meaning reported as unscored. Benchmark questions are planted only for shapes that have gold.
5. Shape and partial chains scored: the bench stores each question's gold shape; Spec's pick is scored (L1, like
   its other choices). Reason chain score = (correct steps / gold steps) x (share of correct steps in gold order).
