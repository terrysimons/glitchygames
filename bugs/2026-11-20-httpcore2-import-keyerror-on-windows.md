# Imports Under httpcore2 Failed With KeyError on CircleCI's Windows Jobs

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
- **Third failure**: CircleCI job 6031, node 0, PR #320's 921262618, Windows, Python 3.15.2, gw2,
  shuffled (seed 2467454726): KeyError 'h11._util' in
  `tests/test_ai_behaviour.py::test_a_refusal_or_endless_tool_calls_fail_the_question`, the first
  report with the recorder's sections (below). Evidence: the ledger's
  `.ledger/triage/httpcore2/job6031/`.
- **Fourth failure** (found afterwards by searching past jobs; it ran before job 6031): CircleCI job
  5925, node 1, main 11a1f298b, Windows, Python 3.15.2, gw2, shuffled (seed 2145114001): KeyError
  'httpcore2._models' in `tests/ai/test_local_service.py`,
  `test_a_refusal_carries_its_status_for_the_callers_retries`.
  Its report has the live threads (MainThread and the test's own serve_forever thread, in select)
  and no recorder sections. Evidence: the ledger's `.ledger/triage/httpcore2/job-search/`.
- **What job 6031 shows**: the 28 removals recorded in that worker were all on the main thread and
  none was during the failing test, so a `patch.dict` end, a pytester restore or a `monkeypatch`
  change is contradicted for this occurrence, as far as those wrapped calls go (an unwrapped one
  is not seen). `h11._abnf`, loaded earlier in the same import, was still there, its package's own
  object: a whole-dictionary restore to a snapshot from before that import would have taken it.
  Only the failed name was absent under h11 (h11 itself and the modules running were absent too, as
  unwinding leaves them). `sys.modules` was the dictionary seen at startup. The other thread,
  serve_forever, was in select when the report was made, which is after the failure, not at it. The
  collector ran 12 generation-0 and 1 generation-1 collections since the test began (21 and 3,532
  objects): a finalizer had chances to run; whether one ran during the import is not known. It does
  not show whether the entry was there when the pop ran. It says nothing of the other three.
- **Status**: Open (root cause not found; four sightings, all on Windows and all on the first import
  of httpcore2 in a worker; a triage tool is in, 2026-11-20, branch
  `fix/httpcore2-import-keyerror-triage`; it records the known removals too since 2026-11-24,
  branch `triage/sys-modules-watcher`, and the points of each import, branch
  `triage/import-probe`; none of it is a fix)
- **Priority**: Medium (a CI flake; the same class can break any import in the suite)
- **What the error means**: importlib's `_load_unlocked` runs the module, then does
  `module = sys.modules.pop(spec.name)`. A `KeyError` there means that, for the pop, the module's
  entry was not in `sys.modules`: it left after the store (most likely while the module's own code
  ran), or it was there and the pop missed it. The code of the modules that failed does not remove
  itself, and the importing thread's traceback cannot show what did. That need not be a
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
- **Injection** (2026-11-24, macOS 3.15.1): a whole restore at one traced point of the import (a
  line or audit event, sampled evenly, about 290 of 436,611). `_synchronization` (its body imports
  anyio) came up at 18 of the sampled points, `_api` at none; a separate targeted sweep found `_api`
  only in the short end of its own body. So a restore at a uniformly random traced point readily
  gives the first failure's name and is an unlikely way to the second's. Limits: traced points are
  not moments of time, and the snapshot was taken just before the import with httpx2, anyio and ssl
  already loaded; what CI's worker had loaded, and any snapshot's age, may differ.
- **Surviving hypotheses (speculation: no evidence singles one out, and the order is not a ranking;
  the four failures are taken to share a cause, which is itself not shown)**:
  - A targeted removal of the failed name, or a second load of it whose failure-path delete removed
    it, by code running on the importing thread or on one that had ended by report time.
  - A finalizer run on the importing thread during the import (by a collection or by a reference
    count reaching 0) that removes the name, or that ends a restore whose snapshot still held the
    earlier modules.
  - A whole-dictionary restore on another thread that had ended by report time. Job 6031 contradicts
    it for that occurrence, unless its call is not one of the wrapped ones and its snapshot was
    taken after `h11._abnf` loaded. For the other three nothing recorded speaks to it: for `_api` it
    must have landed as that module's body ended; for `_synchronization` it had far more room.
  - A fault in the dictionary or the interpreter (the pop missing an entry that is there): Windows
    only so far. Job 6031's two lookups agreed that the name was absent, but after the failure: they
    do not say what the pop met.
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
- **Test gap**: nothing records the other threads when an import fails, so the first failure
  gave only the importing thread's stack; and nothing recorded the steps of an import, so job 6031's
  report could not say whether the entry was there when the pop ran.
- **The triage tool**: `tests/import_failure_threads.py` (a plugin in the root `conftest.py`)
  marks every thread with the test that started it and, when a test's setup, call or teardown fails
  inside the import machinery, adds `live threads at the import failure` to its report: each live
  thread, daemon or not, the test that started it, and its stack. Since 2026-11-24 it also adds
  `recorded sys.modules removals` (`tests/module_removals.py`: the ends of `patch.dict`, pytester's
  snapshot restores and `monkeypatch`'s changes, with the imports each may have overlapped, on the
  same or another thread; a missing mark proves nothing) and `sys.modules at the import failure`
  (`tests/import_failure_state.py`: whether the failed name is present, what else is under its
  package, whether the dictionary was rebound, the garbage collector's state, and how to read it).
  Not recorded by it: direct `del` and `pop`, third-party code's changes, importlib's failure-path
  delete. Tests:
  `tests/test_import_failure_threads.py` (a planted failure, a module that deletes its own
  `sys.modules` entry mid-import, gives the CI signature), `tests/test_module_removals.py`,
  `tests/test_import_failure_state.py`.
- **The probe** (2026-11-24, `tests/import_load_probe.py`, part of the recorder; evidence, not a fix):
  `sys.monitoring` events on `_load_unlocked`'s code alone, under a tool id that was free (coverage
  keeps id 1; here 4, else 3), read whether the module's entry is present after the store, at the
  pop's line, as pop is called and as it returns or raises, with every garbage collection beside
  them (and the importing module's entry before and after it). At a pop that raises it also reads
  the entry by hash and by iteration, which modules loaded since the outermost import began are
  missing, and the other threads' stacks, before anything unwinds. The places are found in the code
  object's instructions; an unrecognised shape, or no free id, is reported as not recorded. The
  report also lists every ident running Python code and the interpreter's build. It costs about 7
  microseconds an import and 1.2 a collection (measured, macOS), and no more on collecting the suite
  than its noise (about 0.1 s of 5), so it runs in every test run.
- **The probe's caveat**: an instrumented `_load_unlocked` does not run as the plain one does: its
  calls leave the interpreter's specialised path, and the callbacks add points where threads switch
  and garbage is collected. If the cause is an interpreter fault, or needs exact timing, the probe
  may hide it. Failures that stop after it landed are NOT evidence of a fix: take it out (or wait
  for the failure on a run without it) before drawing anything from their absence.
- **How to read the next failure** (the section `recorded points of the failed import`; each is a
  hint, with what it leaves open):
  - "left between the store and the pop's line": removed while `exec_module` ran, by the module, by
    what it called, by a finalizer or by another thread; the pop did not miss a present entry. A
    collection marked `THE ENTRY WENT DURING THIS COLLECTION` points at a finalizer (another thread
    can run inside one). With none marked, a finalizer by reference count stays open. The other
    threads' stacks and the thread counts say who was there, not who did it. `last seen present` and
    `first seen absent from inside` narrow it to between two nested imports; the removals section's
    event numbers say whether a recorded removal fell there.
  - "between the start of the pop's line and the call": the same suspects, in a very short gap.
  - "present when pop was called, and pop raised": perhaps an interpreter or dictionary fault. The
    callback calls nothing after its reading, so no Python code should run on that thread between
    the reading and the pop (read from the bytecode, not proven); C code stays open.
  - "already absent at the first line after the store": a lost store, or a removal in that gap.
  - "not recorded" or a count of faults that is not 0: nothing follows from the missing readings.
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
  `tests/import_load_probe.py`, `tests/test_import_load_probe.py`,
  `conftest.py`, `scripts/reproduce_import_keyerror.py`
