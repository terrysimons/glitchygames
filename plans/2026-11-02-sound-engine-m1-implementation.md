# Sound Engine M1 (One-Call Sound API + CRT) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Games get sounds with one call, `audio.sound(...)` (compiled on first request, cached as
`None` or `'ram'`, never played until `.play()`), with notes/hertz/MIDI/scale pitches, named and
blendable waves, TOML instruments, buses and voice management, per-frame audio accounting, an
Audio debug panel, offline rendering, the CRT power-on sound and a Sound Board demo.

**Architecture:** A layer over `pygame.mixer`, which stays the only output device. Pure, numpy
render functions turn an immutable `SoundSpec` into a float64 buffer; a library resolves names and
paths to specs, compiles once per identity and caches. A voice table on reserved mixer channels
plays compiled sounds. Everything runs on the main thread. No new threads, no new dependencies.

**Tech Stack:** Python 3.14, pygame-ce 2.5.8 (`pygame.mixer`), numpy, pydantic v2, `tomllib`,
`tomli-w`, pytest with the dummy SDL drivers, bokeh not needed in M1.

**Spec:** `docs/specs/2026-11-02-sound-engine-feature-spec.md` (requirement IDs) and
`docs/specs/2026-11-02-sound-engine-implementation-spec.md` (section numbers below are this
document's). Read both before starting; the implementation spec's §8 is the API contract.

## Global Constraints

- Python 3.14 (`requires-python = ">=3.14,<4.0"`); ruff, 100-character lines; Google-style
  docstrings; basedpyright and ty clean (CLAUDE.md, Code Style).
- No new runtime dependencies (AUD-PORT-001): numpy, pygame-ce, pydantic, `tomllib`, `tomli-w` only.
- Time: never import `time`; measure with `clock.raw_counter_ns()` / `clock.raw_counter_seconds()`,
  sleep with `clock.raw_sleep`, always as `from glitchygames import clock` then `clock.<name>()`
  (`tests/test_engine_doors.py`).
- Randomness: no unseeded generators; sound noise uses `numpy.random.Generator(numpy.random.PCG64(seed))`
  seeded per impl §6.3, never `glitchygames.randomness` streams
  (`tests/test_unseeded_randomness_guard.py`).
- Tests: real pygame on the dummy drivers, pixel assertions for drawing, no wall-clock timings in
  the normal suite (benchmarks only under `--benchmark-only`), 100% coverage, descriptive test file
  names (CLAUDE.md, Testing Guidelines). The engine never imports a workspace member.
- Names: the owner dislikes abbreviated variable names (`sample_rate`, not `sr`; `frequency`, not
  `freq`). Keyword-only arguments after the first, as the spec's §8 signatures show.
- Attribute every algorithm taken from a reference with a comment naming it (impl §5 lists them:
  Fritsch–Carlson, the PolyBLEP already in `synth.py`).
- Defaults copied from the spec: A4 = 440.0 Hz; wave table length 2048; library channels 32,
  legacy channels 8, live pool 4; default note length 0.25 s; de-click 1 ms in / 2 ms out above
  magnitude 1/1024; steal fade 10 ms; scene-cleanup fade 50 ms; shutdown wait ≤ 100 ms; memory
  cache 256 MB; supported pitch 8 Hz–12 kHz; `audio_work` at most 32 entries per frame.
- Commits: the owner's rule is that nothing is committed or pushed automatically. Run each task's
  commit step only when the owner has authorized commits for this execution; otherwise stage and
  report.

## Review Focus

- **A sound requested before the mixer exists, then played after it starts** (a `--headless`
  restart, a test that initializes the mixer late): the play must work, building the
  `pygame.mixer.Sound` on first play. Test in Task 7.
- **A mixer at another rate than 44100 Hz** (a device that opened at 48000): the sound compiles at
  the running rate and its identity differs from the 44100 Hz one. Test in Task 7.
- **A short name in a game with no `sounds` directory:** a `KeyError` that names the directory it
  looked in, not a `FileNotFoundError` traceback. Test in Task 6.
- **One `Sound` played many times at once:** each play is its own voice; stopping one handle leaves
  the others playing. Test in Task 8.
- **A handle used after its scene switched away or after `audio.close()`:** methods return `False`,
  never raise. Test in Task 9.

---

### Task 1: Pitch types

**Files:**
- Create: `src/glitchygames/audio/pitch.py`
- Test: `tests/audio/test_pitch.py`

**Interfaces:**
- Produces: `Note`, `Hz`, `Midi`, `Scale`, `ScaleStep`, `PitchTable`, `Tuning`,
  `resolve_pitch(pitch: PitchLike, *, tuning: Tuning) -> Hz`, `PitchLike`, and constants
  `SUPPORTED_LOW_HZ = 8.0`, `SUPPORTED_HIGH_HZ = 12000.0`. Signatures exactly as impl §8 `pitch.py`.
  `Scale.step` returns a `Note`.

- [ ] **Step 1: Write the failing tests**

```python
def test_note_names_resolve_to_equal_temperament_hertz():
    tuning = Tuning()
    assert resolve_pitch('A4', tuning=tuning) == pytest.approx(440.0)
    assert resolve_pitch('C4', tuning=tuning) == pytest.approx(261.6256, abs=1e-4)
    assert resolve_pitch('Bb3', tuning=tuning) == pytest.approx(resolve_pitch('A#3', tuning=tuning))

def test_a_float_is_hertz_and_a_bare_int_is_refused():
    assert resolve_pitch(880.0, tuning=Tuning()) == 880.0
    with pytest.raises(ValueError, match=r'Midi\(60\)'):
        resolve_pitch(60, tuning=Tuning())

def test_midi_and_intervals():
    assert resolve_pitch(Midi(69), tuning=Tuning()) == pytest.approx(440.0)
    octave_up = Note('C4').up(semitones=12)
    assert resolve_pitch(octave_up, tuning=Tuning()) == pytest.approx(2 * 261.6256, abs=1e-3)
    assert Hz(220.0).times(1.5) == pytest.approx(330.0)
    assert Hz(220.0).octave_up() == pytest.approx(440.0)

def test_scale_steps_wrap_octaves():
    assert Scale('C', 'major').step(7) == Note('C5')
    assert Scale('C', 'major_pentatonic').step(2) == Note('E4')

def test_pitch_table_lookups_equal_the_games_floats():
    table = PitchTable.from_dict({'C4': 261.63, 'E4': 329.63})
    assert table['E4'] == 329.63

def test_tuning_moves_every_note_by_one_ratio():
    assert resolve_pitch('A4', tuning=Tuning(a4=432.0)) == pytest.approx(432.0)

@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -1.0, 30000.0])
def test_out_of_range_pitches_raise(bad):
    with pytest.raises(ValueError):
        resolve_pitch(bad, tuning=Tuning(), sample_rate=44100)
```

(`resolve_pitch` also takes keyword `sample_rate: int = 44100` for the Nyquist check; values outside
8 Hz–12 kHz but under Nyquist log one warning per distinct value.) Cover every scale in impl §8's
list with one step each.

- [ ] **Step 2: Run** `uv run pytest --dummy-only tests/audio/test_pitch.py -v` — expected FAIL (module missing).
- [ ] **Step 3: Implement `pitch.py`.** Note names parse `^[A-G](#|b)?-?\d$`; `Midi` is an `int`
  subclass validated 0–127; `ScaleStep` is what `Scale.step` uses internally when a melody passes
  steps lazily (a frozen dataclass of scale and number). `Note`/`Midi`/`ScaleStep` hash and compare
  by value.
- [ ] **Step 4: Run the tests** — expected PASS.
- [ ] **Step 5: Commit** `feat(audio): pitch types (Note, Hz, Midi, Scale, PitchTable, Tuning)`.

---

### Task 2: Named waves, blends, harmonics, points and the registry

**Files:**
- Create: `src/glitchygames/audio/waves.py`
- Test: `tests/audio/test_waves.py`, `tests/audio/test_render_aliasing.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `CYCLE`, `LEVEL`, `WavePoint`, `Harmonics`, `Wave`, `WaveRegistry`,
  `WAVE_TABLE_LENGTH = 2048`, `BUILT_IN_WAVE_NAMES` (`sine`, `triangle`, `saw`, `square`,
  `pulse_12`, `pulse_25`, `pulse_75`, `pulse`). `Wave.table() -> numpy.ndarray` (2048 float64, one
  cycle) and `Wave.band_limited_table(*, highest_frequency: float, sample_rate: int) -> numpy.ndarray`
  (the mip table for that band). `Wave.is_built_in_polyblep -> bool` is true for `saw`, `square`,
  `pulse*`, which Task 4 renders with `synth.oscillator` instead of tables. `Wave.detuned(*,
  cents: float) -> SourceSpecDraft` is added in Task 3.

- [ ] **Step 1: Write the failing tests** (impl §5 table rows "Custom waves", "Harmonics", "WavePoint"):

```python
def test_mix_by_name_normalizes_weights():
    mixed = Wave.mix(square=1.0, triangle=1.0).table()
    expected = 0.5 * Wave('square').table() + 0.5 * Wave('triangle').table()
    numpy.testing.assert_allclose(mixed, expected / numpy.max(numpy.abs(expected)), atol=1e-9)

def test_blend_is_a_crossfade_toward_the_other_wave():
    numpy.testing.assert_allclose(Wave('saw').blend('sine', amount=1.0).table(), Wave('sine').table(), atol=1e-9)

def test_harmonics_by_musical_name_set_the_spectrum():
    table = Wave.from_harmonics(Harmonics(fundamental=1.0, octave=0.5, two_octaves=0.25)).table()
    magnitudes = numpy.abs(numpy.fft.rfft(table))[1:5]
    ratios_db = 20 * numpy.log10(magnitudes / magnitudes[0] + 1e-30)
    assert ratios_db[1] == pytest.approx(20 * numpy.log10(0.5), abs=0.1)
    assert ratios_db[3] == pytest.approx(20 * numpy.log10(0.25), abs=0.1)

def test_drawbars_read_nine_digits():
    assert Harmonics.drawbars('008000000') == Harmonics(fundamental=1.0)

def test_points_reproduce_and_lose_their_dc():
    wave = Wave.from_points((WavePoint(at=CYCLE.START, level=LEVEL.CENTER), WavePoint(at=CYCLE.QUARTER, level=LEVEL.TOP),
                             WavePoint(at=CYCLE.THREE_QUARTERS, level=LEVEL.BOTTOM), WavePoint(at=CYCLE.END, level=LEVEL.CENTER)))
    table = wave.table()
    assert abs(table.mean()) < 1e-9 and numpy.max(numpy.abs(table)) == pytest.approx(1.0)

def test_a_flat_wave_is_refused():
    with pytest.raises(ValueError, match='no variation'):
        Wave.from_points((WavePoint(at=0.0, level=0.5), WavePoint(at=1.0, level=0.5)))

def test_registered_waves_mix_like_built_ins_and_built_in_names_are_reserved():
    registry = WaveRegistry()
    registry.register('ghost', Wave.from_points(GHOST_POINTS, shape='smooth'))
    assert registry['ghost'].table().shape == (WAVE_TABLE_LENGTH,)
    with pytest.raises(ValueError):
        registry.register('square', Wave('sine'))
```

`test_render_aliasing.py` (AUD-WAVE-006): render 1 s of `square` and `saw` at 3520 Hz through
Task 4's renderer once it exists; in this task, test the mip tables: the band table for
`highest_frequency=3520, sample_rate=44100` has no FFT bin above harmonic `floor(22050/3520) = 6`
larger than 1e-9 of the fundamental. Drawbar footages map to harmonics 0.5, 1.5, 1, 2, 3, 4, 5, 6, 8
(`Harmonics` gains `sub_octave` (harmonic 0.5, the 16' bar) and `fifth` (harmonic 1.5, the 5⅓'
bar) fields).

- [ ] **Step 2: Run** `uv run pytest --dummy-only tests/audio/test_waves.py tests/audio/test_render_aliasing.py -v` — FAIL.
- [ ] **Step 3: Implement `waves.py`.** `smooth` uses monotone cubic interpolation — add the
  comment `# Monotone cubic: F. N. Fritsch and R. E. Carlson, SIAM J. Numer. Anal. 17(2), 1980`.
  Mip bands: one per octave from 20 Hz up to Nyquist, built lazily and cached on the `Wave`.
  `Wave` is immutable and hashable by its table bytes (identity hashing in Task 3 needs it).
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(audio): named waves, mixes, harmonics, wave points and mip tables`.

---

### Task 3: Sound specs, instruments and identity

**Files:**
- Create: `src/glitchygames/audio/spec.py`, `src/glitchygames/audio/instrument.py`
- Test: `tests/audio/test_sound_spec.py`

**Interfaces:**
- Consumes: Task 1 `resolve_pitch`, `PitchLike`, `Tuning`; Task 2 `Wave`.
- Produces (all frozen dataclasses with `slots=True`):
  - `EnvelopeSpec(attack: float, decay: float, sustain: float, release: float, curve: str)` with
    presets `ENVELOPE_PRESETS: dict[str, EnvelopeSpec]` (`pluck`, `pad`, `organ`, `percussive`,
    `swell`), and `EnvelopeSpec.from_legacy(envelope: synth.Envelope)`.
  - `FilterSpec(kind: str, cutoff_hz: float)` (`low_pass` | `high_pass`, FIR in M1).
  - `PitchCurveSpec(target_hz: float, seconds: float, easing: str)`.
  - `SourceSpec(wave: Wave | None, noise: NoiseSpec | None, level: float, semitones: float,
    detune_cents: float, fixed_hz: float | None, pitch_curve: PitchCurveSpec | None,
    envelope: EnvelopeSpec | None, filter: FilterSpec | None, duty: float)`.
  - `NoiseSpec(kind: str, bits: int, taps: tuple[int, int], rate_hz: float | None, seed: int | None)`.
  - `NoteEvent(start_seconds: float, hz: float, length_seconds: float)`.
  - `SoundSpec(name: str, sources: tuple[SourceSpec, ...], envelope: EnvelopeSpec,
    filter: FilterSpec | None, drive: float, notes: tuple[NoteEvent, ...] | None, unpitched_scale: float,
    sample_rate: int, seed: int, normalize: bool, hard_edges: bool, live: bool, tuning_a4: float,
    playback_defaults: PlaybackDefaults)`.
  - `PlaybackDefaults(bus: str = 'effects', volume: float = 1.0, pan: float = 0.0,
    priority: int = 50, loop: bool = False)`.
  - `identity_key(spec: SoundSpec) -> str` (128-bit hex, impl §6.2: canonical JSON with sorted
    keys, floats by `repr`, plus `AUDIO_RENDER_VERSION = 1`, `numpy.__version__`,
    `sysconfig.get_platform()`).
  - `Instrument` and `Noise` (public, impl §8), and
    `build_spec(instrument: Instrument, *, name: str, pitch, notes, chord, length, transpose,
    tuning: Tuning, sample_rate: int, playback_defaults: PlaybackDefaults) -> SoundSpec`.
  - `parse_notes(notes: str | Sequence[tuple[PitchLike, float]], *, tuning: Tuning) -> tuple[NoteEvent, ...]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_note_string_becomes_back_to_back_events():
    events = parse_notes('B5:0.06 _:0.02 E6:0.18', tuning=Tuning())
    assert [round(event.start_seconds, 6) for event in events] == [0.0, 0.08]
    assert events[1].length_seconds == pytest.approx(0.18)

def test_pitch_with_notes_or_chord_is_refused():
    with pytest.raises(ValueError, match='transpose'):
        build_spec(PULSE, name='x', pitch='C4', notes='C4:0.1', chord=None, length=None, transpose=0.0,
                   tuning=Tuning(), sample_rate=44100, playback_defaults=PlaybackDefaults())

def test_chord_is_simultaneous_events_of_one_length():
    spec = build_spec(PULSE, name='x', pitch=None, notes=None, chord=('C4', 'E4', 'G4'), length=0.5, transpose=0.0,
                      tuning=Tuning(), sample_rate=44100, playback_defaults=PlaybackDefaults())
    assert {event.start_seconds for event in spec.notes} == {0.0} and len(spec.notes) == 3

def test_identity_changes_with_any_identifying_field_and_not_otherwise():
    first, same, other_pitch, other_rate = (make_spec(pitch='C5'), make_spec(pitch='C5'),
                                           make_spec(pitch='D5'), make_spec(pitch='C5', sample_rate=48000))
    assert identity_key(first) == identity_key(same)
    assert len({identity_key(first), identity_key(other_pitch), identity_key(other_rate)}) == 3

def test_default_seed_is_derived_from_the_name_not_the_run():
    assert make_spec(name='coin').seed == make_spec(name='coin').seed != make_spec(name='thud').seed

def test_instrument_takes_exactly_one_of_wave_noise_sources():
    with pytest.raises(ValueError):
        Instrument(wave='square', noise='white')
    with pytest.raises(ValueError, match='at most 4'):
        Instrument(sources={str(index): Wave('sine') for index in range(5)})
```

`Wave.detuned(*, cents)` returns a `Source` (a public wrapper building a `SourceSpec` with
`detune_cents`). Default `length` is 0.25 s for a single pitch or chord (feature spec W3);
`transpose` shifts every note by semitones. An unpitched instrument (noise only) with a pitch sets
`unpitched_scale = pitch_hz / 440.0`, else 1.0.

- [ ] **Step 2: Run** `uv run pytest --dummy-only tests/audio/test_sound_spec.py -v` — FAIL.
- [ ] **Step 3: Implement** `spec.py` (data, `identity_key`, `parse_notes`) and `instrument.py`
  (`Instrument`, `Noise`, `Source`, `build_spec`). Seeds: `int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], 'big')`
  unless the instrument gives one (impl §6.3).
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(audio): sound specs, instruments and identity keys`.

---

### Task 4: The M1 renderer

**Files:**
- Create: `src/glitchygames/audio/render.py`
- Test: `tests/audio/test_render_pitch_accuracy.py`, `test_render_envelopes.py`,
  `test_render_noise.py`, `test_render_layers.py`, `test_render_notes_and_chords.py`,
  `test_render_pitch_curves.py`, `test_render_effects.py`, `test_render_fuzz.py`
  (all under `tests/audio/`)

**Interfaces:**
- Consumes: Task 3 specs; Task 2 `Wave.band_limited_table`; existing `synth.oscillator`,
  `synth.frequency_curve`, `synth.apply_kernel`, `synth.filter_kernel`, `synth.distort`.
- Produces: `render_sound(spec: SoundSpec) -> RenderedSound` where
  `RenderedSound(samples: numpy.ndarray (float64, mono), peak: float, clipped: bool)`, and
  `class SoundRenderError(GlitchyGamesAudioError)` in `audio/exceptions.py`.

- [ ] **Step 1: Write the failing tests** (values from feature spec §15):

```python
@pytest.mark.parametrize('wave', ['sine', 'square', 'saw', 'triangle'])
@pytest.mark.parametrize('frequency', [55.0, 440.0, 3520.0])
def test_measured_fundamental_is_within_half_a_cent(wave, frequency):
    samples = render_sound(single_note_spec(wave=wave, hz=frequency, length=1.0, sustain=1.0)).samples
    assert cents_between(measured_fundamental(samples, 44100), frequency) <= 0.5

def test_adsr_stage_times_are_within_a_millisecond():
    samples = render_sound(single_note_spec(wave='sine', hz=440.0, envelope=EnvelopeSpec(0.05, 0.1, 0.5, 0.2, 'linear'), length=0.5)).samples
    assert stage_boundaries_in_seconds(samples, 44100) == pytest.approx([0.05, 0.15, 0.5, 0.7], abs=0.001)

def test_stepped_envelope_has_exactly_n_levels():
    envelope = render_envelope_only(EnvelopeSpec(0.1, 0.1, 0.5, 0.1, 'steps(16)'), length=0.3)
    assert len(numpy.unique(numpy.round(envelope, 9))) <= 16 + 1

def test_lfsr_period_and_seeded_repeatability():
    spec = noise_spec(kind='lfsr', bits=15, taps=(14, 13), rate_hz=44100.0, seed=7)
    assert numpy.array_equal(render_sound(spec).samples, render_sound(spec).samples)
    assert lfsr_period(bits=15, taps=(14, 13)) == 32767
    with pytest.raises(ValueError):
        noise_spec(kind='lfsr', bits=15, taps=(14, 3))     # not a maximal-length tap set

def test_note_onsets_land_on_exact_frames():
    samples = render_sound(notes_spec('C5:0.1 E5:0.1', hard_edges=True)).samples
    assert onset_frames(samples) == [0, round(0.1 * 44100)]

def test_every_source_of_a_layer_is_present():
    samples = render_sound(layered_spec(hz=(110.0, 330.0, 990.0))).samples
    assert all(spectrum_peak_db(samples, frequency) > -30 for frequency in (110.0, 330.0, 990.0))

def test_boundary_declick_applies_only_when_the_edge_is_loud():
    loud_start = render_sound(single_note_spec(wave='square', hz=440.0)).samples
    assert abs(loud_start[0]) < 1 / 1024 and abs(loud_start[-1]) < 1 / 1024
    hard = render_sound(single_note_spec(wave='square', hz=440.0, hard_edges=True)).samples
    assert abs(hard[0]) > 0.5

def test_peak_over_full_scale_is_clipped_and_reported():
    rendered = render_sound(single_note_spec(wave='square', hz=440.0, level=3.0))
    assert rendered.clipped and numpy.max(numpy.abs(rendered.samples)) <= 1.0

def test_pitch_curve_follows_its_easing_within_one_percent(): ...   # 10 points, measured by zero crossings
def test_drive_output_is_finite_and_bounded(): ...

@settings(max_examples=200)   # if hypothesis is not in the dev group, use a seeded parameter sweep instead
def test_fuzzed_valid_specs_never_produce_non_finite_output(spec): ...
```

The measuring helpers (`measured_fundamental`, `cents_between`, `stage_boundaries_in_seconds`,
`onset_frames`, `spectrum_peak_db`) go in `tests/audio/measuring.py`, imported by its qualified path
(`tests.audio.measuring`). Check whether `hypothesis` is in the dev group first (`pyproject.toml`);
if not, the fuzz test is a seeded sweep of 200 specs, not a new dependency.

- [ ] **Step 2: Run** `uv run pytest --dummy-only tests/audio/test_render_*.py -v` — FAIL.
- [ ] **Step 3: Implement `render.py`.** Per note: each source renders its oscillator (built-in
  PolyBLEP waves through `synth.oscillator`; other waves by table lookup with linear interpolation
  in the band chosen from the note's highest frequency) or noise (white: `PCG64` seeded from
  `SeedSequence([spec.seed, source_index])`; LFSR: precomputed period table, gathered at step
  positions), applies its envelope and level, mixes; then instrument filter (FIR), the amplifier
  envelope, drive; notes are summed at `round(start_seconds * sample_rate)`; total length = last
  note end + release. Then de-click (impl §5), normalize if asked, clip and report. Raise
  `SoundRenderError(spec.name)` when `numpy.isfinite` fails.
- [ ] **Step 4: Run** — PASS. Also run `uv run pytest --dummy-only tests/audio/test_synth.py` (existing, unchanged).
- [ ] **Step 5: Commit** `feat(audio): renderer for oscillators, noise, envelopes, layers, notes and chords`.

---

### Task 5: Sound files: v1 schema, v0 recipes and the short-name index

**Files:**
- Create: `src/glitchygames/audio/assets.py`
- Create: `tests/audio/fixtures/sounds/` (valid files: the feature spec §9.2 pickup, a v0 recipe
  file copied from Mr. Muncher's shapes, two files defining the same name for the duplicate test)
- Create: `tests/audio/fixtures/malformed/` (≥ 20 `.toml` cases, each with its expected message in
  a sibling `expected.toml` table keyed by file name)
- Test: `tests/audio/test_assets.py`, `tests/audio/test_sound_names.py`

**Interfaces:**
- Consumes: Task 3 `Instrument`, `build_spec`; existing `recipes.SoundRecipe.from_dict`.
- Produces:
  - `class SoundAssetError(GlitchyGamesAudioError)` (in `exceptions.py`).
  - `load_sound_file(path: Path) -> SoundFile` (cached per resolved path and mtime), where
    `SoundFile.version: int`, `.waves: Mapping[str, Wave]`, `.instruments: Mapping[str, Instrument]`,
    `.sounds: Mapping[str, SoundEntry]`. `SoundEntry` holds the instrument reference or `file`, the
    identity fields (`pitch`, `notes`, `chord`, `length`, `transpose`) and `PlaybackDefaults`.
    A v0 file's recipes become `SoundEntry(legacy_recipe=SoundRecipe, ...)`.
  - `ShortNameIndex(directory: Path)` with `.resolve(name: str) -> SoundLocation` (a
    `.toml` path plus table name, or a recorded file path), raising `KeyError` (unknown, naming
    the directory and `difflib.get_close_matches`) or `SoundAssetError` (duplicate, naming both
    files).
  - `is_path_reference(source: str) -> bool` (`/`, `#` or a suffix in `('.toml', '.wav', '.ogg')`).

- [ ] **Step 1: Write the failing tests**

```python
def test_the_pickup_example_loads():
    sound_file = load_sound_file(FIXTURES / 'sounds' / 'pickups.toml')
    assert sound_file.version == 1 and 'coin' in sound_file.sounds

@pytest.mark.parametrize('case', MALFORMED_CASES, ids=lambda case: case.name)
def test_each_malformed_file_names_its_field_and_reason(case):
    with pytest.raises(SoundAssetError) as raised:
        load_sound_file(case.path)
    assert case.expected_path in str(raised.value) and case.expected_reason in str(raised.value)

def test_a_typo_suggests_the_field():
    with pytest.raises(SoundAssetError, match="did you mean 'envelope'"):
        load_sound_file(FIXTURES / 'malformed' / 'envelope_typo.toml')

def test_a_later_milestone_field_says_when_it_arrives():
    with pytest.raises(SoundAssetError, match='routes arrives in M2'):
        load_sound_file(FIXTURES / 'malformed' / 'routes_in_m1.toml')

def test_newer_versions_are_refused_and_v0_recipes_load():
    with pytest.raises(SoundAssetError, match='version 99'):
        load_sound_file(FIXTURES / 'malformed' / 'version_99.toml')
    assert load_sound_file(FIXTURES / 'sounds' / 'legacy_recipes.toml').version == 0

def test_paths_escaping_the_package_are_refused(): ...
def test_short_names_and_recorded_file_stems_resolve(): ...
def test_a_duplicate_short_name_names_both_files(): ...
def test_a_missing_sound_directory_is_a_key_error_naming_it(tmp_path):   # Review Focus
    with pytest.raises(KeyError, match=str(tmp_path / 'sounds')):
        ShortNameIndex(tmp_path / 'sounds').resolve('coin')
```

The malformed corpus must cover at least: missing header, wrong `kind`, unknown top-level table,
unknown instrument field, unknown source field, two of `wave`/`noise`, five sources, bad envelope
curve, negative attack, sustain > 1, `duty` 1.0, unknown wave name, invalid LFSR taps, `pitch` with
`notes`, malformed note token, chord of 9, unknown `bus`, `volume` > 1, a `routes` table (M2), a
`wavetable` source (M4), a sample path that escapes, a missing instrument reference.

- [ ] **Step 2: Run** `uv run pytest --dummy-only tests/audio/test_assets.py tests/audio/test_sound_names.py -v` — FAIL.
- [ ] **Step 3: Implement `assets.py`** with pydantic v2 models, `extra='forbid'`, one model per
  table of impl §6.1 restricted to M1 fields; later-milestone field names are listed in
  `FIELDS_ARRIVING_LATER: dict[str, str]` (`'routes': 'M2'`, `'parameters': 'M2'`, `'live': 'M2'`,
  `'wavetable': 'M4'`, `'sample': 'M4'`, ...) and produce the "arrives in" message. Render pydantic
  `loc` tuples as TOML paths (`instruments.pickup.sources.tone.wave`).
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(audio): sound files (v1 schema, v0 recipes) and the short-name index`.

---

### Task 6: Accounting and the library (`sound()`, cache modes, compile accounting)

**Files:**
- Create: `src/glitchygames/audio/accounting.py`, `src/glitchygames/audio/library.py`
- Test: `tests/audio/test_audio_accounting.py`, `tests/audio/test_sound_library.py`,
  `tests/audio/test_sound_cache.py`

**Interfaces:**
- Consumes: Tasks 3–5.
- Produces:
  - `accounting.py`: `AudioFrameAccount(audio_seconds: float, audio_work: tuple[tuple[str, str, int], ...])`;
    `class AudioAccountant` with `measure(kind: str, name: str) -> ContextManager[None]`,
    `take_frame() -> AudioFrameAccount` (returns and resets; at most 32 entries, the rest summed
    into `('other', '', microseconds)`), `setup_mode: bool` (compiles before the first logic frame
    are attributed to setup), `compile_log: tuple[CompileRecord, ...]` (last 8:
    `CompileRecord(frame_number: int | None, name: str, milliseconds: float, during_setup: bool)`).
    Kinds: `'compile'`, `'decode'`, `'live_chunk'`, `'cache_read'`.
  - `library.py`: `class CacheMode(enum.StrEnum)`: `NONE = 'none'`, `RAM = 'ram'`, `DISK = 'disk'`;
    `class Sound` (impl §8 fields `name`, `length`, `peak`, `is_live`; plus internal
    `spec: SoundSpec`, `samples_float: numpy.ndarray | None` (float64 mono, None for a `none`-mode
    sound not yet compiled), `samples_int16: numpy.ndarray | None`, `mixer_sound() -> pygame.mixer.Sound | None`
    which builds the pygame sound on first call when a mixer exists); `class SoundLibrary`
    with `__init__(self, *, cache: CacheMode, accountant: AudioAccountant, waves: WaveRegistry,
    tuning_source: Callable[[], Tuning], memory_limit_bytes: int = 256 * 1024 * 1024)`,
    `sound(source, *, scene_sound_directory: Path | None, pitch=None, notes=None, chord=None,
    length=None, transpose=0.0, parameters=None) -> Sound`, `compile_for_play(sound: Sound) -> Sound`
    (identity for `ram`; a fresh compile under `none`), `warm(requests, *, budget_ms=None) -> float`,
    `add_recipes(recipes: Iterable[SoundRecipe]) -> None`, `names() -> tuple[str, ...]`,
    `statistics() -> CacheStatistics(hits: int, misses: int, compiles: int, bytes_held: int)`.
  - `CacheMode.DISK` raises `ValueError('the disk cache arrives in M3')` in M1.

- [ ] **Step 1: Write the failing tests**

```python
def test_equal_requests_return_the_same_object_and_compile_once(library):
    first = library.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')
    assert all(library.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5') is first for _ in range(100))
    assert library.statistics().compiles == 1

def test_cache_none_compiles_on_every_play(library_without_cache):
    sound = library_without_cache.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')
    for _ in range(5):
        library_without_cache.compile_for_play(sound)
    assert library_without_cache.statistics().compiles == 5

def test_compiles_are_attributed_to_setup_or_their_frame(library, accountant):
    accountant.setup_mode = False
    accountant.frame_number = 30
    library.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='D5')
    assert accountant.compile_log[-1].frame_number == 30 and not accountant.compile_log[-1].during_setup

def test_frame_account_caps_entries_and_sums_the_rest(accountant): ...   # 40 measured pieces -> 32 entries, last is 'other'
def test_v0_recipes_compile_bit_identical_to_today(library):              # impl §10.4
    recipe = MUNCHER_LIKE_RECIPE
    library.add_recipes([recipe])
    compiled = library.sound(recipe.name, scene_sound_directory=None)
    numpy.testing.assert_array_equal(compiled.samples_float, recipe.render(sample_rate=44100))

def test_a_sound_compiled_without_a_mixer_plays_once_the_mixer_starts(): ...   # Review Focus
def test_a_48000_hz_mixer_compiles_at_its_rate_with_another_identity(): ...    # Review Focus
def test_memory_limit_evicts_least_recently_played_sounds_that_are_not_playing(): ...
def test_disk_mode_is_refused_until_m3(): ...
```

- [ ] **Step 2: Run** `uv run pytest --dummy-only tests/audio/test_audio_accounting.py tests/audio/test_sound_library.py tests/audio/test_sound_cache.py -v` — FAIL.
- [ ] **Step 3: Implement.** `measure` reads `clock.raw_counter_ns()` twice. `sound()` memoizes
  `(source key, frozen identity arguments, sample rate, tuning) -> identity key` (impl §6.2), then
  looks up the compiled `Sound`. The mixer rate is `synth.mixer_sample_rate()` at request time.
  v0 entries compile through `SoundRecipe.render(sample_rate=...)` unchanged.
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(audio): sound library with one-call sound(), cache modes and accounting`.

---

### Task 7: Voices, buses and the channel partition

**Files:**
- Create: `src/glitchygames/audio/voices.py`, `src/glitchygames/audio/buses.py`
- Modify: `src/glitchygames/audio/live.py` (`reserve_live_voice_pool` gains the library and legacy
  counts; see Step 3)
- Test: `tests/audio/test_voices.py`, `tests/audio/test_buses.py`,
  `tests/audio/test_sound_handles.py`, `tests/audio/test_channel_partition.py`

**Interfaces:**
- Consumes: Task 6 `Sound`, `SoundLibrary.compile_for_play`.
- Produces:
  - `reserve_channels(*, live_pool: int, library_channels: int, legacy_channels: int) -> ChannelPartition`
    (`ChannelPartition(live: tuple[int, ...], library: tuple[int, ...], legacy_count: int)`),
    replacing `reserve_live_voice_pool`'s body; `reserve_live_voice_pool(pool_size)` stays as a
    wrapper until M2 removes it.
  - `class BusTree` with default buses `master`, `music`, `effects`, `ui`, `ambience`,
    `dialogue`; `add(name, *, parent='master', volume=1.0, reserved_channels=0)`,
    `__getitem__(name) -> Bus`; `Bus.volume`, `.mute`, `.solo`, `.effective_gain() -> float`.
    Reservations: `ui` 2, `music` 2.
  - `class VoiceTable` with `play(sound: Sound, *, volume, pan, bus, priority, loop, persist,
    owner: object) -> SoundHandle`, `advance(*, dt: float, paused_owners: Collection[object]) -> None`,
    `silenced(channel_index: int) -> None`, `stop_owner(owner, *, fade_seconds=0.05)`,
    `close(*, fade_seconds=0.05)`, `snapshot() -> tuple[ChannelState, ...]`
    (`ChannelState(index: int, group: str, state: str)`; states `idle`, `playing`, `fading`,
    `paused`).
  - `SoundHandle(slot: int, generation: int)` bound to its table; methods `stop(*, fade=0.05)`,
    `cancel()`, `release()`, `is_playing`, `set_volume(volume, *, fade=0.0)`, `set_pan(pan)`;
    each returns `False` on a stale handle.
  - `constant_power_gains(*, pan: float, gain: float) -> tuple[float, float]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_constant_power_pan_keeps_power_within_a_tenth_of_a_db():
    powers = [sum(side ** 2 for side in constant_power_gains(pan=pan, gain=1.0)) for pan in numpy.linspace(-1, 1, 21)]
    assert 10 * numpy.log10(max(powers) / min(powers)) <= 0.1

def test_library_and_legacy_plays_never_cut_each_other(mixer):        # AUD-MIX-008
    partition = reserve_channels(live_pool=4, library_channels=32, legacy_channels=8)
    handles = [table.play(SHORT_SOUND, **PLAY_DEFAULTS) for _ in range(40)]
    legacy_channels = [LEGACY_SOUND.play() for _ in range(8)]
    assert all(channel is not None and channel.get_busy() for channel in legacy_channels)
    assert sum(handle.is_playing for handle in handles) == 32

def test_stealing_is_deterministic_and_prefers_releasing_low_priority_old_voices(): ...   # 3 identical runs, same steal log
def test_ui_reservation_is_never_starved_by_an_effects_storm(): ...
def test_a_paused_voice_is_never_reaped_or_reused(table):          # impl §7.3
    handle = table.play(ONE_SECOND_SOUND, owner=GAME_SCENE, **PLAY_DEFAULTS)
    for _ in range(300):
        table.advance(dt=1 / 60, paused_owners={GAME_SCENE})
    assert handle.is_playing

def test_is_playing_follows_played_time_not_the_device(table): ...
def test_stale_handles_return_false_after_the_slot_is_reused(): ...
def test_one_sound_played_many_times_is_many_voices(table):        # Review Focus
    handles = [table.play(ONE_SECOND_SOUND, owner=GAME_SCENE, **PLAY_DEFAULTS) for _ in range(3)]
    handles[0].stop()
    assert [handle.is_playing for handle in handles[1:]] == [True, True]

def test_bus_volume_applies_to_playing_channels(): ...
def test_solo_mutes_non_soloed_siblings(): ...
def test_release_on_a_non_looping_baked_sound_returns_false(): ...
```

- [ ] **Step 2: Run** `uv run pytest --dummy-only tests/audio/test_voices.py tests/audio/test_buses.py tests/audio/test_sound_handles.py tests/audio/test_channel_partition.py -v` — FAIL.
- [ ] **Step 3: Implement.** `reserve_channels` keeps `reserve_live_voice_pool`'s "grow once per
  process" rule and its comments (BUGS.md #145): total = live + library + legacy,
  `set_reserved(live + library)`. Plays use `pygame.mixer.Channel(index).play(sound, loops=-1 if loop else 0)`
  then `set_volume(left, right)`. Steals call `Channel.fadeout(10)` and mark the channel fading;
  the stealer takes another free channel, or waits one frame (impl §7.1).
- [ ] **Step 4: Run** — PASS; also `uv run pytest --dummy-only tests/audio/test_live.py` (existing).
- [ ] **Step 5: Commit** `feat(audio): voice table, buses and the live/library/legacy channel partition`.

---

### Task 8: `AudioEngine`, the engine options and the frame hook

**Files:**
- Create: `src/glitchygames/audio/engine.py`
- Modify: `src/glitchygames/audio/__init__.py` (exports: `Note`, `Hz`, `Midi`, `Scale`,
  `PitchTable`, `Tuning`, `Wave`, `WavePoint`, `Harmonics`, `CYCLE`, `LEVEL`, `Noise`,
  `Instrument`, `AudioEngine`, `Sound`, `SoundHandle`, `CacheMode`, `SoundAssetError`,
  `SoundRenderError`, `render_to_file` (Task 9))
- Modify: `src/glitchygames/engine/game_engine.py` (options next to `--live-voice-pool` at ~965;
  channel reservation at ~1817; `_shutdown`)
- Modify: `src/glitchygames/scenes/scene.py` (`audio` property beside `live_audio` at ~1262; the
  per-frame call beside `_live_audio.update` at ~1227; `Scene.SOUND_DIRECTORY = 'sounds'`;
  `SceneManager` sets `accountant.setup_mode` around `_setup_new_scene`)
- Modify: `src/glitchygames/replay/driver.py` (`REPLAY_LOCAL_OPTIONS` += `'sound_cache'`,
  `'sound_diagnostics'`)
- Modify: `src/glitchygames/replay/silence.py` (after each `channel.stop()` and `pygame.mixer.stop()`,
  call the active audio engine's `silenced(...)`)
- Modify: `src/glitchygames/sources.py`, `live_sources.py`, `host.py`, `recording.py`,
  `replay/playback.py`, `replay/driver.py` — `end_frame(..., audio_frame: AudioFrameAccount | None = None)`;
  only `RecordingSources` writes it.
- Modify: `src/glitchygames/recording_history.py` (`AUDIO_SECONDS_FIELD = 'audio_seconds'`,
  `AUDIO_WORK_FIELD = 'audio_work'`, both in `MEASUREMENT_FRAME_FIELDS`)
- Test: `tests/audio/test_audio_engine.py`, `tests/audio/test_audio_engine_integration.py`,
  `tests/test_recording_history.py` (extend)

**Interfaces:**
- Consumes: Tasks 1–7.
- Produces: `AudioEngine` exactly as impl §8 (`sound`, `play`, `beep`, `diagnostics`, `stop_all`,
  `waves`, `buses`, `tuning`, `sounds`), plus engine-facing `update(*, dt, active_scene,
  previous_scene, active_transitions, paused_owners) -> None` (same arguments as
  `LiveAudio.update`), `take_frame_account() -> AudioFrameAccount`, `silenced(channel_index: int | None)`
  (None = all), `close()`, and `snapshot() -> AudioDiagnosticsSnapshot` (Task 10 reads it).
  `SceneManager.audio -> AudioEngine` (a `ContextSlot` value, impl §8). Options:
  `--sound-channels N` (default 32), `--sound-cache {none,ram,disk}` (default `ram`; `disk` refused
  with `OPTIONS_REFUSED` naming M3), `--sound-cache-memory MB` (256), `--crt-power-on-sound {on,off}`
  (on), `--sound-diagnostics`.

- [ ] **Step 1: Write the failing tests**

```python
def test_getting_a_sound_never_plays_it(engine):
    engine.sound('coin')
    assert engine.diagnostics().voices_playing == 0

def test_play_shorthand_splits_identity_and_playback_arguments(engine): ...
def test_without_a_mixer_sound_compiles_and_play_is_a_logged_once_no_op(caplog): ...
def test_a_handle_after_its_scene_switched_or_after_close_returns_false(engine):   # Review Focus
    handle = engine.play('coin')
    engine.close()
    assert handle.stop() is False and handle.is_playing is False

def test_scene_cleanup_fades_the_scenes_voices_unless_persisted(): ...
def test_pause_screen_pauses_and_resumes_voices(): ...                   # a pause longer than the sound
def test_replay_rebuild_silence_ends_voices_in_the_table(): ...
def test_recorded_frames_carry_audio_seconds_and_work_as_measurements(tmp_path): ...
def test_golden_replay_still_matches_under_each_cache_mode(): ...       # paddleslap's via replay_recording_headless, --sound-cache none and ram
def test_sound_cache_is_replay_local(): ...
def test_disk_cache_option_is_refused_until_m3(): ...
```

The `engine` fixture runs a stand-in scene whose `SOUND_DIRECTORY` points at
`tests/audio/fixtures/sounds/`. In game code, `AudioEngine.sound(...)` resolves short names
against the active scene's `SOUND_DIRECTORY`, relative to its package directory
(`replay.tools.identity.game_identity(game=...).package_directory`), so the public signature stays
impl §8's. The library's internal `scene_sound_directory=` argument is how the engine passes it.

- [ ] **Step 2: Run** the new tests plus `uv run pytest --dummy-only tests/test_recording_history.py tests/replay -x` — the new ones FAIL, existing pass.
- [ ] **Step 3: Implement.** In the frame: `SceneManager` calls `audio.update(...)` where it calls
  `_live_audio.update(...)` today, and passes `audio_frame=audio.take_frame_account()` to
  `active_sources().end_frame(...)` beside `processing_seconds` (scene.py ~2038 and the scoped call
  ~1945). Accountant `setup_mode` is True from engine start until the first logic frame of each new
  scene's first `dt_tick`.
- [ ] **Step 4: Run** `uv run pytest --dummy-only tests/audio tests/test_recording_history.py tests/replay tests/engine` — PASS.
- [ ] **Step 5: Commit** `feat(audio): AudioEngine on the scene manager, sound options and per-frame accounting`.

---

### Task 9: Offline rendering and the `sound-render` / `sound-migrate` tools

**Files:**
- Create: `src/glitchygames/audio/offline.py`, `src/glitchygames/replay/tools/sound_tools.py`
- Modify: `src/glitchygames/replay/tools/registry.py` (two `Tool(...)` entries, `runs_game=False`,
  like `performance-pages`)
- Modify: `tests/replay/tools/test_an_unseen_game.py` (a case per new tool: CLAUDE.md requires one)
- Test: `tests/audio/test_offline.py`, `tests/replay/tools/test_sound_tools.py`

**Interfaces:**
- Consumes: Task 6 `Sound`, Task 4 `render_sound`.
- Produces: `render_to_file(sound: Sound, path, *, sample_rate=None, sample_format='int16',
  loops=1, tail_seconds=None, stems=False, events=()) -> RenderReport(path, frames, peak, clip_count)`
  (`parameter_timeline` is accepted and must be None in M1: `ValueError('live sounds arrive in M2')`);
  tools `glitchygames sound-render SOURCE -o PATH` and `glitchygames sound-migrate FILE`
  (v0 recipes → v1 TOML via `tomli_w`, round-trip tested). WAV writing uses the standard library
  `wave` module through `output_files.write_aside_then_replace`.

- [ ] **Step 1: Write the failing tests**

```python
def test_offline_render_equals_the_compiled_buffer_bit_for_bit(tmp_path, library_without_mixer):
    sound = library_without_mixer.sound(PULSE_INSTRUMENT, scene_sound_directory=None, notes='B5:0.06 E6:0.18')
    report = render_to_file(sound, tmp_path / 'coin.wav')
    assert numpy.array_equal(read_wav_int16(report.path), sound.samples_int16)

def test_events_mix_at_exact_sample_offsets(tmp_path): ...
def test_tail_stops_after_100_ms_below_minus_90_dbfs(tmp_path): ...
def test_float32_output_keeps_overs_and_reports_clips(tmp_path): ...
def test_migrate_round_trips_a_v0_recipe_file(tmp_path): ...            # load(migrated) compiles to the same samples except for noise seeds
def test_sound_render_tool_writes_the_file_and_exits_success(tmp_path): ...
```

- [ ] **Step 2: Run** `uv run pytest --dummy-only tests/audio/test_offline.py tests/replay/tools/test_sound_tools.py tests/replay/tools/test_an_unseen_game.py -v` — FAIL.
- [ ] **Step 3: Implement** both modules and the registry entries.
- [ ] **Step 4: Run** — PASS, including `tests/replay/tools/test_registry.py`.
- [ ] **Step 5: Commit** `feat(audio): offline rendering and the sound-render and sound-migrate tools`.

---

### Task 10: The Audio debug panel

**Files:**
- Modify: `src/glitchygames/debug/overlay.py` (`DebugPanel.AUDIO = 'audio'` after `PERFORMANCE`;
  a rolling per-frame audio-work history beside `_frame_times`, same `GRAPH_WINDOW_SECONDS`)
- Modify: `src/glitchygames/debug/panels.py` (`DebugFrameInfo.audio: AudioDiagnosticsSnapshot | None`
  replacing `live_voice_count`; `draw_audio_panel`, `draw_audio_header`; colour constants)
- Modify: `src/glitchygames/scenes/scene.py` (~1286: build `DebugFrameInfo(audio=...)`)
- Modify: `src/glitchygames/engine/game_engine.py` (`--sound-diagnostics` turns the overlay on at
  the Audio panel)
- Test: `tests/debug/test_audio_panel.py`; update the existing overlay tests that pass
  `live_voice_count`

**Interfaces:**
- Consumes: Task 8 `AudioEngine.snapshot()` →
  `AudioDiagnosticsSnapshot(cache_mode: CacheMode, device: str, voices_live: int,
  voices_library: int, voices_legacy: int, compiles_last_second: int, cache_hit_rate: float | None,
  frame_work_by_kind: Mapping[str, float], frame_processing_seconds: float | None,
  channels: tuple[ChannelState, ...], bus_levels: Mapping[str, float], muted_buses: frozenset[str],
  compile_log: tuple[CompileRecord, ...])`.
- Produces: `draw_audio_panel(*, surface, overlay, font, frame_info) -> None` and
  `draw_audio_header(*, surface, font, frame_info, top: int) -> int` (returns the next line's y).
  Colours: `AUDIO_COMPILE_COLOR = (230, 60, 60)`, `AUDIO_DECODE_COLOR = (240, 150, 40)`,
  `AUDIO_LIVE_COLOR = (70, 130, 240)`, `AUDIO_CACHE_COLOR = (150, 150, 150)`;
  channel `idle (60, 60, 60)`, `playing (80, 200, 100)`, `fading (230, 200, 60)`, `paused (120, 120, 200)`.

- [ ] **Step 1: Write the failing tests** (pixel assertions; CLAUDE.md, Testing Guidelines):

```python
def test_a_gameplay_compile_draws_a_compile_coloured_bar_in_its_frame_column(display):
    overlay = overlay_with_audio_history(compile_at_frame=10, frames=60)
    draw_audio_panel(surface=display, overlay=overlay, font=FONT, frame_info=frame_info_with_audio())
    assert colour_present_in(display, audio_graph_column_rect(overlay, frame=10), AUDIO_COMPILE_COLOR)

@pytest.mark.parametrize('state, colour', CHANNEL_STATE_COLOURS.items())
def test_each_channel_state_has_its_colour(display, state, colour): ...
def test_gameplay_compiles_are_red_in_the_log(display): ...
def test_cache_none_header_is_red(display): ...
def test_the_all_panel_draws_only_the_header(display): ...
def test_the_panel_is_absent_from_screenshots(): ...
def test_f4_reaches_the_audio_panel_after_performance(): ...
def test_sound_diagnostics_starts_on_the_audio_panel(): ...
```

- [ ] **Step 2: Run** `uv run pytest --dummy-only tests/debug -v` — new tests FAIL.
- [ ] **Step 3: Implement**, following `draw_performance_panel`'s structure and helpers
  (`_draw_text_lines`, the cached translucent backings, `HUD_*` constants).
- [ ] **Step 4: Run** `uv run pytest --dummy-only tests/debug tests/scenes` — PASS.
- [ ] **Step 5: Commit** `feat(debug): Audio panel for per-frame audio work, channels, buses and compiles`.

---

### Task 11: CRT power-on sound

**Files:**
- Create: `src/glitchygames/crt_power_on_sound.py`
- Modify: `src/glitchygames/crt_power_on.py` (`play_power_on` and `play_power_on_async` gain
  `sound_cues: PowerOnSoundCues | None = None`; `_PowerOnFrames.next_frame` calls
  `sound_cues.at_progress(progress)` and `sound_cues.frame(dt)` each frame, and `skip()` when a
  key or button ends it)
- Modify: `src/glitchygames/engine/game_engine.py` (`_prepare_run`: compile the CRT sounds, build
  the cues when `should_play` and `--crt-power-on-sound on`)
- Test: `tests/test_crt_power_on_sound.py`; extend `tests/test_crt_power_on.py` with a recording fake

**Interfaces:**
- Consumes: Task 8 `AudioEngine` (system owner: `owner=SYSTEM_OWNER`, `persist=True`), the
  existing progress stage constants in `crt_power_on.py`.
- Produces: `class PowerOnSoundCues(Protocol)` in `crt_power_on.py` (no audio import there);
  `CrtPowerOnSound` implementing it in `crt_power_on_sound.py`, with named constants
  `DEGAUSS_HUM_HZ = 60.0`, `BARS_TONE_HZ = 1000.0`, `FLYBACK_WHINE_HZ` (an audible value chosen
  by ear, documented as lower than a real set's 15,734 Hz), `STATIC_SEED`, `SKIP_FADE_MILLISECONDS = 20`,
  `TAIL_FADE_MILLISECONDS = 500`; cue progress points copied from the power-on's stage starts
  (dot, line, `OPEN_STAGE_START`, `WARM_UP_STAGE_START`, `SETTLED_STAGE_START`).

- [ ] **Step 1: Write the failing tests**

```python
def test_cues_start_each_sound_at_its_progress_point():
    audio = recording_audio_engine()
    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)
    for progress in numpy.linspace(0.0, 1.0, 73):
        cues.at_progress(float(progress))
    assert audio.started_names() == ['crt_power_click', 'crt_degauss', 'crt_flyback_whine', 'crt_static', 'bars_tone']

def test_channel_three_gets_the_hiss_not_the_tone(): ...
def test_offline_render_of_the_sequence_puts_onsets_within_10_ms_of_their_cues(tmp_path): ...  # AUD-CRT-001
def test_skip_fades_to_silence_within_20_ms_without_a_step(): ...                              # AUD-CRT-003, rendered
def test_no_sound_in_headless_replay_recording_or_with_the_option_off(): ...                   # AUD-CRT-002
def test_the_tail_persists_into_frame_zero_then_fades(): ...
def test_the_static_never_draws_from_engine_random_streams(): ...
```

- [ ] **Step 2: Run** `uv run pytest --dummy-only tests/test_crt_power_on_sound.py tests/test_crt_power_on.py -v` — FAIL.
- [ ] **Step 3: Implement.** The sounds are `Instrument`s requested through `audio.sound(...)`;
  the hum is a 60 Hz sine with its 2nd and 3rd harmonics (`Harmonics(fundamental=1.0, octave=0.4,
  octave_and_fifth=0.2)`) swelling over 0.2 s and decaying over 0.5 s; static is white noise
  through a band of FIR filters with a decaying envelope.
- [ ] **Step 4: Run** — PASS; then by hand: `uv run paddleslap --crt-power-on on`, listen, and
  record the owner's sign-off in the task notes (AUD-CRT-001's listening check).
- [ ] **Step 5: Commit** `feat(crt): power-on sound`.

---

### Task 12: Sound Board demo

**Files:**
- Create: `src/demos/sound-board-demo/` (`pyproject.toml`, `README.md`,
  `src/sound_board_demo/__init__.py`, `__main__.py`, `sounds/board.toml`,
  `tests/test_sound_board_demo_*.py`), modelled on `src/demos/dt-demo/`
- Modify: root `pyproject.toml` (the `demos` extra list at ~132, workspace members ~144, sources
  ~157, the dev group ~173/~198, testpaths ~254, `--cov=sound_board_demo` in `addopts` ~284)
- Modify: `tests/workspace_expectations.py` (~57), `mkdocs.yml` (nav ~75, mkdocstrings paths ~181)

**Interfaces:**
- Consumes: the public `glitchygames.audio` API only (no internals).
- Produces: console script `sound-board-demo`; a scene with a keyboard grid (one row per built-in
  wave and noise, keys play notes), a toggle between note names, hertz and scale steps, a chord key,
  and the Audio panel on by default.

- [ ] **Step 1: Write the failing tests:** the demo imports; its scene requests every built-in wave in
  `setup` (the accountant's compile log shows only setup compiles); a scripted key press in a headless
  run plays a voice (`audio.diagnostics().voices_playing == 1`); `tests/test_workspace_config.py`
  passes with the new member.
- [ ] **Step 2: Run** `uv run pytest --dummy-only src/demos/sound-board-demo/tests tests/test_workspace_config.py -v` — FAIL.
- [ ] **Step 3: Implement** the member.
- [ ] **Step 4: Run** — PASS; `uv sync --all-packages` then `uv run sound-board-demo` launches.
- [ ] **Step 5: Commit** `feat(demos): Sound Board demo`.

---

### Task 13: Verify the open M1 items, document, and run the whole gate

**Files:**
- Create: `docs/architecture/sound.md` (with an mkdocs nav entry)
- Modify: `CLAUDE.md` ("Sound Synthesis" section: the new API, cache modes, accounting, the Audio
  panel), `plans/future-features.md` (#53: power-on sound built; #63: M1 built),
  `docs/specs/2026-11-02-sound-engine-implementation-spec.md` (record the verification results
  below in §7.1/§7.2/§10.1 and flip their **[Open]** labels)
- Test: `tests/audio/test_channel_fades.py`

- [ ] **Step 1: Write the probe tests** for the two pygame behaviours the spec leaves open, recording
  through SDL's disk audio driver (as `scripts/audio_glitch_probe.py`'s `dsp` mode does):
  `Channel.fadeout(10)` followed by `Channel.play` on the same channel — measure the largest
  sample step at the switch; and a bus fade stepped once per frame over 50 ms — measure step size.
  Assert against the discontinuity metric of feature spec §16.1.
- [ ] **Step 2: Run** them. If the fadeout-then-play case passes, remove the one-frame steal delay
  (impl §7.1); if it fails, keep the delay and leave the test asserting the delayed path.
- [ ] **Step 3: Browser check (manual):** `nox -s browser -- mr-muncher`, open in Chrome and Safari,
  click, and confirm the CRT power-on sound is heard (AUD-PORT-003). Record the result in the spec.
- [ ] **Step 4: Write the docs** listed above.
- [ ] **Step 5: Run the full gate:** `uv run pytest` (native + dummy, 100% coverage), `nox -s lint`,
  `nox -s static-analysis`, `nox -s lint-docs`. Expected: all pass. Investigate any warning a test
  prints (the owner's rule) before calling M1 done.
- [ ] **Step 6: Commit** `docs(audio): sound architecture, CLAUDE.md, feature status; verified channel behaviours`.

---

## Self-review notes (kept for the executor)

- Spec coverage: every M1 requirement in the feature spec §15 maps to a task — AUD-FUNC-001…008,
  011 (Tasks 3, 6, 8, 9); AUD-PITCH (1, 4); AUD-WAVE-001…006 (2, 4); AUD-SRC-001, 004, 005 (4, 5, 6);
  AUD-INST-001, 007 (drive), 008 (4); AUD-TIME-001, 003, 006 (3, 4, 8); AUD-MIX-001…004, 008 (7);
  AUD-RETRO-003 steps (4); AUD-ASSET-001…005, 006 (ram) (5, 6); AUD-RT-004, 005 (4, 6);
  AUD-MEAS-001 (none, ram), 002 (6, 8); AUD-DIAG-001, 002 (8, 10); AUD-PORT-001…003 (all, 8, 13);
  AUD-CRT-001…003 (11); AUD-DEMO-001 (12).
- Deferred on purpose (not M1): live sounds, routes, parameters, the disk cache, scheduled plays,
  everything M2+.
