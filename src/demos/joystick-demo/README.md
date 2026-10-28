# Joystick Demo

The Joystick Demo lists every joystick and game controller the engine sees, live: a column per
device with its name, GUID and ids, the layer its events come from, and that layer's axes, held
buttons and hats, plus the last device change and input event. It is a member of the demos layer
(distribution `joystick-demo`, import package `joystick_demo`, under `src/demos/joystick-demo/`),
with its tests beside it. Demos get no browser build. From the repository root, `uv sync
--all-extras --all-groups --all-packages` installs it, `uv run joystick-demo` (or `uv run python -m
joystick_demo`) runs it, and `uv run pytest --no-cov src/demos/joystick-demo/tests` (`--no-cov`:
only the whole run meets the coverage gate) runs its tests (the engine's `uv run pytest` runs them
too).