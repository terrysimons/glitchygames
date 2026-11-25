# Live Sounds Restart in the Middle of a Chunk

- **Description**: A live sound clicked from time to time: `LiveStream.update` restarted it over a
  chunk about to start, which was cut short. The same misreading lost a release's fade, let a
  paused sound play on, dropped a chunk, and let a silenced replay frame's sound start.
- **Status**: Fixed (2026-11-25, `fix/live-sounds-restart-mid-chunk`, stacked on
  `fix/live-sounds-keep-their-pan`).
- **Priority**: High. 1 to 7% of a live sound's chunks clicked, the more the busier the frame.
- **Root Cause**: `Channel.get_busy()` False was taken as an underrun. SDL_mixer 2.8.2's thread marks
  a channel idle (`playing` 0), then calls pygame-ce 2.5.8's `endsound_callback`, which waits for
  the GIL while Python holds it (SDL's `Mix_Playing` takes no lock). Until it runs, pygame's table
  (`get_sound`, `get_queue`) still names both chunks. `LiveStream._play` then gave up the GIL, the
  callback started the queued chunk, and `_play` cut it.
- **Evidence** (macOS arm64, Python 3.15.1, pygame-ce 2.5.8, SDL 2.32.10, SDL_mixer 2.8.2, SDL's disk
  driver, so nothing was played). The scripts and results named here are in the Ledger's triage
  folder `live-restarts`, which is not in the repository; the numbers are all below.
  - The triage (`det.py`): deterministic. Hold the GIL (a 100 s switch interval), spin until the
    channel reads idle, act. All of about 440 cases had pygame still naming both chunks.
  - The triage (`rate.py`), the engine's 0.5 ms switch interval, on main: 48 restarts in 2,248 chunks
    at 120 updates a second (2.14%, 95% interval 1.61-2.82), 2 in 443 at 60, 19 in 458 at 60 with
    4 ms of Python a frame. The pan branch was the same (49 in 2,248).
  - The fix's author (`after.sh`, `results-after.jsonl`), one live sine, 0.1 s chunks, 0.5 ms switch
    interval, 4 ms of Python a frame; a click is a jump in the sine, whose own largest step is 73:

    | Updates | Build | Chunks | Restarts | Clicks | Largest step |
    |---|---|---|---|---|---|
    | 120 Hz | 6adfff523 | 2350 | 163 (6.94%) | 157 | 2260 |
    | 120 Hz | the fix | 2195 | 0 (95% under 0.17%) | 0 | 73 |
    | 60 Hz | 6adfff523 | 2251 | 68 (3.02%) | 63 | 2260 |
    | 60 Hz | the fix | 2187 | 0 (95% under 0.18%) | 0 | 73 |

    With the fix the channel was read idle with a chunk queued 156 times at 120 Hz and 68 at
    60, none of them cut.
    After a 350 ms hitch (a true underrun) the sound plays again within the next update: 0.22 ms
    (0.16 ms before).
- **Siblings** (each reproduced on 6adfff523 with the GIL held):

  | Where | Before | Now |
  |---|---|---|
  | `update` | cut the queued chunk | starts it |
  | `is_finished`, `is_playing` while draining | finished with the fade still queued: the pool stopped it | finished once the table names nothing |
  | `pause` | SDL ignores a pause of an idle channel: the next chunk played (3700 loud samples) | waits for the callback first, and pauses again at each update |
  | `stop_now`, `update` with a chunk queued after the end callback looked | the chunk was stranded (queued, nothing playing): skipped, or left in the table | played, or dropped |
  | Two table reads with the callback between them | a chunk in neither read, so let go while pygame named it (#313's double free) | the queue is read first |
  | `FrameSilencer` (replay/silence.py) | a stop starts the queued chunk; an idle-looking channel was not stopped | stops twice, by the table |

- **Test gap**: `test_underrun_recovers` pinned the bug: it set only `get_busy` False, on a mock whose
  table still named a chunk. No test used pygame's contract for a channel.
- **Fix**: `live.channel_state` is the one reader of a channel's state: PLAYING, QUEUED, STRANDED or
  ENDED, by pygame's table. A channel that reads idle but is named is settled first by
  `Channel.unpause()`: it gives up the GIL and takes the mixer's lock, which the callback's thread
  holds, so it returns once the callback has run (and resumes nothing: SDL resumes only a playing
  channel, and a paused one is busy). At most `MAXIMUM_SETTLING_ATTEMPTS` times. `update`,
  `is_playing`, `is_finished`, `pause` and the silencer use it. An underrun restarts in the same
  update. `_play` refuses, logs once, and renders nothing if the table names one of its own chunks
  as playing: raising would end a player's game over a click already prevented. Held chunks stay at
  most two. No event, draw, clock read or recorded value changed.
- **Not changed**: `set_pan` reads the queue slot, and rewrites only a chunk still queued. With the
  callback pending that chunk is about to start, the race its record already describes (a small
  step if it starts during the copy); no test showed more.
- **Known limits**:
  - `is_playing` and `is_finished` are truer, but still follow the mixer's time
    (`2026-11-24-live-voice-answers-read-the-real-mixer.md`, open).
  - SDL_mixer's pause takes no lock: a chunk that ends as it is made lets the next one start, which
    the next update pauses (a frame of sound).
  - A channel pygame names but SDL never plays would stay silent: nothing known makes one.
  - Not tested on Windows, Linux or in a browser, on an audible driver, or in a played game.
- **Sweep** (`grep -rn "get_busy\|get_queue\|get_sound\|\.queue(" src/`): covered: everything in
  `audio/live.py` and `replay/silence.py`. Read and left: `VoiceTable` (`audio/voices.py`: library
  voices never queue a chunk, so an idle reading is true but for a moment), `take_heard_set` and
  `release_inner_context_channels` there (stopped twice; a stranded chunk could stay in the table,
  silent, until the channel's next play), `AudioEngine._a_library_channel_sounds`,
  `golden_traces` and `tests/harness.py` (stop twice already).
- **Tests**: `tests/audio/test_live.py`: `TestChannelStateFromTheTable` on `TableChannel`, a model of
  pygame's and SDL_mixer's contract (its docstring cites the source lines) in which the callback
  runs at the next GIL release: every reachable busy, sound and queue against every voice state,
  and 20 seeded walks in which every chunk rendered is heard whole and in order. `TestPendingEndCallback` and
  `tests/replay/test_rebuild.py`: the real mixer with the GIL held. `TestChunksHeardWhole`: the
  recording of eight updates in the window (`tests/audio/live_restart_probe.py`). None depends on
  how fast the mixer or the machine runs.
- **Reporter**: The pan fix's author and the live-restarts triage
- **Date Reported**: 2026-11-25
- **Files**: `src/glitchygames/audio/live.py`, `src/glitchygames/replay/silence.py`
