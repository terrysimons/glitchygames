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

## Shared frames

A sprite file's text compiles once per process and sprite class: every sprite of one class loaded
from the same text gets frames of its own that share the compile's surfaces and pixels, as
compiled sounds are shared (`compiled_sprites`, `ENGINE_SPRITE_CACHE`). The compile is the loader
run on the first such sprite, so a subclass that changes how a file loads loads as it always did.
Sixteen sprites of one file hold one copy of its frames, and the second load parses nothing, not
even for `SpriteFactory.load_sprite`'s content check, which the compile keeps. Each sprite keeps
its own playback and its own copies of everything else the load set, and an Arcade tile reuses
what another game compiled. The compile's load logs the file's warnings (a skipped transition,
say) once; the sprites loaded from it log none.

A frame's `image` and `pixels` copy the shared surface and pixels on their first read
(copy-on-write), so whatever a game or the editor then does with them, drawing into the surface
included, changes only that sprite. Engine code reads frames through `read_only_image` and
`read_only_pixels`, which never copy: a sprite that is only played keeps sharing. Assigning a
frame's `image`, `rect`, `hitbox` or `pixels` changes that sprite's frame only.

!!! warning "Never change `drawn_frame_surface()` in place"

    At scale 1 the surface a sprite draws is the compile's, shared by every sprite of that file.
    A game that changes its image in place (`set_alpha`, `fill`) copies it first, as
    Brave Adventurer Papyrus's fade does.

::: glitchygames.sprites.compiled_sprites
    options:
      heading_level: 2
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
        - surface_rgba_pixels
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
        - frame_tables_in_load_order

::: glitchygames.sprites.sprite
    options:
      heading_level: 2
      inherited_members: false
      show_submodules: false
