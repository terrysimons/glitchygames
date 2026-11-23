r"""Measure a game's frames in a real browser: build it with the frame probe, run it in Chrome.

It builds the game's browser bundle (scripts/build_browser_bundle.py) with the frame-phase probe
(scripts/frame_phase_probe.py) copied in and switched on in boot_config.json, serves it on
localhost, starts Chrome (headless unless ``--headed``) with a throwaway profile, and drives it
over the DevTools protocol: it loads the page, clicks the start overlay once the game is ready,
collects the probe's report from the console, and prints a summary. ``--trace`` also records a
Chrome performance trace of the measured run (open it in DevTools' Performance panel), which
shows what happens outside Python: canvas copies, the browser's own garbage collection, frames
the compositor dropped.

The report (``--output``, default build/browser-measure/<game>/report.json) holds the probe's
whole JSON: the environment, the surface audit, the summary and one row per frame.

Usage:
    uv run python -m scripts.measure_browser_frames zombies-aint-my-neighbors
    uv run python -m scripts.measure_browser_frames zombies-aint-my-neighbors --seconds 15 \
        --trace build/browser-measure/title-trace.json -- --crt-power-on off

Headless Chrome paces animation frames itself and draws in software, so compare runs with each
other (before and after a change), not with a player's browser; ``--headed`` uses a real window.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import itertools
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Final

import websockets
from pydantic import BaseModel, ConfigDict

from glitchygames.process import ErrorOutput, start_command, stop_command
from scripts import frame_phase_probe
from scripts.build_browser_bundle import (
    GAMES,
    PYGAME_CE_DIRECTORY,
    REPOSITORY_DIRECTORY,
    WHEEL_OUTPUT_DIRECTORY_NAME,
    bind_server,
    build_wheel,
    report,
    reusable_wheel,
    submodule_commit,
    write_bundle,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from websockets.asyncio.client import ClientConnection

# Where Chrome is looked for when --chrome is not given, in order
CHROME_CANDIDATES: Final = (
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    'google-chrome',
    'google-chrome-stable',
    'chromium',
    'chromium-browser',
)
# The line Chrome writes to standard error once DevTools listens (--remote-debugging-port=0)
DEVTOOLS_LISTENING_PATTERN: Final = re.compile(r'DevTools listening on ws://[^:/]+:(?P<port>\d+)/')
# What boot.py's status line ends with once the game waits for the player's click
READY_TEXT: Final = ': click to play'
# The start overlay's middle in page coordinates, or null while it is hidden
OVERLAY_MIDDLE_EXPRESSION: Final = (
    "(() => { const overlay = document.getElementById('start-overlay');"
    " if (!overlay || getComputedStyle(overlay).display === 'none') return null;"
    ' const box = overlay.getBoundingClientRect();'
    ' return [box.x + box.width / 2, box.y + box.height / 2]; })()'
)
# What the trace records: the timeline (tasks, frames, paints), V8 and its garbage collection
TRACE_CATEGORIES: Final = (
    'devtools.timeline',
    'disabled-by-default-devtools.timeline',
    'disabled-by-default-devtools.timeline.frame',
    'v8',
    'v8.execute',
    'disabled-by-default-v8.gc',
    'blink',
    'cc',
    'gpu',
)
# The scene each game's measurement waits for by default (its first scene class)
DEFAULT_SCENES: Final = {'zombies-aint-my-neighbors': 'TitleScene'}


def find_chrome(*, candidates: Sequence[str] = CHROME_CANDIDATES) -> str | None:
    """Return the first Chrome or Chromium found: a path that exists or a name on PATH.

    Returns:
        Its path, or None when none is installed.

    """
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
        found = shutil.which(candidate)
        if found is not None:
            return found
    return None


def console_text(*, event_parameters: dict[str, Any]) -> str:
    """Return a ``Runtime.consoleAPICalled`` event's text: its arguments' values, spaced.

    Returns:
        The text (an argument without a value, such as an object, shows its description).

    """
    return ' '.join(
        str(argument.get('value', argument.get('description', '')))
        for argument in event_parameters.get('args', [])
    )


def report_from_console(*, text: str) -> dict[str, Any] | None:
    """Return the probe's report when a console line is its report line.

    Returns:
        The parsed report, or None for any other line.

    """
    if not text.startswith(frame_phase_probe.REPORT_MARKER):
        return None
    return json.loads(text[len(frame_phase_probe.REPORT_MARKER) :])


def milliseconds(seconds: float) -> str:
    """Return seconds as milliseconds with three decimals (the summary's unit).

    Returns:
        The text.

    """
    return f'{seconds * 1000:.3f}'


def summary_lines(*, report_data: dict[str, Any]) -> list[str]:
    """Return the report's summary as text lines: environment, surfaces, phases, hitches.

    Returns:
        The lines.

    """
    summary = report_data['summary']
    audit: dict[str, Any] = report_data.get('surface_audit') or {}
    lines = [
        f'Environment: {report_data["environment"]}',
        f'Display: {audit.get("display")}',
        *(
            f'  sprite {sprite["name"]}: dirty={sprite["dirty"]} visible={sprite["visible"]} '
            f'size={sprite["format"]["size"]} bitsize={sprite["format"]["bitsize"]} '
            f'per_pixel_alpha={sprite["format"]["per_pixel_alpha"]} '
            f'matches_display={sprite["matches_display"]}'
            for sprite in audit.get('sprites', [])
        ),
        f'Frames measured: {summary["frames"]}',
        '                         median      p95      p99      max  (ms)',
    ]
    rows = [
        ('frame', summary['frame_seconds']),
        ('interval', summary['interval_seconds']),
        *summary['phase_seconds'].items(),
        ('gc pause', summary['gc_pause_seconds']),
    ]
    lines.extend(
        f'  {name:22} '
        + ' '.join(f'{milliseconds(values[key]):>8}' for key in ('median', 'p95', 'p99', 'max'))
        for name, values in rows
    )
    lines.append(
        f'Dirty rects per frame: median {summary["rects"]["count"]["median"]}, '
        f'area median {summary["rects"]["area"]["median"]} pixels; '
        f'sprites blitted per frame: median {summary["sprites_blitted"]["median"]}'
    )
    hitches = summary['hitches']
    lines.append(f'Hitches (interval > {frame_phase_probe.HITCH_FACTOR}x median): {len(hitches)}')
    lines.extend(
        f'  game_time={hitch["game_time"]:.3f} interval={milliseconds(hitch["interval"])} '
        f'frame={milliseconds(hitch["frame"])} slowest={hitch["slowest_phase"]} '
        f'({milliseconds(hitch["slowest_phase_seconds"])}) gc={milliseconds(hitch["gc_seconds"])}'
        for hitch in hitches
    )
    return lines


class DevToolsSession:
    """One DevTools protocol connection to a page: commands answered by id, events queued."""

    def __init__(self, *, connection: ClientConnection) -> None:
        """Wrap an open connection (``run`` reads it).

        Args:
            connection: The page target's WebSocket.

        """
        self.connection = connection
        self.events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._ids = itertools.count(1)

    async def run(self) -> None:
        """Read messages until the connection closes: answers to their commands, events queued."""
        async for raw_message in self.connection:
            message = json.loads(raw_message)
            pending = self._pending.pop(message.get('id', 0), None)
            if pending is not None:
                if 'error' in message:
                    pending.set_exception(RuntimeError(f'DevTools error: {message["error"]}'))
                else:
                    pending.set_result(message.get('result', {}))
            else:
                await self.events.put(message)

    async def send(self, method: str, **parameters: object) -> dict[str, Any]:
        """Send a command and wait for its answer.

        Returns:
            The command's result.

        """
        command_id = next(self._ids)
        answer: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[command_id] = answer
        await self.connection.send(
            json.dumps({'id': command_id, 'method': method, 'params': parameters})
        )
        return await answer

    async def evaluate(self, expression: str) -> object:
        """Evaluate JavaScript in the page.

        Returns:
            Its value (by value: JSON-ready values only).

        """
        result = await self.send('Runtime.evaluate', expression=expression, returnByValue=True)
        return result.get('result', {}).get('value')


async def click_start_overlay(*, session: DevToolsSession) -> None:
    """Click the middle of the page's start overlay (a real mouse click, as a player's).

    Called once boot.py says the game waits for a click (``READY_TEXT`` on the console):
    boot.py shows the overlay and listens for the click before it next yields to the page.

    Raises:
        RuntimeError: When the overlay is not showing.

    """
    middle = await session.evaluate(OVERLAY_MIDDLE_EXPRESSION)
    match middle:
        case [int() | float() as x, int() | float() as y]:
            pass
        case _:
            message = f'The start overlay is not showing (the page answered {middle!r})'
            raise RuntimeError(message)
    for event_type in ('mousePressed', 'mouseReleased'):
        await session.send(
            'Input.dispatchMouseEvent', type=event_type, x=x, y=y, button='left', clickCount=1
        )


async def save_trace(*, session: DevToolsSession, path: Path) -> None:
    """End the trace started at the page load and write it to ``path`` (DevTools' JSON)."""
    await session.send('Tracing.end')
    while True:
        event = await session.events.get()
        if event.get('method') == 'Tracing.tracingComplete':
            stream = event['params']['stream']
            break
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as trace_file:
        while True:
            chunk = await session.send('IO.read', handle=stream)
            trace_file.write(chunk.get('data', ''))
            if chunk.get('eof'):
                break
    await session.send('IO.close', handle=stream)


async def measure_page(
    *,
    devtools_port: int,
    url: str,
    trace_path: Path | None,
    echo_console: bool,
) -> dict[str, Any]:
    """Load ``url`` in Chrome's page target, start the game, and wait for the probe's report.

    The caller bounds the wait (``asyncio.timeout``).

    Returns:
        The report.

    Raises:
        RuntimeError: When Chrome has no page target.

    """
    targets = await asyncio.to_thread(devtools_targets, devtools_port=devtools_port)
    page = next((target for target in targets if target.get('type') == 'page'), None)
    if page is None:
        message = 'Chrome has no page target'
        raise RuntimeError(message)
    async with websockets.connect(page['webSocketDebuggerUrl'], max_size=None) as connection:
        session = DevToolsSession(connection=connection)
        reader = asyncio.create_task(session.run())
        try:
            await session.send('Runtime.enable')
            await session.send('Page.enable')
            if trace_path is not None:
                await session.send(
                    'Tracing.start',
                    transferMode='ReturnAsStream',
                    traceConfig={'includedCategories': list(TRACE_CATEGORIES)},
                )
            await session.send('Page.navigate', url=url)
            report_data = await run_until_report(session=session, echo_console=echo_console)
            if trace_path is not None:
                await save_trace(session=session, path=trace_path)
            return report_data
        finally:
            reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reader


def devtools_targets(*, devtools_port: int) -> list[dict[str, Any]]:
    """Return Chrome's DevTools targets (its tabs and workers), from its local HTTP endpoint.

    Returns:
        The targets.

    """
    url = f'http://127.0.0.1:{devtools_port}/json/list'
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())


async def run_until_report(*, session: DevToolsSession, echo_console: bool) -> dict[str, Any]:
    """Read page events: click the start overlay when the game is ready, return the report.

    Returns:
        The report.

    Raises:
        RuntimeError: When the page throws an uncaught exception first.

    """
    while True:
        event = await session.events.get()
        method = event.get('method')
        if method == 'Runtime.exceptionThrown':
            details = event['params']['exceptionDetails']
            message = f'The page threw: {details.get("exception", {}).get("description", details)}'
            raise RuntimeError(message)
        if method != 'Runtime.consoleAPICalled':
            continue
        text = console_text(event_parameters=event['params'])
        report_data = report_from_console(text=text)
        if report_data is not None:
            return report_data
        if echo_console:
            report(f'console: {text[:300]}')
        if text.endswith(READY_TEXT):
            await click_start_overlay(session=session)


def chrome_command(*, chrome: str, profile_directory: Path, headed: bool) -> list[str]:
    """Return Chrome's command line: its own profile, DevTools on a port it picks, a blank page.

    Audio may start without a click (the measurement clicks anyway, as a player does).

    Returns:
        The command.

    """
    return [
        chrome,
        *([] if headed else ['--headless=new']),
        '--remote-debugging-port=0',
        f'--user-data-dir={profile_directory}',
        '--no-first-run',
        '--no-default-browser-check',
        '--autoplay-policy=no-user-gesture-required',
        '--window-size=1024,768',
        'about:blank',
    ]


def devtools_port_from_line(*, line: str) -> int | None:
    """Return the port in Chrome's ``DevTools listening on ws://127.0.0.1:PORT/...`` line.

    Returns:
        The port, or None for any other line.

    """
    found = DEVTOOLS_LISTENING_PATTERN.search(line)
    return None if found is None else int(found.group('port'))


def read_devtools_port(*, chrome_errors: IO[str]) -> int:
    """Read Chrome's standard error until it says where DevTools listens; keep draining it.

    Chrome's standard error is a pipe: once the port is found, a daemon thread keeps reading
    it, so Chrome never blocks on a full pipe.

    Returns:
        The port.

    Raises:
        RuntimeError: When Chrome exits (its standard error ends) before saying.

    """
    for line in chrome_errors:
        port = devtools_port_from_line(line=line)
        if port is not None:
            threading.Thread(target=chrome_errors.read, daemon=True).start()
            return port
    message = 'Chrome exited before its DevTools listened'
    raise RuntimeError(message)


def resolve_wheel() -> Path:
    """Return the pygame-ce wheel for the submodule's commit, building it when none is current.

    Returns:
        The wheel's path.

    """
    commit = submodule_commit(pygame_ce_directory=PYGAME_CE_DIRECTORY)
    wheel = reusable_wheel(
        wheel_directory=PYGAME_CE_DIRECTORY / WHEEL_OUTPUT_DIRECTORY_NAME, commit=commit
    )
    if wheel is None:
        report(f'Building the pygame-ce wheel for {commit[:9]} (several minutes the first time)')
        wheel = build_wheel(pygame_ce_directory=PYGAME_CE_DIRECTORY)
    return wheel


def write_measurement_bundle(
    *,
    game: str,
    output_directory: Path,
    game_arguments: list[str],
    probe_settings: dict[str, object],
) -> None:
    """Write the game's bundle with the probe beside boot.py and switched on in its config."""
    write_bundle(
        game=game,
        output_directory=output_directory,
        wheel_path=resolve_wheel(),
        arguments=game_arguments,
    )
    shutil.copy2(Path(frame_phase_probe.__file__), output_directory / 'frame_phase_probe.py')
    config_path = output_directory / 'boot_config.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    config['frame_probe'] = probe_settings
    config_path.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    add_probe_to_pyscript_files(pyscript_path=output_directory / 'pyscript.toml')


def add_probe_to_pyscript_files(*, pyscript_path: Path) -> None:
    """List the probe in pyscript.toml's ``[files]``, so PyScript fetches it beside boot.py.

    Raises:
        RuntimeError: When pyscript.toml has no ``[files]`` table (the bundle's format changed).

    """
    text = pyscript_path.read_text(encoding='utf-8')
    marker = '[files]\n'
    if marker not in text:
        message = f'{pyscript_path} has no [files] table to add the probe to'
        raise RuntimeError(message)
    entry = '"./frame_phase_probe.py" = "./frame_phase_probe.py"\n'
    pyscript_path.write_text(text.replace(marker, marker + entry, 1), encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    """Build, serve and measure; print the summary and write the report.

    Returns:
        0 with a report; 1 when Chrome is missing or the measurement failed.

    """
    parser = argparse.ArgumentParser(description="Measure a game's frames in Chrome.")
    parser.add_argument('game', choices=sorted(GAMES))
    parser.add_argument('--seconds', type=float, default=10.0, help='how long to measure')
    parser.add_argument('--warmup', type=float, default=2.0, help='scene seconds before measuring')
    parser.add_argument(
        '--scene', default=None, help="measure only this scene class (default: the game's first)"
    )
    parser.add_argument('--output', type=Path, default=None, help='the report JSON')
    parser.add_argument('--trace', type=Path, default=None, help='also save a Chrome trace here')
    parser.add_argument('--chrome', default=None, help='the Chrome or Chromium binary')
    parser.add_argument('--headed', action='store_true', help='use a visible browser window')
    parser.add_argument(
        '--timeout', type=float, default=240.0, help='seconds for the page to load and report'
    )
    parser.add_argument('--echo-console', action='store_true', help="print the page's console")
    parser.add_argument('game_arguments', nargs='*', help='after --: the game command line')
    arguments = parser.parse_args(argv)
    chrome = arguments.chrome or find_chrome()
    if chrome is None:
        report('No Chrome or Chromium found: pass --chrome')
        return 1
    measure_directory = REPOSITORY_DIRECTORY / 'build' / 'browser-measure' / arguments.game
    output_path = arguments.output or measure_directory / 'report.json'
    bundle_directory = measure_directory / 'site'
    write_measurement_bundle(
        game=arguments.game,
        output_directory=bundle_directory,
        game_arguments=arguments.game_arguments,
        probe_settings={
            'measure_seconds': arguments.seconds,
            'warmup_seconds': arguments.warmup,
            'scene_name': arguments.scene or DEFAULT_SCENES.get(arguments.game),
        },
    )
    server = bind_server(directory=bundle_directory, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_address[1]}/'
    report(f'Serving {bundle_directory} at {url}')
    try:
        report_data = run_chrome(
            run=ChromeRun(
                chrome=chrome,
                url=url,
                headed=arguments.headed,
                timeout_seconds=arguments.timeout,
                trace_path=arguments.trace,
                echo_console=arguments.echo_console,
            )
        )
    except (TimeoutError, RuntimeError) as error:
        report(f'Measurement failed: {error!r}')
        return 1
    finally:
        server.shutdown()
        server.server_close()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report_data, indent=2) + '\n', encoding='utf-8')
    for line in summary_lines(report_data=report_data):
        report(line)
    report(f'Report: {output_path}')
    if arguments.trace is not None:
        report(f'Chrome trace: {arguments.trace} (DevTools > Performance > Load profile)')
    return 0


class ChromeRun(BaseModel):
    """One measurement in Chrome: the browser, the page, and how to watch it."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    # The Chrome or Chromium binary
    chrome: str
    # The served bundle's page
    url: str
    # True for a visible window; False runs headless
    headed: bool
    # The bound on starting Chrome, loading the page and the probe's report, in seconds
    timeout_seconds: float
    # Where to save a Chrome performance trace of the run (None: no trace)
    trace_path: Path | None
    # Whether the page's console lines are printed as they come
    echo_console: bool


def run_chrome(*, run: ChromeRun) -> dict[str, Any]:
    """Start Chrome with a throwaway profile, measure the page, and stop Chrome's whole group.

    Returns:
        The probe's report.

    Raises:
        RuntimeError: When Chrome starts without a standard error pipe.

    """
    # Chrome, with the arguments built here (no shell), leading a session of its own so
    # stop_command ends its helper processes with it; its standard error, where it prints its
    # DevTools address, is piped, and its standard output discarded. Leaving the process's
    # context closes that pipe, after stop_command has reaped Chrome.
    with (
        tempfile.TemporaryDirectory(prefix='measure-browser-chrome-') as profile,
        Path(os.devnull).open('w', encoding='utf-8') as discarded,
        start_command(
            command=chrome_command(
                chrome=run.chrome, profile_directory=Path(profile), headed=run.headed
            ),
            environment=os.environ,
            output=discarded,
            errors=ErrorOutput.PIPED,
        ) as chrome_process,
    ):
        try:
            if chrome_process.stderr is None:  # pragma: no cover - errors=PIPED always gives one
                message = 'Chrome was started without a standard error pipe'
                raise RuntimeError(message)
            return asyncio.run(measure_with_chrome(chrome_errors=chrome_process.stderr, run=run))
        finally:
            stop_command(process=chrome_process)


async def measure_with_chrome(*, chrome_errors: IO[str], run: ChromeRun) -> dict[str, Any]:
    """Wait for Chrome's DevTools, then measure the page, all within ``run.timeout_seconds``.

    Returns:
        The probe's report.

    """
    async with asyncio.timeout(run.timeout_seconds):
        devtools_port = await asyncio.to_thread(read_devtools_port, chrome_errors=chrome_errors)
        return await measure_page(
            devtools_port=devtools_port,
            url=run.url,
            trace_path=run.trace_path,
            echo_console=run.echo_console,
        )


if __name__ == '__main__':
    sys.exit(main())
