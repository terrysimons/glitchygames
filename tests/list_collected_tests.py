"""A pytest plugin that writes every collected test's node id to a file, one a line.

For a test that needs the whole suite's node ids from a child ``pytest --collect-only``
(tests/test_suite_collection.py): the listing pytest prints is its tree, whatever the verbosity
asked for. The file is named by ``GLITCHYGAMES_COLLECTED_TESTS_OUTPUT``; unset, the plugin does
nothing.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    import pytest

OUTPUT_VARIABLE: Final = 'GLITCHYGAMES_COLLECTED_TESTS_OUTPUT'


def pytest_collection_finish(session: pytest.Session) -> None:
    """Write the collected node ids, when the variable names a file."""
    output = os.environ.get(OUTPUT_VARIABLE)
    if output is None:
        return
    Path(output).write_text(''.join(f'{item.nodeid}\n' for item in session.items), encoding='utf-8')
