# The games on the new sound library: effects, live instruments, compiled at start

Master: the sound engine specs, `docs/specs/2026-11-02-sound-engine-feature-spec.md` and
`docs/specs/2026-11-02-sound-engine-implementation-spec.md` (§7.5 live voices, §8 the API, §10.4
migration and clean-up, M2). Sibling: `plans/2026-11-14-sound-cache-on-first-use.md` (the disk
layer this migration gives something to cache). Branch `chore/upgrade-and-sounds-on-first-use`
(the owner: "I want to do the migration here in this branch. All together."). TODO:
`plans/future-work.md`, "Move the games onto the new sound library".

**Status (2026-11-15): steps 1-9 done**, 7b included, each a commit on the branch (step 9: the
specs, `docs/architecture/sound.md`'s Effects and Live sounds sections, `gameplay_replay.md`, the
games' pages). Left, in `plans/future-work.md`: measuring the first launch's cost and ten Arcade
tiles' memory, and the rest of M2's live instruments.

## Why

Building the disk cache showed that no golden or bundled demo makes a sound through
`scene_manager.audio`: the games still use the old toolkit, so the disk layer had nothing to
cache in them (a PaddleSlap golden replayed under `--sound-cache disk` wrote no file, and the
`disk_sound_cache` fixture failed the test). Moving the games onto the library is what makes
"sounds made on first use" true for them.

## What each game uses today (research, 2026-11-14)

| Game | Today | After |
| --- | --- | --- |
| Clockwork Keep | `SoundBank(ALL_RECIPES)` per floor scene, `prerender()` in `setup()`, seven `sounds.play(name)` sites; the elevator motor, a `live_audio.create_voice` saw with low-pass and tremolo whose frequency and volume follow the ride, owned by the transition | Its recipes become effects, played with `audio.sound(name).play()`; the motor a live instrument with `speed` (and its tremolo), owned by the transition |
| Mr. Muncher | `shared_sound_bank()` (`functools.cache`, process state row R14), nine play sites, crunch alternating; the projector, a live noise voice whose cutoff and tremolo rate change by state | Effects; the projector a live instrument whose cutoff and tremolo rate are parameters |
| Brave Adventurer | `GameSounds`: five `_generate_*_sound()` functions on `synth` (sines and sweeps, envelopes, PEAK 24000/32767, `set_volume`) | Five effects, bit-identical to today's samples |
| PaddleSlap | `game_objects.load_sound(SFX.BOUNCE/SLAP)`: two WAV files | `audio.sound('bounce')` / `audio.sound('slap')`: recorded files by short name |
| Drawing Fire | no sound | nothing |

## Decisions (the owner, 2026-11-14)

1. **The migration is in this branch,** with the upgrade and the disk cache.
2. **Two first-class kinds of sound, each for its own use:**
   - **Effects**: synthetic sound effects, tones mixed straight (summed). A `Tone` is a
     waveform, start and end frequency, duration, envelope, offset and optional filter, tremolo
     and distortion; an `Effect` is its tones and a volume. Exact and cheap: blips, sweeps,
     crunches, jingles.
   - **Instruments**: the layered renderer, for music, notes and timbres, and live voices.
   - One way to get and play either: `audio.sound(source)`, where the source is a short name, a
     path (`file.toml#name`), an `Instrument` or an `Effect`; it returns the same `Sound`.
   - Not "version 0" or "the old way": `SoundRecipe` becomes `Effect` (`Tone` keeps its name).
     In sound files, effects are a table of their own in the current format (`[effects.jump]`
     with `[[effects.jump.tones]]`); files that still say `[recipes.*]` load as effects. An
     effect's `volume` is its default playback volume (today the library ignores it, which would
     have made a crunch about 5.5 times louder). `add_recipes` becomes registering effects by
     name. Spec §10.4's plan to convert recipes to instruments and delete them is dropped;
     `sound-migrate` stays only as an optional effect-to-instrument tool.
3. **The −3 dB centre pan stays.** The library's constant-power pan plays a centred sound at
   0.707 per side, where the old `Sound.play` played both sides at the set volume, so migrated
   sounds are 3 dB quieter. An engine-wide choice; not changed for the migration.
4. **Live instruments are built (M2's first item),** with exposed parameters, routes, curves
   and smoothing (spec §5.3-5.4 of the feature spec, §4.3 and §6.1 of the implementation spec),
   plus a live **tremolo** (rate and depth, each a parameter; spec LFOs stay M4), because both
   live sounds use one and the projector changes its rate. Parameters and routes are declared in
   Python too: `Instrument(..., live=True, parameters={...}, routes=[...])`, mirroring the TOML
   schema (the spec gives them only in TOML). Then `live_audio` and `create_voice` are removed
   (§10.4); §7.5 and §8, which say they stay, are corrected.
5. **`owner=` on `start()` only,** defaulting to today's rule (the scene in setup, else the
   active scene), so the elevator transition can own the motor as it does now (the owner,
   2026-11-14, after the evidence below changed the first plan of `owner=` on `play()` too).
   The motor starts in `_go_to_next_floor`, before the transition starts, while the old floor is
   still active: under the default it would be the old floor's and fade 50 ms into the ride. The
   arrival clank needs nothing: `start_transition` makes the arriving floor the active scene
   before the transition runs (`scenes/scene.py`, `self.active_scene = scene`), so the clank,
   played from the progress-1.0 cue, is the arriving floor's and plays on after the switch (a
   regression test pins it). `play()` gets `owner=` when a play needs one.
6. **Every game compiles all its sounds when it starts, asynchronously during the CRT power-on**
   ("start the compile before the CRT and let it run async then block on the CRT screen"):
   - No thread: each CRT frame, after drawing, the engine compiles sounds until shortly before
     the next frame is due (a time budget per frame), then lets the frame go on. When the
     power-on ends, it compiles what is left on the settled screen, then builds the game. The
     spec's "no new thread" (§4.1) still holds. The same per-tick slices fit `start_async`'s
     awaited ticks (the browser).
   - The CRT's own sounds compile first (it needs them at once).
   - Where the power-on is skipped (the dummy driver, replays, recordings, audits, rebaselines,
     `--crt-power-on off`), everything compiles before frame 0. A key that skips the power-on
     goes straight to the wait.
   - The start-up compiles count as setup compiles, never as a frame's audio work.
   - A failed compile surfaces at the wait, into the normal crash boundary and exit codes.
7. **`warm()` is replaced** by that start-up call: a game declares its sounds (a scene class's
   sound list), the engine compiles them in the CRT's idle time and hands back playable
   `Sound`s. `warm` (no callers, and not the spec's signature) goes.

## Interfaces

- `glitchygames.audio.Effect(tones: Sequence[Tone], volume: float, ...)` and `Tone(...)`
  (today's `Tone` fields), frozen pydantic models; `audio.sound(Effect(...))`.
- Sound files: `[effects.<name>]` (volume, peak) with `[[effects.<name>.tones]]`; `[recipes.*]`
  still read as effects.
- Live instruments (the owner, 2026-11-14, took the sketch as recommended):
  - `Instrument(..., live=True, tremolo=Tremolo(rate_hz, depth), parameters={'speed':
    Parameter(range=(0.0, 1.0), default=0.0, smoothing_ms=30)}, routes=[Route(source='speed',
    destination='pitch', curve='linear', output=(45.0, 110.0)), ...])`. `Parameter` and
    `Route` mirror the TOML schema one to one (frozen pydantic models), so sound files'
    `[instruments.x.parameters.*]` and `[[instruments.x.routes]]` stop being refused.
    `Tremolo` is the effects' own (`audio/effects.py`), reused.
  - Route destinations: `pitch`, `level`, `filter.cutoff`, `tremolo.rate`, `tremolo.depth`,
    `sources.<name>.level`; curves `linear`, `exponential`, `logarithmic`, `smoothstep`,
    `steps(n)`; at most 8 routes; a route's source is an exposed parameter.
  - Smoothing: the spec's one-pole glide per sample, `target + (start - target) * exp(-n / tau)`,
    vectorized per chunk. Updates coalesce: the latest value per chunk counts.
  - Rendering reuses the live-voice chunk code (phase-continuous oscillators, the crossfaded
    FIR low-pass, tremolo, 100 ms chunks) on the context's live pool, so the Arcade's rules hold;
    the motor renders what today's voice does for the same settings (tested).
  - The rest of M2 neither game needs is left as TODOs (`plans/future-work.md`): the
    state-variable filter and resonance, pink noise, `note_on`/`note_off` and retrigger, bit and
    rate reduction, `at_frame`, the Audio panel's live-voices section, `--live-chunk-ms`.
- `Sound.start(*, parameters=None, volume=..., pan=..., bus=..., priority=..., owner=None)
  -> LiveSoundHandle` (`set(name, value) -> bool`, `release()`, `stop()`).
- A scene declares the sounds its game needs at start (`Scene.SOUNDS`, a sequence of sources),
  and the engine's start-up compile reads it. Names are proposals.

## Order of work

1. Effects: `Effect`/`Tone`, the `[effects.*]` table, effect volume as the playback default,
   `add_recipes` reworded; `[recipes.*]` compatibility.
2. Clockwork Keep's and Mr. Muncher's one-shot sounds as effects through `audio.sound`;
   Brave Adventurer's five sounds as effects; PaddleSlap's two WAVs by short name.
3. The clank's ownership pinned by a test (decision 5); `owner=` itself comes with `start()`.
4. The start-up compile: `Scene.SOUNDS`, the CRT-idle slices, the wait, the skipped-power-on
   path; `warm` removed.
5. Live instruments: parameters, routes, curves, smoothing, tremolo, `start()`/`set()`, on the
   live pools (inner games included).
6. The two live sounds on live instruments.
7. Clean-up: `SoundBank`, `live_audio`/`create_voice`/`LiveAudio`'s public face, `GameSounds`,
   `load_sound`/`SFX`, `shared_sound_bank` and its process-state rows, their tests; the
   stand-in games' live voice moved to a live instrument.
   - **7b. Live parity** (the owner, 2026-11-15: "I want all of them"): what the removed
     `LiveVoice`/`LiveAudio`/`SoundBank` could do that the live API could not, built into the
     live API (the handle, `InstrumentVoice`, `LiveStream`), never by restoring the old classes,
     reusing the baked plays' rules where they exist:
     1. `start(persist=True)`: the baked plays' rule; scene changes never release it, the pause
        rules still apply; it ends through its handle or the pool's release.
     2. `handle.set_volume(volume, fade=0.0)`: a linear glide over at least one chunk.
     3. `handle.pause()`/`resume()`: a pause made through the handle holds until resumed (the
        owner rules no longer resume it).
     4. `start(pan=, bus=, priority=)`, `handle.set_pan()`: `voices.constant_power_gains` on
        the voice's channel, always (the owner, 2026-11-15, option 1 of three: one pan law for
        every sound, so a centred live sound is as loud as a baked one and its first pan never
        jumps; Clockwork Keep's motor level and Mr. Muncher's projector volume raised by the
        square root of 2 to sound as before); pan, bus and priority default to the sound
        file's; the bus's `effective_gain` per chunk; a full pool steals the lowest-priority
        live voice of equal or lower priority (earliest made first), else refuses as before.
     5. A live sound's chunk length, 0.03-0.5 s (below 0.03 a chunk cannot cover a 60 fps frame
        plus the device buffer): `Instrument(chunk_seconds=0.1)` and in sound files, not on
        `start()` (the owner, 2026-11-15: latency is part of how a live sound is designed;
        `start()` keeps flat keyword arguments like `play()`, with the same reasoned
        suppression). Both handles are a `voices.PlayingSound`.
     6. `handle.set_frequency(hz)`, `set_cutoff(hz | None)`, `set_tremolo(Tremolo | None)`:
        base values with no declared range; a cutoff on an instrument without a filter adds a
        low-pass, None removes it; linear over one chunk for frequency (the old voice's), the
        crossfade for cutoff. **[Call]** A direct set of what a route moves is refused,
        naming the route.
     7. `Parameter(glide='linear')` (and in TOML): a straight line to the target over
        `smoothing_ms`, beside the one-pole glide.
     8. `LiveAudio` exported again, and `AudioEngine` outside a game documented and tested
        (reserve channels, a live pool, `update(dt)` each frame): what `SoundBank` offered.
8. The proof: every golden and bundled demo under `--sound-cache disk`, cold and warm, with
   `disk_sound_cache` (writes, then hits, nothing compiled twice, digests equal).
9. Docs and spec: §4.1 (start-up slices), §7.5/§8/§10.4 (effects first-class, live instruments,
   `live_audio` removed), `docs/architecture/sound.md`, the games' pages, CLAUDE.md's Sound
   Synthesis lines; every new option and name documented.

## Tests (behaviours)

- Each migrated effect's samples are byte-identical to what today's code renders (Clockwork
  Keep's and Mr. Muncher's recipes, Brave Adventurer's five generators), computed in the test
  from the old code before it is removed.
- An effect plays at its own volume; a `[recipes.*]` file and the same sounds as `[effects.*]`
  give identical sounds.
- Every golden replay and bundled demo still matches (their sprites are unchanged by sound).
- The start-up compile: every declared sound is compiled before frame 0, on the power-on path
  and on every skipped path; no CRT frame is later than its deadline by more than the compile
  of one sound (measured, with a stand-in sound list); a key skip waits on the same screen; a
  failing compile exits through the crash boundary with its code; start-up compiles are setup
  compiles and appear in no frame's audio work; the browser's `start_async` path compiles in
  its ticks.
- The elevator clank, played from the transition's last cue, belongs to the arriving floor and
  is not faded by the switch.
- `start(owner=transition)`: a transition-owned live voice keeps playing through the transition
  and stops with it.
- Live instruments: AUD-GAME-001 to 006 (parameters by name, smoothing, clamping, curves, 1000
  sets per frame coalesced, latency at most a chunk plus 12 ms); tremolo rate and depth change
  live; a live voice on an inner game's live pool is silent while the tile is silent and heard
  when switched heard (the inner-game proof keeps passing).
- The motor follows the ride (frequency and volume from `speed`); the projector's cutoff and
  tremolo rate follow its state.
- The disk proof (step 8).

## Risks

- Live instruments are the largest piece and touch the Arcade's live pools; the inner-game proof
  and `tests/engine/test_inner_game.py`'s live-pool tests guard them.
- A sound that takes longer than a frame to compile delays one CRT frame; the test bounds it.
- Ten Arcade tiles each compile their game's sound set into their own memory cache; measured
  once built (the disk layer makes repeats cheap).
