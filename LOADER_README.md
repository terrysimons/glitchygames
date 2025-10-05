# Sprite Loader Architecture and File Format Implementation Guide

## Overview

This document provides comprehensive guidance for implementing new file formats in the GlitchyGames sprite loading system. The system has been cleaned up to support **TOML format only**, with a well-documented architecture for adding new formats in the future.

## Current Architecture

### Core Components

1. **SpriteFactory** (`glitchygames/sprites/__init__.py:1768-1985`)
   - Main entry point for loading sprites
   - Automatic file format detection
   - Type analysis and sprite creation

2. **BitmappySprite** (`glitchygames/sprites/__init__.py:997-1858`)
   - Static sprite implementation
   - TOML loading/saving support
   - Legacy compatibility layer

3. **AnimatedSprite** (`glitchygames/sprites/animated.py:332+`)
   - Animated sprite implementation
   - Frame management and animation playback
   - TOML loading/saving support

### File Format Detection

The system uses file extensions to detect format:

```python
@staticmethod
def _detect_file_format(filename: str) -> str:
    """Detect file format based on file extension."""
    filename_str = str(filename)
    filename_lower = filename_str.lower()
    if filename_lower.endswith((".yaml", ".yml")):
        return "yaml"  # REMOVED - no longer supported
    if filename_lower.endswith(".ini"):
        return "ini"   # REMOVED - no longer supported
    return "toml"  # Default to toml
```

**Current Support:**
- ✅ **TOML** (`.toml`) - Primary format
- ❌ **YAML** (`.yaml`, `.yml`) - Removed
- ❌ **INI** (`.ini`) - Removed

## Implementing New File Formats

### Step 1: Update File Format Detection

**Location:** `glitchygames/sprites/__init__.py:1809-1817`

```python
@staticmethod
def _detect_file_format(filename: str) -> str:
    """Detect file format based on file extension."""
    filename_str = str(filename)
    filename_lower = filename_str.lower()
    
    # Add your new format detection here
    if filename_lower.endswith(".json"):
        return "json"
    if filename_lower.endswith(".xml"):
        return "xml"
    if filename_lower.endswith(".png"):
        return "png"
    
    return "toml"  # Default to toml
```

### Step 2: Add File Analysis Method

**Location:** `glitchygames/sprites/__init__.py:1820-1885`

Add a new analysis method for your format:

```python
@staticmethod
def _analyze_file(filename: str) -> dict:
    """Analyze file content to determine sprite type."""
    file_format = SpriteFactory._detect_file_format(filename)

    if file_format == "toml":
        return SpriteFactory._analyze_toml_file(filename)
    elif file_format == "json":  # NEW FORMAT
        return SpriteFactory._analyze_json_file(filename)
    elif file_format == "xml":   # NEW FORMAT
        return SpriteFactory._analyze_xml_file(filename)
    # Add more formats as needed
    else:
        raise ValueError(f"Unsupported file format: {file_format}")

@staticmethod
def _analyze_json_file(filename: str) -> dict:
    """Analyze JSON file content to determine sprite type."""
    import json
    
    with Path(filename).open("r", encoding="utf-8") as f:
        data = json.load(f)

    has_sprite_pixels = False
    has_animation_sections = False
    has_frame_sections = False

    # Check for sprite.pixels
    if "sprite" in data and "pixels" in data["sprite"] and data["sprite"]["pixels"].strip():
        has_sprite_pixels = True

    # Check for animation sections
    if "animations" in data:
        has_animation_sections = True
        # Check for frames within animations
        for anim in data["animations"]:
            if "frames" in anim:
                has_frame_sections = True
                break

    return {
        "has_sprite_pixels": has_sprite_pixels,
        "has_animation_sections": has_animation_sections,
        "has_frame_sections": has_frame_sections,
    }
```

### Step 3: Update BitmappySprite Save/Load Methods

**Location:** `glitchygames/sprites/__init__.py:1283-1325`

Add support in the save method:

```python
def _save_static_only(
    self: Self, filename: str, file_format: str = DEFAULT_FILE_FORMAT
) -> None:
    """Save a static sprite to a file (legacy method)."""
    try:
        self.log.debug(f"Starting static-only save in {file_format} format to {filename}")
        config = self.deflate(file_format=file_format)
        self.log.debug(f"Got config from deflate: {config}")

        if file_format == "toml":
            # TOML saving logic (existing)
            self._save_toml(filename, config)
        elif file_format == "json":  # NEW FORMAT
            self._save_json(filename, config)
        elif file_format == "xml":   # NEW FORMAT
            self._save_xml(filename, config)
        else:
            self._raise_unsupported_format_error(file_format)

        self.log.debug(f"Successfully saved to {filename}")

    except Exception:
        self.log.exception("Error in save")
        raise

def _save_json(self: Self, filename: str, config: dict) -> None:
    """Save sprite data to JSON format."""
    import json
    
    # Convert config to JSON-serializable format
    json_data = self._convert_config_to_json(config)
    
    with Path(filename).open("w", encoding="utf-8") as json_file:
        json.dump(json_data, json_file, indent=2, ensure_ascii=False)
```

### Step 4: Update AnimatedSprite Save/Load Methods

**Location:** `glitchygames/sprites/animated.py:560-570`

Add format support in the load method:

```python
def _load(self: Self, filename: str, file_format: str = "toml") -> None:
    """Load animated sprite from file."""
    if file_format == "toml":
        self._load_toml(filename)
    elif file_format == "json":  # NEW FORMAT
        self._load_json(filename)
    elif file_format == "xml":   # NEW FORMAT
        self._load_xml(filename)
    else:
        raise ValueError(f"Unsupported file format: {file_format}")

def _load_json(self: Self, filename: str) -> None:
    """Load animated sprite from JSON file."""
    import json
    
    with Path(filename).open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Implement JSON loading logic
    self.name = data.get("sprite", {}).get("name", "animated_sprite")
    self._animations = {}
    
    # Process animations from JSON structure
    for anim_data in data.get("animations", []):
        anim_name = anim_data.get("name", "default")
        frames = self._load_json_frames(anim_data)
        if frames:
            self._animations[anim_name] = frames
    
    self._set_initial_animation()
```

### Step 5: Update Deflate Method

**Location:** `glitchygames/sprites/__init__.py:1326-1400`

Add format support in the deflate method:

```python
def deflate(self: Self, file_format: str = "toml") -> dict | configparser.ConfigParser:
    """Deflate a sprite to a configuration format."""
    try:
        self.log.debug(f"Starting deflate for {self.name} in {file_format} format")
        
        # ... existing logic ...
        
        if file_format == "toml":
            return self._deflate_toml()
        elif file_format == "json":  # NEW FORMAT
            return self._deflate_json()
        elif file_format == "xml":   # NEW FORMAT
            return self._deflate_xml()
        else:
            self._raise_unsupported_format_error(file_format)
            
    except Exception:
        self.log.exception("Error in deflate")
        raise

def _deflate_json(self: Self) -> dict:
    """Convert sprite data to JSON format."""
    return {
        "sprite": {
            "name": self.name,
            "pixels": self._get_pixel_string(),
            "width": self.pixels_across,
            "height": self.pixels_tall
        },
        "colors": self._get_color_mapping(),
        "metadata": {
            "format_version": "1.0",
            "created_by": "GlitchyGames"
        }
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

### 1. Unit Tests

Create test files in `tests/` directory:

```python
# tests/test_json_sprite_loader.py
import unittest
from pathlib import Path
import tempfile

class TestJSONSpriteLoader(unittest.TestCase):
    def test_load_json_sprite(self):
        """Test loading a sprite from JSON format."""
        # Create test JSON file
        json_content = {
            "sprite": {
                "name": "test_sprite",
                "pixels": "##\n##",
                "width": 2,
                "height": 2
            },
            "colors": {
                "#": {"red": 0, "green": 0, "blue": 0},
                ".": {"red": 255, "green": 255, "blue": 255}
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            import json
            json.dump(json_content, f)
            temp_filename = f.name
        
        try:
            # Test loading
            sprite = SpriteFactory.load_sprite(filename=temp_filename)
            self.assertEqual(sprite.name, "test_sprite")
            self.assertEqual(sprite.pixels_across, 2)
            self.assertEqual(sprite.pixels_tall, 2)
        finally:
            Path(temp_filename).unlink()
```

### 2. Integration Tests

Test the full save/load cycle:

```python
def test_json_save_load_cycle(self):
    """Test complete save/load cycle for JSON format."""
    # Create original sprite
    original_sprite = BitmappySprite(x=0, y=0, width=4, height=4, name="test")
    original_sprite.pixels = [(255, 0, 0)] * 16  # Red pixels
    
    # Save to JSON
    json_file = self.temp_path / "test.json"
    original_sprite.save(str(json_file), "json")
    
    # Load from JSON
    loaded_sprite = SpriteFactory.load_sprite(filename=str(json_file))
    
    # Verify they match
    self.assertEqual(original_sprite.name, loaded_sprite.name)
    self.assertEqual(original_sprite.pixels, loaded_sprite.pixels)
```

## Migration Guide

### Removing YAML/INI Support

The following changes were made to remove YAML and INI support:

1. **File Format Detection** - Removed YAML/INI detection
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

Always provide clear error messages:

```python
def _raise_unsupported_format_error(self: Self, file_format: str) -> None:
    """Raise error for unsupported file format."""
    supported_formats = ["toml"]  # Add new formats here
    raise ValueError(
        f"Unsupported file format: {file_format}. "
        f"Supported formats: {', '.join(supported_formats)}"
    )
```

### 2. Logging

Add comprehensive logging for debugging:

```python
def _save_new_format(self: Self, filename: str, config: dict) -> None:
    """Save sprite to new format."""
    self.log.debug(f"Starting save to {filename} in new format")
    
    try:
        # Implementation here
        self.log.debug(f"Successfully saved to {filename}")
    except Exception as e:
        self.log.error(f"Failed to save to {filename}: {e}")
        raise
```

### 3. Documentation

Update documentation when adding new formats:

- Add format examples to this README
- Update API documentation
- Add usage examples
- Update test documentation

### 4. Backward Compatibility

When possible, maintain backward compatibility:

```python
def _detect_file_format(filename: str) -> str:
    """Detect file format with fallback to TOML."""
    # Try to detect specific format
    if filename.endswith(".json"):
        return "json"
    
    # Fallback to TOML for unknown formats
    return "toml"
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
