# Question planning: main question → sub-questions → protocol (draft, 2 Nov 2026)

Status: draft for Aditya to review. Not approved, nothing built.

## Why

Today a question is answered only if someone hand-wrote its protocol, or if it fits the propose flow
(`evidence/propose/`), whose frame always asks for a treatment and a control. So planning is either manual or
comparison-only. Aditya's flags on the EV4 map (2 Nov): "keep it general, not only comparisons", "a small agentic
loop rather than hard-coded values".

Goal: a user types one main question, works with the system on a short list of sub-questions, and gets a
protocol that collects the evidence for each. Easy for the user, general across question types, and still
scoreable against the answer key.

## The flow

1. **Main question.** The user types it.
2. **Sub-questions proposed.** One model call returns 3–6 sub-questions. Each is one evidence need, and each
   is tagged with one of the registered kinds (`effect`, `consistency`, `best`, `inventory`, `chaining`,
   `limitations`, `builds_on`) or `unsupported`, with a one-line reason.
3. **User edits the list.** The user adds, deletes, rewrites or reorders sub-questions, and marks one as the
   **headline**: the sub-question whose answer is the main answer. A sub-question the user types is tagged by
   the same call (step 2, given only that sub-question).
4. **One protocol piece per sub-question.** For each supported sub-question, the kind's frame fills only the
   fields that kind needs (no treatment/control for `limitations` or `inventory`). `draft` turns it into
   protocol YAML as it does today.
5. **Check and repair.** Code validates each piece (schema, enums, kind's required fields, screen terms not
   empty). If a check fails, a repair call gets only the failed piece and the failed checks. At most 3
   attempts; every attempt is kept. Still failing → the sub-question is shown as "could not plan".
6. **Independent review.** A second model (the critic) gets the main question, the sub-question list and each
   piece's plain-language effect. It does not see the generator's reasoning. It flags sub-questions that do
   not serve the main question, or a wrong kind.
7. **Approve and freeze.** Cards per sub-question (the existing card flow), then the protocol is locked
   (`protocol.lock.json`).

## The answer

- Each sub-question is answered by its kind's fixed rule, exactly as today.
- The main answer is the headline sub-question's answer. The other sub-answers are shown under it as
  supporting evidence, each with its own trace.
- No free-text model synthesis of the main answer. That keeps extraction errors and synthesis errors apart
  (Tim, M2 §5) and keeps every sub-answer scoreable.
- `unsupported` sub-questions stay visible as "not answerable yet" and are counted. This is the list of kinds
  to add next.

## Added 2 Nov (agreed with Aditya)

1. **"What would prove it?" first.** Step 2 asks the model for the evidence that would settle the main question
   (Tim's influence example: contributions, who built on them, impact), each phrased as a sub-question.
2. **Main-answer rule.** Replaces "headline = main answer". The user picks and approves a decision rule over
   the sub-answers from a small fixed set (e.g. "yes if at least 70% of studies show a gain on the same
   metric"). Code applies it; the rule's truth is computed from the answer key, so the main answer is scored.
3. **Oversell check, always on.** Every plan with an `effect` or `consistency` sub-question gets one more:
   "do the authors' conclusions match their numbers?" (Tim M2 §7).
4. ~~Learn from a pilot run~~ dropped 2 Nov: no pilot run. Tim (reported by Aditya, 2 Nov) is fine with an
   empty answer. A sub-question that finds nothing gets an empty sub-answer, shown and counted as
   "no evidence found", never retried or patched mid-run.

## Building blocks instead of fixed kinds (agreed 2 Nov)

The 7 kinds become 7 ready-made chains of a small set of building blocks: find (an evidence type, with
fields), keep (filter), group (by a field or name group), count, compare (A vs B on one metric), and test
(A > B, share ≥ threshold). For each sub-question the model writes a chain (typed JSON, one block per step).
Code checks it (each block's inputs match the previous block's output) and runs it. The user sees each chain
as plain sentences on its card, never as code. The main-answer rule is a chain over the sub-answers.

Scoring stays automatic: the same chain runs on the answer key's items to compute the expected answer.
Risk: a chain that runs but does not answer the question; the critic and the user's card approval must catch it.

## One page, rule not asked (agreed 2 Nov, supersedes the screens above)

- One page. The user types the question and presses Plan; the evidence lines appear below it. Each line has ×
  (remove) and "how?" (its steps as sentences, closed by default). The oversell line has no ×. Run fills each
  line with its result in place; empty results read "No evidence found".
- The user is never asked for the main-answer rule. The system picks a default from the question (for "does X
  improve Y": most comparisons show a gain). It is shown only next to the answer, as one line with "change".
- Card approval is no longer a separate step: pressing Run on the plan is the approval; the plan is frozen then.

## Human in the loop (agreed 2 Nov, Tim wants a human involved)

Grounded in Tim: the plan is "refined through interaction with the user" (M1) and protocol generation may
involve "a dialogue with the user to clarify methodological decisions" (M2 §2); "much like a protocol in a
systematic review" (M1).

- **Clarifying question.** After Plan, when the question is ambiguous, the system asks at most one or two
  multiple-choice questions first (e.g. what "factual accuracy" means here). The answer is recorded.
- **Decisions panel.** Beside the evidence lines, the methodological decisions the system defaulted, each in
  one line with its reason: which papers count, what the baseline is, which metrics count, the smallest gain
  that counts, the main-answer rule. Each is Confirm or Change; "Confirm all" is one click. Run stays disabled
  until every decision is confirmed. This replaces "the rule is never asked": the rule is a default the human
  confirms, not a question they must answer.
- **Protocol record.** After the run, the panel becomes a record: each decision, who confirmed it and when,
  and the clarifications. It is saved with the frozen protocol.

## Rest of point 1: numbers, records, chaining (proposed 2 Nov, shown in the mockup, not yet agreed)

- **Read numbers.** Code finds every number and its sentence (general). The model labels each number's role
  from a fixed list taken from the protocol's fields (result, sample size, time point, dose, statistic, other)
  and quotes the words that show it. Code checks the number is in the text and converts units. Only results
  are used; time point and dose become conditions. No per-topic switches.
- **Make records (replaces "build claims").** Every result becomes one general record: trial, arm, what was
  measured, value, conditions, source span. Author statements (claims, limitations, builds-on) are records
  too. No answer shape is assumed; the blocks (compare, count, chain) read records.
- **Connect through shared comparators (replaces A>B>C chaining).** When no direct comparison exists, find
  every comparator both sides were tested against (a path), under the conditions the user confirmed must
  match (outcome, week, population). Each path gives a number (difference of differences); paths are
  checked against each other: agreeing → answer marked indirect; disagreeing by more than the smallest
  difference → "conflicting". Records that fail the match rule are listed as not used. New decision card:
  "What must match to compare through a shared drug".

## Robustness review (3 Nov)

- **Dropped: "answer blanks first".** Fixing the answer's shape before planning goes against Tim ("we no longer
  need to define the complete graph structure at the beginning", M2 §2), and an evidence line that finds
  nothing is an acceptable empty result, not a bug.
- **Dropped as a new fix: different names for one outcome.** The funnel's LLM and agent read meaning
  ("50% drop in score" = response); the names step (D38, `evidence/names.py`) groups spellings. Remaining gap:
  the funnel asks the LLM only where regex found nothing, so a regex find with a wrong label is never
  re-checked. Measured by extraction accuracy on paraphrased papers (M2 §5A, §6).
- **Agreed: prompts written by DSPy.** Every model step (planner, number labeller, extractor, critic) is a DSPy
  signature (typed inputs and outputs); prompts are written and tuned by a DSPy optimizer (GEPA or MIPROv2)
  against a score from the synthetic answer key, not by hand. Tuning papers and test papers are kept apart,
  so the scores and the baseline comparison stay fair. Validators and the held-out evaluation stay fixed
  (`docs/prompt-writing.md`).
- **Agreed: D40 narrowed, no model labelling of every number.** The existing funnel stays: screen drops
  unusable papers, code reads every number (`numreader.py`) and links it to its condition and metric
  (`numbers.py`), the model fills gaps. One change: the model also re-checks what regex and code found, one
  paragraph per call, not one number per call.
- **Agreed: answer sensitivity to decisions (general, any field).** Replaces fixed match rules in D41.
  1. Four decision types, the same in every domain: *must-match* (which condition fields must be equal to
     compare or connect two results), *counts-as* (which metrics, baselines or measures count), *threshold*
     (smallest difference that counts), *include* (borderline papers or items). The human confirms the main
     setting of each in the decisions panel.
  2. Code derives the alternatives, ordered strict → main → loose: must-match drops or adds one field;
     counts-as removes or adds one value; threshold uses 0, main, 2× main. No alternatives invented per domain.
  3. Papers are read once and nothing is filtered at extraction (records keep all conditions); synthesis code
     reruns per setting, one decision at a time.
  4. Labels by code: solid / same direction / depends on X / too few to tell (under a minimum count). Only
     settings that flip the answer are shown. Every unused record carries its reason; records used only
     under a loose setting are tagged "indirect on: <field>". An empty answer comes with its reasons.
  5. Scoring: the answer key runs through the same settings, so each setting and label is scored;
     extraction and synthesis errors stay apart (M2 §5).
  6. Optional, exploratory, unscored: a split table of the answer by each condition field.
  Examples. RAG: main setting 9 of 12 comparisons favour RAG; dropping models under 7B gives 5 of 9 → "depends
  on model size". Best author: main "most built on" gives Chen 12 vs Rossi 9; any author position still Chen;
  counting papers gives Rossi 7 vs Chen 5 → "Chen, depends on what best means".
  Sources: multiverse analysis (Steegen et al. 2016), specification curve (Simonsohn et al. 2020), garden of
  forking paths (Gelman & Loken 2013), Cochrane Handbook ch. 10 (sensitivity, pre-specified subgroups),
  GRADE indirectness (Guyatt et al. 2011), benchmark lottery (Dehghani et al. 2021). Rough cost 3–5 days.
- **Agreed: flagged decisions and independent evidence lines.** Before Run the critic flags the 1–2 decisions
  it doubts, each with a reason, highlighted in the panel; "Confirm all" confirms every decision, flagged
  ones included (a careless confirm is caught after the run by the reruns). Each evidence line runs on its
  own; a crashed line shows "failed: <reason>", the answer is computed from the other lines and labelled
  "missing: <line>", and is scored like an empty answer. Mockup: "Best Author Run" artifact
  (https://claude.ai/artifact/2GQWhcw9wFxRboUzbdje2T).
- **Prior art (search 3 Nov, preprints unverified):** otto-SR, TrialMind, Manalyzer (LLM systematic reviews,
  medical); DocETL (YAML pipelines over documents); MetaMind (indirect comparison, medical); MetaSyn
  (stage-wise scoring on real meta-analyses); PaperQA2 (answer-level baseline). Looks new: a synthetic corpus
  generated from ground truth with tunable difficulty, synthesis reruns under decision settings, and the whole
  loop outside medicine. Must cite otto-SR, MetaSyn, PaperQA2; re-check the synthetic-corpus novelty claim.
- **Agreed: more labelled datasets from other fields.** Today: synthetic RAG corpora (tests/EV1, tests/EV2;
  answer key by construction), SciREX (names), SciLead (values, rankings), Yun + Evidence Inference (trial
  records); arXiv has no labels. Add: CochraneForest (Pronesti et al., ACL 2025; 202 forest plots from 48
  Cochrane reviews with question, study full texts and conclusions; the first real-paper check of a whole run,
  question to answer; check licence and release), SOFC-Exp (Friedrich et al., ACL 2020; 45 materials papers,
  Material/Value/Device slots with units), MeasEval (Harper et al., SemEval 2021; quantities, units, measured
  entity and property; whether it spans several fields is unverified).
- **Agreed: ontology decided now, one public standard per field, loaded by code, none hand-written.**
  Computer science (RAG, SciREX, SciLead): CS-KG, as today. Medicine (Yun, CochraneForest): MeSH. Units in
  every field: QUDT (our call); materials (SOFC-Exp) uses QUDT only.
- **Agreed: no hand-typed topic words; the LLM writes the regex words.** Problem: screen, regex and number
  reading find only what a person typed into `domains/<name>/words.yaml` (rag: 134 lines; ml: almost empty),
  so a new field does nothing until someone types its folder. Fix: (1) one LLM call (a DSPy step) per
  question writes a long list, 20–50 other names, spellings and abbreviations for each thing the plan asks
  about, from the question alone, without reading the test papers; (2) the ontology's other names (MeSH entry
  terms, CS-KG labels) are added; (3) code turns the list into screen and regex words; (4) the list shows as
  decisions in the planning panel, the human confirms, and it is locked with the run. A long list also
  catches wrong things, so the funnel's LLM re-checks every regex find (now required, not optional); names
  the list misses are left to the funnel's LLM and agent steps. GLiNER labels come from the plan's building
  blocks. No sentence transformer (considered and dropped 3 Nov; the 1 Nov "no embedding-based retrieval"
  note stands).
- **Agreed: word leak made visible.** Problem: the synthetic papers take their names from
  `domains/rag/generator.yaml`, typed by the same hands as `words.yaml`, so regex finds them by construction;
  an LLM-written word list from the same model as the paper writer would share its favourite words. Fix:
  (1) the word list is written by a different model family than the papers (Claude writes the papers); an
  exception to the 16 Oct "same model for all" rule, agreed 3 Nov; (2) each answer-key name is marked "on
  the list" or "unseen" (not in the locked word list), and scores are reported for both groups; (3) the main
  claim rests on the real labelled sets (CochraneForest, SciREX, SciLead), which cannot leak; synthetic
  papers show which difficulty breaks the system.
- **Agreed: whole-run scoring on real papers.** Problem: only synthetic papers have an answer key for a whole
  run (question to answer); real sets score one part each (names, values, trial records). Fix: code turns each
  real labelled set's records into questions with known answers, and the whole run is scored on them.
  (1) SciLead (computer science): each of the 27 leaderboards becomes "which method is best on dataset X by
  metric Y?", answer = the leaderboard's top and order. (2) SciREX (computer science): its labelled relations
  become "which datasets are used for task T?" and the like, answer = the labelled list. (3) CochraneForest
  (medicine): its own question, studies and conclusions. (4) SOFC-Exp (materials): "which material gives the
  highest Z?" from the labelled values; check first that the labels are complete enough. (5) Synthetic
  corpora stay for controlled difficulty. Limit: only the question kinds the labels support.
- **Agreed: ontology never silent, gaps filled by the LLM.** Problem: without a tree the reasoning step
  switches off without a word; fields with no standard tree (maths, parts of social science) and new names
  (a 2026 model) get no grouping. Fix: (1) every run shows the tree it used or "reasoning off: no tree", and
  counts found names with no place in it; (2) for a name missing from the tree the LLM proposes a parent
  ("Llama 3 is a kind of LLM"; board card h02: invent only with a parent); (3) a field with no tree gets a
  small tree built by the LLM from the run's found names only, marked "made by LLM"; (4) answers that use an
  LLM-made link are labelled. Our call: the new links are found during the run, so the human checks them
  after the run in the result (accept or reject, then synthesis reruns, no new reading), not in the planning
  panel; links from the question's own words can be shown before the run. Each question is scored with
  reasoning on and off, so reasoning errors stay apart from extraction errors (Tim M2).
- **Agreed: real papers are not clean.** Problem: Docling's PDF tables can come out scrambled (values under the
  wrong column), and `evidence/rules.py` `duplicates` treats equal value pairs as one study (true only for
  the generator), while real papers report many experiments. Fix: (1) structured source first: arXiv LaTeX
  source, PubMed Central XML (exact table cells), then arXiv HTML, then Docling on the PDF; (2) PDF tables are
  read by two separate table tools (Docling and a second one, e.g. pdfplumber); when they disagree the value
  is marked "table unsure"; no vision model (Aditya, 3 Nov); (3) one LLM step per paper first lists its
  experiments ("exp 1: dataset A, model X"), and every number is attached to one experiment; this replaces
  the duplicate guess, and SOFC-Exp's experiment frames score the step; (4) code checks every value against
  the source text or cell, else drops it; (5) two new generator difficulty settings: several experiments per
  paper, and messy tables.
- **Agreed: scope of synthetic papers and scale.** The generator stays RAG comparisons only and is not
  widened; other question kinds and fields come from the real labelled sets (SciLead: rankings; SciREX:
  lists; CochraneForest: comparisons with effects; SOFC-Exp: rankings). No 10k-paper target: the scale is
  the size of the external labelled sets.
- **Agreed: the answer is a SPARQL query the plan writes.** Problem: the answer rules are fixed per kind:
  `evidence/kinds/best.py` ranks method kinds typed in advance by wins inside each paper, and
  `evidence/kinds/inventory.py` lists every item with no "for task T" filter, so SciLead (rank methods
  across papers on dataset X by metric Y) and SciREX (datasets used for task T) would be answered by the wrong
  rule. Fix: (1) every record goes into one graph with its links (paper, experiment, dataset, value, source
  sentence) and the ontology; (2) a DSPy step writes a SPARQL query for the question, shown in the planning
  panel for the human to confirm; it may filter, group, count, sort, join or take a maximum, and "kind of"
  comes from the ontology (rdfs:subClassOf*); (3) code runs it, the query is locked with the run and replays;
  (4) the same query also runs on the answer key's records: wrong there = synthesis error, right there but
  wrong on ours = extraction error (Tim M2). Scoring: rankings by top-1 and Kendall tau, lists by precision
  and recall. Our call: today's kinds (effect, best, inventory, consistency, chaining) become saved query
  templates the DSPy step starts from (board Maybe cards h03 SPARQL and g06 query templates, Aditya said yes
  3 Nov); a step SPARQL cannot express stays code, called after the query.
- **Agreed: author claims are general records.** Problem: a claim is found only when it matches the rag
  pack's `claim_subject` ("retriev…|RAG"), and its meaning is read by typed patterns (`claims` in
  `domains/rag/words.yaml`) into improves / worsens / no_effect, with RAG words (hallucination, factual) in
  them; claims in other fields and claims that are not comparisons ("X is the state of the art", "Y depends
  on Z") are lost. Fix: (1) the subjects come from the LLM-written word list (the plan's things), and the
  LLM also writes general claim cue words ("we show", "outperforms", "we conclude"); regex finds candidate
  sentences, the LLM confirms each (funnel); (2) a claim record is subject, relation, object, setting and
  strength (firm or hedged: "shows" vs "suggests"), open, not three labels; (3) a comparison claim also maps
  its relation to improves / worsens / no_effect, so today's checks and synthetic RAG scoring keep working;
  (4) claims go into the graph; the oversell check is a saved SPARQL query comparing a claim with the values
  of the same experiment; (5) scored on CochraneForest conclusions, and on the three labels in synthetic RAG.
- **Agreed: links between studies are graph paths (D41 settled).** Problem: `evidence/kinds/chaining.py`
  reads only two-sided comparisons (comparisons.json, RAG vs baseline) and chains steps whose settings
  differ (A vs B on dataset X with B vs C on dataset Y); `evidence/kinds/builds_on.py` resolves a cited
  label by name to a paper of the run only (others dropped) and "reuses" has three fixed values. Fix:
  (1) any two values of the same experiment (point 5's experiment map) on the same metric make a comparison
  edge carrying the experiment's setting, for any two things; (2) "A vs C through B" is a SPARQL path query
  that keeps only steps whose settings match on the must-match fields the human confirmed; this adopts the
  2 Nov "connect through shared comparators" proposal: agreeing paths give "indirect", disagreeing ones
  "conflicting", and the decision reruns show looser and stricter matching; (3) builds-on resolves a citation
  by DOI or arXiv id through OpenAlex; a cited paper outside the run stays in the graph marked "outside the
  set"; (4) "reuses" is an open relation (subject, relation, object), like claims; (5) scoring: the synthetic
  truth network for chaining; OpenAlex's reference list for which cited papers builds-on found.

## Scoring

Each supported sub-question is scored against the answer key with its kind's truth, as one question is today.
A main question's score is its sub-scores side by side, not one blended number.

## What changes in code (rough)

- `evidence/propose/frame.py`: one frame schema per kind instead of one compare-pair frame.
- New step `split` before `frame`: main question → tagged sub-questions.
- A protocol holds a list of sub-questions, each with its own kind and evidence types; or one protocol per
  sub-question bundled under the main question (builder's call; the bundle is simpler).
- Web app: a sub-question list editor before the cards, and a pilot-run view.

## Goals, non-goals

- Goals: easy start (the model suggests, the user edits); general across the registered kinds; scoreable.
- Non-goals: inventing a new kind on the fly; model-written main answers; embedding retrieval (D-board, 1 Nov).
- Anti-goal: a plan that looks complete but silently drops a sub-question. Every dropped or unsupported one is
  shown.

## Fit with Tim

Tim made LLM protocol generation an optional extension (M2 §8) and asked for "a complete vertical slice"
first (M2 §9). This design is that extension. It keeps his fixed-rule synthesis and separate scoring. Risk:
scope creep before EV4 is done.

## Open for Aditya

1. Is "headline sub-question = main answer" enough, or should the main answer combine sub-answers by a fixed rule?
2. Build it now, or after the EV4 run?
