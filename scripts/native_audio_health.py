r"""Is this machine's native audio working, and which failed tests say it was not?

``nox -s compare-drivers`` runs the suite on the native driver (cocoa on macOS). On 2026-11-20
macOS CoreAudio broke under that run twice: once ``pygame.mixer.init`` hung (SDL's audio thread
crashed in AudioQueueNewOutput and pygame-ce's parachute handler spun forever on it, bugs/
2026-11-20-a-crash-on-the-audio-thread-hung-the-process.md, #252; the run hung until it was
killed by hand), once every mixer start failed with ``CoreAudio error
(AudioQueueStart): -66681`` (the run took 7202 s instead of 341 s, and the session blamed 235
tests for "different frames" that really had no audio). Both are this machine's audio, not the
change being pushed. Two commands here keep them from looking like a frame difference:

``probe``
    Reads the plan (``scripts/driver_configurations.py plan``'s plan.json) and, for each
    configuration that would use a native audio driver on this machine (not ``dummy``, not the
    Linux container), opens and closes one pygame mixer at the engine's settings in a child
    process with a time limit. An error or a hang stops the session at once (exit
    ``SERVICE_UNAVAILABLE``) with a message naming it. A configuration with the dummy audio
    driver (Wayland, X11, x11-macos) needs no probe.

``classify``
    Reads the differing tests and the junit reports of the native runs, and prints JSON:
    the tests whose failure carries a mixer-unavailable message (``audio``) and the others
    (``frames``). The session reports the first as audio failures, never as frame differences.

``child`` is the probe's child: it opens and closes the mixer and exits ``SUCCESS``, or exits
``SERVICE_UNAVAILABLE`` with pygame's error on stderr.

Usage:
    uv run python -m scripts.native_audio_health probe --plan plan.json
    uv run python -m scripts.native_audio_health classify --tests-file FILE --junit RUN/junit.xml
"""

from __future__ import annotations

import argparse
import os
import sys
import xml.etree.ElementTree as ET  # ruff: ignore[suspicious-xml-etree-import] — our own pytest's junit.xml, not untrusted input
from pathlib import Path
from typing import TYPE_CHECKING, Final, TextIO

from pydantic import BaseModel, ConfigDict

from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, TimeoutExpired, run_command
from scripts.driver_configurations import DriverPlan

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# The mixer the engine opens (CLAUDE.md, Sound Synthesis: 44100 Hz, signed 16-bit, stereo,
# 512-sample buffer)
MIXER_FREQUENCY: Final = 44100
MIXER_SIZE: Final = -16
MIXER_CHANNELS: Final = 2
MIXER_BUFFER: Final = 512
# A healthy mixer start takes well under a second; a hung mixer start never returns
PROBE_TIMEOUT_SECONDS: Final = 30.0
DUMMY_AUDIO_DRIVER: Final = 'dummy'
# What pygame and SDL say when the audio device could not start, or no mixer is running: the
# texts a failing test carries (junit.xml) when its sound had no device
AUDIO_UNAVAILABLE_MARKERS: Final = ('CoreAudio error', 'mixer not initialized')
RETRY_ADVICE: Final = (
    "This is this machine's audio, not the change being pushed. Run it again; if it keeps "
    'failing, restart the audio daemon (sudo killall coreaudiod).'
)


class AudioProbeResult(BaseModel):
    """What probing one configuration's native audio found."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    configuration: str
    working: bool
    # Why it is not working (empty when it is)
    detail: str = ''


class AudioClassification(BaseModel):
    """The differing tests, split by whether their failure says audio was unavailable."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    audio: tuple[str, ...]
    frames: tuple[str, ...]


def native_audio_configurations(*, plan: DriverPlan) -> list[tuple[str, dict[str, str]]]:
    """Return the planned configurations that would use a native audio driver on this machine.

    Args:
        plan: The plan (plan.json).

    Returns:
        Each such configuration's name and environment: not the dummy audio driver, not run in
        the Linux container (which has its own audio).

    """
    chosen: list[tuple[str, dict[str, str]]] = []
    for configuration in plan.configurations:
        audio_driver = configuration.environment.get('SDL_AUDIODRIVER', DUMMY_AUDIO_DRIVER)
        if configuration.runs_in_linux_container or audio_driver == DUMMY_AUDIO_DRIVER:
            continue
        chosen.append((configuration.name, configuration.environment))
    return chosen


def child_command() -> list[str]:
    """Return the probe child's command line.

    Returns:
        This script's ``child`` command, in this interpreter.

    """
    return [sys.executable, '-m', 'scripts.native_audio_health', 'child']


def probe_native_audio(
    *,
    configuration: str,
    environment: Mapping[str, str],
    timeout_seconds: float = PROBE_TIMEOUT_SECONDS,
    command: Sequence[str] | None = None,
) -> AudioProbeResult:
    """Open and close one native mixer in a child process, with a time limit.

    Args:
        configuration: The configuration's name (for the message).
        environment: The variables its runs set (SDL_AUDIODRIVER), over this process's.
        timeout_seconds: Kill the child after this long: a hung mixer start never returns.
        command: The child's command line (None: ``child_command()``; a test passes a fake).

    Returns:
        The result: working, or why not (the child's error, or the hang).

    """
    try:
        finished = run_command(
            command=child_command() if command is None else command,
            environment={**os.environ, **environment},
            timeout_seconds=timeout_seconds,
            capture_output=OutputCapture.TOGETHER,
        )
    except TimeoutExpired:
        return AudioProbeResult(
            configuration=configuration,
            working=False,
            detail=f'opening the mixer did not return within {timeout_seconds:g} s (it hung)',
        )
    if finished.returncode == ExitCode.SUCCESS:
        return AudioProbeResult(configuration=configuration, working=True)
    return AudioProbeResult(
        configuration=configuration,
        working=False,
        detail=(finished.stdout or '').strip() or f'the probe exited {finished.returncode}',
    )


def failure_texts(*, junit_path: Path) -> dict[str, str]:
    """Return every failed or errored test's failure text in a junit report, by junit key.

    Args:
        junit_path: A pytest ``--junitxml`` file.

    Returns:
        ``classname.name`` to the failure's message and body.

    """
    texts: dict[str, str] = {}
    for case in ET.parse(junit_path).getroot().iter('testcase'):  # ruff: ignore[suspicious-xml-element-tree-usage]
        key = f'{case.get("classname", "")}.{case.get("name", "")}'
        for problem in (*case.findall('failure'), *case.findall('error')):
            texts[key] = f'{texts.get(key, "")}\n{problem.get("message", "")}\n{problem.text or ""}'
    return texts


def junit_key(*, nodeid: str) -> str:
    """Return the junit ``classname.name`` of a pytest node id.

    Args:
        nodeid: e.g. ``tests/test_a.py::TestB::test_c[x/y]``.

    Returns:
        e.g. ``tests.test_a.TestB.test_c[x/y]``: the path and classes dotted, the parameter
        text left as it is.

    """
    head, bracket, parameters = nodeid.partition('[')
    path, _, rest = head.partition('::')
    dotted = path.removesuffix('.py').replace('/', '.')
    if rest:
        dotted = f'{dotted}.{rest.replace("::", ".")}'
    return f'{dotted}{bracket}{parameters}'


def classify_differing_tests(
    *, nodeids: Sequence[str], junit_paths: Sequence[Path]
) -> AudioClassification:
    """Split the differing tests by whether any run's failure says audio was unavailable.

    Args:
        nodeids: The tests found to present different frames.
        junit_paths: The junit reports of the runs on native drivers.

    Returns:
        The audio failures and the remaining (frame) differences, each in the given order.

    """
    texts: dict[str, str] = {}
    for junit_path in junit_paths:
        for key, text in failure_texts(junit_path=junit_path).items():
            texts[key] = f'{texts.get(key, "")}\n{text}'
    audio: list[str] = []
    frames: list[str] = []
    for nodeid in nodeids:
        text = texts.get(junit_key(nodeid=nodeid), '')
        if any(marker in text for marker in AUDIO_UNAVAILABLE_MARKERS):
            audio.append(nodeid)
        else:
            frames.append(nodeid)
    return AudioClassification(audio=tuple(audio), frames=tuple(frames))


def open_and_close_mixer(*, error_output: TextIO) -> ExitCode:
    """Open and close one mixer at the engine's settings (the probe child's work).

    Args:
        error_output: Where pygame's error goes.

    Returns:
        ``SUCCESS``, or ``SERVICE_UNAVAILABLE`` when pygame could not open the mixer.

    """
    import pygame

    try:
        pygame.mixer.init(
            frequency=MIXER_FREQUENCY,
            size=MIXER_SIZE,
            channels=MIXER_CHANNELS,
            buffer=MIXER_BUFFER,
        )
    except pygame.error as error:
        error_output.write(f'pygame.error: {error}\n')
        return ExitCode.SERVICE_UNAVAILABLE
    pygame.mixer.quit()
    return ExitCode.SUCCESS


def run_probe(*, plan_path: Path, log: TextIO) -> ExitCode:
    """Probe every configuration that uses native audio; stop at the first that fails.

    Args:
        plan_path: plan.json.
        log: Where the verdict goes.

    Returns:
        ``SUCCESS`` when every probed mixer opened (or none needed a probe),
        ``SERVICE_UNAVAILABLE`` otherwise.

    """
    plan = DriverPlan.model_validate_json(plan_path.read_text(encoding='utf-8'))
    for configuration, environment in native_audio_configurations(plan=plan):
        result = probe_native_audio(configuration=configuration, environment=environment)
        if not result.working:
            log.write(
                f'{configuration}: native audio is not working: {result.detail}\n{RETRY_ADVICE}\n'
            )
            return ExitCode.SERVICE_UNAVAILABLE
        log.write(f'{configuration}: native audio opens and closes\n')
    return ExitCode.SUCCESS


def run_classify(*, tests_file: Path, junit_paths: Sequence[Path], output: TextIO) -> ExitCode:
    """Print the differing tests split into audio failures and frame differences, as JSON.

    Args:
        tests_file: The differing tests' node ids, one per line.
        junit_paths: The native runs' junit reports.
        output: Where the JSON goes.

    Returns:
        ``SUCCESS``.

    """
    nodeids = [line for line in tests_file.read_text(encoding='utf-8').splitlines() if line]
    classification = classify_differing_tests(nodeids=nodeids, junit_paths=junit_paths)
    output.write(classification.model_dump_json() + '\n')
    return ExitCode.SUCCESS


def argument_parser() -> argparse.ArgumentParser:
    """Return the command line parser.

    Returns:
        The parser.

    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    commands = parser.add_subparsers(dest='command', required=True)
    probe = commands.add_parser('probe', help='open and close a native mixer, with a time limit')
    probe.add_argument('--plan', type=Path, required=True)
    classify = commands.add_parser('classify', help='split differing tests: audio or frames')
    classify.add_argument('--tests-file', type=Path, required=True)
    classify.add_argument('--junit', type=Path, action='append', default=[])
    commands.add_parser('child', help="the probe's child: open and close a mixer")
    return parser


def run(*, arguments: Sequence[str]) -> ExitCode:
    """Run a command: see the module docstring.

    Args:
        arguments: The command line, without the program name.

    Returns:
        The exit code.

    """
    options = argument_parser().parse_args(arguments)
    if options.command == 'probe':
        return run_probe(plan_path=options.plan, log=sys.stderr)
    if options.command == 'classify':
        return run_classify(
            tests_file=options.tests_file, junit_paths=options.junit, output=sys.stdout
        )
    return open_and_close_mixer(error_output=sys.stdout)


def main() -> None:
    """Command line: see the module docstring."""
    os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
    sys.exit(run(arguments=sys.argv[1:]))


if __name__ == '__main__':
    main()
