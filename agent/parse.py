"""Reply parser for the main loop (row 1.8; docs/earlier-work.md, Decisions after tests §2, B1-B3, B8).

Only the reply's `content` is parsed; the reasoning field is never looked at, so nothing in it
can run. In order:

0. guided (rows 1.13, 1.15): a conclude reply decoded under the answer's JSON schema (vLLM
   structured outputs) is the bare answer object. When the call was guided, a reply that starts
   with `{` is the answer, mode `guided_answer`, even if it does not parse (a length cut): the
   answer check then says why. Anything else falls through to the rules below, in case the
   server ignored the schema;
1. strict: exactly one fenced ```bash or ```sh block -> run it;
2. a reply with no bash block and a ```json block -> the final answer (the last json block);
3. lenient fallbacks, each logged with its mode:
   - several bash blocks -> run the first and say so (B1: rare, but it happens);
   - one unlabelled ``` fence -> its body (a JSON object there is the answer);
   - a Qwen tool-call text form `<function=bash><parameter=command>...` -> the command (every
     reply of the four M1-real runs came in this form);
   - no fence: a JSON object is the answer; one non-empty line, or at most 3 lines none of which
     ends like a sentence, is the command verbatim;
4. otherwise nothing runs and the harness writes a `coverage` record.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

FENCE = "`" * 3
BASH_BLOCK = re.compile(FENCE + r"(?:bash|sh|shell)[ \t]*\r?\n(.*?)" + FENCE, re.S)
JSON_BLOCK = re.compile(FENCE + r"json[ \t]*\r?\n(.*?)" + FENCE, re.S)
PLAIN_BLOCK = re.compile(FENCE + r"[ \t]*\r?\n(.*?)" + FENCE, re.S)
TOOL_CALL = re.compile(r"<function=bash>\s*(?:<parameter=command>\s*)?(.*?)\s*(?:</parameter>|</function>|</tool_call>|$)", re.S)
SENTENCE_END = re.compile(r"[.!?:]\s*$")


@dataclass(frozen=True)
class Parsed:
    """kind: command, answer or none. `mode` names the rule that matched; `notice` goes to the agent."""
    kind: str
    mode: str
    command: str = ""
    answer: str = ""
    notice: str = ""


def _json_object(text: str) -> bool:
    try:
        return isinstance(json.loads(text), dict)
    except ValueError:
        return False


def parse_reply(content: str | None, guided: bool = False) -> Parsed:
    """`guided`: the call was decoded under the answer schema (the conclude phase), see rule 0."""
    text = (content or "").strip()
    if guided and text.startswith("{"):
        return Parsed("answer", "guided_answer", answer=text)
    bash = [b.strip() for b in BASH_BLOCK.findall(text)]
    bash = [b for b in bash if b]
    if len(bash) == 1:
        return Parsed("command", "strict", command=bash[0])
    if len(bash) > 1:
        return Parsed("command", "lenient_first_of_many", command=bash[0],
                      notice=f"Your reply had {len(bash)} bash blocks; only the first ran. "
                             "Reply with exactly one bash block.")
    answers = [b.strip() for b in JSON_BLOCK.findall(text)]
    if answers:
        return Parsed("answer", "answer_json_block", answer=answers[-1])
    plain = [b.strip() for b in PLAIN_BLOCK.findall(text) if b.strip()]
    if len(plain) == 1:
        if _json_object(plain[0]):
            return Parsed("answer", "lenient_answer_fence", answer=plain[0])
        return Parsed("command", "lenient_unlabelled_fence", command=plain[0])
    call = TOOL_CALL.search(text)
    if call and call.group(1).strip():
        return Parsed("command", "lenient_tool_call", command=call.group(1).strip())
    if FENCE not in text and text:
        if _json_object(text):
            return Parsed("answer", "lenient_bare_answer", answer=text)
        lines = [line for line in text.splitlines() if line.strip()]
        if len(lines) == 1 or (len(lines) <= 3 and not any(SENTENCE_END.search(line) for line in lines)):
            return Parsed("command", "lenient_bare_command", command="\n".join(lines))
    return Parsed("none", "unparsed")


ANTHOLOGY_ID = r"\d{4}(?:-[a-z]+)+-\d+"  # 2025-acl-long-892, 2025-emnlp-main-1032
CORPUS_FILE = re.compile(rf"(?<![\w.-])(?:(p\d+)\.md\b|({ANTHOLOGY_ID})(?:\.md\b|(?![\w.-])))")
CORPUS_DIR = re.compile(rf'\$\{{?CORPUS\}}?"?(?!/+(?:p\d+|{ANTHOLOGY_ID})\.md)')


def files_read(command: str) -> tuple[list[str], bool]:
    """Best-effort guess at which corpus files a command reads, for the PROV `uses` edge.

    Heuristic, from the command text only (nothing traces the process). The corpus names its
    files `p<N>.md` (the first papers) and by ACL Anthology id (`2025-acl-long-892.md`). Every
    such name in the command, whether written as `$CORPUS/p12.md`, `"$CORPUS"/p12.md` or plain
    `p12.md`, is a file read, returned as corpus-relative names in order of first mention; an
    anthology id also counts without `.md` (M1-real loops ran `for f in 2025-acl-long-1106 ...;
    do rg ... "$f.md"`), a bare `p12` does not. The second value is True when the command names
    the corpus directory itself (`$CORPUS` not followed by a file name, e.g. `rg -l RAG "$CORPUS"`),
    i.e. it may read any file. Files reached through variables, globs (`p1*.md`) or scripts are
    missed; a name that only appears in a string is over-counted.
    """
    names = list(dict.fromkeys(f"{p or a}.md" for p, a in CORPUS_FILE.findall(command)))
    return names, bool(CORPUS_DIR.search(command.replace('"/', "/")))


def normalise_command(command: str) -> str:
    """Whitespace-insensitive form used to detect repeated commands (B4)."""
    return " ".join(command.split())
