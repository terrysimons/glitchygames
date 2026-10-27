r"""The SDL driver configurations ``nox -s compare-drivers`` runs the suite on; which run here.

A configuration is a video driver plus where and how the suite runs on it:

- ``dummy``: SDL's windowless driver, every platform (the baseline every other is compared with);
- ``cocoa`` (macOS), ``windows`` (Windows), ``wayland`` and ``x11`` (Linux, by WAYLAND_DISPLAY or
  DISPLAY): the platform's own driver, as tests/driver_comparison.py runs it;
- ``x11-macos``: x11 on this Mac, drawing on XQuartz, through an SDL built with x11
  (scripts/build_sdl_x11.py) that ``SDL_DYNAMIC_API`` loads in place of the wheel's SDL;
- ``x11-linux``: x11 in the Linux container of ``nox -s test-linux-x11`` (Docker), its windows
  forwarded over TCP to this Mac's XQuartz.

``plan`` probes the machine (``MachineFacts``: platform, displays, the Docker daemon, XQuartz,
the build tools), keeps the requested configurations (``--drivers a,b``; default: every one
available here), builds SDL with x11 when ``x11-macos`` is kept, and writes a ``DriverPlan``
(each configuration's SDL environment, whether XQuartz is needed, why the others cannot run) as
JSON for the noxfile, which runs the suite on each. ``dummy`` is always first: it is the
baseline. A configuration asked for that cannot run here is refused with the reason.

Usage:
    uv run python -m scripts.driver_configurations plan --output plan.json \\
        [--drivers dummy,cocoa,x11-macos,x11-linux]

Exit codes: ``SUCCESS``; ``OPTIONS_REFUSED`` for an unknown or unavailable configuration;
``INTERNAL_ERROR`` when SDL with x11 cannot be built.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from pydantic import BaseModel, ConfigDict

from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, TimeoutExpired, run_command
from scripts.build_sdl_x11 import (
    X11_PREFIX,
    BuildError,
    SdlX11Build,
    default_cache_root,
    ensure_built,
    make_jobs,
    say,
    wheel_sdl_version,
    x11_environment,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

DUMMY = 'dummy'
COCOA = 'cocoa'
WINDOWS = 'windows'
WAYLAND = 'wayland'
X11 = 'x11'
X11_MACOS = 'x11-macos'
X11_LINUX = 'x11-linux'
DRIVERS_SEPARATOR = ','
DOCKER_CHECK_TIMEOUT_SECONDS = 30.0


class DriverConfiguration(BaseModel):
    """One way to run the suite: a video driver, its audio driver and where it runs."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    name: str
    description: str
    video_driver: str
    audio_driver: str
    # Runs in the Linux X11 container (nox's test-linux-x11 machinery), not on this machine
    runs_in_linux_container: bool = False
    # Runs through SDL built with x11 (scripts/build_sdl_x11.py), loaded by SDL_DYNAMIC_API
    uses_sdl_x11_build: bool = False
    # Draws on XQuartz (started and waited for before the runs)
    needs_xquartz: bool = False
    # More environment variables for its runs
    extra_environment: dict[str, str] = {}


# Every configuration, in the matrix's column order (the baseline first)
CONFIGURATIONS = (
    DriverConfiguration(
        name=DUMMY,
        description="SDL's windowless driver (the baseline)",
        video_driver=DUMMY,
        audio_driver=DUMMY,
    ),
    DriverConfiguration(
        name=COCOA,
        description='macOS native',
        video_driver=COCOA,
        audio_driver='coreaudio',
        # Its windows must not take keyboard focus from the person typing
        extra_environment={'SDL_MAC_BACKGROUND_APP': '1'},
    ),
    DriverConfiguration(
        name=WINDOWS, description='Windows native', video_driver=WINDOWS, audio_driver='wasapi'
    ),
    DriverConfiguration(
        name=WAYLAND, description='Linux Wayland', video_driver=WAYLAND, audio_driver=DUMMY
    ),
    DriverConfiguration(
        name=X11, description='Linux X11 (native)', video_driver=X11, audio_driver=DUMMY
    ),
    DriverConfiguration(
        name=X11_MACOS,
        description='x11 on macOS, drawing on XQuartz (SDL built with x11)',
        video_driver=X11,
        audio_driver=DUMMY,
        uses_sdl_x11_build=True,
        needs_xquartz=True,
    ),
    DriverConfiguration(
        name=X11_LINUX,
        description="x11 in Docker's Linux container, forwarded to XQuartz over TCP",
        video_driver=X11,
        audio_driver=DUMMY,
        runs_in_linux_container=True,
        needs_xquartz=True,
    ),
)
CONFIGURATIONS_BY_NAME = {configuration.name: configuration for configuration in CONFIGURATIONS}


class SelectionError(ValueError):
    """A requested configuration is unknown or cannot run here."""


class MachineFacts(BaseModel):
    """What this machine offers the configurations."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    platform: str
    wayland_display: bool
    x_display: bool
    docker_running: bool
    xquartz_installed: bool
    # A C compiler, make and XQuartz's X11 headers (to build SDL with x11)
    build_tools: bool


class Availability(BaseModel):
    """Whether a configuration can run here, and why not."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    name: str
    available: bool
    reason: str = ''


class PlannedConfiguration(BaseModel):
    """A configuration to run: its name, where it runs and its environment variables."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    name: str
    runs_in_linux_container: bool
    environment: dict[str, str]


class DriverPlan(BaseModel):
    """The configurations to run, in order (dummy first), and those left out with the reason."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    configurations: tuple[PlannedConfiguration, ...]
    unavailable: tuple[Availability, ...]
    needs_xquartz: bool


def docker_running(*, environment: Mapping[str, str]) -> bool:
    """Tell whether the Docker daemon answers.

    Args:
        environment: The process environment.

    Returns:
        True when ``docker info`` succeeds; False without docker, or when it fails or hangs.

    """
    try:
        completed = run_command(
            command=['docker', 'info', '--format', '{{.ServerVersion}}'],
            environment=environment,
            timeout_seconds=DOCKER_CHECK_TIMEOUT_SECONDS,
            capture_output=OutputCapture.TOGETHER,
        )
    except FileNotFoundError, TimeoutExpired:
        return False
    return completed.returncode == 0


def probe_machine(
    *,
    platform: str,
    environment: Mapping[str, str],
    x11_prefix: Path = X11_PREFIX,
    docker_check: Callable[[], bool] | None = None,
) -> MachineFacts:
    """Find what this machine offers.

    Args:
        platform: ``sys.platform``.
        environment: The process environment.
        x11_prefix: XQuartz's install prefix.
        docker_check: Tells whether Docker runs (default: ``docker_running``).

    Returns:
        The facts. Docker and the build tools are looked for on macOS only (the configurations
        that need them run there only).

    """
    on_macos = platform == 'darwin'
    xquartz_installed = on_macos and (x11_prefix / 'bin' / 'Xquartz').exists()
    build_tools = (
        on_macos
        and shutil.which('cc') is not None
        and shutil.which('make') is not None
        and (x11_prefix / 'include' / 'X11' / 'Xlib.h').is_file()
    )
    check = docker_check or (lambda: docker_running(environment=environment))
    return MachineFacts(
        platform=platform,
        wayland_display=bool(environment.get('WAYLAND_DISPLAY')),
        x_display=bool(environment.get('DISPLAY')),
        docker_running=on_macos and check(),
        xquartz_installed=xquartz_installed,
        build_tools=build_tools,
    )


def configuration_availability(
    *, configuration: DriverConfiguration, facts: MachineFacts
) -> Availability:
    """Tell whether a configuration can run on a machine.

    Args:
        configuration: The configuration.
        facts: The machine.

    Returns:
        Its availability, with the reason when it cannot run.

    """
    on_linux = facts.platform.startswith('linux')
    on_macos = facts.platform == 'darwin'
    # Each configuration's needs, in order: the first unmet one is the reason
    needs: dict[str, tuple[tuple[bool, str], ...]] = {
        DUMMY: (),
        COCOA: ((on_macos, 'macOS only'),),
        WINDOWS: ((facts.platform == 'win32', 'Windows only'),),
        WAYLAND: ((on_linux, 'Linux only'), (facts.wayland_display, 'no WAYLAND_DISPLAY')),
        X11: ((on_linux, 'Linux only'), (facts.x_display, 'no DISPLAY')),
        X11_MACOS: (
            (on_macos, 'macOS only (Linux runs x11 natively)'),
            (facts.xquartz_installed, 'XQuartz is not installed (/opt/X11)'),
            (facts.build_tools, 'no C compiler, make or X11 headers to build SDL with x11'),
        ),
        X11_LINUX: (
            (on_macos, 'macOS only (it forwards to XQuartz)'),
            (facts.xquartz_installed, 'XQuartz is not installed (/opt/X11)'),
            (facts.docker_running, 'the Docker daemon is not running'),
        ),
    }
    unmet = next((reason for met, reason in needs[configuration.name] if not met), None)
    return Availability(name=configuration.name, available=unmet is None, reason=unmet or '')


def parse_drivers(*, text: str | None) -> list[str] | None:
    """Parse ``--drivers a,b,c``.

    Args:
        text: The option's value (None: not given).

    Returns:
        The names, in order and without repeats; None when not given.

    """
    if text is None:
        return None
    names = [name.strip() for name in text.split(DRIVERS_SEPARATOR) if name.strip()]
    return list(dict.fromkeys(names))


def select_configurations(
    *, requested: Sequence[str] | None, facts: MachineFacts
) -> tuple[list[DriverConfiguration], list[Availability]]:
    """Choose the configurations to run.

    Args:
        requested: The names asked for (None: every available one).
        facts: The machine.

    Returns:
        The configurations to run, in ``CONFIGURATIONS`` order with dummy first (added when
        not asked for: it is the baseline), and the availability of each one left out.

    Raises:
        SelectionError: If a requested name is unknown or cannot run here.

    """
    if requested is not None:
        unknown = [name for name in requested if name not in CONFIGURATIONS_BY_NAME]
        if unknown:
            message = (
                f'unknown configuration {", ".join(unknown)}; '
                f'known: {", ".join(CONFIGURATIONS_BY_NAME)}'
            )
            raise SelectionError(message)
    availabilities = {
        configuration.name: configuration_availability(configuration=configuration, facts=facts)
        for configuration in CONFIGURATIONS
    }
    if requested is not None:
        refused = [
            f'{name} ({availabilities[name].reason})'
            for name in requested
            if not availabilities[name].available
        ]
        if refused:
            message = f'cannot run here: {"; ".join(refused)}'
            raise SelectionError(message)
    wanted = {DUMMY, *(requested or [])}
    selected = [
        configuration
        for configuration in CONFIGURATIONS
        if availabilities[configuration.name].available
        and (requested is None or configuration.name in wanted)
    ]
    left_out = [
        availability
        for availability in availabilities.values()
        if not availability.available or (requested is not None and availability.name not in wanted)
    ]
    return selected, left_out


def configuration_environment(
    *,
    configuration: DriverConfiguration,
    environment: Mapping[str, str],
    sdl_x11_library: Path | None,
) -> dict[str, str]:
    """Return the environment variables a configuration's runs set.

    Args:
        configuration: The configuration.
        environment: The process environment (x11-macos keeps its DISPLAY).
        sdl_x11_library: The SDL built with x11 (for x11-macos).

    Returns:
        SDL_VIDEODRIVER, SDL_AUDIODRIVER and the configuration's own variables; for x11-macos
        also SDL_DYNAMIC_API and DISPLAY.

    Raises:
        SelectionError: If x11-macos is given no library.

    """
    variables = {
        'SDL_VIDEODRIVER': configuration.video_driver,
        'SDL_AUDIODRIVER': configuration.audio_driver,
        **configuration.extra_environment,
    }
    if configuration.uses_sdl_x11_build:
        if sdl_x11_library is None:
            message = f'{configuration.name} needs SDL built with x11'
            raise SelectionError(message)
        display = {'DISPLAY': environment['DISPLAY']} if environment.get('DISPLAY') else {}
        variables.update(x11_environment(environment=display, library=sdl_x11_library))
    return variables


def plan_configurations(
    *,
    requested: Sequence[str] | None,
    facts: MachineFacts,
    environment: Mapping[str, str],
    build_sdl_x11: Callable[[], Path],
) -> DriverPlan:
    """Plan the runs: choose the configurations and build what they need.

    Args:
        requested: The names asked for (None: every available one).
        facts: The machine.
        environment: The process environment.
        build_sdl_x11: Builds (or reuses) SDL with x11 and returns its library; called only
            when x11-macos is chosen.

    Returns:
        The plan.

    """
    selected, left_out = select_configurations(requested=requested, facts=facts)
    library = (
        build_sdl_x11()
        if any(configuration.uses_sdl_x11_build for configuration in selected)
        else None
    )
    return DriverPlan(
        configurations=tuple(
            PlannedConfiguration(
                name=configuration.name,
                runs_in_linux_container=configuration.runs_in_linux_container,
                environment=configuration_environment(
                    configuration=configuration, environment=environment, sdl_x11_library=library
                ),
            )
            for configuration in selected
        ),
        unavailable=tuple(left_out),
        needs_xquartz=any(configuration.needs_xquartz for configuration in selected),
    )


def describe_plan(*, plan: DriverPlan) -> str:
    """Describe a plan in a few lines (for the session's log).

    Args:
        plan: The plan.

    Returns:
        The configurations to run, then those left out with the reason.

    """
    lines = [
        'Configurations: ' + ', '.join(configuration.name for configuration in plan.configurations)
    ]
    lines.extend(
        f'  not run: {availability.name}'
        + (f' ({availability.reason})' if availability.reason else ' (not asked for)')
        for availability in plan.unavailable
    )
    return '\n'.join(lines) + '\n'


def argument_parser() -> argparse.ArgumentParser:
    """Build the command line parser.

    Returns:
        The parser, with the plan command.

    """
    parser = argparse.ArgumentParser(description="Plan compare-drivers' configurations")
    commands = parser.add_subparsers(dest='command', required=True)
    plan = commands.add_parser('plan', help='choose the configurations; write the plan as JSON')
    plan.add_argument('--output', type=Path, required=True, help='the plan file')
    plan.add_argument(
        '--drivers',
        default=None,
        help=f'configurations, comma separated (default: all available): '
        f'{", ".join(CONFIGURATIONS_BY_NAME)}',
    )
    plan.add_argument(
        '--cache-root', type=Path, default=None, help='where SDL with x11 is built and kept'
    )
    return parser


def run(
    *,
    arguments: Sequence[str],
    environment: Mapping[str, str],
    facts: MachineFacts,
    home: Path,
    log: TextIO,
) -> ExitCode:
    """Run the plan command.

    Args:
        arguments: The command line arguments (without the program name).
        environment: The process environment.
        facts: The machine.
        home: The user's home directory (SDL with x11's default cache).
        log: Where the plan's description and errors go.

    Returns:
        The exit code.

    """
    options = argument_parser().parse_args(arguments)

    def build_sdl_x11() -> Path:
        build = SdlX11Build(
            version=wheel_sdl_version(),
            cache_root=options.cache_root or default_cache_root(home=home),
        )
        return ensure_built(
            build=build,
            environment=environment,
            jobs=make_jobs(cpu_count=os.process_cpu_count()),
            log=log,
        )

    try:
        plan = plan_configurations(
            requested=parse_drivers(text=options.drivers),
            facts=facts,
            environment=environment,
            build_sdl_x11=build_sdl_x11,
        )
    except SelectionError as error:
        say(log=log, text=f'{error}\n')
        return ExitCode.OPTIONS_REFUSED
    except BuildError as error:
        say(log=log, text=f'x11-macos: {error}\n')
        return ExitCode.INTERNAL_ERROR
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(plan.model_dump_json(indent=2), encoding='utf-8')
    say(log=log, text=describe_plan(plan=plan))
    return ExitCode.SUCCESS


def main() -> None:
    """Command line: see the module docstring."""
    os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
    sys.exit(
        run(
            arguments=sys.argv[1:],
            environment=os.environ,
            facts=probe_machine(platform=sys.platform, environment=os.environ),
            home=Path.home(),
            log=sys.stderr,
        )
    )


if __name__ == '__main__':
    main()
