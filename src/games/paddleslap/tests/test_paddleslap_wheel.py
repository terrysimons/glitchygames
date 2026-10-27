"""PaddleSlap's rally demo ships inside its package, where the replay plugin finds it."""

from __future__ import annotations

from pathlib import Path

import paddleslap
from glitchygames.testing.replays import bundled_demo_paths

# The rally demo ships inside the package (package data), beside its __init__.py
RALLY_DEMO_PATH = Path(paddleslap.__file__).parent / 'demos' / 'rally.jsonl.gz'


def test_bundled_demos_are_found_in_member_packages():
    """The rally demo is found inside the paddleslap package and replayed by its console script."""
    assert ('paddleslap', RALLY_DEMO_PATH) in bundled_demo_paths()
    assert RALLY_DEMO_PATH == paddleslap.PADDLESLAP_DEMO_PATH
    assert RALLY_DEMO_PATH.is_file()
