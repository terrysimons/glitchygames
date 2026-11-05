# Raspberry Pi 4 as a CircleCI hardware runner

Status: in progress (branch `feat/rpi4-ci-runner`). The `taplo` fix and the job with its config
tests are written, uncommitted; the job is not in the workflow, and the runner is not installed.
Goal: run the test suite on real ARM
hardware, on every push, on `rpi4-ubuntu-2604` (terry@172.23.23.155).

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
3. **`taplo` breaks the install (fixed, uncommitted).** `nox -s test` installs all extras from
   `uv.lock`, and `taplo` 0.9.3 has no Linux ARM wheel (its sdist fails to build). A platform marker
   in `pyproject.toml` leaves it out there, and `noxfile.py` skips the TOML format and lint on Linux
   ARM, saying so.

## Steps

1. **Fix `taplo`.** Written, uncommitted (see blocker 3). Only `taplo`'s marker changed in
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
4. **Add a `build-and-test-raspberry-pi` job.** Written, uncommitted, and validated with
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
