"""Root pytest configuration.

pytest only accepts ``pytest_plugins`` in the rootdir (top-level) conftest, so plugins the
suite needs are declared here rather than in tests/conftest.py.
"""

# pytester runs a test sequence in a fresh interpreter (tests/world/test_mock_isolation.py);
# glitchygames.testing.replays runs each recording under tests/fixtures/replays/<console-script>/
# as a test item (a headless replay through the real engine); tests.driver_comparison runs a local
# run on the native SDL driver too and compares the frames glitchygames.testing.frame_fingerprints
# records (it must configure before that plugin reads its variables: its hook is tryfirst)
pytest_plugins = [
    'pytester',
    'glitchygames.testing.replays',
    'tests.driver_comparison',
    'glitchygames.testing.frame_fingerprints',
]
