# A Slow AI Service Was Taken for a Stopped One and Started Again

- **Description**: `LocalAIClient` ran the control script's `start` for a service that was running
  but did not answer its readiness check within `HEALTH_TIMEOUT_SECONDS` (2 s).
- **Status**: Fixed (2026-11-25, `fix/slow-ai-service-is-not-started`).
- **Priority**: Medium. A busy service got a needless start, which can be refused for want of memory.
- **Root Cause**: `_is_ready` answered False for every HTTP error, so "refused" and "not answered in
  time" were one answer, and `_ensure_ready` started the service for both.
- **Evidence**: CircleCI job 6150 (Windows, main `a4f9dca0d`):
  `test_a_running_service_is_left_alone` failed after 9.0 s, and the test server's write of the
  readiness answer met WinError 10053 (the client had gone). Reproduced on macOS: a first answer 0.5 s
  late runs no script, 2.5 s late runs it. Why that machine stalled is not known.
- **Fix**: A check is ready, slow (a read timeout) or not ready. A slow service is waited for, up to
  `READY_TIMEOUT_SECONDS`, and started only if a later check finds it isn't up. A connection that
  times out stays "not ready": Windows ends a connect to a closed port that way.
- **Test gap**: No test had a running service that answers late.
- **Files**: `src/glitchygames/ai/local_service.py`, `tests/ai/test_local_service.py`.
- **Siblings (swept)**: `services/ai-service/src/glitchygames_ai_service/workers.py` `state_of` has the
  same shape and is **not fixed**: a model server that does not answer in 1 s is described as stopped,
  so `/health/ready` answers 503 and the client starts the service. `scripts/ai_model_comparison.py`
  only waits on a failed check, and `AiLink` retries a connection without starting anything: both fine.
- **Limit**: The check is still one HTTP request; a 503 (models stopped or loading) still runs `start`.
