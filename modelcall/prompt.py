"""Prompt templates: one loader, one hash.

A prompt is a file read as UTF-8 with LF line ends whatever the checkout, so its hash is the same on Windows and
on the cluster. `Prompt.sha256` is what every cached result records: the text and the output schema together."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from jsonio import canonical_bytes, sha256_hex

ROOT = Path(__file__).resolve().parents[1]


def prompt_sha256(instructions: str, output_type: type[BaseModel] | None = None) -> str:
    """Hash of a prompt template and its output schema: recorded with every result it produced."""
    schema = output_type.model_json_schema() if output_type else None
    return sha256_hex(canonical_bytes({"instructions": instructions, "schema": schema}))


@dataclass(frozen=True)
class Prompt:
    """One prompt template and the output type it is used with."""
    name: str                                  # the file, relative to the repo root (POSIX), or "inline"
    text: str                                  # LF line ends
    output_type: type[BaseModel] | None = None

    @property
    def sha256(self) -> str:
        return prompt_sha256(self.text, self.output_type)

    @property
    def file_sha256(self) -> str:
        return sha256_hex(self.text.encode("utf-8"))

    def json(self) -> dict[str, str]:
        return {"file": self.name, "file_sha256": self.file_sha256, "prompt_sha256": self.sha256}

    @classmethod
    def inline(cls, text: str, output_type: type[BaseModel] | None = None) -> Prompt:
        return cls("inline", text, output_type)


def load_prompt(path: Path, output_type: type[BaseModel] | None = None, *, strip: bool = False) -> Prompt:
    """The prompt in `path`; `strip` trims it and ends it with one newline (the proposal prompts)."""
    path = Path(path)
    text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
    if strip:
        text = text.strip() + "\n"
    try:
        name = path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        name = path.as_posix()
    return Prompt(name, text, output_type)
