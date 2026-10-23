# Driver Comparison

The test suite draws in software on SDL's `dummy` video driver, which has no window. The
platform's own driver (macOS `cocoa`, Windows `windows`, Linux `wayland` or `x11`) draws through
the same code, and the engine presents opaque frames, so every test should show the same pixels
on both. When they differ, the engine depends on the driver: on macOS a display with per-pixel
alpha once showed black frames (BUGS.md #142) and a black box around the player during
Clockwork Keep's elevator ride (BUGS.md #189), neither visible on `dummy`.

## Every local run compares

Outside CI, `uv run pytest` (and `nox -s test`) runs the suite twice at once:

1. on `dummy`, in the pytest process and its xdist workers, with coverage and the 99% gate as
   always;
2. on the native driver, as a child pytest run with the same arguments. The usual workers are
   split between the two runs (the native run gets two thirds: it is slower per test), so the
   machine is no busier than for one run.

Both runs record a fingerprint (size and SHA-256 of the RGB bytes, as the window shows them) of
every frame each test presents (`glitchygames/testing/frame_fingerprints.py`). When both have
finished, the frames are compared (`scripts/compare_driver_frames.py`). Any difference, or a
failure in the native run, fails the run; the differing tests are re-run on both drivers to save
the differing frames as PNG files with a difference image (the baseline dimmed to grey, differing
pixels magenta) under `test-results/driver-comparison/pytest/`. The terminal summary names every
file and the native run's log.

The comparison is off, and the summary says why, in CI (`CI=true`), with `--dummy-only` (fast
iteration), when `SDL_VIDEODRIVER` or `SDL_AUDIODRIVER` is set (that driver runs alone), and on a
Linux machine without a display.

## Tests whose frames vary

A test whose frames are not expected to match between runs or drivers is marked
`@pytest.mark.frames_vary(reason=...)`: it is listed with its reason and not compared. Today
these are a session recorded through the real frame loop (each frame moves by its measured frame
time), watched replays of a live session (the overlay shows the live window's mouse focus, which
`dummy` always reports and a background window does not have) and a test that switches the
display back to the run's driver part way through.

## On demand: `nox -s compare-drivers`

The session runs the suite twice on `dummy` (a test whose frames differ between those runs is
nondeterministic: it should be marked) and once on the native driver, one after another with
four workers each, and writes the same report and images under
`test-results/driver-comparison/nox/` without failing. `nox -s compare-drivers -- tests/scenes`
selects tests; `-- --driver x11` on macOS runs both in the Linux container of
`nox -s test-linux-x11`.
