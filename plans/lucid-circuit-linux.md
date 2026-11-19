# Lucid Circuit: the local AI service on Linux, and its .deb

- **Date:** 2026-11-18
- **Status:** Design approved by the owner (2026-11-18), not built. Branch `feature/ai-service-raspberry-pi`. Benchmarks on the first
  machine (a Raspberry Pi 5) wait for its power supply to be fixed (section 8.3).
- **Implementation plan:** [lucid-circuit-linux-implementation.md](lucid-circuit-linux-implementation.md).
- **Master plan:** [lucid-circuit.md](lucid-circuit.md). This sub-plan widens section 6 (the
  installer) and the Ansible setup from "a Mac" to "a Mac or a Linux machine": 64-bit ARM, built
  and tested on a 16 GB Raspberry Pi 5 first, and x86_64, designed for but not yet tested.
- **Source:** the owner, 2026-11-17: "16GB Raspberry Pi systems should be able to bring up the
  smallest 0.6B model", then "let's do the 2B model ... and embedding ... Same as a regular host",
  then "Also create a .deb for the service, just like we did a .pkg for the service on mac"; and
  2026-11-18: "We'll need to support other linux arm systems too", then a generic Linux document
  with a Raspberry Pi section, x86_64 "designed for and not tested yet".

## 1. Intent

A Linux machine gets the local AI service the way a Mac does: Bonsai 2 2B (reasoning and vision)
and Qwen3-Embedding 0.6B, installed by Ansible, started when a game loads and stopped after the
last game leaves, with nothing using memory in between. A `.deb` installs the same service without
Ansible, as the `.pkg` does on a Mac.

Why: the Raspberry Pis are already the project's second platform (CI runners, the pre-push
measurements), and games run on them. With the service on Linux, every Lucid Circuit feature
(console, agents, the mirror) can be built and tested beyond the owner's Mac, and the same design
reaches any other ARM board or x86_64 machine without a rewrite.

There is no 0.6B Bonsai. The smallest reasoning model is 2B; 0.6B is the embedding model, which the
service always runs beside it.

## 2. Goals, non-goals, anti-goals

**Goals**

1. Ansible installs the service on any `ai_enabled` Linux host the inventory lists, with the same
   models, pins, ports, keys, settings and on-demand start as a Mac. First host: the 16 GB Ubuntu
   Raspberry Pi 5.
2. A `.deb` holds the service with no model; after install, each user's models download in the
   background on first login, as the `.pkg`'s setup job does.
3. A game on Linux finds and starts the service exactly as on a Mac (`ai_link.py`): the same exit
   codes, the same "not enough memory means no AI this run".
4. One code path wherever platforms differ only in a backend: the size picker, the agent settings
   and the staging are shared, and only memory reading, process control and packaging have a macOS
   and a Linux implementation.
5. **Architecture-neutral.** Nothing in the design names a board or a CPU model. One build per
   architecture runs on every CPU of that architecture and uses the best instructions the CPU it
   lands on has (6.4). Whether a machine *gets* the models stays the memory picker's decision.
   64-bit ARM is built and tested now (on the Pi 5); x86_64 is designed for (every
   architecture-dependent value is a variable with its x86_64 value written down, section 4) and
   checked only by static tests until an x86_64 host joins the inventory (section 9).

**Non-goals (now)**

- Running or testing on x86_64 hardware, or building x86_64 in an emulated container.
- GPU backends on any Linux machine. On the Pi the GPU was measured and ruled out (8.1); on x86_64
  desktops a GPU is the natural next step (9.2), using the same runtime-loaded backends (6.4).
- A players' release: signing, an apt repository, building on the oldest supported distribution,
  a clean-machine matrix. These are Stage 12 in the master plan, for the `.pkg` too.
- Linux without systemd (Alpine and the like) and distributions without `dpkg` (Fedora, Arch). The
  staging is kept apart from the packaging (6.6) so an `.rpm` or a tarball can be added from the
  same stage later; the systemd units are the one part such a port would replace.
- Windows.

**Anti-goals (a failure even if it works)**

- The game's frame rate suffers because the AI took every core.
- A second, Linux-only copy of the picker, the agent settings or the download logic that drifts
  from the Mac's; or ARM- and x86-specific copies of anything beyond the values in section 4.
- A build tuned to the machine that compiled it, so the same `.deb` crashes (SIGILL) or runs slowly
  on another machine of the same architecture.
- A `.deb` that installs where it can't run (a newer glibc than the system's, another
  architecture) instead of `apt` refusing it clearly.
- `dpkg -r` leaving system files behind, or `dpkg` touching a user's models and history.

## 3. Constraints

- **CPUs differ within an architecture,** and the speed of quantised inference depends on the
  instructions they have: on ARM from no dot product (Cortex-A72) up to SVE2 and SME; on x86_64
  from SSE4.2 up to AVX-512 and AMX.
- **Memory.** On the Mac, 2B and 0.6B together reserved 6.5 GB at the configured context (master
  plan section 5, `ai_service_bonsai_reserved_mib`), with 2 GB kept for the game
  (`ai_service_game_reserve_mib`). The figures were measured on Metal and are provisional on Linux
  until measured on a Linux CPU (8.3).
- **Page size.** Linux kernels run 4K, 16K or 64K pages (ARM especially). Every binary shipped must
  run on all three.
- **glibc.** A binary runs only on a glibc at least as new as the one it was built against.
- **The CPU is shared.** Without a GPU backend, the game and inference compete for the same cores.
- **Unchanged rules from the master plan:** loopback only, keys for the API and the workers,
  nothing starts at login, models start on demand and stop 30 s after the last session, pinned
  revisions with SHA-256 checks and `reasoning_effort: medium`. The context changes: 128K (6.5).

## 4. Architectures

Every value the design needs per architecture. Ansible chooses by
`ansible_facts['architecture']`; nothing else tests for an architecture.

| | 64-bit ARM (`aarch64`) | x86_64 |
|---|---|---|
| Status | Built and tested (on the Pi 5, 8.3) | Designed for, static tests only (9) |
| `.deb` architecture | `arm64` | `amd64` |
| Sidecar Python build | `cpython-<version>-linux-aarch64-gnu` | `cpython-<version>-linux-x86_64-gnu` |
| llama.cpp CPU variants at `b12167` | 8 (below) | 14 (below) |
| GPU | none in scope; the Pi's measured and ruled out (8.1) | none in scope; the next step (9.2) |

**llama.cpp's CPU variants**, from `ggml/src/CMakeLists.txt` at the pinned `b12167` with
`GGML_CPU_ALL_VARIANTS` on (read 2026-11-18). `llama-server` loads the best one the CPU supports.

- ARM on Linux: `armv8.0_1` (baseline), `armv8.2_1` (dot product), `armv8.2_2` (+ fp16
  arithmetic), `armv8.2_3` (+ SVE), `armv8.6_1` (+ i8mm), `armv8.6_2` (+ SVE2), `armv9.2_1` and
  `armv9.2_2` (+ SME, without and with SVE2). The Pi 5's Cortex-A76 gets `armv8.2_2`; a Pi 4's A72
  gets `armv8.0_1` (from their published cores; only the Pi 5's features were measured here).
- x86_64: `x64`, `sse42`, `sandybridge`, `ivybridge`, `piledriver`, `haswell`, `skylakex`,
  `cannonlake`, `cascadelake`, `icelake`, `cooperlake`, `zen4`, `alderlake`, `sapphirerapids` (the
  last four of these with AVX-512 BF16, AVX-VNNI or AMX; four are built only outside MSVC, which
  Linux always is).

## 5. Approaches

### 5.1 How Ansible and the .deb install

The Mac installs everything into the user's home, both by Ansible and by the `.pkg` (which is
built from what Ansible installed). On Linux, `dpkg` installs as root and tracks system paths only.

| Approach | What happens on a Linux host | Trade-off |
|---|---|---|
| **A. One layout: Ansible builds the .deb and installs it** (chosen) | Ansible builds llama.cpp and the sidecar on the host, stages them, builds the `.deb`, installs it with `apt`, then runs the per-user setup for the owner. Anyone else's machine gets the same `.deb` | One Linux layout and one install path, so Ansible exercises exactly what the `.deb` does. Needs `become` (sudo), as `raspberry_pi_runner.yml` already does |
| B. Two layouts: Ansible per-user like the Mac, the .deb system-wide | Ansible copies into `~/.local/share`; the `.deb` into `/opt` | Two Linux layouts, two sets of paths in `ai_link.py`, and Ansible never tests the `.deb` |
| C. The .deb's postinst copies everything into the installing user's home | Mirrors the `.pkg` | `dpkg` doesn't know those files: `dpkg -r` leaves them, a second user gets nothing |

**A**, because it follows the project's rule of one shared code path and makes every Ansible run a
test of the package. Confirmed by the owner, 2026-11-18.

### 5.2 Where the models run

On the CPU, on every Linux machine for now (non-goals, section 2). The build links no GPU loader.

### 5.3 How the shared shell logic handles two platforms

`ai-service.sh`, `run-llama-server.sh` and the setup script stay one Jinja template each. The
platform parts become named shell functions (`total_memory_mb`, `available_memory_mb`,
`agent_is_running`, `start_agent_process`, `stop_agent_process`, `port_is_listening`,
`sha256_of`) whose bodies are chosen at render time by `ansible_facts['system']`. The size picker,
the overrides, the exit codes and the start order stay written once. Two separate scripts were
rejected: they would drift. Nothing in these scripts depends on the architecture.

## 6. The design

### 6.1 Layout

| What | Where | Owner |
|---|---|---|
| `llama-server`, its libraries, its license | `/opt/glitchygames/ai/runtime/llama.cpp-<tag>-<options hash>/` | the `.deb` |
| The sidecar Python and the service | `/opt/glitchygames/ai/sidecar/` | the `.deb` |
| `ai-service.sh`, `run-llama-server.sh`, `setup.sh`, `uninstall-user.sh` | `/opt/glitchygames/ai/bin/` | the `.deb` |
| Per-agent settings templates, `service.json` template, notices | `/opt/glitchygames/ai/share/` | the `.deb` |
| systemd user units (one per agent, the API, the setup job) | `/usr/lib/systemd/user/` | the `.deb` |
| Models | `~/.local/share/glitchygames/ai/models/` | the user |
| Keys, `service.json`, each agent's `.env`, `selection.env` | `~/.local/share/glitchygames/ai/config/` | the user |
| Console history | `~/.local/share/glitchygames/ai/history/` | the user |
| Logs | `~/.local/state/glitchygames/ai/logs/` (and the user journal) | the user |
| Build trees, downloads in progress | `~/.cache/glitchygames/ai/` | the user |

The paths are lowercase, matching the engine's existing Linux save and cache folders
(`~/.local/share/<game>`, `~/.cache/<game>`), and `/opt/glitchygames/ai` follows the filesystem
standard's `/opt/<provider>/<package>`, so later packages sit beside it. The Mac keeps
`~/Library/Application Support/GlitchyGames/AI`. `$XDG_DATA_HOME`, `$XDG_STATE_HOME` and
`$XDG_CACHE_HOME` win when set.

The group variables become per platform: `ansible/group_vars/macos.yml` as today, and a new
`ansible/group_vars/linux.yml` with `ai_program_root: /opt/glitchygames/ai` and `ai_user_root`,
`ai_cache_root`, `ai_log_root` under the XDG paths. On a Mac `ai_program_root` and `ai_user_root`
are the same folder, so every template can name the two roles without a platform test.

Today's single `ai_install_root` (`group_vars/macos.yml`) is used across the roles:
`ai_sidecar`, `ai_service`, `ai_models` and `ai_package` defaults, and `ai_package/tasks/main.yml`
line 64 among others. It is replaced everywhere by whichever of the two each use means
(programs: `ai_program_root`; models, keys, history: `ai_user_root`), and no alias is kept, so a
missed use fails loudly. The builder lists every use first (`grep -rn ai_install_root ansible/`)
and records the mapping in the plan.

### 6.2 Processes: systemd user units in place of launchd agents

Each launchd agent becomes a systemd user unit with the same label as its name
(`ai.glitchygames.bonsai-2-2b.llama-cpp.service`,
`ai.glitchygames.qwen3-embedding-0.6b.llama-cpp.service`, `ai.glitchygames.api.service`):
`Type=simple`, `ExecStart=` the same `run-llama-server.sh CONFIG LABEL`, `Restart=on-failure` (an
exit 0 from `refuse` stops it, as `SuccessfulExit=false` does on a Mac), `RestartSec=10`. **No
`[Install]` section**: nothing starts at login; `ai-service.sh` starts them with
`systemctl --user start` and stops them with `systemctl --user stop`. The unit names `%h` for the
home, so one unit file serves every user.

**CPU placement of the two model units** (the owner, 2026-11-18). The cores a game needs: one for
the game's main thread and one for the mirror, the AI's headless copy of the game, which runs
uncapped while it catches up (Stage 4b). llama.cpp gets the rest.

- **Each part on its own cores (the owner, 2026-11-18): the game on the fastest core, the mirror
  on the next fastest, everything AI sharing the rest.** "Everything AI" is both model units, the
  API sidecar and the setup job. On a Pi 5, whose cores are all alike, that is the game on core 0,
  the mirror on core 1 and the AI on cores 2-3.
- **Cores are ranked by speed, not by number.** `setup.sh` orders the cores by
  `/sys/devices/system/cpu/cpu*/cpu_capacity`, highest first, ties by core number; the game takes
  the first, the mirror the second, the AI the rest. Speed and not number, because big.LITTLE
  chips often number their little cores first: the RK3588's four A55s are cores 0-3 and its four
  A76s cores 4-7, so "core 0" there would be a slow core (the owner asked for the game and the
  mirror both on big cores, 2026-11-18). Where every core is alike, or no core reports a capacity,
  or only some do, the ranking is by number alone:

  | Machine | Capacities | Game | Mirror | AI units | `AI_THREADS` |
  |---|---|---|---|---|---|
  | Pi 5 | 4 alike | 0 | 1 | 2, 3 | 2 |
  | 8 alike | 8 alike | 0 | 1 | 2-7 | 6 |
  | RK3588-style | cores 0-3 little, 4-7 big | 4 | 5 | 0-3, 6, 7 | 6 |
  | Three tiers | core 7 fastest, 4-6 big, 0-3 little | 7 | 4 | 0-3, 5, 6 | 6 |
  | 3 alike | 3 alike | 0 | 1 | 2 | 1 |
  | 2 cores | either | the faster | the other (shared with the AI) | the slower | 1 |
  | 1 core | | not pinned | not pinned | not pinned | 1 |

  With two cores the mirror shares the AI's core rather than the game's: the game is the one a
  person watches.
- **Open, for a big.LITTLE board when one is in the inventory:** llama.cpp splits each step's
  work evenly across its threads and waits for the slowest, so threads on little cores can hold
  back the big ones, and the AI could answer faster with `AI_THREADS` set to the big cores it has
  (two, on an RK3588) than to all six. The default stays every AI core until a measurement on such
  a board says otherwise; `benchmark_llama_cpp.sh` with `THREADS` and `taskset` measures it.
- **x86_64 (designed for, not tested, 9).** Intel's hybrid chips may report no `cpu_capacity`;
  there the P-cores (`/sys/devices/cpu_core/cpus`) rank above the E-cores
  (`/sys/devices/cpu_atom/cpus`). With SMT, a "core" is a physical core: the game and the mirror
  each get both of their core's threads (`topology/thread_siblings_list`), so the AI never shares
  a physical core with them. Both are the designer's proposal.
- **One record of the placement.** `setup.sh` decides it and writes it twice: as a user drop-in
  for each AI unit, `~/.config/systemd/user/<unit>.d/cpu-placement.conf` holding `CPUAffinity=`
  (the package can't carry it, as it is per machine), and as
  `<user root>/config/cpu-placement.json`, `{"game": [0], "mirror": [1], "ai": [2, 3]}`, which the
  engine and the mirror read. Where nothing is pinned it removes both. The engine never works the
  rule out for itself: a second copy of the rule would drift.
- **The game pins itself.** A game isn't a systemd unit (it starts from `uv run`, a menu or a
  terminal), so the engine sets its own affinity, on Linux only and only for a live run that has
  AI (the run `create_link` gives a link): `--no-ai`, `--headless`, replays, the browser and the
  pre-push measurements keep every core. `create_link` runs after `pygame.init()`, so SDL's audio
  thread already exists; the engine sets the game's cores on every thread in `/proc/self/task`,
  and threads started later inherit them. A placement naming a core this machine doesn't have (a
  disk moved to another machine, a core taken offline) is logged as a warning and the run goes on
  unpinned, never stopped.
- **The mirror pins itself to its core** when Stage 4b builds it. Started by the game, it would
  inherit core 0, so it sets its own affinity from `cpu-placement.json` before it runs a frame.
  Recorded here so Stage 4b's plan carries it.
- **One core for the whole game process.** The Python main loop, SDL's audio thread and the AI
  link's socket thread share core 0. The designer flagged audio underruns and late frames as the
  risk; the owner chose this split, and 8.3's game-beside run measures it.
- **`CPUWeight=20` stays** on the model units (the default is 100). Weights act only when two
  things want the same core at the same moment; then the AI gets about a sixth. Pinned, the game
  and the AI never share a core, so it costs nothing; unpinned (one core) it is what keeps the
  game first. The API sidecar keeps the default: it mostly waits on its sockets.
- **Not `AllowedCPUs=`.** That is the cgroup `cpuset` controller, and systemd does not hand it to
  user services: on the 16 GB Pi (systemd 259) `user@1000.service` delegates only
  `cpu memory pids`, so `AllowedCPUs=` in a user unit would be silently ignored. `CPUAffinity=` is
  an ordinary affinity mask set on the process, needs no controller, and every thread llama.cpp
  starts inherits it. `CPUWeight=` needs the `cpu` controller, which is delegated.
- **Pinning keeps the AI's computation off the game's cores, not its memory traffic or its heat.**
  On a Pi 5 the 2 MB L3 cache is shared by all four cores and one clock policy covers them all,
  so text generation, which mostly reads the model from memory, still slows the game's memory
  access, and a hot chip slows every core. The frame-time measurements in 8.3 are what show
  whether that matters.

**User units stop when their user has no session.** Lingering is off by default, so when a user's
last session ends, systemd stops their user units (seen 2026-11-18, when a logger started as a
transient user unit stopped between two SSH sessions). Harmless here: a game runs inside a session,
and a model download that `setup.sh` was doing resumes at the next login. Lingering is not turned
on.

The setup job is the one exception: `ai.glitchygames.setup.service`, `Type=oneshot`, enabled for
every user with `systemctl --global enable` by the `.deb`'s postinst. It runs `setup.sh` at each
login; when everything is in place it exits in well under a second. The postinst also starts it at
once for the user who ran `sudo` (`systemctl --user --machine="$SUDO_USER@" start ...`), so the
owner doesn't have to log out. With no `SUDO_USER` (a root login, an unattended install) it skips
that start and says so; the job then runs at that user's next login.

### 6.3 One per-user setup path: `setup.sh`

The `.pkg`'s `setup.sh.j2` already does everything a user's first run needs, with nothing from
Ansible at run time: Ansible renders it with the model pins built in (repository, revision, bytes,
SHA-256 from `ai_models`), and it downloads the models with resumable `curl` and a hash check,
generates the two keys (`openssl rand`), and renders `service.json` and each agent's settings from
templates staged in `share/agents/` with the home placeholder filled in.

On Linux the same template is used, with its platform parts made functions (5.3): `sha256sum` for
`shasum -a 256`, unit files with no placeholder (systemd's `%h` names the home) for plists that need
one, and `systemctl --user daemon-reload` for `plutil -lint`. The download source stays the pinned
Hugging Face URLs, as on a Mac; no mirror.

Ansible on Linux therefore does not write the user's config itself, as `ai_service` does on a Mac:
after installing the `.deb` it runs the installed `/opt/glitchygames/ai/bin/setup.sh` as the owner
and checks its result. One per-user path, used by Ansible and by every `.deb` install. (The Mac
keeps its current Ansible path; making the Mac use `setup.sh` too is possible later and out of
scope.)

### 6.4 The picker and memory

`select_sizes` is unchanged. Only its inputs differ:

- total: `MemTotal` from `/proc/meminfo` (the Mac: `hw.memsize`);
- free now: `MemAvailable` (the Mac: `kern.memorystatus_level` as a percentage of total);
- the overrides for tests stay `AI_MEMORY_MB`, plus `AI_AVAILABLE_MB` on both platforms, which
  replaces `AI_FREE_PERCENT` as the way to fake free memory (the Mac computes its free figure from
  the percentage, then the same comparison runs).

The tiers (`ai_service_bonsai_tiers`) and reserved figures stay shared. Linux gets its own measured
`ai_service_bonsai_reserved_mib` and `ai_service_qwen_reserved_mib` once 8.3 runs, in
`group_vars/linux.yml`; until then the Mac's figures stand, marked provisional. Memory decides, not
the machine: a 4 GB board installs the service and gets "not enough memory" at each game start, as
a small Mac does; the inventory's `ai_enabled` only spares such a host the download. 6.4.1 proposes
changing that for 8 GB machines; until the owner decides, the rule above stands.

#### 6.4.1 Open: smaller-memory machines (not decided)

Raised by the owner, 2026-11-18: what could run on machines with less memory, for speed and
features. Not part of this branch's build until the owner decides.

**The context's memory is what's too big, not the model.** Of the 2B's 4,816 MiB reserved on the
Mac, the weights are 0.55 GB (`Ternary-Bonsai-2-2B-Q2_0.gguf`) and the vision projector 0.36 GB;
most of the rest is the KV cache and compute buffers for the 262,144-token context. Bonsai 2 2B
keeps Qwen3.5-2B's hybrid attention (18 linear-attention and 6 full-attention layers, its card),
and only the 6 full-attention layers keep a per-token cache, so the cache scales with the context.
The designer's estimate is about 0.4 GB at 32K; the real per-token figure comes from the server
log in 8.3 (step 5). On the Pi (8.1), Bonsai held 4,154 MiB at load, so roughly 3.2 GB beyond the
weights and projector at 262K, which agrees with the estimate's scale.

**Tiers by total memory, chosen by the same picker as the sizes**, all at the q8_0 cache of 6.5
(KV cache from the models' configs: Bonsai 6.4 KiB a token at q8_0, Qwen 59.5 KiB; the rest from
the 2026-11-18 Pi measurements):

| Memory | Bonsai context | Qwen | Prompt cache cap | KV cache, both | Models in use | Status |
|---|---|---|---|---|---|---|
| 16 GB and up | 131,072 | 8,192 | 4,096 MiB | 1,292 MiB | about 3.9 GB | the owner, 2026-11-18 |
| 8 GB | 32,768 | 8,192 | about 1,024 MiB | 680 MiB | about 3.3 GB | proposed |
| 4 GB | 32,768 | none | about 512 MiB | 204 MiB | about 1.6 GB | the owner, 2026-11-18 |
| 2 GB, 1 GB | nothing | nothing | | | | Bonsai alone holds 1.3 GB at load |

- **4 GB: Bonsai alone (the owner, 2026-11-18).** No embedding model on these machines: the
  picker's "Bonsai only" becomes a result in its own right, `setup.sh` downloads no Qwen, the API
  reports ready with only a reasoning model when the tier has no embedding model (today
  `/health/ready` wants both, `app.py`), and `/v1/embeddings` answers with a clear "this machine has
  no embedding model" error. Nothing in the engine embeds today (only the sprite catalog exports
  text for it), so games lose nothing yet.
- **The game's reserve decides whether the small tiers fit.** `ai_service_game_reserve_mib` (2,048)
  predates any measurement; Bitmappy idles at about 262 MiB on the Pi (2026-11-18, with its `uv`
  wrapper). With 2,048 the 4 GB tier needs about 3.6 GB free against about 2.8 GB on a 4 GB Pi
  with a desktop, so it would never start. Open: measure every game's peak memory and set the
  reserve from it.
- **Pi 4 (Cortex-A72, no dot product, `armv8.0_1`):** unmeasured; the designer estimates 2.5-3.5
  tokens a second for answers, 40-70 s for a short question. The inventory's 4 GB Pi 4 runs the
  same benchmark (`BONSAI_CONTEXT=32768`).

**Qwen keeps 8,192 on every machine (the owner, 2026-11-18).** Qwen's context is the longest text
one embedding request takes, not a history: it reads each text in one pass, and a longer one is
refused. A smaller Qwen would save about 800 MiB, but an 8 GB machine would then refuse texts a
16 GB one accepts. Only Bonsai's context shrinks per tier.

- Kept: vision, reasoning, the same answers, and embeddings comparable with every other host's
  (another embedding model's vectors can't be compared with Qwen's).
- Lost: context length. Prism's card says reasoning can use 3,000+ tokens and asks for at least
  8,192 output tokens with thinking on, so 32K leaves room and 4K would not.
- Also owed on 8 GB: `ai_service_bonsai_cache_ram_mib` (4,096) comes down, to about 1,024 (still
  dozens of saved 32K prompts at q8_0): a full 4 GB prompt cache would push an 8 GB machine into
  swap. Whether the reserved figure includes a full prompt cache is checked first.
- The reserved figures become per context tier, not only per model size.

**Smaller models, only if the measured speed asks for one** (sizes from the Hugging Face files,
2026-11-18):

| Model | Weights + vision | For | Against |
|---|---|---|---|
| Qwen3.5-0.8B (`ggml-org/Qwen3.5-0.8B-GGUF`) | 0.56 GB at Q4_0, plus its vision | Bonsai 2's own base family and chat template: nearly a drop-in; vision and thinking | Decode on the Pi is bound by bytes read per token, about the same as the ternary 2B's, so likely no faster |
| LFM2.5-VL-450M (`LiquidAI/LFM2.5-VL-450M-GGUF`) | 0.22 GB + 0.10 GB | Built for the edge; about a third of the bytes per token, so the likely speed win; a 4 GB board fits | LFM Open License, not Apache (a commercial revenue cap): the owner's call; thinking and answer quality unmeasured |
| LFM2.5-VL-1.6B | 0.70 GB + 0.58 GB | Middle ground | Same license; bytes per token like Bonsai's |
| Bonsai 2B as `PTQ1_0` | 0.43 GB | The same weights, smaller | Upstream llama.cpp rejects the type; only Prism's fork runs it |
| EmbeddingGemma 300M | about 0.2-0.3 GB | Half the embedder | Vectors incompatible with Qwen's; Gemma terms; trimming Qwen's context saves more |

**Designer's recommendation:** context tiers first, no new model. Try LFM2.5-VL-450M with the same
benchmark only if Bonsai 2B on two threads is too slow (8.3's go/no-go), or for 4 GB boards.

### 6.5 llama.cpp

`ansible/roles/llama_cpp/tasks/` has only `main.yml` today, Mac-specific from its first task (the
Apple Silicon refusal, the Xcode SDK, the Metal and Homebrew checks). It is split first, with no
change in behaviour on the Mac: `main.yml` keeps the shared steps (clone, pinned-commit check,
option hashing, build, install) and includes `macos.yml` or `linux.yml` for the platform steps
(refusals, SDK or `cmake` package, extra options, the binary's checks).

- **One build per architecture, choosing the CPU variant at run time:** the base options plus
  `GGML_NATIVE=OFF`, `GGML_BACKEND_DL=ON`, `GGML_CPU_ALL_VARIANTS=ON`, `BUILD_SHARED_LIBS=ON`,
  `GGML_VULKAN=OFF`, `GGML_OPENMP=OFF`, identical on ARM and x86_64. llama.cpp then builds every
  variant section 4 lists for the host's architecture, each a shared library, and `llama-server`
  loads the best one the CPU supports when it starts. No machine is refused for its CPU. The
  trade-offs, accepted: the libraries are shared, not one static binary as on the Mac, so they live
  in the runtime's `lib/` with an `$ORIGIN`-relative RPATH; the build takes several times longer;
  the package is bigger by a few megabytes per variant. At `b12167`, `GGML_BACKEND_DL` requires
  `BUILD_SHARED_LIBS` and `GGML_CPU_ALL_VARIANTS` refuses `GGML_CPU_ARM_ARCH`, both checked by
  CMake. The Mac keeps its static Metal build: Apple Silicon is one CPU family.
- **Which variant ran is recorded:** `llama-server` logs the library it loaded
  (`load_backend: loaded CPU backend from .../libggml-cpu-<variant>.so`). `ai_validate` and the
  benchmark report it, so a machine running a weaker variant than it should is noticed.
- **OpenMP off:** one fewer runtime library for the `.deb` to depend on (llama.cpp falls back to its
  own thread pool); the builder checks with the benchmark that it costs nothing measurable, and turns
  it back on with a `libgomp1` dependency if it does.
- **Build directory emptied before every build** (section 10.1).
- **The binary's checks** after install, replacing the Mac's Metal and Homebrew checks: `ldd` on
  `llama-server` and every library beside it lists only glibc, libstdc++, libgcc, libm and the
  runtime's own `lib/` (no Vulkan, no OpenSSL, no `/usr/local`); the highest `GLIBC_` symbol version
  they need is recorded and becomes the `.deb`'s `libc6 (>= ...)`; every variant for the
  architecture is present; `llama-server --version` runs and names a variant this CPU supports.
- **Threads:** `--threads` becomes an agent setting (`AI_THREADS`), empty on a Mac (llama.cpp's
  default; Metal does the work there). On Linux it is the CPU count less two, at least one,
  written by `setup.sh` from `nproc` on the machine itself (2 on a Pi 5, 14 on a 16-core desktop),
  and **the same count for both model servers**, which share the cores pinned for them (6.2):
  one server per core count would give Bonsai and Qwen 3 threads each on a four-core Pi, six
  threads competing with the game when both are busy. The two cores left are the game's and the
  mirror's (6.2). 8.3 measures 1 to 4 threads on the Pi.
- **Page size:** the build runs on whatever page size the build host uses; validation runs the
  result on a 4K-page kernel too (8.3).
- **KV cache: 8-bit for every model on every system, the Mac included (the owner, 2026-11-18).** The
  owner's llama-bench comparison on the Pi (Bonsai 2B, two threads, one repetition each, with
  Bitmappy running idle beside it on purpose, to keep a game in the picture, neither pinned;
  llama-bench names it `qwen35 2B Q2_0`, its architecture):

  | Test | f16 | q8_0 | q4_0 |
  |---|---|---|---|
  | pp512 | 10.95 tok/s | 10.61 (-3%) | 10.74 (-2%) |
  | tg128 | 5.92 | 5.74 (-3%) | 5.85 (-1%) |
  | pp512 @ d4096 | 9.75 | 7.77 (-20%) | 8.45 (-13%) |
  | tg128 @ d4096 | 4.09 | 4.59 (+12%) | 5.17 (+26%) |

  - A 4,096-token cache slows f16's answer writing by 31%, far more than reading a cache of about
    50 MB beside 520 MB of weights explains: the attention arithmetic is the cost, and it shrinks
    with the type (the designer's reading, unconfirmed in llama.cpp's code: the quantized types
    can use the A76's integer dot product). The gain should grow with depth.
  - Prompt reading at depth is fastest at f16; q8_0 measuring slower than q4_0 has no ready
    explanation, so that row waits for three repetitions under the same load (8.3 step 5).
  - q4_0 is fastest and smallest; its open question is quality (keys are known to lose precision
    at 4 bits), which the three short questions can't show. K q8_0 with V q4_0 is the middle
    option, unmeasured. A long-context recall check is what would decide between them.

  New shared settings, `ai_service_cache_type_k` and `ai_service_cache_type_v`, both `q8_0`,
  written to every model agent's settings (`AI_CACHE_TYPE_K`, `AI_CACHE_TYPE_V`), Bonsai's and
  Qwen's, and passed as `--cache-type-k` and `--cache-type-v`.
  - A quantized V cache needs flash attention: llama.cpp refuses to load otherwise
    (`src/llama-context.cpp:4340` at b12167, "quantized V cache requires flash_attn"). Bonsai's
    agent already passes `--flash-attn on`; Qwen's adds it, rather than trusting the `auto`
    default.
  - Qwen's vectors with a q8_0 cache differ slightly from f16's. Every host makes them the same
    way, so they stay comparable with each other; nothing stores vectors yet, so nothing made at
    f16 needs remaking. Not measured: how far they move from f16's, and Qwen's speed.
  - Every reserved figure (`ai_service_bonsai_reserved_mib` for all four sizes,
    `ai_service_qwen_reserved_mib`) was measured with an f16 cache, so it overstates memory now:
    the Mac's are measured again with `--tags ai_validate`, and Linux's come from a q8_0 run
    (8.3). Smaller figures can let a size fit on a machine where it didn't, so the tiers are
    checked against the new figures too.
  - Not yet measured: the three answers and the embeddings with a q8_0 cache (8.3 step 5), and
    q8_0's speed on Metal.
  - What it saves, from the models' configs (Qwen3.5-2B: 6 full-attention layers, 2 KV heads of
    256; Qwen3-Embedding-0.6B: 28 layers, 8 KV heads of 128; q8_0 stores 34 bytes per 32 values,
    0.53 of f16):

    | | Per token, f16 | Context | KV cache, f16 | KV cache, q8_0 | Saved |
    |---|---|---|---|---|---|
    | Bonsai 2B | 12 KiB | 262,144 (before) | 3,072 MiB | 1,632 MiB | 1,440 MiB |
    | Bonsai 2B | 12 KiB | 131,072 (now) | 1,536 MiB | 816 MiB | 720 MiB |
    | Qwen 0.6B | 112 KiB | 8,192 | 896 MiB | 476 MiB | 420 MiB |
- **Context: 128K for Bonsai on every system (the owner, 2026-11-18).**
  `ai_service_bonsai_context_size` goes from 262,144, the model's whole context (the owner's
  choice on 2026-11-06), to 131,072. With the q8_0 cache that halves Bonsai's KV cache again, to
  816 MiB. A request then ends when the model finishes, the context fills or it times out, as
  before; 128K still leaves Prism's 8,192 output tokens for reasoning many times over. The
  defaults file's comment on the context names this decision. Bonsai's estimated footprint on
  the Pi, from the 2026-11-18 measurements less the calculated cache savings:

  | | f16, 262K (measured) | q8_0, 262K | q8_0, 128K (the default) | q8_0, 32K (6.4.1's tier) |
  |---|---|---|---|---|
  | Bonsai at load | 4,154 MiB | about 2,714 | about 1,898 | about 1,286 |
  | Bonsai after three questions | 4,503 MiB | about 3,063 | about 2,247 | about 1,635 |
  | Qwen | 2,105 MiB | about 1,685 | about 1,685 | about 1,685 (8,192) |
  | Both, after the questions | 6,608 MiB | about 4,748 | about 3,932 | about 3,320 |

  `--cache-ram 4096` can add up to 4 GB of saved prompts over a long session on top of these. The
  reserved figures are measured again at 128K and q8_0 (8.3, and `ai_validate` on the Mac).
- **`ai_validate` runs what the service runs.** Its argument lists are a second copy of
  `run-llama-server.sh`'s, and they have drifted: validation omits `--chat-template-kwargs`
  (`reasoning_effort: medium`), so it never checked the reasoning setting the service uses (found
  2026-11-18). Both lists come from one place, or a test fails when they differ (7).

### 6.6 The sidecar Python

`ai_sidecar_python_build` becomes per platform and architecture (section 4 for Linux;
`cpython-<version>-macos-aarch64-none` on a Mac), installed through uv's python-build-standalone as
today. Its "uses nothing outside itself" check becomes per platform too (`otool -L` on a Mac, `ldd`
on Linux). The service's own code (`services/ai-service`) needs no change: it already reads every
path from `service.json`.

### 6.7 The .deb

A new task file in `ansible/roles/ai_package`, beside the `.pkg`'s, sharing the staging tasks (they
are platform-free except the launchd plists, which become a per-platform "stage the agents" step:
plists on a Mac, unit files on Linux).

- **Name, version, architecture:** `glitchygames-ai`, `ai_package_version` (shared with the `.pkg`),
  the host's `.deb` architecture (section 4).
- **Built with** `dpkg-deb --root-owner-group --build` from the stage, into
  `{{ ai_cache_root }}/package/glitchygames-ai_<version>_<architecture>.deb`. Rebuilt only when
  something staged changed, as the `.pkg` is.
- **Depends:** `libc6 (>= <recorded GLIBC version>)`, `libstdc++6`, `libgcc-s1`, `systemd`, `curl`,
  `openssl`, `ca-certificates`, `coreutils`. Checked against the binaries' `ldd` output.
- **Maintainer scripts:** `postinst` enables and starts the setup job (6.2); `prerm` stops every
  running `ai.glitchygames.*` user unit for every logged-in user; `postrm purge` removes nothing in
  homes (Debian convention). `/opt/glitchygames/ai/bin/uninstall-user.sh` removes one user's data
  when they ask.
- **Contents check** (as the `.pkg`'s "holds the server and its notices, and no model"):
  `dpkg-deb --contents` lists `llama-server`, every CPU variant for the architecture, the sidecar,
  the licenses and every unit file, and no `.gguf`.
- **Where it runs:** the architecture and distribution release that built it, or a newer release.
  A `.deb` built on Ubuntu 26.04 won't install on Debian 13 (older glibc); the `libc6` dependency
  and the architecture field make `apt` refuse it clearly. Building for every distribution at once
  (on the oldest glibc) is the players' release, not this.

### 6.8 The engine (`ai_link.py`, `ai/local_service.py`, `ai_console.py`)

Today one `install_root` holds both the control script and the user's files, and two modules each
work out `bin/ai-service.sh` and `config/service-api-key` from it: `ai_link.py` (lines 100-101) and
`ai/local_service.py` (lines 215-216), which also keeps its own copy of `EXIT_NOT_ENOUGH_MEMORY`.
That becomes one place:

- A frozen pydantic model `ServiceLocations` in `ai_link.py` with `program_root`, `user_root` and
  the derived `control_script`, `key_file`, `history_directory`, built by one function
  `service_locations()`. `ai/local_service.py`, `ai_console.py` and `ai_host.py` take a
  `ServiceLocations` instead of an `install_root`, and import the exit codes from `ai_link.py`
  instead of copying them.
- `program_root`: `~/Library/Application Support/GlitchyGames/AI` on macOS, `/opt/glitchygames/ai`
  on Linux. Holds `bin/ai-service.sh`.
- `user_root`: the same folder on macOS, `<data home>/glitchygames/ai` on Linux, where the data home
  comes from the platform logic `state/paths.py` already has for saves (macOS `Application Support`,
  Linux `$XDG_DATA_HOME` or `~/.local/share`). That logic is lifted into a `platform_data_home()`
  both use, because `get_save_directory` only takes `[a-z0-9_-]+` names and the service's folder is
  two levels deep (`glitchygames/ai`).

`GLITCHYGAMES_AI_INSTALL_ROOT` keeps meaning "both", so the test harness keeps pointing it nowhere;
`GLITCHYGAMES_AI_PROGRAM_ROOT` and `GLITCHYGAMES_AI_USER_ROOT` override one each. Another platform
(Windows, a browser) gets no default and no link, as a missing service does today. No new exit code
or link state is needed: every CPU can run the service (6.5). The message "Install it with
ansible/macos_ai_service.yml or its package" (`ai/local_service.py` line 220) names the renamed
playbook. Nothing here depends on the architecture.

### 6.9 Ansible: playbook, inventory, validation, uninstall

- **Playbook:** `ansible/macos_ai_service.yml` is renamed `ansible/ai_service.yml`, with one service
  play for `macos:&ai_enabled` and one for `linux:&ai_enabled`, sharing the roles. Every `.md` and
  test naming the old path is updated in the same change (CLAUDE.md, the master plan, docs,
  `tests/test_ansible_macos_ai_service.py`).
- **Root:** the Linux play sets `become: false` and raises it per task (apt, dpkg, the postinst's
  systemctl), run with `-K` (`--ask-become-pass`) as `raspberry_pi_runner.yml` already is. No
  passwordless sudo is added.
- **Build host:** each `ai_enabled` Linux host builds its own llama.cpp, sidecar and `.deb` and
  installs that, as each Mac builds its own `.pkg`. A `.deb` therefore always matches its host's
  architecture and distribution release.
- **Inventory:** a new `linux` group holds every Linux host (no such group exists today). Every
  `linux` host states an explicit `host_memory_gb`, and those with 16 or more set
  `ai_enabled: true` for themselves. Nothing in the AI roles tests for a board or a CPU model; only
  `ansible_facts['architecture']`, and only for the values in section 4.
- **`ai_validate`:** a `linux.yml` beside `macos.yml`: each model in its own temporary server, its
  answers, its resident memory, the threads used and the CPU variant loaded, instead of Metal's
  evidence.
- **`ai_service` smoke test:** unchanged in what it asks; it already starts through
  `ai-service.sh`.
- **`ai_uninstall`:** on Linux `apt remove glitchygames-ai`, then `uninstall-user.sh` for the owner.

## 7. Tests, named as behaviours

In `tests/test_ansible_macos_ai_service.py`, renamed with the playbook to
`tests/test_ansible_ai_service.py` (the same subject, every platform):

- The picker, run as rendered for Linux with faked memory: 16 GB total with 9 GB available picks 2B
  and 0.6B; 16 GB with 6 GB available exits 3 ("nothing-fits"); 8 GB exits 3; a hand-picked size
  that doesn't fit still gets nothing. The same table runs against the macOS rendering, so the two
  can't drift.
- Both renderings of every shell template pass `sh -n` and shellcheck.
- Every agent's unit has no `[Install]` section; only the setup unit is enabled; every unit listens
  on loopback through the shared ports table.
- The model units carry `CPUWeight=20` and no unit carries `AllowedCPUs=` (6.2 says why, so
  nobody swaps in the cgroup version and silently loses the pinning); `setup.sh` follows 6.2's
  table, big.LITTLE rows included: for each row, every AI unit's drop-in, `AI_THREADS` and
  `cpu-placement.json`, with the game and the mirror always on the two highest capacities; for one
  core, no drop-in and no placement file, and an earlier one removed.
- Both model agents' settings carry `AI_CACHE_TYPE_K=q8_0` and `AI_CACHE_TYPE_V=q8_0` on both
  platforms and `run-llama-server.sh` passes them, each with `--flash-attn on`.
- `ai_validate`'s arguments for each role equal what `run-llama-server.sh` passes for it (the drift
  6.5 found), checked by rendering both.
- A live run with AI on Linux sets the game's cores on every thread it has; a run with `--no-ai`,
  `--headless` or a replay, a Mac, or a missing placement file sets nothing; a placement naming a
  core the machine lacks logs a warning and the run plays on unpinned.
- The Linux llama.cpp options turn on runtime-loaded backends and every CPU variant, and turn off
  native tuning, Vulkan and OpenMP; no option names a CPU; the options are the same for both
  architectures.
- **Every architecture-dependent value has an x86_64 value:** rendering the Linux roles with
  `architecture: x86_64` facts gives the `amd64` `.deb` name, the `linux-x86_64-gnu` sidecar build
  and the x86_64 variant list, and `aarch64` facts give the ARM ones. This is all x86_64 gets until
  section 9 is built.
- The build directory is emptied before configure (10.1).
- The `.deb`'s control file depends on what its binaries link, and its contents hold every CPU
  variant for its architecture and no model.
- The inventory: every `linux` host states `host_memory_gb`, and a host has `ai_enabled: true`
  exactly when that is 16 or more (replaces
  `test_the_ai_service_is_on_by_default_and_off_on_the_raspberry_pis`; the owner's 2026-11-17
  decision changes that spec). The play test checks a `macos` and a `linux` service play, each
  `&ai_enabled`.
- The rendered `setup.sh` for Linux carries every pinned model's revision and SHA-256 from
  `ai_models`, as the Mac's does.

Every existing test in the Mac file is kept, adjusted only for the renamed playbook and the split
roots; none is deleted.

In the engine's tests (`tests/test_ai_link.py`, `tests/test_ai_console.py`, and the tests of
`ai/local_service.py` and `state/paths.py` where they live now):

- `service_locations()` defaults per platform and follows each override; the old variable still sets
  both roots.
- A missing control script, a missing key, or an unsupported platform gives no link and no local
  service client.
- The link, the local service client and the console agree on every path, because they read one
  `ServiceLocations` (an invariant test: build each from the same locations and compare).
- `platform_data_home()` gives what `get_save_directory` gave before, for every platform.

Package tests, in an arm64 Linux container on the Mac (Docker runs arm64 natively on Apple
Silicon), as a nox session the builder adds: install the `.deb` built on the Pi into a container of
the same release, check `llama-server --version` names a variant, the sidecar imports the service,
`dpkg -r` leaves nothing in `/opt` or `/usr/lib/systemd/user`, and `apt` refuses it on an older
release. No x86_64 container: emulation is slow, and x86_64 isn't tested yet (section 2).

## 8. Raspberry Pi

What only the Pis add. The rest of this document applies to them unchanged.

### 8.1 What was measured (the 2026-11-17 spike)

Scripts: `scripts/raspberry_pi_llama_cpp/` (`build_llama_cpp.sh`, `benchmark_llama_cpp.sh`,
`summarize_llama_cpp_results.py`), kept as the validation tools for 8.3.

- **CPU:** the Pi 5's Cortex-A76 has dot product (`asimddp`) and fp16 arithmetic, no i8mm, no SVE:
  the build's own detection, `-mcpu=cortex-a76+crc+crypto+dotprod+noi8mm+nosve+nosme`. A native
  CPU build of `b12167` took 496 s with two jobs. The Pi 4's A72 has no dot product.
- **Vulkan: ruled out.** `V3D 7.1.10.2 (V3DV Mesa)` reports `shared memory: 16384 | fp16: 0 |
  int dot: 0 | matrix cores: none`. llama.cpp refuses the device ("Shared memory size too small for
  matrix multiplication", `ggml-vulkan.cpp` line 1904): its smallest matrix-multiply tile needs more
  than 16 KB for some type, and it checks every type. Bonsai (Q2_0) and Qwen (Q8_0) both fail to
  load. Patching the check would leave a GPU with no fp16, no integer dot product and 16 KB of
  shared memory, which is unlikely to beat four A76 cores; not worth a fork. The Pi's second DRM
  device (`vc4-drm`, `bcm2712-vc6`) is the display controller and has no shader cores.
- **A power cut mid-build left zero-byte object files** newer than their sources; the next build
  trusted them and failed to link (`undefined reference to ggml_abort`). The script now empties its
  build directory first; the Ansible role gets the same fix (10.1).
- **Measured 2026-11-18, on the 27 W supply** (`benchmark_llama_cpp.sh`, results
  `~/ai-spike/results/20261118-190605` with `THREADS=1,2,3,4`, and `20261118-192923` with
  `THREADS=2 taskset -c 2,3`):

  | Threads | Bonsai 2B prompt (pp512) | Bonsai 2B decode (tg128) | Qwen 0.6B prompt (pp512) |
  |---|---|---|---|
  | 1 | 6.2 tok/s | 4.3 tok/s | 65 tok/s |
  | 2 | 12.0 | 7.5 | 121 |
  | 2, pinned to cores 2-3 | 11.8 | 7.5 | 116 |
  | 3 | 15.2 ± 1.9 | 5.5 ± 1.8 | 158 |
  | 4 | 18.7 ± 2.3 | 7.0 ± 2.5 | 186 |

  - Decode peaks at two threads: three and four are no faster and vary run to run (memory
    bandwidth and heat). Prompt speed keeps rising with threads. This supports cores minus two
    (6.5).
  - Pinning costs nothing measurable: two pinned threads equal two unpinned. The run with a game
    beside it (8.3 step 2) is still owed.
  - All three answers right (391, Canberra, the image's colours) at both thread counts; the server
    decoded at 7.0-7.5 tok/s on two threads (8.4 on four), 103-188 reasoning tokens per answer, so
    about 15-25 seconds per short question. Prompts are read at about 12 tok/s on two threads: a
    1,000-token prompt takes about 80 seconds before the first token unless the prompt cache holds
    it.
  - Embeddings ordered (apple~apple 0.843, apple~locomotive 0.442), 1,024 dimensions.
  - Resident memory at the Mac's flags (262K context): Bonsai 4,154 MiB loaded, 4,503 MiB after
    three questions; Qwen 2,105 MiB; both loaded left 7,190 MiB available of 16,179. The Mac's
    reserved figures (4,816 and 1,884) are close; Qwen's is 221 MiB low on Linux.
  - The KV cache and compute buffer sizes are not in the logs at llama-server's default
    verbosity; 8.3 step 5 needs the benchmark to raise it.
  - Power: no kernel voltage messages, supply never below 5.036 V, throttle bit 19 ("soft
    temperature limit has occurred") at up to 82.6 C during four-thread runs, with the clock
    dipping to 2,200-2,900 MHz. The pwm fan was running. Two-thread runs peaked at 69.4 C.
  - Bitmappy ran idle beside the runs, on purpose (the owner, 2026-11-18: a mixed load, to see the
    AI with a game running), unpinned; load average about 1.9 before the second run. Idle, it used
    about 60% of one core, which matters for the game-on-one-core placement (6.2) and is not yet
    explained.
- **Not measured yet:** the game's frame times beside the models, and the 32K-context memory
  (6.4.1).

### 8.2 Pi-specific facts the design relies on

- **Which Pis:** the 16 GB Pi 5s set `ai_enabled: true`. The 8 GB Pi 5 and the 4 GB Pi 4 don't;
  the picker would refuse them anyway. First host: the 16 GB Ubuntu 26.04 Pi 5; the 16 GB Raspberry
  Pi OS 13 Pi when it is in this branch's inventory (it is only on another branch today). The
  `raspberry_pis` group keeps `ai_enabled: false`; each 16 GB Pi turns it on for itself.
- **Distributions:** Ubuntu 26.04, Ubuntu 26.10 and Raspberry Pi OS 13 (Debian 13). Each Pi builds
  its own `.deb` (6.9), so differing glibc versions don't matter now.
- **Page size:** the 16 GB Ubuntu Pi runs a 16K-page kernel (`7.0.0-999-raspi`), and a 64K-page
  kernel was being built on it.
- **Power:** the overclocked 16 GB Ubuntu Pi (3.0 GHz, `over_voltage=6`) logged an under-voltage
  (2026-11-17 23:27:53) with one four-job build running, reset (`get_rsts=1000`) with two builds at
  once, and went down at the start of the CPU benchmark (2026-11-18), coming back without network.
  Inference is sustained all-core load, so validation waits for the supply or the overclock to be
  fixed (the owner's call).
- **The cores** (read 2026-11-18 with `lscpu` and sysfs): four identical Cortex-A76 (part
  `0xd0b`, `cpu_capacity` 1024 each, one thread per core, one cluster), each with its own 64 KB L1
  data, 64 KB L1 instruction and 512 KB L2, sharing one 2 MB L3; one cpufreq policy (`policy0`)
  covers all four, 1.5 to 3.0 GHz under `ondemand`. So the Pi pins: llama.cpp on cores 2 and 3
  with 2 threads, the game and the mirror free on 0 and 1 (6.2, 6.5).
- **No useful GPU:** the game presents through V3D and both the game and inference run on the
  CPU.
- **`raspberry_pi_runner.yml`:** keeps only what the runners themselves need. The spike's
  additions move: `cmake` into the Linux `llama_cpp` task file; the Vulkan packages, the `render`
  group and the V3DV check are removed (Vulkan is ruled out).

### 8.3 Validation on the Pi (after the power fix)

Using `scripts/raspberry_pi_llama_cpp/`, on the 16 GB Pi 5 once it holds all-core load without
under-voltage (`vcgencmd get_throttled` stays `0x0` through a full benchmark, and the kernel logs no
"Undervoltage detected"):

1. `benchmark_llama_cpp.sh ~/ai-spike cpu`: prompt and decode speed for both models, the three
   answers right, the embeddings ordered, the resident memory at the full context, the CPU variant
   loaded (expected `armv8.2_2`).
2. `THREADS=1,2,3,4` for raw speed per core count (done, 8.1); then the owner's placement: the
   models on cores 2-3 (`taskset -c 2,3`), a game on the real display on core 0, and an uncapped
   headless replay of a golden trace standing in for the mirror on core 1, recording the game's
   p50/p95/p99 frame times and any audio underruns against `--no-ai` (the Stage 5 harness, once
   it exists; a stopwatch comparison until then). Until the engine pins itself, `taskset -c 0`
   runs the game there.
3. The measured memory replaces the provisional Linux reserved figures (6.4).
4. On a 4K-page kernel too, if the Pi can boot one.
5. With the Bonsai cache at q8_0 (6.5) for the service's figures, and at f16 for comparison: the
   three answers right, and for 6.4.1 the KV cache, recurrent state and compute buffer sizes (the benchmark now runs the
   servers at `--log-verbosity 4` and prints them) at the full context, then
   `BONSAI_CONTEXT=32768 QWEN_CONTEXT=2048` for the 8 GB tier's reserved figures, and
   `CACHE_TYPE_K=f16,q8_0,q4_0 DEPTHS=0,4096` for what a quantized KV cache saves and costs:
   decode speed with an empty and a 4,096-token cache, prompt speed, and the three answers (the
   servers run with the last type listed). The designer's expectation, unmeasured: f16 fastest
   at short lengths (the A76 has half-precision arithmetic), q8_0 ahead once the cache is deep,
   bf16 slow (no bf16 instructions before Armv8.6). A quantized cache would be a new setting on every host, so it is the
   owner's call, not part of the tiers by default.

**The go/no-go:** if Bonsai 2B's decode on the Pi is too slow for the console to be usable (the
owner sets the bar once the numbers exist), the design still ships the service and the `.deb`, and
the Pi's default becomes embeddings plus reasoning on request rather than at every game start. That
fallback is the designer's proposal, not decided.

### 8.4 Sharing a Pi with the pre-push measurements and CI

The 16 GB Ubuntu Pi is also a CircleCI runner and a machine the pre-push hook measures replays on.
With the models loaded (about 6.7 GB and most cores), a replay measured beside them gives wrong
timings, and CI's test memory guard (1750 MiB) has less room.

- **Measurements stop the AI first** (the owner, 2026-11-18). In `measure_script`
  (`scripts/measure_on_raspberry_pi.py`), once the exclusive `flock` is held and before the
  measurement runs, the script runs `/opt/glitchygames/ai/bin/ai-service.sh stop` when that file
  exists, and logs that it did. It runs as the same user the models run as (the SSH user). A game
  that was using them sees its connection drop and plays on with AI unavailable for the rest of that
  run (rule 3 in `ai_link.py`: starting is one attempt). Nothing restarts the models after the
  measurement; the next game start does.
- **CI jobs:** nothing now. No workflow runs the Pi jobs yet (`raspberry_pi_runner.yml`'s header);
  when one does, the same stop belongs at the start of that job. Recorded in plans/future-work.md
  when this is built.
- **Not covered:** a game started on the Pi *during* a measurement would start the models again.
  Accepted: it needs someone playing on the Pi while pushing from another machine.

Test, in `tests/test_measure_on_raspberry_pi.py`: the rendered script runs the stop after taking the
lock and before the measurement command, and only when the control script exists.

## 9. x86_64

Designed for, not tested (the owner, 2026-11-18).

### 9.1 What is ready

Every architecture-dependent value has its x86_64 entry (section 4): the `amd64` `.deb`, the
`linux-x86_64-gnu` sidecar build, and llama.cpp's 14 x86 CPU variants from the same build options.
The static tests (section 7) render the Linux roles with x86_64 facts. Nothing else in the design
changes for x86_64.

### 9.2 What it takes to call it supported

1. An x86_64 Linux host in the inventory, in the `linux` group with its `host_memory_gb`.
2. The Ansible run, the `.deb`'s package tests and an 8.3-style validation on it (speed, answers,
   memory, the variant loaded, the game's frame times).
3. Its own measured reserved-memory figures if they differ from ARM's.
4. A check of Bonsai's known issue on AVX-512 CPUs: Prism's `KNOWN_ISSUES.md` reports a crash on
   load for the `PQ2_0` files on AVX-512 machines. The service uses `Q2_0`, which the report doesn't
   name, but the `skylakex` and later variants are exactly the code that would hit it.
5. **Then the GPU**, the main way x86_64 differs: desktop GPUs run llama.cpp well through Vulkan,
   CUDA or ROCm. With runtime-loaded backends (6.5) a GPU backend is one more library that loads only
   when its device works, so the CPU path stays as is. Its own design: which backends, how the picker
   counts GPU memory, and how the game and the AI share the GPU.

## 10. Fixes found on the way, done in this branch

1. **A build interrupted by a power cut poisons later builds.** `ansible/roles/llama_cpp` reuses its
   build directory whenever the binary isn't installed, so zero-byte objects from a cut-off build are
   trusted next time; on the Mac too. Fix: remove the build directory before configuring, on both
   platforms. Test gap: nothing checks that a build starts clean. Regression test: the role's task
   list empties the build directory before its configure step. Sibling sweep: every other place that
   builds into a reused directory (`ai_sidecar` already starts from nothing; check `scripts/`
   builds).
2. **The spike's wait loop matched its own command line** (`pgrep -f "build_llama_cpp.sh cpu"`
   inside an SSH command that contains the same text). Throwaway, gone; recorded so the validation
   scripts use the `[b]uild` pattern trick or a PID file.
3. **The embedding comment that names splitting nobody does.** `ai_service/defaults/main.yml` says
   of Qwen's context "Records are split up before embedding, so one batch is all this needs" (since
   #157), but neither the sidecar nor the engine splits anything: `/v1/embeddings` passes the text
   straight to llama.cpp, which refuses one longer than 8,192 tokens. The comment is corrected to
   say the caller keeps each text under the context; splitting, if wanted, is its own feature
   (`plans/future-work.md`). Found 2026-11-18.

## 11. Left to the builder

- Unit file details beyond those named (environment loading, `TimeoutStartSec` for a slow model
  load, journald versus the log file).
- How `prerm` reaches every logged-in user's units.
- The nox session's name and its container images.
- Where the CPU variants' libraries sit inside the runtime folder, and the RPATH that finds them.

## 12. Decisions, and who made them

| Decision | Made by |
|---|---|
| 16 GB Pi 5s get the service; 2B and 0.6B, as on a Mac | The owner, 2026-11-17 |
| A `.deb` like the `.pkg` | The owner, 2026-11-17 |
| A branch of its own, `feature/ai-service-raspberry-pi` | The owner, 2026-11-17 |
| The Vulkan and CPU builds measured separately | The owner, 2026-11-17 |
| CPU only on the Pi; Vulkan ruled out | Measured, 2026-11-17 (8.1) |
| Any 64-bit ARM Linux machine is a target; the Pi 5 is the first tested (2) | The owner, 2026-11-18 |
| One Linux document, architecture-neutral, with Raspberry Pi and x86_64 sections | The owner, 2026-11-18 |
| x86_64 designed for, not tested yet (2, 9) | The owner, 2026-11-18 |
| Lowercase Linux paths: `/opt/glitchygames/ai` and `~/.local/share/glitchygames/ai` with its XDG siblings; the Mac keeps `GlitchyGames/AI` (6.1) | The owner, 2026-11-18 |
| Pre-push measurements stop the AI models after taking their lock; CI jobs later do the same (8.4) | The owner, 2026-11-18 |
| One Linux layout: Ansible installs the `.deb` it builds (5.1 A) | The owner, 2026-11-18 |
| One llama.cpp build per architecture with every CPU variant, chosen at run time; no CPU refused (6.5) | Designer's call, from the owner's goals |
| systemd user units, none at login except setup (6.2) | Designer's call, following the master plan's rule |
| `setup.sh` is the one per-user path on Linux, Ansible included (6.3) | Designer's call |
| Threads: the CPU count less two, at least one, shared by both model servers (6.5) | The owner, 2026-11-18 |
| The game on core 0, the mirror on core 1, every AI unit on the rest (the Pi 5: 2-3), with `CPUAffinity=`, not `AllowedCPUs=` (6.2). Replaces "the game and the mirror unpinned" | The owner, 2026-11-18 |
| On big.LITTLE boards too: the game and the mirror on big cores, the AI sharing the rest (6.2) | The owner, 2026-11-18 |
| Cores ranked by `cpu_capacity`, not number, so "core 0, core 1" means the two fastest; the x86 P-core and SMT rules (6.2) | Designer's call, from the owner's intent |
| The placement recorded once by `setup.sh` (drop-ins and `cpu-placement.json`); the engine and the mirror pin themselves from it (6.2) | Designer's call, from the owner's placement |
| `CPUWeight=20` on the model units, kept for unpinned machines (6.2) | Designer's call, accepted by the owner, 2026-11-18 |
| `ai_link.py` split into program and user roots, one `ServiceLocations` for every module (6.8) | Designer's call |
| Playbook renamed `ansible/ai_service.yml` (6.9) | Designer's call |
| Linux hosts opt in per host with an explicit `host_memory_gb`; the Pi group stays off (6.9, 8.2) | Designer's call |
| Root through `-K` per task, no passwordless sudo (6.9) | Designer's call, following `raspberry_pi_runner.yml` |
| Each host builds and installs its own `.deb` (6.9) | Designer's call |
| `ai_install_root` replaced everywhere, no alias (6.1) | Designer's call |
| One renamed test file for every platform (7) | Designer's call |
| KV cache q8_0 for every model (Bonsai and Qwen) on every system, the Mac included (6.5) | The owner, 2026-11-18 |
| Bonsai's context 128K (131,072) on every system, down from the model's whole 262K (6.5) | The owner, 2026-11-18 |
| Qwen's context stays 8,192 on every machine, the 8 GB tier included (6.4.1) | The owner, 2026-11-18 |
| 16 GB and up: Bonsai 128K with Qwen; 4 GB: Bonsai alone at 32K, no Qwen (6.4.1) | The owner, 2026-11-18 |
| Qwen's agent passes `--flash-attn on`, which a quantized V cache needs (6.5) | Designer's call |
| Smaller-memory machines: context tiers proposed, smaller models listed; open (6.4.1) | Raised by the owner, 2026-11-18; not decided |
