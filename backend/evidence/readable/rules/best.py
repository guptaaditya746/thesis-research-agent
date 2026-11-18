"""The rules of the best kind, copied from the engine (drift tests pin each copy): a paper's method kinds, its top
value, the winner or the tie, the tally of wins, and the answer's lines."""
from .common import (CANT_TELL_LINE, cut_lines, fold, join_words, name_of, reason_text)  # program: drop
# --- rules ---


def kind_of_thing(thing_fact, kinds):
    """The method kind of a compared thing: its kind value when that names one of the kinds, else the kind whose
    names hold its label (spaces collapsed, case folded); None when none does."""
    given = thing_fact.get("kind")
    if given in kinds:
        return str(given)
    label = fold(thing_fact.get("label") or "")
    for kind, names in kinds.items():
        if label in [fold(n) for n in names]:
            return kind
    return None


def tally_wins(winners, kinds):
    """{wins, winner, tied} from the per-paper winners (None: no win): each kind's wins in the order of `kinds`,
    leaving out kinds without a win; the winner is the kind with the most wins, or none with `tied` listing (sorted)
    the kinds that share the most."""
    wins = {}
    for kind in kinds:
        count = sum(1 for w in winners if w == kind)
        if count:
            wins[kind] = count
    most = max(wins.values()) if wins else 0
    leaders = sorted(k for k, n in wins.items() if n == most) if most else []
    return {"wins": wins, "winner": leaders[0] if len(leaders) == 1 else None,
            "tied": leaders if len(leaders) > 1 else []}


def read_one_paper(settings, facts, paper):
    """One paper's row of the answer: its values by kind (as floats, in the order of the settings' kinds), the top
    value, and the winner or the sorted tie."""
    row = {"document": paper["paper"], "winner": None, "tied": [], "values": {}, "reason": None}
    if "no_comparison" in paper:
        row["reason"] = dict(paper["no_comparison"])
        return row
    found = {}
    for key in paper["values"]:
        fact = facts[key]
        kind = kind_of_thing(facts[fact["thing"]], settings["kinds"])
        found[kind] = float(fact["value"])
    values = {k: found[k] for k in settings["kinds"] if k in found}
    top = (max if settings["higher_is_better"] else min)(values.values())
    leaders = sorted(k for k, v in values.items() if v == top)
    row["values"] = values
    row["winner"] = leaders[0] if len(leaders) == 1 else None
    row["tied"] = leaders if len(leaders) > 1 else []
    return row


def rebuild_answer(settings, facts, papers, model_text):
    """The best answer, rebuilt from the recorded facts alone (`model_text` is not used)."""
    studies = [read_one_paper(settings, facts, paper) for paper in papers]
    view = {"metric": settings["measure"]}
    view.update(tally_wins([s["winner"] for s in studies], settings["kinds"]))
    view["studies"] = studies
    return view


def answer_lines(settings, view, names):
    """The lines of a best answer: one summary line, then one line per paper, cut to the most lines an answer shows."""
    metric = name_of(names, view.get("metric") or settings["measure"])
    studies = view.get("studies", [])
    winner, tied = view.get("winner"), view.get("tied", [])
    if winner is not None:
        wins = sorted(view.get("wins", {}).items(), key=lambda pair: (-pair[1], name_of(names, pair[0])))
        counts = join_words([name_of(names, k) + " " + str(n) for k, n in wins])
        head = [f"On {metric}, {name_of(names, winner)} is best in the most papers ({counts})."]
    elif tied and any(s.get("winner") or s.get("tied") for s in studies):
        head = [f"On {metric}, no single kind is best: {join_words([name_of(names, k) for k in tied])} tie."]
    else:
        head = [CANT_TELL_LINE]
    body = []
    for study in studies:
        if study.get("winner"):
            body.append(f"{study['document']}: {name_of(names, study['winner'])} is best.")
        elif study.get("tied"):
            body.append(f"{study['document']}: {join_words([name_of(names, k) for k in study['tied']])} tie.")
        else:
            body.append(f"{study['document']}: no comparison ({reason_text(study.get('reason'), settings, names)}).")
    return cut_lines(head + body)


def notes_of(view):
    """The notes printed under the answer: none, because a fixed kind's answer is rebuilt in full."""
    return []
