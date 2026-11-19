# Lucid Circuit on Linux: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** The local AI service (Bonsai 2 2B + Qwen3-Embedding 0.6B) installs on Linux by Ansible
and as a `.deb`, architecture-neutral, built and tested on 64-bit ARM (a 16 GB Raspberry Pi 5),
designed for x86_64.

**Architecture:** The engine reads the service's two locations (programs, user data) from one
`ServiceLocations`. The Ansible roles split each Mac-only step into a shared step plus a
`macos.yml`/`linux.yml` platform step; the shell templates stay one each, with named platform
functions chosen at render time. On Linux, Ansible builds llama.cpp (every CPU variant, loaded at
run time) and the sidecar into a stage, builds a `.deb`, installs it, and runs the installed
`setup.sh` as the owner, the same per-user path every `.deb` install takes.

**Tech stack:** Python 3.14 (pydantic, pytest, pytest-mock), Ansible (ansible-core, Jinja2),
POSIX `sh`, systemd user units, `dpkg-deb`, llama.cpp `b12167`, uv's python-build-standalone.

**Spec:** [plans/lucid-circuit-linux.md](lucid-circuit-linux.md) (approved 2026-11-18). Section
numbers below (§) are the spec's. Master plan: [plans/lucid-circuit.md](lucid-circuit.md).

## Global constraints

- Linux program root: `/opt/glitchygames/ai`. Linux user root:
  `${XDG_DATA_HOME:-$HOME/.local/share}/glitchygames/ai`; cache
  `${XDG_CACHE_HOME:-$HOME/.cache}/glitchygames/ai`; logs
  `${XDG_STATE_HOME:-$HOME/.local/state}/glitchygames/ai/logs`. The Mac keeps
  `~/Library/Application Support/GlitchyGames/AI` for both roots (§6.1).
- Debian package name `glitchygames-ai`; architecture `arm64` on `aarch64`, `amd64` on `x86_64`;
  sidecar build `cpython-<version>-linux-aarch64-gnu` / `cpython-<version>-linux-x86_64-gnu` (§4).
- llama.cpp on Linux, both architectures: `GGML_NATIVE=OFF`, `GGML_BACKEND_DL=ON`,
  `GGML_CPU_ALL_VARIANTS=ON`, `BUILD_SHARED_LIBS=ON`, `GGML_VULKAN=OFF`, `GGML_OPENMP=OFF`; never
  `GGML_CPU_ARM_ARCH` (§6.5). The Mac's options are unchanged.
- systemd unit names are the launchd labels plus `.service`; only `ai.glitchygames.setup.service`
  has an `[Install]` section (§6.2).
- `ai-service.sh` exit codes stay 0, 1, 3 (nothing fits), 4 (port in use), 64 (usage) (§6.8).
- Threads on Linux: `max(1, nproc - 2)`, the same for both model servers, written by `setup.sh` as
  `AI_THREADS`; empty on a Mac (§6.5).
- CPU placement on Linux (§6.2, the owner, 2026-11-18): with at least two cores, rank them by
  `cpu_capacity`, highest first, ties by number (by number alone when every capacity is equal,
  none exists, or only some do); the game gets the first, the mirror the second, and every AI unit
  (both model units, the API sidecar, the setup job) the rest (with two cores: the AI and the
  mirror share the second). On a Pi 5: game 0, mirror 1, AI 2-3. `setup.sh` is the only place that
  works this out. It writes `~/.config/systemd/user/<unit>.d/cpu-placement.conf` (`CPUAffinity=`) for each
  AI unit and `<user root>/config/cpu-placement.json` (`{"game": [0], "mirror": [1], "ai": [2,
  3]}`), and removes both for one core. Units never carry `AllowedCPUs=` (user
  services get no `cpuset` controller). The model units keep `CPUWeight=20`; the API unit keeps
  the default.
- Bonsai's context is 131,072 on every platform (`ai_service_bonsai_context_size`, down from
  262,144; the owner, 2026-11-18), its defaults comment saying so (§6.5).
- Every model's KV cache is `q8_0` for K and V on every platform (`ai_service_cache_type_k`,
  `ai_service_cache_type_v`; the owner, 2026-11-18), and every model agent passes
  `--flash-attn on`, which a quantized V cache needs (§6.5).
- Every build of llama.cpp starts from an empty build directory, on both platforms (§10.1).
- x86_64 gets static tests only; no x86_64 build or container (§2, §9).
- Root on Linux only per task through `become`, run with `-K`; no passwordless sudo (§6.9).
- Project rules: `uv run` for everything; ruff, then basedpyright and ty, then pytest; pytest-mock's
  `mocker`, never `unittest.mock`; pydantic `BaseModel` (frozen, `extra='forbid'`) for data
  classes; keyword arguments; full names, no abbreviations; no `assert` outside tests; 100%
  coverage; new tests in the existing file for their module.
- **Commits only when the owner asks** (their global rule). Each task ends at a green checkpoint;
  the owner decides when to commit.

## Review focus

The cases the spec implies but no task's main tests reach, most likely to bite first. Each has a
test in the task named.

1. **`XDG_DATA_HOME` set in a shell but not in the systemd user manager.** The game (which reads
   the variable) and the units (which don't see it) would look in different folders. Expected: the
   units and scripts resolve the user root by the same rule as the engine, and `setup.sh` warns
   when the systemd manager's environment and its own disagree. Test in Task 4
   (`test_the_engine_and_the_scripts_agree_on_the_user_root`).
2. **Two users on one machine start the AI.** The ports are fixed (23231-23238), so the second
   user's start finds them taken. Expected: exit 4 ("port-N-in-use"), the game plays on with AI
   unavailable, no crash, the first user's models untouched. Test in Task 3
   (`test_a_port_held_by_another_user_exits_4_and_starts_nothing`).
3. **No network or a full disk at first login.** Expected: `setup.sh` exits non-zero, leaves no
   model under its final name, keeps the `.part` for resuming, and the next login retries; Ansible's
   run of it fails loudly. Test in Task 4 (`test_a_failed_download_leaves_no_model_and_retries`).
4. **Upgrading the `.deb` while models run.** Expected: `prerm` stops every running
   `ai.glitchygames.*` unit, the upgrade keeps each user's models, keys and history, and the next
   game start runs the new binaries. Test in Task 6 (`test_upgrade_keeps_user_data_and_stops_units`,
   in the container session).
5. **A home path with spaces or shell-special characters** (the Mac's already has a space).
   Expected: every rendered script quotes every path. Test in Task 3
   (`test_every_script_runs_from_a_home_with_spaces`).

---

### Task 1: One `ServiceLocations` for the engine and the tools (§6.8)

**Files:**
- Modify: `src/glitchygames/state/paths.py` (lift the platform part of `get_save_directory`)
- Modify: `src/glitchygames/ai_link.py` (lines 47-50 constants, 83-101 `AiLink.__init__`,
  255-284 `install_root`/`create_link`)
- Modify: `src/glitchygames/ai/local_service.py` (lines 25, 42, 189-221)
- Modify: `src/glitchygames/ai_console.py` (lines 280-292, 984, 1076)
- Modify: `src/glitchygames/ai_host.py` (line 83)
- Modify: `scripts/ai_model_comparison.py` (45, 700), `scripts/ai_behaviour/run.py` (26, 317),
  `scripts/ai_behaviour/paired.py` (38, 312)
- Test: `tests/state/test_paths.py`, `tests/test_ai_link.py`, `tests/ai/test_local_service.py`,
  `tests/test_ai_console.py`

**Interfaces:**
- Produces, in `state/paths.py`: `platform_data_home() -> Path` (macOS
  `~/Library/Application Support`, Windows `%APPDATA%` or `~/AppData/Roaming`, else
  `$XDG_DATA_HOME` or `~/.local/share`). `get_save_directory(app_name)` returns
  `platform_data_home() / app_name`, behaviour unchanged.
- Produces, in `ai_link.py`:
  - `class ServiceLocations(BaseModel)`, frozen, `extra='forbid'`: `program_root: Path`,
    `user_root: Path`; properties `control_script` (`program_root/bin/ai-service.sh`), `key_file`
    (`user_root/config/service-api-key`), `history_directory` (`user_root/history`); classmethod
    `in_one_folder(*, root: Path) -> ServiceLocations` (both roots the same, as on a Mac and in
    tests).
  - `service_locations() -> ServiceLocations | None`: `GLITCHYGAMES_AI_INSTALL_ROOT` sets both;
    `GLITCHYGAMES_AI_PROGRAM_ROOT` / `GLITCHYGAMES_AI_USER_ROOT` each set one (and win over the
    first); else macOS → one folder `platform_data_home()/GlitchyGames/AI`, Linux →
    `/opt/glitchygames/ai` and `platform_data_home()/glitchygames/ai`; any other platform → None.
  - Constants `PROGRAM_ROOT_ENVIRONMENT_VARIABLE`, `USER_ROOT_ENVIRONMENT_VARIABLE`,
    `EXIT_NOT_ENOUGH_MEMORY = 3` (the only copy), `LINUX_PROGRAM_ROOT = Path('/opt/glitchygames/ai')`.
  - `AiLink(*, locations: ServiceLocations, session_url=..., sleep=...)`, attribute `locations`.
  - `install_root()` and `DEFAULT_INSTALL_ROOT` are removed; every caller moves.
- Produces elsewhere: `LocalAIClient(*, locations: ServiceLocations | None = None, ...)` (None →
  `service_locations()`; None from that → `LocalAIServiceNotInstalledError`);
  `AiConsole(*, link, locations: ServiceLocations)`. The not-installed message names
  `ansible/ai_service.yml` (the renamed playbook, Task 7).

- [ ] **Step 1: Write the failing tests**
  - `tests/state/test_paths.py::test_platform_data_home_is_what_saves_used_on_every_platform`:
    for `darwin`, `win32` (with and without `APPDATA`), `linux` (with and without
    `XDG_DATA_HOME`), `get_save_directory('paddleslap') == platform_data_home() / 'paddleslap'`
    and equals today's value for that platform (patch `sys.platform` with `mocker`).
  - `tests/test_ai_link.py`:
    - `test_service_locations_on_macos_are_one_folder`: both roots
      `~/Library/Application Support/GlitchyGames/AI`.
    - `test_service_locations_on_linux_split_programs_and_user_data`: `/opt/glitchygames/ai` and
      `<XDG_DATA_HOME or ~/.local/share>/glitchygames/ai`, both cases.
    - `test_the_install_root_variable_still_sets_both_roots`, and
      `test_the_program_and_user_variables_each_set_one_and_win`.
    - `test_another_platform_has_no_locations_and_no_link` (`win32`, `emscripten`).
    - `test_create_link_needs_the_control_script_and_the_key_in_their_own_roots`: control script
      only under `program_root`, key only under `user_root` → a link; either missing → None.
  - `tests/test_ai_console.py::test_the_link_the_client_and_the_console_agree_on_every_path`: one
    `ServiceLocations` with different roots; the link's, `LocalAIClient`'s and the console's
    control script, key file and history path are equal (the invariant of §7).
  - `tests/ai/test_local_service.py::test_the_client_reads_the_link_exit_code`:
    `glitchygames.ai.local_service.EXIT_NOT_ENOUGH_MEMORY is glitchygames.ai_link.EXIT_NOT_ENOUGH_MEMORY`.
  - Existing tests that build `AiLink(install_root=tmp_path)` or `AiConsole(..., install_root=...)`
    switch to `locations=ServiceLocations.in_one_folder(root=tmp_path)`; none is deleted.

- [ ] **Step 2: Run them and see them fail**
  Run: `uv run pytest --dummy-only tests/state/test_paths.py tests/test_ai_link.py tests/ai/test_local_service.py tests/test_ai_console.py`
  Expected: FAIL (`ImportError: cannot import name 'ServiceLocations'`, `platform_data_home`).

- [ ] **Step 3: Implement the interfaces above**, then move the three scripts to
  `service_locations()` (each exits with its existing "not installed" message on None).

- [ ] **Step 4: Gates**
  Run: `uv run ruff format src tests scripts && uv run ruff check src tests scripts && uv run basedpyright && uv run ty check`, then
  `uv run pytest --dummy-only tests/state tests/test_ai_link.py tests/ai tests/test_ai_console.py tests/test_ai_behaviour.py tests/test_ai_model_comparison.py`
  Expected: clean; all pass; `grep -rn "install_root()" src scripts tests` finds nothing.

- [ ] **Step 5: Checkpoint** (commit if the owner has asked).

---

### Task 2: Split `ai_install_root` into program and user roots; `llama_cpp` split and clean builds (§6.1, §6.5, §10.1)

**Files:**
- Modify: `ansible/group_vars/macos.yml`; Create: `ansible/group_vars/linux.yml`
- Modify every `ai_install_root` use: `ansible/roles/ai_package/tasks/main.yml:64`,
  `ai_service/templates/agent.plist.j2:14`, `ai_models/defaults/main.yml:89`,
  `ai_service/defaults/main.yml:68-72`, `ai_sidecar/defaults/main.yml:8`,
  `llama_cpp/tasks/main.yml:35`
- Split: `ansible/roles/llama_cpp/tasks/main.yml` → shared `main.yml` + `macos.yml` + `linux.yml`;
  Modify `ansible/roles/llama_cpp/defaults/main.yml`
- Create: `tests/ansible_rendering.py` (test support: the Jinja rendering of role files)
- Test: `tests/test_ansible_macos_ai_service.py` (renamed in Task 7; keep the name until then)

**Interfaces:**
- Produces, Ansible variables: `ai_program_root`, `ai_user_root`, `ai_cache_root`, `ai_log_root`
  in both group_vars files (Mac: `ai_program_root` and `ai_user_root` both the old
  `ai_install_root` value; Linux: Global constraints). `ai_install_root` no longer exists.
  On Linux `llama_cpp_install_directory` is inside the package stage, not `/opt` (Ansible
  installs `/opt` only through the `.deb`): `{{ ai_cache_root }}/package/stage{{ ai_program_root }}/runtime/llama.cpp-<tag>-<hash>`.
- Produces, `llama_cpp/defaults`: `llama_cpp_linux_cmake_options` (the six options of Global
  constraints), `llama_cpp_cpu_variants` keyed by architecture: `aarch64` → the 8 names of §4,
  `x86_64` → the 14 names of §4.
- Produces, `tests/ansible_rendering.py`:
  `ansible_variables(*, system: Literal['Darwin', 'Linux'], architecture: Literal['aarch64', 'x86_64'], home: Path) -> dict[str, Any]`
  (every role's defaults plus the platform's group_vars, with facts `system`, `architecture`,
  `user_dir`, `processor_vcpus` set, Jinja references resolved until stable) and
  `render_template(*, path: Path, variables: dict[str, Any]) -> str` (Ansible's own filters
  that the templates use, `quote`, `to_json`, `hash`, available).

- [ ] **Step 1: Write the failing tests**
  - `test_no_role_names_the_old_install_root`: no file under `ansible/` contains `ai_install_root`.
  - `test_the_mac_roots_are_one_folder_and_unchanged`: rendered Mac `ai_program_root` and
    `ai_user_root` both equal `<home>/Library/Application Support/GlitchyGames/AI`.
  - `test_the_linux_roots_follow_the_design`: Global constraints' Linux paths.
  - `test_every_llama_cpp_build_starts_from_an_empty_directory` (§10.1's regression test): in
    `llama_cpp/tasks/main.yml`, a task removing `llama_cpp_build_directory` comes before the
    "Configure the build" task, unconditionally inside the build block.
  - `test_the_linux_llama_cpp_options_name_no_cpu_and_match_on_both_architectures`: rendered for
    `aarch64` and `x86_64`, the Linux options are equal, contain the six of Global constraints, and
    no key `GGML_CPU_ARM_ARCH` or value naming a CPU.
  - `test_every_architecture_has_its_variant_list`: `llama_cpp_cpu_variants['aarch64']` and
    `['x86_64']` equal §4's lists exactly.
  - `test_the_mac_llama_cpp_options_are_unchanged`: the rendered Mac options equal today's
    (`llama_cpp_base_cmake_options` plus the inventory's Metal options and the three OSX keys).

- [ ] **Step 2: Run them and see them fail**
  Run: `uv run pytest --dummy-only tests/test_ansible_macos_ai_service.py`
  Expected: FAIL (old name present; `ansible_rendering` missing; no clean-build task).

- [ ] **Step 3: Implement.** Map each `ai_install_root` use (programs → `ai_program_root`; models,
  config, history → `ai_user_root`) and record the mapping in the task's report. Split
  `llama_cpp/tasks/main.yml`: `macos.yml` holds the Apple Silicon refusal, the SDK lookup, the OSX
  options and the Metal/Homebrew checks; `linux.yml` installs `cmake`, `build-essential` and
  `rsync` with `become`, adds the Linux options, and after install checks with `ldd` that
  `llama-server` and every `lib/*.so` link only glibc, libstdc++, libgcc, libm and the runtime's
  own `lib/` (RPATH `$ORIGIN/../lib`), that every name in `llama_cpp_cpu_variants[architecture]`
  has its `libggml-cpu-<name>.so`, and records the highest `GLIBC_` version as
  `llama_cpp_glibc_version`. Add the empty-the-build-directory task to the shared build block.

- [ ] **Step 4: Gates** as Task 1, plus
  `uvx --from ansible-core ansible-playbook -i ansible/inventory.yml ansible/macos_ai_service.yml --syntax-check`.
  Expected: clean; pass.

- [ ] **Step 5: Checkpoint.**

---

### Task 3: The shared shell templates gain platform functions (§5.3, §6.4)

**Files:**
- Modify: `ansible/roles/ai_service/templates/ai-service.sh.j2`,
  `run-llama-server.sh.j2`, `agent.env.j2`, `uninstall.sh.j2`
- Create: `ansible/roles/ai_service/templates/agent.service.j2` (systemd user unit)
- Test: `tests/test_ansible_macos_ai_service.py`

**Interfaces:**
- Consumes: `ansible_variables`, `render_template` (Task 2).
- Produces, shell functions defined once per rendered script, bodies by `ansible_facts['system']`:
  `total_memory_mb`, `available_memory_mb` (honours `AI_MEMORY_MB` / `AI_AVAILABLE_MB`; the Mac
  converts `kern.memorystatus_level` to MB), `agent_is_running LABEL`,
  `start_agent_process LABEL`, `stop_agent_process LABEL`, `port_is_listening PORT` (`lsof` on a
  Mac, `ss -Hltn` on Linux), `sha256_of FILE`, `user_root` (the Global constraints rule on Linux).
  `AI_FREE_PERCENT` is removed.
- Produces: `agent.env.j2` gains `AI_THREADS` (empty on a Mac); `run-llama-server.sh` passes
  `--threads "$AI_THREADS"` only when it is set. Both model agents' settings gain
  `AI_CACHE_TYPE_K` and `AI_CACHE_TYPE_V` from the two new defaults, passed as `--cache-type-k` and
  `--cache-type-v`; the embedding agent also gains `--flash-attn on`. The defaults comment on
  `ai_service_qwen_context_size` stops claiming records are split before embedding (§10.3): the
  caller keeps each text under the context. `ai_validate`'s per-role arguments are built from the same source as
  `run-llama-server.sh`'s (one list in the role defaults both read), adding the missing
  `--chat-template-kwargs` and the cache types. `agent.service.j2`: `Type=simple`,
  `ExecStart=/opt/glitchygames/ai/bin/run-llama-server.sh <label>` (the script finds its config by
  `user_root`), `Restart=on-failure`, `RestartSec=10`, no `[Install]`; the two model units add
  `CPUWeight=20`, the API unit doesn't.

- [ ] **Step 1: Write the failing tests** (each runs the rendered script with `HOME` and
  `XDG_*` pointed into `tmp_path`, empty model files where the picker looks, and memory faked):
  - `test_the_picker_chooses_the_same_on_both_platforms`, parametrized over `Darwin`/`Linux` and
    the table of §7: 16384 MB total / 9216 available → `bonsai=2b`, `qwen=0.6b`, exit 0; 16384 /
    6144 → `reason=nothing-fits`, exit 3; 8192 / 6144 → exit 3; `AI_BONSAI_SIZE=4b` that doesn't
    fit → exit 3.
  - `test_a_port_held_by_another_user_exits_4_and_starts_nothing` (Review focus 2): a listening
    socket on the Bonsai port in the test; `start` (Linux rendering, `systemctl` replaced by a
    recording stub on `PATH`) prints `reason=port-23232-in-use`, exits 4, and the stub saw no start.
  - `test_every_script_runs_from_a_home_with_spaces` (Review focus 5): the picker, `stop` and
    `status` succeed with `HOME=<tmp>/a home/with 'quotes'`.
  - `test_every_rendered_script_passes_sh_n`: every shell template, both platforms, both
    architectures.
  - `test_no_agent_unit_starts_at_login`: every rendered agent unit parses (configparser) with no
    `[Install]` section, `Restart=on-failure`, and an `ExecStart` under `/opt/glitchygames/ai/bin/`.
  - `test_the_model_units_yield_the_cpu_and_never_use_a_cpuset`: both model units have
    `CPUWeight=20`; the API unit has no `CPUWeight`; no unit or drop-in template contains
    `AllowedCPUs` (the assertion message names §6.2's delegation finding).
  - `test_run_llama_server_passes_threads_only_when_set`: rendered with a stub `llama-server`
    that prints its arguments; `--threads 3` appears with `AI_THREADS=3`, nothing without it.
  - `test_every_model_runs_an_8_bit_kv_cache_on_every_platform`, both renderings, same stub: the
    reasoning and the embedding agent each pass `--cache-type-k q8_0 --cache-type-v q8_0` with
    `--flash-attn on`; the API agent passes none of them; the reasoning agent passes
    `--ctx-size 131072`.
  - `test_validation_runs_what_the_service_runs`: for each role, the arguments `ai_validate`
    renders equal the stub-printed arguments of `run-llama-server.sh`, except the port, the
    `--verbose` flag and the fields the validation exists to vary (the model file per size).
    Proven to fail first on today's code (it lacks `--chat-template-kwargs`).
  - Keep `test_a_plist_holds_no_shell_script`, `test_the_agents_listen_on_loopback_only`,
    `test_no_model_starts_at_login` passing.

- [ ] **Step 2: Run them and see them fail.** Expected: FAIL (no Linux bodies, no unit template).

- [ ] **Step 3: Implement.** One template each; a Jinja `{% if ansible_facts['system'] == 'Linux' %}`
  appears only inside the platform functions' bodies.

- [ ] **Step 4: Gates**, plus `shellcheck` on each rendered script (written to `tmp_path` by a
  one-off `uv run python -c` using `tests/ansible_rendering.py`). Expected: clean; pass.

- [ ] **Step 5: Checkpoint.**

---

### Task 4: `setup.sh` as the one per-user path on Linux (§6.3)

**Files:**
- Move: `ansible/roles/ai_package/templates/setup.sh.j2` keeps its place; its Mac-only parts become
  the Task 3 platform functions; Create: `ansible/roles/ai_package/templates/uninstall-user.sh.j2`
- Test: `tests/test_ansible_macos_ai_service.py`

**Interfaces:**
- Consumes: Task 3's functions, `ai_models` pins.
- Produces: rendered `setup.sh` (exit 0 done, 1 a failure to retry at next login), which on Linux:
  makes the user-root folders; downloads the chosen models (§6.3) with resumable `curl` into
  `.part` files and renames only after `sha256_of` matches; generates the two keys; renders
  `service.json` and each agent's `.env` from `/opt/glitchygames/ai/share/agents/*.template`,
  writing `AI_THREADS` = `max(1, nproc - 2)`; writes or removes every AI unit's
  `cpu-placement.conf` drop-in and `config/cpu-placement.json` (Global constraints), reading core
  capacities under
  `${AI_SYSFS_CPU_ROOT:-/sys/devices/system/cpu}` (the override exists for tests); runs
  `systemctl --user daemon-reload`; writes every AI unit's `user-root.conf` drop-in (design §6.2);
  and logs a warning when `systemctl --user show-environment` has a different `XDG_DATA_HOME` from
  its own.
  `uninstall-user.sh` removes the calling user's user root, cache and logs, after stopping their
  units.

- [ ] **Step 1: Write the failing tests** (`curl`, `openssl`, `systemctl`, `nproc` replaced by stubs
  on `PATH`; downloads served from files under `tmp_path`):
  - `test_setup_carries_every_pinned_model`: the rendered Linux `setup.sh` contains each
    `ai_models` revision and SHA-256 for the downloaded sizes.
  - `test_setup_on_linux_leaves_a_working_user_root`: after a run, models, keys (mode 0600),
    `service.json` and each `.env` exist, and a second run changes nothing (same file mtimes).
  - `test_setup_gives_the_game_the_mirror_and_the_ai_their_own_cores`, parametrized on a fake
    `AI_SYSFS_CPU_ROOT` and `nproc` stub:
    | cores | capacities | `AI_THREADS` | AI drop-in | `cpu-placement.json` |
    |---|---|---|---|---|
    | 4 | all 1024 | 2 | `CPUAffinity=2 3` | game `[0]`, mirror `[1]`, ai `[2, 3]` |
    | 4 | none present | 2 | `CPUAffinity=2 3` | the same |
    | 8 | all 1024 | 6 | `CPUAffinity=2 3 4 5 6 7` | game `[0]`, mirror `[1]`, ai `[2, ..., 7]` |
    | 8 | 0-3: 446, 4-7: 1024 (RK3588-style) | 6 | `CPUAffinity=0 1 2 3 6 7` | game `[4]`, mirror `[5]`, ai `[0, 1, 2, 3, 6, 7]` |
    | 8 | 0-3: 325, 4-6: 870, 7: 1024 | 6 | `CPUAffinity=0 1 2 3 5 6` | game `[7]`, mirror `[4]`, ai `[0, 1, 2, 3, 5, 6]` |
    | 8 | 0-3: 1024, 4-7: 446 (big first) | 6 | `CPUAffinity=2 3 4 5 6 7` | game `[0]`, mirror `[1]`, ai `[2, ..., 7]` |
    | 4 | only cores 0-1 report one | 2 | `CPUAffinity=2 3` | game `[0]`, mirror `[1]`, ai `[2, 3]` (by number) |
    | 3 | all 1024 | 1 | `CPUAffinity=2` | game `[0]`, mirror `[1]`, ai `[2]` |
    | 2 | 0: 446, 1: 1024 | 1 | `CPUAffinity=0` | game `[1]`, mirror `[0]`, ai `[0]` |
    | 1 | 1024 | 1 | none (an earlier one removed) | none (an earlier one removed) |
    Every AI unit (both model units, the API, setup) gets the same drop-in. Invariants checked on
    every row: the game's cores never overlap the AI's; every core named is below `nproc`; game,
    mirror and AI together name every core; no AI core has a higher capacity than the game's.
  - `test_a_failed_download_leaves_no_model_and_retries` (Review focus 3): `curl` stub fails; exit 1,
    no file under the model's final name, its `.part` kept; a later run with a working stub
    completes.
  - `test_a_wrong_hash_is_discarded`: a served file with the wrong bytes leaves neither the model
    nor its `.part`.
  - `test_the_engine_and_the_scripts_agree_on_the_user_root` (Review focus 1): with
    `XDG_DATA_HOME` unset and set, `service_locations().user_root` (patched to Linux) equals the
    folder the rendered `setup.sh` and `run-llama-server.sh` use; and `setup.sh` logs the warning
    when the `systemctl --user show-environment` stub reports a different value.

- [ ] **Step 2: Run them and see them fail.** Expected: FAIL.

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Gates.** Expected: clean; pass.

- [ ] **Step 5: Checkpoint.**

---

### Task 4b: The game pins itself to its core (§6.2)

**Files:**
- Create: `src/glitchygames/cpu_placement.py` (Linux affinity, kept out of the engine's frame code)
- Modify: `src/glitchygames/ai_link.py` (`ServiceLocations` gains the placement file's path)
- Modify: `src/glitchygames/engine/game_engine.py` (after `create_link`, line ~1642)
- Test: `tests/test_cpu_placement.py` (a distinct subject), `tests/test_ai_link.py`

**Interfaces:**
- Consumes: `ServiceLocations` (Task 1); the file Task 4 writes.
- Produces:
  - `ServiceLocations.cpu_placement_file` → `user_root/config/cpu-placement.json`.
  - `class CpuPlacement(BaseModel)`, frozen, `extra='forbid'`: `game: frozenset[int]`,
    `mirror: frozenset[int]`, `ai: frozenset[int]`, each non-empty, each core `>= 0`. Stage 4b's
    mirror reads `mirror` from the same model.
  - `read_cpu_placement(*, path: Path) -> CpuPlacement | None`: None when the file is missing; a
    file that fails validation logs a warning and gives None.
  - `pin_this_process(*, cores: frozenset[int], task_directory: Path = Path('/proc/self/task'),
    set_affinity: Callable[[int, set[int]], None] | None = None) -> bool`: sets `cores` on every
    thread id listed in `task_directory` (resolved at call time, `os.sched_setaffinity` when
    None); an `OSError` (a core this machine lacks) logs a warning, leaves the threads as they
    were where it can, and returns False; never raises.
  - The engine calls it only when `sys.platform == 'linux'`, `create_link` returned a link, and
    the run isn't an inner context; with the placement's `game` cores. Amended by the final
    review's fix wave (2026-11-19): not as `create_link` returns but on the main thread, the first
    frame the link reports `CONNECTED` (`AiHostSources.pump_events`), so a start refused for
    memory or one that fails never pins (design §6.2).

- [ ] **Step 1: Write the failing tests** (a fake `task_directory` under `tmp_path` holding thread
  id folders; `set_affinity` a recording `mocker.Mock`):
  - `test_a_live_run_with_ai_pins_every_thread_to_the_game_cores`: three thread ids → three calls,
    each with `{0}`; returns True.
  - `test_a_core_the_machine_lacks_is_a_warning_not_a_crash`: `set_affinity` raises
    `OSError(errno.EINVAL)`; returns False, one warning naming the cores, no exception.
  - `test_no_pinning_without_ai_on_a_mac_or_without_a_placement`, parametrized: `--no-ai`,
    `--headless`, `sys.platform` `darwin`, no placement file; `set_affinity` never called (through
    the engine's start, `mocker.patch('glitchygames.cpu_placement.os.sched_setaffinity')`).
  - `test_a_malformed_placement_is_ignored_with_a_warning`: empty `game`, a negative core,
    an unknown key; `read_cpu_placement` gives None and warns.
  - `test_the_placement_file_lives_in_the_user_config`: `ServiceLocations.in_one_folder(root=r)`
    gives `r/config/cpu-placement.json`.
  - `tests/test_process_state_guard.py` and `tests/test_engine_doors.py` stay green: the module
    holds no module-level mutable state and reads no input.

- [ ] **Step 2: Run them and see them fail.** Expected: FAIL (no module).

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Gates.** Expected: clean; pass.

- [ ] **Step 5: Checkpoint.**

---

### Task 5: The sidecar per platform and architecture (§6.6)

**Files:**
- Modify: `ansible/roles/ai_sidecar/defaults/main.yml`, `ansible/roles/ai_sidecar/tasks/main.yml`
- Test: `tests/test_ansible_macos_ai_service.py`

**Interfaces:**
- Produces: `ai_sidecar_python_build` from facts: Mac `cpython-<version>-macos-aarch64-none`,
  Linux §4's names. On Linux the sidecar installs into the package stage
  (`.../stage/opt/glitchygames/ai/sidecar`). The "uses nothing outside itself" check is `otool -L`
  on a Mac and `ldd` on Linux, failing on any library outside the sidecar and the system's libc.

- [ ] **Step 1: Write the failing tests:** `test_the_sidecar_build_matches_the_platform` (Darwin
  aarch64, Linux aarch64, Linux x86_64 → the three names); keep
  `test_the_sidecar_pins_its_python_and_its_docs_script` passing.
- [ ] **Step 2: Run, see it fail.** **Step 3: Implement.** **Step 4: Gates.** **Step 5: Checkpoint.**

---

### Task 6: The `.deb`, sharing the `.pkg`'s staging (§6.7)

**Files:**
- Split: `ansible/roles/ai_package/tasks/main.yml` → `stage.yml` (shared), `macos.yml` (plists,
  postinstall, `pkgbuild`/`productbuild`, payload check), `linux.yml`
- Create templates: `ansible/roles/ai_package/templates/deb-control.j2`, `deb-postinst.sh.j2`,
  `deb-prerm.sh.j2`, `deb-postrm.sh.j2`, `setup.service.j2`
- Modify: `ansible/roles/ai_package/handlers/main.yml` (a `dpkg-deb` handler beside the `.pkg`'s)
- Modify: `noxfile.py` (session `deb-package`)
- Test: `tests/test_ansible_macos_ai_service.py`

**Interfaces:**
- Consumes: `llama_cpp_glibc_version` (Task 2), the stage (Tasks 2, 5), templates (Tasks 3, 4).
- Contracts from Task 4 the staging must honour (found in its review, 2026-11-18): render
  `share/agents/*.template` (`agent.env.j2`, `service.json.j2`) with `ai_user_root` and
  `ai_program_root` set to the `ai_package_*_placeholder` defaults, as the tests' `LinuxSetup`
  helper does, since `setup.sh` fills those placeholders per user; install the rendered
  `uninstall.sh.j2` as `bin/uninstall-user.sh` (one uninstaller, Task 4 ruling 3); `setup.sh`
  writes every AI unit a drop-in, `user-root.conf`, holding
  `Environment="GLITCHYGAMES_AI_USER_ROOT=..."` with the resolved user root, so the units' runner
  finds the same folder however a unit starts (the final review's fix wave replaced the first
  build's `systemctl --user set-environment` in `ai-service.sh`, which leaked the variable into
  every later process of the user manager; design §6.2); stage `bin/*.so*` (the CPU variant modules) and `lib/` from the llama.cpp runtime, not
  only `bin/llama-server` (Task 2); `Depends` gains `iproute2` (`ss`, which the port check needs:
  an absent `ss` reads as "port free", Task 3 review).
- Produces: `{{ ai_cache_root }}/package/glitchygames-ai_<ai_package_version>_<deb arch>.deb`;
  control `Package: glitchygames-ai`, `Architecture` from §4, `Depends: libc6 (>= <glibc>),
  libstdc++6, libgcc-s1, systemd, curl, openssl, ca-certificates, coreutils, iproute2`; postinst
  `systemctl --global enable ai.glitchygames.setup.service` then, with `SUDO_USER`,
  `systemctl --user --machine="$SUDO_USER@" start ai.glitchygames.setup.service`, else a line
  saying it runs at next login; prerm stops every `ai.glitchygames.*` unit of every logged-in
  user (`loginctl list-users`); postrm touches no home.
- Produces: nox session `deb-package -- PATH_TO_DEB` (manual: needs a `.deb` built on a Pi and
  Docker): installs it into an arm64 container of the matching release, checks
  `llama-server --version` and its `load_backend` line, the sidecar imports
  `glitchygames_ai_service`, upgrade and `dpkg -r` (below), and refusal on an older release.

- [ ] **Step 1: Write the failing tests**
  - `test_the_deb_control_follows_the_design`: rendered for aarch64 and x86_64: architecture,
    `Depends` exactly as above with the glibc version filled.
  - `test_the_setup_unit_is_the_only_one_enabled`: `setup.service` has `[Install]
    WantedBy=default.target`, `Type=oneshot`; postinst enables only it.
  - `test_postinst_without_sudo_user_skips_the_start` (§6.2): run with `systemctl` stubbed, no
    `SUDO_USER` → no `--user --machine` call, the message printed, exit 0.
  - `test_the_package_never_takes_the_models` extended to the `.deb` stage: no `.gguf`; every
    variant library, `llama-server`, the sidecar, the licenses and every unit present.
  - In the nox session: `test_upgrade_keeps_user_data_and_stops_units` (Review focus 4) and
    `dpkg -r` leaving nothing under `/opt/glitchygames/ai` or `ai.glitchygames.*` in
    `/usr/lib/systemd/user`.
- [ ] **Step 2: Run, see them fail.** **Step 3: Implement** (the Mac's `.pkg` output unchanged:
  `test_the_mac_package_stage_is_unchanged` compares the staged file list before and after).
- [ ] **Step 4: Gates.** **Step 5: Checkpoint.**

---

### Task 7: The playbook, the inventory, models, validation and uninstall on Linux (§6.9)

**Files:**
- Rename: `ansible/macos_ai_service.yml` → `ansible/ai_service.yml`;
  `tests/test_ansible_macos_ai_service.py` → `tests/test_ansible_ai_service.py`
- Modify: `ansible/inventory.yml` (a `linux` group; `host_memory_gb` on every Linux host;
  `ai_enabled: true` on the 16 GB Pi 5 host(s))
- Modify: `ansible/roles/ai_models/tasks/main.yml` (on Linux only the notices; `setup.sh`
  downloads models), `ansible/roles/ai_service/tasks/main.yml` (on Linux: install the `.deb` with
  `become`, run the installed `setup.sh` as the owner, then the smoke test)
- Create: `ansible/roles/ai_validate/tasks/linux.yml`, `ansible/roles/ai_uninstall/tasks/linux.yml`
- Update every mention of the old playbook: `CLAUDE.md:82`, `README.md:275`, `API_README.md:30`,
  `plans/lucid-circuit.md` (lines 5, 326), `src/glitchygames/ai/local_service.py` (Task 1's message)
- Test: `tests/test_ansible_ai_service.py`

**Interfaces:**
- Produces: plays `macos:&ai_enabled` (`become: false`, unchanged roles) and `linux:&ai_enabled`
  (`become: false`, per-task `become`); `ai_validate` on Linux reports per model its answers,
  resident memory, threads and the `load_backend` variant.

- [ ] **Step 1: Write the failing tests**
  - `test_only_hosts_with_ai_enabled_get_the_ai_service`, updated: a sorting play, then a
    `macos:&ai_enabled` and a `linux:&ai_enabled` play.
  - `test_every_linux_host_states_its_memory_and_opts_in_at_16_gb` (replaces
    `test_the_ai_service_is_on_by_default_and_off_on_the_raspberry_pis`): every `linux` host has an
    integer `host_memory_gb`; `ai_enabled` is true exactly where it is ≥ 16; the `raspberry_pis`
    group's own `ai_enabled` stays false.
  - `test_no_ai_role_tests_for_a_board`: no file under the `ai_*`/`llama_cpp` roles mentions
    `raspberry`, `pi5` or a CPU model; architecture appears only as
    `ansible_facts['architecture']`.
  - `test_no_document_names_the_old_playbook`: no tracked `.md`, `.py` or `.yml` outside `plans/`
    contains `macos_ai_service.yml` (`plans/` records history and keeps the old name where it was
    true then).
- [ ] **Step 2: Run, see them fail.** **Step 3: Implement.**
- [ ] **Step 4: Gates**, plus `--syntax-check` of `ansible/ai_service.yml`.
- [ ] **Step 5: Checkpoint.**

---

### Task 8: Measurements stop the AI first; the Pi playbook's spike additions move (§8.2, §8.4)

**Files:**
- Modify: `scripts/measure_on_raspberry_pi.py` (`measure_script`, after the `flock` block)
- Modify: `ansible/raspberry_pi_runner.yml` (remove the Vulkan packages task, the `render` group
  task, its V3DV check and `raspberry_pi_gpu_compute_users`; `cmake` now comes from Task 2)
- Modify: `plans/future-work.md` (the CI-job stop, for when a workflow runs the Pi jobs)
- Test: `tests/test_measure_on_raspberry_pi.py`

**Interfaces:**
- Produces: in the rendered measure script, after the lock is held and before `cd` to the clone:
  `if [ -x /opt/glitchygames/ai/bin/ai-service.sh ]; then echo "stopping the local AI models
  before measuring"; /opt/glitchygames/ai/bin/ai-service.sh stop || true; fi`.

- [ ] **Step 1: Write the failing test** `test_the_measurement_stops_the_ai_after_the_lock`: in
  `measure_script(...)`'s text, the stop comes after the `flock --wait` block and before the
  measurement subshell, guarded by `-x`; running the rendered script's prefix in a shell with a stub
  `ai-service.sh` records one `stop`, and without the file records nothing.
- [ ] **Step 2: Run, see it fail.** **Step 3: Implement.** **Step 4: Gates**, plus
  `--syntax-check` of `ansible/raspberry_pi_runner.yml`. **Step 5: Checkpoint.**

---

### Task 9: Whole-suite gate, docs and records

**Files:**
- Modify: `docs/architecture/` page for the AI service if one names the Mac only (grep), the
  master plan's status line, `plans/lucid-circuit-linux.md` status ("built; hardware validation
  pending"), `plans/future-work.md` (x86_64 support steps of §9.2; GPU backends), the project's
  memory note.

- [ ] **Step 1:** `grep -rn "macos_ai_service\|ai_install_root\|install_root()" --include='*.md' --include='*.py' --include='*.yml' .`
  outside `.venv`; expected: only finished plans, by date.
- [ ] **Step 2:** The whole gate session once: `uv run nox -s lint static-analysis`, then
  `uv run pytest` (both drivers outside CI). Expected: all green, coverage 100%.
- [ ] **Step 3:** Report what was **not** verified: the Ansible run on the Pi, the `.deb` session
  (needs a Pi-built `.deb`), §8.3's hardware validation, anything x86_64.
- [ ] **Step 4: Checkpoint.**

---

### Task 11: Memory tiers: Bonsai's context, the prompt cache and Qwen chosen by total memory (§6.4.1)

Added 2026-11-19: the owner wants the tiers in this branch (they were decided 2026-11-18 and
recorded, not built). Every system, the Mac included: the tier settings are shared.

**Files:**
- Modify: `ansible/roles/ai_service/defaults/main.yml` (the tier table; the reserved figures per
  tier; `ai_service_game_reserve_mib` 768, provisional), `ai-service.sh.j2` (the picker),
  `ansible/roles/ai_package/templates/setup.sh.j2` (no Qwen download on a Bonsai-only machine; the
  setup job's own units without the user-root drop-in)
- Modify: `services/ai-service/src/glitchygames_ai_service/app.py` and its settings (readiness and
  `/v1/embeddings` without an embedding model); its tests in `services/ai-service/tests/` (own lock,
  own 100% coverage)
- Modify: plans/future-work.md (the tiers item it holds is now built: remove it), the design's
  §6.4.1 header ("decided, built")
- Test: `tests/test_ansible_ai_service.py`, `services/ai-service/tests/`

**Interfaces:**
- `ai_service_memory_tiers` (shared default), smallest first, each `{minimum_memory_mb,
  bonsai_context_size, bonsai_cache_ram_mib, qwen}`:
  | minimum | Bonsai context | prompt cache | Qwen |
  |---|---|---|---|
  | 3,072 MiB (a 4 GB machine; total memory reported is below 4,096) | 32,768 | 512 | none |
  | 6,144 MiB (8 GB) | 32,768 | 1,024 | `0.6b` |
  | 12,288 MiB (16 GB and up) | 131,072 | 4,096 | `0.6b` |
  Below the smallest: nothing (exit 3, as today). The thresholds are below the nominal sizes because
  `MemTotal` reports less than the board's size; check them against a real 4 GB, 8 GB and 16 GB
  reading (the 16 GB Pi reports 16,179 MiB) and record the source.
- The picker chooses the tier by **total** memory, then checks **available** memory against the
  tier's reserved figures plus `ai_service_game_reserve_mib`, as today. It writes the tier's
  Bonsai context and prompt cache to Bonsai's `config/<label>.env.runtime` (the existing per-run
  override the runner already reads), and starts Qwen only when the tier names one. "Bonsai alone"
  is a valid result, printed as such (`qwen=none`), exit 0.
- Reserved figures per tier, estimates until the Pi measures them (Task 10): Bonsai at 128K about
  2,560 MiB, at 32K about 1,948 MiB; Qwen 0.6b about 1,464 MiB (the design's §6.5 table). The Mac's
  larger Bonsai sizes keep their per-size figures scaled the same way, marked provisional.
- `ai_service_game_reserve_mib`: 768 (the owner, 2026-11-19, provisional until one figure is
  measured from every game's peak on the Pi).
- setup.sh: on a machine whose tier has no Qwen, it downloads no Qwen model and writes no Qwen
  settings. Its own setup unit gets no `user-root.conf` drop-in (controller ruling, 2026-11-19: the
  setup job computes its root each run; with the drop-in a later `XDG_DATA_HOME` change would be
  ignored at login); every other AI unit keeps it.
- The API sidecar: `/health/ready` is ready when every model the selection names answers — a
  reasoning model alone when the selection has no embedding model; `/v1/embeddings` without an
  embedding model answers 503 with code `no_embedding_model` and the message "this machine has no
  embedding model" (the service's error shape, `ServiceError`).

- [ ] **Step 1: Write the failing tests**
  - `test_the_picker_chooses_the_tier_by_total_memory`, parametrized Darwin/Linux over: 16,179 MiB
    total with 9 GB free → Bonsai 128K, cache 4,096, Qwen; 7,800 total with 5.5 GB free → Bonsai
    32K, cache 1,024, Qwen; 3,800 total with 2.6 GB free → Bonsai 32K, cache 512, `qwen=none`,
    exit 0; 1,900 total → exit 3; a tier whose models don't fit what's free → exit 3. The
    `.env.runtime` written holds exactly the tier's context and cache; no Qwen start on the 4 GB
    tier (the systemctl/launchctl stub's calls).
  - `test_setup_downloads_no_qwen_on_a_bonsai_only_machine` (nproc/memory stubs, curl counts).
  - `test_the_setup_job_has_no_user_root_drop_in` and every other AI unit has one.
  - In `services/ai-service/tests/`: ready with only a reasoning model when the selection names no
    embedding model; not ready when the selection names one that doesn't answer;
    `/v1/embeddings` → 503 `no_embedding_model` without one.
  - The tier table's invariant: thresholds increasing, contexts never decreasing, every row's
    reserved figures defined.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Gates**, the service's own (`cd services/ai-service && uv run ...` per its README)
  and the repository's; every new Ansible conditional proven in real Ansible or the Debian container.
- [ ] **Step 5: Checkpoint.**

---

### Task 12: CI runs the Ansible checks (the owner, 2026-11-19)

**Files:** `pyproject.toml` (a dependency group holding `ansible-core`), `uv.lock`, the SBOM
(`docs/sbom.cyclonedx.json`, regenerated by `nox -s security-scan`), `.circleci/config.yml`
(install `iproute2` and `lsof` in the Linux test image or job), tests/test_ci_config.py if it pins
the job's packages.

- [ ] `ansible-core` in a development dependency group the test runs install (check how
  `uv sync --all-groups` and the CircleCI jobs install groups), so
  `test_every_playbook_passes_ansibles_syntax_check` and the role-file check run in CI instead of
  skipping; the license check accepts it (GPL-3.0; it is a development tool, not shipped — if
  `scripts/check_licenses.py` refuses it, report that to the owner rather than adding an exception).
- [ ] `iproute2` and `lsof` in the CircleCI Linux image, so the real-socket port test runs there.
- [ ] `nox -s security-scan` regenerates the SBOM; commit it with `uv.lock`.
- [ ] Show the two test groups no longer skip on Linux (a `nox -s test-linux-ci` run if it is
  practical here, or the CircleCI run after the owner pushes).

---

### Task 13: Removing the package names other users' leftover AI data (the owner, 2026-11-19)

`apt remove` never touches a home (Debian convention), so every other user's
`~/.local/share/glitchygames/ai` (models of about 1.4 GB, keys, settings, history) stays, and
their `uninstall-user.sh` goes with the package. The owner chose a notice, never a deletion.

**Files:** `ansible/roles/ai_package/templates/deb-postrm.sh.j2` (or prerm, whichever still has
the user list when it runs: decide and say), its tests in tests/test_ansible_ai_service.py, the
design's §6.7 and §13.1.

- [ ] On `remove` and `purge`, the script finds every local user (from `/etc/passwd`, UID in the
  login range) whose user root exists — `${XDG_DATA_HOME:-$HOME/.local/share}/glitchygames/ai`, and
  the cache and state folders — and prints, per user: the folder, its size (`du -sh`), and the
  command that deletes it (`rm -rf <folder>`), plus one line that nothing was deleted. Nothing
  printed when no user has data. It reads no secret file (sizes only) and exits 0 whatever happens
  (a maintainer script failure must not block dpkg).
- [ ] Tests: users with and without data (a fake passwd and homes under tmp_path); the folders
  and sizes named; nothing deleted (bytes unchanged); exit 0 when `du` fails; nothing printed on
  `upgrade`. Prove the rendered script once in the Debian container (a real `apt remove` of a
  small test package, or `dpkg -r` in the existing check_package.sh flow).

---

### Task 10 (after the power fix; the owner runs or authorizes it): first install and validation on the Pi (§8.3)

Not code. On the 16 GB Ubuntu Pi 5, once `vcgencmd get_throttled` stays `0x0` under a full
benchmark:

- [ ] `ansible-playbook -i ansible/inventory.yml ansible/ai_service.yml -K --limit <16 GB Pi host>`,
  with the owner's Ansible (ansible-core isn't a project dependency; see the design's 13.1); expected: the `.deb` builds,
  installs, `setup.sh` completes, the smoke test answers.
- [ ] `uv run nox -s deb-package -- <the .deb copied from the Pi>`.
- [ ] `THREADS=1,2,3,4 scripts/raspberry_pi_llama_cpp/benchmark_llama_cpp.sh ~/ai-spike cpu`;
  record speeds, answers, memory and the variant (`armv8.2_2`).
- [ ] The owner's placement: the models on cores 2-3, a game on the real display on core 0, an
  uncapped headless golden replay standing in for the mirror on core 1; the game's p50/p95/p99
  frame times and audio underruns against `--no-ai`.
- [ ] On the installed service: `systemctl --user show <model unit> -p CPUAffinity -p CPUWeight`
  gives `2 3` and `20`, the API unit `2 3`; `taskset -cp <llama-server pid>` gives `2,3`; with a
  game running, `taskset -cp` on each of its threads (`/proc/<pid>/task`) gives `0`.
- [ ] Replace the provisional Linux reserved-memory figures (Bonsai's and Qwen's) in
  `group_vars/linux.yml` with ones measured at the q8_0 cache; the owner sets the go/no-go bar (§8.3).
- [ ] On the Mac: `--tags ai_validate` with the q8_0 cache, every Bonsai size and Qwen; replace
  `ai_service_bonsai_reserved_mib` and `ai_service_qwen_reserved_mib` with the new figures and check `ai_service_bonsai_tiers`
  against them; the three smoke answers right; speed against the f16 figures (§6.5).
