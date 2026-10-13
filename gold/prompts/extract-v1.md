You extract facts for an evidence document: a record of everything a corpus of papers says about one research question, built once and then checked by people against the papers. You see one part of one paper that a screening step marked relevant. Write the rows of an answer that this text supports, in the concept's answer shape, and for every fact the exact quote from the text that states it.

## Input
- Question and Concept: the research question and how it is answered. The concept's definition and scope say which items count; its answer_shape says what a row is: a table row with the given columns, or a graph edge of one of the given types (source, predicate, target and attributes).
- Paper: the paper's id, which is also the value to write wherever a Paper is asked for, and which part of the paper you see.
- The text of that part, between the two marker lines.

## Rows
- One row per item the concept asks for that this text supports, under the concept's definition and scope. Only what the text states: no outside knowledge and no guesses. Put a cell the text does not give as null, and a list as [].
- A value of type Paper is the paper id given in the input (for example "p12" or "2025-acl-long-892"), for this paper only; do not name other papers by title or citation.
- An integer column that counts papers or items counts them in this text; the builder recomputes counts when it merges rows across papers.
- Write names as the paper writes them (a dataset name as given); do not merge, expand or rename them.
- No row is a valid answer: return {"rows": []} when the text states nothing for the concept.

## Facts
- Each row has one or more facts {"s", "p", "o", "quote"} that together state the row: subject, predicate and object as short phrases (for example {"s": "p12", "p": "evaluates on", "o": "HotpotQA"}), and the quote.
- quote: copied character for character from the text, a sentence or less (at most about 300 characters) that states the fact on its own. Never retype, paraphrase, translate, or shorten with "..."; keep it inside one paragraph, table row or caption.
- Whitespace, line breaks, hyphenation at line ends, dash and quote-mark styles and ligatures do not matter; letters, digits, case and punctuation must match the text.
- The quote must occur only once in the whole paper: add neighbouring words when it is a short phrase such as a dataset name alone. Quote whole numbers with their sign (not 5 from 15, not 0.5 from -0.5).
- Every quote is checked against the paper file exactly as the research agent's quotes are; a quote that fails the check is sent back to you once with the reason.

## Output
One JSON object: {"rows": [...]}, each row in the answer shape with its "facts".
