"""The synth3 system runs of the plan page: which built folder a plan is run on."""
from __future__ import annotations

from pathlib import Path

from .evreview import ReviewFiles
from .files import NotFound, check_id
from .settings import Settings


def synth3_folder(settings: Settings, domain: str, seed: int) -> Path:
    """The built folder `<synth3>/built/<domain>/s<seed>`: NotFound for a bad id or a seed that is not built, a
    Conflict (409) naming why when the folder does not load or does not match its spec."""
    check_id(domain, "domain")
    files = ReviewFiles(settings)
    if seed not in files.built_seeds(domain):
        raise NotFound(f"no built folder s{seed} of {domain!r}")
    return files.folder(domain, seed, files.spec(domain)).path
