# The Pre-Push test-random Hook Crashed Writing Its Output Into a Pipe

- **Description**: Pushing `arcade-4-sound` (PR #207) on 2026-11-14, the second push's pre-push run crashed inside pre-commit with `BlockingIOError` (errno 35, `EAGAIN` on macOS) while `test-random` wrote its output, with no test failed (`0 FAILED`). The push had been started with its output piped through `tail`. The third push, with the output redirected to a file instead, passed every check
- **Status**: Open (cause not established; seen once)
- **Priority**: Low (a push piped into another program can fail with no test failed; redirecting to a file avoids it)
- **Reporter**: Claude, from the Arcade sub-plan 4 run's ledger (archived outside the repository)
- **Date Reported**: 2026-11-14
- **Details**: errno 35 on a write means the output was non-blocking and the pipe was full: something in the chain (pre-commit, nox, pytest-xdist's workers, or a child of the suite) left the shared stdout in non-blocking mode, and `tail` did not read fast enough. Next checks: reproduce with `git push 2>&1 | tail -5` on a branch with a code change, and see which process set `O_NONBLOCK` on the descriptor (check `fcntl.fcntl(1, fcntl.F_GETFL)` in the hook's environment)
- **Test gap**: nothing runs the hooks with their output going into a slow pipe
- **Files**: `.pre-commit-config.yaml` (`test-random`), `noxfile.py`
