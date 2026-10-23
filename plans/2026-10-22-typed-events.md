# Typed Events — Plan

- **Date:** 2026-10-22
- **Status:** Approved 2026-10-22 ("Do both now", with the unified devices plan); to be implemented
  on `cleanup/post-replay` after the devices work. Decision (the user, 2026-10-22): events become
  immutable (step 5: mutators replaced by `with_fields(**changes) -> Self`).
- **Why:** `HashableEvent` exists because pygame events are not hashable and the engine needs to
  hash and serialize events (API mechanics, recordings, replays). Its fields are reached through
  `__getattr__ -> Any` (the attribute bag; pygame's own `Event.__getattr__` is `Any` too), so every
  handler's `event.pos`, `event.key`, `event.instance_id` is `Any`: no checking, no completion. It
  is the last engine-core ANN401 site (`events/base.py`), kept with a per-file ignore and its reason
  until this lands (`plans/2026-10-20-lint-ignores-cleanup.md`, Phase 4).

## Findings that shape it

- basedpyright does not let a class with `__getattr__` satisfy a Protocol (probed 2026-10-22: "pos
  is not present"), so typed *views* must be real classes, not Protocols over the bag.
- Events are built in one place for dispatch (`GameEngine.process_events`, now through the
  constructor) and a handful elsewhere (`bitmappy/controllers/slider_operations.py`, tests).
- Since #179 an event holds only its type and fields and hashes its content; it is still mutable
  (`__setitem__`, `update`, `clear`), and the chord handler no longer mutates it (#180).
- The chord handlers are declared `keys: list[int]` but receive a tuple of KEYDOWN events (BUGS.md
  #178 item 14).

## Proposal

1. **Per-family subclasses that only declare fields** (no new behaviour, no runtime cost beyond the
   class chosen at construction):
   `class MouseMotionEvent(HashableEvent): pos: tuple[int, int]; rel: tuple[int, int]; buttons:
   tuple[int, int, int]; touch: bool; window: object`, likewise `MouseButtonEvent`,
   `MouseWheelEvent`, `KeyEvent` (`key`, `mod`, `scancode`, `unicode` for KEYDOWN), `TextInputEvent`,
   `JoyAxisEvent` / `JoyButtonEvent` / `JoyHatEvent` / `JoyDeviceEvent`, `ControllerAxisEvent` /
   `ControllerButtonEvent` / `ControllerDeviceEvent`, `WindowEvent`, `GameEvent` (custom types keep
   the base class).
2. **One map** `EVENT_CLASSES: dict[int, type[HashableEvent]]` used by the dispatch site
   (`EVENT_CLASSES.get(event_type, HashableEvent)(event_type, **fields)`); the subclasses pickle and
   hash exactly as the base (`__reduce__` uses `self.__class__`).
3. **Handler signatures** in the event interfaces and stubs (`events/input_event_interfaces.py`,
   `events/system_event_interfaces.py`) name the family:
   `def on_mouse_motion_event(self, event: MouseMotionEvent) -> None`. Game code is unchanged (still
   `event.pos`); it gains real types. The chord handlers become `keys: tuple[KeyEvent, ...]`.
4. **Serialization**: an explicit `to_json()` / `from_json()` on the base using the
   `tracing.JsonValue` alias, with the window reference mapped to None as recordings already do;
   a declared value vocabulary (`EventValue = int | float | str | bool | None | tuple[EventValue,
   ...]`) for the fields.
5. **Immutability (optional, separate step)**: hashable objects should not change. Replace the
   mutators with `with_fields(**changes) -> Self` once nothing mutates events (grep shows only
   tests do today); decide after steps 1-4.
6. `__getattr__ -> Any` stays on the base class only, for custom and unknown events; the per-file
   ANN401 ignore then covers just that line's reason.

## Steps

1. Subclasses + `EVENT_CLASSES` + the dispatch site; tests: each pygame event type maps to its
   class, round-trips through pickle and JSON, hashes and compares as before.
2. Interface/stub signatures; fix the chord signature; basedpyright over the package and tests
   (expect real errors to surface in handlers that misuse fields: fix each, report any that are
   bugs).
3. `to_json`/`from_json`; use them wherever events are serialized by hand today (find them first).
4. Immutability (decided: yes): replace the mutators with `with_fields`; update the tests that
   mutate events. Then cache the hash (the user, 2026-10-22: "cache it once it's safe"): computed
   on first `__hash__`, stored outside the event's fields (a slot or a name `__iter__`/`__eq__`/
   pickling never see; BUGS.md #179 was a stored hash leaking into the fields), never carried
   through pickling or `with_fields`. Test: an event's fields never include it; a pickled and a
   `with_fields` copy hash by their own content; measure `hash(event)` before/after.
5. Docs: CLAUDE.md Event System, `docs/`.

## Cost

Event construction picks a class from a dict: no measurable cost (one dict lookup per event).
Frozen pydantic models were considered (free validation and JSON) and rejected for dispatch: a few
microseconds per event, and mouse-motion bursts make that visible.
