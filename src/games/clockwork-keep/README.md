# Clockwork Keep

Clockwork Keep is a steampunk tower climb built on the GlitchyGames engine: a workspace member
of its own (distribution `clockwork-keep`, import package `clockwork_keep`, under
`src/games/clockwork-keep/`), with its tests and its golden replay
(`tests/fixtures/replays/golden.jsonl.gz`) beside it. From the repository root, `uv sync
--all-extras --all-groups --all-packages` installs it, `uv run clockwork-keep` plays it, and `uv
run pytest src/games/clockwork-keep/tests` runs its tests (the engine's `uv run pytest` runs them
too, golden replay included). Its golden trace (`tests/world/golden/clockwork_keep.jsonl.gz`)
stays with the engine's trace tests. The game itself is described in
`docs/games/clockwork_keep.md`.
