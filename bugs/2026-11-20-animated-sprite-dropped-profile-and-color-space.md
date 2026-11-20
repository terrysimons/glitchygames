# AnimatedSprite Dropped `[sprite] profile` and `color_space` on Load Then Save

- **Description**: A sprite file with `profile` or `color_space` in `[sprite]` loaded (the schema and `sprite_toml` accept both) but `AnimatedSprite.to_text()` wrote neither back. Bitmappy saves through `to_text`, so one save stripped them (found by a planning agent, 2026-11-20).
- **Status**: Fixed (2026-11-20, branch `fix/bug-sweep-2026-11-20`)
- **Priority**: Low (nothing writes the keys yet; part 2 of plans/2026-11-17-sprite-color-profiles.md would have lost data)
- **Root Cause**: `sprite_toml.py` declared the keys (`SPRITE_KEYS`, `SPRITE_LINE_STRING_KEYS`) and the schema allowed them, but `AnimatedSprite` had no attribute for them: `_load_text_uncached` never read them and `_static_document` / `_build_toml_data_structure` never wrote them. `CompiledSprite`, `SHARED_SPRITE_FIELDS` and `copy_sprite_metadata_from` did not carry them either.
- **Test gap**: The round-trip tests covered `sprite_toml` (document in, text out), never a sprite loaded and saved through `AnimatedSprite`.
- **Solution**: `AnimatedSprite.profile` and `.color_space` (`str | None`, absent stays absent, no default), read on load, written in both layouts, copied by `copy_sprite_metadata_from`, carried by `CompiledSprite` and `SHARED_SPRITE_FIELDS` (the cache conservation test compares them). Values are not validated: that is part 2.
- **Tests**: `tests/sprites/test_animated_sprite.py::TestColorProfileKeysRoundTrip` (static and animated layouts, absent keys, metadata copy). Three of its four cases failed before the fix (`KeyError: 'profile'`, `AttributeError`).
- **Sweep**: other `[sprite]` keys (`name`, `description`, `tags`, `frame_anchor`, `hitbox`) already round-trip. Not covered: a sprite class other than `AnimatedSprite` that writes sprite text.
- **Reporter**: A planning agent
- **Date Reported**: 2026-11-20
- **Files**: `src/glitchygames/sprites/animated.py`, `src/glitchygames/sprites/compiled_sprites.py`, `tests/sprites/test_animated_sprite.py`, `tests/sprites/test_compiled_sprites.py`
