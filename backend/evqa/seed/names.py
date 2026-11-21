"""Made-up names: the LLM proposes, code checks and picks.

One LLM call per name slot proposes 8 candidates. Code keeps the first candidate that
  - is 6-14 letters, letters only;
  - is not a MeSH or ChEBI label, and no label is close to it (rapidfuzz ratio < CLOSE);
  - is not close to a name already picked for another slot (ratio < CLOSE_OWN).
It also makes a short code name (`VLZ-104`) from the name and checks that it is not a label either. Every candidate,
its nearest real label and the score go into `names.json`, so the check can be redone by hand.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from rapidfuzz import fuzz, process

from evqa import llm
from evqa.seed.vocab import norm

CLOSE = 85        # ratio (0-100) at or above which a real label counts as a clash
CLOSE_OWN = 70    # between two of our own names (they must be easy to tell apart)
ROUNDS = 3
SCHEMA = {"type": "object", "properties": {"names": {"type": "array", "items": {"type": "string"},
                                                     "minItems": 8, "maxItems": 8}},
          "required": ["names"], "additionalProperties": False}
SYSTEM = """Task: invent 8 new names for one thing in a made-up dataset. No real thing may have these names.

Input fields:
- kind: what the thing is (e.g. a drug).
- avoid: names already used or rejected; your names must look clearly different from them.

Output: {"names": [8 strings]}. Each name is one word, 6 to 14 letters, letters only, lower case, easy to say.
For a drug, make it look like an international nonproprietary name, but do not end it with a real drug-class stem
(-gliflozin, -gliptin, -glutide, -mab, -tinib, -pril, -sartan, -statin, -olol, -azole).

Examples:
input: {"kind": "oral once-daily blood-pressure drug", "avoid": []}
output: {"names": ["corvantel", "melisoran", "tavedrin", "pelorast", "ximbaron", "duvarel", "quenatrol", "lomivex"]}

input (names close to real drugs must be avoided): {"kind": "oral glucose-lowering drug", "avoid": ["metformin"]}
output: {"names": ["velotrazin", "sorbanide", "kelutrin", "fapmorel", "trivacene", "duromast", "zenquirol", "halibrex"]}

input (kind is vague, still give 8 names): {"kind": "", "avoid": ["velotrazin"]}
output: {"names": ["obrinal", "marquelon", "pistavor", "renduxil", "ulmarocet", "gavintrel", "ceptarin", "sondalex"]}"""


def code_name(name: str) -> str:
    """A development code like `VLZ-104`: first letter + next two consonants, and 3 digits from a hash."""
    rest = [c for c in name[1:].lower() if c not in "aeiou"]
    letters = (name[0] + "".join(rest[:2])).upper()
    return f"{letters}-{100 + int(hashlib.sha256(name.encode()).hexdigest(), 16) % 900}"


def nearest(key: str, index: dict[str, tuple[str, str]]) -> dict[str, Any]:
    hit = process.extractOne(key, index.keys(), scorer=fuzz.ratio)
    label, src = index[hit[0]]
    return {"label": label, "source": src, "score": round(hit[1], 1)}


def judge(name: str, index: dict[str, tuple[str, str]], picked: list[str]) -> dict[str, Any]:
    """Check one candidate; `ok` is True only when every rule passes."""
    key = norm(name)
    near = nearest(key, index)
    own = max((fuzz.ratio(key, norm(p)) for p in picked), default=0.0)
    code = code_name(name)
    problems = []
    if not re.fullmatch(r"[a-z]{6,14}", name):
        problems.append("not 6-14 lower-case letters")
    if key in index or near["score"] >= CLOSE:
        problems.append(f"close to real label {near['label']!r} ({near['source']})")
    if own >= CLOSE_OWN:
        problems.append("close to another made-up name")
    if norm(code) in index:
        problems.append(f"code {code} is a real label")
    return {"name": name, "code": code, "nearest": near, "closest_own": round(own, 1), "ok": not problems,
            "problems": problems}


def propose(lm: Any, kind: str, avoid: list[str]) -> list[str]:
    user = json.dumps({"kind": kind, "avoid": avoid}, ensure_ascii=False)
    out = llm.call(lm, SYSTEM, user, SCHEMA, step="seed.names")
    return [n.strip().lower() for n in out["names"]]


def invent(lm: Any, slots: dict[str, str], index: dict[str, tuple[str, str]],
           keep: list[str] | None = None) -> dict[str, Any]:
    """{slot: {name, code, checked: [...]}} for every slot (slot -> kind). Raises if a slot finds no name.
    `keep`: names already picked earlier (new names must differ from them and are proposed with them as `avoid`)."""
    keep = list(keep or [])
    proposals = dict(zip(slots, llm.pmap(lambda s: propose(lm, slots[s], keep), list(slots)), strict=True))
    picked: list[str] = list(keep)
    out: dict[str, Any] = {}
    for slot, kind in slots.items():
        checked: list[dict[str, Any]] = []
        candidates = proposals[slot]
        for _ in range(ROUNDS):
            for name in candidates:
                verdict = judge(name, index, picked)
                checked.append(verdict)
                if verdict["ok"]:
                    break
            if checked and checked[-1]["ok"] and checked[-1]["code"][:3] not in {code_name(p)[:3] for p in picked}:
                break
            if checked and checked[-1]["ok"]:     # same code letters as another drug: too easy to mix up
                checked[-1] = {**checked[-1], "ok": False, "problems": ["code letters as another made-up name"]}
            candidates = propose(lm, kind, picked + [c["name"] for c in checked])
        if not checked[-1]["ok"]:
            raise ValueError(f"no usable name for {slot} after {ROUNDS} rounds")
        picked.append(checked[-1]["name"])
        out[slot] = {"name": checked[-1]["name"], "code": checked[-1]["code"], "kind": kind, "checked": checked}
    return {"model": lm.model, "prompt_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest(), "close": CLOSE,
            "close_own": CLOSE_OWN, "slots": out}
