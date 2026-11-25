"""Source text for test children that wait to be stopped by a signal they handle in Python.

Python runs a signal's handler between bytecodes or when a system call is interrupted. A signal
that lands after its last check and before ``time.sleep`` enters the system call interrupts
nothing, so its handler runs only when the whole sleep ends
(bugs/2026-11-24-probe-test-times-out-on-macos-ci.md: measured 10 of 3,000). A child that handles a
signal therefore waits in short sleeps, which acts on such a signal at the next step.
"""

from __future__ import annotations

# The longest a child waits to be stopped, and the longest one of its sleeps lasts
LONGEST_WAIT_SECONDS = 60
STEP_SECONDS = 0.05

# Statements (the child's own source imports nothing for them)
WAIT_TO_BE_STOPPED = (
    'import time\n'
    f'deadline = time.monotonic() + {LONGEST_WAIT_SECONDS}\n'
    'while time.monotonic() < deadline:\n'
    f'    time.sleep({STEP_SECONDS})\n'
)

# Put before a child's source: its signals are taken by another thread, so the main thread's
# sleep is never interrupted. That is the gap above, every time instead of rarely (POSIX).
SIGNALS_INTERRUPT_NO_SLEEP = (
    'import signal, threading\n'
    'threading.Thread(target=threading.Event().wait, daemon=True).start()\n'
    'signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})\n'
)
