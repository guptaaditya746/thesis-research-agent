# Guidelines for the Markdown paper (argument genre)

- Genre: an argument paper ({PAPER_KIND}). It makes a case for one thesis by analysing sources ({SOURCE_KINDS}),
  not by reporting a new experiment. There are no Methods or Results sections, no data tables and no statistics.
- Output: one Markdown file. No LaTeX, no HTML, no images, no figures.
- Length: {PAGES} printed pages, which is about {WORDS_LO} to {WORDS_HI} words.
- Structure: keep the level-1 title and the level-2 sections of `template.md` in their order. The Introduction
  states the issue and the thesis. Level-3 subsections are allowed inside a section. Do not add other level-2
  sections.
- Abstract: one paragraph of 150 to 250 words.
- Sources: name each {SUBJECT_KIND} in full the first time (as `experimental_log.md` gives it), later by a short
  name. Name every source exactly as `experimental_log.md` does.
- {FACTS_CAP}: state what each {SUBJECT_KIND} did with each source with exactly the meaning `experimental_log.md`
  gives, but in your own, varied words. Never reuse one fixed phrase for several {FACTS} and never copy the
  log's wording. Never invent a {SUBJECT_KIND}, a source or a {FACT}, and never change who did what.
- Every {FACT} listed in `experimental_log.md` must be stated at least once and at most
  {MAX_MENTIONS} times, in prose.
- References: no reference list, no citations of scholarly work, no author names, no `[1]`.
- Anonymity: no author names, affiliations, funding or acknowledgements.
- Style: formal, precise, argued, as in a peer-reviewed {VENUE}; take a position and defend it.
