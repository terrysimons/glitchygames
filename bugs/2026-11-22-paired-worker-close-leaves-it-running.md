# A Paired-Run Worker That Outlives Its Close Is Left Running

- **Description**: `scripts/ai_behaviour/paired.py`'s `Worker.close()` closed the worker's input, waited `WORKER_CLOSE_SECONDS` (30) for it to end, then closed its output pipe. When the wait ran out, `subprocess.TimeoutExpired` raised past the rest: the worker was neither stopped nor reaped, and its output pipe was left for the garbage collector. Its direct `Popen` also put it in this process's group, so nothing could stop it with what it started. Reproduced on main (`6163d80c`, 2026-11-22) with a stand-in worker that ignores the end of its input: `close()` raised `TimeoutExpired` and the test harness's child-process guard found the worker still running.
- **Status**: Fixed on `fix/paired-worker-close` (2026-11-22)
- **Priority**: Low. Only a worker that hangs (a version stuck in a question, or a server that never answers) reaches it, and only in the hand-run paired comparison.
- **Root Cause**: the close assumed the wait succeeds: nothing handled its timeout, and the output close sat after the wait instead of in a `finally`.
- **Test gap**: the worker tests ran only workers that end on their own (one answering, one crashing); none outlived its close.
- **Fix**: the worker starts in a session of its own (`start_new_session=True`). `close()` stops and reaps a worker still running when its wait runs out, with its group (`glitchygames.process.stop_command`), and closes its output pipe in a `finally`, however the close ends. It keeps its direct `Popen` (the owner's choice, 2026-11-22): `start_command` cannot pipe a child's input and output or set its working directory.
- **Tests**: `tests/test_ai_behaviour.py::test_a_worker_that_outlives_its_close_is_stopped_and_its_pipes_closed`, which raised `TimeoutExpired` on main, with the worker left running.
- **Siblings**: found by the pipe-leak sweep of 2026-11-22 (every child started with a pipe: is the pipe closed once the child is reaped, on every path?), recorded in `bugs/2026-11-20-killpg-misses-a-process-forked-during-it-on-macos.md` on `fix/killpg-misses-forked-process`, where `stop_command` now closes a reaped child's pipes. This worker was the only caller not covered.
- **Reporter**: the pipe-leak sweep (session glitchygames-bc), at the coordinator's request
- **Date Reported**: 2026-11-22
- **Files**: `scripts/ai_behaviour/paired.py`, `tests/test_ai_behaviour.py`
