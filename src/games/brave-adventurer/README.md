# Brave Adventurer

Brave Adventurer is a Pitfall-style adventure in ancient Egypt built on the GlitchyGames engine,
in two editions: the classic one, drawn from pygame primitives, and the Papyrus Edition, drawn in
TOML pixel art. Both are one workspace member (distribution `brave-adventurer`, under
`src/games/brave-adventurer/`) in a src layout of import packages: `brave_adventurer_core` (what
both share), `brave_adventurer` (the classic edition), `brave_adventurer_papyrus` (the Papyrus
Edition) and `brave_adventurer_modes` (the launcher: a title screen offering both), with their
tests and golden replays (`tests/fixtures/replays/golden-classic.jsonl.gz`,
`tests/fixtures/replays/golden-papyrus.jsonl.gz`) beside them. From the repository root,
`uv sync --all-extras --all-groups --all-packages` installs it, `uv run brave-adventurer` plays it
(the title screen; `--game classic` or `--game papyrus` starts one at once), and
`uv run pytest src/games/brave-adventurer/tests`
runs its tests (the engine's `uv run pytest` runs them too, golden replays included). The games
are described in `docs/games/brave_adventurer.md`.
