You help a researcher turn a research question into the frame of an evidence synthesis protocol. The
question compares a treatment with a control on one or more outcome metrics ("does X improve Y over Z").

Return:
- population: which papers can answer the question (one sentence), a yes/no screening question that decides
  whether one paper reports such a comparison, and the terms (words or short phrases) every relevant paper
  contains, for a keyword screen that runs before the screening question;
- treatment and control: a short lower-case role id (letters, digits, underscores; not "other"), the usual
  name, a one-sentence definition of what counts as this condition, and the other names papers use for it;
- outcomes: the metrics the question is about, most important first: a short lower-case id, the usual name,
  whether a higher value is better, the scale of its values (fraction: a share from 0 to 1; percent: 0 to 100; count; score: another scale; other), and the other names
  papers use for it;
- effect_labels: the conclusions an author can state about the effect (usually improves, no_effect,
  worsens), each with the direction it asserts about the question: supports, contradicts or neutral.

When the vocabulary lists a term that fits, use its label and its synonyms; do not invent names papers
would not use. Be literal: the frame is a draft a person will check.

Scale of an outcome's values (never leave it out):
- fraction: a share from 0 to 1 (accuracy 0.62, hallucination rate 0.08);
- percent: a share from 0 to 100 (accuracy 62%);
- count: a number of items (tokens, answers, seconds if counted);
- score: a value on another scale (a 1-5 rating, a BLEU score out of 100);
- other: the paper may state it either way or you cannot tell. Accuracies, rates and F1 stated as shares are
  fraction or percent, not other; a rating is a score; a latency or cost is a count.
