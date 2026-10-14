You extract evidence of one type from one part of a research paper, for a research protocol.

Evidence type: {evidence_type}
{description}

Every item has these fields (JSON schema):
{fields}
{links}
For every item, copy verbatim quotes from the text, one per passage role:
{roles}

Rules:
- Copy each quote exactly as it appears in the text, character for character. Do not paraphrase, do not
  shorten it with "...", do not fix typos or formatting.
- A quote is short (a few words up to one sentence) but long enough to occur only once in the paper.
- Report only what the text states. If this part has no such evidence, return an empty list of items.
- Report each distinct item once; the same fact stated twice in this part is one item.
