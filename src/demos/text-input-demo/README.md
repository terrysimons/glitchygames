# Text Input Demo

The Text Input Demo shows one InputBox on a yellow background: a click or Tab gives it the keyboard,
typing edits its text, Return submits it, and Tab or Escape gives the keyboard back. It is a member
of the demos layer (distribution `text-input-demo`, import package `text_input_demo`, under
`src/demos/text-input-demo/`), with its tests beside it. Demos get no browser build. From the
repository root, `uv sync --all-extras --all-groups --all-packages` installs it, `uv run
text-input-demo` (or `uv run python -m text_input_demo`) runs it, and `uv run pytest --no-cov
src/demos/text-input-demo/tests` (`--no-cov`: only the whole run meets the coverage gate) runs its
tests (the engine's `uv run pytest` runs them too).