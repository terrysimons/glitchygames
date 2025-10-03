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

The GlitchyGames Animation System allows you to create animated sprites using the familiar `.ini` file format. It extends the existing BitmappySprite format with minimal disruption, supporting both simple 2-frame animations and complex multi-animation sprites.

### Key Features

- **Simplified static sprite definitions**: Minimal metadata needed for static sprites
- **Flexible Timing**: Global animation namespace and per-frame timing control
- **Multiple Animations**: Single file can contain multiple named animations
- **Pythonic API**: Clean, intuitive Python interface
- **Frame Interpolation**: Support for key-frame animation with auto-generation, optimized for common retro game formats (2-4 frame walk cycles, idle animations)

## File Format

### Static Sprite

```ini
[sprite]
name = StaticSprite
pixels = #@@@#  # Single frame pixel data
         @AAA@
         #@@@#

[#]  # Color definition for '#' character
red = 0
green = 0
blue = 0
alpha = 0.5  # Optional - half transparency

[@]  # Color definition for '@' character
red = 255
green = 0
blue = 0
alpha = 0.5  # Optional - half transparency

[A]  # Color definition for 'A' character
red = 255
green = 255
blue = 255
alpha = 0.5  # Optional - half transparency
```

### Animated Sprite

```ini
[sprite]
name = AnimatedHero

[animation]
namespace = idle
frame_interval = 0.5  # Optional, defaults to 0.5 seconds
loop = true  # Optional, defaults to true

[frame]
namespace = idle
frame_index = 0  # Optional, auto-generated if missing
pixels = #@@@#
         @AAA@
         #@@@#

[frame]
namespace = idle
frame_index = 1  # Optional, auto-generated if missing
pixels = #@@@#
         @.A.@
         #@@@#

# Color definitions (required)
[#]
red = 0
green = 0
blue = 0
alpha = 0.5  # Optional - half transparency

[@]
red = 255
green = 0
blue = 0
alpha = 0.5  # Optional - half transparency

[A]
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

#### `[frame]` Section
- **`namespace`** (required): Must match its corresponding animation namespace
- **`frame_index`** (optional): Frame position in animation (auto-generated if missing)
- **`pixels`** (required): Frame pixel data using character map
- **`frame_interval`** (optional): Per-frame timing override in seconds (overrides animation namespace default for this frame)

### Animation-Frame Relationship

The `namespace` field creates a binding between `[animation]` and `[frame]` sections. This relationship is necessary because:

- **Animation sections** define the timing and behavior (`frame_interval`, `loop`) for a group of frames
- **Frame sections** contain the actual pixel data for individual frames and can override animation timing with per-frame `frame_interval` values
- **Namespace matching** ensures frames are grouped under the correct animation
- **Multiple animations** can exist in the same file, each with their own namespace

For example, frames with `namespace = idle` belong to the animation with `namespace = idle`, while frames with `namespace = walk` belong to a separate animation with `namespace = walk`.

## Animation Features

### 1. Per-Frame Timing

Control timing at the animation namespace global and per-frame levels:

```ini
[sprite]
name = WalkingCharacter

[animation]
namespace = walk
frame_interval = 0.3  # Animation namespace default: 0.3 seconds per frame

[frame]
namespace = walk
frame_index = 0
# No frame_interval: uses global 0.3 seconds
pixels = #@@@#
         @AAA@
         #@@@#

[frame]
namespace = walk
frame_index = 1
frame_interval = 0.6  # Override: this frame takes 0.6 seconds
pixels = #@@@#
         @.A.@
         #@@@#

[frame]
namespace = walk
frame_index = 2
# No frame_interval: uses global 0.3 seconds
pixels = #@@@#
         @AAA@
         #@@@#
```

**Timing Rules:**
- Global `frame_interval` = default for all frames
- Per-frame `frame_interval` = override for that specific frame
- Missing per-frame `frame_interval` = use animation namespace default
- No animation namespace `frame_interval` specified = use 0.5s default

### 2. Frame Order and Auto-Generation

Frames can be ordered explicitly or auto-generated:

```ini
[animation]
namespace = complex
frame_interval = 0.2

[frame]
namespace = complex
frame_index = 0  # Explicit: key frame
pixels = #@@@#
         @AAA@
         #@@@#

[frame]
namespace = complex
# No frame_index: auto-generated as 1
pixels = #@@@#
         @.A.@
         #@@@#

[frame]
namespace = complex
frame_index = 5  # Explicit: another key frame
pixels = #@@@#
         @AAA@
         #@@@#

[frame]
namespace = complex
# No frame_index: auto-generated as 6
pixels = #@@@#
         @.A.@
         #@@@#
```

**Auto-Generation Rules:**
- Missing `frame_index` values are filled in sequence
- Starts from 0, skips existing explicit indices
- Enables frame interpolation between key frames
- Interpolated frames are generated automatically and marked with `interpolated = True`
- Original frames from the sprite file have `interpolated = False`

### 3. Multiple Animations

Single file can contain multiple animations:

```ini
[sprite]
name = Hero

[animation]
namespace = idle
frame_interval = 0.5
loop = true

[frame]
namespace = idle
pixels = #@@@#
         @AAA@
         #@@@#

[frame]
namespace = idle
pixels = #@@@#
         @.A.@
         #@@@#

[animation]
namespace = walk
frame_interval = 0.3
loop = true

[frame]
namespace = walk
pixels = #@@@#
         @AAA@
         #@@@#

[frame]
namespace = walk
pixels = #@@@#
         @.A.@
         #@@@#

[animation]
namespace = death
frame_interval = 0.4
loop = false

[frame]
namespace = death
pixels = #XXX#
         XXXX#
         #XXX#

[frame]
namespace = death
pixels = .....
         .....
         .....

[#]
red = 0
green = 0
blue = 0
alpha = 0.5  # half transparent

[@]
red = 255
green = 0
blue = 0
alpha = 0.5  # half transparent

[A]
red = 255
green = 255
blue = 255
alpha = 0.5  # half transparent

[X]
red = 128
green = 128
blue = 128
alpha = 0.5  # half transparent

[.]
red = 255
green = 0
blue = 255
alpha = 0.5  # half transparent
```

### 4. Mixed Loop Behavior

Different animations can have different loop settings:

```ini
[animation]
namespace = idle
loop = true  # Loops forever

[animation]
namespace = death
loop = false  # Plays once

[animation]
namespace = explosion
loop = false  # One-time effect
```

## API Reference

### Loading Animated Sprites

```python
from glitchygames.sprites import AnimatedBitmappySprite

# Load animated sprite
sprite = AnimatedBitmappySprite("hero.ini")
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

### Static Sprite Examples

#### Sparse Static Sprite (Minimal)
```ini
[sprite]
name = SimpleSprite
pixels = #@@@#
         @AAA@
         #@@@#

[#]
red = 0
green = 0
blue = 0

[@]
red = 255
green = 0
blue = 0

[A]
red = 255
green = 255
blue = 255
```

#### Verbose Static Sprite (Explicit)
```ini
[sprite]
name = ComplexSprite
pixels = #@@@#
         @AAA@
         #@@@#

[#]  # Color definition for '#' character
red = 0
green = 0
blue = 0
alpha = 0.5  # half transparent

[@]  # Color definition for '@' character
red = 255
green = 0
blue = 0
alpha = 0.5  # half transparent

[A]  # Color definition for 'A' character
red = 255
green = 255
blue = 255
alpha = 0.5  # half transparent
```

### Animated Sprite Examples

#### Sparse Configuration (Minimal)

```ini
[sprite]
name = SimpleHero

[animation]
namespace = idle
loop = true

[frame]
namespace = idle
pixels = #@@@#
         @AAA@
         #@@@#

[frame]
namespace = idle
pixels = #@@@#
         @.A.@
         #@@@#

[#]
red = 0
green = 0
blue = 0

[@]
red = 255
green = 0
blue = 0

[A]
red = 255
green = 255
blue = 255
```

### Verbose Configuration (Explicit)

```ini
[sprite]
name = ComplexHero

[animation]
namespace = idle
frame_interval = 0.5
loop = true

[frame]
namespace = idle
frame_index = 0
pixels = #@@@#
         @AAA@
         #@@@#

[frame]
namespace = idle
frame_index = 1
pixels = #@@@#
         @.A.@
         #@@@#

[animation]
namespace = walk
frame_interval = 0.3
loop = true

[frame]
namespace = walk
frame_index = 0
pixels = #@@@#
         @AAA@
         #@@@#

[frame]
namespace = walk
frame_index = 1
frame_interval = 0.2
pixels = #@@@#
         @.A.@
         #@@@#

[.]
red = 255
green = 0
blue = 255
alpha = 0.5  # half transparent

[#]
red = 0
green = 0
blue = 0
alpha = 0.5  # half transparent

[@]
red = 255
green = 0
blue = 0
alpha = 0.5  # half transparent

[A]
red = 255
green = 255
blue = 255
alpha = 0.5  # half transparent
```

### Key Frame Animation

```ini
[sprite]
name = Explosion

[animation]
namespace = explosion
frame_interval = 0.1
loop = false

[frame]
namespace = explosion
frame_index = 0
pixels = .....
         .#@#.
         .....

[frame]
namespace = explosion
frame_index = 2
pixels = #@@@#
         @@@@#
         #@@@#

[frame]
namespace = explosion
frame_index = 4
pixels = .....
         .....
         .....

[.]
red = 128
green = 0
blue = 128

[#]
red = 0
green = 0
blue = 0

[@]
red = 255
green = 0
blue = 0

[A]
red = 255
green = 255
blue = 255
```

## Migration Guide

### From Static Sprites

**Static:**
```ini
[sprite]
name = StaticHero
pixels = #@@@#
         @AAA@
         #@@@#

[#]
red = 0
green = 0
blue = 0

[@]
red = 255
green = 0
blue = 0

[A]
red = 255
green = 255
blue = 255
```

**Animated:**
```ini
[sprite]
name = AnimatedHero

[animation]
namespace = idle
loop = true

[frame]
namespace = idle
pixels = #@@@#
         @AAA@
         #@@@#

[#]
red = 0
green = 0
blue = 0

[@]
red = 255
green = 0
blue = 0

[A]
red = 255
green = 255
blue = 255
```

### Code Changes

**Before:**
```python
sprite = BitmappySprite("hero.ini")
```

**After:**
```python
sprite = AnimatedBitmappySprite("hero.ini")
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

## Troubleshooting

### Common Issues

**Error: "Both [frame] sections AND [sprite] pixels exist"**
- Remove `pixels` from `[sprite]` section when using animations

**Error: "Missing color definition for character 'X'"**
- Add color definition:
```ini
[X]
red = 255
green = 0
blue = 0
```

**Animation not playing**
- Check that `namespace` matches between `[animation]` and `[frame]` sections
- Ensure `loop` is set correctly
- Check the global animation `frame_interval` for that namespace
- Check for per-frame `frame_interval` overrides that might be too fast/slow
- Call `sprite.play_animation("animation_name")` to start

**Frames in wrong order**
- Use explicit `frame_index` values to control order
- Or ensure frames are in correct file order

### Validation Checklist

- [ ] All `[frame]` sections have matching `namespace`
- [ ] All `[animation]` sections have `namespace` and `loop`
- [ ] All characters in `pixels` have color definitions
- [ ] No `pixels` in `[sprite]` section when using animations
- [ ] `frame_index` values are sequential (if specified)

## Advanced Features

### Frame Interpolation

Use key frames with auto-generation for smooth animations:

```ini
[frame]
namespace = walk
frame_index = 0
pixels = #@@@#
         @AAA@
         #@@@#

[frame]
namespace = walk
# Auto-generated as frame 1
pixels = #@@@#
         @.A.@
         #@@@#

[frame]
namespace = walk
frame_index = 3
# Auto-generated frames 2 and 4 will be interpolated
pixels = #@@@#
         @AAA@
         #@@@#
```

### Complex Timing

Mix animation namespace global and per-frame timing for realistic motion:

```ini
[animation]
namespace = walk
frame_interval = 0.3

[frame]
namespace = walk
frame_index = 0
frame_interval = 0.5  # Foot contact - hold longer
pixels = #@@@#
         @AAA@
         #@@@#

[frame]
namespace = walk
frame_index = 1
# Uses animation namespace default 0.3s - quick transition
pixels = #@@@#
         @.A.@
         #@@@#

[frame]
namespace = walk
frame_index = 2
frame_interval = 0.5  # Other foot contact - hold longer
pixels = #@@@#
         @AAA@
         #@@@#
```

This animation system provides powerful, flexible animation capabilities while maintaining the simplicity and familiarity of the existing GlitchyGames sprite format.
