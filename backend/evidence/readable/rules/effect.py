"""The rules of the effect and consistency kinds, copied from the engine (drift tests pin each copy): a paper's
direction from its two values, repeats, large effects, the label table, and the answer's lines.

`settings["kind"]` is `effect` or `consistency`."""
import re
from statistics import median

from .common import (CANT_TELL_LINE, GROUPS, LABEL_TEXT, SAYS, cut_lines, join_words, name_of,  # program: drop
                     number_text, reason_text)  # program: drop
# --- rules ---

VALUE_DECIMALS = 3
NO_CLAIM = {"code": "no_claim", "text": "no author claim found"}
CONDITION_PATTERN = re.compile(r"^\s*(>=|<=|==|>|<)\s*(\d+)\s*$")
FLAG_NAMES = ("claim_disagrees", "duplicate", "large_effect")


def direction_and_difference(treatment_value, control_value, higher_is_better, smallest_real_difference):
    """The direction of one paper's effect (supports, contradicts or neutral) and its signed difference, where a
    positive difference means the treatment is better; a difference under the smallest real one is neutral."""
    if higher_is_better:
        difference = round(float(treatment_value) - float(control_value), 6)
    else:
        difference = round(float(control_value) - float(treatment_value), 6)
    if abs(difference) < smallest_real_difference:
        return "neutral", difference
    return ("supports" if difference > 0 else "contradicts"), difference


def claim_agrees(claim, direction, claim_map):
    """True when the author's claim names the direction the numbers give."""
    return claim_map[claim] == direction


def condition_holds(condition, value):
    """True when a count meets a condition written as an operator and a whole number, such as `>=2`."""
    found = CONDITION_PATTERN.match(condition)
    if not found:
        raise ValueError("a label condition is an operator and a whole number, not " + repr(condition))
    operator, limit = found.group(1), int(found.group(2))
    return {">": value > limit, ">=": value >= limit, "<": value < limit, "<=": value <= limit,
            "==": value == limit}[operator]


def label_from_counts(counts, label_rows):
    """The answer label: the `then` of the first row whose every `when` condition holds on the counts."""
    for row in label_rows:
        if all(condition_holds(condition, int(counts.get(name, 0))) for name, condition in row["when"].items()):
            return row["then"]
    raise ValueError("the label table has no row that matches")


def repeated_studies(studies):
    """Each later paper that repeats an earlier one, as {later paper: first paper}. A study is (paper, measure,
    treatment value, control value) and may add a fifth part, the experiment setting; two studies repeat each other
    when their values agree after rounding and their settings are the same (a study with no setting only repeats
    another with none)."""
    first = {}
    found = {}
    for paper, measure, treatment_value, control_value, *rest in studies:
        key = (measure, round(float(treatment_value), VALUE_DECIMALS), round(float(control_value), VALUE_DECIMALS))
        if rest and rest[0] is not None:
            key = (rest[0],) + key
        if key in first:
            found[paper] = first[key]
        else:
            first[key] = paper
    return found


def large_effect_papers(differences, factor, min_studies, smallest_real_difference):
    """The papers whose difference is more than `factor` times the median size among the papers with a real
    difference, when at least `min_studies` papers have one; sorted."""
    sizes = {}
    for paper, difference in differences.items():
        if difference is not None and abs(difference) >= smallest_real_difference:
            sizes[paper] = abs(difference)
    if len(sizes) < min_studies:
        return []
    limit = factor * median(sizes.values())
    return sorted(paper for paper, size in sizes.items() if size > limit)


def read_one_paper(settings, facts, paper):
    """One paper's row of the answer, with the values read from the facts it names."""
    claim = facts[paper["claim"]]["direction"] if paper.get("claim") else None
    if "could_not_be_read" in paper:
        return {"paper": paper["paper"], "direction": "undetermined", "difference": None, "measure": None,
                "treatment_value": None, "control_value": None, "claim": claim, "claim_agrees": None,
                "reason": paper["could_not_be_read"], "setting": None}
    treatment_value = facts[paper["treatment_value"]]["value"]
    control_value = facts[paper["control_value"]]["value"]
    higher = [m["higher_is_better"] for m in settings["metrics"] if m["canonical"] == paper["measure"]][0]
    direction, difference = direction_and_difference(treatment_value, control_value, higher,
                                                     settings["smallest_real_difference"])
    agrees = None
    if claim is not None:
        agrees = claim_agrees(claim, direction, settings["claim_map"])
    return {"paper": paper["paper"], "direction": direction, "difference": difference, "measure": paper["measure"],
            "treatment_value": treatment_value, "control_value": control_value, "claim": claim,
            "claim_agrees": agrees, "reason": None, "setting": paper.get("experiment_setting")}


def rebuild_effect(settings, facts, papers):
    """The effect answer: each paper's direction, repeats, large effects, flags, groups, counts and label."""
    rows = [read_one_paper(settings, facts, paper) for paper in papers]
    determined = [row for row in rows if row["direction"] != "undetermined"]
    repeats = {}
    if settings["flags"]["duplicates"]:
        repeats = repeated_studies([(row["paper"], row["measure"], row["treatment_value"], row["control_value"],
                                     row["setting"]) for row in determined])
    large = large_effect_papers({row["paper"]: row["difference"] for row in determined if row["paper"] not in repeats},
                                settings["flags"]["large_effect"]["factor"],
                                settings["flags"]["large_effect"]["min_studies"],
                                settings["smallest_real_difference"])
    studies = []
    for row in rows:
        flags = set()
        if row["paper"] in repeats:
            flags.add("duplicate")
        if row["paper"] in large:
            flags.add("large_effect")
        if row["claim_agrees"] is False:
            flags.add("claim_disagrees")
        studies.append({"document": row["paper"], "direction": row["direction"], "delta": row["difference"],
                        "metric": row["measure"], "treatment_value": row["treatment_value"],
                        "control_value": row["control_value"], "claim": row["claim"],
                        "claim_agrees": row["claim_agrees"], "reason": row["reason"], "flags": sorted(flags),
                        "duplicate_of": repeats.get(row["paper"])})
    groups = {}
    for name, direction in (("supporting", "supports"), ("contradicting", "contradicts"), ("neutral", "neutral"),
                            ("undetermined", "undetermined")):
        groups[name] = [s["document"] for s in studies if s["direction"] == direction and s["duplicate_of"] is None]
    groups["duplicates"] = [s["document"] for s in studies if s["duplicate_of"] is not None]
    counts = {name: len(members) for name, members in groups.items()}
    flag_groups = {name: [s["document"] for s in studies if name in s["flags"]] for name in FLAG_NAMES}
    view = {"label": label_from_counts(counts, settings["label_rows"]), "counts": counts}
    view.update(groups)
    view["flags"] = flag_groups
    view["studies"] = studies
    return view


def rebuild_consistency(settings, facts, papers):
    """The consistency answer: for each paper whether the author's claim agrees with the direction of its numbers."""
    studies = []
    for paper in papers:
        row = read_one_paper(settings, facts, paper)
        reason = row["reason"]
        if reason is None and row["claim"] is None:
            reason = dict(NO_CLAIM)
        studies.append({"document": row["paper"], "claim": row["claim"], "direction": row["direction"],
                        "agrees": row["claim_agrees"], "reason": reason})
    view = {"metric": settings["measure"]}
    for name, value in (("agreeing", True), ("disagreeing", False), ("undetermined", None)):
        view[name] = [s["document"] for s in studies if s["agrees"] is value]
    view["studies"] = studies
    return view


def rebuild_answer(settings, facts, papers, model_text):
    """The answer of the program's kind, rebuilt from the recorded facts alone (`model_text` is not used)."""
    if settings["kind"] == "consistency":
        return rebuild_consistency(settings, facts, papers)
    return rebuild_effect(settings, facts, papers)


def effect_lines(settings, view, names):
    """The lines of an effect answer: summary lines first, then one line per paper."""
    treatment = name_of(names, settings["treatment"])
    control = name_of(names, settings["control"])
    if view.get("label") == "insufficient":
        head = [CANT_TELL_LINE]
    else:
        label = view.get("label")
        said = LABEL_TEXT.get(label, f"{label}.".replace("_", " ")).format(t=treatment)
        measures = join_words([name_of(names, m["canonical"]) for m in settings["metrics"]])
        head = [f"{treatment} against {control} on {measures}: {said}"]
    for key, words in GROUPS:
        if view.get(key):
            head.append(f"Papers that {words}: {join_words(view[key])}.")
    body = []
    for study in view.get("studies", []):
        if study["direction"] in SAYS:
            values = ""
            if study.get("treatment_value") is not None and study.get("control_value") is not None:
                values = f" ({number_text(study['treatment_value'])} against {number_text(study['control_value'])})"
            body.append(f"{study['document']}: {SAYS[study['direction']]} on "
                        f"{name_of(names, study.get('metric') or '')}{values}.")
        else:
            body.append(f"{study['document']}: could not be read ({reason_text(study.get('reason'), settings, names)}).")
    return head + body


def consistency_lines(settings, view, names):
    """The lines of a consistency answer: one summary line, then one line per paper."""
    measure = view.get("metric") or settings["measure"]
    agreeing, disagreeing, unknown = view.get("agreeing", []), view.get("disagreeing", []), view.get("undetermined", [])
    if not agreeing and not disagreeing:
        head = [CANT_TELL_LINE]
    else:
        parts = []
        if agreeing:
            parts.append("agree with their numbers in " + join_words(agreeing))
        if disagreeing:
            parts.append("disagree in " + join_words(disagreeing))
        if unknown:
            parts.append("cannot be checked in " + join_words(unknown))
        head = [f"On {name_of(names, measure)}, the authors' claims {'; '.join(parts)}."]
    body = []
    for study in view.get("studies", []):
        if study.get("agrees") is None:
            body.append(f"{study['document']}: cannot be checked ({reason_text(study.get('reason'), settings, names)}).")
        else:
            said = settings["claim_map"].get(study.get("claim"))   # the direction the author's claim names
            body.append(f"{study['document']}: the authors say {SAYS.get(said, 'nothing clear')}, "
                        f"the numbers say {SAYS.get(study.get('direction'), 'nothing clear')}.")
    return head + body


def answer_lines(settings, view, names):
    """The answer's lines for the program's kind, cut to the most lines an answer shows."""
    if settings["kind"] == "consistency":
        return cut_lines(consistency_lines(settings, view, names))
    return cut_lines(effect_lines(settings, view, names))


def notes_of(view):
    """The notes printed under the answer: none, because a fixed kind's answer is rebuilt in full."""
    return []
