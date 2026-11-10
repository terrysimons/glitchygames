# A controller-layer-only button binding (BUGS.md #178.26)

Part of the 2026-11-02 backlog run (the owner's explicit permission to plan, fix, commit, test
and push each item on its own branch).

## Design

**The problem.** `ActionMap.bind(controller_button=N)` binds button N on every layer the input
mode uses: the controller layer (CONTROLLERBUTTONDOWN/UP) in `controller` and `auto`, and the raw
joystick layer (JOYBUTTONDOWN/UP) in `joystick` and `auto`. That is right for the standard
buttons, whose controller-layer number is also a sensible raw index on most pads, but wrong for a
button whose raw index differs. Brave Adventurer's mic is 15 on the controller layer and 16 on the
raw layer (`MIC_BUTTON_CONTROLLER`, `MIC_BUTTON_JOYSTICK`), so `controller_button=15,
joystick_button=16` also binds **raw button 15** in `joystick` and `auto` mode: whatever a pad
reports there opens the mic.

**The fix.** A `controller_layer_button=` keyword, the counterpart of `joystick_button=` (which
binds the raw layer only, in every mode): it binds CONTROLLERBUTTONDOWN/UP only, in every input
mode. In `joystick` mode no controller-layer events are dispatched, so it never fires there, which
is what a button with its own raw index wants (its `joystick_button` covers that layer).

- `Binding` gains `controller_layer_only: bool = False`, set by the new keyword only.
- **Saving.** `to_dict` writes `"controller_layer_only": true` on that binding's
  `ControllerButtonDown` entry; `from_dict` binds an entry with the flag through
  `controller_layer_button`. A loader from before the change ignores the flag and binds the entry
  as a `controller_button` (today's behavior), so old engines still load new saves.
- **Brave Adventurer** binds the mic with `controller_layer_button=MIC_BUTTON_CONTROLLER,
  joystick_button=MIC_BUTTON_JOYSTICK`.

**Not in scope (hardware).** Whether 15/16 are right for every pad, #248 (a trigger read on the
raw layer rests at -1.0) and #184.5 (both managers on real pads, hot-plugging) need real pads:
they stay for the owner to check.

## Plan

1. `tests/input/test_action_map.py`: the new keyword binds the controller layer only in each mode
   (`joystick`, `controller`, `auto`), takes an instance filter, and round-trips through
   `to_dict`/`from_dict` (and an entry without the flag still loads as a `controller_button`).
2. `src/glitchygames/input/action_map.py`: the field, the keyword, its save flag and load path;
   update `joystick_button`'s docstring (it cites the mic).
3. Brave Adventurer: the mic binding; a test that raw button 15 is not the mic in `auto` and
   `joystick` mode while controller-layer 15 and raw 16 are.
4. Docs: `docs/games/brave_adventurer.md` (the mic), the input docs that list `bind`'s keywords.
5. BUGS.md #178.26 fixed; full suite, type checks; commit, push, PR.
