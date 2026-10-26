# Mr. Muncher

Mr. Muncher is a maze chase at the movies built on the GlitchyGames engine: a workspace member of
its own (distribution `mr-muncher`, import package `mr_muncher`, under `src/games/mr-muncher/`),
with its tests and its golden replay (`tests/fixtures/replays/golden.jsonl.gz`) beside it. From
the repository root, `uv sync --all-extras --all-groups --all-packages` installs it, `uv run
mr-muncher` plays it, and `uv run pytest --no-cov src/games/mr-muncher/tests` (`--no-cov`: only
the whole run meets the coverage gate) runs its tests (the engine's `uv run pytest` runs them too,
golden replay included). The game itself is described in `docs/games/mr_muncher.md`.
