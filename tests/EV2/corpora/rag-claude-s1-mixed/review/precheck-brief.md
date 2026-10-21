# Pre-check of a fidelity review sheet

You pre-check rows of a review sheet for synthetic research papers. A human then reviews the rows you flag and a random
sample. Your answers are labelled as a model pre-check. Be careful and honest: flag anything you are not sure of.

## Input

You get a batch file (JSON) with two parts:

- `papers`: paper id → absolute path of the Markdown paper. Read every paper in full with the Read tool.
- `rows`: one row per place where a planned fact appears in a paper. Each row has:
  - `exact`: the text found there, at line `line`;
  - `context`: about 40 characters on either side, with the text marked `[[like this]]`;
  - `kind`: `measurement`, `author_claim`, `condition` or `metric`;
  - `truth`: what the ground truth says this text should express.

`truth` reads in one of these forms:

| kind | Form of `truth` |
|---|---|
| measurement | `<role> '<condition>' / '<metric>' / <dataset> = <value as a fraction>` |
| author_claim | `author claim: <direction> (data: <direction the numbers show>)` |
| condition | `condition, role <role>: '<label>' (also <aliases>)` |
| metric | `metric <canonical>: '<name>'` |

## For each row, decide three checks

Answer each check with `y` or `n`.

- `present`: the text `exact` is at that place in the paper. The code already confirmed that the exact string is at the
  recorded offset, so this is `y` unless the paper text clearly differs.
- `states_truth`: in its sentence or table cell, the text says what `truth` says.
  - **measurement:** the value belongs to that condition, that metric and that dataset. A percentage is the fraction ×
    100 (`29.5%` = 0.295). `571 out of 1,000` = 0.571. A relative value such as `6.7 percentage points higher than X`
    must give the truth value when applied to X's value in the paper.
  - **author_claim:** the sentence states that direction (`improves` / `worsens` / `no effect`). In contradictory papers
    the claim disagrees with the numbers on purpose. Judge only whether the sentence states the claim direction given;
    do not judge whether the claim is correct.
  - **condition / metric:** the mention refers to that condition or metric, by its label or one of the listed aliases or
    codes.
- `unambiguous`: a careful reader could not take this text for a different fact. Examples that fail: the same number
  stated for two conditions; a value that could belong to two datasets; a name that could mean two systems.
  Abbreviations and codes defined earlier in the paper are fine.

Also give:

- `sure`: `true` or `false`. Use `false` whenever you hesitated.
- `note`: one short sentence when any check is `n` or you are not sure; otherwise an empty string. Also note anything
  wrong that you see nearby, for example a planted value repeated elsewhere or an invented extra number.

## Output

Write one JSON file with the Write tool, at the path given in your task:

```json
{"rows": [{"row": 2, "present": "y", "states_truth": "y", "unambiguous": "y", "sure": true, "note": ""}, ...]}
```

Write one entry for every row of the batch, in the same order. Do not change the papers or any other file, and do not
dispatch subagents. When you are done, reply with one line: how many rows you wrote, and how many have an `n` or
`sure: false`.
