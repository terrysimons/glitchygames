# Requirements

A computer meets GlitchyGames' minimum for a game when that game's typical frame takes less than
16.7 ms of work, the budget for the engine's default 60 FPS. Pick a target and a measure below, and
a platform from the tabs: every verdict and color follows your choice. Three machines have been
measured so far.

!!! note "Provisional"
    These numbers were measured from November 5 to 9, 2026. They will change once the in-flight
    work lands: the Arcade's engine-context sub-plans, Lucid Circuit Stage 4b and the Raspberry Pi
    speedups. Then every machine gets re-measured and this page updated
    (`plans/future-work.md`, Performance and pacing).

## What a machine needs

| Requirement | Minimum | Recommended |
| --- | --- | --- |
| Each game's frame work, in the replay benchmark | Under the frame budget: 16.7 ms at 60 FPS, 33.3 ms at 30 | Under 60% of it (10 ms at 60 FPS), leaving the rest to draw the frame on screen |
| Operating system | Ubuntu 26.04 LTS or later, or macOS 27 | Same |
| Python and pygame-ce | Python 3.14 and pygame-ce 2.5.8 (uv installs both) | Same |
| Memory | 4 GB, the smallest machine measured | Same |

The 60% recommended line is a proposal. The benchmark doesn't time drawing to the screen, so the
line leaves room for it. Windows passes the test suite in CI, but no Windows machine has been
measured.

## Measured platforms

<div class="requirements-explorer" data-source="../data/requirements.json" markdown>
<div class="explorer-controls"></div>
<div class="requirements-summary"><p>Loading the measurements…</p></div>
</div>

The FPS column is the rate a game would run at if every frame took the measure you picked
(1000 ÷ ms), colored from red at 15 FPS to green at 60 FPS and above; the black line on the scale
marks the target. The ranges are the lowest and highest across a machine's runs.

=== "Raspberry Pi 4"

    The Pi 4 has no added cooling and boots from an SD card. At 60 FPS, Brave Adventurer is too
    slow on it; it fits a 30 FPS target. A one-off CircleCI job (build 2857) measured a 30.1 ms
    flip per frame on SDL's `wayland` driver at 2560x1440: on a screen that size, presenting alone
    takes more than the 60 FPS budget.

    <div class="requirements-platform" data-platform="raspberry-pi-4"></div>

=== "Raspberry Pi 5"

    The Pi 5 has active cooling, and its NVMe case is a large heat sink. With only two runs, its
    ranges are thin. Drawing to a real screen hasn't been measured on it.

    <div class="requirements-platform" data-platform="raspberry-pi-5"></div>

=== "Apple M4 Max"

    The highest p99s (up to 20.2 ms) come from a few runs, most likely ones measured while the Mac
    was busy with other work. The typical run is ten times faster: pick "Slowest run's p99" to see
    what those runs alone would say.

    <div class="requirements-platform" data-platform="apple-m4-max"></div>

## How this was measured

- **Source:** the replay ledger, `quality/replay-ledger/` ([Replay Performance](quality/performance.md)),
  summarized in `docs/data/requirements.json`, which this page reads. Each ledger row is one
  measured run of one golden replay or bundled demo. The pre-push hook measures both Pis for each
  new code tree.
- **What a number is:** each frame's processing time while the recording replays headless,
  unpaced, on SDL's dummy driver. It is the game's own work, without drawing to a real screen.
- **Typical:** the median across a machine's runs. Runs are from November 5 to 9, 2026.

What the numbers leave out:

- **Drawing to a real screen.** Real-driver timing is planned, not yet measured.
- **Memory.** Not recorded in the ledger.
- **Thermals.** The ledger doesn't record temperature on Linux. The Pi 4, with no added cooling,
  varies about 12% across runs.
- **Other machines.** No Windows PC, x86 Linux machine or older Mac has been measured.
