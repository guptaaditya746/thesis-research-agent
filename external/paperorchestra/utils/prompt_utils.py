# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

UNIVERSAL_NO_LEAKAGE_PROMPT = """
---
### Strict Knowledge Isolation & Anonymity (CRITICAL)

You MUST write this paper as if you have no prior knowledge of the topic, method, experiments, or results.
Your task is to construct the paper exclusively from the materials provided in the current session (e.g., idea.md, experimental_log.md, figures, and other inputs). Treat these inputs as the only available source of information.

#### Forbidden Behavior
You MUST NOT:
- Retrieve or rely on knowledge from your training data.
- Attempt to recall or reconstruct any existing or published paper.
- Use external facts, assumptions, or prior familiarity with the work.
- Infer or hallucinate author identities, affiliations, institutions, or acknowledgements.
- Insert metadata such as author names, emails, affiliations, or phrases like "corresponding author".

#### Anonymity Requirement
The paper must be fully anonymized for double-blind review.  
Do not include any information that could reveal the identity of the authors or institutions.

#### Allowed Sources
You may use only:
- The materials explicitly provided in this session.
- Logical reasoning derived from those materials.

#### Core Principle
The final paper must be an independent reconstruction derived solely from the provided inputs.  
This constraint is strict and overrides all other instructions.
---
"""


# --- Added for the thesis vendoring (VENDORED.md, changes C3 and C5) -------------------------------------------

NO_CITATION_PROMPT = """
---
### No Citations (this paper has no reference list)
Write no citations of any kind: no `[1]`, no `(Author, year)`, no `\\cite{}`, no names of other authors, and no
"References" section. Describe prior work by its approach in general terms (e.g. "earlier trials of add-on
therapies", "first-principles screening studies") and never attribute a specific finding or number to it.
---
"""

FACT_RULE_PROMPT = """
---
### Values from experimental_log.md (HARD RULE, checked by code after you write)
Each result value in `experimental_log.md` has a row id, a value, a unit and a placement.
1. Write every value exactly as the log writes it: the same digits, the same number of decimals, the same sign,
   and the ASCII minus "-". Write -0.50 as "-0.50"; never "-0.5", "0.50 lower", "−0.50" or "-0.500".
2. Placement "table" ("put in a table"): put the value as a cell of a Markdown table. Give its unit in the column
   header or next to the value.
3. Placement "text" ("state in a sentence"): write "<value> <unit>" inside a sentence of the running text, e.g.
   "a mean difference of -0.57 pp". Do not put this value in any table.
4. Write no other result numbers: no values the log does not give, no confidence intervals, p-values,
   percentages, ratios, differences, averages or rankings computed from the values. Numbers that describe the
   setup (sample size, doses, durations) may be used only as written in `idea.md` or `experimental_log.md`.
5. Never write row ids (such as "R-xyz-01-02") in the paper.
6. If the log has no value for a combination, do not fill it in: leave it out or write "not reported".
7. Write as the study's authors. Never mention the input files, the "source materials", the log, row ids,
   placement rules, or which information was "not provided"; state limitations as limits of the study
   design (e.g. "dispersion measures are not reported here").

Examples (from an unrelated field trial; follow the rule, not the topic):
- Log: `R-agr-01-03 | -1.40 | t/ha | put in a table`
  Right: a table with the header `| Fertiliser rate | Yield change vs control (t/ha) |` and the cell `-1.40`.
  Wrong: `-1.4` (decimal dropped); "1.40 t/ha lower" (sign dropped).
- Log: `R-agr-01-04 | 0.85 | t/ha | state in a sentence`
  Right: "At week 20, the high rate changed yield by 0.85 t/ha relative to control."
  Wrong: 0.85 in a table; "0.85 tonnes per hectare" (unit rewritten); "+0.85 t/ha" (sign added).
- Missing: the log gives no value for the low rate at week 20.
  Right: leave that cell out or write "not reported". Wrong: estimating or computing a value.
---
"""
