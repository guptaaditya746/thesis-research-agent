"""Load the frozen JSON Schemas in agent/schemas/ and validate documents against them."""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"


@cache
def load(name: str) -> dict[str, Any]:
    """`name` is e.g. "config" for agent/schemas/config.schema.json."""
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def errors(schema: dict[str, Any], doc: Any) -> list[str]:
    """Every validation error as "path: message"; empty means valid."""
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    found = sorted(validator.iter_errors(doc), key=lambda e: list(map(str, e.absolute_path)))
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in found]


def check(name: str, doc: Any) -> list[str]:
    return errors(load(name), doc)
