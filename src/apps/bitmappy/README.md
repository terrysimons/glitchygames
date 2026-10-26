# Bitmappy

Bitmappy is GlitchyGames' pixel-art and animation editor (film strips, undo and redo, several
controllers at once, AI sprite generation), built on the GlitchyGames engine: the first member of
the apps layer (distribution `bitmappy`, import package `bitmappy`, under `src/apps/bitmappy/`),
with its tests beside it and its resources inside the package as package data
(`bitmappy/resources/`: the window icon, `bitmappy.cfg`, and the sprite library under
`bitmappy/resources/sprites/`, the AI training data, read through `bitmappy.SPRITE_CONFIG_DIR`).
From the repository root, `uv sync --all-extras --all-groups --all-packages` installs it,
`uv run bitmappy` starts it, and `uv run pytest --no-cov src/apps/bitmappy/tests` (`--no-cov`:
only the whole run meets the coverage gate) runs its tests (the engine's `uv run pytest` runs them
too). `nox -s build-binary` builds its desktop binary (`bitmappy.spec`), and
`nox -s browser -- bitmappy` builds and serves its browser version. The editor itself is
described in `docs/architecture/bitmappy.md`.
