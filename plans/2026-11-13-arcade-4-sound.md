# Arcade Sub-plan 4: Sound Only From the Watched Game — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task (execution is subagent-driven for every engine-context sub-plan: decision 4 of plans/2026-10-25-engine-context.md). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Only one context is heard (the top frame's tile, or later a launched game); every
other inner game runs silent without touching the channels the heard one uses, and a game sees
exactly the same answers heard or silent, so every tile still replays as it does alone.

**Architecture:** An audible flag per engine context (`audio/route.py`, the spike's module name;
the default context is audible, a new inner context silent). The engine keeps a silent context
off the mixer at each of the three ways sound reaches it today, all from the engine's side:
plain `Sound.play()` finds no free channel while a silent inner game builds or steps (every
channel reserved for that call, then put back); the `AudioEngine`'s voice table makes no mixer
call in a silent context (its voices already run by frame time); the old live voices get a block
of channels per context and play silent chunks at volume 0 (the spike's rule). `InnerGame`
gains the switch.

**Tech Stack:** Python 3.14, pygame-ce (SDL_mixer), pydantic (frozen, `extra='forbid'`), pytest
+ pytest-mock + xdist, ruff, basedpyright, ty.

**Spec:** [2026-10-23-arcade-showcase.md](2026-10-23-arcade-showcase.md), Sub-plans item 4
("Sound only from the watched game = engine context sub-plan 5: an audio route per context;
silent tiles keep off the shared channels entirely; only the top frame or a launched game is
heard") and its Decisions of 2026-11-12 (no game changes; build on the full-Arcade spike).
Builds on [2026-11-12-arcade-3-inner-game.md](2026-11-12-arcade-3-inner-game.md) (branch
`arcade-3-inner-game`, PR #185; this branch is stacked on it). Evidence: the spike's
`audio/route.py` (`.superpowers/arcade-spike/engine-changes-main.diff`) and findings
(`engine-context-spike-findings.md`, its audio section).

## How sound reaches the mixer today (2026-11-13)

| Path | Who uses it | Channel | Collides with the heard game? |
| --- | --- | --- | --- |
| Plain `Sound.play()` | PaddleSlap (`ball1.snd.play()`), the engine's ball (`game_objects/ball.py`), `SoundBank.play` (`audio/recipes.py`: Mr. Muncher, Clockwork Keep), Brave Adventurer's `sounds.py` | SDL picks a free unreserved channel | Takes a channel and is heard |
| `AudioEngine` voice table (`audio/voices.py`) | the CRT power-on (skipped before a replay), new code; M2 moves the games here | fixed library channels, the same numbers in every context | Plays over or steals the heard game's channel |
| Old live voices (`audio/live.py`) | Mr. Muncher's projector | fixed live-pool channels | The same; and its lifecycle reads the channel's busy and queue state |

An inner build also re-runs the channel partition (`reserve_channels`, with the recording's
options: a non-default `--sound-channels` or `--live-voice-pool` re-sizes the outer game's
reservation), and `InnerGame.finish` never discards the inner context's audio engine
(`plans/future-work.md`, both from sub-plan 3). `pygame.mixer.music`: no game uses it.

## What the spike did, and what this plan changes in it

The spike routed each path through `play_one_shot` / `route_voice_chunk`, which needed edits in
PaddleSlap's and Brave Adventurer's own code, and gave each context a block of live channels
whose `set_reserved` dropped the sound library's reservation (the #145 bug). Kept: the audible
flag per context, the silent context's live chunks at volume 0 on its own block, the old heard
game's sounds stopped when the heard game changes. Changed: no routing call in any game; plain
`Sound.play()` is kept off the mixer by reserving channels around a silent call instead; the
voice table is muted at its source; the live blocks are allocated inside main's partition.
Dropped: the routing spy (`MIXER_CALLS`).

## Global Constraints

- **No changes must be required for a game to be wrapped**: no file under `src/games/`,
  `src/demos/` or `src/apps/` changes (`git diff --stat` against the base branch empty there).
- **No pygame function is replaced.**
- Ordinary games do not change: in the default context every sound plays exactly as today,
  every existing test, golden replay, golden trace and bundled demo passes unchanged.
- A game sees the same answers heard or silent (`SoundHandle.is_playing`, a voice's end, a
  steal, `create_voice` succeeding or raising), so the sub-plan 3 proof still holds with every
  tile silent and with any one tile heard.
- New data classes: pydantic `BaseModel`, `frozen=True`, `extra='forbid'`; a slot value that is
  changed in place stays a plain class. Every new `ContextSlot` gets an `ISOLATION_CHECKS` entry.
- Keyword arguments; full names; Google docstrings; no lint or type suppressions and no
  configuration edits; 100% coverage; real pygame and real files in tests (SDL's dummy or disk
  audio driver), pytest-mock only for what cannot run.
- Branch `arcade-4-sound` on `arcade-3-inner-game`, one PR; commits local until the owner says;
  commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Decisions (the owner reviews them with the plan)

1. **One flag per context, default audible, a new inner context silent.** `InnerGame` gets an
   `audible` property and `set_audible(*, audible: bool)`; the host keeps at most one inner game
   audible (the Arcade's top frame). The default context stays audible (the Arcade itself).
2. **Plain `Sound.play()` from a silent inner game reaches no channel**: `InnerGame` reserves
   every mixer channel (`pygame.mixer.set_reserved(pygame.mixer.get_num_channels())`) around a
   silent build, step and finish, and restores the reservation after. SDL then finds no free
   channel and `Sound.play()` returns None, as on a busy mixer: nothing starts, so nothing blips
   and no channel is taken. `SoundBank` already treats None as "no free channel". Explicit
   `Channel(i)` calls are unaffected (the other two paths handle themselves).
3. **The voice table is muted at its source**: in a silent context `audio/voices.py` makes no
   mixer call (`play`, `fadeout`, `stop`, `pause`, `unpause`, `set_volume`) and reads a channel
   as idle; voices, their ends, steals and `is_playing` go on by frame time, as they already do.
   Going silent fades the context's playing voices over the existing 50 ms switch-away fade;
   going audible starts nothing already under way (a sound heard from its start only).
4. **One heard set of library channels, swapped to whichever tile is heard; a small live pool
   per tile** (the owner, 2026-11-13, after Task 3's review found that growing the mixer while
   sound plays is BUGS.md #145's heap corruption: "a bigger mixer allocation at startup for the
   arcade in particular", then "we just swap out the active set of 32"). A silent tile's voice
   table touches no channel (decision 3), so only the heard tile needs library channels:
   - **Grown once, at the host's startup, before anything plays**: the host declares how many
     inner games it runs (`reserve_inner_game_channels(*, games: int, ...)`); the engine grows
     the mixer once to the default partition (unchanged) + **two heard sets of 32 library
     channels** + **4 live-voice channels per game**, with the legacy (plain `Sound.play()`)
     channels above all of it and the reservation covering everything below them. The mixer
     never grows again.
   - **The heard set**: the heard tile's voice table plays its logical slots on one heard set.
     When the heard tile changes, the old tile fades out on its set (decision 3's 50 ms) while
     the new tile starts on the other set; the two sets alternate (the owner: "two sets of 32").
     A tile whose recording asks for more library channels than a heard set holds replays
     silent but cannot be made heard (a clear error from `set_audible(audible=True)`).
   - **Live pools**: each inner game takes 4 live-voice channels from the capacity at build
     (Mr. Muncher's projector reads its own channel, so a silent copy still needs real channels;
     its chunks play at volume 0 while silent, the spike's rule); freed at `InnerGame.finish`.
   - An inner game built with no capacity declared, or past the declared count, fails alone with
     a clear error naming the call to make. The default context's partition is exactly as today.
5. **A tile's table keeps its recording's size**: its logical slot count is the recording's
   `--sound-channels` (and its live pool its `--live-voice-pool`, up to the per-game live
   channels), so its steals and drops equal the game run alone; an inner build never
   re-partitions the mixer, and the outer's reservation never changes.
6. **When the heard game changes**, the old one goes silent (decision 3's fade, its live block to
   volume 0) and its plain `Sound.play()` sounds still on unreserved channels are stopped (the
   Arcade itself plays through its `AudioEngine`, never plain `Sound.play()`).
7. **`InnerGame.finish` discards the inner context's audio engine** (`discard_audio_engine`,
   context-scoped; never the process-wide `release_channels`).

## Review Focus

1. **A silent tile and the heard game playing at once**: the heard game's sound plays to its end
   uninterrupted, on its channel. Test in Task 2 (voice table) and Task 1 (plain `Sound.play()`).
2. **A replay's answers heard vs silent**: the sub-plan 3 proof passes with all tiles silent, and
   with one tile switched audible and back mid-replay. Test in Task 4.
3. **Mr. Muncher's projector in a tile while the Arcade's own live voice plays**: neither steals
   the other's channel; `create_voice` succeeds in both. Test in Task 3.
4. **The heard game switching while its sound plays**: the sound stops (fades) within the fade
   time, the new heard game's next sound is heard. Test in Task 4.
5. **A tile whose recording asked for non-default channel options**: its block has those sizes
   and the outer's reservation is unchanged after its build. Test in Task 3.

---

### Task 1: The audible flag, and plain `Sound.play()` kept off the mixer

**Files:** Create `src/glitchygames/audio/route.py` (`AUDIO_ROUTE_SLOT`, `is_audible() -> bool`,
`set_audible(*, audible: bool)`; default audible, `InnerGame` sets its new context silent);
modify `src/glitchygames/inner_game.py` (`audible`, `set_audible`; the reservation around a
silent build, step and finish, restored on every exit path). Tests: `tests/audio/test_route.py`,
`tests/engine/test_inner_game.py`, `ISOLATION_CHECKS`.

- [x] Tests: a silent inner game whose step calls `Sound.play()` leaves every channel idle and
  the reservation as it was after the step (also after a step that raises); an audible one's
  play is heard (a channel busy); the outer's sound already playing on a channel plays on.
- [x] Implement; full suite; commit (`Audio route: a silent inner game's Sound.play() reaches no channel`).

### Task 2: The voice table muted in a silent context

**Files:** `src/glitchygames/audio/voices.py`, `src/glitchygames/audio/engine.py` (going silent
fades the context's voices). Tests: `tests/audio/` (the voice table's file).

- [x] Tests: a voice played in a silent context makes no mixer call (spy on `Channel` methods
  only to assert absence) and its handle's `is_playing`, end and steals equal those of the same
  plays in an audible context frame for frame; the heard context's voice on the same channel
  number plays to its end (Review Focus 1); going silent fades within 50 ms.
- [x] Implement; full suite; commit (`Audio: a silent context's voice table never touches the mixer`).

### Task 3: The heard set and the live pools, grown once at startup; an inner build never re-partitions

**Files:** `src/glitchygames/audio/live.py`, `src/glitchygames/audio/voices.py`
(`reserve_channels`), `src/glitchygames/engine/game_engine.py` (`reserved_channel_partition`
outside an inner context only), `src/glitchygames/inner_game.py` (`finish`: the block freed,
`discard_audio_engine`). Tests: `tests/audio/test_live*.py`, `tests/engine/test_inner_game.py`.

- [x] Tests: Review Focus 3 and 5; a silent context's live chunks play at volume 0 on its own
  block, never on the default context's; the library's reservation is unchanged after an inner
  build and after finish; a finished inner game's block is free again and its audio engine gone.
- [x] Implement; full suite; commit (`Audio: a live-voice block per context; an inner build keeps the outer's partition`).

### Task 4: Switching the heard game, the proof, and the documents

**Files:** `src/glitchygames/inner_game.py` (decision 6 on `set_audible(audible=False)`),
`tests/test_every_recording_replays_inside_an_inner_game.py` (silent and switched runs),
`CLAUDE.md` (Sound Synthesis and Engine Context), `docs/architecture/sound.md`,
`docs/architecture/engine_context.md`, `plans/2026-10-23-arcade-showcase.md` (item 4 done),
`plans/2026-10-25-engine-context.md` (rows S3, S4; sub-plan 5), `plans/future-work.md`.

- [x] Tests: Review Focus 2 and 4: each pair's digests still equal their solo replays with every
  tile silent and with the first tile switched audible at a frame and back; a switched-away
  tile's sounds stop.
- [x] Docs; `uv run pytest`, `nox -s lint`, `nox -s static-analysis`; commit (`Audio: only the
  heard game is heard; the proof with switching`).
- [ ] `nox -s compare-drivers -- --drivers native --fail-on-difference` (the controller runs it).
