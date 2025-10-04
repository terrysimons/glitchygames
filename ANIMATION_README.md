# GlitchyGames Animation System

A comprehensive animation system for GlitchyGames that extends the existing BitmappySprite format to support multi-frame animations with flexible timing and playback control.

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

The GlitchyGames Animation System allows you to create animated sprites using the modern `.toml` file format. It extends the existing BitmappySprite format with minimal disruption, supporting both simple 2-frame animations and complex multi-animation sprites.

### Key Features

- **Simplified static sprite definitions**: Minimal metadata needed for static sprites
- **Flexible Timing**: Global animation namespace and per-frame timing control
- **Multiple Animations**: Single file can contain multiple named animations
- **Pythonic API**: Clean, intuitive Python interface
- **Frame Interpolation**: Support for key-frame animation with auto-generation, optimized for common retro game formats (2-4 frame walk cycles, idle animations)
- **Automatic Type Detection**: GGSpriteLoader automatically detects static vs animated sprites
- **Unified Save/Load**: Single API for loading and saving both static and animated sprites
- **Format Support**: Both TOML and YAML formats supported for maximum flexibility
- **Extensible Architecture**: GGSpriteLoader designed to support future sprite and sprite sheet formats
- **Backwards Compatibility**: Existing BitmappySprite code continues to work unchanged

## File Format

### Static Sprite

```toml
[sprite]
name = "StaticSprite"
pixels = """
#@@@#  # Single frame pixel data
@AAA@
#@@@#
"""

[colors]
[colors."#"]  # Color definition for '#' character
red = 0
green = 0
blue = 0
alpha = 0.5  # Optional - half transparency

[colors."@"]  # Color definition for '@' character
red = 255
green = 0
blue = 0
alpha = 0.5  # Optional - half transparency

[colors."A"]  # Color definition for 'A' character
red = 255
green = 255
blue = 255
alpha = 0.5  # Optional - half transparency
```

### Animated Sprite

```toml
[sprite]
name = "AnimatedHero"

[animation]
namespace = "idle"
frame_interval = 0.5  # Optional, defaults to 0.5 seconds
loop = true  # Optional, defaults to true

[animation.frame]
namespace = "idle"
frame_index = 0  # Optional, auto-generated if missing
pixels = """
#@@@#
@AAA@
#@@@#
"""

[animation.frame]
namespace = "idle"
frame_index = 1  # Optional, auto-generated if missing
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
alpha = 0.5  # Optional - half transparency

[colors."@"]
red = 255
green = 0
blue = 0
alpha = 0.5  # Optional - half transparency

[colors."A"]
red = 255
green = 255
blue = 255
alpha = 0.5  # Optional - half transparency
```

### Section Definitions

#### `[sprite]` Section
- **`name`** (required): The sprite's display name
- **`pixels`** (static only): Required for static sprites, forbidden for animated sprites (backwards compatibility/simplicity)

#### `[animation]` Section
- **`namespace`** (required): Animation identifier (must match the corresponding frame namespaces)
- **`frame_interval`** (optional): Global animation namespace time interval between frames in seconds (default: 0.5)
- **`loop`** (optional): Whether animation loops (default: true)

#### `[animation.frame]` Section
- **`namespace`** (required): Must match its corresponding animation namespace
- **`frame_index`** (optional): Frame position in animation (auto-generated if missing)
- **`pixels`** (required): Frame pixel data using character map
- **`frame_interval`** (optional): Per-frame timing override in seconds (overrides animation namespace default for this frame)

### Animation-Frame Relationship

The `namespace` field creates a binding between `[animation]` and `[animation.frame]` sections. This relationship is necessary because:

- **Animation sections** define the timing and behavior (`frame_interval`, `loop`) for a group of frames
- **Frame sections** contain the actual pixel data for individual frames and can override animation timing with per-frame `frame_interval` values
- **Namespace matching** ensures frames are grouped under the correct animation
- **Multiple animations** can exist in the same file, each with their own namespace

For example, frames with `namespace = "idle"` belong to the animation with `namespace = "idle"`, while frames with `namespace = "walk"` belong to a separate animation with `namespace = "walk"`.

## Animation Features

### 1. Per-Frame Timing

Control timing at the animation namespace global and per-frame levels:

```toml
[sprite]
name = "WalkingCharacter"

[animation]
namespace = "walk"
frame_interval = 0.3  # Animation namespace default: 0.3 seconds per frame

[animation.frame]
namespace = "walk"
frame_index = 0
# No frame_interval: uses global 0.3 seconds
pixels = """
#@@@#
@AAA@
#@@@#
"""

[animation.frame]
namespace = "walk"
frame_index = 1
frame_interval = 0.6  # Override: this frame takes 0.6 seconds
pixels = """
#@@@#
@.A.@
#@@@#
"""

[animation.frame]
namespace = "walk"
frame_index = 2
# No frame_interval: uses global 0.3 seconds
pixels = """
#@@@#
@AAA@
#@@@#
"""
```

**Timing Rules:**
- Global `frame_interval` = default for all frames
- Per-frame `frame_interval` = override for that specific frame
- Missing per-frame `frame_interval` = use animation namespace default
- No animation namespace `frame_interval` specified = use 0.5s default

### 2. Frame Order and Auto-Generation

Frames can be ordered explicitly or auto-generated:

```toml
[animation]
namespace = "complex"
frame_interval = 0.2

[animation.frame]
namespace = "complex"
frame_index = 0  # Explicit: key frame
pixels = """
#@@@#
@AAA@
#@@@#
"""

[animation.frame]
namespace = "complex"
# No frame_index: auto-generated as 1
pixels = """
#@@@#
@.A.@
#@@@#
"""

[animation.frame]
namespace = "complex"
frame_index = 5  # Explicit: another key frame
pixels = """
#@@@#
@AAA@
#@@@#
"""

[animation.frame]
namespace = "complex"
# No frame_index: auto-generated as 6
pixels = """
#@@@#
@.A.@
#@@@#
"""
```

**Auto-Generation Rules:**
- Missing `frame_index` values are filled in sequence
- Starts from 0, skips existing explicit indices
- Enables frame interpolation between key frames
- Interpolated frames are generated automatically and marked with `interpolated = True`
- Original frames from the sprite file have `interpolated = False`

### 3. Multiple Animations

Single file can contain multiple animations:

```toml
[sprite]
name = "Hero"

[animation]
namespace = "idle"
frame_interval = 0.5
loop = true

[animation.frame]
namespace = "idle"
pixels = """
#@@@#
@AAA@
#@@@#
"""

[animation.frame]
namespace = "idle"
pixels = """
#@@@#
@.A.@
#@@@#
"""

[animation]
namespace = "walk"
frame_interval = 0.3
loop = true

[animation.frame]
namespace = "walk"
pixels = """
#@@@#
@AAA@
#@@@#
"""

[animation.frame]
namespace = "walk"
pixels = """
#@@@#
@.A.@
#@@@#
"""

[animation]
namespace = "death"
frame_interval = 0.4
loop = false

[animation.frame]
namespace = "death"
pixels = """
#XXX#
XXXX#
#XXX#
"""

[animation.frame]
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
alpha = 0.5  # half transparent

[colors."@"]
red = 255
green = 0
blue = 0
alpha = 0.5  # half transparent

[colors."A"]
red = 255
green = 255
blue = 255
alpha = 0.5  # half transparent

[colors."X"]
red = 128
green = 128
blue = 128
alpha = 0.5  # half transparent

[colors."."]
red = 255
green = 0
blue = 255
alpha = 0.5  # half transparent
```

### 4. Mixed Loop Behavior

Different animations can have different loop settings:

```toml
[animation]
namespace = "idle"
loop = true  # Loops forever

[animation]
namespace = "death"
loop = false  # Plays once

[animation]
namespace = "explosion"
loop = false  # One-time effect
```

## API Reference

### Loading Sprites

The GGSpriteLoader provides automatic type detection for loading both static and animated sprites:

```python
from glitchygames.sprites import GGSpriteLoader

# Load any sprite file (automatic type detection)
sprite = GGSpriteLoader.load_sprite(filename="hero.toml")  # Could be static or animated
sprite = GGSpriteLoader.load_sprite(filename="static.toml")  # Static sprite
sprite = GGSpriteLoader.load_sprite(filename="animated.toml")  # Animated sprite

# Load default sprite (raspberry.cfg) when no filename provided
default_sprite = GGSpriteLoader.load_sprite()  # Loads default sprite
default_sprite = GGSpriteLoader.load_sprite(filename=None)  # Same as above
```

### Saving Sprites

The GGSpriteLoader also handles saving with automatic type detection:

```python
from glitchygames.sprites import GGSpriteLoader

# Save any sprite (automatic type detection)
GGSpriteLoader.save_sprite(sprite=sprite, filename="output.toml", file_format="toml")  # TOML format
GGSpriteLoader.save_sprite(sprite=sprite, filename="output.yaml", file_format="yaml")  # YAML format

# Save with default format (TOML)
GGSpriteLoader.save_sprite(sprite=sprite, filename="output.toml")
```

### Backwards Compatibility

Existing BitmappySprite code continues to work unchanged:

```python
from glitchygames.sprites import BitmappySprite

# Load static sprite (uses factory internally)
sprite = BitmappySprite(x=0, y=0, width=32, height=32, filename="static.toml")

# Save static sprite (uses factory internally)
sprite.save("output.toml", "toml")
sprite.save("output.yaml", "yaml")
```

### Loading Animated Sprites

```python
from glitchygames.sprites import AnimatedSprite

# Load animated sprite
sprite = AnimatedSprite("hero.toml")
```

### File Format Support

The GGSpriteLoader supports both TOML and YAML formats for loading and saving:

```python
# Load from different formats
sprite1 = GGSpriteLoader.load_sprite(filename="sprite.toml")    # TOML format
sprite2 = GGSpriteLoader.load_sprite(filename="sprite.yaml")   # YAML format

# Save to different formats
GGSpriteLoader.save_sprite(sprite=sprite, filename="output.toml", file_format="toml")    # TOML format
GGSpriteLoader.save_sprite(sprite=sprite, filename="output.yaml", file_format="yaml")   # YAML format
```

### Default Sprite Loading

When no filename is provided, the GGSpriteLoader loads the default raspberry sprite:

```python
# Load default sprite (raspberry.cfg)
default_sprite = GGSpriteLoader.load_sprite()  # Loads default sprite
default_sprite = GGSpriteLoader.load_sprite(None)  # Same as above

# The default sprite has these properties:
print(default_sprite.name)  # "Tiley McTile Face"
print(default_sprite.image.get_size())  # (16, 16)
```

### Extensible Architecture

The GGSpriteLoader is designed with extensibility in mind to support future sprite and sprite sheet formats:

```python
# Current supported formats
sprite = GGSpriteLoader.load_sprite(filename="sprite.toml")    # TOML format
sprite = GGSpriteLoader.load_sprite(filename="sprite.yaml")   # YAML format

# Future format support (planned)
# sprite = GGSpriteLoader.load_sprite("sprite.png")     # PNG sprite sheets
# sprite = GGSpriteLoader.load_sprite("sprite.json")   # JSON sprite data
# sprite = GGSpriteLoader.load_sprite("sprite.xml")    # XML sprite definitions
```

The factory pattern enables easy addition of new format support without breaking existing code:

- **Modular Design**: Each format has its own loader/saver implementation
- **Automatic Detection**: File extension and content analysis determine format
- **Consistent API**: Same interface regardless of underlying format
- **Future-Proof**: New formats can be added without API changes

### Error Handling

The GGSpriteLoader provides clear error messages for common issues:

```python
try:
    # Mixed content error (both [sprite] pixels and [animation.frame] sections)
    sprite = GGSpriteLoader.load_sprite(filename="mixed.toml")
except ValueError as e:
    print(f"Invalid sprite file: {e}")
    # Output: "Invalid sprite file format: mixed.toml"

try:
    # Animated sprite save not yet implemented
    GGSpriteLoader.save_sprite(animated_sprite, "output.toml")
except NotImplementedError as e:
    print(f"Save not supported: {e}")
    # Output: "AnimatedSprite save functionality not yet implemented"
```

### State Properties (Read-Only)

```python
# Current animation and frame
sprite.current_animation  # "idle"
sprite.current_frame      # 0

# Playback state
sprite.is_playing         # True
sprite.is_looping         # True
```

### Frame Access

```python
# Access specific frames
sprite.frames["idle"][0]  # Get idle frame 0
sprite.frames["walk"][1]  # Get walk frame 1

# Access all frames for an animation (includes interpolated frames)
sprite.frames["idle"]      # Generator yielding all frames (original + interpolated)
frame.interpolated         # False for original frames, True for interpolated frames

# Iterate through all frames (original + interpolated)
for frame in sprite.frames["idle"]:
    if not frame.interpolated:
        # This is an original frame from the sprite file
        pass
    else:
        # This is an interpolated frame generated between key frames
        pass
```

### Animation Information

```python
# Direct access to current animation metadata (recommended)
sprite.frame_interval  # Returns the frame_interval for the current animation
sprite.loop           # Returns the loop setting for the current animation
sprite.frame_count    # Returns the number of frames in the current animation

# Access specific animation metadata by name
sprite.animations["idle"].frame_interval  # Returns the frame_interval value from the [animation] section
sprite.animations["idle"].loop            # Returns the loop value from the [animation] section
sprite.animations["idle"].frame_count     # Returns the number of frames in this animation

# Current frame information
sprite.current_frame                       # Returns the current frame index (0, 1, 2, etc.)
```

### Control Properties (Write-Only)

```python
# Switch animations (resets frame_index to 0)
sprite.next_animation = "walk"  # Switch to walk animation, reset to frame 0
sprite.next_animation = "idle" # Switch to idle animation, reset to frame 0

# Jump to specific frames
sprite.next_frame = 1  # Jump to frame 1 of current animation
sprite.next_frame = 0  # Jump to frame 0 of current animation
```

### Playback Control Methods

```python
# Start playing specific animation
sprite.play_animation("idle")

# Resume current animation
sprite.play()

# Pause (preserves position)
sprite.pause()

# Stop and reset to frame 0
sprite.stop()
```

## Examples

### Practical Usage Examples

#### Loading and Saving Sprites

```python
from glitchygames.sprites import GGSpriteLoader

# Load any sprite file (automatic type detection)
sprite = GGSpriteLoader.load_sprite(filename="hero.toml")

# Check if it's animated
if hasattr(sprite, 'animations'):
    print("This is an animated sprite")
    print(f"Available animations: {list(sprite.animations.keys())}")
else:
    print("This is a static sprite")
    print(f"Sprite name: {sprite.name}")

# Save the sprite to different formats
GGSpriteLoader.save_sprite(sprite=sprite, filename="output.toml", file_format="toml")
GGSpriteLoader.save_sprite(sprite=sprite, filename="output.yaml", file_format="yaml")
```

#### Working with Static Sprites

```python
from glitchygames.sprites import BitmappySprite, GGSpriteLoader

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
loaded_sprite = GGSpriteLoader.load_sprite(filename="my_sprite.toml")
print(f"Loaded sprite: {loaded_sprite.name}")
```

#### Working with Animated Sprites

```python
from glitchygames.sprites import GGSpriteLoader

# Load animated sprite
sprite = GGSpriteLoader.load_sprite(filename="hero.toml")

# Control animation
sprite.play_animation("idle")
print(f"Current animation: {sprite.current_animation}")
print(f"Current frame: {sprite.current_frame}")

# Switch animations
sprite.next_animation = "walk"
sprite.play()

# Access frames
for frame in sprite.frames["idle"]:
    if not frame.interpolated:
        print("Original frame from file")
    else:
        print("Interpolated frame")
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
alpha = 0.5  # half transparent

[colors."@"]  # Color definition for '@' character
red = 255
green = 0
blue = 0
alpha = 0.5  # half transparent

[colors."A"]  # Color definition for 'A' character
red = 255
green = 255
blue = 255
alpha = 0.5  # half transparent
```

### Animated Sprite Examples

#### Sparse Configuration (Minimal)

```toml
[sprite]
name = "SimpleHero"

[animation]
namespace = "idle"
loop = true

[animation.frame]
namespace = "idle"
pixels = """
#@@@#
@AAA@
#@@@#
"""

[animation.frame]
namespace = "idle"
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
```

### Verbose Configuration (Explicit)

```toml
[sprite]
name = "ComplexHero"

[animation]
namespace = "idle"
frame_interval = 0.5
loop = true

[animation.frame]
namespace = "idle"
frame_index = 0
pixels = """
#@@@#
@AAA@
#@@@#
"""

[animation.frame]
namespace = "idle"
frame_index = 1
pixels = """
#@@@#
@.A.@
#@@@#
"""

[animation]
namespace = "walk"
frame_interval = 0.3
loop = true

[animation.frame]
namespace = "walk"
frame_index = 0
pixels = """
#@@@#
@AAA@
#@@@#
"""

[animation.frame]
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
alpha = 0.5  # half transparent

[colors."#"]
red = 0
green = 0
blue = 0
alpha = 0.5  # half transparent

[colors."@"]
red = 255
green = 0
blue = 0
alpha = 0.5  # half transparent

[colors."A"]
red = 255
green = 255
blue = 255
alpha = 0.5  # half transparent
```

### Key Frame Animation

```toml
[sprite]
name = "Explosion"

[animation]
namespace = "explosion"
frame_interval = 0.1
loop = false

[animation.frame]
namespace = "explosion"
frame_index = 0
pixels = """
.....
.#@#.
.....
"""

[animation.frame]
namespace = "explosion"
frame_index = 2
pixels = """
#@@@#
@@@@#
#@@@#
"""

[animation.frame]
namespace = "explosion"
frame_index = 4
pixels = """
.....
.....
.....
"""

[colors]
[colors."."]
red = 128
green = 0
blue = 128

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

[animation]
namespace = "idle"
loop = true

[animation.frame]
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

### Code Changes

**Before:**
```python
sprite = BitmappySprite("hero.toml")
```

**After:**
```python
sprite = AnimatedSprite("hero.toml")
sprite.play_animation("idle")
```

## Best Practices

### 1. Animation Design

- **Keep animations short**: 2-4 frames for most cases
- **Use consistent timing**: Stick to animation namespace global `frame_interval` when possible
- **Plan your namespaces**: Choose clear, descriptive animation namespace names. These names aid in debugging and code clarity.

### 2. File Organization

- **One sprite per file**: Keep related animations together
- **Use sparse configuration**: Only specify what you need
- **Group related animations**: idle, walk, jump in same file

### 3. Performance

- **Reuse color definitions**: Define colors once per file
- **Use key frames**: Let auto-generation fill in between frames
- **Optimize frame count**: More frames = more memory usage

### 4. Code Usage

```python
# Good: Check animation state
if sprite.current_animation == "idle" and sprite.current_frame == 0:
    # Handle idle state

# Good: Use properties for state
if sprite.is_playing and not sprite.is_looping:
    # Handle one-time animation

# Good: Access frames efficiently
current_frame = sprite.frames[sprite.current_animation][sprite.current_frame]
```

### 5. Factory Pattern Usage

**Use GGSpriteLoader for new code:**
```python
# Recommended: Use GGSpriteLoader for automatic type detection
sprite = GGSpriteLoader.load_sprite(filename="hero.ini")
GGSpriteLoader.save_sprite(sprite=sprite, filename="output.ini", file_format="ini")
```

**Maintain backwards compatibility:**
```python
# Existing code continues to work
sprite = BitmappySprite(x=0, y=0, width=32, height=32, filename="static.ini")
sprite.save("output.ini", "ini")
```

**Handle different sprite types:**
```python
sprite = GGSpriteLoader.load_sprite(filename="unknown.ini")

if hasattr(sprite, 'animations'):
    # It's an animated sprite
    sprite.play_animation("idle")
else:
    # It's a static sprite
    print(f"Static sprite: {sprite.name}")
```

**Use appropriate file formats:**
```python
# TOML format for human-readable files
GGSpriteLoader.save_sprite(sprite=sprite, filename="sprite.toml", file_format="toml")

# YAML format for programmatic editing
GGSpriteLoader.save_sprite(sprite=sprite, filename="sprite.yaml", file_format="yaml")
```

**Plan for future format support:**
```python
# Current: Use TOML/YAML for maximum compatibility
GGSpriteLoader.save_sprite(sprite=sprite, filename="sprite.toml", file_format="toml")

# Future: Additional formats will be supported
# GGSpriteLoader.save_sprite(sprite=sprite, filename="sprite.png", file_format="png")    # PNG sprite sheets
# GGSpriteLoader.save_sprite(sprite=sprite, filename="sprite.json", file_format="json")  # JSON sprite data
# GGSpriteLoader.save_sprite(sprite=sprite, filename="sprite.xml", file_format="xml")    # XML definitions
```

**Design for extensibility:**
```python
# Good: Use GGSpriteLoader for future-proof code
sprite = GGSpriteLoader.load_sprite(filename="sprite.toml")  # Works with any supported format

# Avoid: Direct format-specific loading
# sprite = BitmappySprite("sprite.toml")  # Tied to specific format
```

## Troubleshooting

### Common Issues

**Error: "Both [animation.frame] sections AND [sprite] pixels exist"**
- Remove `pixels` from `[sprite]` section when using animations

**Error: "Missing color definition for character 'X'"**
- Add color definition:
```toml
[colors."X"]
red = 255
green = 0
blue = 0
```

**Animation not playing**
- Check that `namespace` matches between `[animation]` and `[animation.frame]` sections
- Ensure `loop` is set correctly
- Check the global animation `frame_interval` for that namespace
- Check for per-frame `frame_interval` overrides that might be too fast/slow
- Call `sprite.play_animation("animation_name")` to start

**Frames in wrong order**
- Use explicit `frame_index` values to control order
- Or ensure frames are in correct file order

### Validation Checklist

- [ ] All `[animation.frame]` sections have matching `namespace`
- [ ] All `[animation]` sections have `namespace` and `loop`
- [ ] All characters in `pixels` have color definitions
- [ ] No `pixels` in `[sprite]` section when using animations
- [ ] `frame_index` values are sequential (if specified)

## Advanced Features

### Extensible Format Support

The GGSpriteLoader architecture is designed to support future sprite and sprite sheet formats without breaking existing code:

#### Current Format Support
- **TOML Format**: Human-readable configuration files
- **YAML Format**: Programmatic editing and data exchange

#### Planned Format Support
- **PNG Sprite Sheets**: Traditional sprite sheet images with metadata
- **JSON Sprite Data**: Structured data format for programmatic generation
- **XML Sprite Definitions**: Industry-standard sprite definition format
- **Custom Formats**: Plugin architecture for specialized formats

#### Architecture Benefits
```python
# Consistent API regardless of format
sprite = GGSpriteLoader.load_sprite(filename="sprite.toml")    # TOML format
sprite = GGSpriteLoader.load_sprite(filename="sprite.yaml")   # YAML format
# Future: sprite = GGSpriteLoader.load_sprite("sprite.png")     # PNG format
# Future: sprite = GGSpriteLoader.load_sprite("sprite.json")   # JSON format

# Same save API for all formats
GGSpriteLoader.save_sprite(sprite=sprite, filename="output.toml", file_format="toml")
GGSpriteLoader.save_sprite(sprite=sprite, filename="output.yaml", file_format="yaml")
# Future: GGSpriteLoader.save_sprite(sprite=sprite, filename="output.png", file_format="png")
# Future: GGSpriteLoader.save_sprite(sprite=sprite, filename="output.json", file_format="json")
```

#### Plugin Architecture
The factory pattern enables easy addition of new format support:

```python
# Future: Custom format plugins
class PNGSpriteLoader:
    def load(self, filename):
        # Load PNG sprite sheet
        pass

    def save(self, sprite, filename):
        # Save as PNG sprite sheet
        pass

# Register new format
GGSpriteLoader.register_format("png", PNGSpriteLoader())
```

### Frame Interpolation

Use key frames with auto-generation for smooth animations:

```toml
[animation.frame]
namespace = "walk"
frame_index = 0
pixels = """
#@@@#
@AAA@
#@@@#
"""

[animation.frame]
namespace = "walk"
# Auto-generated as frame 1
pixels = """
#@@@#
@.A.@
#@@@#
"""

[animation.frame]
namespace = "walk"
frame_index = 3
# Auto-generated frames 2 and 4 will be interpolated
pixels = """
#@@@#
@AAA@
#@@@#
"""
```

### Complex Timing

Mix animation namespace global and per-frame timing for realistic motion:

```toml
[animation]
namespace = "walk"
frame_interval = 0.3

[animation.frame]
namespace = "walk"
frame_index = 0
frame_interval = 0.5  # Foot contact - hold longer
pixels = """
#@@@#
@AAA@
#@@@#
"""

[animation.frame]
namespace = "walk"
frame_index = 1
# Uses animation namespace default 0.3s - quick transition
pixels = """
#@@@#
@.A.@
#@@@#
"""

[animation.frame]
namespace = "walk"
frame_index = 2
frame_interval = 0.5  # Other foot contact - hold longer
pixels = """
#@@@#
@AAA@
#@@@#
"""
```

This animation system provides powerful, flexible animation capabilities while maintaining the simplicity and familiarity of the existing GlitchyGames sprite format.
