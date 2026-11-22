# Guidelines for the Markdown paper (evidence synthesis)

- Genre: {PAPER_TYPE}. It pools what earlier {SUBJECT_PLURAL} reported; it runs no new experiment. Every
  {SUBJECT_KIND} is named; its setup, results and the pooled values come only from `experimental_log.md`.
- Output: one Markdown file. No LaTeX, no HTML, no images, no figures.
- Length: {PAGES} printed pages, which is about {WORDS_LO} to {WORDS_HI} words.
- Structure: keep the level-1 title and the level-2 sections of `template.md` in their order. Level-3
  subsections are allowed. Do not add other level-2 sections.
- Abstract: one paragraph of 150 to 250 words that names the {SUBJECT_PLURAL} the paper pools and gives the main
  pooled value.
- Tables: at least {MIN_TABLES} Markdown tables, built as `experimental_log.md` section "Tables to build" says, each
  with a caption line ("Table 1: ...") directly above it and the unit in the column header. Every number in a table
  comes from the log, exactly as written there (same digits and decimals). Pooled values are given in the log: copy
  them, never compute your own.
- Sources: name each {SUBJECT_KIND} in full the first time (as `experimental_log.md` gives it), later by a short
  name. Describe each source only with the details the log gives (its summary and attributes); never add a detail,
  a number, a design feature or a result that the log does not give.
- {FACTS_CAP}: state what each {SUBJECT_KIND} found for each object with exactly the meaning the log gives, in your
  own words. Every {FACT} listed in the log must be stated at least once and at most {MAX_MENTIONS} times in prose.
- Citations: name the {SUBJECT_PLURAL} in the text; no reference list, no `[1]`, no author names other than the
  study names, no real papers.
- Anonymity: no author names, affiliations, funding or acknowledgements.
{STYLE_CARD}
