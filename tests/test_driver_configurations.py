"""scripts/driver_configurations.py: which driver configurations run here, and their plan.

Machines are fabricated (``MachineFacts``); XQuartz's prefix is a folder under tmp_path. The
Docker check's ``docker info`` is patched (an external tool whose answer depends on the
machine); building SDL with x11 is replaced by a stand-in (tests/test_build_sdl_x11.py tests
the build).
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from scripts import driver_configurations
from scripts.build_sdl_x11 import BuildError
from scripts.driver_configurations import (
    CONFIGURATIONS_BY_NAME,
    DriverPlan,
    MachineFacts,
    SelectionError,
    configuration_availability,
    configuration_environment,
    describe_plan,
    docker_running,
    parse_drivers,
    plan_configurations,
    probe_machine,
    run,
    select_configurations,
)

from glitchygames.exit_codes import ExitCode
from glitchygames.process import CompletedProcess, TimeoutExpired

LIBRARY = Path('/cache/sdl-x11/2.32.10/install/lib/libSDL2-2.0.0.dylib')


def mac(**changes: bool) -> MachineFacts:
    """Return a Mac with Docker running, XQuartz and the build tools (changes applied).

    Returns:
        The facts.

    """
    facts = {
        'platform': 'darwin',
        'wayland_display': False,
        'x_display': True,
        'docker_running': True,
        'xquartz_installed': True,
        'build_tools': True,
    }
    return MachineFacts(**(facts | changes))


def linux(*, wayland: bool = False, x_display: bool = True) -> MachineFacts:
    """Return a Linux machine.

    Returns:
        The facts.

    """
    return MachineFacts(
        platform='linux',
        wayland_display=wayland,
        x_display=x_display,
        docker_running=False,
        xquartz_installed=False,
        build_tools=False,
    )


class TestDockerRunning:
    """``docker info`` tells whether the daemon answers."""

    @pytest.mark.parametrize(('returncode', 'running'), [(0, True), (1, False)])
    def test_the_daemons_answer(self, mocker, returncode, running):
        mocker.patch.object(
            driver_configurations,
            'run_command',
            return_value=CompletedProcess(args=[], returncode=returncode, stdout=''),
        )

        assert docker_running(environment={}) is running

    @pytest.mark.parametrize(
        'error', [FileNotFoundError('docker'), TimeoutExpired(cmd='docker', timeout=30)]
    )
    def test_no_docker_or_a_hang(self, mocker, error):
        mocker.patch.object(driver_configurations, 'run_command', side_effect=error)

        assert docker_running(environment={}) is False


class TestProbeMachine:
    """The machine's facts, from its platform, environment and files."""

    @pytest.fixture
    def xquartz(self, tmp_path) -> Path:
        """An XQuartz prefix with its server and X11 headers.

        Returns:
            The prefix.

        """
        (tmp_path / 'bin').mkdir()
        (tmp_path / 'bin' / 'Xquartz').write_text('', encoding='utf-8')
        (tmp_path / 'include' / 'X11').mkdir(parents=True)
        (tmp_path / 'include' / 'X11' / 'Xlib.h').write_text('', encoding='utf-8')
        return tmp_path

    def test_a_mac_with_everything(self, xquartz, mocker):
        mocker.patch.object(driver_configurations.shutil, 'which', return_value='/usr/bin/cc')

        facts = probe_machine(
            platform='darwin',
            environment={'DISPLAY': ':0'},
            x11_prefix=xquartz,
            docker_check=lambda: True,
        )

        assert facts == mac()

    def test_a_mac_without_xquartz_or_docker(self, tmp_path):
        facts = probe_machine(
            platform='darwin', environment={}, x11_prefix=tmp_path, docker_check=lambda: False
        )

        assert not facts.xquartz_installed
        assert not facts.build_tools
        assert not facts.docker_running
        assert not facts.x_display

    def test_linux_looks_for_neither_docker_nor_build_tools(self, xquartz):
        checked: list[bool] = []

        facts = probe_machine(
            platform='linux',
            environment={'WAYLAND_DISPLAY': 'wayland-0'},
            x11_prefix=xquartz,
            docker_check=lambda: checked.append(True) or True,
        )

        assert facts == MachineFacts(
            platform='linux',
            wayland_display=True,
            x_display=False,
            docker_running=False,
            xquartz_installed=False,
            build_tools=False,
        )
        assert checked == []

    def test_docker_is_checked_by_default(self, tmp_path, mocker):
        checked = mocker.patch.object(driver_configurations, 'docker_running', return_value=True)

        facts = probe_machine(platform='darwin', environment={'A': 'b'}, x11_prefix=tmp_path)

        assert facts.docker_running
        checked.assert_called_once_with(environment={'A': 'b'})


class TestAvailability:
    """Each configuration's needs; the first unmet one is the reason."""

    @pytest.mark.parametrize(
        ('facts', 'name', 'reason'),
        [
            (mac(), 'dummy', ''),
            (mac(), 'cocoa', ''),
            (linux(), 'cocoa', 'macOS only'),
            (mac(), 'windows', 'Windows only'),
            (linux(wayland=True), 'wayland', ''),
            (linux(), 'wayland', 'no WAYLAND_DISPLAY'),
            (mac(), 'wayland', 'Linux only'),
            (linux(), 'x11', ''),
            (linux(x_display=False), 'x11', 'no DISPLAY'),
            (mac(), 'x11-macos', ''),
            (linux(), 'x11-macos', 'macOS only (Linux runs x11 natively)'),
            (mac(xquartz_installed=False), 'x11-macos', 'XQuartz is not installed (/opt/X11)'),
            (
                mac(build_tools=False),
                'x11-macos',
                'no C compiler, make or X11 headers to build SDL with x11',
            ),
            (mac(), 'x11-linux', ''),
            (mac(docker_running=False), 'x11-linux', 'the Docker daemon is not running'),
            (mac(xquartz_installed=False), 'x11-linux', 'XQuartz is not installed (/opt/X11)'),
            (linux(), 'x11-linux', 'macOS only (it forwards to XQuartz)'),
        ],
    )
    def test_the_availability(self, facts, name, reason):
        availability = configuration_availability(
            configuration=CONFIGURATIONS_BY_NAME[name], facts=facts
        )

        assert availability.available is (not reason)
        assert availability.reason == reason


class TestSelection:
    """``--drivers`` parsing and the choice of configurations."""

    @pytest.mark.parametrize(
        ('text', 'names'),
        [
            (None, None),
            ('cocoa', ['cocoa']),
            (' dummy, x11-macos ,,x11-macos', ['dummy', 'x11-macos']),
        ],
    )
    def test_parse_drivers(self, text, names):
        assert parse_drivers(text=text) == names

    def test_by_default_every_available_one(self):
        selected, left_out = select_configurations(requested=None, facts=mac())

        assert [each.name for each in selected] == ['dummy', 'cocoa', 'x11-macos', 'x11-linux']
        assert [each.name for each in left_out] == ['windows', 'wayland', 'x11']

    def test_dummy_is_always_the_baseline(self):
        selected, left_out = select_configurations(requested=['x11-linux', 'cocoa'], facts=mac())

        assert [each.name for each in selected] == ['dummy', 'cocoa', 'x11-linux']
        assert 'x11-macos' in [each.name for each in left_out]

    def test_an_unknown_name_is_refused(self):
        with pytest.raises(SelectionError, match='unknown configuration x11-windows; known: '):
            select_configurations(requested=['x11-windows'], facts=mac())

    def test_an_unavailable_one_is_refused_with_its_reason(self):
        with pytest.raises(
            SelectionError, match=r'cannot run here: x11-linux \(the Docker daemon is not running'
        ):
            select_configurations(requested=['x11-linux'], facts=mac(docker_running=False))


class TestEnvironment:
    """Each configuration's environment variables."""

    def test_cocoa_keeps_its_windows_in_the_background(self):
        assert configuration_environment(
            configuration=CONFIGURATIONS_BY_NAME['cocoa'], environment={}, sdl_x11_library=None
        ) == {
            'SDL_VIDEODRIVER': 'cocoa',
            'SDL_AUDIODRIVER': 'coreaudio',
            'SDL_MAC_BACKGROUND_APP': '1',
        }

    def test_x11_macos_loads_the_built_sdl(self):
        variables = configuration_environment(
            configuration=CONFIGURATIONS_BY_NAME['x11-macos'],
            environment={'DISPLAY': '/private/xquartz:0', 'HOME': '/home'},
            sdl_x11_library=LIBRARY,
        )

        assert variables == {
            'SDL_VIDEODRIVER': 'x11',
            'SDL_AUDIODRIVER': 'dummy',
            'SDL_DYNAMIC_API': str(LIBRARY),
            'DISPLAY': '/private/xquartz:0',
        }

    def test_x11_macos_without_a_display_uses_xquartzs(self):
        variables = configuration_environment(
            configuration=CONFIGURATIONS_BY_NAME['x11-macos'],
            environment={},
            sdl_x11_library=LIBRARY,
        )

        assert variables['DISPLAY'] == ':0'

    def test_x11_macos_needs_the_library(self):
        with pytest.raises(SelectionError, match='needs SDL built with x11'):
            configuration_environment(
                configuration=CONFIGURATIONS_BY_NAME['x11-macos'],
                environment={},
                sdl_x11_library=None,
            )


class TestPlan:
    """The plan: the configurations, their environments, XQuartz, and what was left out."""

    def test_sdl_with_x11_is_built_only_for_x11_macos(self):
        builds: list[bool] = []

        def build() -> Path:
            builds.append(True)
            return LIBRARY

        without = plan_configurations(
            requested=['cocoa'], facts=mac(), environment={}, build_sdl_x11=build
        )
        with_x11_macos = plan_configurations(
            requested=None, facts=mac(), environment={}, build_sdl_x11=build
        )

        assert builds == [True]
        assert not without.needs_xquartz
        assert with_x11_macos.needs_xquartz
        assert [each.name for each in with_x11_macos.configurations] == [
            'dummy',
            'cocoa',
            'x11-macos',
            'x11-linux',
        ]
        assert with_x11_macos.configurations[3].runs_in_linux_container
        assert with_x11_macos.configurations[2].environment['SDL_DYNAMIC_API'] == str(LIBRARY)

    def test_the_description(self):
        plan = plan_configurations(
            requested=['dummy'],
            facts=mac(docker_running=False),
            environment={},
            build_sdl_x11=lambda: LIBRARY,
        )

        assert describe_plan(plan=plan).splitlines() == [
            'Configurations: dummy',
            '  not run: cocoa (not asked for)',
            '  not run: windows (Windows only)',
            '  not run: wayland (Linux only)',
            '  not run: x11 (Linux only)',
            '  not run: x11-macos (not asked for)',
            '  not run: x11-linux (the Docker daemon is not running)',
        ]


class TestCommandLine:
    """``plan`` writes the plan as JSON; refusals and build failures have their exit codes."""

    def run_plan(self, arguments: list[str], *, facts: MachineFacts, home: Path):
        """Run the command line; return its exit code and log."""
        log = io.StringIO()
        exit_code = run(arguments=arguments, environment={}, facts=facts, home=home, log=log)
        return exit_code, log.getvalue()

    def test_the_plan_is_written(self, tmp_path, mocker):
        built = mocker.patch.object(driver_configurations, 'ensure_built', return_value=LIBRARY)
        output = tmp_path / 'out' / 'plan.json'

        exit_code, log = self.run_plan(
            ['plan', f'--output={output}', '--drivers=x11-macos'], facts=mac(), home=tmp_path
        )

        assert exit_code == ExitCode.SUCCESS
        plan = DriverPlan.model_validate_json(output.read_text(encoding='utf-8'))
        assert [each.name for each in plan.configurations] == ['dummy', 'x11-macos']
        assert log.startswith('Configurations: dummy, x11-macos\n')
        build = built.call_args.kwargs['build']
        assert build.cache_root == tmp_path / 'Library' / 'Caches' / 'glitchygames' / 'sdl-x11'

    def test_a_cache_root_is_used(self, tmp_path, mocker):
        built = mocker.patch.object(driver_configurations, 'ensure_built', return_value=LIBRARY)

        self.run_plan(
            [
                'plan',
                f'--output={tmp_path / "plan.json"}',
                f'--cache-root={tmp_path / "cache"}',
            ],
            facts=mac(),
            home=tmp_path,
        )

        assert built.call_args.kwargs['build'].cache_root == tmp_path / 'cache'

    def test_an_unavailable_configuration_is_refused(self, tmp_path):
        exit_code, log = self.run_plan(
            ['plan', f'--output={tmp_path / "plan.json"}', '--drivers=cocoa'],
            facts=linux(),
            home=tmp_path,
        )

        assert exit_code == ExitCode.OPTIONS_REFUSED
        assert log == 'cannot run here: cocoa (macOS only)\n'
        assert not (tmp_path / 'plan.json').exists()

    def test_a_failed_build(self, tmp_path, mocker):
        mocker.patch.object(
            driver_configurations, 'ensure_built', side_effect=BuildError('make failed')
        )

        exit_code, log = self.run_plan(
            ['plan', f'--output={tmp_path / "plan.json"}'], facts=mac(), home=tmp_path
        )

        assert exit_code == ExitCode.INTERNAL_ERROR
        assert log == 'x11-macos: make failed\n'

    def test_main_exits_with_the_code(self, tmp_path, monkeypatch, mocker):
        mocker.patch.object(driver_configurations, 'docker_running', return_value=False)
        output = tmp_path / 'plan.json'
        monkeypatch.setattr(
            sys, 'argv', ['driver_configurations', 'plan', f'--output={output}', '--drivers=dummy']
        )

        with pytest.raises(SystemExit) as raised:
            driver_configurations.main()

        assert raised.value.code == ExitCode.SUCCESS
        assert json.loads(output.read_text(encoding='utf-8'))['configurations'][0]['name'] == (
            'dummy'
        )
