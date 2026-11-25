# Every Engine Start Runs uname and file, Starts Joysticks and Loads Device Libraries

- **Description**: Starting the engine, in a live run, a `--headless` run or a replay, spawns `uname
  -p` and `file -b <python>` on macOS, starts SDL's joystick subsystem and imports `hid`,
  `miniaudio`, `speech_recognition`, `pygame.midi` and its PortMidi module. A replay asks for none
  of them.
- **Reproduction**: Reproduced 2026-11-24 at `5006bcb6` (macOS arm64, Python 3.15.1, pygame-ce
  2.5.8, SDL 2.32.10) in child processes on the dummy drivers, with `HOME`, the sound cache root and
  the AI install root in a scratch folder.
  - The game is a throwaway scene of one 4x4 sprite that quits itself at frame 90 and moves the
    sprite when the branch is taken; it is recorded with `--headless --no-ai --record-trace
    run.jsonl.gz` and replayed with `--headless --replay-trace run.jsonl.gz`. An audit hook on
    `subprocess.Popen` in the replay listed `uname -p` and `file -b .../python3.15`, and nothing
    else. At the end `pygame.joystick.get_init()` was True and `pygame.midi.get_init()` False.
  - `sys.modules` right after `from glitchygames import engine` held `hid`, `miniaudio`,
    `speech_recognition`, `pygame.midi` and `pygame.pypm`.
  - With the recording itself (`--record-trace`) the engine also runs `git`, `sysctl` and `pmset`
    for the source revision and the machine's facts (meant to, once a recording).
- **Status**: Open
- **Priority**: Low for a live run; a blocker for a mirror's 'no child process' guard, which would
  refuse the engine's own start.
- **Root Cause**: `print_system_info` (`src/glitchygames/engine/game_engine.py:2018`, called at
  1802) calls `platform.platform()` (2025) at any log level, as its arguments are evaluated.
  Joysticks: `pygame.init()` (1682) and `pygame.joystick.init()`
  (`src/glitchygames/events/joystick.py:386`). Imports:
  `src/glitchygames/audio/controller_audio.py:42`, 47, 52,
  `src/glitchygames/audio/voice_assistant.py:32`, `src/glitchygames/events/midi.py:36`.
- **Test gap**: No test asserts what an engine start spawns, starts or imports; the harness turns
  the macOS joystick drivers off (`tests/sdl_defaults.py`).
- **Solution**: Not chosen. Options, all unproven:
  - `platform.system()` and the like instead of `platform.platform()`, or log it only when the level
    asks for it.
  - SDL's joystick hints off before `pygame.init()` in a headless replay (the inventory measured two
    fewer threads), or init the modules by name.
  - Import `hid`, `miniaudio`, `speech_recognition` and PortMidi on first use.
- **Known limits**: The programs are macOS's (other platforms were not run). With a controller
  plugged in, what SDL opens was not measured.
- **Sweep**: Covered: every child the audit hook saw at a start. Not covered: C code (SDL,
  CoreAudio), which the hook can't see. Not a replay's: `src/glitchygames/replay/processing.py:56`,
  also `platform.platform()`.
- **Related**: [No real
  stimulus](../plans/lucid-circuit-4b-mirror.md#no-real-stimulus-the-owner-2026-11-24) in the
  mirror's plan.
- **Reporter**: The mirror game's hardware inventory, the coordinator
- **Date Reported**: 2026-11-24
- **Files**: `src/glitchygames/engine/game_engine.py`, `src/glitchygames/events/joystick.py`,
  `src/glitchygames/audio/controller_audio.py`, `src/glitchygames/audio/voice_assistant.py`,
  `src/glitchygames/events/midi.py`
