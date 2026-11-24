"""Log who signals whom, in every Python process of a run: the process-stop triage's probe.

Put this folder first on ``PYTHONPATH`` and name a log file in ``PROCESS_STOP_PROBE_LOG``; Python
imports ``sitecustomize`` at start-up, so every Python process the run starts (the outer pytest,
its xdist workers, a test's nested pytest run, ``glitchygames record-trace`` and its game) then
appends one JSON line per event to that file:

- ``start``: the process's pid, parent, process group, session and command line;
- ``send``: an ``os.kill`` or ``os.killpg`` call (``subprocess``'s ``send_signal``, ``kill`` and
  ``terminate`` go through ``os.kill``), logged before the call, with the sender, its target,
  the signal and where in the code it was called; ``send-failed`` when the call raised;
- ``handler``: a ``signal.signal`` call, with the handler installed;
- ``receive``: a Python-level handler called for a signal (a signal whose action is the default
  kills or stops the process with no Python code running, so it shows only as the process's
  ``exit`` missing);
- ``exit``: a normal interpreter exit (``atexit``; a process killed by a signal has none).

A Python signal handler isn't told who sent the signal, so the senders are read from the ``send``
events instead: every process that can send one is a Python process of the run. Each line is one
``os.write`` to a descriptor opened with ``O_APPEND``, so lines from many processes never mix.
Without ``PROCESS_STOP_PROBE_LOG`` it does nothing. Used by
``scripts/reproduce_process_stop_under_load.py``
(bugs/2026-11-20-process-stop-tests-failed-under-load.md).
"""

from __future__ import annotations

import atexit
import json
import os
import signal
import sys
import time
import traceback
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import FrameType

    # What signal.signal takes and returns (typeshed's _HANDLER; signal.Handlers is an int)
    type SignalHandler = Callable[[int, FrameType | None], Any] | int | None

PROBE_LOG_VARIABLE = 'PROCESS_STOP_PROBE_LOG'
# How many frames of the caller's stack a send event keeps (innermost last)
SENDER_STACK_DEPTH = 6
# How many command-line words a start event keeps
COMMAND_WORDS = 12


def _install(*, log_path: str) -> None:
    """Wrap the signal functions and log this process's start and exit.

    Args:
        log_path: The file every process of the run appends its events to.

    """
    descriptor = os.open(log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)

    def record(kind: str, **fields: Any) -> None:
        event = {'time': time.time(), 'kind': kind, 'pid': os.getpid(), **fields}
        os.write(descriptor, (json.dumps(event, default=repr) + '\n').encode())

    def caller() -> list[str]:
        frames = traceback.extract_stack()[:-2][-SENDER_STACK_DEPTH:]
        return [f'{frame.filename}:{frame.lineno} {frame.name}' for frame in frames]

    original_kill = os.kill
    original_killpg = os.killpg
    original_signal = signal.signal

    def kill(pid: int, signal_number: int, /) -> None:
        # Logged before the call, so the send is never after the receipt it caused
        record('send', call='kill', target=pid, signal=signal_number, stack=caller())
        try:
            original_kill(pid, signal_number)
        except OSError as error:
            record('send-failed', call='kill', target=pid, error=type(error).__name__)
            raise

    def killpg(group: int, signal_number: int, /) -> None:
        record('send', call='killpg', target=group, signal=signal_number, stack=caller())
        try:
            original_killpg(group, signal_number)
        except OSError as error:
            record('send-failed', call='killpg', target=group, error=type(error).__name__)
            raise

    def install_handler(signal_number: int, handler: SignalHandler, /) -> SignalHandler:
        record('handler', signal=int(signal_number), handler=repr(handler))
        if not callable(handler):
            return original_signal(signal_number, handler)
        inner = handler

        def logged(received: int, frame: FrameType | None, /) -> object:
            record('receive', signal=received, handler=repr(inner))
            return inner(received, frame)

        return original_signal(signal_number, logged)

    # Through the modules' namespaces: a type checker reads a plain assignment as replacing a
    # function with another of a different declared type, which this deliberately does
    os.__dict__['kill'] = kill
    os.__dict__['killpg'] = killpg
    signal.__dict__['signal'] = install_handler
    record(
        'start',
        parent=os.getppid(),
        group=os.getpgrp(),
        session=os.getsid(0),
        # orig_argv: sys.argv holds only '-c' or '-m' while site runs
        command=sys.orig_argv[:COMMAND_WORDS],
    )
    atexit.register(lambda: record('exit'))


if sys.platform != 'win32' and os.environ.get(PROBE_LOG_VARIABLE):
    _install(log_path=os.environ[PROBE_LOG_VARIABLE])
