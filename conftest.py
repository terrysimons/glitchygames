"""Root pytest configuration.

pytest only accepts ``pytest_plugins`` in the rootdir (top-level) conftest, so plugins the
suite needs are declared here rather than in tests/conftest.py.
"""

# pytester runs a test sequence in a fresh interpreter (tests/world/test_mock_isolation.py)
pytest_plugins = ['pytester']
