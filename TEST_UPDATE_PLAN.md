# Test Suite Update Plan for TOML-Only Support

## Overview
After removing YAML and INI support from the sprite loading system, the test suite needs to be updated to reflect the new TOML-only functionality.

## Tests to Add

### ✅ **Already Created**
- `test_toml_only_support.py` - Comprehensive tests for TOML-only functionality

## Tests to Update

### 1. **test_universal_sprite_glyphs.py**
**Issues:**
- Tests YAML/INI save functionality that no longer exists
- Tests format consistency across YAML/INI/TOML

**Updates Needed:**
- Remove `test_static_sprite_yaml_save()`
- Remove `test_animated_sprite_ini_save()`
- Update `test_character_mapping_consistency()` to only test TOML
- Update `test_sequential_character_assignment()` to only test TOML

### 2. **test_animated_sprite_glyphs.py**
**Issues:**
- Tests INI/YAML save functionality
- Tests format consistency across multiple formats

**Updates Needed:**
- Remove `test_animated_sprite_ini_save_load()`
- Remove `test_animated_sprite_yaml_save()`
- Update `test_animated_sprite_character_mapping_consistency()` to only test TOML
- Update `test_animated_sprite_special_character_reservation()` to only test TOML

### 3. **test_animated_sprites.py**
**Issues:**
- Creates INI files for testing
- Tests INI/YAML save functionality

**Updates Needed:**
- Update `create_static_sprite_file()` to create TOML files
- Update `create_animated_sprite_file()` to create TOML files
- Remove `test_save_static_sprite_ini()`
- Remove `test_save_static_sprite_yaml()`
- Update `test_bitmappy_sprite_save_backwards_compatibility()` to use TOML

### 4. **test_character_limit_enforcement.py**
**Issues:**
- Tests INI save functionality

**Updates Needed:**
- Update all INI save tests to use TOML
- Update file extensions from `.ini` to `.toml`

### 5. **test_animated_canvas.py**
**Issues:**
- Uses INI file extension in temp file creation

**Updates Needed:**
- Update temp file creation to use `.toml` extension

## Tests to Remove

### Files with YAML/INI References
- Remove all YAML/INI specific test methods
- Update test descriptions to reflect TOML-only support
- Remove format consistency tests that compare YAML/INI/TOML

## New Tests to Add

### 1. **Format Rejection Tests**
```python
def test_yaml_format_rejected():
    """Test that YAML format is properly rejected."""
    
def test_ini_format_rejected():
    """Test that INI format is properly rejected."""
```

### 2. **TOML-Only Functionality Tests**
```python
def test_toml_save_load_cycle():
    """Test complete save/load cycle for TOML format."""
    
def test_toml_animated_sprite_save_load():
    """Test animated sprite TOML save/load."""
```

### 3. **Error Message Tests**
```python
def test_unsupported_format_error_messages():
    """Test that error messages are clear for unsupported formats."""
```

## Implementation Priority

### High Priority (Critical)
1. ✅ `test_toml_only_support.py` - Already created
2. Update `test_animated_sprites.py` - Core functionality tests
3. Update `test_character_limit_enforcement.py` - Important for sprite limits

### Medium Priority (Important)
4. Update `test_universal_sprite_glyphs.py` - Character mapping tests
5. Update `test_animated_sprite_glyphs.py` - Animated sprite tests

### Low Priority (Nice to Have)
6. Update `test_animated_canvas.py` - Canvas interface tests
7. Update any remaining test files

## Testing Strategy

### 1. **Run Existing Tests**
```bash
pytest tests/ -v
```

### 2. **Identify Failing Tests**
- Tests that try to save as YAML/INI
- Tests that try to load YAML/INI files
- Tests that compare formats

### 3. **Update Tests Systematically**
- Start with core functionality tests
- Update format-specific tests
- Remove obsolete tests

### 4. **Verify TOML Functionality**
- Ensure all TOML save/load works
- Ensure error handling works for unsupported formats
- Ensure backward compatibility for existing TOML files

## Expected Test Results After Updates

### ✅ **Should Pass**
- All TOML save/load tests
- All TOML format detection tests
- All error handling tests for unsupported formats

### ❌ **Should Fail (Expected)**
- Any tests trying to save as YAML/INI
- Any tests trying to load YAML/INI files
- Any tests comparing YAML/INI/TOML formats

## Files to Update

1. `tests/test_universal_sprite_glyphs.py`
2. `tests/test_animated_sprite_glyphs.py`
3. `tests/test_animated_sprites.py`
4. `tests/test_character_limit_enforcement.py`
5. `tests/test_animated_canvas.py`

## Files to Keep As-Is

1. `tests/test_toml_only_support.py` - New comprehensive tests
2. `tests/test_canvas_interfaces.py` - No format-specific code
3. `tests/test_legacy_sprite_glyphs.py` - Legacy sprite tests (if applicable)

## Summary

The test suite needs significant updates to reflect the TOML-only architecture. The new `test_toml_only_support.py` file provides comprehensive coverage for the new functionality, while existing tests need to be updated to remove YAML/INI references and focus on TOML-only functionality.
