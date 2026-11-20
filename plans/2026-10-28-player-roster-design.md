# Players as an Engine Staple: the Player Roster — Design

- **Date:** 2026-10-28
- **Status:** DESIGN, agreed with the owner in conversation on 2026-10-28; a plan follows.
  Parked on 2026-11-08 in the docs PR (#145), to be picked up and implemented later (the owner).
- **Branch:** written on `feature/player-roster` (stacked on `feature/workspace-packages-3a-src-layout`,
  PR #111, merged since); kept in the docs PR from 2026-11-08.

## Where it sits now (2026-11-08)

The order below says "after engine context sub-plan 2 and before sub-plan 6". On 2026-11-08 the
owner folded the engine context plan into the Arcade's (`plans/2026-10-23-arcade-showcase.md`):
engine context sub-plan 2 became Arcade sub-plan 1 ("each engine owns its own state"), and
sub-plan 6 (each game's own events and devices) went into Arcade sub-plan 3 ("a game inside the
Arcade"). So the roster sits between Arcade sub-plans 1 and 3, and is one of the Arcade's
sub-plans: a game launched from the Arcade with a pad or two needs its players to land in that
game. Engine context sub-plan 2 still leaves C16 (Bitmappy's controller singleton) to this work
(its decision 7).

Checked against main on 2026-11-08: `MultiControllerManager` is still 415 lines, and Drawing
Fire's `players.py` and `seats.py` are where the extraction starts.

## Open question: players that are not people (2026-11-08)

This design covers people at devices. Two other plans expect players that are not: the game
samples design (`plans/2026-10-25-game-samples-design.md`: each game's scripted `cpu` player,
beside its human and AI players) and the AI work (`plans/lucid-circuit.md`: the AI playing a
game). Whether a slot can be held by a script or the AI instead of a device, and what JOINING,
the leave rule and reconnecting then mean for it, is open. Answer it before the plan, so the
roster is not built in a way that rules it out.

## Why

Two of our programs already let several people play at once, and each built its own way:

- **Bitmappy** (`src/apps/bitmappy/src/bitmappy/controllers/manager.py`, `MultiControllerManager`,
  415 lines): up to four controllers draw at once. A controller is assigned on its first button
  press, gets a color (red, green, blue, yellow), is tracked as connected, assigned or active,
  is re-attached on reconnect and dropped when idle. It reads pygame controller events by SDL
  instance id and is a process-wide singleton (audit row C16 of
  `plans/2026-10-25-engine-context.md`; the cause of BUGS.md #234).
- **Drawing Fire** (`src/games/drawing-fire/src/drawing_fire/players.py` and `seats.py`, 744
  lines): up to two local players join a running battle. START (Enter on the keyboard) opens a
  seat, the player chooses a side and then a soldier, and holding Back leaves. The keyboard and
  mouse count as one device. Everything is read from the engine's `InputSnapshot`
  (`glitchygames.input.state`), never from pygame, with no clock or randomness of its own, so
  it is replay-safe by construction.

The engine itself has controller and joystick events (`glitchygames/events/controller.py`,
`joystick.py`) and `ActionMap` bindings, but no notion of a player. The owner (2026-10-28):
pull the core multi-controller work into the engine, make players "a sort of staple of the
engine", "but the game can layer on behavior", and reuse it for multiplayer games.

## Goals

1. The engine has players: a **roster** per game, with one lifecycle every game shares.
2. A game configures the roster and layers its own behavior on it, never reimplementing joining.
3. Bitmappy and Drawing Fire both run on it, and Bitmappy's singleton is gone (C16 dissolves:
   the roster is per engine context).
4. Replay-safe: a roster is driven only by the input snapshot and the frame clock, so a replay
   joins, readies and drops the same players on the same frames.

## Non-goals

- **Device routing between games** (which game in the Arcade gets which physical pad): engine
  context sub-plan 6 (S7). The roster reads the snapshot its own context is given.
- Online or networked players.
- A lobby screen or player-name entry: a game may build one as join steps (below); the engine
  ships none.
- Changing what either game does for its players (Bitmappy's cursors, indicators and canvas
  navigation; Drawing Fire's side and soldier choice, intents and pennants).

## Anti-goals (a failure even if it works)

- A second player system living on inside either game after its move.
- Drawing Fire's golden changing because of the extraction (`src/games/drawing-fire/tests/
  fixtures/replays/golden.jsonl.gz` must replay identically; if it can't, stop and ask).
- The roster reading pygame events, the wall clock or an unseeded random source.
- Process-wide roster state.

## The design (the owner's decisions, 2026-10-28)

### The lifecycle every game shares

```
 (join gesture)            (the game's join steps done)          (leave rule)
   ─ join ─▶  JOINING  ─────────── ready() ───────────▶  PLAYING  ───── leave ─────▶  gone
                │                                                                   ▲
                └──────────────── leave while still JOINING (cancels) ──────────────┘
```

- A player's **slot** is held from the moment of joining: the slot number, color and name are
  the engine's and are the same in every game.
- **Engine guarantees:** the player limit; cancelling during JOINING frees the slot;
  reconnecting a device returns its player to the same slot; a log of every join, ready and
  leave; all of it driven from the snapshot.
- **What a game reads:** `roster.players` (everyone, JOINING included), `roster.playing` (only
  PLAYING), each player's `stage`, and joined / ready / left notifications.

### What a game configures

| Setting | Bitmappy | Drawing Fire |
|---|---|---|
| Join gesture | any button | START (Enter on the keyboard) |
| Leave rule | idle for a time (today it drops inactive controllers) | hold Back |
| Max players | 4 | 2 |
| Colors | Bitmappy's four | Drawing Fire's (its army colors stay game state) |
| The keyboard and mouse as a device | no (controllers only, as today) | yes |
| JOINING counts toward the limit | (no steps) | yes (the engine default: the slot is held) |

### Where a game layers on behavior: two hooks

1. **Join steps.** What JOINING means for this game. The engine holds the player in JOINING
   until the game calls `player.ready()`. Bitmappy has no steps (straight to PLAYING); Drawing
   Fire's are choose a side, then choose a soldier.
2. **Per-player game state.** The game attaches its own data to a player (Bitmappy's cursor;
   Drawing Fire's side, soldier and aim); the engine carries it with the player and never looks
   inside.

So someone who presses START in Drawing Fire and walks away mid-choice is visibly JOINING
("player 2 choosing…") and holds the slot until they hold Back or the leave rule drops them.

### What moves where

- **Into the engine** (`src/glitchygames/input/`, per engine context): device identity (the
  keyboard and mouse as one device, each controller), button edges (pressed this frame, held
  for how many frames and seconds: Drawing Fire's `ButtonEdges`), and the roster (slots, the
  lifecycle, the two hooks, the log: the generic part of Drawing Fire's `Seats`), then
  Bitmappy's additions (reconnect to the same slot, per-player colors, more than two players,
  join on any button).
- **Stays in Drawing Fire:** side and soldier choosing (its join steps), turning a device's
  input into an `Intent`, soldier takeover on death, the seat panel's text.
- **Stays in Bitmappy:** cursors, visual indicators and collision avoidance, film-strip and
  slider navigation per player.

## Order (the owner, 2026-10-28)

1. **Extract from Drawing Fire.** Move device identity, button edges and the generic seat
   lifecycle into the engine; Drawing Fire uses them and keeps its join steps. Proof: its golden
   replays byte for byte, and its tests pass unchanged apart from imports.
2. **Grow the roster** with Bitmappy's needs: reconnect to the same slot, per-player colors,
   more than two players, join on any button, the idle leave rule. Each with engine tests.
3. **Move Bitmappy onto the roster**, deleting `MultiControllerManager`'s singleton (C16).
   Bitmappy has no recording, so this lands last, on a proven base.

It sits after engine context sub-plan 2 and before sub-plan 6, whose device routing builds on
the roster.

## Constraints

- The project's rules (CLAUDE.md): Python 3.14, ruff with every rule, basedpyright strict and
  ty, 100% branch coverage, no warnings, descriptive names, American spellings.
- Replay determinism: every golden replays identically after each step.
- The roster's state is per engine context (a `ContextSlot`, `src/glitchygames/engine_context.py`),
  never a class or module global; the process-state guard of sub-plan 2 must see none.
- The engine imports no game or app.

## Left to the builder

- Names and module layout under `src/glitchygames/input/` (one module per responsibility).
- How "held for N seconds" reads time: from the frame clock the snapshot path already uses, as
  Drawing Fire's `ButtonEdges.update(snapshot, dt=...)` does today.
- How the join steps are expressed (a callback, a per-game step object, or the game simply
  calling `player.ready()` from its own update), provided Drawing Fire's two steps and
  Bitmappy's none both fit without special cases.
- How notifications reach the game (polled from the roster each frame, as Drawing Fire's
  `take_new_entries` does, or engine events), provided a replay delivers them identically.

## Settled after the builder check (2026-10-28)

- **A stable device identity across reconnects: in recordings, as an optional field** (the
  owner, 2026-10-28, option A). SDL gives a reconnected controller a new instance id, and the
  snapshot is keyed by instance id today. Each controller gets a stable key (its GUID, which
  the device-added events already carry, `src/glitchygames/events/base.py:1165`, plus a
  tie-breaker for two identical pads), and recordings made from then on carry it, so a replay
  re-seats a reconnected pad exactly as live play did. The field is optional: an older
  recording without it replays exactly as it does today (a key-less pad is a new device). It
  arrives in step 2 with reconnect support; step 1 needs no format change, so Drawing Fire's
  golden stays byte-identical. The alternative (no format change; a reconnected pad is always a
  new player) was declined because it drops Bitmappy's reconnect handling.
- **The idle leave rule is Bitmappy's as it is** (the controller's call, from the code):
  `MultiControllerManager.cleanup_inactive_controllers` uses the frame clock
  (`glitchygames.clock.elapsed_seconds`) and `ASSIGNMENT_TIMEOUT = 5.0` seconds, and an idle
  controller is only unassigned (it stays connected; a press joins again). The engine's idle
  rule does exactly that, so Bitmappy's behavior does not change.
- **The keyboard and mouse is one always-present device** (the controller's call): when it
  joins it takes a slot and counts toward the limit and the log like a controller; it never
  disconnects.
- **`player.ready()` must be called from snapshot-driven logic** (the controller's call): the
  contract for games, documented with the hook; the roster does not police it (Drawing Fire
  already meets it).
- **The join/leave log is in-memory, for the game to show** (the controller's call), as Drawing
  Fire's seat panel reads it today (`Seats.take_new_entries`); it is not written to recordings,
  whose input already reproduces it.
