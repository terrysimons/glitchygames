# Sound Board Demo

The Sound Board Demo is the hands-on way to hear the sound engine's built-in waves and noises and to
compare notes, hertz and scale steps. It shows one row for each built-in wave (sine, triangle, saw,
square, pulse 12.5 %, 25 % and 75 %) and noise (white, 15-bit LFSR, 7-bit LFSR), each with the eight
notes of C major. It is a member of the demos layer (distribution `sound-board-demo`, import
package `sound_board_demo`, under `src/demos/sound-board-demo/`), with its tests beside it. Demos
get no browser build.

| Key | Does |
| --- | --- |
| `1`-`8` | play the current row's notes |
| Up / Down | pick the row (the current row is lit) |
| `L` | cycle the labels: note names, hertz, scale steps (only the labels change) |
| `C` | play a C major chord on the current row |
| Esc | quit |

The Audio debug panel is on by default (the demo adds `--sound-diagnostics` unless you pass flags
of your own). Every sound is requested in `setup()`, so the panel's compile log shows only setup
compiles: playing a key never compiles anything.

From the repository root, `uv sync --all-extras --all-groups --all-packages` installs it, `uv run
sound-board-demo` (or `uv run python -m sound_board_demo`) runs it, and `uv run pytest --no-cov
src/demos/sound-board-demo/tests` (`--no-cov`: only the whole run meets the coverage gate) runs its
tests (the engine's `uv run pytest` runs them too).
