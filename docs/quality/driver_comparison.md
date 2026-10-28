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
every frame each test presents (`src/glitchygames/testing/frame_fingerprints.py`). When both have
finished, the frames are compared (`src/glitchygames/testing/frame_comparison.py`; its command line
is `scripts/compare_driver_frames.py`). Any difference, or a
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

The session compares every driver configuration available on this machine with every other, an
N-way matrix (`scripts/driver_configurations.py` lists them and finds which run here):

| Configuration | What runs | Needs |
| --- | --- | --- |
| `dummy` | SDL's windowless driver, run twice (a test whose frames differ between those runs is nondeterministic: it should be marked) | nothing; always the baseline |
| `cocoa` (`windows`, `wayland`, `x11`) | the platform's own driver | its platform (Linux: `WAYLAND_DISPLAY` or `DISPLAY`) |
| `x11-macos` | x11 on this Mac, drawing on XQuartz, through SDL built with x11 | macOS, XQuartz, a C compiler and make |
| `x11-linux` | x11 in the Linux container of `nox -s test-linux-x11`, forwarded to XQuartz over TCP | macOS, XQuartz (TCP enabled), Docker |

The runs go one after another with four workers each (the container's too), so the machine stays
usable. `nox -s compare-drivers -- --drivers dummy,cocoa,x11-macos` chooses configurations
(`dummy` is always added: it is the baseline; one that cannot run here is refused with the
reason), and other arguments select tests (`-- tests/scenes`). The tests that differ anywhere are
re-run on every configuration saving their differing frames, and every differing pair gets both
PNG files and a difference image under
`test-results/driver-comparison/nox/differences/<first>-vs-<second>/`.

The report, `test-results/driver-comparison/nox/matrix.md` (and `matrix.json`), holds each
run's time, a summary row per pair (tests compared, how many differ, by kind: pixels, size,
present count, display, outcome), the patterns of agreement ("cocoa differs from all others",
"x11-macos and x11-linux differ from dummy and cocoa"), a table per test file and, folded per
file, a row per test with a cell per pair: `agree`, `n/a` (not recorded by both) or the first
differing frame's index and kind with the differing pixel count linked to the difference image.
The session prints the pair summary and the patterns at the end. It reports; it never fails on
a difference.

It fails when a run recorded no test, naming the run: arguments that make pytest run nothing and
exit 0 (`-- --help`, `-- --collect-only`) reach every run, and a report of empty runs would say
every configuration agrees. It fails too when a pytest run cannot run at all. A comparison that
fails or is interrupted never replaces the last complete one: while a comparison runs, the last
complete one waits in `test-results/driver-comparison/nox-previous/`, and it goes back to
`test-results/driver-comparison/nox/` when the comparison fails; the failed comparison's runs
are kept in `test-results/driver-comparison/nox-failed/`.

### x11 on macOS: SDL built with x11

pygame-ce's macOS wheel bundles an SDL without x11. SDL's dynamic API loads another SDL at run
time instead: with `SDL_DYNAMIC_API=/path/libSDL2-2.0.0.dylib` the wheel's SDL fills its jump
table from that library, and every SDL call (pygame's, SDL_image's, SDL_mixer's, SDL_ttf's) runs
it. `nox -s build-sdl-x11` (run by `compare-drivers` when needed) builds the very version the
wheel reports (`pygame.get_sdl_version()`) from its GitHub release tarball, its SHA-256 pinned
per version in `scripts/build_sdl_x11.py`, with SDL's autotools build (SDL 2's CMake build never
enables x11 on Apple platforms) and x11 against XQuartz's `/opt/X11`. Cocoa, Metal, Vulkan, MFi,
OpenGL and OpenGL ES are left out: the wheel's SDL is loaded too, and two copies of SDL's
Objective-C classes in one process make the runtime warn and risk crashes; OpenGL crashed workers
on XQuartz (see the caveats below). The build lives in
`~/Library/Caches/glitchygames/sdl-x11/<version>/` (never a system path) and is reused while its
`build.json` matches; the session then checks that a child pygame opens and fills a window on
XQuartz through it. The runs use `SDL_VIDEODRIVER=x11`, dummy audio and XQuartz's `DISPLAY`.

### x11 caveats

Both x11 configurations draw on XQuartz, a real X server with a window manager, so some tests
see what a real desktop does and the dummy driver never shows (measured 2026-10-23, SDL 2.32.10,
XQuartz 2.8):

- **Slow windows**: creating a window on XQuartz takes about 0.75 s, so `x11-macos` ran the
  suite in 872 s (dummy 46 s, cocoa 110 s) and `x11-linux`, over TCP, in 552 s.
- **Smallest window**: XQuartz's window manager widens a window narrower than 72 pixels (a
  64x48 window becomes 72x48), so pygame warns "Requested window was forcibly resized by the
  OS" (an error in this suite). Tests open windows at least 96 pixels wide.
- **Late resizes**: resizing an existing window is asynchronous on x11. SDL waits 100 ms for
  the window manager, then keeps the old size (pygame warns as above) and the new size arrives
  on a later pump. On a loaded machine every resize came late (over TCP from the container, 8
  processes resizing at once: 0.8-3.4 s), so a window changed from 800x600 to 800x480 reported
  the old size. The engine and the tests set the display mode through
  `glitchygames.display_mode.set_display_mode`, which pumps until the size changes and warns
  only if the window ends at another size than the requested one.
- **Real window events**: the X server sends focus, exposure and move events for the real
  window; a recording made on x11 holds them, and tests that assume only the dummy driver's
  window events see them. Its raw messages (pygame's `SYSWMEVENT`) stay blocked unless a game
  opts in (`NATIVE_WINDOW_MESSAGES`); before 2026-10-23 the engine's allow-all enabled them,
  filling queues, recordings and instant-replay journals.
- **No OpenGL** (`x11-macos`): with OpenGL, SDL on macOS marks every window OpenGL, loading
  XQuartz's libGL and Apple's Xplugin into the process, and draws window surfaces through an
  OpenGL texture. Under load that ended pytest workers without a traceback (`GLXBadContext` in
  `X_GLXMakeCurrent` through Xlib's default error handler; a crash in SkyLight on Xplugin's event
  thread). The build leaves OpenGL out (`--disable-video-opengl`), so window surfaces are drawn
  in software, as in the container, which has no libGL.
- **Root in the container** (`x11-linux`): the container runs as root, who can read a file
  without read permission, so `tests/templates/test_template_errors.py`'s permission test is
  skipped there (an outcome difference, not a failure). It runs with an init process (`docker
  run --init`) that reaps orphaned processes, as on a real system.
- **Pixels**: no passing test drew different pixels on x11 than on dummy or cocoa; every x11
  difference was a window size or a test's outcome (the two x11 configurations' pixels differed
  only in the final frames of tests that had already failed on the widened window).

## Linux in Docker: `nox -s test-linux-x11`

The suite runs on Linux in a container (`scripts/linux_x11/Dockerfile`) with real X11 windows on
the Mac's XQuartz (TCP enabled: `defaults write org.xquartz.X11 nolisten_tcp -bool false`, then
restart XQuartz) and its sound on the Mac's PulseAudio (`brew install pulseaudio`; the project's
`.envrc` installs it). The session starts XQuartz and, when it is not running, the PulseAudio
server with TCP on port 4713, accepting connections without a cookie only from loopback and
Docker's private ranges (`127.0.0.1;192.168.0.0/16;172.16.0.0/12`); both are left running
afterwards (`pulseaudio --kill` stops PulseAudio). The container plays through it with
`SDL_AUDIODRIVER=pulseaudio` and `PULSE_SERVER=tcp:host.docker.internal:4713`. Without
PulseAudio, or when it will not start, one line says so and the container uses dummy audio.
`compare-drivers`' `x11-linux` runs use dummy audio (frames do not depend on sound); `--sound`
plays theirs through PulseAudio too.

## Linux as CI runs it: `nox -s test-linux-ci`

`nox -s test-linux-x11` runs the suite on Linux for its drivers; `nox -s test-linux-ci` runs it
the way CircleCI's Linux job does, to reproduce that job's failures here. It reads the job
(`build-and-test-linux`) from `.circleci/config.yml`: its image (`cimg/python` at
`PYTHON_LATEST_VERSION`), its resource class's memory and CPUs (`small`: 2 GB, no swap, and one
CPU, given to `docker run` as `--memory`, `--memory-swap` and `--cpus`) and its environment
(`PYTEST_WORKERS=0`: one serial process; `GLITCHYGAMES_TEST_RSS_LIMIT_MB=1750`:
`tests/memory_guard.py` stops the run past it, naming the test), with `CI=true` and
`CIRCLECI=true`. The container gets what git would commit from this checkout: tracked files and
untracked ones that are not ignored, uncommitted changes included, never an ignored file (the
host's caches, Hypothesis's database) and no submodule's contents (CircleCI's checkout has none).
Its `.git` is cloned from the repository's git directory, mounted read-only at its own path, so
the session runs from a worktree too; HEAD is this checkout's, on its branch, and the remote
branches are this checkout's, as fresh as its last fetch. It installs fontconfig, uv and Python at
the job's versions and runs `uvx nox -s test` as the job does. Its `test-results/` (junit.xml)
come back to `test-results/linux-ci/`. The memory guard's summary line names the peak it saw (the
container's memory less its page cache, what the kernel's 2 GB kill counts), and the last line
the container's raw peak (the page cache included, so near 2 GB even on a healthy run). It takes
as long as the job (a serial run) or longer: the image is amd64, as CircleCI's machines are (the
same wheels: taplo has no arm64 Linux wheel, and building it ran out of the 2 GB), emulated on
Apple silicon. Made on macOS; on a Linux host the results are made writable for any user.

