# GlitchyGames Animation System

The animation system for GlitchyGames: the TOML sprite format extended to multi-frame animations with per-animation and per-frame timing and playback control.

## Table of Contents

- [Overview](#overview)
- [File Format](#file-format)
- [Animation Features](#animation-features)
- [API Reference](#api-reference)
- [Examples](#examples)
- [Migration Guide](#migration-guide)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [Advanced Features](#advanced-features)

## Overview

The GlitchyGames Animation System lets you create animated sprites in `.toml` files. Static sprites keep their terse format, and one file can hold both simple 2-frame animations and several named animations.

### Key Features

- **Simplified static sprite definitions**: Minimal metadata needed for static sprites
- **Flexible Timing**: Per-animation `frame_interval` with per-frame overrides
- **Multiple Animations**: Single file can contain multiple named animations
- **Pythonic API**: Clean, intuitive Python interface
- **Automatic Type Detection**: `SpriteFactory` loads static and animated sprites alike, always as an `AnimatedSprite`
- **Unified Save/Load**: Single API for loading and saving both static and animated sprites
- **Format Support**: TOML only (YAML and INI support were removed); see LOADER_README.md for adding a format
- **Backwards Compatibility**: Existing BitmappySprite code continues to work

## File Format

### Static Sprite

```toml
[sprite]
name = "StaticSprite"
pixels = """
#@@@#
@AAA@
#@@@#
"""

[colors]
[colors."#"]  # Color definition for '#' character
red = 0
green = 0
blue = 0

[colors."@"]  # Color definition for '@' character
red = 255
green = 0
blue = 0
alpha = 127  # Optional - about half transparent (0-254; omit for opaque)

[colors."A"]  # Color definition for 'A' character
red = 255
green = 255
blue = 255
```

### Animated Sprite

Animations and their frames are TOML arrays of tables: each `[[animation]]` starts an animation, and every `[[animation.frame]]` after it (until the next `[[animation]]`) is one of its frames.

```toml
[sprite]
name = "AnimatedHero"

[[animation]]
namespace = "idle"
frame_interval = 0.5  # Optional, defaults to 0.5 seconds
loop = true  # Optional, defaults to true

[[animation.frame]]
namespace = "idle"  # Optional, written on save for readability
frame_index = 0  # Optional, written on save; the loader keeps file order
pixels = """
#@@@#
@AAA@
#@@@#
"""

[[animation.frame]]
namespace = "idle"
frame_index = 1
pixels = """
#@@@#
@.A.@
#@@@#
"""

[colors]
[colors."#"]  # Color definitions (required)
red = 0
green = 0
blue = 0

[colors."@"]
red = 255
green = 0
blue = 0

[colors."A"]
red = 255
green = 255
blue = 255

[colors."."]
red = 255
green = 0
blue = 255  # Magenta: the transparency key
```

### Section Definitions

#### `[sprite]` Section
- **`name`** (required): The sprite's display name (a static sprite's single animation is named after it)
- **`description`** (optional): Free text, kept on save
- **`pixels`** (static only): Required for static sprites, forbidden for animated sprites (a file with both is refused)
- **`frame_anchor`** (optional): How frames of different shapes line up when drawn (`FrameAnchor` values: `"none"` (default), `"top_left"`, `"top"`, `"top_right"`, `"left"`, `"center"`, `"right"`, `"bottom_left"`, `"bottom"`, `"bottom_right"`)
- **`[sprite.hitbox]`** (optional): Default hitbox in native pixels (`offset_x`, `offset_y`, `width`, `height`); without one, collision uses the visible pixels

#### `[[animation]]` Section
- **`namespace`** (required): Animation name (defaults to `"default"` if missing)
- **`frame_interval`** (optional): Seconds per frame for this animation (default: 0.5)
- **`loop`** (optional): Whether the animation loops (default: true)

#### `[[animation.frame]]` Section
- **`pixels`** (required): Frame pixel data using the character map (a frame without pixels is skipped)
- **`frame_interval`** (optional): Per-frame timing override in seconds
- **`namespace`** (optional): Written on save to match its animation; the loader ignores it (the frame belongs to the `[[animation]]` above it)
- **`frame_index`** (optional): Written on save as the frame's position; the loader ignores it (frames play in file order)
- **`[animation.frame.hitbox]`** (optional): Per-frame hitbox (`offset_x`, `offset_y`, `width`, `height`)

#### `[[transition]]` Section (optional)
- **`from`**, **`to`**, **`when`**: Animation state machine transitions (`src/glitchygames/animation/state_machine.py`); see `src/games/brave-adventurer/src/brave_adventurer_papyrus/sprites/cobra.toml`

### Animation-Frame Relationship

Frames belong to the `[[animation]]` table they follow (TOML nests each `[[animation.frame]]` in the most recent `[[animation]]`):

- **Animation tables** define the timing and behavior (`frame_interval`, `loop`) for a group of frames
- **Frame tables** contain the pixel data for individual frames and can override timing with a per-frame `frame_interval`
- **Multiple animations** can exist in the same file, each with its own `namespace`

The `namespace` on each frame is a readability aid: keep it equal to its animation's `namespace` (saves write it that way).

### Format Benefits

The TOML sprite format provides several key utilities that make it powerful for game development:

#### Human-Readable Design

The format is intentionally designed to be **easy to read by humans**. Single-frame sprites use the most terse format possible for maximum readability:

```toml
[sprite]
name = "SimpleSprite"
pixels = """
#@@@#
@AAA@
#@@@#
"""

[colors."#"]
red = 0
green = 0
blue = 0

[colors."@"]
red = 255
green = 0
blue = 0

[colors."A"]
red = 255
green = 255
blue = 255
```

This compact representation allows developers to quickly visualize and understand sprite artwork directly in the file, without needing specialized tools.

#### Unified Animation System

The system provides a unified approach to handling both static and animated sprites:

- **Single-frame sprites** are converted at load time into a single-frame animation named after `[sprite] name`
- When saved, a sprite with one animation of one frame is written back in the terse static format
- This unified approach means the same animation system handles both static and animated sprites seamlessly

#### AI-Assisted Generation

The text-based format enables powerful AI-assisted sprite generation workflows:

- **Easy to debug**: The text format makes it straightforward to inspect and verify AI-generated sprites
- **Style matching**: Developers can provide example art in the same format to help AI match existing sprite styles
- **Iterative refinement**: The readable format allows for quick manual adjustments and style nudges when working with AI-generated content

This combination of human readability, unified handling, and AI-friendly format makes the TOML sprite format a powerful tool for both manual sprite creation and automated generation workflows.

## Color Handling: Indexed, RGBA, and Mixed Modes

The GlitchyGames animation system supports three color modes: **indexed (RGB-only)**, **RGBA (per-pixel alpha)**, and **mixed mode** (combining both in the same sprite). The system automatically determines the color mode for each character based on the presence and value of the `alpha` field in its color definition.

### Character-to-Color Mapping

Each character in the `pixels` string maps to an RGB or RGBA tuple through the `[colors."<character>"]` sections. During loading, the system looks up each character in the pixel data and replaces it with the corresponding color tuple defined in the colors section.

**Example:**

```toml
[colors."#"]
red = 0
green = 0
blue = 0

[colors."@"]
red = 255
green = 0
blue = 0
alpha = 127

[[animation.frame]]
pixels = """
#@@@#
@.A.@
#@@@#
"""
```

In this example:

- The `#` character maps to `(0, 0, 0)` (black RGB)
- The `@` character maps to `(255, 0, 0, 127)` (red with semi-transparency RGBA)
- The `.` character maps to whatever is defined in `[colors."."]`
- The `A` character maps to whatever is defined in `[colors."A"]`

### Color Modes

#### Indexed Color (RGB-Only)

Indexed colors are opaque and use RGB tuples only:

- **No `alpha` field**: When a color definition has no `alpha` field, it's treated as an opaque indexed color
- **`alpha = 255`**: When `alpha` is explicitly set to 255, it's also treated as an opaque indexed color
- **Save behavior**: Indexed colors are written as RGB only (no `alpha` field) for clarity

**Example (Indexed):**

```toml
[colors."#"]
red = 0
green = 0
blue = 0

[colors."A"]
red = 255
green = 255
blue = 255
```

#### RGBA Color (Per-Pixel Alpha)

RGBA colors support transparency with per-pixel alpha values:

- **`alpha` 0-254**: When `alpha` is present with a value from 0-254, it represents semi-transparent or fully transparent pixels
  - `alpha = 0`: Fully transparent
  - `alpha = 1-254`: Semi-transparent (lower values = more transparent)
- **Save behavior**: RGBA colors with alpha 0-254 are written with the `alpha` field preserved

**Example (RGBA):**

```toml
[colors."~"]        # Semi-transparent red
red = 255
green = 0
blue = 0
alpha = 127

[colors."."]        # Fully transparent
red = 0
green = 0
blue = 0
alpha = 0
```

#### Mixed Mode

Sprites can combine indexed and RGBA colors in the same file:

- **Flexible composition**: Some characters can be indexed (opaque) while others use RGBA (transparent)
- **Preserved format**: The system preserves each character's original format and order
- **Save behavior**: During save, original per-pixel alpha values are preserved, and opaque colors are saved without the `alpha` field

**Example (Mixed):**

```toml
[colors."#"]        # Indexed (opaque)
red = 0
green = 0
blue = 0

[colors."@"]        # RGBA (semi-transparent)
red = 255
green = 0
blue = 0
alpha = 96

[colors."A"]        # Explicit opaque; treated like indexed
red = 255
green = 255
blue = 255
alpha = 255
```

### Special Block Character: Magenta Transparency (255, 0, 255)

The color `(255, 0, 255)` (magenta) is a special transparency color used throughout the GlitchyGames system. It serves as the transparency key color and has special handling:

#### Block Character Assignment

- **Preferred character**: The block character `█` is reserved and preferred for `(255, 0, 255)`
- **Original character preservation**: If a sprite file already uses a different character (like `.` or `M`) for `(255, 0, 255)`, that character is preserved on load
- **Automatic assignment**: If `(255, 0, 255)` is present but not mapped to a character, `█` is automatically assigned

#### Internal Format

- **RGBA in frames**: A frame that contains magenta stores its pixels as RGBA, with magenta as `(255, 0, 255, 255)`
- **Save behavior**: When saved, it's written as RGB only (no `alpha` field) since it's opaque
- **Transparency role**: Despite being opaque RGB internally, magenta serves as the transparency key color for sprite backgrounds and padding

**Example:**

```toml
[colors."█"]        # Block character for magenta (transparency key)
red = 255
green = 0
blue = 255

# Or using a different character:
[colors."."]
red = 255
green = 0
blue = 255
```

#### Loading Behavior

When loading sprites:

- Each glyph keeps the color its `[colors]` entry gives it, magenta included
- Magenta pixels are normalized to `(255, 0, 255, 255)` format internally
- The character mapping is preserved so the sprite can be saved with the same character

#### Saving Behavior

When saving sprites:

- If the sprite contains magenta pixels, the system:
  - Uses the original character from the loaded file if available
  - Otherwise assigns `█` to magenta
  - Writes the color definition as RGB only (no `alpha` field) since it's opaque
- The block character `█` is reserved/preferred but not forced if another character was originally used

### Load/Save Details

#### Loading Process

1. **Character lookup**: Each character in the `pixels` string is looked up in the `[colors."<character>"]` sections (unknown characters become magenta)
2. **Color tuple creation**: Based on the color definition:
   - No `alpha` field → RGB tuple `(r, g, b)`
   - `alpha` 0-254 → RGBA tuple `(r, g, b, a)`
   - `alpha` 255 → RGBA tuple `(r, g, b, 255)` (opaque; treated as indexed)
3. **Magenta normalization**: A frame with magenta or alpha below 255 stores its pixels as RGBA (magenta as `(255, 0, 255, 255)`); other frames store RGB
4. **Per-pixel alpha tracking**: Colors with `alpha` 0-254 are tracked for preservation during save
5. **Surface creation**: Each frame's image is drawn from its pixels:
   - A frame with translucent pixels (alpha 1-254) gets a per-pixel alpha (`SRCALPHA`) surface; its transparent pixels (magenta, alpha 0) get alpha 0
   - Any other frame gets a plain surface with magenta as its colorkey (it blits faster, and its keyed pixels are never written, whatever the destination's alpha)

#### Saving Process

1. **Color map building**: All unique colors from pixel data are collected
2. **Character assignment**: Characters are assigned to colors, preserving original mappings when possible
3. **Magenta handling**: If `(255, 0, 255)` is present:
   - Uses original character if available
   - Otherwise assigns `█`
4. **Alpha preservation**: Colors that originally had `alpha` 0-254 are preserved with their exact alpha values
5. **Format determination**: For each color:
   - **Original alpha 0-254**: Write RGB + `alpha` field with original value
   - **Opaque colors** (`alpha=255` or no `alpha`): Write RGB only (no `alpha` field)
   - **New RGBA colors**: Write RGB + `alpha` field if alpha < 255, otherwise RGB only
6. **Pixel string generation**: Each pixel tuple is converted back to its assigned character
7. **Layout**: Colors are written in the loaded file's order; frames get `namespace` and a sequential `frame_index`; a frame's `frame_interval` is written only when it differs from its animation's

Caveat: a single-frame sprite saved in the static format currently writes `alpha = 255` on its opaque colors (magenta included) when the sprite also has per-pixel alpha; the loader reads them back as the same opaque colors.

#### Transparency Rendering

In terminal/ASCII rendering tools (`src/glitchygames/tools/ascii_renderer.py`):

- **Fully transparent** (`alpha = 0`, or magenta): Uses a transparency placeholder glyph
- **Semi-transparent** (`alpha` 1-254): Color intensity is adjusted based on alpha value
- **Opaque colors**: Render normally

### Best Practices

1. **Prefer indexed colors**: Omit the `alpha` field unless transparency is needed
2. **Use magenta for transparency**: Use `(255, 0, 255)` (mapped to `█` or `.`) for transparent backgrounds
3. **Avoid `alpha = 255`**: Don't explicitly set `alpha = 255`; it's redundant and treated like indexed RGB
4. **Preserve character mappings**: The system preserves original character assignments, so your sprite files will maintain consistent character usage
5. **Mixed mode efficiency**: Use indexed colors for opaque pixels and RGBA only where transparency is needed; a frame without translucent pixels draws as a faster colorkey surface

## Animation Features

### 1. Per-Frame Timing

Control timing per animation and per frame:

```toml
[sprite]
name = "WalkingCharacter"

[[animation]]
namespace = "walk"
frame_interval = 0.3  # Animation default: 0.3 seconds per frame

[[animation.frame]]
namespace = "walk"
frame_index = 0
# No frame_interval: uses the animation's 0.3 seconds
pixels = """
#@@@#
@AAA@
#@@@#
"""

[[animation.frame]]
namespace = "walk"
frame_index = 1
frame_interval = 0.6  # Override: this frame takes 0.6 seconds
pixels = """
#@@@#
@.A.@
#@@@#
"""

[[animation.frame]]
namespace = "walk"
frame_index = 2
# No frame_interval: uses the animation's 0.3 seconds
pixels = """
#@@@#
@AAA@
#@@@#
"""
```

**Timing Rules:**
- Animation `frame_interval` = default for all its frames
- Per-frame `frame_interval` = override for that specific frame
- Missing per-frame `frame_interval` = use the animation's default
- No animation `frame_interval` specified = use 0.5s default

### 2. Frame Order

Frames play in the order they appear in the file. `frame_index` is written on save (0, 1, 2, ...) but the loader does not read it, so reordering frames means moving their tables.

### 3. Multiple Animations

Single file can contain multiple animations:

```toml
[sprite]
name = "Hero"

[[animation]]
namespace = "idle"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "idle"
pixels = """
#@@@#
@AAA@
#@@@#
"""

[[animation.frame]]
namespace = "idle"
pixels = """
#@@@#
@.A.@
#@@@#
"""

[[animation]]
namespace = "walk"
frame_interval = 0.3
loop = true

[[animation.frame]]
namespace = "walk"
pixels = """
#@@@#
@AAA@
#@@@#
"""

[[animation.frame]]
namespace = "walk"
pixels = """
#@@@#
@.A.@
#@@@#
"""

[[animation]]
namespace = "death"
frame_interval = 0.4
loop = false

[[animation.frame]]
namespace = "death"
pixels = """
#XXX#
XXXX#
#XXX#
"""

[[animation.frame]]
namespace = "death"
pixels = """
.....
.....
.....
"""

[colors]
[colors."#"]
red = 0
green = 0
blue = 0

[colors."@"]
red = 255
green = 0
blue = 0

[colors."A"]
red = 255
green = 255
blue = 255

[colors."X"]
red = 128
green = 128
blue = 128
alpha = 127  # half transparent

[colors."."]
red = 255
green = 0
blue = 255
```

The first animation in the file is the current one after loading.

### 4. Mixed Loop Behavior

Different animations can have different loop settings:

```toml
[[animation]]
namespace = "idle"
loop = true  # Loops forever

[[animation]]
namespace = "death"
loop = false  # Plays once

[[animation]]
namespace = "explosion"
loop = false  # One-time effect
```

Switching to an animation (`set_animation` or `play`) applies its `loop` flag to `is_looping`.

## API Reference

### Loading Sprites

`SpriteFactory` (`src/glitchygames/sprites/factory.py`) loads both static and animated sprites. It always returns an `AnimatedSprite`; a static sprite becomes one animation of one frame:

```python
from glitchygames.sprites import SpriteFactory

# Load any sprite file (automatic type detection)
sprite = SpriteFactory.load_sprite(filename="hero.toml")  # Could be static or animated
sprite = SpriteFactory.load_sprite(filename="static.toml")  # Static sprite
sprite = SpriteFactory.load_sprite(filename="animated.toml")  # Animated sprite

# Load default sprite (src/glitchygames/assets/raspberry.toml) when no filename provided
default_sprite = SpriteFactory.load_sprite()  # Loads default sprite
default_sprite = SpriteFactory.load_sprite(filename=None)  # Same as above
```

`load_sprite` takes keyword arguments only.

### Saving Sprites

```python
from glitchygames.sprites import SpriteFactory

# Save any sprite (automatic type detection)
SpriteFactory.save_sprite(sprite=sprite, filename="output.toml", file_format="toml")

# Save with default format (TOML)
SpriteFactory.save_sprite(sprite=sprite, filename="output.toml")

# Or directly
sprite.save("output.toml")
```

TOML is the only format; any other `file_format` raises `ValueError`.

### Backwards Compatibility

Existing BitmappySprite code continues to work:

```python
from glitchygames.sprites import BitmappySprite

# Load static sprite (uses the factory internally); filename is keyword-only
sprite = BitmappySprite(x=0, y=0, width=32, height=32, filename="static.toml")

# Save static sprite (uses the factory internally)
sprite.save("output.toml", "toml")
```

### Loading Animated Sprites

```python
from glitchygames.sprites import AnimatedSprite

# Load animated sprite (TOML only)
sprite = AnimatedSprite("hero.toml")
```

### Default Sprite Loading

When no filename is provided, `SpriteFactory` loads the default raspberry sprite:

```python
# Load default sprite (raspberry.toml)
default_sprite = SpriteFactory.load_sprite()

# The default sprite has these properties:
print(default_sprite.name)  # "Tiley McTile Face"
print(default_sprite.image.get_size())  # (16, 16)
```

### Error Handling

```python
try:
    # Mixed content (both [sprite] pixels and [[animation]] sections), or no sprite content
    sprite = SpriteFactory.load_sprite(filename="mixed.toml")
except ValueError as e:
    print(f"Invalid sprite file: {e}")
    # Output: "Invalid sprite file: Invalid sprite file"
```

A file that is not `.toml` raises `ValueError` (`Unsupported format: ...`), and a missing file raises `FileNotFoundError`.

### State Properties (Read-Only)

```python
# Current animation and frame
sprite.current_animation  # "idle"
sprite.current_frame      # 0

# Playback state
sprite.is_playing         # False until play() is called
sprite.is_looping         # The current animation's loop flag (also settable)
```

### Frame Access

```python
# Frames per animation: a dict of animation name to a list of SpriteFrame
sprite.frames["idle"][0]  # Get idle frame 0
sprite.frames["walk"][1]  # Get walk frame 1
sprite.get_frame("walk", 1)  # Same, raising ValueError/IndexError when missing

# Iterate through an animation's frames
for frame in sprite.frames["idle"]:
    print(frame.duration, frame.get_size())
```

`sprite.animations` returns the same dict as `sprite.frames` (a copy).

### Animation Information

```python
# Current animation
sprite.frame_interval  # The current frame's duration in seconds
sprite.loop            # Whether the current animation loops
sprite.frame_count     # The number of frames in the current animation
sprite.animation_names # Animation names
sprite.animation_order # Animation names in file order

# Specific animation by name
sprite.get_animation_metadata("idle")
# {'frame_count': 2, 'total_duration': 1.0, 'is_looping': True}
```

### Control Methods

```python
# Switch animations (resets the frame to 0 and applies the animation's loop flag)
sprite.set_animation("walk")

# Jump to a specific frame of the current animation
sprite.set_frame(1)

# The animation after the current one, in order (read-only)
sprite.next_animation  # "walk" when the current one is "idle"
```

### Playback Control Methods

```python
# Start playing specific animation
sprite.play("idle")
sprite.play_animation("idle")  # Alias of play()

# Resume current animation
sprite.play()

# Pause (preserves position)
sprite.pause()

# Stop and reset to frame 0
sprite.stop()

# Advance timing; call each frame with the elapsed seconds
sprite.update(dt)
```

A non-looping animation stops on its last frame.

## Examples

### Practical Usage Examples

#### Loading and Saving Sprites

```python
from glitchygames.sprites import SpriteFactory

# Load any sprite file (always an AnimatedSprite)
sprite = SpriteFactory.load_sprite(filename="hero.toml")

if sprite.is_static_sprite():
    print(f"Static sprite: {sprite.name}")
else:
    print(f"Available animations: {sprite.animation_names}")

# Save the sprite
SpriteFactory.save_sprite(sprite=sprite, filename="output.toml")
```

#### Working with Static Sprites

```python
import pygame

from glitchygames.sprites import BitmappySprite, SpriteFactory

# Create a static sprite programmatically
sprite = BitmappySprite(x=0, y=0, width=16, height=16, name="MySprite")
sprite.image = pygame.Surface((16, 16))
sprite.image.fill((255, 0, 0))  # Red
sprite.rect = sprite.image.get_rect()
sprite.pixels = [(255, 0, 0)] * 256  # 16x16 red pixels
sprite.pixels_across = 16
sprite.pixels_tall = 16

# Save it
sprite.save("my_sprite.toml", "toml")

# Load it back
loaded_sprite = SpriteFactory.load_sprite(filename="my_sprite.toml")
print(f"Loaded sprite: {loaded_sprite.name}")
```

#### Working with Animated Sprites

```python
from glitchygames.sprites import SpriteFactory

# Load animated sprite
sprite = SpriteFactory.load_sprite(filename="hero.toml")

# Control animation
sprite.play("idle")
print(f"Current animation: {sprite.current_animation}")
print(f"Current frame: {sprite.current_frame}")

# Switch animations
sprite.play("walk")

# Access frames
for frame in sprite.frames["idle"]:
    print(f"Frame lasts {frame.duration}s")
```

### Static Sprite Examples

#### Sparse Static Sprite (Minimal)
```toml
[sprite]
name = "SimpleSprite"
pixels = """
#@@@#
@AAA@
#@@@#
"""

[colors]
[colors."#"]
red = 0
green = 0
blue = 0

[colors."@"]
red = 255
green = 0
blue = 0

[colors."A"]
red = 255
green = 255
blue = 255
```

#### Verbose Static Sprite (Explicit)
```toml
[sprite]
name = "ComplexSprite"
description = "A sprite with a hitbox and translucent colors"
pixels = """
#@@@#
@AAA@
#@@@#
"""

[sprite.hitbox]
offset_x = 0
offset_y = 0
width = 5
height = 3

[colors]
[colors."#"]  # Color definition for '#' character
red = 0
green = 0
blue = 0
alpha = 127  # half transparent

[colors."@"]  # Color definition for '@' character
red = 255
green = 0
blue = 0
alpha = 127  # half transparent

[colors."A"]  # Color definition for 'A' character
red = 255
green = 255
blue = 255
alpha = 127  # half transparent
```

### Animated Sprite Examples

#### Sparse Configuration (Minimal)

```toml
[sprite]
name = "SimpleHero"

[[animation]]
namespace = "idle"

[[animation.frame]]
pixels = """
#@@@#
@AAA@
#@@@#
"""

[[animation.frame]]
pixels = """
#@@@#
@.A.@
#@@@#
"""

[colors]
[colors."#"]
red = 0
green = 0
blue = 0

[colors."@"]
red = 255
green = 0
blue = 0

[colors."A"]
red = 255
green = 255
blue = 255

[colors."."]
red = 255
green = 0
blue = 255
```

### Verbose Configuration (Explicit)

```toml
[sprite]
name = "ComplexHero"

[[animation]]
namespace = "idle"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = """
#@@@#
@AAA@
#@@@#
"""

[[animation.frame]]
namespace = "idle"
frame_index = 1
pixels = """
#@@@#
@.A.@
#@@@#
"""

[[animation]]
namespace = "walk"
frame_interval = 0.3
loop = true

[[animation.frame]]
namespace = "walk"
frame_index = 0
pixels = """
#@@@#
@AAA@
#@@@#
"""

[[animation.frame]]
namespace = "walk"
frame_index = 1
frame_interval = 0.2
pixels = """
#@@@#
@.A.@
#@@@#
"""

[colors]
[colors."."]
red = 255
green = 0
blue = 255

[colors."#"]
red = 0
green = 0
blue = 0
alpha = 127  # half transparent

[colors."@"]
red = 255
green = 0
blue = 0
alpha = 127  # half transparent

[colors."A"]
red = 255
green = 255
blue = 255
alpha = 127  # half transparent
```

### One-Shot Animation

```toml
[sprite]
name = "Explosion"

[[animation]]
namespace = "explosion"
frame_interval = 0.1
loop = false

[[animation.frame]]
namespace = "explosion"
pixels = """
.....
.#@#.
.....
"""

[[animation.frame]]
namespace = "explosion"
frame_interval = 0.2  # Hold the biggest frame longer
pixels = """
#@@@#
@@@@#
#@@@#
"""

[[animation.frame]]
namespace = "explosion"
pixels = """
.....
.....
.....
"""

[colors]
[colors."."]
red = 255
green = 0
blue = 255

[colors."#"]
red = 0
green = 0
blue = 0

[colors."@"]
red = 255
green = 0
blue = 0
```

## Migration Guide

### From Static Sprites

**Static:**
```toml
[sprite]
name = "StaticHero"
pixels = """
#@@@#
@AAA@
#@@@#
"""

[colors]
[colors."#"]
red = 0
green = 0
blue = 0

[colors."@"]
red = 255
green = 0
blue = 0

[colors."A"]
red = 255
green = 255
blue = 255
```

**Animated:**
```toml
[sprite]
name = "AnimatedHero"

[[animation]]
namespace = "idle"
loop = true

[[animation.frame]]
namespace = "idle"
pixels = """
#@@@#
@AAA@
#@@@#
"""

[colors]
[colors."#"]
red = 0
green = 0
blue = 0

[colors."@"]
red = 255
green = 0
blue = 0

[colors."A"]
red = 255
green = 255
blue = 255
```

Note that an animated file with one animation of one frame is saved back in the static format.

### Code Changes

**Before:**
```python
sprite = BitmappySprite(filename="hero.toml")
```

**After:**
```python
sprite = AnimatedSprite("hero.toml")
sprite.play("idle")
```

## Best Practices

### 1. Animation Design

- **Keep animations short**: 2-4 frames for most cases
- **Use consistent timing**: Stick to the animation's `frame_interval` when possible
- **Plan your namespaces**: Choose clear, descriptive animation namespace names. These names aid in debugging and code clarity.

### 2. File Organization

- **One sprite per file**: Keep related animations together
- **Use sparse configuration**: Only specify what you need
- **Group related animations**: idle, walk, jump in same file

### 3. Performance

- **Reuse color definitions**: Define colors once per file
- **Optimize frame count**: More frames = more memory usage
- **Avoid translucent pixels you don't need**: frames without alpha 1-254 draw as faster colorkey surfaces

### 4. Code Usage

```python
# Good: Check animation state
if sprite.current_animation == "idle" and sprite.current_frame == 0:
    ...  # Handle idle state

# Good: Use properties for state
if sprite.is_playing and not sprite.is_looping:
    ...  # Handle one-time animation

# Good: Access the current frame
current_frame = sprite.get_current_frame()
```

### 5. Factory Pattern Usage

**Use SpriteFactory for new code:**
```python
# Recommended: Use SpriteFactory for automatic type detection
sprite = SpriteFactory.load_sprite(filename="hero.toml")
SpriteFactory.save_sprite(sprite=sprite, filename="output.toml", file_format="toml")
```

**Maintain backwards compatibility:**
```python
# Existing code continues to work
sprite = BitmappySprite(x=0, y=0, width=32, height=32, filename="static.toml")
sprite.save("output.toml", "toml")
```

**Handle different sprite types:**
```python
sprite = SpriteFactory.load_sprite(filename="unknown.toml")

if sprite.is_static_sprite():
    print(f"Static sprite: {sprite.name}")
else:
    sprite.play("idle")
```

## Troubleshooting

### Common Issues

**Error: `ValueError: Invalid sprite file`**
- The file has both `[sprite] pixels` and `[[animation]]` sections (remove `pixels` from `[sprite]` when using animations), or neither

**Unknown characters draw as magenta (transparent)**
- Every character in `pixels` needs a color definition:
```toml
[colors."X"]
red = 255
green = 0
blue = 0
```

**Error: `Cannot declare ('animation', 'frame') twice` (or similar TOML parse error)**
- Use `[[animation]]` and `[[animation.frame]]` (arrays of tables), not `[animation]` / `[animation.frame]`

**Animation not playing**
- Call `sprite.play("animation_name")` to start (loading does not start playback)
- Call `sprite.update(dt)` every frame
- Ensure `loop` is set correctly (a non-looping animation stops on its last frame)
- Check the animation's `frame_interval`
- Check for per-frame `frame_interval` overrides that might be too fast/slow

**Frames in wrong order**
- Frames play in file order; move the `[[animation.frame]]` tables (`frame_index` is not read)

### Validation Checklist

- [ ] Animations use `[[animation]]` and frames `[[animation.frame]]`, each frame after its animation
- [ ] Each `[[animation]]` has a `namespace`
- [ ] All characters in `pixels` have color definitions
- [ ] No `pixels` in `[sprite]` section when using animations
- [ ] Frame `namespace` values (if specified) match their animation's

## Advanced Features

### Adding Formats

TOML is the only supported format. `SpriteFactory`, `AnimatedSprite.load`/`save` and `BitmappySprite` each check the format and refuse others with `ValueError`; LOADER_README.md describes how to add one.

### Complex Timing

Mix the animation's timing and per-frame timing for realistic motion:

```toml
[[animation]]
namespace = "walk"
frame_interval = 0.3

[[animation.frame]]
namespace = "walk"
frame_index = 0
frame_interval = 0.5  # Foot contact - hold longer
pixels = """
#@@@#
@AAA@
#@@@#
"""

[[animation.frame]]
namespace = "walk"
frame_index = 1
# Uses the animation's default 0.3s - quick transition
pixels = """
#@@@#
@.A.@
#@@@#
"""

[[animation.frame]]
namespace = "walk"
frame_index = 2
frame_interval = 0.5  # Other foot contact - hold longer
pixels = """
#@@@#
@AAA@
#@@@#
"""
```

### Animation State Machine

`[[transition]]` tables declare animation changes that the state machine (`src/glitchygames/animation/state_machine.py`) evaluates; a sprite loaded with them gets `sprite.state_machine`:

```toml
[[transition]]
from = "idle"
to = "strike"
when = "timer > 2.0"
```

Transitions are kept verbatim and written back on save.

This animation system provides flexible animation capabilities while keeping the simplicity and familiarity of the GlitchyGames sprite format.
