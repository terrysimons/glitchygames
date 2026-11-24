# An Import of httpcore2 Failed With KeyError on CircleCI's Windows Job

- **Description**: CircleCI job 4241 (`test-python-3-15-windows`, node 0, branch
  `docs/arcade-5-playback-core-plan` at `0e5de482`) failed
  `tests/test_ai_model_comparison.py::test_asking_sends_what_the_console_sends_and_times_the_answer`
  with `KeyError: 'httpcore2._synchronization'`, raised from `<frozen importlib._bootstrap>:868`
  while `httpx2.Client` imported `httpcore2` for the first time in that worker (lazily, in
  `HTTPTransport.__init__`). It failed once; the job's other runs of the test pass. Evidence (the
  job log's tail, the step output's `[gw0]` lines, node 0's junit) is in the owner's
  `.superpowers/overnight-2026-11-20/job4241-*`.
- **Status**: Open (root cause not found; a triage tool is in, 2026-11-20, branch
  `fix/httpcore2-import-keyerror-triage`)
- **Priority**: Medium (a CI flake; the same class can break any import in the suite)
- **What the error means**: importlib's `_load_unlocked` runs the module, then does
  `module = sys.modules.pop(spec.name)`. A `KeyError` there means the module's entry left
  `sys.modules` while the module's own code was running. Its code does not remove itself, so
  something else did, and the importing thread's traceback cannot show what.
- **Reproduced (the mechanism, not the CI run)**, with scripts kept in
  `scripts/reproduce_import_keyerror.py`:
  - A second thread restoring a `sys.modules` snapshot (as `mock.patch.dict(sys.modules)` does
    when its patch ends: `clear()` then `update(snapshot)`) while the main thread imports httpcore2
    for the first time: about 10% of 300 tries fail, with this exact `KeyError` (for
    `httpcore2`, `httpcore2._sync`, `httpcore2._types` and others) or "cannot import name ... from
    partially initialized module".
  - Ruled out: two threads importing httpcore2 at once with no restore (600 of 600 imports
    succeed); a leftover thread mid-import when the main thread restores a snapshot and then
    imports (400 of 400 main-thread imports succeed).
- **What ran before it**: node 0's junit (completion order, `-n 2`) puts the failing test right
  after five `tests/replay/tools/test_compare_trace.py` tests (the other worker was in
  `test_verify.py`'s 13 s test), the last being
  `test_an_old_that_streams_nothing_is_labelled_and_nothing_is_drawn[never-connects]`, whose
  `color_game` fixture does `mocker.patch.dict(sys.modules)`. That restore runs on the main
  thread at teardown, before the next test starts, so it cannot overlap the next test's import;
  and no code found restores `sys.modules` off the main thread. Running that order locally
  (`-n 0`, the five tests then the failing one) passed 15 times of 15.
- **Test gap**: nothing records the other threads when an import fails, so the one failure gave
  only the importing thread's stack.
- **The triage tool**: `tests/import_failure_threads.py` (a plugin in the root `conftest.py`)
  marks every thread with the test that started it and, when a test's call fails inside the import
  machinery, adds `live threads at the import failure` to its report: each live thread, daemon or
  not, the test that started it, and its stack. The next occurrence names the other thread. Tests:
  `tests/test_import_failure_threads.py` (a planted failure, a module that deletes its own
  `sys.modules` entry mid-import, gives the CI signature).
- **The class, swept** (2026-11-20; `git grep` for `sys.modules` changes in `tests/` and `src/`):
  - Whole-dict restores (uncovered: each one, when it ends, drops every module imported since it
    began, on any thread, and a thread importing at that moment fails as above). `mock.patch.dict`
    restores the whole dict whether or not it is given values, so all 26 are in this class:
    `tests/replay/tools/test_compare_trace.py` (1, the suspect),
    `src/apps/bitmappy/tests/test_bitmappy_film_strip_operations.py` (2, with
    `del sys.modules['pytest']`), `src/apps/bitmappy/tests/test_bitmappy_film_strip.py` (3),
    `tests/timing/test_timing.py` (6), `tests/events/test_voice_backends.py` (4),
    `tests/test_generate_complexity_graphs.py` (3), `tests/replay/tools/test_identity.py` (2),
    `tests/test_clipboard.py` (2), `tests/engine/test_game_engine.py` (1),
    `tests/test_workspace_config.py` (1), `tests/test_browser_storage.py` (1).
  - Single-entry changes (covered: `monkeypatch.setitem`/`delitem` put back only their key):
    `tests/audio/test_audio_engine.py`, `tests/templates/test_templates_extra.py`,
    `tests/replay/tools/test_golden_trace_harness.py`, `tests/replay/tools/test_scripted_sessions.py`,
    `tests/replay/test_replay_plugin.py`.
  - Pops of a test's own stand-in package, on the main thread (covered: they remove only a name
    the test itself imported): `tests/engine/test_inner_game.py` (8),
    `tests/engine/test_inner_engine.py`, `tests/benchmarks/test_engine_context_benchmarks.py`,
    `tests/replay/tools/test_golden_trace_harness.py` (2),
    `tests/replay/tools/test_scripted_sessions.py`.
  - A reload (covered: re-runs a module in place; removes no entry):
    `src/apps/bitmappy/tests/test_bitmappy_ai_manager.py`.
- **Fix to make (once the evidence implicates a restore)**: replace the whole-dict restores with
  one helper that removes, at the test's end, only the modules the test itself added under the
  names it owns, and a guard test that refuses `patch.dict(sys.modules ...)` in the suite.
- **Reporter**: The coordinating session (glitchygames-bc)
- **Date Reported**: 2026-11-20
- **Files**: `tests/import_failure_threads.py`, `tests/test_import_failure_threads.py`,
  `conftest.py`, `scripts/reproduce_import_keyerror.py`
