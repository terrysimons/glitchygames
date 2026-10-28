# Delta Time Demo

The Delta Time Demo shows frame-rate-independent movement on the GlitchyGames engine: Space starts
a white square crossing the screen at 300 pixels per second, and the time it took is shown once it
has left. It is the first member of the demos layer (distribution `dt-demo`, import package
`dt_demo`, under `src/demos/dt-demo/`), with its tests beside it. Demos get no browser build. From
the repository root, `uv sync --all-extras --all-groups --all-packages` installs it, `uv run
dt-demo` (or `uv run python -m dt_demo`) runs it, and `uv run pytest --no-cov
src/demos/dt-demo/tests` (`--no-cov`: only the whole run meets the coverage gate) runs its tests
(the engine's `uv run pytest` runs them too).
