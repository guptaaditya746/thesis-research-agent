"""The texts and small steps every kind's rules share, copied from the engine (drift tests pin each copy).

Rule-file convention: a docstring, the import lines (standard library only; a line ending in the drop mark is a
test-only relative import), a line exactly as below, then the body."""
import hashlib
import json
import sys
# --- rules ---

CANT_TELL_LINE = "The papers in this folder cannot answer this question."
MAX_KIND_LINES = 120
SAYS = {"supports": "better", "contradicts": "worse", "neutral": "no real difference"}
LABEL_TEXT = {"supported": "{t} does better.", "refuted": "{t} does worse.", "no_effect": "no real difference.",
              "mixed": "the papers disagree."}
GROUPS = (("supporting", "show it better"), ("contradicting", "show it worse"), ("neutral", "show no real difference"),
          ("undetermined", "could not be read"), ("duplicates", "repeat an earlier paper"))
INVENTORY_TARGETS = {"condition": "compared things", "metric": "measures"}
REASON_TEMPLATES = {"screened_out": "screened out",
                    "no_treatment_condition": "no {treatment} condition found",
                    "no_control_condition": "no {control} condition found",
                    "no_question_metric": "no metric of the question found",
                    "no_pair": "no {treatment} and {control} measurement on a question metric"}
BEST_REASON_TEMPLATES = {"too_few_kinds": "conditions of fewer than two method kinds found",
                         "no_question_metric": "no metric item of {metric} found",
                         "no_comparison": "no dataset with values of two method kinds on {metric}"}
CHECK_OK = "Check: this is the answer the run recorded."
CHECK_FAILED = "Check FAILED: this is not the answer the run recorded."
NOTE_WRITTEN = ("The sentences were written by a model from the facts above, not rebuilt by this file; this file "
                "re-ran the code checks and added the paper ids.")
FAILED_NOTE = "The model's answer failed its checks: {problems}"


def fold(name):
    """A name with its spaces collapsed and its case folded, to compare two names."""
    return " ".join(str(name).split()).casefold()


def join_words(words):
    """The words joined with a comma and a space."""
    return ", ".join(words)


def number_text(value):
    """A number as the answer prints it: up to ten significant digits."""
    return f"{value:.10g}"


def name_of(names, identifier):
    """The plain name of a thing id (the id itself when it has none)."""
    return names.get(identifier, identifier)


def reason_text(reason, settings, names):
    """The words for a reason {code, text}: a known code is written again from its template with the names of the
    compared things (or of the measure, for the best kind); anything else keeps its own text."""
    reason = reason or {}
    code = reason.get("code") if reason.get("text") else None
    if settings["kind"] == "best" and code in BEST_REASON_TEMPLATES:
        measure = settings["measure"]
        return BEST_REASON_TEMPLATES[code].format(metric=names.get(measure, measure))
    if settings["kind"] != "best" and code in REASON_TEMPLATES:
        treatment, control = settings["treatment"], settings["control"]
        return REASON_TEMPLATES[code].format(treatment=names.get(treatment, treatment),
                                             control=names.get(control, control))
    return str(reason.get("text") or "no reason given")


def cut_lines(lines):
    """The lines, at most MAX_KIND_LINES of them, then a line saying how many more there are."""
    if len(lines) <= MAX_KIND_LINES:
        return lines
    return lines[:MAX_KIND_LINES] + [f"... and {len(lines) - MAX_KIND_LINES} more."]


def text_sha256(text):
    """The sha256 of a text (as UTF-8 bytes), in hex."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def values_sha256(view):
    """The sha256 of a rebuilt answer's values: its JSON with sorted keys and no spaces, as UTF-8 bytes."""
    text = json.dumps(view, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return text_sha256(text)


def main(argv, data):
    """Rebuild the answer from the program's data, print it and check it against what the run recorded; return 0 when
    the check holds and 1 when it does not (also with --json, whose text is the same either way)."""
    view = data["rebuild_answer"](data["RULE_SETTINGS"], data["FACTS_USED"], data["PAPERS"], data["MODEL_TEXT"])
    text = "\n".join(data["answer_lines"](data["RULE_SETTINGS"], view, data["NAMES_OF_THINGS"]))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    holds = (text_sha256(text) == data["RECORDED_ANSWER_SHA256"]
             and values_sha256(view) == data["RECORDED_VALUES_SHA256"])
    if "--json" in argv:
        print(json.dumps({"kind": data["KIND"], "answer": view, "text": text}, ensure_ascii=False, sort_keys=True))
        return 0 if holds else 1
    if not holds:
        print(CHECK_FAILED)
        print()
    print(text)
    if holds:
        print()
    for note in data["notes_of"](view):
        print(note)
    if holds:
        print(CHECK_OK)
    return 0 if holds else 1
