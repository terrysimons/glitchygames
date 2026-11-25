# pygame-ce's Mixer Frees a Live Voice's Queued Sound Twice

- **Description**: `tests/world/test_golden_traces.py::test_golden_script_recording_replays_without_divergence[mr_muncher]`
  segfaulted intermittently (exit 139; on origin/main 8 of 20 single runs). The crash was in
  `pymalloc` at the next `pygame.Rect` allocation (`pg_rect_new` → `_PyObject_Malloc`, address
  `0xffffffff`), long after the heap was corrupted. The test records one game, then replays a
  second in the same process. The recording game's Mr. Muncher projector (a live voice) was never
  stopped, and the replay game's projector started on the same mixer channel while that channel
  still played one chunk with another queued.
- **Status**: Fixed on `feature/mascot-demo` (2026-11-24). The pygame-ce defect itself is open
  upstream (below).
- **Priority**: High. Heap corruption in the engine's audio path: it crashed a golden test in up to
  half the group runs, and the corruption can also pass silently or hang.
- **Root Cause**: pygame-ce 2.5.8's `endsound_callback` (`src_c/mixer.c`) runs
  `Py_XSETREF(channeldata[channel].sound, channeldata[channel].queue)` and only then clears the
  queue slot. `Channel.play(C)` on a channel playing Sound A with Sound B queued calls it. When
  pygame's table holds the only reference to A, dropping A runs `sound_dealloc` → `Mix_FreeChunk`,
  and SDL_mixer halts the channel still playing A, calling `endsound_callback` again, nested. The
  nested call finds `sound == queue == B` with one reference between them and releases B; the outer
  path releases it again, so B is freed while the table still names it. It all happens on the main
  thread: re-entrancy, not a data race. Our side of it: `LiveStream`
  (`src/glitchygames/audio/live.py`) handed every chunk straight to `Channel.play` and
  `Channel.queue` and kept no reference of its own, so pygame's table held the last ones. The full
  triage, with the C stack of the second free and the probes, is in the Ledger's triage tools
  (`segfault-2026-11-24/triage-report.md`).
- **Test gap**: nothing played a Sound on a busy channel with one queued while pygame held the only
  references, so no test reached the re-entrant path. `golden_game` tore a game down without
  stopping its live voices, so one test's two games shared a playing channel, and nothing checked
  that pygame's channel table never outlives the Sounds it names.
- **Fix**:
  - **The root fix, for the whole class**: `LiveStream` holds its own reference to every chunk it
    plays or queues (`held_chunks`) and lets go of one only once its channel names it neither
    playing nor queued: after each `play`, `queue`, `update` and `stop_now`, never inside a pygame
    call. That keeps at most two (`MAXIMUM_HELD_CHUNKS`, one playing and one queued). A stream
    dropped without being stopped stops its channel first, if the channel still names one of its
    chunks, then lets go (`_let_go_of_chunks`, a `weakref.finalize` holding the channel and the
    list, not the stream). The holder is instance state, not module state.
  - **A stored channel is used only while pygame's table has it** (`_channel_in_the_table`,
    `_channel_table_slots`): pygame-ce 2.5.8's `Channel.get_sound` and `get_queue` index
    `channeldata` with no check that the mixer runs or the channel exists, and `chan_play`
    indexes it with SDL's -1 when SDL refuses the channel. A fresh `pygame.mixer.Channel(index)`
    checks init and range itself (`_channel_init` raises), so the hazard is only a stored
    `Channel` outliving a mixer quit or restart, and only `live.py` stores them. On a quit mixer
    the table is NULL; after a restart it has 8 entries, while an inner game's live pool sits far
    above that. Such a read crashed a test worker once while this fix was being built (a stream
    collected after a later test restarted the mixer). The table never shrinks, so a channel
    below `get_num_channels()` is inside it. Every table read in `live.py` goes through
    `_channel_table_slots`, and a stream whose channel is at or past `get_num_channels()` (a pool
    shrunk or a mixer restarted under it) is silent: it renders, plays and queues nothing.
  - **Explicit voice lifetime**: `SceneManager.terminate`, which every game end passes through
    (`end_frames`, `stop`, a QUIT), releases the live voices, persisting ones included. The
    finalizer stays as a backstop. It never raises (an exception in a weakref callback is only
    printed): it reports to its engine context's registry of live streams (`LIVE_STREAMS_SLOT`,
    `LiveStreamRegistry`: the context's streams held weakly, and a list of reports no logger
    level can filter) and logs `UNRELEASED_LIVE_STREAM_MESSAGE` as a warning.
    - A first version warned with a `ResourceWarning` instead. Under the suite's
      `filterwarnings = error` that raised inside the callback, and pytest reported
      `PytestUnraisableExceptionWarning` on whichever test the garbage collector ran in (seen
      in `tests/replay/test_instant_replay.py` and `test_playback_scope.py`).
    - Those were real missing releases in a test helper: `running_scene`
      (`tests/world/frame_harness.py`) never ended its game's audio. 13 more tests dropped
      their pools' voices unreleased before quitting the mixer. All of them now release.
  - **The harness teardowns**: `golden_game` and `running_scene` both end the game's audio
    through one step, `GoldenTraceSceneManager.end_game_audio`. It releases the live voices,
    then halts every channel twice. It is still needed: these harnesses step frames themselves
    and never call `terminate`. Voices go first because halting a channel with a chunk queued
    starts the queued chunk.
  - **The invariants across the suite**, in `tests/harness.py`, read after every test before the
    channels are silenced and reported after the rest of the teardown, so a failing check never
    leaves sound or drivers behind:
    - `queued_sounds_no_live_stream_holds`: a channel with a queue naming a Sound no live stream
      holds. A second queuer anywhere in the suite is caught.
    - `unreleased_live_stream_problems`: every stream of the current context still holding a
      chunk was never released, whatever its channel's state. The registry enumerates them
      exactly. A first version walked the garbage collector's referrers (Sound, then list, then
      stream). It went blind once a stream's `__dict__` existed (`mocker.patch.object`, `vars`,
      `copy` make it): the list's referrer is then that dict.
      - When the registry finds a stream, the harness collects the garbage (only then: a full
        `gc.collect()` costs about 44 ms a test), so a dropped stream's finalizer report lands on
        this test.
      - A report of a stream the registry did not find here is worded "collected during this
        test; leaked by an earlier test on this worker".
    - `end_of_test_sound_problems` gathers these and the silencing check, so no report is lost
      when the silencing check fails too.
    - **Limit:** the harness asks the current context's registry. A stream an inner context made
      (a test's `EngineContext(name='tile')`) is found only by the queue check, if it left a
      queue, and by its log report.
- **Sweep** (`git grep -n "\.queue(\|Channel(\|\.play(" -- src/`):
  - Covered by the fix: `audio/live.py`'s `LiveStream.start` (`Channel.play`), `LiveStream.update`'s
    underrun restart (`Channel.play`) and its `Channel.queue`. These are the only places in the
    engine and members that queue a Sound.
  - Not affected, no queue: `audio/voices.py`'s `VoiceTable` (`channel.play(voice.mixer_sound)`,
    library channels only, never queued). With nothing queued, the callback takes `Py_CLEAR`,
    which clears the slot before releasing, so a nested call finds nothing to release. Every member
    `.play()` on a sound (Mr. Muncher, Clockwork Keep, Brave Adventurer, Zombies Ain't My
    Neighbors, the Sound Board demo, paddleslap's and `game_objects/ball.py`'s collision sounds) is
    the engine's `Sound.play`, which goes through that table; `crt_power_on_sound.py` too.
  - Not affected, no play or queue: the other `pygame.mixer.Channel(...)` calls only read or stop
    (`audio/live.py` `take_channel`, `audio/voices.py`'s inner-game channel helpers,
    `audio/engine.py`, `replay/silence.py`). `Channel.stop()` takes the halt path, which does not
    re-enter (the triage's reproducer: no bad free in 3 of 3).
  - The rest of the hits are sprite animations' `play(name)`, not sounds.
- **Tests**:
  - `TestLiveStreamKeepsItsChunks` in `tests/audio/test_live.py`, on the real mixer (dummy driver):
    - `test_a_voice_started_over_another_voices_queued_chunk_frees_no_chunk_too_soon`: the
      reproduction's pattern through two live voices on one channel, with a weakref on the
      queued chunk. Before the fix it segfaulted 5 of 5 runs; after, 5 of 5 pass.
    - `test_every_chunk_on_the_channel_is_held_by_the_voice_at_each_step`: the invariant, checked
      after start, queue, the queue promoted, an underrun's restart and `stop_now`. Every Sound on
      the channel's playing or queued slot is held by the voice, and it holds at most two.
    - `test_a_voice_on_a_channel_past_a_shrunk_pool_is_silent`: a stale stream never reaches
      `chan_play`. Before the fix its underrun restart called it, and `start` raised.
    - `test_a_voice_stopped_before_it_is_dropped_reports_nothing`: no false report.
    - A stream collected while playing, after a mixer quit, after a mixer restart, and inside a
      playback scope
      (`test_a_stream_collected_inside_a_scope_is_let_go_without_raising`,
      `tests/replay/test_playback_scope.py`): the finalizer finishes without raising and
      reports once.
    - `test_a_draining_voice_lets_go_of_the_chunks_its_channel_has_finished`,
      `test_a_voice_dropped_while_playing_stops_its_channel_before_letting_go`,
      `test_a_voice_dropped_after_the_mixer_quit_lets_go_without_the_mixer` and
      `test_a_voice_dropped_after_a_mixer_restart_lets_go_without_reading_the_table`: the
      releases.
  - `TestChunksTheChannelNames` (same file): a quit mixer and a channel past a restarted mixer's
    table are never read (both fail with the guard removed), and a channel inside it names what
    plays and what is queued.
  - `test_a_golden_games_teardown_leaves_no_mixer_channel_busy`
    (`tests/replay/tools/test_golden_trace_harness.py`): the teardown.
  - `test_a_game_ended_with_a_live_voice_playing_leaves_nothing_on_its_channels`
    (`tests/scenes/test_scene_manager.py`): `terminate` leaves no channel busy and no chunk held.
  - `test_a_queued_sound_no_live_stream_holds_fails_the_test_that_left_it` and
    `test_a_live_streams_queued_chunk_passes_the_check` (`tests/test_harness_silences_the_mixer.py`):
    the harness invariant fails on a planted unheld queue and passes a live stream's;
    `test_a_live_stream_left_playing_after_a_test_is_named_as_never_released`,
    `test_a_patched_stream_left_unreleased_is_still_named` (the `__dict__` case),
    `test_a_dropped_stream_is_reported_on_the_test_that_dropped_it`,
    `test_a_report_of_a_stream_collected_late_names_an_earlier_test`,
    `test_a_silencing_failure_and_an_unreleased_stream_are_reported_together` and, through an
    inner pytest run, `test_a_leaked_live_stream_fails_only_the_test_that_leaked_it` (the
    leak errors its own test; the next one passes).
  - `tests/test_engine_context.py`: `check_live_streams`, the registry slot's isolation check.
  - The proof, the golden test alone 20 times: on origin/main, 8 of 20 crashed; on origin/main
    with only the `live.py` fix, 0 of 20; with both fixes, 0 of 20; on this branch with both
    fixes, 0 of 20. On this branch without them, 0 of 20 too, because the lighting step moved the
    timing out of the window, as the triage predicted.
- **Checked, not affected**: `audio/voices.py`'s and `replay/silence.py`'s `get_sound()` and
  `get_queue()` reads each build a fresh `pygame.mixer.Channel(index)`, whose constructor checks
  init and range and raises. They never read through a stored `Channel`, so they cannot reach a
  quit or shrunk table.
- **Upstream**: `docs/quality/upstream_issues.md`, "pygame-ce's mixer frees a queued Sound while it
  is still referenced (re-entrant `endsound_callback`)": the reproduction, the fix to propose and
  the drafted issue text. Remove the engine's guard only after a fixed pygame-ce release ships.
- **Reporter**: found by the agent triaging the golden-trace segfault
- **Date Reported**: 2026-11-24
- **Files**: `src/glitchygames/audio/live.py`, `src/glitchygames/scenes/scene.py`,
  `src/glitchygames/replay/tools/golden_traces.py`, `tests/harness.py`, `tests/world/frame_harness.py`,
  `tests/replay/test_playback_scope.py`, `tests/audio/test_live.py`,
  `tests/audio/test_live_instrument.py`, `tests/audio/test_channel_partition.py`,
  `tests/scenes/test_scene_manager.py`, `tests/test_harness_silences_the_mixer.py`,
  `tests/replay/tools/test_golden_trace_harness.py`
