"""Process exit codes: the exit code alone says who refused the run and why.

``ExitCode`` is shared by the engine (``glitchygames/engine/game_engine.py``;
``glitchygames.engine`` re-exports it, so games and scripts can import it from the engine), the
replay driver and audit (``glitchygames/replay/``) and the sprite API client
(``glitchygames/api/client.py``). Every exit
code is an ``ExitCode`` member; no code or test writes the number itself.

====  ===========================  ============================================================
Code  Member                       Meaning
====  ===========================  ============================================================
0     ``SUCCESS``                  Success; the replay matched; the audit is deterministic
1     ``REPLAY_DIVERGED``          A replay's frames differ from the recording
2     ``ARGUMENT_PARSER_ERROR``    A usage error reported by argparse (the engine never exits with
                                   it itself)
3     ``AUDIT_NONDETERMINISTIC``   ``--audit``'s two runs differ from each other or from the
                                   recording
4     ``GENERATION_REJECTED``      The API server rejected the client's sprite generation (an
                                   error status, or a response that says it failed)
5     ``EXTRACTION_REJECTED``      The API server rejected the client's frame extraction
6     ``AUDIO_DROPOUT_RISK``       ``scripts/audio_glitch_probe.py`` found a risk of audio
                                   dropouts
7     ``REBASELINE_INPUT_LOST``    ``--rebaseline`` wrote the new recording, but the run never
                                   received some of the old one's input (it ended early, or did
                                   not pump a recorded batch): not a faithful re-run
8     ``PROCESSING_SLOWER``        A replay matched, but its processing time exceeded the
                                   recording's by more than ``--max-processing-slowdown``
64    ``OPTIONS_REFUSED``          The engine refuses the options given (a combination it will not
                                   run)
65    ``UNUSABLE_INPUT``           The recording or input data is unusable (another game's
                                   recording, an unsupported format version, a corrupt or
                                   unreadable file, a bad server response)
66    ``MISSING_INPUT``            The input file does not exist
69    ``SERVICE_UNAVAILABLE``      A required service (the API server) cannot be reached
70    ``INTERNAL_ERROR``           An internal error: an uncaught exception during a run (or in
                                   its teardown), or an audit that could not run (a replay child
                                   crashed, timed out or wrote no digests)
73    ``CANNOT_WRITE_OUTPUT``      An output file or directory cannot be created or written
129   ``HANGUP``                   Stopped by SIGHUP (Unix only), after the normal teardown
130   ``INTERRUPTED``              Stopped by SIGINT (Ctrl-C), after the normal teardown
143   ``TERMINATED``               Stopped by SIGTERM, after the normal teardown
149   ``BREAK``                    Stopped by SIGBREAK (Windows only: Ctrl-Break), after the
                                   normal teardown
====  ===========================  ============================================================

The signal members are 128 + the signal number (the shell convention, ``SIGNAL_EXIT_STATUS_BASE``);
``ExitCode.for_signal`` maps a signal to its member. The engine exits with them only once its
teardown has run (recordings closed): SIGINT through KeyboardInterrupt, the others through the
handler ``GameEngine.start`` installs for the run (``exit_on_signal``) wherever nothing else
handles the signal yet. The engine also turns off SDL's own SIGINT/SIGTERM handler
(``SDL_NO_SIGNAL_HANDLERS``), which would turn them into QUIT events. Not wired: SIGKILL and
SIGSTOP (they cannot be caught), SIGPIPE (Python ignores it) and SIGQUIT (it keeps its core-dump
convention); a process they stop exits as the system decides.

An exception raised before ``GameEngine.start()`` (in ``GameEngine.__init__``, or a game's own
code around it) is not mapped: each game has its own entry point (``GameEngine(game=...)
.start()`` in its ``main``), so there is no single place to wrap, and Python exits with its
default 1 and a traceback. The engine's tools are mapped as a run is, on both front ends: a tool
given as a game flag and a ``glitchygames`` subcommand each run inside
``game_engine.run_inside_tool_crash_boundary``. The command reports a child game killed by
signal N as 128 + N (``shell_exit_status``), as a shell does, not as Python's 256 - N.

Every code has exactly one name. The engine's own failed checks (1, 3-6) avoid 2
(argparse's), 64-78 (``sysexits.h``) and 126 and up (the shell's and signal exits).

The codes 0, 64-70 and 73 have the values of BSD ``sysexits.h``, which Python exposes as
``os.EX_OK``, ``os.EX_USAGE`` and so on. They are defined here rather than read from ``os``
because the ``os.EX_*`` names exist only on Unix, and the engine runs on Windows too;
``tests/test_exit_codes.py`` checks that the values agree wherever ``os`` has them.

A file that exists but cannot be read (no permission, a directory, not gzip) is unusable input
(65), not missing input (66): only a file that does not exist is 66.

This module is a leaf: it imports nothing from the engine, so anything may import it.
"""

from __future__ import annotations

import enum

# Stopped by signal N: the process exits with this plus N (the shell convention)
SIGNAL_EXIT_STATUS_BASE = 128


class ExitCode(enum.IntEnum):
    """The process exit codes of the engine, the replay tools and the API client."""

    # Success; the replay matched; the audit is deterministic. Same value as Python's os.EX_OK
    # (sysexits.h EX_OK)
    SUCCESS = 0

    # A replay's frames differ from the recording
    REPLAY_DIVERGED = 1

    # argparse's own status for a usage error. The engine never exits with it: it is named for
    # callers and tests that tell argparse's refusals from the engine's
    ARGUMENT_PARSER_ERROR = 2

    # --audit's two replay runs differ from each other or from the recording
    AUDIT_NONDETERMINISTIC = 3

    # The API server rejected the client's sprite generation (an error status, or a response that
    # says it failed)
    GENERATION_REJECTED = 4

    # The API server rejected the client's frame extraction (an error status, or a response that
    # says it failed)
    EXTRACTION_REJECTED = 5

    # scripts/audio_glitch_probe.py found a risk of audio dropouts
    AUDIO_DROPOUT_RISK = 6

    # --rebaseline wrote the new recording, but the run never received some of the old one's
    # input (glitchygames/replay/rebaseline.py, rule 2)
    REBASELINE_INPUT_LOST = 7

    # A replay matched, but took longer to process than --max-processing-slowdown allows; see
    # glitchygames/replay/processing.py
    PROCESSING_SLOWER = 8

    # The engine refuses the options given (a combination it will not run). Same value as
    # Python's os.EX_USAGE (sysexits.h EX_USAGE)
    OPTIONS_REFUSED = 64

    # The recording or input data is unusable. Same value as Python's os.EX_DATAERR (sysexits.h
    # EX_DATAERR)
    UNUSABLE_INPUT = 65

    # The input file does not exist. Same value as Python's os.EX_NOINPUT (sysexits.h EX_NOINPUT)
    MISSING_INPUT = 66

    # A required service (the API server) cannot be reached. Same value as Python's
    # os.EX_UNAVAILABLE (sysexits.h EX_UNAVAILABLE)
    SERVICE_UNAVAILABLE = 69

    # An uncaught exception during a run, or an audit that could not run. Same value as Python's
    # os.EX_SOFTWARE (sysexits.h EX_SOFTWARE)
    INTERNAL_ERROR = 70

    # An output file or directory cannot be created or written. Same value as Python's
    # os.EX_CANTCREAT (sysexits.h EX_CANTCREAT)
    CANNOT_WRITE_OUTPUT = 73

    # Stopped by SIGHUP (Unix only): 128 + signal.SIGHUP
    HANGUP = 129

    # Stopped by SIGINT (Ctrl-C): 128 + signal.SIGINT
    INTERRUPTED = 130

    # Stopped by SIGTERM: 128 + signal.SIGTERM
    TERMINATED = 143

    # Stopped by SIGBREAK (Windows only: Ctrl-Break): 128 + signal.SIGBREAK
    BREAK = 149

    @classmethod
    def for_signal(cls, signal_number: int) -> ExitCode:
        """Return the member a run stopped by a signal exits with.

        Args:
            signal_number: The signal (``signal.SIGTERM`` and so on).

        Returns:
            ``HANGUP``, ``INTERRUPTED``, ``TERMINATED`` or ``BREAK``.

        Raises:
            ValueError: For a signal the engine does not wire (see the module docstring), rather
                than a number with no name.

        """
        message = f'signal {signal_number} has no exit code: the engine does not handle it'
        if signal_number <= 0:
            raise ValueError(message)
        try:
            return cls(SIGNAL_EXIT_STATUS_BASE + signal_number)
        except ValueError as error:
            raise ValueError(message) from error

    def describe(self) -> str:
        """Return the code's name and number, as logs show it.

        ``str()`` of an IntEnum member is only its number (Python 3.11 on).

        Returns:
            For example ``'OPTIONS_REFUSED (64)'``.

        """
        return f'{self.name} ({self.value})'

    @classmethod
    def describe_status(cls, status: int) -> str:
        """Describe any process exit status: a member, a signal exit, or an unknown number.

        Args:
            status: A process's exit status (a child's ``returncode``).

        Returns:
            ``'INTERNAL_ERROR (70)'`` for a member; for a signal, ``'signal 6 (134)'`` (128 + the
            signal number, as a shell reports it) or, for a process killed by the signal (a
            subprocess reports -N), ``'TERMINATED (signal 15)'`` where the signal has a member and
            ``'signal 6'`` otherwise; any other number alone.

        """
        if status < 0:
            signal_number = -status
            try:
                return f'{cls.for_signal(signal_number).name} (signal {signal_number})'
            except ValueError:
                return f'signal {signal_number}'
        try:
            return cls(status).describe()
        except ValueError:
            pass
        if status > SIGNAL_EXIT_STATUS_BASE:
            return f'signal {status - SIGNAL_EXIT_STATUS_BASE} ({status})'
        return str(status)


def shell_exit_status(*, returncode: int) -> int:
    """Return a child's exit status as a shell reports it, for this process to exit with.

    ``subprocess`` reports a child killed by signal N as ``-N``; exiting with that
    (``sys.exit(-9)``) would end this process with 256 - N (247), a code nobody documents. A
    shell reports it as 128 + N (137), which this returns, as for the game run alone.

    Args:
        returncode: The child's ``returncode``.

    Returns:
        ``SIGNAL_EXIT_STATUS_BASE`` + N for a child killed by signal N; otherwise ``returncode``.

    """
    if returncode < 0:
        return SIGNAL_EXIT_STATUS_BASE - returncode
    return returncode
