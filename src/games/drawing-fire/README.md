# Drawing Fire

Drawing Fire is a stick-figure battle drawn in pencil on paper, built on the GlitchyGames engine:
a workspace member of its own (distribution `drawing-fire`, import package `drawing_fire`, under
`src/games/drawing-fire/`), with its tests and its golden replay
(`tests/fixtures/replays/golden.jsonl.gz`) beside it and its soldier sprite inside the package
(`drawing_fire/sprites/soldier.toml`, package data). From the repository root, `uv sync
--all-extras --all-groups --all-packages` installs it, `uv run drawing-fire` plays it, and `uv run
pytest --no-cov src/games/drawing-fire/tests` (`--no-cov`: only the whole run meets the coverage
gate) runs its tests (the engine's `uv run pytest` runs them too, golden replay included). `uv run
python -m scripts.simulate_drawing_fire` plays headless battles. The game itself is described in
`docs/games/drawing_fire.md`.
