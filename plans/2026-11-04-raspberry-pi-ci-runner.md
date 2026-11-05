# Raspberry Pi 4 as a CircleCI hardware runner

Status: in progress (branch `feat/hardware-runner`). The runner is installed and registered by
`ansible/raspberry_pi_runner.yml`, and online. `build-and-test-raspberry-pi` is defined but commented
out of the workflow: the owner, 2026-11-05, wants the Pi to run only its performance measurement at
push time, with the rows copied back before they are committed. A throwaway job (build 2857, removed) showed that jobs
inherit the display: SDL's `wayland` driver on the 2560x1440 screen, the `circleci` user's groups,
`vcgencmd`, and the service's 2 GiB memory limit. Its flip took 30.1 ms per frame on `wayland` and
2.4 ms on `dummy`. Why `wayland` is that slow is unmeasured: driver timing starts there.
Goal: run the test suite on real ARM
hardware, on every push, on `rpi4-ubuntu-2610` (terry@172.23.23.155).

## The host (read 2026-11-04)

- Ubuntu 26.10, aarch64, 4 CPUs, 3.7 GB RAM (1.7 GB in use while idle), 1 GB swap file.
- 464 GB SD card holds everything: `/`, `/tmp` and swap. No added cooling (44.8 C idle).
- `circleci-runner` not installed; `sudo` needs the owner's password.
- `/dev/vcio` is `root:root` mode 0600, so it has no group to join and `vcgencmd get_throttled`
  fails as `terry`. A udev rule gives it to the `video` group; `terry` and the runner's `circleci`
  user both need to be in that group.

## Blockers

1. **Fork builds.** The repository is public, and CircleCI does not allow self-hosted runners while
   "Build forked pull requests" is on. Not yet checked (the setting is not visible from here). Leave
   it off: a fork PR could otherwise alter the machine.
2. **The owner's GitHub key is on the Pi.** Jobs run directly on the host with the runner user's
   privileges. The private key must not be readable by that user; ideally replace it with a narrowly
   scoped key.
3. **`taplo` breaks the install (fixed).** `nox -s test` installs all extras from
   `uv.lock`, and `taplo` 0.9.3 has no Linux ARM wheel (its sdist fails to build). A platform marker
   in `pyproject.toml` leaves it out there, and `noxfile.py` skips the TOML format and lint on Linux
   ARM, saying so.

## Steps

1. **Fix `taplo`.** Done (see blocker 3). Only `taplo`'s marker changed in
   `uv.lock`; CI on the other platforms still has to confirm it.
2. **Install the runner.**
   - Create the resource class `terrysimons/raspberry-pi-4`. The owner handles the token and
     `sudo`.
   - Install machine runner 3 as its own `circleci` user; pre-install `fontconfig`, because that user
     has no `sudo`, and add it to the `video` group.
   - CircleCI lists Ubuntu 18.04+ on ARM64, but an apt package for ARM64 or 26.10 is unconfirmed
     (`apt-cache policy circleci-runner` settles it). If there is none, use the manual tarball.
3. **Measure one run by hand as the `circleci` user.** Record duration, peak memory, swap use, disk
   writes, temperature and throttling. This also shows whether the suite and its 100% coverage gate
   pass on ARM.
4. **Add a `build-and-test-raspberry-pi` job.** Written, and validated with
   `circleci config validate`. Add it to the workflow only once the runner and its resource class
   exist.
   - Executor: `machine: true` with the new resource class.
   - Steps: `checkout`, `install-deps-posix`, `nox-timer-report`, `nox-test`, a throttling check.
   - Cache: none from CircleCI. The uv cache stays on the host, and storage and network use credits.
     The job runs `uv cache prune` after the tests.
   - Workers: start with `PYTEST_WORKERS: "0"`. A serial run peaked near 1.4 GB (measured on the
     Linux CI job's setup), and parallel workers could reach swap on the SD card.
   - Config tests: `tests/test_ci_config.py` checks the job's runner, serial workers, no benchmarks,
     no `sudo` or CircleCI cache, and the prune and throttling steps. The job does not set
     `GLITCHYGAMES_TEST_RSS_LIMIT_MB`, which must appear exactly once in the config.
5. **Run it on a branch.** Check the job passes, then take the Pi offline to see how that behaves.

## Constraints

- **Never run `test_logging_cost.py` on the Pi** (SD card wear). `nox -s test` skips it unless
  `--benchmark-only` is passed, so this job is safe, but it must not run `nox-performance-test`.
- **SD wear.** The card still takes many writes per push, because `/tmp`, swap and the job's working
  files are all on it. Step 3 gives the real numbers.
- **One runner, one job at a time.** Pushes queue behind each other.

## Decisions for the owner

0. **Pending, recorded 2026-11-04.** Keep the desktop. Rename the host to `rpi4-ubuntu-2610`. Playbook
   packages: `git`, `curl`, `openssh-server`, `fontconfig`, `build-essential`, `python3-dev` (`numpy`
   and `miniaudio` compile from source), and uv pinned to 0.13.6 for `terry`. Remove `cargo` before
   the clean-user test: only `taplo` needed Rust. Limits stay on real hardware: the job sets the
   1600 MiB test guard; `MemoryMax=2G` and `MemorySwapMax=0` go on the runner's unit when it is
   installed. Commits from the Pi use the GitHub noreply address. OpenBLAS is not installed: testing
   it with and without is in `plans/future-work.md`, under Raspberry Pi speedups.
1. **Storage.** Recommended: a USB 3 SSD for the working directory, `/tmp` and swap if this runs on
   every push. Alternative: stay on the SD card and accept the wear step 3 measures.
2. **Required or advisory.** Recommended: advisory at first. CircleCI documents no timeout for queued
   jobs, so a required job could block merges whenever the Pi is offline. `deploy-docs` depends only
   on the macOS job, so it is not held up either way.
3. **Benchmarks.** Recommended: leave them out of the first version. They would need a Pi-safe session
   that excludes the logging test, and a Pi with no added cooling gives noisier numbers, so a nightly
   or `main`-only run may suit them better than every push.
4. **Setup method.** Decided: all changes to the Pi go through Ansible, not directly on the host
   (`ansible/raspberry_pi_runner.yml`). So far it holds the `/dev/vcio` access; the runner's install
   goes there too.

## Sources

- <https://circleci.com/docs/guides/execute/run-jobs-on-self-hosted-runners/>
- <https://circleci.com/docs/guides/execution-runner/runner-concepts/>
- <https://circleci.com/docs/runner/runner-overview/>
- <https://circleci.com/docs/runner/install-machine-runner-3-on-linux/>
- <https://circleci.com/docs/runner/machine-runner-3-manual-installation/>

## The Pi on the Performance page

The page reads `quality/replay-ledger/`, not `.benchmarks/`, and CI never measures, so the Pi appears
only through rows committed from it. On the Pi: `git add ...`, `nox -s measure-staged`, `git commit`,
then squash-merge. The hook is not installed there, so this is by hand. The first seven rows are in
this branch; if `main`'s code changes and the branch is updated, measure again. Check with
`glitchygames unmeasured --code-tree TREE`: without `--code-tree` it judges by commit.

## Real displays: the requirement that shapes the runner

The owner, 2026-11-04: "The hardware runners will have displays connected for performance
measurement." A hardware runner exists to measure real graphics drivers. Today nothing does:
`glitchygames measure` runs `--headless` on SDL's `dummy` driver, on any machine, and `CI=true` turns
driver comparison off. So the rows on the Performance page are CPU and engine time, not driver time.

### What the runner needs

1. **A real graphical session for the job.** `gdm` auto-logs in a dedicated `circleci` user at boot,
   and the runner runs inside that session, not as a plain system service, so jobs have the display.
   Not `terry`'s session: `~/.ssh/github` must stay out of the job's reach.
2. **A display that stays on.** No screen lock, blanking or suspend: a sleeping output can stop a
   compositor presenting frames.
3. **Exclusive use while measuring.** One job at a time. Playing the games on the Pi as `terry` means
   switching users, and an inactive session does not present, so a job could stall or measure nothing.
4. **Fail rather than fall back.** A job meant for the real driver fails if SDL chose `dummy` or
   `offscreen`, or if OpenGL is software (`llvmpipe`). A missing monitor must not produce numbers.
5. **Rows that say what they measured.** Record SDL's video and render driver, the GL renderer, the
   resolution and refresh rate. Different monitors must not read as one machine's history.
6. **Several machines.** Inventory group `hardware_runners`, a resource class per machine.

### Why both drivers

The owner, 2026-11-04: "We need both measurements to a) catch weird platform bugs, and b) do real
speed tests." They need different runs:

- **Platform bugs: every push.** `nox -s compare-drivers -- --drivers native --fail-on-difference`,
  pass or fail, in hidden windows (what stops stray input reaching tests). Add driver failures
  to this: a replay that diverges or crashes on the native driver fails the job.
- **Speed tests: per measured commit.** Replays on `dummy` and the native driver, in a visible window
  on the real display. `dummy` is the engine's own time; the difference is what the driver costs.
  Record processing and presenting separately: vsync can hold a real display to its refresh rate,
  which would hide headroom. Whether vsync can be off is the first thing to test on each platform.

### What has to be built

- **Measure both drivers.** The owner, 2026-11-04: "I want to measure *BOTH* hardware and dummy on
  systems that support it, like my mac does." `measure` replays every recording on `dummy`, then on
  each native driver that runs here (`scripts/driver_configurations.py` already finds them; Linux
  needs `WAYLAND_DISPLAY` or `DISPLAY`), unpaced where possible. Macs get this too. Today the Mac
  compares both drivers' frames in the tests, but its measured rows name no driver: of the last 400
  ledger rows, 393 are `measure`'s headless replays. `--compare-processing` needs `--headless` in
  the engine, so limits like that need checking first.
- **Rows name their driver.** Existing rows have no driver field and count as `dummy`. The graphs and
  the comparison dropdowns (`plans/2026-11-04-performance-page-comparison.md`) gain a driver choice,
  and machine plus driver is one line. Measuring takes about twice as long, in the pre-commit hook too.
- **Driver comparison on the runner.** Add `nox -s compare-drivers -- --drivers native
  --fail-on-difference` to the job, which `CI=true` otherwise leaves off in `nox -s test`.
- **A way for rows to reach the page.** The docs say "CI never measures (its machines vary)", because
  CI's machines vary. Fixed hardware removes that reason, but the rule and its tests change.

### Decisions for the owner

0. **Plotted speed numbers include the real driver: decided, 2026-11-04.** Today's rows are real
   machines on `dummy`, so they leave out the time spent presenting. Build driver timing.
0. **Driver time is measured, not judged: decided, 2026-11-04.** A slow present on real hardware
   is a number to record, not a failure, so driver timing sets no pass or fail limit on speed. The
   owner, on the Pi's 30.1 ms flip: "That's ok on the Pi. I want to measure it, not fail it."
0. **Registration is part of the deploy: decided, 2026-11-04.** `ansible/raspberry_pi_runner.yml`
   checks the fork setting with a personal API token (`CIRCLECI_API_TOKEN`), creates the resource
   class and token through the controller's `circleci auth login`, installs the runner, and sets up
   the auto-login session with a display that stays on. The runner starts after chrony's first sync
   (`chrony-wait`), because the Pi has no battery-backed clock and boots with a stale date.
1. **Do runners measure, or only test?** Recommended: measure once per merge to `main`, not on every
   push: rows only count once their code lands.
2. **How do rows land?** Recommended: push them to `gh-pages`' published ledger, which `docs-deploy`
   already merges, so a runner holds no key that can write to `main`. Alternative: a follow-up commit
   on `main`, which the code-tree rule accepts as its code tree is unchanged, but needs that key.
3. **Does `terry` still use the Pi's desktop?** Recommended: yes, between jobs, with a runner pause.
