# Live Sounds Lose Their Pan and Centre Gain From Their Second Chunk

- **Description**: A live sound (Clockwork Keep's elevator motor, Mr. Muncher's projector, any
  `Sound.start()`) was panned only in its first chunk. From the second chunk on (0.1 s in) it played
  at full on both sides: a sound panned hard left was heard on both, and a centred one was 3 dB
  louder than meant, with a step at the join.
- **Status**: Fixed (2026-11-25, `fix/live-sounds-keep-their-pan`).
- **Priority**: High. Every live sound was too loud, and `set_pan` did not last.
- **Root Cause**: SDL_mixer keeps volume and pan on the channel and removes them when the channel's
  sound ends; pygame-ce 2.5.8 then starts the queued Sound at full on both sides. `LiveStream`
  (`src/glitchygames/audio/live.py`) set its channel's gains in `start` and `set_pan` only, and its
  chunks (queued, and an underrun's `Channel.play`) carried none.
- **Evidence** (macOS arm64, Python 3.15.1, pygame-ce 2.5.8, SDL 2.32.10, SDL's disk driver, so
  nothing was played; a 441 Hz tone of peak 16384):
  - The coordinator, raw pygame (`pan_check.py` in the Ledger's triage folder
    `channel-fade-windows`): pan left, chunk 0 peaks 16384/0, chunks 1 and 2 16384/16384.
  - The triage, a real `LiveStream` (`engine_paths.py`): the same.
  - The fix's author (`live_gains.py` there), left/right peaks per chunk and the largest step at the
    first join (the tone's own largest step is 1029):

    | Pan | Before: chunk 0 | Before: later | Join | After: every chunk | Join |
    |---|---|---|---|---|---|
    | -1 | 16384 / 0 | 16384 / 16384 | 13255 | 16384 / 0 | within the tone's own |
    | 0 | 11565 / 11565 | 16384 / 16384 | 3491 | 11585 / 11585 | within the tone's own |
    | 1 | 0 / 16384 | 16384 / 16384 | 13255 | 0 / 16384 | within the tone's own |

  - A pan change from centre to left: before, steps of 9630 (the change) and 13255 (the change lost
    at the next chunk); after, none above the tone's own.
- **The owner's levels**: On 2026-11-15 the owner chose one pan law for every sound, and raised the
  motor's level and the projector's volume by the square root of 2 so that a centred live sound
  stays as loud as before. The centre gain was then lost from the second chunk, so both played about
  3 dB louder than chosen. The fix makes them what was chosen; the constants are unchanged. Recorded
  at the games' own volumes (RMS per side, after the first chunk): the motor at rest and at full
  speed and the projector are each 3.0 dB quieter (`listening/README.md` in the triage folder).
- **Test gap**: The tests asserted that `Channel.set_volume` was called, on a mock channel. Nothing
  measured a level past the first chunk, and no call reads a channel's pan back.
- **Fix**: The gains are rendered into each chunk's left and right samples (`synth.panned_pcm16`,
  after clipping), and the channel is set to full on both sides before each play. A chunk starts at
  the gains the one before it ended at and ramps to the pan's. `set_pan` rewrites the queued chunk
  in place: nothing is rendered again, so no noise draw moves, and a chunk muted by its game going
  silent stays muted. A mono mixer plays the centre gain (both sides' mean power) whatever the pan;
  before, it ignored the gain.
- **Latency of a pan change**: before, the next mixer chunk (up to 11.6 ms), for the rest of the
  playing chunk only. After, it starts as the next chunk does (0 to one chunk, 100 ms by default),
  and is complete one chunk later.
- **Known limits**:
  - The ramp is straight in each side's gain, so half way through a swing from one side to the other
    the power is 3 dB down.
  - If the queued chunk starts playing while it is rewritten, the mixer may play a few frames of the
    old version first. Both versions start at the same gains, so the difference is at most the ramp
    so far; not provoked in a test.
  - On more than two output channels the sides alternate, left first: right for four, untested on a
    device, and approximate for 5.1's centre and low-frequency speakers.
  - A step in the bus's gain is still a step at the chunk's start, as before.
- **Sweep** (`grep -rn "set_volume\|\.queue(" src/`): `LiveStream` is the only code that queues a
  Sound, so the only one this loses a pan for. Sibling, open (bug 1, its own pull request):
  `VoiceTable._start` (`audio/voices.py`) calls `Channel.play` and then `set_volume`, so what the
  mixer plays between the two is at full on both sides. A restart by `Channel.play` in
  `LiveStream` is safe: its chunk holds its gains. Found, open: on a mono mixer `set_volume(left,
  right)` is SDL's panning, which does nothing there, so a library voice's volume and pan are lost
  (measured with raw pygame: samples of 16000 at `set_volume(.1, .1)` play at 16000; the engine's
  own path was not run on a mono mixer). Found, open: `LiveStream.update` can read the channel idle
  while SDL_mixer is between a chunk's end and pygame's start of the queued one, and then restarts
  over the queued chunk, which is cut short: a click. With an update every 8 to 10 ms and no stall
  (`false_underrun.py` in the triage folder), 11 restarts in 205 chunks with the fix and 10 in 205
  without, each with pygame still naming a chunk for the channel.
- **Tests** (`tests/audio/test_live.py`; every chunk's heard frames on the real mixer, and the
  mixer's output on the disk driver through `tests/audio/live_pan_probe.py`): `TestLiveStreamGains`
  (every chunk at its gains, pan changes, pause, fade, ducked bus, an inner game gone silent, noise,
  mono, and the invariant that no chunk's power is above its voice's gains) and `TestHeardPans`
  (left, centred on a panned channel, restarted, paused, stolen, released, moved, the channel's next
  user). `tests/audio/test_synth.py`: the samples clip before the gains.
- **Reporter**: The coordinator and the channel-fade triage
- **Date Reported**: 2026-11-24
- **Files**: `src/glitchygames/audio/live.py`, `src/glitchygames/audio/synth.py`
