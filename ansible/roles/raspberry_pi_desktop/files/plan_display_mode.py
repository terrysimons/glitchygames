#!/usr/bin/env python3
"""Plan a GNOME or labwc session's display mode from the compositor's own state, changing nothing.

Run as the session's user, in its session bus (ansible/roles/raspberry_pi_desktop, Ubuntu). It
asks mutter (org.gnome.Mutter.DisplayConfig, GetCurrentState) for the monitor and its modes,
chooses the mode of the wanted size at the first wanted rate the monitor offers (else the
highest rate at that size), and prints the plan: by default one JSON object (``action``: apply,
none, skip or fail; the ``connector``; the ``mode``; a ``reason``), or with ``--format words``
one line, ``<action> <connector> <mode>`` with a dash for what the plan doesn't name, for the
shell wrapper ``apply_display_mode``, which sets the mode with GNOME's own tool, ``gdctl``. It
exits 1 when the plan fails.

GNOME 50 saves a display change only when someone clicks Keep in its confirmation dialog, and
reverts it after 20 seconds otherwise; nothing a script can call confirms it (mutter's
meta-monitor-manager.c; the Pis' journals, 2026-11-14). So the mode is applied temporarily,
which needs no confirmation, at every login (an autostart entry) and on every deploy.

Interface: https://gitlab.gnome.org/GNOME/mutter/-/blob/main/data/dbus-interfaces/org.gnome.Mutter.DisplayConfig.xml

Raspberry Pi OS runs labwc (wlroots), which has no mutter: with ``--wlr-randr-json -`` the planner
reads ``wlr-randr --json`` from its input instead (``apply_labwc_display_mode`` pipes it in) and
turns it into mutter's shape (``state_from_wlr_randr``), so one ``plan`` serves both desktops.
labwc keeps a mode once set, so there it needs no confirming either.
Tests: tests/test_ansible_raspberry_pis.py (on the Pis' own GetCurrentState, 2026-11-14).
"""

from __future__ import annotations

import argparse
import json
import operator
import sys
from pathlib import Path
from typing import Any

# A wanted rate matches a mode within this many hertz (mutter lists 120.03968811 as 120.040)
REFRESH_TOLERANCE = 0.01
SCALE = 1.0
# Scales are doubles: 1.0 matches within this
SCALE_TOLERANCE = 1e-6
MUTTER = (
    'org.gnome.Mutter.DisplayConfig',
    '/org/gnome/Mutter/DisplayConfig',
    'org.gnome.Mutter.DisplayConfig',
)

# GetCurrentState's shapes, as GLib.Variant.unpack() gives them: a mode is (id, width, height,
# refresh rate, preferred scale, supported scales, properties); a monitor is ((connector, vendor,
# product, serial), modes, properties); a logical monitor is (x, y, scale, transform, primary,
# monitor specs, properties); the state is (serial, monitors, logical monitors, properties)
type Properties = dict[str, object]
type MonitorSpec = tuple[str, str, str, str]
type Mode = tuple[str, int, int, float, float, list[float], Properties]
type Monitor = tuple[MonitorSpec, list[Mode], Properties]
type LogicalMonitor = tuple[int, int, float, int, bool, list[MonitorSpec], Properties]
type State = tuple[int, list[Monitor], list[LogicalMonitor], Properties]


def chosen_mode(
    *, modes: list[Mode], width: int, height: int, refresh_rates: list[float]
) -> Mode | None:
    """Return the mode of a size at the first wanted rate offered, else the highest at that size.

    Args:
        modes: A monitor's modes, as GetCurrentState gives them (id, width, height, refresh
            rate, preferred scale, supported scales, properties).
        width: The wanted width.
        height: The wanted height.
        refresh_rates: The wanted rates, most wanted first.

    Returns:
        The mode, or None when the monitor has none of that size.

    """
    sized = [mode for mode in modes if mode[1] == width and mode[2] == height]
    if not sized:
        return None
    for rate in refresh_rates:
        for mode in sized:
            if abs(mode[3] - rate) <= REFRESH_TOLERANCE:
                return mode
    return max(sized, key=operator.itemgetter(3))


def plan(*, state: State, width: int, height: int, refresh_rates: list[float]) -> dict[str, object]:
    """Return what to do with a session's display, from its GetCurrentState.

    Returns:
        ``action`` (apply, none, skip or fail), the ``connector``, the ``mode`` and a ``reason``.

    """
    _serial, monitors, logical_monitors, _properties = state
    if len(monitors) != 1:
        return {
            'action': 'skip',
            'connector': None,
            'mode': None,
            'reason': f'{len(monitors)} monitors: left as they are',
        }
    ((spec, modes, _monitor_properties),) = monitors
    connector = spec[0]
    mode = chosen_mode(modes=modes, width=width, height=height, refresh_rates=refresh_rates)
    if mode is None:
        return {
            'action': 'fail',
            'connector': connector,
            'mode': None,
            'reason': f'{connector} offers no {width}x{height} mode',
        }
    if not any(abs(scale - SCALE) < SCALE_TOLERANCE for scale in mode[5]):
        return {
            'action': 'fail',
            'connector': connector,
            'mode': mode[0],
            'reason': f'{mode[0]} has no scale {SCALE}',
        }
    current = next((each[0] for each in modes if each[6].get('is-current')), None)
    scale = next(
        (
            logical[2]
            for logical in logical_monitors
            if any(each[0] == connector for each in logical[5])
        ),
        None,
    )
    if current == mode[0] and scale is not None and abs(scale - SCALE) < SCALE_TOLERANCE:
        return {
            'action': 'none',
            'connector': connector,
            'mode': mode[0],
            'reason': f'{connector} is already {mode[0]}',
        }
    return {
        'action': 'apply',
        'connector': connector,
        'mode': mode[0],
        'reason': f'{connector}: {current} at scale {scale} to {mode[0]} at scale {SCALE}',
    }


def wlr_randr_mode_id(mode: dict[str, Any]) -> str:
    """Return a wlr-randr mode as its ``--mode`` takes it: ``<width>x<height>@<refresh>Hz``.

    Six decimals: wlr-randr reports rates to the millihertz, so the name keeps the rate exact.

    Returns:
        The mode's name.

    """
    return f'{mode["width"]}x{mode["height"]}@{mode["refresh"]:.6f}Hz'


def state_from_wlr_randr(outputs: list[dict[str, Any]]) -> State:
    """Return labwc's outputs (``wlr-randr --json``) in the shape mutter's GetCurrentState has.

    Each enabled output is a monitor (a disabled one shows nothing) and a logical monitor at its
    scale; each mode is named as wlr-randr's ``--mode`` takes it, offers scale 1 (wlroots sets
    any scale), and carries mutter's ``is-current`` and ``is-preferred``.

    Args:
        outputs: wlr-randr's outputs, each with ``name``, ``make``, ``model``, ``serial``,
            ``enabled``, ``position``, ``scale`` and ``modes`` (``width``, ``height``,
            ``refresh``, ``preferred``, ``current``).

    Returns:
        The state: (serial 0, monitors, logical monitors, no properties).

    """
    monitors: list[Monitor] = []
    logical_monitors: list[LogicalMonitor] = []
    for output in outputs:
        if not output['enabled']:
            continue
        spec: MonitorSpec = (
            str(output['name']),
            str(output.get('make') or ''),
            str(output.get('model') or ''),
            str(output.get('serial') or ''),
        )
        modes: list[Mode] = [
            (
                wlr_randr_mode_id(mode),
                int(mode['width']),
                int(mode['height']),
                float(mode['refresh']),
                SCALE,
                [SCALE],
                {'is-current': bool(mode['current']), 'is-preferred': bool(mode['preferred'])},
            )
            for mode in output['modes']
        ]
        monitors.append((spec, modes, {}))
        position = output['position']
        logical_monitors.append((
            int(position['x']),
            int(position['y']),
            float(output['scale']),
            0,
            not logical_monitors,
            [spec],
            {},
        ))
    return (0, monitors, logical_monitors, {})


def plan_words(plan_result: dict[str, object]) -> str:
    """Return a plan as one line the shell can split: action, connector, mode.

    Args:
        plan_result: A plan, as ``plan`` returns it.

    Returns:
        The line, with a dash for what the plan doesn't name.

    """
    return ' '.join(str(plan_result.get(key) or '-') for key in ('action', 'connector', 'mode'))


def write_plan(plan_result: dict[str, object], *, plan_format: str) -> None:
    """Print a plan as JSON or as words."""
    text = plan_words(plan_result) if plan_format == 'words' else json.dumps(plan_result)
    sys.stdout.write(text + '\n')


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - runs in a Pi's session
    """Plan the session's display mode and print the plan; change nothing.

    Returns:
        The exit status: 1 when the plan fails, else 0.

    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--height', type=int, required=True)
    parser.add_argument(
        '--refresh-rates', required=True, help='wanted rates, most wanted first, comma-separated'
    )
    parser.add_argument(
        '--format', choices=('json', 'words'), default='json', help='how the plan is printed'
    )
    parser.add_argument(
        '--wlr-randr-json',
        metavar='FILE',
        help="labwc's outputs, as wlr-randr --json prints them ('-': standard input), not mutter's",
    )
    arguments = parser.parse_args(argv)
    refresh_rates = [float(rate) for rate in arguments.refresh_rates.split(',')]

    if arguments.wlr_randr_json is not None:
        text = (
            sys.stdin.read()
            if arguments.wlr_randr_json == '-'
            else Path(arguments.wlr_randr_json).read_text(encoding='utf-8')
        )
        state = state_from_wlr_randr(json.loads(text))
        result = plan(
            state=state, width=arguments.width, height=arguments.height, refresh_rates=refresh_rates
        )
        write_plan(result, plan_format=arguments.format)
        return 1 if result['action'] == 'fail' else 0

    # The Pi's python3-gi, imported only when run there: planning needs none
    from gi.repository import Gio, GLib

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        state = bus.call_sync(
            *MUTTER, 'GetCurrentState', None, None, Gio.DBusCallFlags.NONE, -1, None
        ).unpack()
    except GLib.Error as error:
        no_session = {
            'action': 'skip',
            'connector': None,
            'mode': None,
            'reason': f'no GNOME session: {error.message}',
        }
        write_plan(no_session, plan_format=arguments.format)
        return 0
    result = plan(
        state=state, width=arguments.width, height=arguments.height, refresh_rates=refresh_rates
    )
    write_plan(result, plan_format=arguments.format)
    return 1 if result['action'] == 'fail' else 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
