"""The standard error a pytest run started with, for a plugin that writes past pytest's capture.

While a test runs, pytest's capture has moved file descriptor 2 to its own file, so a line a
plugin writes there (or to ``sys.__stderr__``, the same descriptor) lands in that test's
captured output: shown only if the test fails, and lost if the process ends at once. Two plugins
end a process from a thread of their own and must be seen first: the memory guard
(tests/memory_guard.py) and the per-test limit (tests/per_test_limit.py, whose line job 5171
lost: bugs/2026-11-20-native-run-burned-two-hours-on-a-broken-coreaudio.md). Both write to
this descriptor.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


def original_standard_error(*, config: pytest.Config) -> int:
    """Return a file descriptor of the standard error the run started with.

    pytest's capture has already moved file descriptor 2 to its own file when plugins configure,
    and keeps the original as its error capture's ``targetfd_save`` (pytest's own name, read
    defensively). A run without capture (``-s``) still has the original as descriptor 2.

    Returns:
        A duplicate of it, owned by the caller.

    """
    capture = config.pluginmanager.get_plugin('capturemanager')
    global_capturing = getattr(capture, '_global_capturing', None)
    error_capture = getattr(global_capturing, 'err', None)
    saved = getattr(error_capture, 'targetfd_save', None)
    return os.dup(saved if isinstance(saved, int) else 2)
