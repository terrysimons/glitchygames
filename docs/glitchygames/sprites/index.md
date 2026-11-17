::: glitchygames.sprites
    options:
      heading_level: 2
      inherited_members: false
      show_submodules: false
      members: false

::: glitchygames.sprites.animated
    options:
      heading_level: 2
      inherited_members: false
      show_submodules: false

::: glitchygames.sprites.animated_interface
    options:
      heading_level: 2
      inherited_members: false
      show_submodules: false

::: glitchygames.sprites.bitmappy_sprite
    options:
      heading_level: 2
      inherited_members: false
      show_submodules: false

::: glitchygames.sprites.constants
    options:
      heading_level: 2
      inherited_members: false
      show_submodules: false

::: glitchygames.sprites.factory
    options:
      heading_level: 2
      inherited_members: false
      show_submodules: false

::: glitchygames.sprites.frame
    options:
      heading_level: 2
      inherited_members: false
      show_submodules: false

::: glitchygames.sprites.pixel_utils
    options:
      heading_level: 2
      inherited_members: false
      show_submodules: false

::: glitchygames.sprites.root_sprite
    options:
      heading_level: 2
      inherited_members: false
      show_submodules: false

## Sprites as text

A sprite file is TOML text, and these modules read and write that text in memory, with no
temporary file. `SpriteFactory.load_sprite_from_text` (in `factory`) loads text as
`SpriteFactory.load_sprite` loads a file, refusing text that is neither a static nor an animated
sprite; `AnimatedSprite.to_text` (in `animated`) is the method form of `sprite_to_text`, and the
text `AnimatedSprite.save` writes to its file.

!!! note "`sprite_toml` is pygame-free on purpose"

    `sprite_toml` imports only the standard library, so a tool that cannot import pygame (a
    server, a command-line converter) can parse and write sprite files. It deals in data;
    `sprite_text` turns that data into the `AnimatedSprite` the engine draws.

!!! warning "Opaque magenta cannot be kept"

    A sprite file's transparency key is magenta (255, 0, 255). `sprite_text_from_frames` writes
    every fully transparent pixel (alpha 0), whatever its RGB, as the key. An image pixel that is
    opaque magenta is written as the key too, so it loads and draws as transparent: the format
    cannot tell the two apart. That color is lost, not changed to another. Partial alpha and every
    other color are kept exactly, up to the glyph limit (`SpriteColorLimitError`); the key takes
    no glyph of that limit.

::: glitchygames.sprites.sprite_text
    options:
      heading_level: 3
      inherited_members: false
      show_submodules: false
      members:
        - sprite_from_text
        - sprite_to_text
        - sprite_text_from_frames
        - SpriteColorLimitError

::: glitchygames.sprites.sprite_toml
    options:
      heading_level: 3
      inherited_members: false
      show_submodules: false
      members:
        - parse_sprite_toml
        - write_sprite_toml
        - split_sprite_text

::: glitchygames.sprites.sprite
    options:
      heading_level: 2
      inherited_members: false
      show_submodules: false
