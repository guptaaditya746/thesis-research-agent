I am a master's student. Teach me evaluation metrics for my thesis system, step by step, using MY real data below. I learn best from small worked calculations. Use plain words. Go one metric at a time and stop after each one so I can ask questions.

## My system (short)
A question comes in, for example "Does Alvenor improve blood pressure control compared with standard care?". The system:
1. screens a folder of 40 papers (keeps the ones it thinks are relevant),
2. extracts structured facts from the kept papers, each with an exact quote (a "pulled fact"),
3. links them into a graph (which number belongs to which drug, patient group and measure),
4. synthesises an answer (better / worse / papers disagree) with a rule.

## My test data (synth3)
The papers are synthetic: we planted a hidden truth (ground_truth.json) into them, so we know every true fact. Example planted facts for paper S010:
- Standard care, older adults, normal kidney, blood pressure control: 172 of 400
- Alvenor, same group: 223 of 400
- Standard care, older adults, reduced kidney: 165 of 400
- Alvenor, reduced kidney: 217 of 400
- The authors say Alvenor does better than standard care on blood pressure control
- The study ran at Northgate Heart Cohort
Blood pressure control: higher is better.

Example pulled fact from the system (one JSON item):
{"evidence_type":"measurement","fields":{"dataset":"Older adults, Normal kidney function, University hospital","form":"k_of_n","value":172.0},"spans":[{"quote":"| Older adults, Normal kidney function, University hospital | Standard care | Blood pressure control | 172 | 400 |"}]}
For S010 the system pulled 19 facts in total.

Folder-level numbers for question m01 (seed 1): 9 papers hold 44 planted facts. The screen rejected 6 of the 9 papers, so nothing was pulled from them. From the 3 papers it read, 11 of 16 planted facts were found. Of those 11, 0 were tied to the wrong group.

The system's final answer for m01:
"alvenor against standard care on blood pressure control: the papers disagree.
Papers that show it better: S019. Papers that show it worse: S010, S015.
Papers that could not be read: S001, S002, ... (37 papers)
S010: worse on blood pressure control (223 against 172)."

The answer sheet (true conclusions, made from the hidden truth):
- p1 Alvenor gives better blood pressure control than standard care. (7 studies say better)
- p2 In younger adults, Cardivel is worse than Alvenor.
- p3 In older adults, Cardivel and Alvenor show no real difference.

## What my supervisor asked for (his words)
A. Evidence extraction: "how accurately and completely the system reconstructs the underlying experimental evidence. Relevant metrics include precision, recall, F1, correct association of measurements with experimental conditions, and the accuracy of evidence provenance."
B. Evidence integration: "whether evidence from different sections or documents is correctly connected. For example, a paper might describe the experimental conditions in one section and report the corresponding measurements in a table elsewhere."
C. Evidence synthesis: "Since we know all the underlying experimental results, we can independently calculate the expected synthesis. We can then evaluate whether the system reaches the correct conclusions from the extracted evidence. Importantly, this also allows us to distinguish extraction errors from synthesis errors."

## What I actually measured so far (an LLM judge)
- "A" = planted facts found / planted facts (recall only). m01: 11/44 = 25%.
- "B" = claims in the answer supported by the system's own pulled facts / all claims (faithfulness). m01: 3/44.
- "C" = answer-sheet points met / points. m01: 0/3.
I suspect these do not match what my supervisor asked for, and that I am fitting metrics to what I have instead of the other way round.

## What I want from you
For each metric below:
(a) what question it answers, in one sentence;
(b) the formula;
(c) the actual steps to calculate it, from inputs to number, done by hand on MY data above;
(d) what it needs as input (what gold data, what system output) and whether my data has it;
(e) one way it can mislead.

Metrics, in this order:
1. Extraction precision, recall, F1. Explain how a pulled fact is "matched" to a planted fact (what must agree: drug, group, measure, value?), and what to do with extra true facts that are not in my planted list (my medicine papers are real papers with planted edits, so they contain real results we did not plant).
2. Triple F1, where a triple is (condition, measure, value). Compare with plain F1 from 1.
3. Association accuracy (is each matched number tied to the right condition and measure). Explain why it is computed only over matched facts.
4. Provenance accuracy (does the quote really support the fact).
5. Integration (B): how to measure that facts from different sections or papers are connected correctly, with an example from my data.
6. Synthesis (C), computed two ways: (i) against the true conclusion, (ii) against the conclusion an independent calculator would reach from the system's OWN extracted facts. Show with m01 how (ii) separates extraction errors from synthesis errors. Note: S010's numbers are 223 vs 172 and higher is better, yet the answer says "worse"; tell me which kind of error that is.
7. Finally: compare my current A, B, C with 1-6 and tell me honestly which current ones fit my supervisor's plan, which do not, and what the smallest correct set would be.

Start with metric 1 only.
