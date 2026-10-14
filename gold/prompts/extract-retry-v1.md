You extracted facts from one part of a research paper for an evidence document, each with a quote from the text. The quote check rejected some of the quotes; nothing was recorded for those facts. The check accepts a quote only if it occurs exactly once in the paper file. For each rejected fact you get its id, the fact (s, p, o), your quote and the reason. Give a new quote for each, copied from the text, that states the fact.

## Reasons
- not_found: the quote is not in the file. You retyped it, it spans a table, figure or footnote break, or it is from another file. Copy it again from the text.
- ambiguous: the quote occurs more than once in the file. Add neighbouring words until it occurs once.
- partial_number: the quote occurs only where it cuts a number or drops its sign, for example 5 from 15, 0.5 from 0.55, or 0.5 from -0.5. Quote the whole number with its sign.
- empty_quote: the quote has no text. Give a non-empty quote.
- bad_field:quote: the quote is empty or only whitespace. Give a non-empty quote.

## Rules
- Copy the quote character for character from the text between the marker lines, a sentence or less (at most about 300 characters). Never retype, paraphrase, or shorten with "..."; keep it inside one paragraph, table row or caption.
- Whitespace, line breaks, hyphenation at line ends, dash and quote-mark styles and ligatures do not matter; letters, digits, case and punctuation must match the text.
- Do not change the fact. If the text does not state it, give an empty quote "" for that id.

## Output
One JSON object: {"quotes": [{"id": "<id of the rejected fact>", "quote": "..."}]}, one entry per id you were given.
