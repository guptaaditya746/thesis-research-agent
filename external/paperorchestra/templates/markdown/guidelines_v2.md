# Guidelines for the Markdown paper, v2 (21 Nov 2026; v1 is guidelines.md)

- Output: one Markdown file. No LaTeX, no HTML, no images, no figures.
- Structure: keep the level-1 title and the level-2 sections of `template.md` in their order:
  Abstract, 1. Introduction, 2. Related Work, 3. Methods, 4. Results, 5. Discussion, 6. Conclusion.
  Level-3 subsections (`### 3.1 ...`) are allowed in Methods and Results only. Do not add other level-2 sections.
- Length of each section (words, tables not counted):
  Abstract 180-250 (one paragraph); Introduction 300-450; Related Work 150-250 (no subsections);
  Methods 250-450; Results 150-350 plus the tables; Discussion 450-650; Conclusion 40-90.
- Tables: GitHub Markdown pipe tables. Put a caption line directly above each table, e.g. `Table 1: ...`.
  Give the unit in the column header (e.g. `Change in weight (kg)`) or next to each value. Number tables in order
  and refer to each table in the text.
- References: there is no reference list and no citations in this paper. Do not write `[1]`, `(Author, year)`,
  `\cite{}`, author names of other work, or a "References" section.
- Anonymity: no author names, affiliations, funding, acknowledgements, registration numbers or e-mail addresses.
- Style: as in a peer-reviewed journal of the paper's own field: concrete, dense, each paragraph adds something new.
