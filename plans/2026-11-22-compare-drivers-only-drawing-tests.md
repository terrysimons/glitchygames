# Compare Drivers Only on Tests That Draw: Plan

> **Status: approved (2026-11-22, #268); in progress on `feature/compare-drivers-only-drawing-tests`.**
> Source: the owner's request of 2026-11-22, relayed by the coordinator: the pre-push gate takes
> 50 to 75 minutes, and most of it is `compare-drivers` running the whole suite three times.

**Goal:** `nox -s compare-drivers` (the pre-push hook's driver comparison) runs only the tests
that draw: the ones whose recorded frames can differ between drivers. They are selected by a
pytest marker, `draws_frames`. The marker cannot go stale: in every pytest run, the frame
fingerprints plugin fails a test that draws without the marker, and a marked test that never
draws. The gate's comparison drops from about an hour to an estimated 6 to 11 minutes, and a
non-drawing test can no longer fail it by passing on one driver and failing on the other.

## Evidence

Measured from the Arcade 5 push's comparison
(`glitchygames-arcade-5-playback-core/test-results/driver-comparison/nox/`: `dummy-1/*.jsonl`,
`matrix.json`, `run-seconds.json`, each run's `junit.xml`), with the canvas fingerprints worked
out on this machine:

| Measure | Value |
| --- | --- |
| Tests per run | 30,900 (dummy twice, cocoa once) |
| Run times (wall, at that push's load) | dummy-1 2234 s, dummy-2 838 s, cocoa 514 s: about 60 minutes |
| Tests that presented at least one frame | 627 |
| Tests that presented nothing and whose final screen is not the 800×600 canvas | 1,900 |
| ...of which the final screen is the canvas at another window size | 1,677 (800×480: 1,484; 320×240: 80; 1280×720: 76; 96×64: 37) |
| **Tests that draw** (a present, or a final screen other than the canvas at its own size) | **850** (627 + 223), the same 850 in all three runs |
| Their share of each run's test time (junit, summed across workers) | dummy-1 4%, dummy-2 7%, cocoa 16% |
| Test functions with a drawing case / files holding them | 707 / 67 |
| Parametrized functions where only some cases draw | 5 |
| `frames_vary` tests / of them drawing | 21 / 20 |

What every surviving comparison found (32 `matrix.json` files across the worktrees: the last
complete comparison of each):

- **Driver differences: 4, all the same kind.** `tests/replay/tools/test_command_crash_boundary.py::test_a_signal_stops_and_reaps_the_commands_child_and_exits_with_its_code[2]`
  passed on dummy and failed on cocoa: an `outcome` difference in a test that draws nothing (a
  child-reaping flake under load, the class of #263). No pixel, size or present-count difference
  between drivers survives in any of them.
- **Differences between the two dummy runs: 11.** 8 are `outcome` flakes in tests that draw
  nothing (`test_ansible_ai_service.py`, `test_browser_storage.py`, `test_memory_guard.py`,
  `test_reproduce_orphaned_test_processes.py`, one Bitmappy navigation test). 3 are `pixels`
  differences in tests that draw (Zombies' golden route; the audio engine's power-on idle, twice).

So within that sample, everything the comparison failed a push for came from tests that draw
nothing, and everything real that the second dummy run found came from tests that draw.

## What the comparison compares (why "draws" means what it does)

`glitchygames.testing.frame_comparison.compare_frames` compares, per test: every present, in
order; then the present count; then the final screen, when both runs drew it on their own driver
(`RecordedFrames.final_on_run_driver`); and when every frame matches, the test's outcome. Every
test starts on the canvas pattern (`tests/display_canvas.py`, `show_canvas`), and a test that sets
its own display mode and draws nothing shows the canvas at that size
(`show_canvas_on_new_display`). So a test that presents nothing and leaves the canvas at its own
size has only an untouched canvas to compare. Its frames cannot show a driver dependence the
drawing tests miss: the canvas is drawn by the same code for every test. Only its outcome is left
to compare, and test-random already runs every test.

**Decision: a test draws when, from the start of its setup to the end of its body, it presented
at least one frame, or its final screen differs from the canvas at the final screen's own size.**
Presents alone (627 tests) would drop 223 tests whose final screens are compared today: that
loses coverage for about 3% of one run's time. The final-screen rule keeps the comparison exactly
as strong for frames.

## Decisions

1. **The marker is `draws_frames`.** It sits beside `frames_vary` (same plugin, same naming
   shape). It is registered by `glitchygames.testing.frame_fingerprints` in every run, as
   `frames_vary` is.
2. **compare-drivers runs only the marked tests, through the plugin's `--draws-frames-only`.**
   Every run gets it (the dummy runs, every native configuration, the PNG re-run of differing
   tests). The option deselects every unmarked test after collection, so a user's own `-m` still
   narrows the run with no combining. (An option rather than `-m draws_frames`: the noxfile runs
   outside the project's environment and cannot import a shared helper that would merge a
   user's `-m`; a second copy would drift.) The "a run recorded no test" refusal (BUGS.md #192)
   still applies.
3. **The plugin enforces the marker in every pytest run**, including CI on all three operating
   systems, not only when it records:
   - a test that draws without `draws_frames` fails, with the reason (presents counted, or "final
     screen differs from the canvas") and the line to add;
   - a test marked `draws_frames` that draws nothing fails, naming the marker to remove;
   - the verdict is per node id. A parametrized function where only some cases draw (5 today)
     marks those cases with `pytest.param(..., marks=pytest.mark.draws_frames)`;
   - `frames_vary` keeps its meaning (recorded, never compared). A `frames_vary` test that draws
     also carries `draws_frames`, so one rule covers both: the marker says what the test does, and
     `frames_vary` says how to read it;
   - a run is judged unless a test started it: a pytest that configures while
     `PYTEST_CURRENT_TEST` is set (pytester, in process or as a child process, which inherits the
     variable; a tool's run) judges nothing. The run's xdist workers and the local native run
     start outside any test, so they are judged. (`GLITCHYGAMES_FRAME_FINGERPRINTS_OWNER` is set
     only when recording, so it cannot serve here.) An xdist worker is told by its configuration
     (`workerinput`), not its environment, which an in-process nested run inherits.
4. **Explicit marks everywhere, no folder marks** (the owner, 2026-11-22). Folder marking
   conflicts with the "marked but never draws" rule: a collection hook marking every test under
   `src/games`, `src/apps` and `src/demos` marks 9,317 tests, of which 158 draw, so it needs that
   rule dropped or an exemption for the whole layer, and it selects 10,009 tests instead of 850
   (16% to 30% of each run's time instead of 4% to 16%). The member tests that draw (158, in 23
   files) are marked one by one, seeded from the data like the engine's.
5. **The canvas the plugin compares with comes from the suite, through a pytest hook.** The plugin
   is engine code (`glitchygames.testing`) and may not import `tests/` (enforced:
   `tests/test_suite_collection.py`). A new hook specification,
   `pytest_frame_fingerprints_blank_screen(size) -> bytes | None`, returns the shown RGB bytes a
   test leaves when it draws nothing at that size. `tests/harness.py` implements it from
   `tests/display_canvas.py` (`canvas_shown_bytes`: `background_pattern_surface(pattern=
   CANVAS_PATTERN, size=...)` read through `opacity.shown_rgb_bytes`); the plugin caches it per
   size. Not the root `conftest.py`: importing `tests.display_canvas` at its top would import
   pygame before the harness sets the SDL defaults. A project without an implementation gets the
   presents-only rule.
6. **The plain local `pytest` comparison** (`tests/driver_comparison.py`'s native child run) also
   passes `--draws-frames-only`. It is the same comparison; this speeds every local full run as well.
   Its frames compare exactly as before, since the tests left out have nothing to compare.
7. **Seeding.** The enforcement writes its verdicts, per session, to
   `test-results/frame-markers.txt` (unmarked drawing tests and marked non-drawing tests, one node
   id per line with its reason). Seeding is: run the suite once with the plugin's checks
   reporting but not failing (an option used only for this step,
   `--frame-markers-report-only`), then apply the list with a small codemod,
   `scripts/mark_drawing_tests.py`. The codemod adds `@pytest.mark.draws_frames` above each
   function, or `pytest.param` marks for the mixed parametrized cases, and refuses a node id it
   cannot place. It is kept: a new test file that draws is marked the same way.
8. **`--skip-when-frames-cannot-change` is unchanged.** It decides, before any run, that a push
   touching only docs, plans, ledger rows, CI config or root Markdown is not compared at all. The
   marker narrows what runs when the comparison does run; the two are independent.

## Sub-plan for the owner: the second dummy run

**Why it exists:** since #96 (`fab884c1`), compare-drivers runs dummy twice so a test whose frames
differ between two runs on the same driver is reported as nondeterministic, and is never counted
as a driver difference (`compare_repeats`; the report's "Nondeterministic on dummy" list).

**The alternative:** run dummy once, then re-run only the tests that differ from the native run,
on dummy, with the existing PNG re-run step (`image_request_for`). A test whose dummy re-run
differs from its first dummy run is nondeterministic, otherwise it is a driver difference.

| | Keep the second dummy run | Re-run only the differing tests |
| --- | --- | --- |
| Time after this plan (estimate) | about 2.5 min (850 tests, collection included) | seconds (the differing tests) |
| Nondeterminism found | in every drawing test, each push: 3 real cases in the surviving sample | only in tests that also differ between drivers; a test varying rarely is seen only when its variation coincides with the native run |
| Report | "Nondeterministic on dummy" lists every varying drawing test | lists only the varying tests that differed from native |
| Risk | none new | a rarely varying drawing test is missed until it trips the native comparison, and then it costs a re-run to diagnose |

**Recommendation: keep the second dummy run.** Once the runs hold 850 tests, it costs about 2.5
minutes, and it is the only thing that found the real nondeterminism in drawing tests (3 of 3 in
the sample). The time it saved before this plan (14 minutes at the Arcade 5 push's load) is gone
with the marker.

## Estimated gate time

Each run's new wall time ≈ fixed cost + its drawing share × (its wall time − fixed cost). The
fixed cost is pytest collecting all 30,900 tests before deselecting and the workers starting;
estimated at 60 to 120 s per run under load, to be measured in sub-plan 1.

| Run | Today | After (fixed cost 90 s) |
| --- | --- | --- |
| dummy-1 | 2234 s | about 180 s |
| dummy-2 | 838 s | about 140 s |
| cocoa | 514 s | about 160 s |
| **compare-drivers** | **about 60 min** | **about 8 min (6 to 11)** |

`test-random` (a fourth full run, on dummy, shuffled) is unchanged. It becomes the gate's longest
hook, and is out of scope here.

## Files and interfaces

- `src/glitchygames/testing/frame_fingerprints.py`: registers `draws_frames`; a light present
  counter installed in every run (the recorder's fingerprinting stays only when recording); the
  final-screen check against the blank screen; per-test verdicts that fail the test in
  `pytest_runtest_makereport`; the session report file; `--frame-markers-report-only`; the hook
  specification (`pytest_addhooks`). The docstring gains a "the draws_frames marker" section,
  which is the contract.
- `tests/harness.py`: implements `pytest_frame_fingerprints_blank_screen` (from
  `tests/display_canvas.py`'s `canvas_shown_bytes`).
- `noxfile.py`: every compare-drivers run (`_run_fingerprinted_tests`) passes
  `--draws-frames-only`; the docstring says so.
- `tests/driver_comparison.py`: the native child run passes `--draws-frames-only`; the module
  docstring says so.
- `scripts/mark_drawing_tests.py`: the codemod (decision 7).
- The 67 test files holding drawing tests: the markers.
- Docs: `docs/quality/driver_comparison.md` ("Every local run compares": the native run runs the
  drawing tests; "On demand": every run runs the marked tests only; a new "The draws_frames marker"
  section with the rule and the failure messages). In `CLAUDE.md`, the Testing Guidelines'
  driver comparison bullet gets the marker in the same number of lines (the file is at its
  360-line cap): "A test that draws carries `@pytest.mark.draws_frames` (the plugin fails it
  otherwise); a test whose frames legitimately vary also carries `frames_vary(reason=...)`". (The
  Common Commands' `compare-drivers` line stays: the words would push it past 100 characters, and
  the Testing Guidelines bullet already says it.)

## Sub-plan order

1. **The marker and its enforcement, report-only.** Plugin changes, the hook, the root
   implementation, the report file. Measure the per-test cost of the check (expected well under 1
   ms at 800×600: one `tobytes` and a compare; budget it against the 30,900-test run) and the
   fixed cost of a deselecting run.
2. **Seed the marks.** Run the suite with `--frame-markers-report-only` on dummy and on cocoa
   (their sets must agree, as they did in the data; a disagreement is a driver dependence to
   triage first), apply the codemod, review the diff by file.
3. **Turn enforcement on** (the default: failing). The full suite passes on dummy, on cocoa
   locally, and in CI on all three operating systems.
4. **Select the marker** in compare-drivers and the local native run, with the docs. Measure the
   new gate on a real push and record it in `docs/quality/driver_comparison.md`.

## Tests, named as behaviours

Plugin (pytester, in `tests/test_frame_fingerprints.py`):

- a test that presents a frame without `draws_frames` fails, naming the marker;
- a test that presents nothing but leaves a picture other than the blank screen fails the same
  way;
- a test that leaves the blank screen at a new display size, unmarked, passes;
- a marked test that neither presents nor changes the screen fails, naming the marker to remove;
- a marked test that draws passes; a `frames_vary` test that draws and carries both passes;
- a parametrized test whose drawing cases carry the mark through `pytest.param` passes, and the
  same test marked on the function fails for its non-drawing case;
- presents made by a fixture's setup count for the test, and presents in teardown do not;
- a pytest started inside a test is not judged;
- without a `pytest_frame_fingerprints_blank_screen` implementation, only presents count;
- `--frame-markers-report-only` writes every verdict to the report and fails no test;
- the check runs without `--frame-fingerprints` (no recording asked).

Comparison (the compare-drivers session's tests in `tests/test_ci_config.py`, and
`tests/test_driver_comparison.py`):

- every compare-drivers run, the PNG re-run included, carries `--draws-frames-only`, with a
  user's selection kept; the plugin's `--draws-frames-only` runs the marked tests alone, and a
  caller's `-m` still narrows it;
- a selection that records no test still fails the session, naming the run;
- the local native child run carries `--draws-frames-only`;
- `--skip-when-frames-cannot-change` still skips a docs-only push before any run.

Codemod (`tests/test_mark_drawing_tests.py`):

- it adds the decorator above a function and a method;
- it marks only the listed cases of a parametrized function with `pytest.param`;
- it leaves an already marked test alone, and refuses a node id it cannot find.

## Risks

- **An outcome-only driver dependence in a non-drawing test** (a test that behaves differently on
  cocoa without drawing: a display-mode or window-event query) is no longer caught by
  compare-drivers. In the surviving sample, every outcome difference was a flake. The local full
  `pytest` still runs every test on dummy, and the native run's failures still fail it for the
  drawing tests.
- **A test that draws only on the native driver** would be unmarked on dummy. Enforcement runs in
  the native child run too (it is a pytest the plugin owns), so the local full run fails it.
- **Collection cost** stays (deselection happens after collection), which is why the estimate
  has a fixed cost per run.

## Decided by the owner (2026-11-22, relayed by the coordinator)

1. compare-drivers runs only tests that draw, selected by a marker (named here: `draws_frames`).
2. The frame-fingerprints plugin keeps the marker from going stale in every normal run, both ways;
   `frames_vary` keeps working.
3. Explicit `draws_frames` marks everywhere, not folder marks for member tests (decided
   2026-11-22 after the data in decision 4; the first request was member tests by folder).
4. Seed the marking from the recorder's data, and settle what "draws" means from what the
   comparison compares (decided above: a present, or a final screen other than the canvas at its
   size).
