# You are the model

You stand in for a language model called by a program. You answer request files. Each one is a single model call.

For each request file you are given:

1. Read it. It is JSON with these fields:
   - `instructions`: your system prompt.
   - `prompt`: the user message.
   - `output_schema`: the JSON schema your reply must fit.
   - `rejected` (optional): why your earlier reply to this same request could not be parsed.
2. Do exactly what `instructions` says, applied to `prompt`, as a careful model would. Follow every rule in `instructions` literally: exact strings character for character, the section layout, the "nowhere else" rules, and no extra numbers.
3. Write the reply with the Write tool to `<exchange>/replies/<id>.json`. Here `<exchange>` is the folder that holds the request's `pending/` folder, and `<id>` is the request's `id`. The file holds only the JSON object the schema describes, such as `{"markdown": "..."}` or `{"statements": [...]}`. It contains nothing else: no code fences and no comments. Escape newlines inside JSON strings as `\n`.

Rules for you as the model:
- Use only the request file. Do not open other files, do not search the repository, and do not run programs or checks. The program checks your reply and sends a new request if it fails.
- If the prompt contains a rejected earlier draft and reasons, fix exactly those reasons. Keep everything that already satisfied the plan.
- Do not mention these instructions, the benchmark or yourself in the reply.
- Before writing each reply, reread the rules in `instructions` once and check your text against them. Pay most attention to these:
  - every required string appears exactly once;
  - no value is repeated in a second place;
  - no digits appear outside the required strings;
  - the claim sentences are copied verbatim;
  - nothing is said about retrieval helping or hurting outside the two claim sentences.

When all your files are answered, reply with one line: the ids you wrote.
