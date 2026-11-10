# Hidden test windows on real drivers (BUGS.md #225, #227)

Part of the 2026-11-02 backlog run (the owner's explicit permission to plan, fix, commit, test
and push each item on its own branch).

## Investigation

- **#225's error, reproduced on demand (dummy).** A MOUSEMOTION posted over
  `tests/world/test_frame_integration.py`'s player gives the reported failure exactly:
  `AttributeError: 'WorldSprite' object has no attribute 'on_mouse_focus_event'`. The test's
  `WorldSprite` is a plain `pygame.sprite.DirtySprite`; the mouse manager
  (`glitchygames/events/mouse.py`) calls the focus handlers on the topmost sprite under the
  pointer.
- **Host input is not discarded.** The golden harness's `discard_environment_events` drops
  window, audio and device events (`ENVIRONMENT_EVENT_TYPES`) but keeps mouse and keyboard input,
  which tests post themselves. On a real driver the test window is a real window, so the
  machine's pointer over it, or keys while it holds the keyboard, reach the scene. On dummy there
  is no host input, which matches both bugs being native-only and intermittent.
- **Not reproduced: the last step on cocoa.** Neither a pointer warp nor synthetic HID moves
  (`CGEvent` posted to the window's screen position, with and without `Window.focus()`) gave a
  terminal-started test window mouse focus; posting HID events likely needs the Accessibility
  permission. #227 (a 9-pixel native-only difference, seen once) is not reproduced either.

## Design

Close the channel at its source: **on a real video driver, every test window is hidden.** A
hidden window can be under no pointer and hold no keyboard, so the OS sends it no input; it draws
and presents the same pixels (checked on cocoa: same pixel format, same frame hash, shown or
hidden). It also stops the native run's windows from appearing and taking focus during a run.

- `tests/hidden_test_windows.py`: `hides_test_windows(environment)` (a real driver, unless
  `GLITCHYGAMES_SHOW_TEST_WINDOWS=1`), `hidden_set_mode` (wraps `pygame.display.set_mode`, adding
  `pygame.HIDDEN` to the flags), `hide_test_windows()`.
- `tests/harness.py` installs it at import, before any window opens. Every window goes through
  `pygame.display.set_mode` (the harness's display, the engine's `set_display_mode`, the
  renderer service), so one wrapper covers them; a test that mocks `set_mode` replaces the wrapper
  and sees its own arguments unchanged. The dummy driver is left alone (its focus answers are
  what the `frames_vary` reasons describe).

Rejected: extending the discard to input events (the engine re-posts input-type events between
frames on purpose, around playback scopes, and events arriving between the discard and the
frame's pump would still get in).

## Plan

1. The module and its tests (`tests/test_hidden_test_windows.py`: the predicate per driver, the
   wrapper's arguments, the run installed it as its environment says).
2. Docs: `docs/quality/driver_comparison.md`, `CLAUDE.md`'s testing notes, `tests/sdl_defaults.py`.
3. BUGS.md #225, #227 (what is proven and what is not).
4. Full suite: the native run, every test in hidden windows, must agree with dummy frame for
   frame; then the pre-push driver comparison. Commit, push, PR.
