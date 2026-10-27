"""Testing support for games built on the engine.

``glitchygames.testing.replays`` is a pytest plugin that runs recordings as regression tests,
registered by the engine's ``pytest11`` entry point under that name (``pytest -p
no:glitchygames.testing.replays`` turns it off). ``glitchygames.testing.frame_fingerprints`` (a
pytest plugin that records the frames tests present) and ``glitchygames.testing.frame_comparison``
(comparing those records across SDL drivers or repeated runs) ship in the engine's wheel too.
None of them is imported here, so importing this package never needs pytest.
"""
