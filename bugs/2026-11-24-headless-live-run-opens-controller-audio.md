# A Live --headless Run Can Use the Controller's Microphone and Speaker

- **Description**: Under `--headless`, SDL's dummy drivers cover the display and the mixer. The
  controller's microphone and speaker are reached through `miniaudio` and `hid`, which those drivers
  do not cover: a live `--headless` Brave Adventurer looks for them at start, writes the DualSense's
  speaker report over HID, and a mic press would start capture.
- **Reproduction**: Reproduced 2026-11-24 at `5006bcb6` (macOS arm64, Python 3.15.1, pygame-ce
  2.5.8, SDL 2.32.10) in child processes on the dummy drivers, with `HOME`, the sound cache root and
  the AI install root in a scratch folder.
  - `miniaudio` and `hid` were replaced by stand-in modules that list one device named `DualSense
    Wireless Controller` and log their calls, so no device was touched. Brave Adventurer,
    `--headless --no-ai --record-trace`: logged `miniaudio.Devices()` twice, `hid.device.open(0x54c,
    0xce6)` and one HID write of 63 bytes.
  - The same recording replayed headless: matched 60 frames and logged none of them (Brave's own
    check, BUGS.md #208).
- **Status**: Open
- **Priority**: Medium. Nothing plays or listens until a mic press, but `--headless` promises no
  sound and no device; one game alone guards replays.
- **Root Cause**: `ControllerAudio.discover` (`src/glitchygames/audio/controller_audio.py:861`) and
  its constructor (`mi.Devices()` at 422, `enable_dualsense_speaker` at 443, capture at 490) have no
  test of the mode. The one guard, `BraveAdventurerScene._discover_voice_assistant`
  (`src/games/brave-adventurer/src/brave_adventurer/game.py:87`), asks only whether the devices are
  live, which a `--headless` run's are.
- **Test gap**: `TestVoiceAssistantNeverStartsInAReplay` covers the replay; nothing starts the
  assistant in a live `--headless` run with the modules replaced.
- **Solution**: Not chosen. Options, all unproven:
  - An engine property, read by `ControllerAudio` and `VoiceAssistant`, that is False for a headless
    run, a replay and an inner game.
  - A door for controller audio, with a stand-in in a replay (needed for recording the voice answers
    too).
- **Known limits**: The capture itself was not run (it needs a mic press). A device in both
  miniaudio's capture and playback lists is taken for a controller, so any USB headset can be found
  here; that was read.
- **Sweep**: Covered: `ControllerAudio`, `VoiceAssistant` (Brave is its only user). Read: text to
  speech (`src/glitchygames/audio/tts.py`) runs a `say` child and is reached only through the
  assistant; Bitmappy's voice recognition has no caller.
- **Related**: [No real
  stimulus](../plans/lucid-circuit-4b-mirror.md#no-real-stimulus-the-owner-2026-11-24) in the
  mirror's plan.
- **Reporter**: The mirror game's hardware inventory, the coordinator
- **Date Reported**: 2026-11-24
- **Files**: `src/glitchygames/audio/controller_audio.py`,
  `src/glitchygames/audio/voice_assistant.py`,
  `src/games/brave-adventurer/src/brave_adventurer/game.py`
