# Guidelines for the Markdown paper (argument genre)

- Genre: {PAPER_TYPE}. It makes a case for one thesis by analysing sources ({SOURCE_KINDS}), not by reporting a
  new experiment.
- Output: one Markdown file. No LaTeX, no HTML, no images, no figures.
- Length: {PAGES} printed pages, which is about {WORDS_LO} to {WORDS_HI} words.
- Structure: keep the level-1 title and the level-2 sections of `template.md` in their order. The Introduction
  states the issue and the thesis. Level-3 subsections are allowed inside a section. Do not add other level-2
  sections.
- Abstract: one paragraph of 150 to 250 words.
- Tables: at least {MIN_TABLES} Markdown tables, built as `experimental_log.md` section "Tables to build" says, each
  with a caption line ("Table 1: ...") directly above it and the unit in the column header. Every number in a table
  comes from the log, exactly as written there.
- Sources: name each {SUBJECT_KIND} in full the first time (as `experimental_log.md` gives it), later by a short
  name; cite a {SUBJECT_KIND} with its court and year in brackets. Describe each source only with the details the
  log gives (its summary and attributes); never add facts, reasoning, quotations or parties the log does not give.
- {FACTS_CAP}: state what each {SUBJECT_KIND} did with each source with exactly the meaning `experimental_log.md`
  gives, but in your own, varied words. Never reuse one fixed phrase for several {FACTS} and never copy the log's
  wording. Never invent a {SUBJECT_KIND}, a source or a {FACT}, and never change who did what.
- Every {FACT} listed in `experimental_log.md` must be stated at least once and at most {MAX_MENTIONS} times, in
  prose.
- A court is bound only by courts above it: say so when a lower court departs from a higher one.
- References: no reference list, no citations of scholarly work, no author names.
- Anonymity: no author names, affiliations, funding or acknowledgements.
{STYLE_CARD}
