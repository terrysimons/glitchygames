# Pausing is not leaving: `Scene.pause()` and `Scene.unpause()`

> **Status: design agreed with the owner (2026-11-25); nothing is built.** Stacked on
> `refactor/engine-hud-labels`.

**Goal:** A paused scene stays set up. Pausing runs no `cleanup()`, and unpausing runs no
`setup()` or `load_resources()`: each runs once in a scene's life.

## The problem

Every switch runs the old scene's `cleanup()` and the new scene's `setup()`
(`SceneManager.switch_to_scene`, `_setup_new_scene`, `_configure_active_scene`), and
`Scene.resume()` is such a switch. What that costs today:

- Brave's and Clockwork's HUD labels were added again on each resume
  (`bugs/2026-11-22-resuming-from-pause-added-a-second-hud.md`); each game now guards itself.
- Mr. Muncher loses its projector sound: `cleanup()` releases it when play pauses, and `setup()`
  restarts nothing in `Phase.PLAYING`; only `_start_playing` does. Found by reading, to be
  reproduced first.
- Zombies' roster counts its setups to tell a resume from a first entry.

## Design

- `Scene.pause()` is unchanged: it requests a `PauseScene` for the end of the frame.
- `Scene.unpause()` is on the paused scene. The pause screen calls it; by default it makes the
  scene active again. A scene that must react overrides it and calls `super()`. No `on_pause` or
  `on_unpause` hooks until a scene needs the exact moment.
- The scene manager suspends the outgoing scene when the incoming one presents it as paused
  (`debug_subject`, the rule the audio engine already uses to hold a paused scene's voices).
  Unpausing still does what every activation must: forget key presses, snap mode, `dt` of 0,
  caption, frame rate, full redraw, performance tracking; `previous_scene` is the pause screen.
- A suspended scene is cleaned up exactly once if it is never unpaused: quitting from the pause
  screen (`terminate` switches to None), or the pause screen leaving for another scene.
- `resume()` goes: the pause screen's becomes `unpause()`; `GameOverScene`'s, PaddleSlap's and
  Mr. Muncher's, which all start a new game, become `play_again()`. The audio and instant-replay
  `resume()` methods are separate APIs and stay.

## Steps

1. Characterize: `setup`, `cleanup` and `load_resources` counts over enter, pause, unpause, quit;
   reproduce the projector bug.
2. Rename only (`play_again()`). Every recording replays unchanged.
3. The manager and `unpause()`, red first.
4. Games: the roster's pad check moves to `unpause()`; drop the guards in Brave, Clockwork and
   Zombies' roster; Zombies' yard and Mr. Muncher's ready message as each test allows.
5. Docs (`docs/games/`, `scene_start.py`, comments saying setup runs again), the projector's bug
   record, and the HUD record's class and sweep.

## Tests, as behaviours

- Pausing and unpausing, twice, leaves one `setup`, no `cleanup`, and the same sprites.
- Quitting while paused cleans up the paused scene once, and the pause screen once.
- A pause screen left for another scene cleans up the paused scene once.
- A key held into the pause does not quit on release after unpausing.
- Mr. Muncher's projector is held while paused and sounds after unpausing.
- A pad unplugged while paused frees its slot on unpausing.
- Unpausing by Space, a gamepad and window focus all reach `unpause()`.
- Every game with a pause: no sprite added or removed by pausing and unpausing (the class).

## Constraints

Recordings must replay unchanged. One that diverges stops the work and goes to the owner; none is
re-recorded.

## Open

Bitmappy's dialogs have the same fault by another route: they switch away from the editor and
back, so each one cleans up and sets up the editor again, its AI worker included. They do not go
through `pause()`, so this plan leaves them out unless the owner adds them.
