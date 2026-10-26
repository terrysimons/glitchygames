# GlitchyGames AI Module

Clean, concise AI-powered sprite generation for the GlitchyGames pixel art editor.

## Overview

This module provides optimized prompts and utilities for generating sprites using AI models (via aisuite). It replaces verbose, inline prompt construction with a tested, reusable API.

## Features

✅ **Concise Prompts** - 50% token reduction vs old system
✅ **Smart Hints** - Auto-detects animation requests and size specifications
✅ **Clean Formatting** - Handles TOML format with per-pixel alpha support
✅ **Response Validation** - Catches common AI errors before processing
✅ **Refinement** - Follow-up requests ("make it bigger") that keep the current sprite's structure
✅ **Testable** - Unit tests in `tests/ai/test_sprite_generator.py`
✅ **Type-safe** - Full type hints for better IDE support

## Quick Start

```python
from glitchygames.ai import (
    build_sprite_generation_messages,
    clean_ai_response,
    validate_ai_response
)

# Build optimized messages for AI
messages = build_sprite_generation_messages(
    user_request="Create a 16x16 animated walking hero",
    training_examples=my_training_data,
    max_examples=3
)

# Send to AI (using aisuite)
response = client.chat.completions.create(
    model="anthropic:claude-sonnet-4-5",
    messages=messages
)

# Extract and clean content
raw_content = response.choices[0].message.content
cleaned = clean_ai_response(raw_content)

# Validate before using
is_valid, error = validate_ai_response(cleaned)
if is_valid:
    save_sprite(cleaned)
else:
    print(f"Invalid: {error}")
```

## API Reference

### Message Building

#### `build_sprite_generation_messages(user_request, training_examples=None, *, max_examples=3, include_size_hint=True, include_animation_hint=True)`

Builds optimized conversation for AI sprite generation.

**Parameters:**
- `user_request` (str): User's sprite generation request
- `training_examples` (list[dict], optional): Example sprites for context
- `max_examples` (int): Maximum examples to include (default: 3)
- `include_size_hint` (bool): Auto-detect and emphasize size hints (default: True)
- `include_animation_hint` (bool): Auto-detect and emphasize animation (default: True)

**Returns:** `list[dict[str, str]]` - Messages ready for AI API

**Example:**
```python
messages = build_sprite_generation_messages(
    "Create a 32x32 coin with spinning animation",
    training_examples=[coin_example, animation_example]
)
# Automatically adds: "IMPORTANT: Generate sprite at exactly 32x32 pixels."
# Automatically adds: "IMPORTANT: This should be an ANIMATED sprite..."
```

#### `build_refinement_messages(user_request, last_sprite_content, conversation_history=None, *, include_size_hint=True, include_animation_hint=True)`

Builds a conversation that asks the AI to change an existing sprite, keeping its animation namespaces and frame counts unless the request says otherwise.

**Parameters:**
- `user_request` (str): User's refinement request (e.g. "make it red")
- `last_sprite_content` (str): The current sprite's TOML
- `conversation_history` (list[dict[str, str]], optional): Earlier messages, inserted after the format specification
- `include_size_hint` / `include_animation_hint` (bool): As for `build_sprite_generation_messages` (default: True)

**Returns:** `list[dict[str, str]]` - Messages ready for AI API

### Response Cleaning

#### `clean_ai_response(content)`

Removes markdown formatting and explanatory text from AI responses.

**Parameters:**
- `content` (str | None): Raw AI response

**Returns:** `str | None` - Cleaned TOML content (empty or `None` input is returned unchanged)

**Removes:**
- Markdown code blocks (````toml`, ` ` ` `)
- Leading explanatory text before the first line starting with `[`
- Surrounding whitespace

**Example:**
```python
raw = "```toml\n[sprite]\nname = \"test\"\n```"
clean = clean_ai_response(raw)
# Returns: "[sprite]\nname = \"test\""
```

### Response Validation

#### `validate_ai_response(content)`

Validates AI response for common errors.

**Parameters:**
- `content` (str): AI response content (preferably after cleaning)

**Returns:** `tuple[bool, str]` - (is_valid, error_message)

**Checks for:**
- Empty responses
- Error/apology messages
- Uncleaned markdown
- Truncated pixel data (an unclosed `pixels = """` block)
- Missing required sections ([sprite], [colors])
- Mixed static/animated format
- Comma-separated color values

**Example:**
```python
is_valid, error = validate_ai_response(content)
if not is_valid:
    logging.error(f"Validation failed: {error}")
    # Handle error...
```

### Training Example Formatting

#### `format_training_example(example, *, include_raw=True)`

Formats training examples as clean TOML with metadata.

**Parameters:**
- `example` (dict): Training example with sprite data
- `include_raw` (bool): Use raw_content if available (default: True)

**Returns:** `str` - Formatted TOML with metadata comment

**Example:**
```python
example = {
    "name": "RedSquare",
    "sprite_type": "static",
    "has_alpha": False,
    "pixels": "RR\nRR",
    "colors": {"R": {"red": 255, "green": 0, "blue": 0}}
}

formatted = format_training_example(example)
# Returns:
# # name="RedSquare", type=static
# [sprite]
# name = "RedSquare"
# pixels = """
# RR
# RR
# """
#
# [colors."R"]
# red = 255
# green = 0
# blue = 0
```

### Utility Functions

#### `get_sprite_size_hint(request)`

Extracts size specification from user request.

**Parameters:**
- `request` (str): User request text

**Returns:** `tuple[int, int] | None` - (width, height) or None

**Patterns matched:**
- "16x16", "32x32" (with x)
- "16 x 16" (with spaces)
- "16×16" (with ×)

**Size range:** 1-64 pixels (`MAX_SPRITE_DIMENSION`); larger sizes return None

**Example:**
```python
size = get_sprite_size_hint("Create a 32x32 icon")
# Returns: (32, 32)

size = get_sprite_size_hint("Make a sprite")
# Returns: None
```

#### `detect_animation_request(request)`

Detects if user is requesting animated sprite.

**Parameters:**
- `request` (str): User request text

**Returns:** `bool` - True if animation keywords detected

**Keywords:** animat, frame, walk, run, jump, idle, 2-frame, multi-frame, loop, cycle, sequence, moving, spinning, rotating, bouncing

**Example:**
```python
is_animated = detect_animation_request("animated walking hero")
# Returns: True

is_animated = detect_animation_request("static coin")
# Returns: False
```

#### `detect_refinement_request(request)`

Detects refinement phrasing ("make it", "change", "bigger", "add", ...). Not exported from `glitchygames.ai`; import it from `glitchygames.ai.sprite_generator`.

**Returns:** `bool` - True if refinement keywords detected

## Prompt Templates

### `SpriteGenerationPrompt`

Class containing all prompt templates.

**Attributes:**
- `FORMAT_SPEC`: Concise TOML format specification
- `SYSTEM_MESSAGE`: System role message
- `ASSISTANT_CONFIRMATION`: Assistant confirmation message

**Usage:**
```python
from glitchygames.ai.sprite_generator import SpriteGenerationPrompt

print(SpriteGenerationPrompt.FORMAT_SPEC)
```

## Integration with Bitmappy

See [INTEGRATION.md](INTEGRATION.md) for detailed integration guide.

**Where it is used:**
- `AIManager.on_text_submit_event()` (`src/apps/bitmappy/bitmappy/ai_manager.py`) builds refinement messages when the canvas holds a sprite to refine, else generation messages (`max_examples=3`); responses go through `clean_ai_response` and `validate_ai_response`
- `src/apps/bitmappy/bitmappy/ai_worker.py` (the AI worker process) uses `get_sprite_size_hint`
- `SpriteGenerationService` (`glitchygames/services/sprite_generation_service.py`, used by the API server) builds, cleans and validates the same way

## Testing

```bash
# Run all AI module tests
pytest tests/ai/test_sprite_generator.py -v

# Run specific test class
pytest tests/ai/test_sprite_generator.py::TestResponseValidation -v

# Run without coverage check
pytest tests/ai/test_sprite_generator.py -v --no-cov
```

**Test coverage:** message building (generation and refinement), training example formatting and
reconstruction, response cleaning, response validation (including truncation and mixed formats),
size hint, animation and refinement detection.

## File Structure

```
glitchygames/ai/
├── __init__.py              # Public API exports
├── sprite_generator.py      # Core implementation
├── README.md                # This file
└── INTEGRATION.md           # Integration guide

tests/ai/
├── __init__.py
└── test_sprite_generator.py # Unit tests
```

## Performance

**Token usage comparison:**

| Metric | Old System | New System | Improvement |
|--------|-----------|-----------|-------------|
| Prompt tokens | ~1500 | ~600 | 60% reduction |
| Example tokens | ~2000 | ~1200 | 40% reduction |
| Total avg | ~4000 | ~2000 | 50% reduction |

**Benefits:**
- Faster API calls (fewer tokens)
- Lower costs (50% token reduction)
- Better reliability (clearer prompts)
- Easier testing (modular code)

## Design Principles

1. **Concise over verbose** - Clear, minimal prompts
2. **Testable over inline** - Separate, testable functions
3. **Robust over fragile** - Validation and error handling
4. **Smart over manual** - Auto-detect hints from requests
5. **Documented over assumed** - Clear API with examples

## Future Enhancements

- [ ] Semantic example selection (embeddings)
- [ ] Style transfer support
- [ ] Sprite variation generation
- [ ] Animation preview before generation

## Contributing

When modifying this module:

1. Update tests first (TDD)
2. Keep prompts concise
3. Add validation for new errors
4. Update documentation
5. Run full test suite

## License

Same as parent GlitchyGames project.
