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
# tests.memory_guard stops a run past GLITCHYGAMES_TEST_RSS_LIMIT_MB (the Linux CI job's), naming
# the test, instead of the kernel's signal 9 (BUGS.md #235); unset, it does nothing
# tests.collection_logger_levels stops a run whose collected imports set a project logger's level
# or disabled logging (BUGS.md #235, #236)
# tests.disk_sound_cache gives a test the sound cache's disk layer (the harness turns it off) and
# fails one that never used it
# tests.circleci_test_split keeps one CircleCI machine's share of the suite when
# GLITCHYGAMES_TEST_SPLIT is set (the split CI jobs); unset, it does nothing
pytest_plugins = [
    'tests.harness',
    'pytester',
    'tests.driver_comparison',
    'glitchygames.testing.frame_fingerprints',
    'tests.memory_guard',
    'tests.collection_logger_levels',
    'tests.disk_sound_cache',
    'tests.circleci_test_split',
]
