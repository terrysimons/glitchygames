# Sprite Loader Architecture and File Format Implementation Guide

## Overview

This document provides comprehensive guidance for implementing new file formats in the GlitchyGames sprite loading system. The system supports **TOML format only**, with a well-documented architecture for adding new formats in the future.

## Current Architecture

### Core Components

1. **SpriteFactory** (`src/glitchygames/sprites/factory.py`)
   - Main entry point: `SpriteFactory.load_sprite(filename=...)` validates the file and always returns an `AnimatedSprite` (a static sprite becomes a single-frame animation); with no filename it loads `src/glitchygames/assets/raspberry.toml`
   - `SpriteFactory.save_sprite(sprite=..., filename=..., file_format=...)` saves either sprite type
   - File format detection and content analysis (`detect_file_format`, `_analyze_file`, `_analyze_toml_file`)

2. **BitmappySprite** (`src/glitchygames/sprites/bitmappy_sprite.py`)
   - Static sprite implementation
   - TOML loading/saving support (`load` goes through `SpriteFactory` and copies the result's image, falling back to `_load_static_only` when the factory refuses the file)

3. **AnimatedSprite** (`src/glitchygames/sprites/animated.py`)
   - Animated sprite implementation
   - Frame management and animation playback
   - TOML loading/saving support

### File Format Detection

There are two detection functions, both extension based:

```python
# src/glitchygames/sprites/factory.py (used by SpriteFactory and BitmappySprite)
@staticmethod
def detect_file_format(filename: str) -> str:
    """Detect file format based on extension."""
    filename_str = str(filename)
    if filename_str.endswith('.toml'):
        return 'toml'
    if filename_str.endswith(('.yaml', '.yml')):
        return 'yaml'
    return 'unknown'
```

```python
# src/glitchygames/bitmappy/utils.py (used by AnimatedSprite.load)
def detect_file_format(filename: str) -> str:
    """Detect file format from filename extension."""
    extension = Path(filename).suffix.lower().lstrip('.')
    if extension in {'toml', ''}:
        return 'toml'
    msg = f'Unsupported file format: .{extension} (only TOML is supported)'
    raise ValueError(msg)
```

Anything but `toml` is refused further on: `SpriteFactory._analyze_file` raises
`ValueError('Unsupported format: yaml. Only TOML is currently supported.')`.

**Current Support:**
- ✅ **TOML** (`.toml`) - Primary format
- ❌ **YAML** (`.yaml`, `.yml`) - Removed (still detected, then refused)
- ❌ **INI** (`.ini`) - Removed

## Implementing New File Formats

### Step 1: Update File Format Detection

**Location:** `SpriteFactory.detect_file_format` (`src/glitchygames/sprites/factory.py`) and
`detect_file_format` (`src/glitchygames/bitmappy/utils.py`)

```python
@staticmethod
def detect_file_format(filename: str) -> str:
    """Detect file format based on extension."""
    filename_str = str(filename)
    if filename_str.endswith('.toml'):
        return 'toml'

    # Add your new format detection here
    if filename_str.endswith('.json'):
        return 'json'
    if filename_str.endswith('.xml'):
        return 'xml'

    return 'unknown'
```

### Step 2: Add File Analysis Method

**Location:** `SpriteFactory._analyze_file` (`src/glitchygames/sprites/factory.py`)

Add a new analysis method for your format. It returns the same three flags as
`_analyze_toml_file`; `load_sprite` refuses a file with none of them, or with sprite pixels
and animation/frame sections both:

```python
@staticmethod
def _analyze_file(filename: str) -> dict[str, Any]:
    """Analyze file content to determine sprite type."""
    file_format = SpriteFactory.detect_file_format(filename)

    if file_format == 'toml':
        return SpriteFactory._analyze_toml_file(filename)
    if file_format == 'json':  # NEW FORMAT
        return SpriteFactory._analyze_json_file(filename)

    raise ValueError(
        _ERR_UNSUPPORTED_FORMAT_ANALYZE.format(file_format=file_format),
    )

@staticmethod
def _analyze_json_file(filename: str) -> dict[str, Any]:
    """Analyze JSON file content to determine sprite type."""
    with Path(filename).open('r', encoding='utf-8') as json_file:
        data = json.load(json_file)

    has_sprite_pixels = False
    has_animation_sections = False
    has_frame_sections = False

    # Check for sprite.pixels
    if 'sprite' in data and 'pixels' in data['sprite'] and data['sprite']['pixels'].strip():
        has_sprite_pixels = True

    # Check for animation sections
    if 'animations' in data:
        has_animation_sections = True
        # Check for frames within animations
        for animation in data['animations']:
            if 'frames' in animation:
                has_frame_sections = True
                break

    return {
        'has_sprite_pixels': has_sprite_pixels,
        'has_animation_sections': has_animation_sections,
        'has_frame_sections': has_frame_sections,
    }
```

### Step 3: Update BitmappySprite Save/Load Methods

**Location:** `BitmappySprite._save_static_only` and `BitmappySprite._load_static_only`
(`src/glitchygames/sprites/bitmappy_sprite.py`)

`save()` goes through `SpriteFactory.save_sprite`, which calls `_save` and then
`_save_static_only`. Today `_save_static_only` always writes TOML through
`_write_static_toml` (`deflate()` has already refused any other format). Dispatch on the
format there:

```python
def _save_static_only(
    self: Self,
    filename: str,
    file_format: str = DEFAULT_FILE_FORMAT,
) -> None:
    """Save a static sprite to a file (legacy method)."""
    try:
        if file_format == 'json':  # NEW FORMAT
            self._write_static_json(filename=filename)
        else:
            self._write_static_toml(filename=filename, file_format=file_format)
    except Exception:
        self.log.exception('Error in save')
        raise

def _write_static_json(self: Self, filename: str) -> None:
    """Save sprite data to JSON format."""
    config = self.deflate(file_format='json')

    with Path(filename).open('w', encoding='utf-8') as json_file:
        json.dump(config, json_file, indent=2, ensure_ascii=False)
```

Add the matching branch to `_load_static_only`, which raises for anything but `toml`.

### Step 4: Update AnimatedSprite Save/Load Methods

**Location:** `AnimatedSprite.load` and `AnimatedSprite.save` (`src/glitchygames/sprites/animated.py`)

`load(filename)` takes no format argument; it detects the format itself. `save(filename,
file_format)` writes a single-frame sprite with `_save_as_static_sprite` and anything else with
`_save_toml`; add your format to both.

```python
@override
def load(self: Self, filename: str) -> None:
    """Load animated sprite from a file."""
    file_format = detect_file_format(filename)

    if file_format == 'toml':
        self._load_toml(filename)
    elif file_format == 'json':  # NEW FORMAT
        self._load_json(filename)
    else:
        raise ValueError(ERR_UNSUPPORTED_FORMAT.format(file_format))

def _load_json(self: Self, filename: str) -> None:
    """Load animated sprite from JSON file."""
    with Path(filename).open('r', encoding='utf-8') as json_file:
        data = json.load(json_file)

    # Implement JSON loading logic
    self.name = data.get('sprite', {}).get('name', 'animated_sprite')
    self._animations = {}

    # Process animations from JSON structure
    for animation_data in data.get('animations', []):
        animation_name = animation_data.get('name', 'default')
        frames = self._load_json_frames(animation_data)
        if frames:
            self._animations[animation_name] = frames

    self._set_initial_animation()
```

### Step 5: Update Deflate Method

**Location:** `BitmappySprite.deflate` and `BitmappySprite._deflate_config`
(`src/glitchygames/sprites/bitmappy_sprite.py`)

`deflate()` wraps `_deflate_config()`, which builds the color map and pixel rows and then calls
`_raise_unsupported_format_error` for anything but `toml`. Add your format there:

```python
# End of _deflate_config
if file_format == 'toml':
    return self._create_toml_config(pixel_rows, color_map)
if file_format == 'json':  # NEW FORMAT
    return self._create_json_config(pixel_rows, color_map)
self._raise_unsupported_format_error(file_format)

def _create_json_config(self: Self, pixel_rows: list[str], color_map: dict[str, Any]) -> dict[str, Any]:
    """Convert sprite data to JSON format."""
    return {
        'sprite': {
            'name': self.name,
            'pixels': '\n'.join(pixel_rows),
            'width': self.pixels_across,
            'height': self.pixels_tall,
        },
        'colors': color_map,
        'metadata': {
            'format_version': '1.0',
            'created_by': 'GlitchyGames',
        },
    }
```

## File Format Examples

### TOML Format (Current)

```toml
[sprite]
name = "example_sprite"
pixels = """
##
##
"""

[colors."#"]
red = 0
green = 0
blue = 0

[colors."."]
red = 255
green = 255
blue = 255
```

### JSON Format (Example Implementation)

```json
{
  "sprite": {
    "name": "example_sprite",
    "pixels": "##\n##",
    "width": 2,
    "height": 2
  },
  "colors": {
    "#": {"red": 0, "green": 0, "blue": 0},
    ".": {"red": 255, "green": 255, "blue": 255}
  },
  "metadata": {
    "format_version": "1.0",
    "created_by": "GlitchyGames"
  }
}
```

### XML Format (Example Implementation)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<sprite name="example_sprite">
  <pixels>
    ##
    ##
  </pixels>
  <colors>
    <color char="#" red="0" green="0" blue="0"/>
    <color char="." red="255" green="255" blue="255"/>
  </colors>
</sprite>
```

## Testing New Formats

Tests use pytest with real pygame and real files in `tmp_path` (no shared mocks). The sprite
loader tests live in `tests/sprites/` (`test_sprite_factory.py`, `test_sprite_file_formats.py`,
`test_save_load_pixel_preservation.py`); add new format tests there.

### 1. Unit Tests

```python
# tests/sprites/test_sprite_file_formats.py
import json

from glitchygames.sprites import SpriteFactory


def test_load_json_sprite(tmp_path):
    """Test loading a sprite from JSON format."""
    json_content = {
        'sprite': {
            'name': 'test_sprite',
            'pixels': '##\n##',
            'width': 2,
            'height': 2,
        },
        'colors': {
            '#': {'red': 0, 'green': 0, 'blue': 0},
            '.': {'red': 255, 'green': 255, 'blue': 255},
        },
    }
    json_path = tmp_path / 'test_sprite.json'
    json_path.write_text(json.dumps(json_content), encoding='utf-8')

    sprite = SpriteFactory.load_sprite(filename=str(json_path))

    assert sprite.name == 'test_sprite'
    assert sprite.image.get_size() == (2, 2)
```

### 2. Integration Tests

Test the full save/load cycle:

```python
from glitchygames.sprites import BitmappySprite, SpriteFactory


def test_json_save_load_cycle(tmp_path):
    """Test complete save/load cycle for JSON format."""
    original_sprite = BitmappySprite(x=0, y=0, width=4, height=4, name='test')
    original_sprite.pixels = [(255, 0, 0)] * 16  # Red pixels

    json_path = tmp_path / 'test.json'
    original_sprite.save(str(json_path), 'json')

    loaded_sprite = SpriteFactory.load_sprite(filename=str(json_path))

    assert loaded_sprite.name == original_sprite.name
    assert loaded_sprite.image.get_at((0, 0))[:3] == (255, 0, 0)
```

## Migration Guide

### Removing YAML/INI Support

The following changes were made to remove YAML and INI support:

1. **File Format Detection** - Removed INI detection (`SpriteFactory.detect_file_format` still recognises `.yaml`/`.yml` so the refusal can name the format)
2. **Save Methods** - Removed YAML/INI save logic
3. **Load Methods** - Removed YAML/INI load logic
4. **Analysis Methods** - Removed YAML/INI analysis
5. **Tests** - Updated tests to use TOML only

### Preserving TOML Functionality

All TOML functionality has been preserved:

- ✅ Static sprite loading/saving
- ✅ Animated sprite loading/saving
- ✅ Color mapping
- ✅ Animation frame management
- ✅ File format detection
- ✅ Type analysis

## Best Practices

### 1. Error Handling

Always provide clear error messages. Error messages are module-level constants (ruff's TRY003),
for example in `src/glitchygames/sprites/bitmappy_sprite.py`:

```python
_ERR_UNSUPPORTED_FORMAT = 'Unsupported format: {file_format}'

@staticmethod
def _raise_unsupported_format_error(file_format: str) -> NoReturn:
    """Raise an error for unsupported file format."""
    raise ValueError(_ERR_UNSUPPORTED_FORMAT.format(file_format=file_format))
```

### 2. Logging

Add comprehensive logging for debugging (lazy `%s` arguments, as the loader does):

```python
def _save_new_format(self: Self, filename: str, config: dict[str, Any]) -> None:
    """Save sprite to new format."""
    self.log.debug('Starting save to %s in new format', filename)

    try:
        # Implementation here
        self.log.debug('Successfully saved to %s', filename)
    except Exception:
        self.log.exception('Error in save')
        raise
```

### 3. Documentation

Update documentation when adding new formats:

- Add format examples to this README
- Update API documentation
- Add usage examples
- Update test documentation

### 4. Backward Compatibility

When possible, maintain backward compatibility. `src/glitchygames/bitmappy/utils.py`'s
`detect_file_format` already treats a name with no extension as TOML; keep that when adding
formats:

```python
def detect_file_format(filename: str) -> str:
    """Detect file format from filename extension."""
    extension = Path(filename).suffix.lower().lstrip('.')
    if extension in {'toml', ''}:
        return 'toml'
    if extension == 'json':  # NEW FORMAT
        return 'json'
    msg = f'Unsupported file format: .{extension} (only TOML is supported)'
    raise ValueError(msg)
```

## Future Format Ideas

### PNG Sprite Sheets
- Load sprites from PNG files with metadata
- Support for sprite atlases
- Automatic frame detection

### JSON Sprite Data
- Structured data format
- Easy programmatic generation
- Web-friendly format

### XML Sprite Definitions
- Industry-standard format
- Rich metadata support
- Tool integration

### Binary Formats
- Compact storage
- Fast loading
- Game engine integration

## Conclusion

The GlitchyGames sprite loading system is designed for extensibility. By following this guide, you can easily add support for new file formats while maintaining the existing TOML functionality. The architecture supports both static and animated sprites, with comprehensive error handling and logging.

For questions or contributions, please refer to the main project documentation or create an issue in the project repository.
