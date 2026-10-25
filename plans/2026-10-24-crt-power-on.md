# CRT Power-On Startup Sequence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every game, Bitmappy included (everything started through `GameEngine`), starts
with its canvas switching on like an analogue CRT: a dot, a line, the picture opening, warm-up
flicker, then the configured background, before control is handed to the game.

**Architecture:** A leaf module, `glitchygames/crt_power_on.py`, draws any moment of the
sequence onto a surface from the background pattern (a pure function of progress: easy to test
pixel by pixel) and plays it with a blocking driver (`start()`) and an async one
(`start_async()`, the browser), both called by `GameEngine._prepare_run` before the game's
scene is built. When it plays is decided once from the options and SDL's video driver.

**Tech Stack:** pygame-ce 2.5.8 (surfaces, blend flags, `pygame.transform`), the engine's
background patterns (`glitchygames/backgrounds.py`), `glitchygames/clock.measured_seconds`
(real time for a diagnostic-only presentation).

**Spec:** `plans/future-features.md` #53 (the sequence, the rules it keeps, and the user's
requirement: "wired up to the front of every game ... on their canvas before we hand control to
them").

## Global Constraints

- Branch from `main` after PR #99 merges and its docs deploy.
- Visual only, before the game's first scene exists: no recording, screenshot, golden trace,
  game state, random stream, frame clock or scene clock changes. No randomness at all: the
  flicker is a fixed table.
- Opaque on cocoa: `make_opaque` on each presented frame (glitchygames/opacity.py).
- Doors: events are taken only through `active_sources().pump_events()`; time through
  `clock.measured_seconds()` (allowed for diagnostics); nothing is posted except a QUIT handed
  back with `recording.post_input_event`.
- pytest-mock only; keyword arguments; full names; frozen pydantic models for new data
  classes; no `# noqa`; lint before tests; 100% coverage.

## Review Focus

1. **A test or headless run slowed or changed**: `auto` must skip on SDL's dummy video driver,
   so no existing test (all run on dummy) plays it. Task 3 tests the decision for every case.
2. **A replay or recording disturbed**: pumping events before frame 0 of a recording would
   record input the game never saw. `auto` skips with `--record-trace`, `--replay-trace`,
   `--audit` and `--rebaseline`, and `on` is refused with them. Task 3 tests it.
3. **The window closed during the sequence**: the QUIT must reach the game (it then quits at
   once), never be lost. Task 4 tests it.
4. **Input meant for the game eaten**: a key pressed to skip is the skip; the sequence drops
   it, and the game starts with no input pending. Task 4 tests that nothing else is posted.
5. **A huge or tiny window**: the drawing must work at any size, 1x1 included, with no
   division by zero. Task 2 tests 1x1 and an odd size.

---

## The sequence (constants in `glitchygames/crt_power_on.py`)

| Stage | Progress | What is drawn |
|---|---|---|
| Off | 0.00-0.08 | black |
| Dot | 0.08-0.18 | a bright white-blue dot in the centre, growing to a few pixels |
| Line | 0.18-0.30 | the dot stretches horizontally to a 2-4 px line across the screen, brightest at its middle |
| Open | 0.30-0.50 | the picture opens vertically from the line: the pattern scaled into a centred band whose height eases from the line to full; the band's leading edges brighter |
| Warm-up | 0.50-0.90 | the full pattern, its brightness from `WARM_UP_BRIGHTNESS` (overshoot then sag), a vertical roll on 2 frames, scanlines fading out, a short colour wobble |
| Settled | 0.90-1.00 | the pattern exactly as `paint_default_background` draws it |

`SEQUENCE_SECONDS = 1.2`. The last frame drawn is exactly the default background, so the hand
over to the game is the same picture the engine painted before this feature.

---

### Task 1: Options and the decision

**Files:**
- Create: `glitchygames/crt_power_on.py` (the decision part)
- Modify: `glitchygames/engine/game_engine.py` (the option; the refusal)
- Test: `tests/test_crt_power_on.py`, `tests/engine/test_engine_lifecycle.py`

**Interfaces:**
- Produces: `class CrtPowerOnMode(StrEnum): AUTO = 'auto'; ON = 'on'; OFF = 'off'`;
  `def should_play(*, mode: CrtPowerOnMode, video_driver: str, options: Mapping[str, Any]) -> bool`;
  option `--crt-power-on {auto,on,off}` (default `auto`, Graphics Options).

- [ ] **Step 1: Write the failing tests** (`tests/test_crt_power_on.py`)

```python
@pytest.mark.parametrize(
    ('mode', 'video_driver', 'options', 'plays'),
    [
        (CrtPowerOnMode.AUTO, 'cocoa', {}, True),
        (CrtPowerOnMode.AUTO, 'dummy', {}, False),  # headless, every test
        (CrtPowerOnMode.AUTO, 'cocoa', {'replay_trace': 'run.jsonl.gz'}, False),
        (CrtPowerOnMode.AUTO, 'cocoa', {'record_trace': 'run.jsonl.gz'}, False),
        (CrtPowerOnMode.OFF, 'cocoa', {}, False),
        (CrtPowerOnMode.ON, 'dummy', {}, True),  # the sequence's own tests
    ],
)
def test_when_the_sequence_plays(mode, video_driver, options, plays):
    assert should_play(mode=mode, video_driver=video_driver, options=options) is plays
```

and in `tests/engine/test_engine_lifecycle.py`: `--crt-power-on on` with `--replay-trace` or
`--record-trace` exits `OPTIONS_REFUSED` (same shape as `TestListInputDevices`' refusal test).

- [ ] **Step 2: Run them, see them fail** (`ImportError`, unknown option).
- [ ] **Step 3: Implement** `CrtPowerOnMode`, `should_play` (auto: video driver not `dummy`
  and none of `replay_trace`, `record_trace`, `audit`, `rebaseline` set), the option, and the
  refusal beside `_refuse_listing_input_devices_during_a_run`.
- [ ] **Step 4: Lint, run, commit** ("--crt-power-on: when the power-on sequence plays").

### Task 2: Drawing one moment

**Files:** `glitchygames/crt_power_on.py`, `tests/test_crt_power_on.py`

**Interfaces:**
- Produces: `def draw_power_on(*, surface: pygame.Surface, picture: pygame.Surface, progress: float) -> None`
  (draws the moment `progress` in [0, 1] of the sequence onto `surface`, `picture` being the
  settled background at the same size); the stage boundaries and `WARM_UP_BRIGHTNESS`
  (a tuple of brightness factors, one per warm-up frame step) as constants.

- [ ] **Step 1: Write the failing tests**, on real surfaces, judging pixels:
  - progress 0.0: every pixel black;
  - in the dot stage: the centre pixel bright (each channel > 200), a corner black;
  - in the line stage: the centre row bright at the left and right thirds, the row 10% above
    black;
  - in the open stage at its midpoint: the middle row shows the pattern's colours, the top row
    black;
  - progress 1.0: identical to `paint_default_background` on a surface of the same size
    (compare `pygame.image.tobytes`);
  - every stage at 1x1 and 7x5 draws without error;
  - drawing never changes `picture` (compare its bytes before and after).
- [ ] **Step 2: Run, see them fail.**
- [ ] **Step 3: Implement** with pygame only: fills, `pygame.draw.circle`/`rect`, the picture
  scaled into the band with `pygame.transform.smoothscale` (guard sizes below 1 px), brightness
  with `fill(..., special_flags=pygame.BLEND_RGB_MULT / BLEND_RGB_ADD)`, scanlines as every
  other row darkened, the roll as a vertical offset blit; `make_opaque` at the end.
- [ ] **Step 4: Lint, run, commit** ("The CRT power-on drawing: dot, line, open, warm-up, settled").

### Task 3: Playing it, blocking and async

**Files:** `glitchygames/crt_power_on.py`, `tests/test_crt_power_on.py`

**Interfaces:**
- Produces: `class PowerOnOutcome(StrEnum): FINISHED, SKIPPED, QUIT`;
  `def play_power_on(*, screen, sources, sleep=time.sleep) -> PowerOnOutcome` and
  `async def play_power_on_async(*, screen, sources, wait_for_tick) -> PowerOnOutcome`.
  Each frame: pump events (drop them; a KEYDOWN, MOUSEBUTTONDOWN, JOYBUTTONDOWN or
  CONTROLLERBUTTONDOWN ends it `SKIPPED`; QUIT ends it `QUIT`), draw the moment from
  `measured_seconds`, flip. Ends with the settled picture on screen.

- [ ] **Step 1: Write the failing tests**: with stand-in sources whose `pump_events` returns
  scripted batches and a fake measured clock: plays to `FINISHED` in about
  `SEQUENCE_SECONDS * 60` frames; a KEYDOWN mid-way ends `SKIPPED` with the settled picture on
  screen; a QUIT ends `QUIT`; the async driver awaits one tick per frame.
- [ ] **Step 2-4**: fail, implement, pass, commit.

### Task 4: Wired to the front of every game

**Files:** `glitchygames/engine/game_engine.py` (`_prepare_run`), `tests/engine/test_engine_lifecycle.py`

- [ ] **Step 1: Write the failing tests** (engine built as the lifecycle tests build it, with
  `--crt-power-on on`, the drivers mocked to record calls):
  - `start()` plays it before the game's scene is constructed (the scene's `__init__` records
    whether the sequence had finished);
  - `start_async()` plays the async driver;
  - a QUIT during it is handed back (`post_input_event`) and the run ends after the game's
    first frame, normally;
  - `--crt-power-on auto` on the dummy driver plays nothing (the default for every test).
- [ ] **Step 2-4**: fail; in `_prepare_run`, after the `--list-input-devices` check, call the
  driver when `should_play(...)` (video driver from `pygame.display.get_driver()`); pass; commit.

### Task 5: Docs and a look on the real display

- [ ] CLAUDE.md (Scene backgrounds: the sequence and `--crt-power-on`), README's Graphics
  Options table, `docs/architecture/argument_system.md`, `plans/future-features.md` #53 →
  COMPLETED.
- [ ] Run every console script on cocoa (`paddleslap`, `brave-adventurer`,
  `brave-adventurer-papyrus`, `clockwork-keep`, `mr-muncher`, `bitmappy`) and the browser
  bundles (`nox -s browser -- mr-muncher`, `-- bitmappy`): it plays before each, the user
  watches and tests it, the stage constants are tuned by eye, and any change is recorded in the
  module's docstring.
- [ ] Full suite on both drivers, `nox -s lint static-analysis`, commit, PR.
