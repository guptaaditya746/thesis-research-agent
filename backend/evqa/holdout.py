"""The hold-out rule in one place: hold-out runs are SCORE ONLY, and hold-out gold is never shown
(configs/evqa/holdout-*.yaml header, docs/design/slice1.md). Their totals may be read; their per-question outputs
(spec, find, rows, links, settings, answer, per-question events and scores) and their gold answers may not.

A run is hold-out when its config domain ends in `_holdout` or its config name (or, when the config cannot be
read, its folder name) starts with `holdout-`. bench-* runs are not covered here (their per-question outputs stay
browsable for inspection; only explain.py keeps them closed).
"""
from __future__ import annotations

from typing import Any

SUFFIX = "_holdout"
PREFIX = "holdout-"
RUN_MESSAGE = ("{run} is a hold-out run: score only. Its per-question outputs stay closed "
               "(configs/evqa/holdout-*.yaml); only its totals can be shown.")
GOLD_MESSAGE = "{domain} is a hold-out domain: its gold answers stay closed; only the question text can be shown."


def is_holdout_domain(domain: Any) -> bool:
    return isinstance(domain, str) and domain.endswith(SUFFIX)


def run_closed(cfg: dict[str, Any], folder: str = "") -> str | None:
    """Why the run's per-question outputs stay closed, or None when they may be shown. A config that could not be
    read ({"_error": ...}) counts as closed: it cannot be told apart from a hold-out run."""
    name = cfg.get("name")
    if ("_error" in cfg or is_holdout_domain(cfg.get("domain")) or folder.startswith(PREFIX)
            or (isinstance(name, str) and name.startswith(PREFIX))):
        return RUN_MESSAGE.format(run=folder or name or "this run")
    return None


def gold_closed(domain: str) -> str | None:
    """Why the domain's gold answers stay closed, or None."""
    return GOLD_MESSAGE.format(domain=domain) if is_holdout_domain(domain) else None
