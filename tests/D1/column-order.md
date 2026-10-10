# D1 column order (milestone 1, row 1.4)

**Result: no interleaving.** In all 10 papers Docling 2.110.0 (OCR off, tables on) keeps the two
columns in reading order: left column, then right column, then the next page. No paper needs to be
excluded or flagged in the manifest for column order.

## Setup

- Markdown: the Docling 2.110.0 outputs in `tests/D1/docling/` (same converter and settings as the
  frozen corpus; the frozen corpus itself is on Ceph and was not reachable).
- PDFs: the same 10 files downloaded from the ACL Anthology (`https://aclanthology.org/2025.acl-long.999.pdf`
  etc.; `tests/D1/convert_docling.py` converted the identically named files). They are not committed.
- `tests/D1/column_order.py` (pdfplumber 0.11, used only for this check): words on each PDF page are
  assigned to the left or right half and read as (page, column, top, x). Each Docling body paragraph is
  located in that stream by a unique 40-character alphanumeric probe from its start and from its end, so
  the check is insensitive to Docling's spacing, hyphenation and entity escapes. Raw output:
  `tests/D1/column-order.json`.

## Numbers

| Paper | Pages | Two-column pages | Body paragraphs | Located | Inversions | Column/page breaks inside one paragraph | Split sentences |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2025-acl-long-1031 | 39 | 31 | 253 | 195 | 2 | 8 | 0 |
| 2025-acl-long-1458 | 28 | 20 | 234 | 157 | 5 | 9 | 0 |
| 2025-acl-long-625 | 35 | 30 | 210 | 166 | 4 | 16 | 2 |
| 2025-acl-long-935 | 20 | 18 | 127 | 100 | 2 | 12 | 0 |
| 2025-acl-long-999 | 38 | 36 | 281 | 195 | 5 | 26 | 1 |
| 2025-emnlp-main-1032 | 13 | 12 | 189 | 67 | 2 | 7 | 2 |
| 2025-emnlp-main-1418 | 37 | 34 | 505 | 280 | 15 | 15 | 6 |
| 2025-emnlp-main-1755 | 32 | 29 | 302 | 247 | 4 | 14 | 8 |
| 2025-emnlp-main-356 | 23 | 22 | 180 | 141 | 1 | 16 | 2 |
| 2025-emnlp-main-971 | 23 | 19 | 230 | 182 | 6 | 18 | 5 |

All 10 papers use the two-column ACL template; the single-column pages are full-page tables, figures and
prompt listings in appendices.

**Inversions** (a paragraph that starts before the previous one ends, in PDF order) were read one by one;
none is a column interleave. Before excluding captions and footnotes there were 121; the 46 left are:
footnotes and reference entries placed after the paragraph that cites them; text inside figures and prompt
boxes (1418 p.15, 999 p.22), which the PDF lays out in narrow sub-columns; appendix paragraphs that repeat
a body paragraph word for word (971 p.3/p.11, 1755), so the probe matched the other copy; and three cases
checked against the PDF page text (1031 p.8, 1458 p.18, 1032 p.2), where Docling's order matches the PDF
and the probe hit a table or figure caption first.

## What happens at a column break

1. **Joined inside one paragraph (141 cases).** The usual case: the sentence continues in one Markdown
   paragraph, with the line-end hyphen kept as `solu- tions`. A quote across the break is ordinary text.
2. **Split into two adjacent paragraphs (5 cases at a column or page break).** The sentence stops at the
   end of a paragraph and continues lower-case in the next, with only `\n\n` between:
   `2025-acl-long-625` offset 2344 (`improving LLM SFT` / `performance. ALPAGASUS`),
   `2025-acl-long-999` 12336, `2025-emnlp-main-1032` 3565, `2025-emnlp-main-1418` 37127 and 109075.
   A retyped quote across such a break matches once whitespace is normalised (the 1.5 anchor tests cover
   these three: 625, 1032, 1418).
3. **Split with a float placed between the halves (4 cases, all at page breaks).** Docling put the
   footnote, caption, image marker or table that sits at the bottom or top of the page between the two
   halves of a sentence: `2025-emnlp-main-1418` 13463 (footnote + caption + image) and 128907 (table +
   caption), `2025-emnlp-main-1755` 8642 (footnote) and 18024 (caption + image + table). A quote spanning
   such a break does **not** match, because the inserted text is in the file between the two halves. The
   anchor library rejects it as `not_found`; the agent has to quote one side. This is a property of the
   frozen Markdown, not of the anchor code, and it is rare (4 of ~150 breaks).

Not column-related, found on the way: 6 sentences are split by a display formula that Docling did not
decode (`<!-- formula-not-decoded -->`, or dropped entirely in 356), so a quote across a formula cannot match
either.

## Consequence for 1.5 and the manifest

- No paper is excluded or flagged for column order.
- Anchor normalisation must treat `\n\n` and `- ` line-end hyphenation as whitespace/hyphenation noise,
  which 1.5 does. Quotes across an inserted float or an undecoded formula stay rejected.
