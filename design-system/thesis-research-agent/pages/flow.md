# Page override: the question-first flow (`/flow/:qid/:step`)

Overrides MASTER.md for the flow pages (`webapp/web/src/pages/flow`, `src/components/flow`).

- **Stepper** at the top of every step: Question, Protocol, Corpus, Run, Evidence graph, Answer. Done steps show a
  check and the chosen value; the current one has `aria-current="step"`, a teal ring and bold label. Below `md` the
  labels are hidden behind numbers and a line "Step n of 6: <label>" says where you are.
- **One heading per step** (`h2`, 18 px semibold) with one sentence of what to do; the step's primary action is the
  only filled (teal) button on screen.
- **Step footer:** Back to the previous step, Next to the following one; Next is off, with the reason beside it,
  until the step's choice is made.
- **Cards form:** each card has a visible label per field, the reason marked required, errors under the field,
  and the checker's problems for that card shown inside the card. The checker panel links each problem to its card
  (opening the advanced fold when needed). Save and Freeze stay in a sticky bar under the cards.
- **Waiver:** names the card and the problem in words, says that waiving does not fix it, that the reason is saved
  in the user's name, and that freezing is one-way; counts the characters of each reason.
