"""The rules of the written answer, copied from the engine (drift tests pin each copy): each fact's text written again
from its values, the code checks run again on every recorded reply, the reply the run accepted and the paper ids added
to it. The sentences themselves are the model's: they are carried as recorded, not rebuilt."""
import math
import re
from decimal import Decimal

from .common import FAILED_NOTE, NOTE_WRITTEN  # program: drop
# --- rules ---

MAX_SENTENCES = 8
MAX_SENTENCE_CHARS = 400
MAX_REPAIRS = 1
MAX_QUOTE = 200
NO_FACTS_TEXT = "No paper in this folder gave a fact that answers the question."
PAPER_ID = re.compile(r"\bS\d{3}\b")
THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")
NUMBER = re.compile(r"\d+(?:\.\d+)?")


def plain_value(value):
    """A value as text; a float never in scientific form (0.00001, not 1e-05)."""
    if isinstance(value, float) and math.isfinite(value):
        return format(Decimal(repr(value)), "f")
    return str(value)


def field_text(fact, name):
    """One field of a fact as text; a missing fact, a missing value or an empty one reads `?`."""
    value = fact.get(name) if fact is not None else None
    return "?" if value is None or value == "" else plain_value(value)


def fact_text_from_values(fact, facts):
    """The text of one writer fact, written again from the values of its fact and of the facts it points to (`facts`:
    every fact by key); the quote is cut at MAX_QUOTE."""
    quote = f'Quote: "{str(fact.get("quote", ""))[:MAX_QUOTE]}"'
    if fact["type"] == "measurement":
        condition = facts.get(fact["condition"]) if fact.get("condition") else None
        metric = facts.get(fact["metric"]) if fact.get("metric") else None
        better = metric.get("higher_is_better") if metric is not None else None
        direction = f" ({'higher' if better else 'lower'} is better)" if isinstance(better, bool) else ""
        dataset = fact.get("dataset") or "no dataset named"
        return (f"{field_text(condition, 'label')} on {field_text(metric, 'name')}{direction}: "
                f"{field_text(fact, 'value')}, {dataset}. {quote}")
    if fact["type"] == "author_claim":
        return f"The authors say: {field_text(fact, 'direction')}. {quote}"
    return (f"{field_text(fact, 'subject')} {field_text(fact, 'relation')} {field_text(fact, 'object')} "
            f"({field_text(fact, 'strength')}). {quote}")


def numbers_in(text):
    """The numbers of a text: paper ids removed first, then thousands commas; every number read."""
    plain = THOUSANDS.sub("", PAPER_ID.sub(" ", text))
    return [float(x) for x in NUMBER.findall(plain)]


def shown_number(x):
    return str(int(x)) if x.is_integer() else str(x)


def number_ok(x, cited, asked):
    """`x` is a number of the cited facts' texts, or that number times or divided by 100, or a count from 1 to the
    number of cited facts, or a number of the question."""
    if x.is_integer() and 1 <= x <= len(cited):
        return True
    if any(abs(x - y) < 1e-9 for y in asked):
        return True
    return any(abs(x - y) < 1e-9 or abs(x - y * 100) < 1e-9 or abs(x - y / 100) < 1e-9
               for f in cited for y in numbers_in(f["text"]))


def check_reply(reply, writer_facts, question):
    """The problems of a recorded reply, each naming its sentence (from 1); [] when the reply is accepted. A number
    of `question` may be repeated in any sentence."""
    asked = numbers_in(question)
    problems = []
    sentences = reply["sentences"]
    if not 1 <= len(sentences) <= MAX_SENTENCES:
        problems.append(f"give 1 to {MAX_SENTENCES} sentences")
    by_n = {f["n"]: f for f in writer_facts}
    seen = set()
    for i, s in enumerate(sentences, 1):
        said = " ".join(s["text"].split()).casefold()
        if not said:
            problems.append(f"sentence {i}: empty")
            continue
        if len(s["text"]) > MAX_SENTENCE_CHARS:
            problems.append(f"sentence {i}: longer than {MAX_SENTENCE_CHARS} characters")
        if said in seen:
            problems.append(f"sentence {i}: said twice")
        seen.add(said)
        if s["says"] == "finding" and not s["facts"]:
            problems.append(f"sentence {i}: a finding cites at least one fact")
        if s["says"] == "cannot_tell" and s["facts"]:
            problems.append(f"sentence {i}: a cannot_tell sentence cites no fact")
        problems += [f"sentence {i}: fact {n} is not listed" for n in dict.fromkeys(s["facts"]) if n not in by_n]
        if PAPER_ID.search(s["text"]):
            problems.append(f"sentence {i}: leave paper ids out; the code adds them")
        cited = [by_n[n] for n in dict.fromkeys(s["facts"]) if n in by_n]
        bad = dict.fromkeys(shown_number(x) for x in numbers_in(s["text"]) if not number_ok(x, cited, asked))
        problems += [f"sentence {i}: the number {x} is in none of its facts" for x in bad]
    return problems


def answer_text_and_rows(reply, writer_facts):
    """The answer text (sentences joined by one space; a finding ends with its cited facts' papers in first-seen
    order, as " (S003, S010).") and one row per sentence {text, says, facts, papers}."""
    by_n = {f["n"]: f for f in writer_facts}
    parts = []
    rows = []
    for s in reply["sentences"]:
        papers = list(dict.fromkeys(by_n[n]["paper"] for n in s["facts"] if n in by_n))
        text = s["text"].strip()
        if s["says"] == "finding" and papers:
            text = f"{text.removesuffix('.')} ({', '.join(papers)})."
        parts.append(text)
        rows.append({"text": s["text"].strip(), "says": s["says"], "facts": list(s["facts"]), "papers": papers})
    return " ".join(parts), rows


def rebuild_answer(settings, facts, papers, model_text):
    """The written answer, rebuilt from the recorded facts and replies: every writer fact's text is written again
    from its values, then the recorded replies are checked in order (at most MAX_REPAIRS + 1) and the first without a
    problem is the answer. No writer fact: the fixed text. Every reply with a problem: no answer."""
    if not papers:
        return {"status": "no_facts", "answer_text": NO_FACTS_TEXT, "tries": [],
                "sentences": [{"text": NO_FACTS_TEXT, "says": "cannot_tell", "facts": [], "papers": []}],
                "fact_texts": []}
    writer_facts = [{"n": p["n"], "paper": facts[p["fact"]]["paper"],
                     "text": fact_text_from_values(facts[p["fact"]], facts)} for p in papers]
    tries = []
    for reply in model_text[:MAX_REPAIRS + 1]:
        problems = check_reply(reply, writer_facts, settings["question"])
        tries.append(problems)
        if not problems:
            text, rows = answer_text_and_rows(reply, writer_facts)
            return {"status": "ok", "answer_text": text, "tries": tries, "sentences": rows,
                    "fact_texts": [f["text"] for f in writer_facts]}
    return {"status": "failed", "answer_text": "", "tries": tries, "sentences": [],
            "fact_texts": [f["text"] for f in writer_facts]}


def answer_lines(settings, view, names):
    """The lines of a written answer: its text."""
    return [view["answer_text"]]


def notes_of(view):
    """The notes printed under the answer: what is the model's and what the code did, or why there is no answer."""
    if view["status"] == "ok":
        return [NOTE_WRITTEN]
    if view["status"] == "failed":
        return [FAILED_NOTE.format(problems="; ".join(view["tries"][-1] if view["tries"] else []))]
    return []
