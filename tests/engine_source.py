"""Where the engine's source is in this checkout, for the engine's tests.

The engine's tests (the shared harness, the source guards) need only this, so they need not
import scripts/workspace_packages.py, which reads the whole workspace (Part 3, Stage D, Task D9:
no engine test reaches ``scripts.*``). ``tests/test_workspace_packages.py`` keeps the two equal.
"""

from __future__ import annotations

from pathlib import Path

ENGINE_PACKAGE = 'glitchygames'
# Where the engine's source package is, relative to the repository: under src/, so nothing run
# from the repository root imports the source tree by accident (the user, 2026-10-25;
# scripts/workspace_packages.py ENGINE_DIRECTORY)
ENGINE_DIRECTORY = Path('src') / ENGINE_PACKAGE
