"""Service boundaries (backend/README.md): a package imports only its own service or one below it.

Order, bottom to top: gateway < engine < evaluation < api. Tests are not checked (they may reach across to reuse
fakes). A wrong-way import that exists today is listed in KNOWN with its reason; a new one fails here.
"""
from __future__ import annotations

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SERVICES = {
    "gateway": ("modelcall",),
    "engine": ("evidence", "agent", "gold", "jsonio"),
    "evaluation": ("evaluation", "scoring", "synth", "packbuilder"),
    "api": ("webapp",),
}
RANK = {pkg: rank for rank, pkgs in enumerate(SERVICES.values()) for pkg in pkgs}
SHARED = {"repo_paths"}   # folder locations only; any package may import it
# (importer, imported): reason. Keep the list short; fix an entry rather than add one.
KNOWN = {
    ("modelcall", "jsonio"): "canonical JSON and atomic writes; jsonio is hashed into extractor ids, so it stays put",
}


def imports(pkg: str) -> set[tuple[str, str]]:
    """(file, imported package) for every absolute import of another backend package outside tests/."""
    found = set()
    for f in (BACKEND / pkg).rglob("*.py"):
        if "tests" in f.relative_to(BACKEND).parts:
            continue
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module
                     else [])
            for name in names:
                top = name.split(".")[0]
                if top != pkg and (top in RANK or top in SHARED):
                    found.add((f.relative_to(BACKEND).as_posix(), top))
    return found


def test_every_backend_package_has_a_service() -> None:
    packages = {p.name for p in BACKEND.iterdir() if (p / "__init__.py").is_file()}
    assert packages == set(RANK) | SHARED


def test_imports_follow_the_service_order() -> None:
    wrong = sorted((f, top) for pkg in RANK for f, top in imports(pkg)
                   if top in RANK and RANK[top] > RANK[pkg] and (pkg, top) not in KNOWN)
    assert wrong == [], "import against the direction gateway < engine < evaluation < api (backend/README.md)"


def test_known_exceptions_still_exist() -> None:
    """A fixed exception is taken off the list, so the list stays the truth."""
    for pkg, top in KNOWN:
        assert any(t == top for _, t in imports(pkg)), (pkg, top)
