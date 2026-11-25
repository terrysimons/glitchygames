# Live Sounds Lose Their Pan and Centre Gain From Their Second Chunk

- **Description**: A live sound (Clockwork Keep's elevator motor, Mr. Muncher's projector, any
  `Sound.start()`) was panned only in its first chunk. From the second chunk on (0.1 s in) it played
  at full on both sides: a sound panned hard left was heard on both, and a centred one was 3 dB
  louder than meant, with a step at the join.
- **Status**: Fixed (2026-11-25, `fix/live-sounds-keep-their-pan`).
- **Priority**: High. Every live sound was too loud, and `set_pan` did not last.
- **Root Cause**: `Channel.set_volume(left, right)` is SDL_mixer's panning, an effect it removes
  when the channel's sound ends; pygame-ce 2.5.8 then starts the queued Sound unpanned, so at full on
  both sides. (A one-argument volume is not lost: after `set_volume(.25)`, samples of 16000 play at
  4000 and a later `Channel.play` of 8000 at 2000; the reviewer, repeated by the author.)
  `LiveStream` (`src/glitchygames/audio/live.py`) set its channel's gains in `start` and `set_pan`
  only, and its chunks (queued, and an underrun's `Channel.play`) carried none.
- **Evidence** (macOS arm64, Python 3.15.1, pygame-ce 2.5.8, SDL 2.32.10, SDL's disk driver, so
  nothing was played; a 441 Hz tone of peak 16384). The scripts and recordings named here are in
  the Ledger's triage folder, which is not in the repository; the numbers are all below.
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
    at the next chunk); after, none above the tone's own. This is the pan's own step: the open
    restart over a queued chunk (Sweep) can still click at any join.
- **The owner's levels**: On 2026-11-15 the owner chose one pan law for every sound, and raised the
  motor's level and the projector's volume by the square root of 2 so that a centred live sound
  stays as loud as before. The centre gain was then lost from the second chunk, so both played about
  3 dB louder than chosen. The fix makes them what was chosen; the constants are unchanged. Recorded
  at the games' own volumes (RMS per side, after the first chunk): the motor at rest and at full
  speed and the projector are each 3.0 dB quieter: -20.36 to -23.41 dBFS, -8.99 to -12.00 and
  -48.78 to -51.73 (`listening/README.md` in the triage folder).
- **Test gap**: The tests asserted that `Channel.set_volume` was called, on a mock channel. Nothing
  measured a level past the first chunk, and no call reads a channel's pan back.
- **Fix**: The gains are rendered into each chunk's left and right samples (`synth.panned_pcm16`,
  after clipping), and the channel is set to full on both sides before each play, since it may
  still have a volume or a pan another user left. A chunk starts at
  the gains the one before it ended at and ramps to the pan's. `set_pan` rewrites the queued chunk
  in place, if it is still queued once its new samples are made (else the next chunk rendered ramps
  instead): nothing is rendered again, so no noise draw moves, and a chunk muted by its game going
  silent stays muted. A mono mixer plays the centre gain (both sides' mean power) whatever the pan;
  before, it ignored the gain, so a live sound on a mono mixer is now 3 dB quieter.
- **Latency of a pan change**: before, the next mixer chunk (up to 11.6 ms), for the rest of the
  playing chunk only. After, it starts as the next chunk does (0 to one chunk, 100 ms by default),
  and is complete one chunk later.
- **Known limits**:
  - The ramp is straight in each side's gain, so half way through a swing from one side to the other
    the power is 3 dB down.
  - If the queued chunk starts during the copy (after the check that it is still queued), the mixer
    plays the old version up to where it has got to, then the new one. The step is at most the
    change in gain times the part of the chunk played by then. Forced on the disk driver at level
    0.5, the gain change 1: 0.0226 with no or 5 ms delay, 0.139 at 30 ms. The same promotion forced
    while the samples are being made, before the check, stepped 0.0226, 0.0226, 0.139 and 0.5 at 0,
    5, 30 and 110 ms in the fix's first version; with the check the largest step is the ramp's own,
    0.0001. The ramp is linear, so no step can exceed the change itself.
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
  mono, a queued chunk that starts while its rewrite is made, and the invariant that no chunk is
  louder than the gain in force as it was rendered, its bus's included) and `TestHeardPans`
  (left, centred on a panned channel, restarted, paused, stolen, released, moved, the channel's next
  user, a guard that passed before the fix too). Neither depends on how fast the mixer runs: the
  first holds its channel paused, the second goes on until enough chunks are rendered.
  `tests/audio/test_synth.py`: the samples clip before the gains.
- **Reporter**: The coordinator and the channel-fade triage
- **Date Reported**: 2026-11-24
- **Files**: `src/glitchygames/audio/live.py`, `src/glitchygames/audio/synth.py`
