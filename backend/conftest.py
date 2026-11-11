"""On Windows, a test file that loads `agent.sandbox` is skipped with a reason instead of failing to load.

The sandbox is POSIX-only: it kills process groups and reads `signal.SIGKILL` when it is imported, and Windows
has no such signal. On Linux and macOS this file changes nothing.
"""
from __future__ import annotations

import sys

import pytest

POSIX_ONLY = "module 'signal' has no attribute 'SIGKILL'"
REASON = "loads agent.sandbox, which needs signal.SIGKILL at import (POSIX only)"


class _WindowsModule(pytest.Module):
    def collect(self):
        try:
            return list(super().collect())
        except (AttributeError, self.CollectError) as err:   # an import error arrives as CollectError, any other as itself
            if POSIX_ONLY in str(err):
                pytest.skip(REASON, allow_module_level=True)
            raise


def pytest_pycollect_makemodule(module_path, parent):
    if sys.platform == "win32":
        return _WindowsModule.from_parent(parent, path=module_path)
    return None
