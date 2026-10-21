# Future Work Backlog

Suggested during the `feature/debug-overlay`, `feature/engine-world-space` and
`feature/gameplay-replay` sessions (2026-10-17 to 2026-10-20) and not done yet. One line per item, with where it is detailed. Review, then promote items into
`plans/engine-audit.md`, a plan, or BUGS.md, or delete them.

## Gameplay replay wrap-up (needs the user)

`feature/gameplay-replay` is done, reviewed and committed (97 commits on `80134d1` up to
`34c99ff`, the 2026-10-20/21 close-out), not pushed. What is left waits on the user:

- ~~**Decide `--rebaseline`'s exit code when input was not delivered.**~~ **Done** 2026-10-20
  (the user chose a new code): `ExitCode.REBASELINE_INPUT_LOST` (7); NEW is still written, and
  differing frames alone still exit `SUCCESS` (`ReplayResult.has_lost_input`).
- ~~**Delete the stale `glitchygames.egg-info/`**~~ **Done** 2026-10-20 (BUGS.md #78).
  `game_entry_point`'s search of every installed distribution in
  `glitchygames/testing/replays.py` is kept as a guard against the next stray egg-info.
- **The final review fix round's behaviour decisions** (reviewed with the user 2026-10-20):
  - A game's own `sys.exit(0)` during `--rebaseline`: **changed**; it writes NEW and exits
    `REBASELINE_INPUT_LOST` (a plain replay still exits `REPLAY_DIVERGED`).
  - Held keys record their key codes, no format bump (BUGS.md #83): **kept**; `ActionMap`
    gained scancode bindings (see Input).
  - Saves snapshotted as first opened only for `--record-trace` runs: **kept**.
  - Unwritable outputs refused before the run with `CANNOT_WRITE_OUTPUT`: **kept**, and a
    mid-run write failure now exits `CANNOT_WRITE_OUTPUT` too (BUGS.md #82, fixed).
  - Rumble caching joystick handles per count, and playbacks never rumbling: **kept for now**;
    the user chose the rumble door (Gameplay replay, below), which replaces both.
  - A recorded run's wall clock is `recorded_at` plus the frame clock: **kept**; the
    processing-time comparison was built instead (below).
  - Live supervisors' posts made during a scope are re-posted after it, behind the events the
    scope held: **kept** (it is what lets a supervisor end a playback and then post).
- **Push the branch, open the PR and merge it with GitHub's "Squash and merge"** (the user's
  workflow: no squashing in the branch, so no backup branch is needed). GitHub makes one
  commit on `main` and leaves the branch's commits alone, so the hashes BUGS.md, this file and
  the plans cite (`fead138`, `77ed933` and others) stay valid while the branch exists, and on
  the PR's Commits tab after the branch is deleted.
- ~~**Delete the plan workspace**~~ **Done** 2026-10-20, after an audit put everything worth
  keeping into the plans, docs and module docstrings (the plans stay in `plans/`).
- ~~**Review and commit the close-out fixes**~~ **Done** 2026-10-21 (`34c99ff`): BUGS.md #79,
  #82 and #84, the scope's joystick rumble, `REBASELINE_INPUT_LOST` and
  `PROCESSING_SLOWER`, content hashes and measurement history, scancode bindings (the golden
  fixtures and bundled demo patched and rebaselined), and certifi 2026.10.19 for
  PYSEC-2026-4320.
- Bugs logged on the branch and still open: BUGS.md #83 (a documented limitation).

## Input

- ~~**Move the example games' positional keys to scancode bindings**~~ **Done** 2026-10-21:
  every control of PaddleSlap (paddles W/S and Up/Down, pause Space), Clockwork Keep and both
  Brave Adventurer editions (movement, jump, interact, run, pause Esc, quit Q) binds a physical
  position (`scancode=pygame.KSCAN_*`; pause and quit too, at the user's call: Q is then the key
  in QWERTY's Q place, A on AZERTY). Fabricated key events (the golden scripts' `press`/`release`, tests)
  take their key's US QWERTY position from `glitchygames.testing.keys.qwerty_scancode`
  (name-based, the same on every machine; it matched this machine's keymap for every key the
  scripts use). The golden replay fixtures and the bundled demo were patched in place (each
  recorded key event given its position; a one-off check proved nothing else changed), not
  re-recorded, and `ScriptedInputSupervisor` posts with `post_input_event`. Later: a rebind
  screen saving `ActionMap.to_dict()` (it already round-trips scancodes).

## Bugs found and not fixed yet

| Item | Where | Notes |
|---|---|---|
| Undoing an animation delete loses its per-frame hitboxes and rebuilds frames on surfaces without SRCALPHA (alpha lost); frame-add and animation-create undo captures still copy `frame.pixels`, which is fragile | `glitchygames/bitmappy/history/commands.py` | Found while fixing BUGS.md #53; same family as #51/#53. |
| `CollisionManager.check_overlap` computes each sprite's rect once per pass, so a callback that moves a sprite leaves later pairs using its old rect | `glitchygames/collision/layers.py` (documented in the docstring) | Harmless in PaddleSlap; matters for generic reuse. |
| Frame-anchor reference cache doesn't notice a frame hitbox edited in place (only frame add/remove/replace) | `glitchygames/sprites/animated.py` (documented) | Nothing edits in place today. |
| Frames loaded from TOML keep magenta (255, 0, 255) opaque (no colorkey, alpha 255), so the visible-pixel hitbox fallback of a magenta-keyed sprite is its whole frame (ghosty: `Rect(0, 0, 32, 32)`) | `glitchygames/sprites/animated.py` (loader), `glitchygames/collision/bounds.py` | Found while testing the viewport-save hitbox rule; confirm whether games rely on explicit hitboxes or set a colorkey themselves. |
| A real AI request has not been run in the packaged binary (needs an API key or network) | `dist/bitmappy` | Do once by hand to fully close BUGS.md #47. |
| `scripts/raw_sprite_loader.py` cannot start: `BitmappyLegacySprite` calls `Sprite.__init__` without x and y, and `inflate` draws zero-size rects (nothing) | `scripts/raw_sprite_loader.py:~41, ~84` | Found while deleting `legacy_sprite_loader.py` (BUGS.md #46). Tests use only its `deflate`; fix or fold into Galimore import (sub-plan E). |
| `FrameAddCommand._add_frame` copies pixels through `PixelArray.flat` (pygame-ce has no `.flat`), so undoing a frame delete / redoing a frame add fails whenever the frame has pixels | `glitchygames/bitmappy/history/commands.py:~512` | Same bug fixed in `AnimationAddCommand` for BUGS.md #51 (use `SpriteFrame.set_pixel_data`). |
| Undoing an animation delete restores the sprite data but only refreshes existing film strip widgets, so the restored animation appears to get no film strip until strips are rebuilt (`on_sprite_loaded`) | `glitchygames/bitmappy/history/commands.py` (`AnimationAddCommand._add_animation`) | Found while fixing BUGS.md #51; not checked in the running app. |
| The animation-delete undo capture keeps frame pixels and durations but not per-frame hitboxes | `glitchygames/bitmappy/film_strip_coordinator.py` (`_capture_animation_deletion_for_undo`) | Found while fixing BUGS.md #51. |
| PaddleSlap's `_separate_overlapping_balls` runs after wall and paddle handling, so a ball can sit 1–3 px inside a paddle or past a wall for one frame | `glitchygames/examples/paddleslap.py` | Pre-existing, self-correcting next frame. |
| Papyrus sprites keep their unscaled native rect size | BUGS.md #59 | Latent; fixing it needs its own golden expected-difference class. |
| Brave Adventurer's ground and walls stay drawn only because the parallax layers dirty the whole screen | BUGS.md #60 | Fragile; make the terrain `dirty = 2` or document the dependency. |
| Brave Adventurer's and Papyrus's enemies (Cobra, Scarab, Scorpion) still draw in `update()` | `examples/brave_adventurer/enemies.py` | Harmless while their hitboxes do not depend on the pose (the scarab's bounds are the same at every roll angle); move drawing into `dt_tick` (the pose rule) if they ever do. |
| The multi-ball simulation tests write `ball.rect.x/y` for start positions and separations, which never took effect (the ball's position is `world_x`/`world_y`; rect was rebuilt from it, now by the engine), so every ball starts at its `reset()` serve position, not the drawn random one | `tests/game_objects/test_multi_ball_*.py` | Pre-existing test weakness found in feature/engine-world-space Task 9; set `world_x`/`world_y` instead and re-check the thresholds. |

## Engine roadmap (already in `plans/engine-audit.md`)

- ~~Engine world space (#6) with the `_finish_frame()` consolidation (#15)~~ **Done** on
  `feature/engine-world-space` (see `plans/engine-audit.md`).
- **Next: solid collision (#1) with the rest of balls on `CollisionManager` (#7).** Brave Adventurer
  and Papyrus now duplicate `_player_support_span` / `_entered_wall_from_left`; the solid-collision
  design should absorb them.
- **Level tools / Glitchy Studio (#11):** `plans/2026-10-18-level-tools.md` and sub-plans A–E
  (tilemap format with object layers, Mapsmith, Tilesmith, Bitmappy updates, Galimore import). Each
  needs a brainstormed spec before implementation.
- BUGS.md #19 (ruff PLW0717, 102 overly broad `try` blocks; rule temporarily disabled) is still active.

## World space follow-ups (feature/engine-world-space final review)

- **Clockwork Keep's start-of-scene camera swoop (game design decision):** at scene start the
  camera eases down from world y=0 to the tinker instead of starting on it. It was preserved on
  purpose during the migration so the golden traces match the baseline. A
  `self.camera.snap_to(...)` (or `snap_followed_axes_to`) at the end of `ClockworkKeepScene.setup()`
  would remove it; that changes every floor's opening frames, so it needs a golden
  expected-difference entry. Decide whether the swoop is wanted.
- **Review focus 3 gap:** no shipped game calls `snap_to` in `setup()`, so "a game that snaps in
  setup keeps doing so" is pinned only by `tests/world/test_camera_follow.py::TestSnapToThenAim`
  (function level) and, per game, by the golden traces. Add a frame-level test with a scene that
  snaps in `setup()` if a game starts doing it.
- **Review focus 4 gap:** int `world_x`/`world_y` and the missing-`world_y` `TypeError` are tested
  at function level (`tests/world/test_positioning.py`), not through `_run_scene_frame`
  (positioning calls the same function; acceptable, noted).
- ~~**Review focus 5 gap:** pacing re-anchor after a hitch proven only in the timer tests~~ Done:
  `tests/world/test_finish_frame.py::TestPacingAfterAHitch` runs `SceneManager.start()` with the
  real deadline policy and checks every frame after a 2 s hitch takes exactly one period.
- **WORLD shake, misuse ordering:** a game that calls `camera.update()` in the render phase
  (`update()`) while the engine also aims advances the shake twice that frame and gets no
  double-update warning (the aim ran first and saw no game update). Calls in `dt_tick` are
  handled (one advance, one warning). Remove such calls; consider warning from `update()` itself.

## Gameplay replay

- **Rumble door** (the user chose option c, 2026-10-20): rumble goes through the doors like
  events, saves and devices. Live sends to the real controllers; a recording also writes each
  send (`rumble_sent`: low/high levels, duration, target device) into its frame; a replay
  compares the sends with the recorded ones (a rumble regression is a divergence, as a sprite's
  is) and sends them to nothing or, in a watched replay, to the viewer's controller; a playback
  scope's policy decides per kind (instant replays may rumble, demos stay silent). The door
  owns the device mapping, which replaces the per-count joystick cache
  (`ConnectedRumbleDevices`) and the scope's asked-but-unused counts
  (`SceneManager._rumble_devices_for_scope`).
- **TODO (plan later): physical outputs as recorded events.** The user's direction
  (2026-10-20): an output such as rumble is both an event and a per-frame output record, so it
  can drive more than pygame/SDL (an Arduino over serial, other programmable devices) and leave
  a record of the physical behaviour for playbacks, devices and tools that post-process a
  session. Shape to plan:
  - Command events: a request to do something physical (rumble this controller at these
    levels for this long). Game code, or the game wrapper (the external control API), posts
    one; the engine intercepts the kinds it knows and translates them into the calls (the
    rumble door, a serial sink) instead of handing them to the scene. A wrapper's injected
    commands are input from outside the game, so they go through `post_input_event` and a
    replay serves them (BUGS.md #84's API).
  - Output record: what the engine actually did, per frame (`outputs`: kind, target, payload),
    written by the recorder, compared by a replay (an output regression is a divergence) and
    read by playbacks, devices and tools. A notification event of the same output lets game
    code or a wrapper react to it.
  - Sinks: pluggable per kind (SDL rumble, serial, MIDI out, OSC, DMX); a playback's policy
    picks which sinks it drives (rumble door, above).
  Other candidates worth recording the same way:
  - Haptics beyond rumble: trigger rumble and adaptive triggers (DualSense).
  - Controller lights: DualSense/DualShock light bar colour, player LEDs.
  - Audio cues: which sound or music started or stopped, on which channel, at what volume (audio
    regression checks; syncing lights or video to the game's sound).
  - Speech: text-to-speech lines and the DualSense speaker's audio.
  - Screen effects: shakes and flashes as they start (synced external lights; highlight reels).
  - Game milestones: score changes, lives lost, level start and end, achievements (`GAMEEVENT`
    today; analytics, highlight reels, the external control API's notifications).
  - Save writes: what was written and when (they are sandboxed in a replay; recorded, they could
    be compared).
  - Presentation changes: fullscreen, resolution and window changes.
  Input from such devices (an Arduino's buttons, MIDI in) would come back through the input
  door as device events, recorded as external input like a controller's.
- ~~**Content hashes and measurement history in recordings**~~ **Done** 2026-10-21 (design doc
  `plans/2026-10-20-recording-content-hash-and-history.md`, hashing option "Better"; plan
  `plans/2026-10-21-recording-content-hash-and-history-implementation.md`). The golden fixtures
  and bundled demo were rebaselined (the plan's Task 5, 2026-10-21) and carry one run each.
  Follow-ups: C12 through `recording_content_hash`; a git commit per run if the user decides
  for it; a CI processing-time check needs a baseline rebaselined on its runner (the fixtures'
  times are the developer machine's). A per-frame
  `content_hash` of everything the game did (times left out), and newest-first history lists
  across rebaselines (`processing_seconds`, `content_hash`, a header `measurement_runs`; depth
  constants starting at 10), so the baselines in the repo record behaviour and speed over time.
  The recording-level hash is derived from the frame hashes, not stored.
- ~~**Processing-time comparison**~~ **Done** 2026-10-20: `processing_seconds` per recorded
  frame, `--compare-processing` and `--max-processing-slowdown PERCENT` (exit
  `PROCESSING_SLOWER`, 8); contract in `glitchygames/replay/processing.py`, user docs in
  `docs/architecture/gameplay_replay.md`. Follow-ups: a CI job that keeps a baseline recording
  per runner and checks it; the golden fixtures and bundled demo hold no processing times until
  they are re-recorded (the scancode TODO's re-record would add them).
Design: `plans/2026-10-19-gameplay-replay.md`. Master plan:
`plans/2026-10-19-gameplay-replay-implementation.md`, with one sub-plan per part. User docs:
`docs/architecture/gameplay_replay.md`; engine summary in CLAUDE.md ("Clocks", "Gameplay Recording
and Replay").

- ~~**Part 1, replay core**~~ **Done** on `feature/gameplay-replay`
  (`plans/2026-10-19-gameplay-replay-core.md`): the doors (`glitchygames/sources.py`,
  `live_sources.py`, `RecordingSources`, `ReplaySources`), the clocks (`glitchygames/clock.py`,
  `Scene.game_time`), input snapshots, the devices and saves doors, the supervisor hook and
  control events, trace format 3, `--replay-trace`, `--replay-fps`, `--audit`, golden replay
  fixtures and the doors guard (`tests/test_engine_doors.py`). This replaces the old "Gameplay
  replay" entry; its items (wall-clock reads in gameplay, polled input, reference mapping) are all
  done.
- ~~**Part 2, replay tooling**~~ **Done** (`plans/2026-10-19-gameplay-replay-tooling.md`):
  `--headless` (Task 1: any run on SDL's dummy drivers; replays then run unpaced, print the
  divergence report and exit with `ExitCode` members; it replaced the private `--replay-unpaced`);
  watched replays (Task 2: the `ReplayViewer` outer loop at 60 Hz real time running the recorded
  game's frames from an accumulator, `ReplayControls` for Space pause / `.` step / `]` `[` speed /
  Esc quit with one action per press, the status bar, pausing at a divergence or the end with the
  debug overlay on, and the "Press Spacebar to Start Game Replay" start screen after frame 0 with
  the F3/F4 hint, drawn by the pause screen's `MessageScreen`; KEYDOWN/KEYUP stay unblocked at SDL
  and reach only the replay controls and the debug overlay); step back (Task 3: `,`, Home and D
  restart the replay process at a pause frame, `--replay-pause-at-frame N` rebuilding there
  unpresented and muted, the first process supervising later restarts through a handoff file).
  bookmarks (Task 4: B bookmarks the frame shown, S saves `x.bookmarked.jsonl.gz` with
  `breakpoint` control events that pause a watched replay of the copy; a restart with bookmarks
  saves and replays the copy); the pytest plugin for recordings (Task 5:
  `glitchygames/testing/replays.py`); `--rebaseline` (Task 6: `--replay-trace OLD --rebaseline NEW
  --headless` replays OLD's inputs on the current code without stopping at divergences, writes
  NEW atomically with OLD's inputs and the current sprites, prints a summary of the frames and
  sprites that changed and exits `SUCCESS`; `glitchygames/replay/rebaseline.py`).
- ~~**Part 3, in-game playback**~~ **Done** (`plans/2026-10-19-gameplay-replay-playback.md`):
  scene starts (`glitchygames/scene_start.py`, `replay_arguments`, `CAPTURES_SCENE_START`), the
  playback scope (`glitchygames/replay/playback.py`; does not block real input at SDL; real
  input reaches only its "exit playback" check), demos (`play_recording` and the bundled
  PaddleSlap demo, played by its game-over screen when idle, replay-tested by
  `tests/replay/test_bundled_demos.py`), instant replay (`glitchygames/instant_replay.py`,
  `INSTANT_REPLAY_SECONDS`, `end_playback` from a supervisor, repeated replays through the
  resume bridge) and ghosts (`glitchygames/replay/ghosts.py`).
- **Plain recording over a replay (`--record-trace` with `--replay-trace`) stays refused**
  (`ExitCode.OPTIONS_REFUSED`, 64; `GameEngine._refuse_an_unsound_recording_over_the_replay`),
  pointing at `--rebaseline NEW --headless`, which wires `ReplaySources.last_batch_origins()` and
  `ReplaySources.recording.recorded_frame_fields()` into `RecordingSources` (`replayed=`). A
  watched rebaseline (or `--record-trace` over a watched replay) would need the viewer's held
  frames and keys kept out of the recording; open it only if a use appears.

Follow-ups (not in any plan yet):

- **State snapshots:** serialize game state for fast step-back and instant replay of long
  scenes; today both re-simulate from the scene's start (spec, out of scope). A watched replay's
  step back restarts the process and rebuilds every frame up to the pause frame; an instant
  replay re-simulates the whole scene, so it is refused past
  `MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS` (60 s) and its journal (about 0.5-1.5 MB per minute)
  is dropped then. Snapshots every N seconds would bound both to N seconds of re-simulation and
  let the journal drop frames before the latest snapshot; rollback netcode needs the same.
- **Cheat device spec:** cheatable-field declarations, codes and UI. It plugs into the supervisor
  hook (`SceneManager.add_supervisor`: it runs after the frame's logic and events, so a change
  is drawn that frame and seen by collision on the next) and records each action as a control
  event (`record_control_event(kind='cheat', data=...)`), which a replay must re-apply on the
  same frame: add its kind to `REAPPLIED_CONTROL_EVENT_KINDS` (glitchygames/supervision.py),
  as `breakpoint` is, and apply it in a control event handler. Its reads should go through the
  same named fields the external control API would expose (spec section 2, out of scope).
- ~~**Supervisor posts outside a playback scope** (BUGS.md #84)~~ **Done:**
  `recording.post_input_event` (recorded as external input; every replay serves it). Left: a
  `--replay-trace` of a session whose live supervisor posted during a scope still needs that
  supervisor in the replay (`replay/playback.py` Limits): the scope's pump would have to use
  the installed replay's batch origins to tell a served input post from a scope post.
- ~~**Joystick-mode rumble inside a scope**~~ **Done:** each send asks the scope's devices door
  (a device cache of its own, so the live one is untouched) and rumbles no device. Left: the
  scope's rumble controller starts fresh, so its sends can fall on other frames than the
  recording's (documented in `replay/playback.py` Limits).
- **"Take over" handover:** let the player take control part way through a replay. It must end or
  suspend the SDL input block at the handover and switch the doors from recorded to live input.
- ~~**Audit test helper suppressions**~~ **Done:** every child process, the tests' included,
  starts through `glitchygames.process.run_command`, the one `subprocess` suppression.
- Deferred review notes still open: no test pins the first FPS log waiting one interval;
  `selection.get_state_summary` can return `-inf` for `last_update_time` (not strict JSON);
  `ControlEvent` is unhashable; `tests/test_tracing.py`'s `test_unknown_version_is_refused`
  duplicates `test_unknown_format_version_is_rejected_on_open`; `glitchygames/tracing.py` uses
  `cast('int', format_version)` where narrowing would do; `open_controller`'s
  `controller.quit()` inside its `except` (`glitchygames/input/devices.py`) could hide the
  original error if `quit` itself raises; a save's metadata `version` 1.9 is accepted as 1
  through `int()` (`glitchygames/state/manager.py` `_metadata_version`, pre-existing). Resolved by Part 3: `push_scoped_sources` refuses the installed
  sources (`SourcesAlreadyInstalledError`), so `reset_sources` never uninstalls one object
  twice; `start_trace_recording` can only run before the first frame (`install_sources` raises
  `SourcesAlreadyRunningError` after it), when no playback scope can be active, so it always
  wraps the installed doors.
- Bugs found during the replay core and not fixed (BUGS.md, Active): #67 (Bitmappy's
  joystick-event trigger conversion assumes pygame 1's integer axis scale), #68
  (`ControllerEventManager` keys controllers by device index but routes events by instance id),
  #72 (`MultiControllerEnhancements` stores a duration where a timestamp is expected), #73
  (PaddleSlap sets the `game` logger to INFO at import), #74 (`debug_events` is always False),
  #75 (`pygame_needs_fastevents` compares major and minor separately).

## Headless capture to raw files and a frame/audio ready latch — groundwork for an external control API

User request (2026-10-19). Not planned yet; needs a brainstormed spec. Each part below is a
candidate ticket. The fuller design notes (lossless A/V streaming as its own API separate from the
event/state stream, the packet format, transports, and what to reuse from the replay engine) are in
[`plans/2026-10-20-av-capture-and-streaming.md`](2026-10-20-av-capture-and-streaming.md).

### Headless capture (`--headless DIR`)

- `video.raw`: every presented frame appended as raw RGBA, plus a small sidecar (for example
  `video.json`) giving width, height, pixel format and frame count, so it can be piped to
  `ffmpeg -f rawvideo -pixel_format rgba -video_size WxH -framerate N -i video.raw ...`.
- `audio.raw`: the mixer's final output as raw PCM, 44100 Hz, signed 16-bit, stereo (the engine's
  mixer format). The dummy audio driver plays nothing, so this needs a capture tap on the mix (see
  the latch section below for why a tap alone is not enough in lockstep mode).
- To consider: aligning the two streams by frame number; disk size (a 640×480 RGBA frame is
  about 1.2 MB, so about 74 MB per second at 60 FPS); frame-skip and downscale options.
- Builds on `--headless` (any run, not only replays; Part 2 Task 1 of the replay plans).

### One ready latch per frame (the frame is a packet)

Amended (user and controller decision): one latch tied to the frame, not separate "frame ready"
and "audio buffer ready" flags.

- Each frame is one packet: the presented picture plus exactly the audio that plays during that
  frame. The sample count comes from that frame's duration (about 735 stereo samples at 60 FPS;
  44100 / 60.01 = 734.9), with the fractional sample carried forward to the next frame so the
  stream never drifts.
- The engine sets the latch to 1 when the packet is written; the consumer reads the picture and
  the audio and writes 0.
- **Lockstep mode** (the engine waits for the 0 before the next frame; deterministic and complete,
  which is what an AI consumer needs) requires the engine to render each frame's audio slice
  itself: an offline, per-frame mixing path. pygame's mixer runs on its own real-time thread even
  with the dummy driver, so it cannot simply be tapped while the engine waits. The synth and
  live-voice code (`glitchygames/audio/synth.py`, `live.py`) already generates samples; sounds
  played through `pygame.mixer` (`SoundBank`, loaded sound files) would need the offline path too.
  **This is the main design question.**
- **Free-running mode** (the engine never waits): the latch covers frames only. Audio is a
  continuous stream in a ring buffer that the consumer reads at its own pace, with no audio latch.
- Transports to compare: shared memory or an mmap'd file, a local socket, the API. Exposing the
  latch through an API is a later ticket.

### External control API (brainstorm)

- **Observe:** raw pixels (full or downscaled); sprite state as data (the trace sample,
  `glitchygames.tracing.sample_scene_frame`); declared game state such as score, lives and level
  (shared with the future cheat device's named fields); the frame's audio packet and the sounds and
  voices started this frame; frame hashes (`glitchygames/replay/audit.py`'s `frame_digest`).
- **Act:** input injection through the doors, as an "external input" source alongside live and
  replay (`glitchygames/sources.py`); scripted supervisor actions at the existing hook
  (`glitchygames/supervision.py`); time control (pause, step, speed, reset with a seed); save and
  load state (needs state snapshots); scene control.
- **Output:** draw pixels, lines, rects, text and sprites to an overlay layer that is never in
  traces unless asked for; play a voice from a waveform equation or a preset, with duration, pitch
  curve and envelope, through the synth toolkit and live voices; speech through TTS; rumble and
  LEDs.
- **Recording:** start and stop `--record-trace`, fetch the recording, replay it, run `--audit`.
- **Shape:** a Gymnasium-style environment wrapper, `reset(seed)` and
  `step(actions) -> (observation, reward, done, info)`, built on lockstep mode and the seeded
  doors. Transports: shared memory locally, WebSocket or HTTP remotely. Check what
  `glitchygames/api/` already provides (today a FastAPI server and client for AI sprite
  generation, `glitchygames-server` / `glitchygames-client`). Security: authentication for remote
  input, rate limits, a read-only spectator mode.

### Where it leads (later epics)

- AI players and testers, whose runs are replayable and auditable.
- Twitch Plays: chat mapped to input, with voting or anarchy modes and per-viewer cooldowns,
  streamed from `video.raw` / `audio.raw` through ffmpeg.
- Remote multiplayer: lockstep input sync on the deterministic doors, checked with frame hashes.
  Rollback netcode needs state snapshots, the same prerequisite as fast step-back and long instant
  replays.
- Spectating by streaming recorded inputs.

### Prerequisites already built (replay Part 1)

The doors, deterministic simulation, recordings, the supervisor hook, the input-blocking helper
(`glitchygames/replay/input_blocking.py`), the golden fixtures and `--headless` (any run, not
only replays; Part 2 Task 1).

## Trace format ideas (pending a user decision)

- **A later trace format version (v4; v3 is the replay format):** record each world sprite's world position and snap mode, and the camera
  position and WORLD shake offset, in every frame. Today traces hold only rect and visibility, and
  the golden test samples world and camera positions from the live run (`WorldSampler` in
  `tests/world/test_golden_traces.py`), so a baseline cannot be checked against its own world
  state.
- **Camera-relative traces:** record world sprites in world coordinates (or relative to the
  camera) instead of screen rects, so a change to camera smoothing alone shows up as one camera
  difference rather than as a difference on every sprite.

## Bitmappy

- All Galibmap/GEDIT-derived features (hitbox editor, mirror/rotate, replace colour, colour wells,
  directional templates, tile mode, frame alignment, metadata panel, magenta-key decision):
  `plans/2026-10-18-level-tools-d-bitmappy-updates.md` (D1–D10).
- `plans/future-features.md` (the older feature roadmap, moved from the repo root on 2026-10-18):
  its item 38 (frame alignment command) duplicates plan D's D8.

## Performance and pacing

- Cull pickups by distance before `check_overlap` (Brave Adventurer checks all 46 collectibles per
  frame; each now measures visible pixels, ~0.15 ms/frame). Final review M5.
- Vsync-locked presentation to remove the remaining beat between 60.01 FPS and a 60 Hz display.
- Deferred from the screen-shake spec (see its known follow-ups in
  `plans/2026-10-17-screen-shake-and-synth.md`): the audio probe capture mode and the spin-window
  power idea.

## Assets and art

- Ghosty sprite: frames 1–7 have inferred outer outlines; canvas screenshots of each frame would
  make them exact (`examples/resources/sprites/ghosty.toml`).
- Papyrus player art could be redrawn bottom-aligned, after which `frame_anchor` is unnecessary.

## Galimore

- Summary of the 1998–2001 Galimore code and tools: `docs/galimore.md`.
- Review the survey's read-only decoder (`galimore/tools/galimore_decode.py`) before reusing it in
  sub-plan E.
- Not extracted: the Mac sound resource forks, three nested 2000-04-17 editor zips, and a few files
  with non-ASCII names.
- Do not redistribute the FF3 reference tile rips or the third-party sound samples from the archives.

## Developer environment

- Dropbox syncing test artefacts made the suite run in 10 minutes instead of 46 s. If Dropbox stays
  on, mark `test-results/`, `.coverage*`, `.venv` and cache directories as ignored
  (`xattr -w com.dropbox.ignored 1 <path>`).
- Optional: lazy-import `speech_recognition` so the audio import chain doesn't load `aifc` (its
  deprecation warning is already filtered in `pyproject.toml`).
- ty reports 50 pre-existing `unused-ignore-comment` warnings (identical on main).

## Code quality

- **Lint caps shape the replay classes.** `GameEngine.__init__` and `ReplaySources.__init__`
  sit at the statement limit, `ReplaySources` and `PlaybackSources` at the public-method limit
  (PLR0904), and `GameEngine.start` at the complexity limit. Several shapes come from that:
  `decoded_replay_sources` is a module function, bookmarks save through a collaborator
  (`sources.bookmarks.save()`), `is_fast_forwarding` is a plain attribute, `record_frame`'s
  optional fields are `TypedDict`/`Unpack` keywords, and the processing collector rides on
  `ReplayResult`. The next change to these classes hits the same walls; split them (with the
  SceneManager extraction below) rather than squeezing more in.

- **Extract the playback scope's bookkeeping out of `SceneManager`** (final review of
  `feature/gameplay-replay`, item C6; deferred). `glitchygames/scenes/scene.py`'s `SceneManager`
  carries the scope's entry and exit (`_enter_playback`, `_exit_playback`, the stashed live rumble,
  scope-owned supervisors and handlers, discarded scope posts) and the instant-replay journal's
  begin/resume/journal steps. Split them into collaborators the scene manager calls at fixed
  points: a `PlaybackScopeController` (enter, exit, ownership of what the scope's code adds) and a
  `JournalKeeper` (the journal's lifecycle). The two-sources-of-truth bug the review found is
  fixed (`SceneManager.in_playback_scope` is the one answer); this is the structural follow-up,
  with no behaviour change (the replay, playback and golden tests must pass unchanged).
- **A content hash of the played recording in the `playback` marker** (final review, item C12;
  optional, not done). Adding `recording_sha256` (of a demo file's bytes) to the marker's data would
  make a session replay whose demo was re-recorded since diverge at the scope's first frame, naming
  the cause, instead of at a later sprite. Needs the marker's shape changed in
  `glitchygames/recording.py`'s docs and the tests that assert it; instant replays (in memory, same
  run) gain nothing from it.
- **Audit dataclasses for conversion to pydantic** (user request, 2026-10-20; lean yes unless there's
  a good reason not to). `glitchygames/` has ~49 `@dataclasses.dataclass` structures across ~30 files
  (`git grep -n "@dataclasses.dataclass\|@dataclass" -- glitchygames`). New data classes already use
  pydantic `BaseModel` (frozen where immutable, `extra='forbid'`; house style in
  `glitchygames/api/models/sprite_models.py` and `glitchygames/bitmappy/models.py`). For each existing
  one, decide convert or keep and record why:
  - Convert by default — validation at construction and JSON serialization for free; highest value
    first: replay and recording data (`glitchygames/replay/`, `recording.py`, `input/state.py`
    `InputSnapshot`, `input/devices.py` descriptors and enumeration answers, `supervision.py`
    `ControlEvent`), configuration (`services/config.py`), save data (`state/`).
  - Good reasons to keep a dataclass: a per-frame hot path where pydantic construction cost is
    measurable (benchmark first — `InputSnapshot` is built once per frame; `effects/shake.py` and
    `input/action_map.py` run per frame); identity/mutation semantics pydantic would change (custom
    `__eq__`/`__hash__`, `cached_property`, deliberately mutable state); trivial private helpers.
  - Keep behaviour identical: equality, hashing, ordering, defaults, immutability, and any JSON shapes
    already written to recordings or saves (golden traces and golden replay fixtures must stay
    unchanged).
  - Output: a short table (class, file, decision, reason, benchmark if any) in this file or the task
    report, then the conversions in reviewed commits.
- **Move the package to a `src/` layout** (user request, 2026-10-20): `glitchygames/glitchygames/` →
  `glitchygames/src/glitchygames/`. Why: tests and scripts then import the installed package (via
  `uv sync`), never a stray copy from the repository root, which catches packaging mistakes (missing
  package data, wrong includes) before release; it is the layout the Python Packaging Authority
  recommends. Things to move or update together, in one reviewed change:
  - the build configuration in `pyproject.toml` (package discovery, package data such as fonts,
    sprites and TOML assets, console-script entry points) — this is build config, not lint config,
    but the ruff/pyright/ty/vulture/bandit/coverage path settings will also need `src/`; agree that
    with the user when the task starts (the standing rule is not to change linter or type-checker
    config without asking);
  - `noxfile.py` session paths and every documented command (`ruff format glitchygames tests scripts
    noxfile.py`, `vulture glitchygames …`), CI configs (CircleCI, GitHub Actions);
  - path-based code and tests: the doors guard (`tests/test_engine_doors.py` scans the package
    directory), the randomness guard, the recording guard, `glitchygames/sprites` asset lookups,
    bundled demos, golden harness and fixture paths, `scripts/` that reference `glitchygames/…`;
  - PyInstaller specs (`scripts/bitmappy.spec`, `glitchygames/bitmappy.spec`), mkdocs/mkdocstrings
    source paths, CLAUDE.md, docs and plans that name `glitchygames/...` file paths;
  - verify: `uv sync`, full suite, lint/type checks, mkdocs strict, `nox -s build` (wheel contents
    unchanged apart from paths; assets still included), golden traces and golden replay fixtures
    unchanged.
- **Lint ignores cleanup** (user request, 2026-10-20): planned in
  [`plans/2026-10-20-lint-ignores-cleanup.md`](2026-10-20-lint-ignores-cleanup.md) — dead ignores,
  50 unused `ty: ignore` comments, narrowing `S311`, the 100 broad try blocks (`PLW0717`, BUGS.md #19),
  `ANN401`, and a decision on `G004`.
