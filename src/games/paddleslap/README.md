# PaddleSlap

PaddleSlap is a two-paddle ball game built on the GlitchyGames engine: a workspace member of its
own (distribution `paddleslap`, import package `paddleslap`, under `src/games/paddleslap/`), with
its tests and its golden replay (`tests/fixtures/replays/golden.jsonl.gz`) beside it and its
attract-mode demo inside the package (`paddleslap/demos/rally.jsonl.gz`, package data). From the
repository root, `uv sync --all-extras --all-groups --all-packages` installs it, `uv run
paddleslap` plays it, and `uv run pytest --no-cov src/games/paddleslap/tests` (`--no-cov`: only
the whole run meets the coverage gate) runs its tests (the engine's `uv run pytest` runs them too,
golden replay included, and tests/replay/test_bundled_demos.py replays the demo). Its golden trace
(`tests/world/golden/paddleslap.jsonl.gz`) stays with the engine's trace tests. The game itself is
described in `docs/games/paddleslap.md`.
