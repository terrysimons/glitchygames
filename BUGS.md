# Bug Tracking for GlitchyGames

This document tracks bugs reported during development. Bugs are listed in order of discovery and will be investigated and fixed as time allows.

## Active Bugs

(No active bugs at this time)

## Resolved Bugs

### 6. Anthropic SDK Rejects Bitmappy's Non-Streaming 64k-Token Requests
- **Description**: Every Bitmappy AI request fails client-side with `ValueError: Streaming is required for operations that may take longer than 10 minutes`
- **Status**: Resolved (end-to-end sprite generation pending a funded API key)
- **Priority**: High
- **Reporter**: Found while verifying bug #5
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: The uncommitted `uv.lock` re-lock bumped `anthropic` from 0.30.1 to 0.125.0. Newer SDKs refuse non-streaming requests whose `max_tokens` implies more than 10 minutes, unless a custom timeout is set. Bitmappy sends `max_tokens=AI_MAX_OUTPUT_TOKENS` (64000). `_configure_client_timeouts()` never reaches the Anthropic client because aisuite creates providers lazily on the first request, so `client._providers` is empty at init time.
- **Solution**: `_initialize_ai_client()` always passes `{'anthropic': {'timeout': AI_TIMEOUT}}` (merged with any ollama config) to `ai.Client()`. Verified a full 64k-token request now reaches the API. Switching to streaming remains a possible future improvement.
- **Files Modified**:
  - `glitchygames/bitmappy/ai_worker.py` (`_initialize_ai_client`)
- **Tests**: `tests/tools/test_bitmappy.py` (`TestInitializeAiClient`)

### 5. AI Errors Never Reach the Bitmappy UI
- **Description**: When an AI request failed (e.g. Anthropic "credit balance is too low"), Bitmappy showed nothing or "AI response was empty"
- **Status**: Resolved
- **Priority**: High
- **Reporter**: User
- **Date Reported**: 2026-10-14
- **Date Resolved**: 2026-10-14
- **Root Cause**: Three compounding problems: (1) the retry decorator retried every exception, including permanent 4xx errors, for up to 5 attempts with backoff; (2) `_process_ai_request()` then re-raised provider SDK exceptions (e.g. `anthropic.BadRequestError`), which are not in `run_ai_worker()`'s caught exception types, so the worker process died and no response was ever queued; (3) `AIManager._process_ai_response()` ignored `AIResponse.error` and always displayed "AI response was empty"
- **Solution**: `_process_ai_request()` returns `AIResponse(content=None, error='<Type>: <message>')` instead of raising; new `_is_non_retryable_ai_error()` gives up immediately on 4xx except 408/409/429 (`RETRYABLE_CLIENT_ERROR_STATUS_CODES`); new `AIManager._handle_empty_ai_response()` shows "AI request failed: <error>" in the AI text box
- **Files Modified**:
  - `glitchygames/bitmappy/ai_worker.py`
  - `glitchygames/bitmappy/ai_manager.py`
  - `glitchygames/bitmappy/constants.py`
- **Tests**: `tests/tools/test_bitmappy_additional.py` (`TestProcessAiRequest`, `TestCreateAiRetryDecorator`), `tests/tools/test_bitmappy_editor_scene.py` (`TestProcessAiResponseErrors`)

### 4. Vertical vs Horizontal Ball Collision Detection Bug
- **Description**: Perpendicular ball collisions (vertical ball hitting horizontal ball) were incorrectly skipped based on relative velocity calculation
- **Status**: Resolved
- **Priority**: High
- **Reporter**: User
- **Date Reported**: Current session
- **Date Resolved**: Current session
- **Root Cause**: Collision detection checked if `dvn > 0` (relative velocity along normal), which can be positive for perpendicular collisions depending on geometry. Complex speed ratio logic then incorrectly skipped valid collisions when speeds were similar (speed_ratio < 1.2).
- **Solution**: Simplified collision detection to only skip when balls are BOTH moving away (dvn > 0) AND not overlapping (distance >= collision_distance). Removed faulty speed ratio check that prevented perpendicular collisions.
- **Impact**: Vertical vs horizontal collisions now processed correctly, no more missed collisions
- **Files Modified**:
  - `glitchygames/examples/paddleslap.py` - Simplified collision detection logic in `_handle_ball_collisions()`
- **Tests**: `tests/game_objects/test_ball_collision_physics.py` (21/21 passing)

### 3. First Pasted Frame Alpha Loss
- **Description**: First frame pasted into a newly created film strip on a per-pixel alpha sprite lost transparency
- **Status**: Resolved
- **Priority**: High
- **Reporter**: User
- **Date Reported**: Current session
- **Date Resolved**: Current session
- **Root Cause**: Code duplication - `_add_new_animation()` created surfaces without `pygame.SRCALPHA` flag, while `_insert_frame_at_tab()` had it
- **Solution**: Created canonical `_create_blank_frame()` helper method with proper SRCALPHA support, eliminated 24 lines of duplicated code
- **Impact**: All new frames (first and subsequent) now properly preserve per-pixel alpha transparency
- **Files Modified**:
  - `glitchygames/tools/bitmappy.py` - Created `_create_blank_frame()` helper, refactored `_add_new_animation()` and `_create_animated_sprite()`
  - `glitchygames/tools/film_strip.py` - Refactored `_insert_frame_at_tab()` to use shared helper

### 2. Ball-to-Ball Collision Clipping Bug
- **Description**: Balls moving perpendicular (horizontal vs vertical) would clip through each other, getting stuck in repeated collision loops
- **Status**: Resolved
- **Priority**: High
- **Reporter**: User
- **Date Reported**: Current session
- **Date Resolved**: Current session
- **Root Cause**: Float separation values (< 1.0) rounded to 0 when assigned to integer rect.x/rect.y positions, leaving balls overlapped after collision
- **Solution**: Ensure minimum 1-pixel separation in each direction where collision normal has significant component, use round() for integer conversion
- **Impact**: Balls can now collide cleanly without clipping, especially in horizontal vs vertical scenarios
- **Files Modified**:
  - `glitchygames/examples/paddleslap.py` - Fixed ball separation logic in `_handle_ball_collisions()`
- **Tests**: `tests/game_objects/test_multi_ball_ball_collision_bounce.py` - No more "(clipping through)" messages

### 1. Ball Movement Speed Inconsistency
- **Description**: Balls sometimes travel faster going left than right and faster going up than down
- **Status**: Resolved
- **Priority**: High
- **Reporter**: User
- **Date Reported**: Current session
- **Date Resolved**: Current session
- **Root Cause**: The `speed_up()` method in `BallSprite` was using a flawed logarithmic scaling formula that capped speed increases at 5% instead of the expected 15%, causing inconsistent speed changes over time.
- **Solution**: Replaced the complex logarithmic scaling with simple linear scaling that applies the multiplier directly to both speed components.
- **Files Modified**: 
  - `glitchygames/game_objects/ball.py` - Fixed `speed_up()` method
  - `glitchygames/game_objects/ball.py` - Added `round()` calls in `dt_tick()` for precision
  - `glitchygames/game_objects/paddle.py` - Added `round()` calls in `dt_tick()` for precision

## Notes

- All bugs are tracked with discovery date and priority level
- High priority bugs affect core gameplay and should be addressed first
- Medium priority bugs affect user experience but don't break core functionality
- Low priority bugs are minor issues or edge cases
