"""The rules of the inventory kind, copied from the engine (drift tests pin each copy): the distinct names, the
other forms each goes by, the papers each was found in, and the answer's lines."""
from .common import (CANT_TELL_LINE, INVENTORY_TARGETS, cut_lines, fold, join_words)  # program: drop
# --- rules ---


def rebuild_answer(settings, facts, papers, model_text):
    """The inventory answer, rebuilt from the recorded facts alone (`model_text` is not used): a name that folds to
    a `same` name or one of its others is named by that `same` name, any other name by the first form met."""
    canonical = {}
    for name in settings["same"]:
        canonical[fold(name)] = name
    for name, others in settings["same"].items():
        for other in others:
            if fold(other) not in canonical:
                canonical[fold(other)] = name
    found = {}
    for paper in papers:
        for key in paper["names"]:
            form = facts[key]["name"]
            name = canonical.get(fold(form), form)
            group = found.setdefault(fold(name), {"name": name, "forms": [], "papers": []})
            if form not in group["forms"]:
                group["forms"].append(form)
            if paper["paper"] not in group["papers"]:
                group["papers"].append(paper["paper"])
    entries = [{"name": g["name"], "aliases": sorted(f for f in g["forms"] if f != g["name"]),
                "papers": g["papers"]}
               for g in sorted(found.values(), key=lambda g: (fold(g["name"]), g["name"]))]
    return {"target": settings["target"], "entries": entries}


def answer_lines(settings, view, names):
    """The lines of an inventory answer: one summary line, then one line per name, cut to the most lines an answer
    shows."""
    entries = view.get("entries", [])
    if not entries:
        return [CANT_TELL_LINE]
    target = view.get("target") or settings["target"]
    kind = INVENTORY_TARGETS.get(target, target.replace("_", " ") + "s")
    body = []
    for entry in entries:
        also = f" (also {join_words(entry['aliases'])})" if entry.get("aliases") else ""
        body.append(f"{entry['name']}{also}: {join_words(entry.get('papers', []))}.")
    return cut_lines([f"{len(entries)} distinct names of {kind}."] + body)


def notes_of(view):
    """The notes printed under the answer: none, because a fixed kind's answer is rebuilt in full."""
    return []
