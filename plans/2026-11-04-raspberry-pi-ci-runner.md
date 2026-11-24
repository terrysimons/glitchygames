# Raspberry Pi 4 as a CircleCI hardware runner

Status: in progress (branch `feat/hardware-runner`; the third Pi on
`feature/zombies-aint-my-neighbors`). The runner is installed and registered by
`ansible/raspberry_pi_runner.yml`, and online. `build-and-test-raspberry-pi` is defined but commented
out of the workflow. The owner, 2026-11-05: when they push, the replay measurement also runs on the
Pi, and its files are copied to their machine, in the right place. That is the pre-push hook
`raspberry-pi-replay-metrics` (`scripts/measure_on_raspberry_pi.py`). It stops a push that brings rows,
so they are committed first. All 7 recordings took 205 s in its first real run, with no throttling.
It measures on `dummy`, like every row today: real-driver measuring is
the driver timing work. A throwaway job (build 2857, removed) showed that jobs
inherit the display: SDL's `wayland` driver on the 2560x1440 screen, the `circleci` user's groups,
`vcgencmd`, and the service's 2 GiB memory limit. Its flip took 30.1 ms per frame on `wayland` and
2.4 ms on `dummy`. Why `wayland` is that slow is unmeasured: driver timing starts there.
Goal: run the test suite on real ARM
hardware, on every push, on `rpi4-ubuntu-2610` (terry@172.23.23.155).

**A second Pi (the owner, 2026-11-08):** a Raspberry Pi 5 Model B Rev 1.1, 16 GB, 4 cores, on
Ubuntu 26.04.1 LTS (aarch64, a local Wayland session), `rpi5-ubuntu-2604` (terry@172.23.23.161).
It does both jobs the Pi 4 does: a CircleCI machine runner (resource class
`terrysimons/raspberry-pi-5`, job `build-and-test-raspberry-pi-5`, the Pi 4's job merged with
its own resource class, and like it left out of the workflow) and a machine the pre-push hook
measures on. The two Pis are `ansible/inventory.yml`'s `raspberry_pis`, which the playbook sets
up together (`--limit raspberry-pi-5` for one); the Pi 4's host and job were renamed
`raspberry-pi-4` and `build-and-test-raspberry-pi-4`. The hook measures on both at once, each
Pi's push, measurement and row fetch in its own thread, its output prefixed with its name;
staging, git's index, runs once for both (the owner: the row copying runs in parallel). A Pi that
cannot be reached stops the push before either measures. Its runner keeps the 2 GB limit (the
owner: "Leave it capped at 2GB"). The playbook's OS steps were checked against it on 2026-11-08
and need no change: `/dev/vcio` is root-only as on the Pi 4, gdm3 and its `custom.conf` are
there, chrony is not yet (the playbook installs it), and the runner's repository is added for any
release.

**A third Pi (the owner, 2026-11-14):** a Raspberry Pi 5 with 8 GB on Ubuntu 26.10, at
172.23.23.140, host `raspberry-pi-5-8gb` (hostname `rpi5-8gb-ubuntu-2610`, which the playbook
sets). It does both jobs the others do: a CircleCI machine runner (resource class
`terrysimons/raspberry-pi-5-8gb`, job `build-and-test-raspberry-pi-5-8gb`, the Pi 4's job on its
own runner, left out of the workflow) and a machine the pre-push hook measures on (the owner:
added to the hook at once). Its runner keeps the same 2 GB limit. Never provisioned before; the
owner installed the ssh key (`~/.ssh/github.pub`, the key the 16 GB Pi takes) on 2026-11-14.
Read that day, before the playbook's first run: a Raspberry Pi 5 Model B Rev 1.0 (the 16 GB Pi is
Rev 1.1) in the official cooled case, 4 cores, 7.7 GiB RAM (1.8 GiB in use), Ubuntu 26.10
aarch64; a 229 GB SD card (213 GB free), a 1 GB swap file, `/tmp` in memory (tmpfs, unlike the
Pi 4). Its hostname was `terry-rpi5-official-cooled-case` (the playbook renames it). The
playbook's OS steps need no change: `/dev/vcio` is root-only (`vcgencmd` fails as `terry`) as on
the others, gdm3 and its `custom.conf` are there, chrony is already installed, `/usr/bin/python3`
is there, `terry` is in `sudo`, and a desktop session runs on seat0. Its resource class is created
in CircleCI on the playbook's first run; until the Pi is set up, push with
`SKIP=raspberry-pi-replay-metrics`. Its first playbook run stopped at the throttling check: `terry` joined
`video` mid-run, and Ansible skips sudo when the become user is the login user (ansible-core's
`BECOME_ALLOW_SAME_USER`, off by default), so the check ran in the ssh session opened before the
group was added. The playbook now names its two users (`deploy_user`, the login;
`ci_user`, the runner's `circleci`): deploy-user tasks run with `become: false`, the
CI user through sudo, and the play reconnects (`meta: reset_connection`) before checking the
deploy user (tests in `tests/test_ci_config.py`).

**The Pis renamed (the owner, 2026-11-14):** each name now says its RAM and that it runs Ubuntu:
`raspberry-pi-4-4gb-ubuntu`, `raspberry-pi-5-16gb-ubuntu` and `raspberry-pi-5-8gb-ubuntu`, as
inventory hosts, CircleCI jobs (`build-and-test-<host>`), the push hook's names, and resource
classes (`terrysimons/<host>`; the owner chose to rename the registered ones too). The names
above this note are as they were then. The ledger's row files are named by board
(`raspberry-pi-4-model-b-rev-1-4`) and the requirements page by hardware slug, so neither
changed. The Pi 4 and the 16 GB Pi 5 are registered in CircleCI under the old classes and their
runners hold tokens for them; the playbook only registers a Pi whose config has no token, so
those two must be re-registered before their new classes have a runner.

**Grouped by OS, with their firmware managed (the owner, 2026-11-14):** `raspberry_pis` holds
one child group per OS: `raspberry_pis_ubuntu` (Ubuntu 26.04 and 26.10; all three Pis) and
`raspberry_pis_raspberry_pi_os` (Raspberry Pi OS 64-bit, Trixie only, the owner's choice; no Pi
yet). Each group says how Ansible reports its OS and which releases it supports, and each Pi the
release it runs. The playbook's plays share three roles:

- `raspberry_pi_os` (every play's first step) refuses a Pi whose reported OS or release isn't
  the inventory's, and on Raspberry Pi OS one without `/etc/rpi-issue` (its os-release is
  Debian's).
- `raspberry_pi_desktop` (the runner play) logs the runner's user in at boot and keeps the
  display on, each OS's way: gdm3 and dconf on Ubuntu (the tasks moved here unchanged); on
  Raspberry Pi OS, lightdm's `autologin-user` and no `swayidle` in labwc's autostart files, as
  raspi-config's `do_autologin` and `do_blanking` do it (read from its trixie branch), by hand
  since `do_blanking` detects labwc by a running session.
- `raspberry_pi_firmware` (one play per OS group) writes each Pi's clock
  (`raspberry_pi_overclock_settings`) and fan (`raspberry_pi_fan`: kind, pin, levels in Celsius)
  as one `blockinfile` block appended to `/boot/firmware/config.txt`: the board's own section
  (`[pi5]`/`[pi4]`) ending with `[all]`. Pi 5: the Active Cooler's `dtparam=fan_tempN`,
  `_hyst`, `_speed` (no levels keeps the firmware's default curve); Pi 4: `dtoverlay=gpio-fan`
  (on and off) or `dtoverlay=pwm-gpio-fan` (four levels), as the overlay README on the Pis
  describes them. It refuses a Pi whose model isn't its board, a setting or fan its board can't
  have, and any clock or fan line typed by hand outside a block; says when a reboot is needed
  and never reboots; and when nothing changed checks the clock against `vcgencmd get_config` and
  the Active Cooler's levels against thermal zone 0's trip points.

Every Pi starts with the firmware's defaults for its fan (the owner: build it, apply curves only
once a measurement under load justifies them); the Pi 4 has no fan. A dry run on the three Pis
(`--check --diff`, no sudo, 2026-11-14) showed the one change expected: the 16 GB Pi 5's
hand-typed `[pi5]` lines removed and its block added; the other two unchanged. The Raspberry Pi
OS tasks have not run on a Pi. Tests: `tests/test_ansible_raspberry_pis.py` (the templates and
assertions rendered as Ansible renders them, the hand-set line check run with awk on the Pis'
own config.txt), and `tests/ansible_inventory.py` reads the inventory's nested groups for every
Pi test.

**The first real run (2026-11-14) and its backup.** The run on the three Ubuntu Pis failed on the
16 GB Pi 5 at the block: `blockinfile`'s `backup: true` names its copy
`config.txt.<pid>.<date>@<hh:mm:ss>~`, and `/boot/firmware` is FAT (`vfat`), where a colon is no
file name (`[Errno 22]`). Its hand-typed `[pi5]` lines had just been removed by the cleanup, so
the Pi would boot stock until the block is written; the other two were unchanged. Check mode
makes no backups, which is why the dry run passed. Now the role keeps `config.txt` in memory
before any change and keeps one backup beside it, `config.txt.ansible-backup` (the owner's
choice): made when missing, replaced with the file as it was whenever a run changes it. The
16 GB Pi's cleanup moved into the role as data (its `raspberry_pi_firmware_hand_typed_patterns`),
so one backup covers both changes. The plays import their roles (`import_role`), since
`--start-at-task` cannot reach tasks of an included role. Tests: no task writing the boot
partition uses Ansible's `backup` option, and the backup's name is FAT-safe; and
`test_raspberry_pi_os_overclock` runs a Raspberry Pi OS Pi 5 and Pi 4 through the role on that
OS's default config.txt (pi-gen ccafc13f2574).

**The runner's display mode (the owner, 2026-11-14): 1920x1080 at 120 Hz on every Pi.** The CI
jobs run as `circleci`, whose GNOME session ran 3840x2160 at scale 1.5 (at 60 Hz on the 16 GB Pi
5, 30 Hz on the Pi 4). The owner's own `monitors.xml` names an ASUS ROG XG27UQ, but the monitor
attached through the switch is now a FUERAN 4K/120, so a config pinned to one monitor would not
apply. At 1080p a Pi 5 offers 120.040, 120.000 and 119.880 Hz, a Pi 4 only 120.000 and 119.880;
the owner chose 120 Hz everywhere (the standard 1080p120 timing, so all three drive the display
alike). The monitor is a headless HDMI dummy plug on each Pi (the owner). GNOME 50 saves a display
change only when someone clicks Keep in its "Keep these display settings?" dialog, and reverts it
after 20 seconds otherwise; mutter's source has no unattended way to confirm. Both mutter's
`ApplyMonitorsConfig` (persistent) over D-Bus and `gdctl set --persistent` reverted at 20 s on
every Pi they ran on once (journals: 22:27:23 to 22:27:43 on the 16 GB Pi 5; 22:42:26 to 22:42:46
and 22:42:28 to 22:42:48 on the others). The 16 GB Pi 5 kept 1080p after a manual `gdctl -P` only
because it ran twice, 5 s apart: the second apply cancelled the first's revert, and its own revert
"restored" 1080p, unsaved (`circleci`'s `monitors.xml` was last written at 19:45, for the ASUS
monitor). So the mode is applied temporarily, which asks nothing, with GNOME's own tool (the
owner's rule: use the OS's tool, not its config files): `files/apply_display_mode` runs the
planner `files/plan_display_mode.py` (reads mutter's `GetCurrentState`, picks the wanted size at
the first wanted rate offered, else the highest at that size) and on apply runs `gdctl set
--logical-monitor --primary --scale 1 --monitor <connector> --mode <mode>`. It runs at every
`circleci` login (a GNOME autostart entry) and on every deploy, which then waits 25 s past the
revert window and plans again, failing unless nothing is left to apply. Shown on the three Pis
(2026-11-14): the deploy's apply held on the Pi 4 and 8 GB Pi 5 (no revert at +20 s, the held
check passed; the 16 GB Pi 5 planned none); after a reboot, GNOME launched the autostart entry in
each `circleci` session, it planned `apply HDMI-1 1920x1080@120.000` on all three (the 16 GB Pi 5
had come back in 4K: its earlier 1080p was never saved), and `gdctl show` reported
1920x1080@120.000 at scale 1.0 on each, past the 20 s.

**CircleCI's package repository, declared (2026-11-14).** packagecloud's install script (piped to
bash) re-ran on every deploy and rewrote the repository and its key: its `creates:` named
`circleci_runner.list`, but with `?any=true` the script writes `circleci_runner_any.list`. The
runner play now removes the script's two files (apt refuses one repository listed twice with
different keys) and declares the same repository with `deb822_repository` (`any any main`,
`signed_by` the key URL, which redirects to the key file whose fingerprint
81F73EBF5373FB699904EA158CD45F21E87AC85C matched the script's keyring), refreshing apt's lists only
when it changed. It reports a change only when the repository or its key really changes. A dry
run on the 16 GB Pi 5 showed the expected first run; `python3-debian` is installed for the
module.

**Output in the hosts' natural order (2026-11-14).** The plays run hosts in inventory order, but
Ansible prints each host's result as it finishes, so the faster Pi 5s printed before the Pi 4.
`ansible.cfg` at the repository root selects `ansible/callback_plugins/natural_order.py`, the
default output with each task's results held and printed host by host in natural order (4gb,
8gb, 16gb); its ordering is `ansible/plugin_support/natural_order.py`, plain Python the tests run
(Ansible isn't in this project's environment), and the inventory tests use its natural key. Shown
with real Ansible on three local stand-in hosts finishing in reverse order (results, loop items,
skips and a failure). Ansible's own `PLAY RECAP` keeps its alphabetical list. The inventory's `raspberry_pi_display_mode` holds the size and
rates. Tests run the script's planning on both boards' captured GetCurrentState
(`tests/fixtures/mutter/`). **To do:** Raspberry Pi OS (labwc) sets modes another way (kanshi);
add it to that OS's desktop tasks once a Pi OS host can be read.

The audit (read 2026-11-14, nothing changed): the Pi 4 is stock at 1800 MHz (Ubuntu's
`arm_boost=1`), with no fan, and has throttled since its boot (`get_throttled` 0xe0000: capped,
throttled, soft temperature limit; no undervoltage), so a row measured on it under load may have
run throttled. The 16 GB Pi 5 was overclocked by hand in `[pi5]`: `arm_freq=3000`,
`over_voltage=6`, and `gpu_fre=1100`, a typo the firmware ignored, so its GPU was never
overclocked; its inventory now holds all three, `gpu_freq` spelled right (the owner: "Fix the
typo"), and a one-off task removes the hand-typed section. The 8 GB Pi 5 is stock at 2400 MHz.
Both Pi 5s have the active cooler on the firmware's default curve (50, 60, 67.5, 75 C); fan
curves are not managed yet. A measured row records the board, memory, cores and kernel but no
clock, voltage or throttling, so an overclocked Pi's rows can't be told from a stock one's:
recording them needs the engine (`src/glitchygames/replay/`), off-limits on this branch.

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

## The first Raspberry Pi OS Pi (2026-11-16)

The owner's 16 GB Pi 5 in the NVMe heat-sink case, on Raspberry Pi OS (Debian 13 Trixie, the
2026-10-06 image), brought up to the Ubuntu 16 GB Pi's settings: "This is the 16GB with the fancy
case, so we need to turn on throttling. All of the same sorts of corallary settings that the
Ubuntu system had" (throttling: the overclock, "The overclock yess"), and "All of the Raspberry Pi
OS specific stuff still needs to be wired up". On this branch ("This branch").

### What the audit found (read from both 16 GB Pis, changing nothing)

| | Ubuntu 16 GB | Raspberry Pi OS 16 GB |
|---|---|---|
| Kernel, page size | 7.0.0 raspi, 4 KB | 6.18.60 rpi-2712, 16 KB |
| Memory cgroup | on | off: the firmware's own boot arguments carry `cgroup_disable=memory` |
| Desktop | GNOME (gdm, gdctl) | labwc under lightdm (wlr-randr, kanshi) |
| Clock | 3000 MHz, GPU 1100, over_voltage 6 | stock |
| Boot drive | NVMe, Samsung 970 PRO 1 TB | NVMe, WD SN550 250 GB |
| Network | Wi-Fi, fixed address | Wi-Fi, DHCP (dynamic) |

### Decisions

| Decision | Value | Why |
|---|---|---|
| The host | `raspberry-pi-5-16gb-raspberry-pi-os`, reached at `glitchygames-pi5-16gb-raspberrypios.local`, hostname kept as `glitchygames-pi5-16gb-raspberrypios` | Its address is a DHCP lease; the playbook names the host, so another name would rename it and its `.local` name mid-run |
| Its settings | The Ubuntu 16 GB Pi's: `arm_freq` 3000, `gpu_freq` 1100, `over_voltage` 6, the Active Cooler on the firmware's default curve | The owner's parity; the same values on a different chip are to be proven by a load test after the first boot at 3 GHz |
| The memory cgroup | Left alone: the boot arguments are not touched (the owner, 2026-11-16: "Leave boot arguments alone but make a todo"), so this Pi's runner `MemoryMax=2G` is written and not enforced. A to-do in plans/future-work.md ("The Raspberry Pi OS Pi's memory cgroup") | It matters only once a Pi's CircleCI job runs, and none does. If enabled later: append `cgroup_memory=1 cgroup_enable=memory` to `/boot/firmware/cmdline.txt` (https://docs.k3s.io/installation/requirements); not by removing `cgroup_disable=memory`, which cmdline.txt doesn't have: the firmware puts it in the boot arguments ahead of cmdline.txt's (read 2026-11-16: `/proc/device-tree/chosen/bootargs`) |
| The display mode | One shared set of display tasks for both OSes: the same planner (`plan_display_mode.py`) reads mutter's state on GNOME and `wlr-randr --json` on labwc (an adapter to the same shape), and a login entry in `~/.config/autostart` applies it (lxsession-xdg-autostart runs those under labwc, as GNOME does) | The monitor's preferred mode is 3840x2160 at 60 Hz, so the runner's session would start in 4K. Not the user's `~/.config/labwc/autostart`: labwc reads it instead of the system one, which starts the panel and kanshi |
| Natural order | Within each OS group | The inventory lists hosts group by group; no name keeps all five in one natural order |
| CI and measuring | Its `build-and-test-` job (off, as the others) and its place in the push-time measuring | Parity |

### The 8 GB Pi on Raspberry Pi OS (the owner, 2026-11-21)

A second Raspberry Pi OS Pi, `raspberry-pi-5-8gb-raspberry-pi-os`, reached at
`glitchygames-pi5-8gb-raspberry-pi-os.local` (its hostname as it came, spelled `raspberry-pi-os`
where the 16 GB Pi's is `raspberrypios`; a DHCP lease on wlan0). Read over SSH 2026-11-21:
Raspberry Pi 5 Model B Rev 1.0, 8 GB, Debian 13 (13.7), kernel 6.18.60+rpt-rpi-2712, stock clock
(`arm_freq=2400`, `over_voltage=0`), the `ondemand` governor (none set in the inventory), a PWM
fan taken as the Active Cooler on the default curve, and a 1 TB microSD card (no NVMe SSD). Its
`build-and-test-` job is defined and off in the workflow, like every Pi's. Provisioned 2026-11-22:
the owner ran the playbook with `--limit` this host, which created the resource class
`terrysimons/raspberry-pi-5-8gb-raspberry-pi-os` and registered its runner (online); read back
over SSH, uv and the `~/glitchygames-measure` clone are in place and the runner service is active.
Its cgroup has no memory controller, like the 16 GB Raspberry Pi OS Pi's (see the to-do in
plans/future-work.md).

### Built (2026-11-16, uncommitted), and what only the Pi can prove

The inventory host, its CI job (off) and its place in the push-time measuring; one display path for
both desktops (`display_mode.yml`: the planner reads `wlr-randr --json` through an adapter, and
`apply_labwc_display_mode` sets the mode with wlr-randr), tested on the Pi's own captured
`wlr-randr --json` (`tests/fixtures/wlr-randr/`). The boot arguments are left alone (above).

To bring it up (the owner's run: it needs sudo and a reboot):

1. As the playbook's header says (the circleci CLI logged in, `unset CIRCLE_TOKEN`, and
   `read -rs CIRCLECI_API_TOKEN && export CIRCLECI_API_TOKEN`), then
   `uv run --extra dev ansible-playbook -i ansible/inventory.yml ansible/raspberry_pi_runner.yml --limit raspberry-pi-5-16gb-raspberry-pi-os --ask-become-pass`
   (ansible-core is in the dev extra since 2026-11-16, and alone, without the community
   bundle, since 2026-11-17: 2.22 is the first to run on Python 3.15).
2. Reboot it: the overclock and the runner's auto-login apply at boot.
3. Run the playbook again: it checks the firmware runs 3000 MHz, GPU 1100 and over_voltage 6, and
   applies and checks 1080p at 120 Hz in the runner's session.

Then, by hand: a few minutes of full load at 3 GHz with `vcgencmd get_throttled` and
`measure_temp` (the overclock was proven on the Ubuntu Pi's chip, not this one); and `uv --version`
plus `uv run python -c 'import numpy'` as the runner's user (16 KB pages: never exercised before).

### Brought up (2026-11-16)

The owner ran the playbook, rebooted and ran it again. Read afterwards on the Pi: the managed block
in `config.txt` holds `arm_freq=3000`, `gpu_freq=1100`, `over_voltage=6`, and the firmware runs
exactly those (`vcgencmd get_config`); the original is kept as `config.txt.ansible-backup`;
`circleci-runner` is enabled and active; lightdm auto-logs in as `circleci`; `libusb-1.0-0-dev`
and `libudev-dev` are installed; the display scripts are in `/usr/local/lib/glitchygames`. The
owner confirmed 1920x1080 at 120 Hz on the runner's session.

The load test at 3 GHz (all four cores in busy loops for five minutes, from the owner's login,
sampled every 5 s, a stop at 82 C that never triggered): 3000 MHz throughout, 60.4 C at 30 s,
73.6 C at 3 min, levelling at 75.7 C, peak 77.9 C, back to 52.7 C 20 s after; `get_throttled`
0x0 at the end (its flags latch until reboot, so no under-voltage, cap or throttle happened).
About 7 C below the Pi 5's 85 C throttle, with the Active Cooler on the firmware's default curve.
Not exercised: floating point, memory bandwidth, the GPU, or a run longer than five minutes; the
Pi job prints `vcgencmd get_throttled` and `measure_temp` after every run, where a real workload
would show any throttling.

Still to check on a first run as the runner's user: `uv` and the Python it downloads on the 16 KB
page kernel.
