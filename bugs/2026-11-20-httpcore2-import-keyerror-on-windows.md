# An Import of httpcore2 Failed With KeyError on CircleCI's Windows Job

- **Description**: CircleCI job 4241 (`test-python-3-15-windows`, node 0, branch
  `docs/arcade-5-playback-core-plan` at `0e5de482`) failed
  `tests/test_ai_model_comparison.py::test_asking_sends_what_the_console_sends_and_times_the_answer`
  with `KeyError: 'httpcore2._synchronization'`, raised from `<frozen importlib._bootstrap>:868`
  while `httpx2.Client` imported `httpcore2` for the first time in that worker (lazily, in
  `HTTPTransport.__init__`). It failed once in that job; the test's other runs there passed.
  Evidence (the job log's tail, the step output's `[gw0]` lines, node 0's junit) is in the owner's
  `.superpowers/overnight-2026-11-20/job4241-*`.
- **Second failure**: CircleCI job 5768, node 0, main 6278639a, Windows, Python 3.15.2, -n 4,
  shuffled (seed 2637066936): KeyError 'httpcore2._api' in gw0, the same test. At report time only
  MainThread and the test's own serve_forever thread were alive; a thread that ended earlier would
  not show. In node 0's junit (all four workers, completion order, no worker ids) the nearest
  earlier test_compare_trace result is 2,720 results back, so compare_trace immediately before is
  not necessary. The line that raised, `<frozen importlib._bootstrap>:868`, is `_load_unlocked`'s
  `module = sys.modules.pop(spec.name)` in 3.15.2. Evidence: the ledger's
  `.ledger/triage/httpcore2/job5768/`.
- **Status**: Open (root cause not found; failed twice; a triage tool is in, 2026-11-20, branch
  `fix/httpcore2-import-keyerror-triage`; it records the known removals too since 2026-11-24,
  branch `triage/sys-modules-watcher`)
- **Priority**: Medium (a CI flake; the same class can break any import in the suite)
- **What the error means**: importlib's `_load_unlocked` runs the module, then does
  `module = sys.modules.pop(spec.name)`. A `KeyError` there means the module's entry left
  `sys.modules` while the module's own code was running. Its code does not remove itself, so
  something else did, and the importing thread's traceback cannot show what. That need not be a
  second thread: the failing import ran on the main thread, and code run on that same thread during
  it (a finalizer in a garbage collection, say) can remove the entry too.
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
- **What the reproductions establish** (2026-11-24): the mechanism only. A thread paused inside a
  module's execution while the main thread ends a `mock.patch.dict(sys.modules)`, or deletes the
  name, gives this error every time (`tests/test_import_failure_threads.py`). Neither shows what
  happened on CI.
- **Weak evidence against the suspects** (2026-11-24, macOS): the suspect order and every file the
  first sweep found, run with a watcher on the dictionary (3.15.1 serially, 3.15.2 with two
  workers), recorded 848 removals, none off the main thread and none during an import. Weak,
  because the watcher was a prototype that can itself corrupt `sys.modules`; because its filter
  also left out importlib's failure-path delete (`del sys.modules[spec.name]` when a module's code
  raises), which a nested failed import of the same name would need; and because the first sweep
  had missed files (below). Not covered: Windows, the part of the failing worker's order the
  truncated CI log lost, and direct deletes by code the sweep did not find.
- **Injection** (2026-11-24, macOS 3.15.1): a whole restore at a random moment of the import gave
  `_api` at none of about 290 sampled points of 436,611, only in the short end of `_api`'s own body.
  A restore at a uniformly random moment is therefore an unlikely way to the second failure's name.
- **Hypotheses, most likely first (speculation: no evidence singles one out)**:
  1. A targeted removal of the failed name, or a second load of it whose failure-path delete
     removed it, by code running on the importing thread or on one that had ended by report time.
  2. A whole-dictionary restore on another thread that had ended by report time. It must have
     landed just as the failing module's body ended, in both failures.
  3. A fault in the dictionary or the interpreter (the pop missing an entry that is there): Windows
     only so far, and the state section's lookups by hash and by iteration would show it.
- **A dictionary watcher must not be used in the suite** (`PyDict_AddWatcher` with a Python callback,
  through ctypes or otherwise). Read, in CPython's 3.15 branch `Objects/dictobject.c` (through a
  summary, not the whole file): `_PyDict_DelItem_KnownHash_LockHeld` finds the entry's index, calls
  the watcher, then deletes by that index; `clear_lock_held` reads the keys object before calling
  it. Measured, on macOS with 3.15.1: Python in the callback lets another thread, or a finalizer,
  insert and resize the dictionary, and `del` and `pop` then crash (segmentation fault; every
  try with the change made inside the callback, on a plain dictionary and, by another thread, on
  `sys.modules` during an ordinary import; and 3 of 3 with a callback that does nothing and two
  threads doing pop-then-set). The removal that fires it is importlib's own, at every import. `pop`'s
  code was not read; `clear` did not crash when tried.
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
  marks every thread with the test that started it and, when a test's setup, call or teardown fails
  inside the import machinery, adds `live threads at the import failure` to its report: each live
  thread, daemon or not, the test that started it, and its stack. Since 2026-11-24 it also adds
  `recorded sys.modules removals` (`tests/module_removals.py`: the ends of `patch.dict`, pytester's
  snapshot restores and `monkeypatch`'s changes, with the imports each may have overlapped, on the
  same or another thread; a missing mark proves nothing) and `sys.modules at the import failure`
  (`tests/import_failure_state.py`: whether the failed name is present, what else is under its
  package, whether the dictionary was rebound, the garbage collector's state, and how to read it).
  Not recorded: direct `del` and `pop`, third-party code's changes, importlib's failure-path
  delete. Tests:
  `tests/test_import_failure_threads.py` (a planted failure, a module that deletes its own
  `sys.modules` entry mid-import, gives the CI signature), `tests/test_module_removals.py`,
  `tests/test_import_failure_state.py`.
- **The class, swept** (2026-11-20, again 2026-11-24; `git grep` for `sys.modules` changes in `tests/` and `src/`):
  - Whole-dict restores (uncovered: each one, when it ends, drops every module imported since it
    began, on any thread, and a thread importing at that moment fails as above). `mock.patch.dict`
    restores the whole dict whether or not it is given values, so all 29 are in this class (swept
    again 2026-11-24 by AST, which the first sweep's 26 was not):
    `tests/replay/tools/test_compare_trace.py` (2, the suspect),
    `src/apps/bitmappy/tests/test_bitmappy_film_strip_operations.py` (2, with
    `del sys.modules['pytest']`), `src/apps/bitmappy/tests/test_bitmappy_film_strip.py` (3),
    `tests/timing/test_timing.py` (6), `tests/events/test_voice_backends.py` (4),
    `tests/test_generate_complexity_graphs.py` (3), `tests/replay/tools/test_identity.py` (2),
    `tests/test_clipboard.py` (2), `tests/testing/test_entry_points.py` (2),
    `tests/engine/test_game_engine.py` (1), `tests/test_workspace_config.py` (1),
    `tests/test_browser_storage.py` (1). `scripts/reproduce_import_keyerror.py` (2) and the
    recorder's own tests do it on purpose.
  - pytester's in-process runs (uncovered; the first sweep missed them): each ends with
    `SysModulesSnapshot.restore`, which clears and refills the whole dictionary too. Files that use
    them: `tests/test_circleci_test_split.py`, `tests/test_frame_fingerprints.py`,
    `tests/test_memory_guard.py`, `tests/replay/test_replay_plugin.py`, `tests/test_inner_runs.py`,
    `tests/test_mark_drawing_tests.py`, `tests/test_ci_config.py`,
    `tests/test_interrupted_writes.py`.
  - Single-entry changes (covered: `monkeypatch.setitem`/`delitem` put back only their key):
    `tests/audio/test_audio_engine.py`, `tests/templates/test_templates_extra.py`,
    `tests/replay/tools/test_golden_trace_harness.py`, `tests/replay/tools/test_scripted_sessions.py`,
    `tests/replay/test_replay_plugin.py`, `tests/engine/test_inner_game.py`,
    `tests/test_gen_ref_pages.py`.
  - Pops of a test's own stand-in package, on the main thread (covered: they remove only a name
    the test itself imported): `tests/engine/test_inner_game.py` (8),
    `tests/engine/test_inner_engine.py`, `tests/benchmarks/test_engine_context_benchmarks.py`,
    `tests/replay/tools/test_golden_trace_harness.py` (2),
    `tests/replay/tools/test_scripted_sessions.py`, `tests/test_demo_player.py` (2),
    `src/games/zombies-aint-my-neighbors/tests/test_zombies_aint_my_neighbors_scene_names.py`; and
    `src/glitchygames/testing/entry_points.py` pops a package's `__main__`.
  - A reload (re-runs a module in place; importlib pops its entry and sets it again at the end,
    outside `_load_unlocked`): `src/apps/bitmappy/tests/test_bitmappy_ai_manager.py`,
    `tests/test_gen_ref_pages.py`, `tests/interfaces/test_interfaces_meta.py`.
- **Fix to make (once the evidence implicates a restore)**: replace the whole-dict restores with
  one helper that removes, at the test's end, only the modules the test itself added under the
  names it owns, and a guard test that refuses `patch.dict(sys.modules ...)` in the suite.
- **Reporter**: The coordinating session (glitchygames-bc)
- **Date Reported**: 2026-11-20
- **Files**: `tests/import_failure_threads.py`, `tests/test_import_failure_threads.py`,
  `tests/module_removals.py`, `tests/test_module_removals.py`,
  `tests/import_failure_state.py`, `tests/test_import_failure_state.py`,
  `conftest.py`, `scripts/reproduce_import_keyerror.py`
