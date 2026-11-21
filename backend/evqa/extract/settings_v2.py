"""Read settings with exact, domain-free source checks (prompt v2)."""
from __future__ import annotations

import json
import re
import dspy
from pydantic import BaseModel, Field
from evqa.contracts import Dimension, Row, Setting, SettingSet
from evqa.extract import anchor
from evqa.extract.prompt import field_first
from evqa.llm import service_failed


class DraftSetting(BaseModel):
    dimension: str
    value: str = "not stated"
    quote: str = ""
    source: str = "paper"


class DraftSet(BaseModel):
    settings: list[DraftSetting] = Field(default_factory=list)
    extra_settings: list[DraftSetting] = Field(default_factory=list)


class ReadSettings(dspy.Signature):
    """Extract the paper's settings for each dimension. Input: dimensions are the question's keys and definitions;
    context and passages are paper excerpts; feedback lists failed checks, if any. Output setting_sets, one per
    distinct setting combination explicitly described, with settings containing dimension, value, quote and source.
    Copy each value and quote exactly from the paper. Use value "not stated" and quote "" for missing dimensions.
    Source is "paper" for paper context. For a dimension not listed that varies between rows, put one entry per
    distinct result setting in extra_settings, with the same dimension key and exact value and quote from the row.
    Exclude background claims and excluded groups. Return one set with missing
    values if the source describes no settings.

    Medicine: dimensions [{"key":"population"}], text "The trial enrolled children with asthma." ->
    [{"settings":[{"dimension":"population","value":"children with asthma",
    "quote":"The trial enrolled children with asthma.","source":"paper"}]}].
    Materials: dimensions [{"key":"temperature"}], text "Specimens were tested at 500 C." ->
    [{"settings":[{"dimension":"temperature","value":"500 C","quote":"Specimens were tested at 500 C.",
    "source":"paper"}]}].
    ML: dimensions [{"key":"dataset"}], text "The dataset was not reported." ->
    [{"settings":[{"dimension":"dataset","value":"not stated","quote":"","source":"paper"}]}].
    """
    context: str = dspy.InputField()        # paper text first, question last: vLLM prefix caching reuses the paper
    passages: str = dspy.InputField()
    dimensions: str = dspy.InputField()
    feedback: str = dspy.InputField()
    setting_sets: list[DraftSet] = dspy.OutputField()


ReadSettingsV1 = field_first(ReadSettings, "dimensions")   # predecessor (before 21 Nov 2026): dimensions first


class SettingVerdict(BaseModel):
    id: str
    supported: bool


class VerifySettings(dspy.Signature):
    """Check whether each candidate setting is supported for the reported result by the supplied source.

    Input: source is the paper excerpts and candidates is a JSON list with id, dimension, value and quote.
    Output: verdicts has one {id, supported} per candidate. Supported is false if a quote describes background,
    exclusions, a different result, or does not establish the claimed setting. Copy each id exactly. Do not add
    or infer values. Example: source "Specimens were tested at 500 C", candidate {id:"1", dimension:"temperature",
    value:"500 C", quote:"Specimens were tested at 500 C"} -> [{id:"1", supported:true}]. Example: source
    "Prior studies used 700 C. Our specimens were tested at 500 C", candidate {id:"2", dimension:"temperature",
    value:"700 C", quote:"Prior studies used 700 C"} -> [{id:"2", supported:false}]. Empty candidates -> [].
    """
    source: str = dspy.InputField()
    candidates: str = dspy.InputField()
    verdicts: list[SettingVerdict] = dspy.OutputField()


class SelectSetting(dspy.Signature):
    """Choose the setting set that describes this row's result. Input: setting_sets are the candidate IDs and
    checked settings; row_quote and section describe the result. Output setting_id is one exact candidate ID when
    the row supports it, otherwise an empty string. Do not guess when more than one candidate could apply."""
    setting_sets: str = dspy.InputField()
    row_quote: str = dspy.InputField()
    section: str = dspy.InputField()
    setting_id: str = dspy.OutputField()


def _span(index: anchor.Index, quote: str) -> tuple[int, int] | None:
    """Where the quote is in the paper (same tolerance as row quotes: line breaks, dash types, curly quotes)."""
    found = anchor.spans(index, quote) if quote else []
    return found[0] if found else None


def within(part: str, whole: str) -> bool:
    """`part` occurs in `whole` after the anchor normalisation (used to match setting quotes to row quotes)."""
    a, b = anchor.normalize(part), anchor.normalize(whole)
    return bool(a) and a in b


def check(paper: str, dimensions: list[Dimension], drafts: list[DraftSet], text: str) -> tuple[list[SettingSet], list[str]]:
    keys = [d.key for d in dimensions]
    result, failures = [], []
    index = anchor.Index(text)
    for n, draft in enumerate(drafts, 1):
        by_key: dict[str, DraftSetting] = {}
        for setting in draft.settings:
            if setting.dimension not in keys or setting.dimension in by_key:
                failures.append(f"set {n}: unknown or repeated dimension {setting.dimension!r}")
            else:
                by_key[setting.dimension] = setting
        checked_settings = []
        for key in keys:
            d = by_key.get(key)
            error = ""
            span = None          # per setting: never the previous setting's offsets; "not stated" has none
            if d is None:
                error = "missing dimension"
            elif d.value == "not stated":
                if d.quote:
                    error = "not stated must have an empty quote"
            elif not d.quote or (span := _span(index, d.quote)) is None:
                error = "quote is not in the paper"
            elif not d.value or d.value not in d.quote:
                error = "value is not copied from quote"
            elif any(x not in d.quote for x in re.findall(r"\d+(?:\.\d+)?", d.value)):
                error = "number is not in quote"
            elif d.source not in ("paper", "row"):
                error = "invalid source"
            if error:
                failures.append(f"set {n} {key}: {error}")
                checked_settings.append(Setting(dimension=key, note=error))
            elif d is not None:
                checked_settings.append(Setting(dimension=key, value=d.value, quote=d.quote, source=d.source,
                                                start=span[0] if span else None, end=span[1] if span else None))
        for extra in draft.extra_settings:
            if not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", extra.dimension) or extra.dimension in keys:
                failures.append(f"set {n}: invalid extra dimension {extra.dimension!r}")
            elif (not extra.quote or (span := _span(index, extra.quote)) is None or not extra.value
                  or extra.value not in extra.quote):
                failures.append(f"set {n} {extra.dimension}: extra value or quote not grounded")
            else:
                checked_settings.append(Setting(dimension=extra.dimension, value=extra.value, quote=extra.quote,
                                                source="row", extra=True, start=span[0], end=span[1]))
        label = " · ".join(s.value for s in checked_settings if s.value != "not stated") or "not stated"
        result.append(SettingSet(id=f"{paper}/setting{n}", paper=paper, settings=checked_settings, label=label))
    if not drafts:
        failures.append("no setting set returned")
    return result, failures


def read(paper: str, dimensions: list[Dimension], context: str, passages: str, text: str, lm: dspy.BaseLM,
         verifier: dspy.BaseLM | None = None, trace: list[dict] | None = None) -> list[SettingSet]:
    """Checked setting sets for one paper. `trace` (optional) gets one record per attempt: the raw candidate sets,
    the code checks that failed, the verifier's candidates and verdicts, and whether the attempt was accepted."""
    feedback = ""
    result: list[SettingSet] = []
    for attempt in range(2):
        step: dict = {"attempt": attempt, "drafts": None, "check_failures": [], "verifier": None,
                      "verifier_failures": [], "accepted": False, "error": ""}
        if trace is not None:
            trace.append(step)
        try:
            with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
                out = dspy.Predict(ReadSettings)(dimensions=json.dumps([d.model_dump() for d in dimensions]),
                    context=context, passages=passages, feedback=feedback, config={"attempt": attempt} if attempt else {})
            drafts = [d if isinstance(d, DraftSet) else DraftSet.model_validate(d) for d in out.setting_sets]
            step["drafts"] = [d.model_dump() for d in drafts]
            result, failures = check(paper, dimensions, drafts, text)
            step["check_failures"] = list(failures)
            step["checked_sets"] = [g.model_dump() for g in result]
            if not failures:
                candidates = [(f"{i}:{j}", setting) for i, group in enumerate(result)
                              for j, setting in enumerate(group.settings) if setting.value != "not stated"]
                if candidates:
                    try:
                        with dspy.context(lm=verifier or lm, adapter=dspy.JSONAdapter()):
                            review = dspy.Predict(VerifySettings)(source=context + "\n\n" + passages,
                                candidates=json.dumps([{"id": k, **v.model_dump()} for k, v in candidates]))
                        verdicts = [v if isinstance(v, SettingVerdict) else SettingVerdict.model_validate(v)
                                    for v in review.verdicts]
                        by_id = {v.id: v.supported for v in verdicts}
                        if len(verdicts) != len(candidates) or set(by_id) != {k for k, _ in candidates}:
                            raise ValueError("verdict IDs do not match candidates")
                        step["verifier"] = {"candidates": [{"id": k, **v.model_dump()} for k, v in candidates],
                                            "verdicts": [v.model_dump() for v in verdicts]}
                        failures = [f"{k}: verifier did not support value" for k, _ in candidates if not by_id[k]]
                    except Exception as exc:
                        if service_failed(exc):
                            raise
                        step["verifier"] = step["verifier"] or {"candidates": [{"id": k, **v.model_dump()}
                                                                              for k, v in candidates], "verdicts": []}
                        step["error"] = f"verifier: {type(exc).__name__}: {exc}"[:500]
                        failures = ["verification failed or returned invalid IDs"]
                    step["verifier_failures"] = list(failures)
                    if failures:
                        for _, setting in candidates:
                            setting.value, setting.quote, setting.note = "not stated", "", "; ".join(failures)
                        for group in result:
                            group.label = " · ".join(x.value for x in group.settings if x.value != "not stated") or "not stated"
                if not failures:
                    step["accepted"] = True
                    return result
            feedback = "Rejected output: " + json.dumps([d.model_dump() for d in drafts]) + "\nFailed checks: " + "; ".join(failures)
        except Exception as exc:
            if service_failed(exc):
                raise
            step["error"] = f"{type(exc).__name__}: {exc}"[:500]
            feedback = f"Unreadable output: {type(exc).__name__}"
    return result or [SettingSet(id=f"{paper}/setting1", paper=paper,
        settings=[Setting(dimension=d.key, note="extraction failed") for d in dimensions], label="not stated")]


def assign(row: Row, sets: list[SettingSet], section: str, lm: dspy.BaseLM) -> None:
    picked = sets[0] if len(sets) == 1 else None
    if len(sets) > 1:
        direct = [group for group in sets if any(s.extra and within(s.quote, row.quote) for s in group.settings)]
        if len(direct) == 1:
            picked = direct[0]
    if len(sets) > 1 and picked is None:
        same = {tuple((x.dimension, x.value) for x in g.settings if not x.extra) for g in sets}
        if len(same) == 1:
            # the sets differ only in extras the row does not quote: every pick gives Link the same values, so code
            # takes the first instead of asking (Haiku practice, 21 Nov: P-med-20 rows were left without a set)
            # without the extras: they belong to other rows (e.g. another arm) and must not label this one
            shared = [x for x in sets[0].settings if not x.extra]
            label = " · ".join(x.value for x in shared if x.value != "not stated") or "not stated"
            row.note = "; ".join(filter(None, (row.note, "setting sets differ only in extras; shared settings taken")))
            row.settings, row.setting_set = sets[0].id, sets[0].model_copy(update={"settings": shared, "label": label})
            return
        try:
            with dspy.context(lm=lm, adapter=dspy.JSONAdapter()):
                out = dspy.Predict(SelectSetting)(setting_sets=json.dumps([s.model_dump() for s in sets]),
                    row_quote=row.quote, section=section)
            picked = next((s for s in sets if s.id == out.setting_id.strip()), None)
        except Exception as exc:
            if service_failed(exc):
                raise
    if picked is None:
        row.note = "; ".join(filter(None, (row.note, "setting set could not be assigned")))
        return
    row.settings, row.setting_set = picked.id, picked


def retain_extras(rows: list[Row], sets: list[SettingSet]) -> set[str]:
    """Keep extras only when distinct checked result rows directly contain the quoted values."""
    support: dict[str, dict[str, set[int]]] = {}
    for group in sets:
        for setting in group.settings:
            if not setting.extra:
                continue
            for i, row in enumerate(rows):
                if row.quote_ok and not row.dropped and row.paper == group.paper and within(setting.quote, row.quote):
                    support.setdefault(setting.dimension, {}).setdefault(setting.value, set()).add(i)
    valid = {key for key, values in support.items() if any(
        a != b and any(i != j for i in indexes for j in other)
        for a, indexes in values.items() for b, other in values.items())}
    expanded: list[SettingSet] = []
    for group in sets:
        group.settings = [s for s in group.settings if not s.extra or s.dimension in valid]
        extra = [s for s in group.settings if s.extra]
        if len({s.dimension for s in extra}) < len(extra):
            # Form combinations only from actual checked rows, never a Cartesian product.
            seen: set[tuple[tuple[str, str], ...]] = set()
            for row in rows:
                if row.paper != group.paper or not row.quote_ok or row.dropped:
                    continue
                observed = [s for s in extra if within(s.quote, row.quote)]
                if not observed or len({s.dimension for s in observed}) != len(observed):
                    continue
                signature = tuple(sorted((s.dimension, s.value) for s in observed))
                if signature in seen:
                    continue
                seen.add(signature)
                fields = [s for s in group.settings if not s.extra] + observed
                expanded.append(group.model_copy(deep=True, update={"settings": fields}))
            if not seen:
                group.settings = [s for s in group.settings if not s.extra]
                expanded.append(group)
        else:
            expanded.append(group)
    for i, group in enumerate(expanded, 1):
        group.id = f"{group.paper}/setting{i}"
        group.label = " · ".join(s.value for s in group.settings if s.value != "not stated") or "not stated"
    sets[:] = expanded
    return valid
