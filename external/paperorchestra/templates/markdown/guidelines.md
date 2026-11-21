# Guidelines for the Markdown paper (thesis adaptation, replaces the CVPR/ICLR guidelines)

- Output: one Markdown file. No LaTeX, no HTML, no images, no figures.
- Length: 4 to 6 printed pages, which is about 2,400 to 3,200 words including tables.
- Structure: keep the level-1 title and the level-2 sections of `template.md` in their order:
  Abstract, 1. Introduction, 2. Related Work, 3. Methods, 4. Results, 5. Discussion, 6. Conclusion.
  Level-3 subsections (`### 3.1 ...`) are allowed inside a section. Do not add other level-2 sections.
- Abstract: one paragraph of 150 to 250 words.
- Tables: GitHub Markdown pipe tables. Put a caption line directly above each table, e.g. `Table 1: ...`.
  Give the unit in the column header (e.g. `Change in weight (kg)`) or next to each value. Number tables in order
  and refer to each table in the text.
- References: there is no reference list and no citations in this paper. Do not write `[1]`, `(Author, year)`,
  `\cite{}`, author names of other work, or a "References" section.
- Anonymity: no author names, affiliations, funding, acknowledgements, registration numbers or e-mail addresses.
- Style: formal, objective and precise, as in a peer-reviewed journal of the paper's own field.
