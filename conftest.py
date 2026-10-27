"""Root pytest configuration.

pytest only accepts ``pytest_plugins`` in the rootdir (top-level) conftest, so plugins the
suite needs are declared here; the shared test harness (tests/harness.py) is one of them.
"""

# tests.harness is the shared test harness (fixtures, SDL defaults, display canvas): first, so its
# SDL defaults are in place before any other plugin imports pygame, and loaded here so every
# package's tests (tests/, src/games/*/tests/) get it
# pytester runs a test sequence in a fresh interpreter (tests/world/test_mock_isolation.py);
# tests.driver_comparison runs a local run on the native SDL driver too and compares the
# frames glitchygames.testing.frame_fingerprints records (it must configure before that plugin
# reads its variables: its hook is tryfirst)
pytest_plugins = [
    'tests.harness',
    'pytester',
    'tests.driver_comparison',
    'glitchygames.testing.frame_fingerprints',
]
