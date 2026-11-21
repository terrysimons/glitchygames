"""The Raspberry Pis' Ansible setup: OS groups, the OS check, the desktop and the firmware.

ansible/inventory.yml groups the Pis by OS under ``raspberry_pis``: ``raspberry_pis_ubuntu``
(Ubuntu 26.04 and 26.10) and ``raspberry_pis_raspberry_pi_os`` (Raspberry Pi OS 64-bit, Trixie;
no Pi yet). ansible/raspberry_pi_runner.yml's plays use four roles:

- ``raspberry_pi_os``: refuses a Pi whose OS isn't the one the inventory names.
- ``raspberry_pi_desktop``: auto-login and a display that stays on, done each OS's way (gdm3 and
  dconf on Ubuntu; lightdm and labwc's swayidle on Raspberry Pi OS, as raspi-config does them).
- ``raspberry_pi_audio``: HDMI audio on the Ubuntu Pi 5s (each HDMI sink unmuted at the
  inventory's volume, an HDMI default), as a WirePlumber drop-in and a script that sets each
  user's running session with wpctl.
- ``raspberry_pi_firmware``: each Pi's clock and fan settings, as one ``blockinfile`` block per
  board section appended to config.txt (the block is its ``[pi5]``/``[pi4]`` section and ends
  with ``[all]``), with checks for settings typed by hand and against what the firmware applied.

Templates and assertions are rendered here with Jinja as Ansible renders them, and the hand-set
line check runs with the real awk on the owner's Pis' own config.txt (read 2026-11-14).
"""

from __future__ import annotations

import ast
import base64
import importlib.util
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any

import jinja2
import pytest
import yaml
from pydantic import BaseModel, ConfigDict

from glitchygames.process import OutputCapture, run_command
from tests.ansible_inventory import inventory_group, natural_key, raspberry_pi_hosts
from tests.ansible_rendering import compiled_template

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLAYBOOK_PATH = PROJECT_ROOT / 'ansible' / 'raspberry_pi_runner.yml'
ROLES = PROJECT_ROOT / 'ansible' / 'roles'
UBUNTU_GROUP = 'raspberry_pis_ubuntu'
RASPBERRY_PI_OS_GROUP = 'raspberry_pis_raspberry_pi_os'
PI4 = 'raspberry-pi-4-4gb-ubuntu'
PI5_16GB = 'raspberry-pi-5-16gb-ubuntu'
PI5_8GB = 'raspberry-pi-5-8gb-ubuntu'
# The first Raspberry Pi OS Pi (2026-11-16): the 16 GB Pi 5 in the NVMe heat-sink case
PI5_16GB_RASPBERRY_PI_OS = 'raspberry-pi-5-16gb-raspberry-pi-os'
BLOCK_TASK = 'Write the firmware settings in their board section'
CHANGED = 'raspberry_pi_hand_typed_removed.changed or raspberry_pi_firmware_block.changed'
# Ansible templates with trim_blocks on, so a {% %} line leaves no line of its own, and no
# escaping (config text, not HTML)
ANSIBLE_TEMPLATES = jinja2.Environment(
    trim_blocks=True,
    undefined=jinja2.StrictUndefined,
    autoescape=jinja2.select_autoescape(default_for_string=False, default=False),
)
# Ansible's b64decode filter (https://docs.ansible.com/ansible/latest/collections/ansible/builtin/b64decode_filter.html):
# base64 text to text, as the tasks decode what slurp reads
ANSIBLE_TEMPLATES.filters['b64decode'] = lambda value: base64.b64decode(value).decode('utf-8')
# Ansible's from_json filter (https://docs.ansible.com/ansible/latest/collections/ansible/builtin/from_json_filter.html):
# JSON text to data, as the HDMI audio tasks read the script's report
ANSIBLE_TEMPLATES.filters['from_json'] = json.loads

UBUNTU_HEAD = """[all]
os_prefix=current/

[tryboot]
os_prefix=new/

[all]
arm_64bit=1
kernel=vmlinuz
cmdline=cmdline.txt
initramfs initrd.img followkernel

# Config settings specific to arm64
dtoverlay=dwc2

"""
UBUNTU_TAIL = """[pi4]
max_framebuffers=2
arm_boost=1

[pi3+]
dtoverlay=vc4-kms-v3d,cma-128

[cm4]
dtoverlay=dwc2,dr_mode=host

[all]
dtparam=watchdog=on
"""
# The 16 GB Pi 5's, overclocked by hand (gpu_fre: the owner's typo, ignored by the firmware)
PI5_16GB_CONFIG = (
    UBUNTU_HEAD
    + """[pi5]
arm_freq=3000
gpu_fre=1100
over_voltage=6

"""
    + UBUNTU_TAIL
)
# The 8 GB Pi 5's: no [pi5] section
PI5_8GB_CONFIG = UBUNTU_HEAD + UBUNTU_TAIL
# Raspberry Pi OS's default config.txt, as its image builder writes it (Trixie): pi-gen's
# stage1/00-boot-files/files/config.txt at commit ccafc13f2574 (2026-06-15),
# https://github.com/RPi-Distro/pi-gen/blob/ccafc13f2574/stage1/00-boot-files/files/config.txt
RASPBERRY_PI_OS_CONFIG = """# For more options and information see
# http://rptl.io/configtxt
# Some settings may impact device functionality. See link above for details

# Uncomment some or all of these to enable the optional hardware interfaces
#dtparam=i2c_arm=on
#dtparam=i2s=on
#dtparam=spi=on

# Enable audio (loads snd_bcm2835)
dtparam=audio=on

# Additional overlays and parameters are documented
# /boot/firmware/overlays/README

# Automatically load overlays for detected cameras
camera_auto_detect=1

# Automatically load overlays for detected DSI displays
display_auto_detect=1

# Automatically load initramfs files, if found
auto_initramfs=1

# Enable DRM VC4 V3D driver
dtoverlay=vc4-kms-v3d
max_framebuffers=2

# Don't have the firmware create an initial video= setting in cmdline.txt.
# Use the kernel's default instead.
disable_fw_kms_setup=1

# Disable compensation for displays with overscan
disable_overscan=1

# Run as fast as firmware / board allows
arm_boost=1

[cm4]
# Enable host mode on the 2711 built-in XHCI USB controller.
# This line should be removed if the legacy DWC2 controller is required
# (e.g. for USB device mode) or if USB support is not required.
otg_mode=1

[cm5]
dtoverlay=dwc2,dr_mode=host

[pi5]
dtoverlay=nospi10

[all]
"""
# The recommended curve for an overclocked Pi 5 (the owner's table, 2026-11-14): not applied to
# any Pi yet (every Pi starts on the firmware's defaults), used here to test the template
OVERCLOCKED_PI5_CURVE = [
    {'start_celsius': 45, 'stop_below_celsius': 41, 'speed': 100},
    {'start_celsius': 55, 'stop_below_celsius': 51, 'speed': 150},
    {'start_celsius': 62, 'stop_below_celsius': 58, 'speed': 200},
    {'start_celsius': 68, 'stop_below_celsius': 64, 'speed': 255},
]


def yaml_file(path: Path) -> Any:
    """Return a YAML file, parsed.

    Returns:
        Its contents.

    """
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def plays() -> list[dict[str, Any]]:
    """Return the Pi playbook's plays.

    Returns:
        The plays, in order.

    """
    return yaml_file(PLAYBOOK_PATH)


def role_tasks(role: str, file_name: str = 'main.yml') -> list[dict[str, Any]]:
    """Return one of a role's task files.

    Returns:
        Its tasks.

    """
    return yaml_file(ROLES / role / 'tasks' / file_name)


def task(tasks: list[dict[str, Any]], name: str) -> dict[str, Any]:
    """Return the task with a name.

    Returns:
        The task.

    """
    (found,) = [each for each in tasks if each.get('name') == name]
    return found


def firmware_defaults() -> dict[str, Any]:
    """Return the firmware role's defaults.

    Returns:
        The variables.

    """
    return yaml_file(ROLES / 'raspberry_pi_firmware' / 'defaults' / 'main.yml')


def firmware_task(name: str) -> dict[str, Any]:
    """Return one of the firmware role's tasks.

    Returns:
        The task.

    """
    return task(role_tasks('raspberry_pi_firmware'), name)


def host_variables(host: str, **overrides: Any) -> dict[str, Any]:
    """Return what a host's firmware tasks see: the role's defaults, its groups', its own.

    Returns:
        The variables.

    """
    defaults = yaml_file(ROLES / 'raspberry_pi_firmware' / 'defaults' / 'main.yml')
    return {**defaults, **raspberry_pi_hosts()[host], **overrides}


def render(template: str, **variables: Any) -> str:
    """Render a template as Ansible would.

    Returns:
        The rendered text.

    """
    return compiled_template(environment=ANSIBLE_TEMPLATES, source=template).render(**variables)


def holds(condition: str, **variables: Any) -> bool:
    """Evaluate an assert task's condition as Ansible would (a bare Jinja expression).

    Returns:
        Whether it holds.

    """
    return render('{{ (' + condition + ') }}', **variables) == 'True'


def block_text(**variables: Any) -> str:
    """Return the firmware block's lines for some variables (blockinfile adds no final newline).

    Returns:
        The block.

    """
    return render(
        firmware_task(BLOCK_TASK)['ansible.builtin.blockinfile']['block'], **variables
    ).rstrip('\n')


def blocked(text: str, *, host: str) -> str:
    """Return config.txt with a host's firmware block appended, as blockinfile writes it at EOF.

    Returns:
        The file with the block.

    """
    variables = host_variables(host)
    marker = render(firmware_task(BLOCK_TASK)['ansible.builtin.blockinfile']['marker'], **variables)
    begin, end = marker.replace('{mark}', 'BEGIN'), marker.replace('{mark}', 'END')
    return f'{text}{begin}\n{block_text(**variables)}\n{end}\n'


def hand_set_lines(text: str, *, host: str, tmp_path: Path) -> str:
    """Run the role's check for firmware lines set by hand on a file, with the real awk.

    Returns:
        What the check prints (nothing when every managed line is in a block).

    """
    config = tmp_path / 'config.txt'
    config.write_text(text, encoding='utf-8')
    variables = host_variables(host, raspberry_pi_firmware_config=str(config))
    command = render(
        firmware_task('Refuse firmware settings set by hand')['ansible.builtin.command']['cmd'],
        **variables,
    )
    # ansible.builtin.command runs no shell: it splits the line as shlex does
    result = run_command(
        command=shlex.split(command),
        environment={'PATH': os.environ['PATH']},
        timeout_seconds=30,
        capture_output=OutputCapture.APART,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


# --- Ansible itself, on every Python ----------------------------------------------------------


# The firmware check's awk command and the display wrappers are the Pis' own shell commands: they
# need a POSIX shell, as the Pis have. On Windows awk gets a backslashed path and a shell script
# isn't a program (CircleCI job 3637: "awk: fatal: cannot open file", "WinError 193")
NEEDS_A_POSIX_SHELL = pytest.mark.skipif(
    sys.platform == 'win32', reason="runs the Pis' shell commands, which need a POSIX shell"
)


@pytest.mark.skipif(sys.platform == 'win32', reason='Ansible has no Windows control node')
def test_ansible_runs_on_this_python():
    """``ansible-playbook --version`` starts on the Python running the suite.

    nox -s test runs the suite on each Python of noxfile.TEST_PYTHONS, so each gets this check.
    ansible-core 2.21 patched dataclasses._is_type, which Python 3.15 removed, so it crashed at
    startup on a .venv synced on 3.15 (the owner's deploy, 2026-11-17); 2.22 runs on both.
    """
    playbook_command = Path(sys.executable).parent / 'ansible-playbook'

    result = run_command(
        command=[str(playbook_command), '--version'],
        environment={'PATH': os.environ['PATH']},
        timeout_seconds=60,
        capture_output=OutputCapture.APART,
    )

    assert result.returncode == 0, result.stderr
    assert f'python version = {sys.version_info.major}.{sys.version_info.minor}' in result.stdout


# --- The inventory: OS groups ---------------------------------------------------------------


def test_the_pis_are_grouped_by_os():
    """Two OS groups under raspberry_pis, which holds no host of its own."""
    group = inventory_group('raspberry_pis')

    assert set(group['children']) == {UBUNTU_GROUP, RASPBERRY_PI_OS_GROUP}
    assert 'hosts' not in group
    assert list(group['children'][UBUNTU_GROUP]['hosts']) == [PI4, PI5_8GB, PI5_16GB]
    assert list(group['children'][RASPBERRY_PI_OS_GROUP]['hosts']) == [PI5_16GB_RASPBERRY_PI_OS]


def test_the_natural_order_puts_8gb_before_16gb():
    """Digits compare by value, where plain sorting would put 16gb first."""
    names = [PI5_16GB, PI4, PI5_8GB]

    assert sorted(names) == [PI4, PI5_16GB, PI5_8GB]
    assert sorted(names, key=natural_key) == [PI4, PI5_8GB, PI5_16GB]


@pytest.mark.parametrize('group_name', [UBUNTU_GROUP, RASPBERRY_PI_OS_GROUP])
def test_the_inventory_lists_each_os_groups_pis_in_natural_order(group_name):
    """Ansible runs hosts in inventory order, so each OS group lists its Pis 4gb, 8gb, 16gb.

    Each group, not all the Pis at once: the inventory lists them group by group, and no name
    puts a Raspberry Pi OS 16 GB Pi both after the Ubuntu Pis and before their 16 GB one.
    """
    hosts = list(inventory_group('raspberry_pis')['children'][group_name]['hosts'])

    assert hosts == sorted(hosts, key=natural_key)


def test_all_the_pis_are_listed_group_by_group():
    """raspberry_pis' hosts are its groups' hosts, the Ubuntu Pis first, in each group's order."""
    group = inventory_group('raspberry_pis')['children']

    assert list(raspberry_pi_hosts()) == [
        *group[UBUNTU_GROUP]['hosts'],
        *group[RASPBERRY_PI_OS_GROUP]['hosts'],
    ]


def test_every_play_runs_its_hosts_in_inventory_order():
    """Said in each play, not left to Ansible's default."""
    assert [play.get('order') for play in plays()] == ['inventory'] * len(plays())


@pytest.mark.parametrize(
    ('group_name', 'expected'),
    [
        (
            UBUNTU_GROUP,
            {
                'raspberry_pi_os': 'ubuntu',
                'raspberry_pi_os_distribution': 'Ubuntu',
                'raspberry_pi_os_release_fact': 'distribution_version',
                'raspberry_pi_os_supported_releases': ['26.04', '26.10'],
                'raspberry_pi_firmware_config': '/boot/firmware/config.txt',
            },
        ),
        (
            RASPBERRY_PI_OS_GROUP,
            {
                'raspberry_pi_os': 'raspberry_pi_os',
                # Raspberry Pi OS keeps Debian's os-release; Trixie is Debian 13
                'raspberry_pi_os_distribution': 'Debian',
                'raspberry_pi_os_release_fact': 'distribution_major_version',
                'raspberry_pi_os_supported_releases': ['13'],
                'raspberry_pi_os_marker_file': '/etc/rpi-issue',
                'raspberry_pi_firmware_config': '/boot/firmware/config.txt',
            },
        ),
    ],
)
def test_each_os_group_says_what_it_is(group_name, expected):
    """Each group names its OS, how Ansible reports it, its supported releases and its paths."""
    variables = inventory_group('raspberry_pis')['children'][group_name]['vars']

    assert {key: variables.get(key) for key in expected} == expected


@pytest.mark.parametrize(
    ('host', 'release'),
    [(PI4, '26.10'), (PI5_16GB, '26.04'), (PI5_8GB, '26.10'), (PI5_16GB_RASPBERRY_PI_OS, '13')],
)
def test_each_pi_names_its_release(host, release):
    """The release each Pi runs (read 2026-11-08 to 2026-11-16), one its group supports."""
    variables = raspberry_pi_hosts()[host]

    assert variables['raspberry_pi_os_release'] == release
    assert release in variables['raspberry_pi_os_supported_releases']


# --- The OS check --------------------------------------------------------------------------


def os_check_condition() -> list[str]:
    """Return the OS check's conditions.

    Returns:
        Each condition, as written.

    """
    return task(
        role_tasks('raspberry_pi_os'), 'Refuse a Pi whose OS is not the one the inventory names'
    )['ansible.builtin.assert']['that']


@pytest.mark.parametrize(
    ('facts', 'passes'),
    [
        ({'distribution': 'Ubuntu', 'distribution_version': '26.04'}, True),
        ({'distribution': 'Ubuntu', 'distribution_version': '26.10'}, False),
        ({'distribution': 'Debian', 'distribution_version': '26.04'}, False),
    ],
)
def test_the_os_check_compares_the_facts_with_the_inventory(facts, passes):
    """The 16 GB Pi 5 must report Ubuntu 26.04: another release or OS is refused."""
    variables = {**raspberry_pi_hosts()[PI5_16GB], 'ansible_facts': facts}

    assert all(holds(condition, **variables) for condition in os_check_condition()) is passes


def test_a_release_the_group_does_not_support_is_refused():
    """A Pi that says it runs a release outside its group's list fails even when facts agree."""
    variables = {
        **raspberry_pi_hosts()[PI4],
        'raspberry_pi_os_release': '25.10',
        'ansible_facts': {'distribution': 'Ubuntu', 'distribution_version': '25.10'},
    }

    assert not all(holds(condition, **variables) for condition in os_check_condition())


def test_raspberry_pi_os_is_told_from_plain_debian_by_its_marker_file():
    """Debian 13 on a Pi isn't Raspberry Pi OS: the role checks for /etc/rpi-issue there."""
    check = task(role_tasks('raspberry_pi_os'), "Refuse a Debian that isn't Raspberry Pi OS")

    assert check['when'] == 'raspberry_pi_os_marker_file is defined'
    assert check['ansible.builtin.assert']['that'] == ['raspberry_pi_os_marker.stat.exists']


def test_the_plays_import_their_roles_so_a_run_can_start_at_any_task():
    """Roles are imported, not included, so --start-at-task can reach their tasks.

    It only reaches statically imported tasks: a dry run starting at a role task was refused
    (2026-11-14).
    """
    playbook = PLAYBOOK_PATH.read_text(encoding='utf-8')

    assert 'include_role' not in playbook
    assert playbook.count('ansible.builtin.import_role') == 7


def test_every_play_checks_the_os_first():
    """Each play's first role is the OS check, so no play changes a Pi of the wrong OS."""
    for play in plays():
        first = play['tasks'][0]
        assert first['ansible.builtin.import_role'] == {'name': 'raspberry_pi_os'}, play['name']


# --- The desktop, each OS's way ------------------------------------------------------------


def test_the_desktop_role_takes_the_tasks_of_the_pis_os():
    """One task file per OS, chosen by the group's raspberry_pi_os."""
    (include,) = role_tasks('raspberry_pi_desktop')

    assert include['ansible.builtin.include_tasks'] == '{{ raspberry_pi_os }}.yml'
    for os_name in ('ubuntu', 'raspberry_pi_os'):
        assert (ROLES / 'raspberry_pi_desktop' / 'tasks' / f'{os_name}.yml').is_file()


def test_ubuntu_logs_the_ci_user_in_with_gdm_and_keeps_gnome_awake():
    """gdm3's custom.conf and dconf's system defaults."""
    tasks = role_tasks('raspberry_pi_desktop', 'ubuntu.yml')
    login = task(tasks, "Log the runner's user in at boot")['ansible.builtin.blockinfile']
    display = task(tasks, "Keep the desktop session's display on")['ansible.builtin.copy']

    assert login['path'] == '/etc/gdm3/custom.conf'
    assert 'AutomaticLogin={{ ci_user }}' in login['block']
    assert 'idle-delay=uint32 0' in display['content']


def test_raspberry_pi_os_logs_the_ci_user_in_with_lightdm():
    """The runner's user is lightdm's autologin-user, set as raspi-config's do_autologin sets it."""
    login = task(
        role_tasks('raspberry_pi_desktop', 'raspberry_pi_os.yml'),
        "Log the runner's user in at boot",
    )['ansible.builtin.lineinfile']

    assert login['path'] == '/etc/lightdm/lightdm.conf'
    assert login['regexp'] == '^#?autologin-user='
    assert login['line'] == 'autologin-user={{ ci_user }}'
    assert login['insertafter'] == r'^\[Seat:\*\]'


def test_raspberry_pi_os_keeps_labwc_from_blanking():
    """Blanking is a swayidle line in labwc's autostart files: each one is removed.

    That is raspi-config's do_blanking, done by hand: raspi-config itself can't be used here,
    since it detects labwc by a running session.
    """
    keep_on = task(
        role_tasks('raspberry_pi_desktop', 'raspberry_pi_os.yml'),
        "Keep the desktop session's display on",
    )

    assert keep_on['ansible.builtin.lineinfile'] == {
        'path': '{{ item }}',
        'regexp': 'swayidle',
        'state': 'absent',
    }
    assert keep_on['loop'] == [
        '/etc/xdg/labwc/autostart',
        '/etc/xdg/labwc-greeter/autostart',
        '{{ raspberry_pi_runner_home }}/.config/labwc/autostart',
    ]


def test_ubuntus_dconf_handler_lives_with_the_tasks_that_notify_it():
    """The desktop role holds its handler; the runner play no longer needs to."""
    handlers = yaml_file(ROLES / 'raspberry_pi_desktop' / 'handlers' / 'main.yml')
    runner_handlers = [handler['name'] for handler in plays()[0]['handlers']]

    assert [handler['name'] for handler in handlers] == ['Update the desktop defaults']
    assert 'Update the desktop defaults' not in runner_handlers


# --- The plays -----------------------------------------------------------------------------


def test_the_runner_play_sets_up_every_pi_and_each_os_group_gets_a_firmware_play():
    """The runner, uv and the clone are every Pi's; firmware is set per OS group."""
    assert [play['hosts'] for play in plays()] == [
        'raspberry_pis',
        UBUNTU_GROUP,
        RASPBERRY_PI_OS_GROUP,
    ]
    for play in plays()[1:]:
        roles = [each.get('ansible.builtin.import_role', {}).get('name') for each in play['tasks']]
        assert roles == ['raspberry_pi_os', 'raspberry_pi_firmware'], play['name']


def test_the_runner_play_takes_the_desktop_role():
    """The runner play sets the desktop up through the role, after the OS check, then HDMI audio.

    The audio role comes after the desktop, whose auto-login starts the CI user's session, and in
    this play, which names the CI and deploy users it sets audio up for.
    """
    roles = [
        each['ansible.builtin.import_role']['name']
        for each in plays()[0]['tasks']
        if 'ansible.builtin.import_role' in each
    ]

    assert roles == ['raspberry_pi_os', 'raspberry_pi_desktop', 'raspberry_pi_audio']


# --- Each Pi's clock and fan ---------------------------------------------------------------


@pytest.mark.parametrize(
    ('host', 'board', 'enabled', 'settings', 'fan'),
    [
        # Stock at 1800 MHz; no fan (2026-11-14)
        (PI4, 'pi4', False, {}, {'kind': 'none'}),
        # Overclocked by hand to 3000 MHz at over_voltage 6; the owner's GPU setting (typed
        # gpu_fre, so never applied) fixed to gpu_freq ("Fix the typo"). Its Active Cooler on
        # the firmware's default curve
        (
            PI5_16GB,
            'pi5',
            True,
            {'arm_freq': 3000, 'gpu_freq': 1100, 'over_voltage': 6},
            {'kind': 'active-cooler', 'levels': []},
        ),
        # Stock at 2400 MHz, the Active Cooler on the default curve
        (PI5_8GB, 'pi5', False, {}, {'kind': 'active-cooler', 'levels': []}),
        # The Ubuntu 16 GB Pi's overclock and cooling, in the same kind of case (the owner,
        # 2026-11-16: "the same sorts of corallary settings that the Ubuntu system had")
        (
            PI5_16GB_RASPBERRY_PI_OS,
            'pi5',
            True,
            {'arm_freq': 3000, 'gpu_freq': 1100, 'over_voltage': 6},
            {'kind': 'active-cooler', 'levels': []},
        ),
    ],
)
def test_each_pi_declares_its_board_clock_and_fan(host, board, enabled, settings, fan):
    """Each host names its board section, its clock and its fan."""
    variables = raspberry_pi_hosts()[host]

    assert variables['raspberry_pi_board'] == board
    assert variables['raspberry_pi_overclock_enabled'] is enabled
    assert variables['raspberry_pi_overclock_settings'] == settings
    assert variables['raspberry_pi_fan'] == fan


def settings_conditions() -> list[str]:
    """Return the conditions of the role's settings check.

    Returns:
        Each condition, as written.

    """
    return firmware_task('Refuse unknown firmware settings')['ansible.builtin.assert']['that']


def test_every_pis_settings_pass_the_roles_own_check():
    """The inventory as it is passes the check the role runs on each Pi."""
    for host in raspberry_pi_hosts():
        variables = host_variables(host)
        failed = [
            condition for condition in settings_conditions() if not holds(condition, **variables)
        ]
        assert not failed, (host, failed)


@pytest.mark.parametrize(
    ('host', 'overrides'),
    [
        (PI5_16GB, {'raspberry_pi_overclock_settings': {'gpu_fre': 1100}}),
        (PI5_16GB, {'raspberry_pi_overclock_settings': {'arm_freq': '3000'}}),
        (PI5_8GB, {'raspberry_pi_overclock_settings': {'arm_freq': 2600}}),
        (PI5_8GB, {'raspberry_pi_fan': {'kind': 'gpio-fan', 'pin': 14, 'levels': []}}),
        (PI4, {'raspberry_pi_fan': {'kind': 'active-cooler', 'levels': []}}),
        (
            PI4,
            {
                'raspberry_pi_fan': {
                    'kind': 'gpio-fan',
                    'levels': [{'start_celsius': 50, 'stop_below_celsius': 45, 'speed': 255}],
                }
            },
        ),
        (PI4, {'raspberry_pi_fan': {'kind': 'gpio-fan', 'pin': 14, 'levels': []}}),
        (
            PI5_8GB,
            {'raspberry_pi_fan': {'kind': 'active-cooler', 'levels': OVERCLOCKED_PI5_CURVE * 2}},
        ),
        (
            PI5_8GB,
            {
                'raspberry_pi_fan': {
                    'kind': 'active-cooler',
                    'levels': [{'start_celsius': 50, 'stop_below_celsius': 45, 'speed': 300}],
                }
            },
        ),
        (
            PI5_8GB,
            {
                'raspberry_pi_fan': {
                    'kind': 'active-cooler',
                    'levels': list(reversed(OVERCLOCKED_PI5_CURVE)),
                }
            },
        ),
    ],
    ids=[
        'unknown clock key',
        'clock value not a number',
        'settings while overclocking is off',
        'a gpio fan on a pi5',
        'an active cooler on a pi4',
        'a gpio fan with no pin',
        'a gpio fan with no level',
        'more than four levels',
        'a speed past 255',
        'levels not rising',
    ],
)
def test_bad_settings_are_refused(host, overrides):
    """A typo or a fan the board can't have never reaches a Pi's boot config."""
    variables = host_variables(host, **overrides)

    assert not all(holds(condition, **variables) for condition in settings_conditions())


def test_a_level_that_stops_above_where_it_starts_is_refused():
    """Each level's fan stops below the temperature that starts it."""
    level_check = firmware_task("Refuse a fan level that wouldn't stop below where it starts")

    assert level_check['loop'] == '{{ raspberry_pi_fan.levels | default([]) }}'
    (condition,) = level_check['ansible.builtin.assert']['that']
    assert holds(condition, item={'start_celsius': 50, 'stop_below_celsius': 45, 'speed': 75})
    assert not holds(condition, item={'start_celsius': 50, 'stop_below_celsius': 50, 'speed': 75})


# --- The block -----------------------------------------------------------------------------


def test_the_overclocked_pis_block_is_its_board_section_closed_by_all():
    """The 16 GB Pi 5: its header, its clock in a fixed order, no fan lines (defaults), [all]."""
    assert (
        block_text(**host_variables(PI5_16GB))
        == '[pi5]\narm_freq=3000\ngpu_freq=1100\nover_voltage=6\n[all]'
    )
    marker = firmware_task(BLOCK_TASK)['ansible.builtin.blockinfile']['marker']
    assert render(marker, **host_variables(PI5_16GB)) == (
        '# {mark} firmware settings for [pi5], managed by ansible/raspberry_pi_runner.yml'
    )
    assert firmware_task(BLOCK_TASK)['ansible.builtin.blockinfile']['insertafter'] == 'EOF'


def test_a_pi5_curve_becomes_the_active_coolers_dtparams():
    """Celsius in the inventory, millicelsius in config.txt; hysteresis is start less stop."""
    variables = host_variables(
        PI5_8GB, raspberry_pi_fan={'kind': 'active-cooler', 'levels': OVERCLOCKED_PI5_CURVE}
    )

    assert block_text(**variables) == (
        '[pi5]\n'
        'dtparam=fan_temp0=45000\n'
        'dtparam=fan_temp0_hyst=4000\n'
        'dtparam=fan_temp0_speed=100\n'
        'dtparam=fan_temp1=55000\n'
        'dtparam=fan_temp1_hyst=4000\n'
        'dtparam=fan_temp1_speed=150\n'
        'dtparam=fan_temp2=62000\n'
        'dtparam=fan_temp2_hyst=4000\n'
        'dtparam=fan_temp2_speed=200\n'
        'dtparam=fan_temp3=68000\n'
        'dtparam=fan_temp3_hyst=4000\n'
        'dtparam=fan_temp3_speed=255\n'
        '[all]'
    )


def test_a_pi4_on_off_fan_becomes_the_gpio_fan_overlay():
    """One level: on at 50 C, off below 45 C, on the fan's pin (the Case Fan's 14)."""
    fan = {
        'kind': 'gpio-fan',
        'pin': 14,
        'levels': [{'start_celsius': 50, 'stop_below_celsius': 45, 'speed': 255}],
    }

    assert block_text(**host_variables(PI4, raspberry_pi_fan=fan)) == (
        '[pi4]\ndtoverlay=gpio-fan,gpiopin=14,temp=50000,hyst=5000\n[all]'
    )


def test_a_pi4_pwm_fan_becomes_the_pwm_gpio_fan_overlay():
    """Four levels on one overlay line, half degrees kept (62.5 C is 62500)."""
    levels = [
        {'start_celsius': 48, 'stop_below_celsius': 44, 'speed': 114},
        {'start_celsius': 56, 'stop_below_celsius': 52, 'speed': 160},
        {'start_celsius': 63, 'stop_below_celsius': 59, 'speed': 210},
        {'start_celsius': 68.5, 'stop_below_celsius': 62.5, 'speed': 255},
    ]
    fan = {'kind': 'pwm-gpio-fan', 'pin': 18, 'levels': levels}

    assert block_text(**host_variables(PI4, raspberry_pi_fan=fan)) == (
        '[pi4]\ndtoverlay=pwm-gpio-fan,fan_gpio=18'
        ',fan_temp0=48000,fan_temp0_hyst=4000,fan_temp0_speed=114'
        ',fan_temp1=56000,fan_temp1_hyst=4000,fan_temp1_speed=160'
        ',fan_temp2=63000,fan_temp2_hyst=4000,fan_temp2_speed=210'
        ',fan_temp3=68500,fan_temp3_hyst=6000,fan_temp3_speed=255\n[all]'
    )


def test_clock_and_fan_share_one_block():
    """An overclocked Pi 5 with a curve: the clock first, then the fan."""
    variables = host_variables(
        PI5_16GB, raspberry_pi_fan={'kind': 'active-cooler', 'levels': OVERCLOCKED_PI5_CURVE[:1]}
    )

    assert block_text(**variables) == (
        '[pi5]\n'
        'arm_freq=3000\n'
        'gpu_freq=1100\n'
        'over_voltage=6\n'
        'dtparam=fan_temp0=45000\n'
        'dtparam=fan_temp0_hyst=4000\n'
        'dtparam=fan_temp0_speed=100\n'
        '[all]'
    )


@pytest.mark.parametrize(
    ('host', 'overrides', 'state'),
    [
        (PI4, {}, 'absent'),
        (PI5_16GB, {}, 'present'),
        (PI5_8GB, {}, 'absent'),
        (
            PI5_8GB,
            {'raspberry_pi_fan': {'kind': 'active-cooler', 'levels': OVERCLOCKED_PI5_CURVE}},
            'present',
        ),
        (
            PI4,
            {
                'raspberry_pi_fan': {
                    'kind': 'gpio-fan',
                    'pin': 14,
                    'levels': [{'start_celsius': 50, 'stop_below_celsius': 45, 'speed': 255}],
                }
            },
            'present',
        ),
    ],
)
def test_a_pi_with_nothing_to_set_has_no_block(host, overrides, state):
    """Stock clock and a default (or no) fan: no block; any setting writes it."""
    task_arguments = firmware_task(BLOCK_TASK)['ansible.builtin.blockinfile']

    assert render(task_arguments['state'], **host_variables(host, **overrides)) == state


# --- Settings typed by hand ----------------------------------------------------------------


def test_raspberry_pi_ubuntu_overclock():
    """The 16 GB Pi 5 names its hand-typed [pi5] section; the role removes what a Pi names."""
    cleanup = firmware_task('Remove the settings typed by hand that the block takes over')
    (pattern_text,) = host_variables(PI5_16GB)['raspberry_pi_firmware_hand_typed_patterns']
    pattern = re.compile(pattern_text, re.MULTILINE)
    cleaned = pattern.sub('', PI5_16GB_CONFIG)

    assert cleanup['ansible.builtin.replace']['regexp'] == '{{ item }}'
    assert cleanup['loop'] == '{{ raspberry_pi_firmware_hand_typed_patterns }}'
    assert cleaned == PI5_8GB_CONFIG
    assert pattern.sub('', blocked(cleaned, host=PI5_16GB)) == blocked(cleaned, host=PI5_16GB)


@pytest.mark.parametrize('host', [PI4, PI5_8GB])
def test_a_pi_that_typed_nothing_by_hand_removes_nothing(host):
    """The role's default: no patterns."""
    assert host_variables(host)['raspberry_pi_firmware_hand_typed_patterns'] == []


# --- The backup (/boot/firmware is FAT: vfat, 2026-11-14) ------------------------------------


def boot_partition_tasks() -> list[dict[str, Any]]:
    """Return every Pi task that writes the firmware's config.txt or its backup.

    Returns:
        The tasks.

    """
    tasks = [each for play in plays() for each in play['tasks']]
    for path in ROLES.glob('raspberry_pi_*/tasks/*.yml'):
        tasks += yaml_file(path)
    writes = []
    for each in tasks:
        for module, arguments in each.items():
            if module.startswith('ansible.builtin.') and isinstance(arguments, dict):
                target = str(arguments.get('path', '')) + str(arguments.get('dest', ''))
                if (
                    'raspberry_pi_firmware_config' in target
                    or 'raspberry_pi_firmware_backup' in target
                ):
                    writes.append({'name': each.get('name'), 'module': module, **arguments})
    return writes


def test_no_task_on_the_boot_partition_uses_ansibles_backup():
    """No task writing to the boot partition may use Ansible's backup option.

    It names its copy <file>.<pid>.<date>@<hh:mm:ss>~, and a colon is not a FAT file name: the
    16 GB Pi 5's first run failed with [Errno 22] (2026-11-14).
    """
    writes = boot_partition_tasks()

    assert writes
    assert [write['name'] for write in writes if 'backup' in write] == []


def test_the_backup_name_is_valid_on_fat():
    """One fixed name, of characters FAT allows, beside config.txt."""
    backup = render(
        firmware_defaults()['raspberry_pi_firmware_backup'],
        raspberry_pi_firmware_config='/boot/firmware/config.txt',
    )

    assert backup == '/boot/firmware/config.txt.ansible-backup'
    assert not set(Path(backup).name) & set('"*/:<>?\\|')


def test_config_txt_is_read_before_anything_changes_it():
    """The file as it was is kept in memory first, so the backup can hold it after a change."""
    names = [each['name'] for each in role_tasks('raspberry_pi_firmware')]
    read = firmware_task('Read config.txt as it is before this run')

    assert read['ansible.builtin.slurp']['src'] == '{{ raspberry_pi_firmware_config }}'
    assert read['register'] == 'raspberry_pi_firmware_original'
    assert names.index('Read config.txt as it is before this run') < names.index(
        'Remove the settings typed by hand that the block takes over'
    )
    assert names.index('Write the firmware settings in their board section') < names.index(
        'Keep config.txt as it was before this change'
    )


def test_the_backup_is_made_once_and_kept_up_to_date_with_each_change():
    """Made when there is none; replaced with the file as it was whenever the run changed it."""
    save = firmware_task('Keep config.txt as it was before this change')

    assert save['ansible.builtin.copy'] == {
        'content': '{{ raspberry_pi_firmware_original.content | b64decode }}',
        'dest': '{{ raspberry_pi_firmware_backup }}',
    }
    assert save['when'] == f'not raspberry_pi_firmware_backup_file.stat.exists or {CHANGED}'
    exists = firmware_task('Read whether config.txt has its backup')
    assert exists['ansible.builtin.stat']['path'] == '{{ raspberry_pi_firmware_backup }}'
    assert exists['register'] == 'raspberry_pi_firmware_backup_file'


@NEEDS_A_POSIX_SHELL
def test_the_check_finds_clock_lines_set_by_hand(tmp_path):
    """On the 16 GB Pi 5's file as it was, the check reports its hand-set clock lines."""
    found = hand_set_lines(PI5_16GB_CONFIG, host=PI5_16GB, tmp_path=tmp_path)

    assert 'arm_freq=3000' in found
    assert 'over_voltage=6' in found


@pytest.mark.parametrize(
    'line',
    [
        'dtparam=fan_temp0=40000',
        'dtoverlay=gpio-fan,gpiopin=14,temp=50000',
        'dtoverlay=pwm-gpio-fan,fan_gpio=18',
    ],
)
@NEEDS_A_POSIX_SHELL
def test_the_check_finds_fan_lines_set_by_hand(tmp_path, line):
    """A fan setting typed by hand (raspi-config's Fan menu writes gpio-fan) is refused too."""
    found = hand_set_lines(PI5_8GB_CONFIG + line + '\n', host=PI5_8GB, tmp_path=tmp_path)

    assert line in found


@NEEDS_A_POSIX_SHELL
def test_the_check_passes_lines_inside_a_block(tmp_path):
    """After the cleanup and the block, nothing is reported; nor on a stock Pi with no block."""
    assert not hand_set_lines(
        blocked(PI5_8GB_CONFIG, host=PI5_16GB), host=PI5_16GB, tmp_path=tmp_path
    )
    assert not hand_set_lines(PI5_8GB_CONFIG, host=PI5_8GB, tmp_path=tmp_path)


@NEEDS_A_POSIX_SHELL
def test_the_check_ignores_other_settings_and_comments(tmp_path):
    """Comments, near-miss names and other overlays are not managed lines."""
    text = (
        PI5_8GB_CONFIG
        + '#arm_freq=2000\narm_freqency=1\n#dtparam=fan_temp0=1\ndtoverlay=vc4-kms-v3d\n'
    )

    assert not hand_set_lines(text, host=PI5_8GB, tmp_path=tmp_path)


# --- Board, reboot and what the firmware applied -------------------------------------------


def test_the_pi_must_be_the_board_its_section_names():
    """A [pi5] section on a Pi 4 would do nothing: the role checks the model matches the board."""
    defaults = yaml_file(ROLES / 'raspberry_pi_firmware' / 'defaults' / 'main.yml')
    (condition,) = firmware_task('Refuse a Pi whose board is not the one the inventory names')[
        'ansible.builtin.assert'
    ]['that']

    assert defaults['raspberry_pi_board_models'] == {
        'pi4': 'Raspberry Pi 4 ',
        'pi5': 'Raspberry Pi 5 ',
    }
    variables = host_variables(PI4)
    assert 'raspberry_pi_board_models[raspberry_pi_board]' in condition
    assert variables['raspberry_pi_board'] == 'pi4'


def test_a_change_says_a_reboot_is_needed_and_reboots_nothing():
    """config.txt is read at boot; nothing here reboots (it would end the desktop session)."""
    notice = firmware_task('Say a reboot is needed for the new firmware settings')
    texts = [PLAYBOOK_PATH.read_text(encoding='utf-8')] + [
        path.read_text(encoding='utf-8') for path in ROLES.glob('raspberry_pi_*/**/*.yml')
    ]

    assert (
        notice['when']
        == 'raspberry_pi_hand_typed_removed.changed or raspberry_pi_firmware_block.changed'
    )
    assert not any('ansible.builtin.reboot' in text for text in texts)


def test_an_unchanged_clock_is_checked_against_what_the_firmware_applied():
    """When nothing changed, each clock setting must be what vcgencmd get_config reports."""
    check = firmware_task('Check the firmware runs the configured clock')

    assert check['ansible.builtin.command']['cmd'] == 'vcgencmd get_config {{ item.key }}'
    assert check['loop'] == '{{ raspberry_pi_overclock_settings | dict2items }}'
    assert (
        check['failed_when'] == "raspberry_pi_applied_clock.stdout != item.key ~ '=' ~ item.value"
    )
    assert (
        check['when']
        == 'not (raspberry_pi_hand_typed_removed.changed or raspberry_pi_firmware_block.changed)'
    )


def test_an_unchanged_curve_is_checked_against_the_kernels_trip_points():
    """Each Active Cooler level's start must be its trip point in thermal zone 0.

    The levels are trip points 1 to 4 (the audit read the defaults there: 50000, 60000, 67500,
    75000).
    """
    check = firmware_task('Check the kernel runs the configured fan curve')

    assert check['ansible.builtin.slurp']['src'] == (
        '/sys/class/thermal/thermal_zone0/trip_point_{{ raspberry_pi_level_index + 1 }}_temp'
    )
    assert check['loop'] == '{{ raspberry_pi_fan.levels | default([]) }}'
    assert check['loop_control'] == {'index_var': 'raspberry_pi_level_index'}
    assert check['when'] == f"not ({CHANGED}) and raspberry_pi_fan.kind == 'active-cooler'"


# --- Overclocking, per OS ------------------------------------------------------------------


def raspberry_pi_os_host(**host: Any) -> dict[str, Any]:
    """Return what a Raspberry Pi OS Pi's firmware tasks would see (no such Pi is in the inventory).

    Returns:
        The role's defaults, the Raspberry Pi OS group's variables, then the host's own.

    """
    group = inventory_group('raspberry_pis')['children'][RASPBERRY_PI_OS_GROUP]['vars']
    return {**firmware_defaults(), **group, 'raspberry_pi_os_release': '13', **host}


@pytest.mark.parametrize(
    ('board', 'settings', 'fan'),
    [
        (
            'pi5',
            {'arm_freq': 2800, 'over_voltage_delta': 50000},
            {'kind': 'active-cooler', 'levels': []},
        ),
        ('pi4', {'arm_freq': 2000, 'over_voltage': 6}, {'kind': 'none'}),
    ],
)
@NEEDS_A_POSIX_SHELL
def test_raspberry_pi_os_overclock(board, settings, fan, tmp_path):
    """An overclocked Pi on Raspberry Pi OS goes through the same role, on that OS's own config.txt.

    Its default config.txt already has a [pi5] section (dtoverlay=nospi10) and ends with [all],
    and sets arm_boost=1 for every board: the block leaves all of that alone and comes last.
    """
    variables = raspberry_pi_os_host(
        raspberry_pi_board=board,
        raspberry_pi_overclock_enabled=True,
        raspberry_pi_overclock_settings=settings,
        raspberry_pi_fan=fan,
    )
    task_arguments = firmware_task(BLOCK_TASK)['ansible.builtin.blockinfile']
    marker = render(task_arguments['marker'], **variables)
    block = block_text(**variables)
    configured = (
        f'{RASPBERRY_PI_OS_CONFIG}{marker.replace("{mark}", "BEGIN")}\n{block}\n'
        f'{marker.replace("{mark}", "END")}\n'
    )
    config = tmp_path / 'config.txt'
    config.write_text(configured, encoding='utf-8')
    check = render(
        firmware_task('Refuse firmware settings set by hand')['ansible.builtin.command']['cmd'],
        **{**variables, 'raspberry_pi_firmware_config': str(config)},
    )
    found = run_command(
        command=shlex.split(check),
        environment={'PATH': os.environ['PATH']},
        timeout_seconds=30,
        capture_output=OutputCapture.APART,
    )

    assert variables['raspberry_pi_firmware_config'] == '/boot/firmware/config.txt'
    assert all(holds(condition, **variables) for condition in settings_conditions())
    assert render(task_arguments['state'], **variables) == 'present'
    expected_lines = [
        f'[{board}]',
        *(f'{key}={value}' for key, value in sorted(settings.items())),
        '[all]',
    ]
    assert block.splitlines() == expected_lines
    assert configured.startswith(RASPBERRY_PI_OS_CONFIG)
    assert found.returncode == 0
    assert not found.stdout


def test_raspberry_pi_os_has_its_own_firmware_play():
    """The Raspberry Pi OS group's play runs the OS check and the firmware role, nothing else."""
    play = plays()[2]

    assert play['hosts'] == RASPBERRY_PI_OS_GROUP
    assert [each['ansible.builtin.import_role']['name'] for each in play['tasks']] == [
        'raspberry_pi_os',
        'raspberry_pi_firmware',
    ]


# --- The CI user's display mode (Ubuntu: GNOME's mutter over D-Bus) -------------------------

PLAN_DISPLAY_MODE_PATH = ROLES / 'raspberry_pi_desktop' / 'files' / 'plan_display_mode.py'
MUTTER_FIXTURES = PROJECT_ROOT / 'tests' / 'fixtures' / 'mutter'
# What the inventory asks for (the owner, 2026-11-14): 1920x1080 at 120 Hz on every Pi, the
# standard 1080p120 timing both boards offer (a Pi 5 also offers 120.04, a Pi 4 doesn't), so all
# three drive the display alike; else the highest rate a board offers at that size
WANTED_MODE = {'width': 1920, 'height': 1080, 'refresh_rates': [120.0]}


def load_set_display_mode() -> Any:
    """Load the role's display planner by its path (it is copied to the Pi, not installed).

    Returns:
        The module.

    Raises:
        ImportError: When the file can't be loaded.

    """
    specification = importlib.util.spec_from_file_location(
        'plan_display_mode', PLAN_DISPLAY_MODE_PATH
    )
    if specification is None or specification.loader is None:
        raise ImportError(PLAN_DISPLAY_MODE_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def mutter_state(board: str) -> Any:
    """Return a Pi's captured GetCurrentState in the shape GLib.Variant.unpack() gives the script.

    The captures are gdbus's text (2026-11-14, the CI user's session on the 16 GB Pi 5 and the
    Pi 4); unpacking turns structs into tuples, arrays into lists, a{sv} into dicts and every
    variant into its value, which is what dropping the type annotations here produces.

    Returns:
        The state.

    """
    text = (MUTTER_FIXTURES / f'{board}-get-current-state.txt').read_text(encoding='utf-8')
    text = text.replace('@a{sv} ', '').replace('uint32 ', '')
    text = re.sub(r'[<>]', '', text)
    text = re.sub(r'\btrue\b', 'True', re.sub(r'\bfalse\b', 'False', text))
    return ast.literal_eval(text)


@pytest.mark.parametrize('board', ['raspberry-pi-5', 'raspberry-pi-4'])
def test_every_board_gets_1080p_at_120_hz(board):
    """Both boards offer the standard 120.000 Hz at 1080p (their sessions, 2026-11-14)."""
    script = load_set_display_mode()
    ((_, modes, _),) = mutter_state(board)[1]

    mode = script.chosen_mode(modes=modes, **WANTED_MODE)

    assert mode[0] == '1920x1080@120.000'


@pytest.mark.parametrize(
    ('board', 'expected'),
    [('raspberry-pi-5', '1920x1080@120.040'), ('raspberry-pi-4', '1920x1080@120.000')],
)
def test_rates_are_tried_in_the_order_listed(board, expected):
    """Asked for 120.04 then 120: a Pi 5 has 120.040; a Pi 4 doesn't, so it gets 120.000."""
    script = load_set_display_mode()
    ((_, modes, _),) = mutter_state(board)[1]

    mode = script.chosen_mode(modes=modes, width=1920, height=1080, refresh_rates=[120.04, 120.0])

    assert mode[0] == expected


# --- labwc's displays (Raspberry Pi OS), read from wlr-randr --json into mutter's shape ------

WLR_RANDR_FIXTURES = PROJECT_ROOT / 'tests' / 'fixtures' / 'wlr-randr'


def wlr_randr_outputs(*, current: tuple[int, int, float] | None = None) -> list[dict[str, Any]]:
    """Return the Raspberry Pi OS Pi's wlr-randr --json (its owner's session, 2026-11-16).

    Args:
        current: The mode (width, height, refresh) to make current instead of the captured one
            (1920x1080 at 120 Hz, which the owner's kanshi set).

    Returns:
        The outputs.

    """
    path = WLR_RANDR_FIXTURES / 'raspberry-pi-5-16gb-raspberry-pi-os.json'
    outputs = json.loads(path.read_text(encoding='utf-8'))
    if current is not None:
        for output in outputs:
            for mode in output['modes']:
                mode['current'] = (mode['width'], mode['height'], mode['refresh']) == current
    return outputs


# The monitor's preferred mode, which a session without the owner's kanshi profile starts in
PREFERRED_4K = (3840, 2160, 60.0)


def test_a_labwc_session_in_4k_is_planned_to_1080p_at_120_hz():
    """The runner's session starts in the monitor's preferred 4K: the plan is 1080p at 120 Hz.

    Named as wlr-randr's --mode takes it.
    """
    script = load_set_display_mode()
    state = script.state_from_wlr_randr(wlr_randr_outputs(current=PREFERRED_4K))

    plan = script.plan(state=state, **WANTED_MODE)

    assert plan == {
        'action': 'apply',
        'connector': 'HDMI-A-1',
        'mode': '1920x1080@120.000000Hz',
        'reason': (
            'HDMI-A-1: 3840x2160@60.000000Hz at scale 1.0 to 1920x1080@120.000000Hz at scale 1.0'
        ),
    }


def test_a_labwc_session_already_in_the_mode_is_left_alone():
    """As captured (the owner's kanshi set 1080p at 120 Hz), nothing is applied."""
    script = load_set_display_mode()
    state = script.state_from_wlr_randr(wlr_randr_outputs())

    assert script.plan(state=state, **WANTED_MODE)['action'] == 'none'


def test_a_wlr_randr_mode_names_its_rate_as_reported():
    """Six decimals: wlr-randr reports rates to the millihertz.

    So a 120.040001 Hz mode keeps its own name and is never confused with the 120.000 one.
    """
    script = load_set_display_mode()

    assert script.wlr_randr_mode_id({'width': 1920, 'height': 1080, 'refresh': 120.040001}) == (
        '1920x1080@120.040001Hz'
    )


def test_a_disabled_output_is_not_a_monitor():
    """wlr-randr lists outputs that are off; only the ones showing anything are planned."""
    script = load_set_display_mode()
    outputs = wlr_randr_outputs(current=PREFERRED_4K)
    outputs.append({**outputs[0], 'name': 'HDMI-A-2', 'enabled': False})

    plan = script.plan(state=script.state_from_wlr_randr(outputs), **WANTED_MODE)

    assert (plan['action'], plan['connector']) == ('apply', 'HDMI-A-1')


def test_two_labwc_outputs_are_left_as_they_are():
    """As on GNOME: two monitors showing are the owner's arrangement, not the runner's."""
    script = load_set_display_mode()
    outputs = wlr_randr_outputs()
    outputs.append({**outputs[0], 'name': 'HDMI-A-2'})

    assert script.plan(state=script.state_from_wlr_randr(outputs), **WANTED_MODE)['action'] == (
        'skip'
    )


def test_a_labwc_output_at_another_scale_is_set_back_to_1():
    """1080p at a scale other than 1 is not the mode the runner measures in."""
    script = load_set_display_mode()
    outputs = wlr_randr_outputs()
    outputs[0]['scale'] = 1.5

    assert script.plan(state=script.state_from_wlr_randr(outputs), **WANTED_MODE)['action'] == (
        'apply'
    )


def test_with_no_wanted_rate_offered_the_highest_at_that_size_is_chosen():
    """Asking for 144 Hz, which no board offers, still gets 1080p at its best rate."""
    script = load_set_display_mode()
    ((_, modes, _),) = mutter_state('raspberry-pi-4')[1]

    mode = script.chosen_mode(modes=modes, width=1920, height=1080, refresh_rates=[144.0])

    assert mode[0] == '1920x1080@120.000'


def test_a_size_the_monitor_does_not_offer_chooses_nothing():
    """No mode at that size: nothing to choose."""
    script = load_set_display_mode()
    ((_, modes, _),) = mutter_state('raspberry-pi-5')[1]

    assert script.chosen_mode(modes=modes, width=5120, height=2880, refresh_rates=[60.0]) is None


@pytest.mark.parametrize(
    ('board', 'mode_id'),
    [('raspberry-pi-5', '1920x1080@120.000'), ('raspberry-pi-4', '1920x1080@120.000')],
)
def test_the_ci_users_4k_session_is_planned_to_1080p(board, mode_id):
    """The CI user's 3840x2160 session at scale 1.5 is planned to 1080p at 120 Hz on HDMI-1."""
    script = load_set_display_mode()
    state = mutter_state(board)

    plan = script.plan(state=state, **WANTED_MODE)

    assert plan['action'] == 'apply'
    assert plan['mode'] == mode_id
    assert plan['connector'] == 'HDMI-1'


def test_a_session_already_in_the_mode_is_left_alone():
    """Run again once the mode is in place, nothing is applied."""
    script = load_set_display_mode()
    serial, monitors, _logical, properties = mutter_state('raspberry-pi-5')
    ((spec, modes, monitor_properties),) = monitors
    modes = [
        (mode[0], *mode[1:6], {'is-current': True} if mode[0] == '1920x1080@120.000' else {})
        for mode in modes
    ]
    state = (
        serial,
        [(spec, modes, monitor_properties)],
        [(0, 0, 1.0, 0, True, [spec], {})],
        properties,
    )

    plan = script.plan(state=state, **WANTED_MODE)

    assert plan['action'] == 'none'
    assert plan['mode'] == '1920x1080@120.000'


def test_more_than_one_monitor_is_left_as_it_is():
    """With two monitors there is no one display to set: the plan says so and changes nothing."""
    script = load_set_display_mode()
    serial, monitors, logical, properties = mutter_state('raspberry-pi-5')

    plan = script.plan(state=(serial, monitors * 2, logical, properties), **WANTED_MODE)

    assert plan['action'] == 'skip'
    assert '2 monitors' in plan['reason']


def test_a_monitor_without_the_size_fails_the_run():
    """Asked for a size the monitor can't show, the plan says it can't, by name."""
    script = load_set_display_mode()

    plan = script.plan(
        state=mutter_state('raspberry-pi-4'), width=5120, height=2880, refresh_rates=[60.0]
    )

    assert plan['action'] == 'fail'
    assert '5120x2880' in plan['reason']


def test_the_script_needs_no_gi_to_plan():
    """PyGObject is the Pi's (the desktop's python3-gi); loading the script to plan needs none."""
    assert (
        'from gi' not in PLAN_DISPLAY_MODE_PATH.read_text(encoding='utf-8').split('def main', 1)[0]
    )


def test_the_planner_only_reads():
    """It reads mutter's state and changes nothing: gdctl applies the mode.

    The owner, 2026-11-14: GNOME reverts what isn't set through its own tools. mutter's
    ApplyMonitorsConfig called directly was reverted after 20 s (the 16 GB Pi 5's journal,
    22:27:23 to 22:27:43).
    """
    source = PLAN_DISPLAY_MODE_PATH.read_text(encoding='utf-8')

    assert 'ApplyMonitorsConfig' not in source
    assert 'subprocess' not in source


def display_block() -> dict[str, Any]:
    """Return the shared display tasks' block that sets the runner's display mode.

    Returns:
        The block.

    """
    return task(
        role_tasks('raspberry_pi_desktop', 'display_mode.yml'), "Set the runner's display mode"
    )


def display_settings(os_name: str) -> dict[str, Any]:
    """Return what one OS's desktop tasks hand the shared display tasks.

    Returns:
        The variables its include passes.

    """
    include = task(
        role_tasks('raspberry_pi_desktop', f'{os_name}.yml'), "Set up the runner's display mode"
    )
    assert include['ansible.builtin.include_tasks'] == 'display_mode.yml'
    return include['vars']


def rendered_display(value: Any, *, os_name: str, host: str) -> Any:
    """Render a shared display task's value as a Pi of an OS sees it.

    Returns:
        The value, its templates filled with the host's and the OS's variables.

    """
    variables = {
        **raspberry_pi_hosts()[host],
        **display_settings(os_name),
        'raspberry_pi_runner_user': {'uid': 1001},
        'raspberry_pi_runner_home': '/home/circleci',
    }
    if isinstance(value, str):
        rendered = render(value, **variables)
        # A value that is one template of a list or dict (an argv, an environment) is that list
        # or dict, whose own templates Ansible fills too; anything else stays text
        if value.startswith('{{') and value.endswith('}}') and rendered[:1] in {'[', '{'}:
            return rendered_display(ast.literal_eval(rendered), os_name=os_name, host=host)
        return rendered
    if isinstance(value, list):
        return [rendered_display(each, os_name=os_name, host=host) for each in value]
    if isinstance(value, dict):
        return {
            key: rendered_display(each, os_name=os_name, host=host) for key, each in value.items()
        }
    return value


class OsDisplay(BaseModel):
    """What one OS's desktop gives the shared display tasks, as its Pi sees it rendered."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    host: str
    wrapper: str
    environment: dict[str, str]
    settle_seconds: int
    check_argv: list[str]


# Each OS's way of setting the mode (plans/2026-11-04-raspberry-pi-ci-runner.md): GNOME's gdctl,
# reverted after 20 s unless confirmed, so waited out; labwc's wlr-randr, kept once set
OS_DISPLAY = {
    'ubuntu': OsDisplay(
        host=PI4,
        wrapper='apply_display_mode',
        environment={
            'XDG_RUNTIME_DIR': '/run/user/1001',
            'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/user/1001/bus',
        },
        settle_seconds=25,
        check_argv=[
            '/usr/bin/python3',
            '/usr/local/lib/glitchygames/plan_display_mode.py',
            '--width',
            '1920',
            '--height',
            '1080',
            '--refresh-rates',
            '120.0',
        ],
    ),
    'raspberry_pi_os': OsDisplay(
        host=PI5_16GB_RASPBERRY_PI_OS,
        wrapper='apply_labwc_display_mode',
        environment={'XDG_RUNTIME_DIR': '/run/user/1001', 'WAYLAND_DISPLAY': 'wayland-0'},
        settle_seconds=0,
        check_argv=[
            '/bin/sh',
            '-c',
            (
                'wlr-randr --json | /usr/bin/python3'
                ' /usr/local/lib/glitchygames/plan_display_mode.py'
                ' --width 1920 --height 1080 --refresh-rates 120.0 --wlr-randr-json -'
            ),
        ],
    ),
}


APPLY_DISPLAY_MODE_PATH = ROLES / 'raspberry_pi_desktop' / 'files' / 'apply_display_mode'
APPLY_DISPLAY_MODE_ARGV = [
    '/usr/local/lib/glitchygames/apply_display_mode',
    '{{ raspberry_pi_display_mode.width }}',
    '{{ raspberry_pi_display_mode.height }}',
    "{{ raspberry_pi_display_mode.refresh_rates | join(',') }}",
]


def test_the_planner_prints_a_line_the_shell_can_split():
    """The words form: action, connector, mode; a dash for what a plan doesn't name."""
    script = load_set_display_mode()

    assert script.plan_words(script.plan(state=mutter_state('raspberry-pi-4'), **WANTED_MODE)) == (
        'apply HDMI-1 1920x1080@120.000'
    )
    assert script.plan_words({'action': 'skip', 'connector': None, 'mode': None}) == 'skip - -'


def run_apply_display_mode(tmp_path: Path, *, plan_line: str, planner_status: int = 0) -> tuple:
    """Run the real wrapper beside a stand-in planner, with a stand-in gdctl first on PATH.

    The planner prints the plan line it is given (and exits with the status given); gdctl writes
    its arguments to a file. The wrapper finds the planner beside itself and gdctl on PATH, as
    on a Pi.

    Returns:
        (the wrapper's exit status, its output, gdctl's arguments or None when it never ran).

    """
    library = tmp_path / 'library'
    tools = tmp_path / 'tools'
    library.mkdir()
    tools.mkdir()
    wrapper = library / 'apply_display_mode'
    wrapper.write_text(APPLY_DISPLAY_MODE_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    wrapper.chmod(0o755)
    planner = library / 'plan_display_mode.py'
    planner.write_text(
        f'import sys\nprint({plan_line!r})\nsys.exit({planner_status})\n', encoding='utf-8'
    )
    calls = tmp_path / 'gdctl-arguments'
    gdctl = tools / 'gdctl'
    gdctl.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > {calls}\n', encoding='utf-8')
    gdctl.chmod(0o755)
    result = run_command(
        command=[str(wrapper), '1920', '1080', '120.0'],
        environment={'PATH': f'{tools}:{os.environ["PATH"]}'},
        timeout_seconds=30,
        capture_output=OutputCapture.APART,
    )
    arguments = calls.read_text(encoding='utf-8').splitlines() if calls.exists() else None
    return result.returncode, result.stdout, arguments


@NEEDS_A_POSIX_SHELL
def test_the_wrapper_sets_a_planned_mode_with_gdctl_temporarily(tmp_path):
    """On apply, gdctl sets the planned connector and mode, temporarily.

    Not --persistent: a persistent change waits for someone to click Keep and reverts after 20 s
    (2026-11-14), while a temporary one never asks.
    """
    status, output, arguments = run_apply_display_mode(
        tmp_path, plan_line='apply HDMI-1 1920x1080@120.000'
    )

    assert status == 0
    assert output.splitlines() == ['apply HDMI-1 1920x1080@120.000']
    assert arguments == [
        'set',
        '--logical-monitor',
        '--primary',
        '--scale',
        '1',
        '--monitor',
        'HDMI-1',
        '--mode',
        '1920x1080@120.000',
    ]


@pytest.mark.parametrize('plan_line', ['none HDMI-1 1920x1080@120.000', 'skip - -'])
@NEEDS_A_POSIX_SHELL
def test_the_wrapper_leaves_a_settled_or_skipped_display_alone(tmp_path, plan_line):
    """Nothing to apply: gdctl never runs, and the wrapper succeeds."""
    status, output, arguments = run_apply_display_mode(tmp_path, plan_line=plan_line)

    assert (status, output.splitlines(), arguments) == (0, [plan_line], None)


APPLY_LABWC_DISPLAY_MODE_PATH = (
    ROLES / 'raspberry_pi_desktop' / 'files' / 'apply_labwc_display_mode'
)


def run_apply_labwc_display_mode(
    tmp_path: Path, *, outputs: list[dict[str, Any]] | None
) -> tuple[int, str, list[str] | None]:
    """Run the real labwc wrapper beside the real planner, with a stand-in wlr-randr on PATH.

    The stand-in prints the outputs given for ``--json`` (or, given None, fails as wlr-randr
    does with no Wayland session) and writes any other call's arguments to a file: that is the
    mode being set.

    Returns:
        (the wrapper's exit status, its output, the setting call's arguments or None).

    """
    library = tmp_path / 'library'
    tools = tmp_path / 'tools'
    library.mkdir()
    tools.mkdir()
    for source in (APPLY_LABWC_DISPLAY_MODE_PATH, PLAN_DISPLAY_MODE_PATH):
        copy = library / source.name
        copy.write_text(source.read_text(encoding='utf-8'), encoding='utf-8')
        copy.chmod(0o755)
    reported = tmp_path / 'outputs.json'
    calls = tmp_path / 'wlr-randr-arguments'
    if outputs is None:
        json_reply = 'echo "failed to connect to display" >&2; exit 1'
    else:
        reported.write_text(json.dumps(outputs), encoding='utf-8')
        json_reply = f'cat {reported}; exit 0'
    wlr_randr = tools / 'wlr-randr'
    wlr_randr.write_text(
        f'#!/bin/sh\nif [ "$1" = --json ]; then {json_reply}; fi\nprintf "%s\\n" "$@" > {calls}\n',
        encoding='utf-8',
    )
    wlr_randr.chmod(0o755)
    result = run_command(
        command=[str(library / APPLY_LABWC_DISPLAY_MODE_PATH.name), '1920', '1080', '120.0'],
        environment={'PATH': f'{tools}:{os.environ["PATH"]}'},
        timeout_seconds=30,
        capture_output=OutputCapture.APART,
    )
    arguments = calls.read_text(encoding='utf-8').splitlines() if calls.exists() else None
    return result.returncode, result.stdout, arguments


@NEEDS_A_POSIX_SHELL
def test_the_labwc_wrapper_sets_the_4k_session_to_1080p_at_120_hz_scale_1(tmp_path):
    """From the Pi's own wlr-randr report to the exact call that sets 1080p at 120 Hz, scale 1."""
    status, output, arguments = run_apply_labwc_display_mode(
        tmp_path, outputs=wlr_randr_outputs(current=PREFERRED_4K)
    )

    assert status == 0
    assert output.splitlines() == ['apply HDMI-A-1 1920x1080@120.000000Hz']
    assert arguments == ['--output', 'HDMI-A-1', '--mode', '1920x1080@120.000000Hz', '--scale', '1']


@NEEDS_A_POSIX_SHELL
def test_the_labwc_wrapper_leaves_a_settled_display_alone(tmp_path):
    """Already 1080p at 120 Hz: nothing is set, and it succeeds."""
    status, output, arguments = run_apply_labwc_display_mode(tmp_path, outputs=wlr_randr_outputs())

    assert (status, output.splitlines(), arguments) == (
        0,
        ['none HDMI-A-1 1920x1080@120.000000Hz'],
        None,
    )


@NEEDS_A_POSIX_SHELL
def test_the_labwc_wrapper_skips_when_no_labwc_session_runs(tmp_path):
    """Before the runner's session exists (a first deploy, before the reboot), nothing is set.

    Nothing to plan, and the deploy goes on, as GNOME's does without a session.
    """
    status, output, arguments = run_apply_labwc_display_mode(tmp_path, outputs=None)

    assert (status, output.splitlines(), arguments) == (0, ['skip - -'], None)


@NEEDS_A_POSIX_SHELL
def test_the_labwc_wrapper_fails_when_the_monitor_has_no_1080p(tmp_path):
    """A monitor that can't show the size fails the deploy, and nothing is set."""
    outputs = wlr_randr_outputs(current=PREFERRED_4K)
    outputs[0]['modes'] = [
        mode for mode in outputs[0]['modes'] if (mode['width'], mode['height']) != (1920, 1080)
    ]

    status, output, arguments = run_apply_labwc_display_mode(tmp_path, outputs=outputs)

    assert status == 1
    assert output.splitlines() == ['fail HDMI-A-1 -']
    assert arguments is None


@NEEDS_A_POSIX_SHELL
def test_the_wrapper_fails_when_the_plan_fails(tmp_path):
    """A planner that can't plan fails the wrapper, and gdctl never runs."""
    status, _output, arguments = run_apply_display_mode(
        tmp_path, plan_line='fail HDMI-1 -', planner_status=1
    )

    assert status != 0
    assert arguments is None


def test_nothing_in_the_desktop_role_asks_for_a_persistent_change():
    """Nothing in the desktop role asks gdctl for a persistent change.

    --persistent reverted on every Pi it ran on once. The 16 GB Pi 5 held only because it ran
    twice within the 20 s, which made the revert restore 1080p itself (2026-11-14 journals).
    """
    role = ROLES / 'raspberry_pi_desktop'
    files = [path for path in role.rglob('*') if path.is_file() and '__pycache__' not in path.parts]
    texts = [path.read_text(encoding='utf-8') for path in files]

    assert texts
    assert not any('--persistent' in text for text in texts)


@pytest.mark.parametrize('os_name', list(OS_DISPLAY))
def test_the_display_is_set_as_the_ci_user_in_its_session(os_name):
    """Every step runs as the CI user, in its session: GNOME's D-Bus, or labwc's Wayland socket."""
    block = display_block()
    expected = OS_DISPLAY[os_name]

    assert block['become'] is True
    assert block['become_user'] == '{{ ci_user }}'
    assert (
        rendered_display(block['environment'], os_name=os_name, host=expected.host)
        == expected.environment
    )


@pytest.mark.parametrize('os_name', list(OS_DISPLAY))
def test_the_planner_and_wrapper_are_installed_side_by_side(os_name):
    """Both in /usr/local/lib/glitchygames, where the wrapper looks for the planner.

    One planner for both desktops, each desktop's own wrapper.
    """
    tasks = role_tasks('raspberry_pi_desktop', 'display_mode.yml')
    expected = OS_DISPLAY[os_name]
    wrapper = rendered_display(
        task(tasks, 'Install the display mode wrapper')['ansible.builtin.copy'],
        os_name=os_name,
        host=expected.host,
    )

    assert task(tasks, 'Install the display mode planner')['ansible.builtin.copy'] == {
        'src': 'plan_display_mode.py',
        'dest': '/usr/local/lib/glitchygames/plan_display_mode.py',
        'mode': '0755',
    }
    assert wrapper == {
        'src': expected.wrapper,
        'dest': f'/usr/local/lib/glitchygames/{expected.wrapper}',
        'mode': '0755',
    }
    assert (ROLES / 'raspberry_pi_desktop' / 'files' / expected.wrapper).is_file()


@pytest.mark.parametrize('os_name', list(OS_DISPLAY))
def test_each_login_applies_the_mode_through_the_desktops_autostart(os_name):
    """The CI user's autostart entry runs its desktop's wrapper with the inventory's mode.

    At each login: GNOME reads ~/.config/autostart, and so does labwc's lxsession-xdg-autostart
    (not ~/.config/labwc/autostart, which labwc reads instead of the system's).
    """
    tasks = role_tasks('raspberry_pi_desktop', 'display_mode.yml')
    expected = OS_DISPLAY[os_name]
    directory = task(tasks, "Create the runner's autostart directory")['ansible.builtin.file']
    entry_task = task(tasks, 'Apply the display mode at each login')
    entry = entry_task['ansible.builtin.copy']

    assert directory == {
        'path': '{{ raspberry_pi_runner_home }}/.config/autostart',
        'state': 'directory',
        'owner': '{{ ci_user }}',
        'group': '{{ ci_user }}',
        'mode': '0755',
    }
    assert entry['dest'] == (
        '{{ raspberry_pi_runner_home }}/.config/autostart/glitchygames-display-mode.desktop'
    )
    assert (entry['owner'], entry['group'], entry['mode']) == (
        '{{ ci_user }}',
        '{{ ci_user }}',
        '0644',
    )
    # The task's own variable, as Ansible fills it in before the content
    content = entry['content'].replace(
        '{{ raspberry_pi_display_exec }}', entry_task['vars']['raspberry_pi_display_exec']
    )
    lines = rendered_display(content, os_name=os_name, host=expected.host).splitlines()
    assert '[Desktop Entry]' in lines
    assert 'Type=Application' in lines
    assert f'Exec=/usr/local/lib/glitchygames/{expected.wrapper} 1920 1080 120.0' in lines


@pytest.mark.parametrize('os_name', list(OS_DISPLAY))
def test_a_deploy_applies_the_mode_as_a_login_would_then_proves_it_held(os_name):
    """The same wrapper, then a wait past any revert and a fresh plan that must be none.

    GNOME reverts an unconfirmed mode after 20 s; labwc keeps one.
    """
    steps = display_block()['block']
    expected = OS_DISPLAY[os_name]
    applying = task(steps, 'Apply the display mode as a login does')
    wait = task(steps, "Wait past the desktop's revert")
    check = task(steps, 'Check the mode held')
    applied_for_real = 'raspberry_pi_display_applied.changed and not ansible_check_mode'

    assert [step['name'] for step in steps] == [
        'Apply the display mode as a login does',
        "Wait past the desktop's revert",
        'Check the mode held',
    ]
    assert rendered_display(
        applying['ansible.builtin.command']['argv'], os_name=os_name, host=expected.host
    ) == [f'/usr/local/lib/glitchygames/{expected.wrapper}', '1920', '1080', '120.0']
    assert applying['changed_when'] == "raspberry_pi_display_applied.stdout.startswith('apply ')"
    assert rendered_display(wait['ansible.builtin.pause'], os_name=os_name, host=expected.host) == {
        'seconds': str(expected.settle_seconds)
    }
    assert wait['when'] == f'{applied_for_real} and raspberry_pi_display_settle_seconds | int > 0'
    assert (
        rendered_display(
            check['ansible.builtin.command']['argv'], os_name=os_name, host=expected.host
        )
        == expected.check_argv
    )
    assert check['failed_when'] == (
        "(raspberry_pi_display_check.stdout | from_json).action != 'none'"
    )
    assert check['when'] == applied_for_real


def test_every_pi_asks_for_1080p_at_120():
    """The inventory's mode, for every Pi (one monitor, shared through a switch)."""
    for host, variables in raspberry_pi_hosts().items():
        assert variables['raspberry_pi_display_mode'] == WANTED_MODE, host


def test_the_first_builds_display_script_is_removed():
    """The first build installed set_display_mode.py (2026-11-14); the planner replaced it."""
    removal = task(
        role_tasks('raspberry_pi_desktop', 'ubuntu.yml'), 'Remove the replaced display script'
    )

    assert removal['ansible.builtin.file'] == {
        'path': '/usr/local/lib/glitchygames/set_display_mode.py',
        'state': 'absent',
    }


# --- CircleCI's package repository ---------------------------------------------------------


def runner_play_tasks() -> list[dict[str, Any]]:
    """Return the runner play's tasks.

    Returns:
        The tasks, in order.

    """
    return plays()[0]['tasks']


def test_circleci_runner_repository_is_declared_not_scripted():
    """Ansible's own repository module, which reports a change only when something changed.

    packagecloud's install script, piped to bash, ran on every deploy: its creates: named
    circleci_runner.list, but with ?any=true the script writes circleci_runner_any.list (the Pis,
    2026-11-14), so creates: never matched.
    """
    repository = task(runner_play_tasks(), "Add CircleCI's package repository")

    assert repository['ansible.builtin.deb822_repository'] == {
        'name': 'circleci_runner',
        'types': ['deb'],
        'uris': ['https://packagecloud.io/circleci/runner/any/'],
        'suites': ['any'],
        'components': ['main'],
        # Redirects to the key file; the same two fingerprints the script's keyring held:
        # 81F73EBF5373FB699904EA158CD45F21E87AC85C and its subkey
        # FD7A3274C654790BD61C06ACB450FEA075A11BD3
        'signed_by': 'https://packagecloud.io/circleci/runner/gpgkey',
    }
    assert repository['register'] == 'raspberry_pi_circleci_repository'
    assert 'packagecloud.io/install/repositories' not in PLAYBOOK_PATH.read_text(encoding='utf-8')


def test_the_scripts_repository_files_are_removed_before_the_declared_one_is_added():
    """The script's files go first: apt refuses one repository listed twice with two keys."""
    names = [each['name'] for each in runner_play_tasks()]
    removal = task(runner_play_tasks(), "Remove the install script's repository files")

    assert removal['ansible.builtin.file'] == {'path': '{{ item }}', 'state': 'absent'}
    assert removal['loop'] == [
        '/etc/apt/sources.list.d/circleci_runner_any.list',
        '/etc/apt/keyrings/circleci_runner-archive-keyring.gpg',
    ]
    assert names.index("Remove the install script's repository files") < names.index(
        "Add CircleCI's package repository"
    )


def test_apts_lists_are_refreshed_only_when_the_repository_changed():
    """A new or changed repository needs fresh package lists before the runner installs."""
    names = [each['name'] for each in runner_play_tasks()]
    refresh = task(runner_play_tasks(), "Refresh the package lists for CircleCI's repository")

    assert refresh['ansible.builtin.apt'] == {'update_cache': True}
    assert refresh['when'] == 'raspberry_pi_circleci_repository.changed'
    assert (
        names.index("Add CircleCI's package repository")
        < names.index("Refresh the package lists for CircleCI's repository")
        < names.index('Install machine runner 3')
    )


def test_the_repository_modules_own_dependency_is_installed():
    """deb822_repository needs python3-debian on the Pi."""
    packages = task(
        runner_play_tasks(), 'Install what the checkout, the tests and the source builds need'
    )

    assert 'python3-debian' in packages['ansible.builtin.apt']['name']


# --- Each Pi's cooling ---------------------------------------------------------------------

REQUIREMENTS_PATH = PROJECT_ROOT / 'docs' / 'data' / 'requirements.json'
# The requirements page's platforms that are inventory hosts (the 8 GB Pi 5 isn't on it yet)
REQUIREMENTS_PLATFORM_OF_HOST = {PI4: 'raspberry-pi-4', PI5_16GB: 'raspberry-pi-5'}


@pytest.mark.parametrize(
    ('host', 'cooling'),
    [
        # No fan; passive heatsinks since 2026-11-20 (it had no cooling when read, 2026-11-14)
        (PI4, 'Passive (heatsinks)'),
        # The official Raspberry Pi 5 case with its fan
        (PI5_8GB, 'Active cooling; the official cooled case'),
        # The Active Cooler, booting from an NVMe SSD in a case that is itself a heat sink
        (PI5_16GB, 'Active cooling; the NVMe case is a large heat sink'),
        # The same kind of case and fan (read 2026-11-16)
        (PI5_16GB_RASPBERRY_PI_OS, 'Active cooling; the NVMe case is a large heat sink'),
    ],
)
def test_each_pi_says_how_it_is_cooled(host, cooling):
    """The cooling as a whole (the fan role configures only the fan): its kind, in plain words."""
    assert raspberry_pi_hosts()[host]['raspberry_pi_cooling'] == cooling


def test_a_pi_without_a_fan_is_cooled_passively_or_not_at_all():
    """The cooling and the fan agree: no fan is passive or no added cooling, a fan is active."""
    for host, variables in raspberry_pi_hosts().items():
        no_fan = variables['raspberry_pi_fan']['kind'] == 'none'
        expected = ('None', 'Passive') if no_fan else ('Active',)
        assert variables['raspberry_pi_cooling'].startswith(expected), host


def test_the_requirements_page_describes_each_pis_cooling_as_the_inventory_does():
    """The page's Cooling row starts with the inventory's words (it may add a reading after)."""
    requirements = json.loads(REQUIREMENTS_PATH.read_text(encoding='utf-8'))
    cooling_by_platform = {
        platform['slug']: dict(platform.get('specs', [])).get('Cooling')
        for platform in requirements['platforms']
    }

    for host, platform in REQUIREMENTS_PLATFORM_OF_HOST.items():
        page = cooling_by_platform[platform]
        assert page is not None, f'{platform} has no Cooling row'
        assert page.startswith(raspberry_pi_hosts()[host]['raspberry_pi_cooling']), (host, page)


def test_every_raspberry_pi_on_the_requirements_page_is_mapped_to_a_host():
    """A Pi added to the page must be mapped here, so its cooling is checked too."""
    requirements = json.loads(REQUIREMENTS_PATH.read_text(encoding='utf-8'))
    pis_on_the_page = {
        platform['slug']
        for platform in requirements['platforms']
        if platform['slug'].startswith('raspberry-pi-')
    }

    assert pis_on_the_page == set(REQUIREMENTS_PLATFORM_OF_HOST.values())


def test_the_raspberry_pi_os_pi_is_reached_by_its_lasting_name_and_keeps_it():
    """Its address is a DHCP lease, so it is reached by its mDNS name, which stays its own.

    The playbook names each host, so its hostname is the one it has: any other would change the
    mDNS name it is reached by.
    """
    variables = raspberry_pi_hosts()[PI5_16GB_RASPBERRY_PI_OS]

    assert variables['ansible_host'] == 'glitchygames-pi5-16gb-raspberrypios.local'
    assert variables['raspberry_pi_hostname'] == 'glitchygames-pi5-16gb-raspberrypios'
    assert variables['raspberry_pi_resource_class'] == (
        'terrysimons/raspberry-pi-5-16gb-raspberry-pi-os'
    )


def test_the_16gb_ubuntu_pi_is_reached_by_its_mdns_name():
    """Its address is a DHCP lease (it moved after a power cut, 2026-11-20): reached by name."""
    variables = raspberry_pi_hosts()[PI5_16GB]

    assert variables['ansible_host'] == f'{variables["raspberry_pi_hostname"]}.local'


# --- The CPU governor ----------------------------------------------------------------------

GOVERNOR_UNIT_TASK = 'Install the unit that sets the CPU governor at boot'
GOVERNOR_TASKS = [
    'Read the governors the kernel offers',
    'Refuse a governor the kernel does not offer',
    GOVERNOR_UNIT_TASK,
    'Enable the governor unit and run it now',
    "Read every cpufreq policy's governor",
]
# Read on the 16 GB Pi 5, 2026-11-20 (cpu0's scaling_available_governors)
PI5_AVAILABLE_GOVERNORS = 'conservative ondemand userspace powersave performance schedutil'


def available_governors_content(text: str = PI5_AVAILABLE_GOVERNORS) -> str:
    """Return what slurp reports for the kernel's governor file: base64 of its text."""
    return base64.b64encode(f'{text}\n'.encode()).decode()


def test_only_the_16gb_pi5s_set_a_governor():
    """Unset elsewhere means untouched: only the 16 GB Pi 5s name one (the owner, 2026-11-20)."""
    governors = {
        host: variables.get('raspberry_pi_cpu_governor')
        for host, variables in raspberry_pi_hosts().items()
    }

    assert governors[PI5_16GB] == 'performance'
    assert governors[PI5_16GB_RASPBERRY_PI_OS] == 'performance'
    assert {host for host, governor in governors.items() if governor is not None} == {
        PI5_16GB,
        PI5_16GB_RASPBERRY_PI_OS,
    }


def test_every_governor_task_waits_for_a_governor_and_becomes_root():
    """No governor named, nothing done; each task writes /sys or /etc, so each becomes root."""
    tasks = role_tasks('raspberry_pi_firmware')

    for name in GOVERNOR_TASKS:
        found = task(tasks, name)
        assert found['when'] == 'raspberry_pi_cpu_governor is defined', name
        if name != 'Refuse a governor the kernel does not offer':
            assert found['become'] is True, name


@pytest.mark.parametrize(
    ('governor', 'offered'),
    [('performance', True), ('powersave', True), ('turbo', False), ('Performance', False)],
)
def test_a_governor_the_kernel_does_not_offer_is_refused(governor, offered):
    """The check reads the kernel's own list: a typo never reaches the unit."""
    (condition,) = task(role_tasks('raspberry_pi_firmware'), GOVERNOR_TASKS[1])[
        'ansible.builtin.assert'
    ]['that']
    variables = {
        'raspberry_pi_cpu_governor': governor,
        'raspberry_pi_available_governors': {'content': available_governors_content()},
    }

    assert holds(condition, **variables) is offered


def governor_unit(governor: str = 'performance') -> str:
    """Return the governor unit's rendered content."""
    content = task(role_tasks('raspberry_pi_firmware'), GOVERNOR_UNIT_TASK)['ansible.builtin.copy'][
        'content'
    ]
    return render(content, raspberry_pi_cpu_governor=governor)


def test_the_governor_unit_writes_the_governor_to_every_policy_at_boot():
    """A oneshot, kept as active, wanted by multi-user: it runs at every boot."""
    unit = governor_unit()

    assert 'Type=oneshot' in unit
    assert 'RemainAfterExit=yes' in unit
    assert 'WantedBy=multi-user.target' in unit
    assert 'for policy in /sys/devices/system/cpu/cpufreq/policy*; do' in unit
    assert 'echo performance > "$$policy/scaling_governor" || exit 1' in unit
    assert 'Description=Set the CPU governor to performance' in unit


def test_the_governor_units_shell_variable_survives_systemd():
    """Systemd expands $NAME in ExecStart itself: a shell variable must be written $$NAME."""
    exec_start = next(
        line for line in governor_unit().splitlines() if line.startswith('ExecStart=')
    )

    assert re.findall(r'(?<!\$)\$(?!\$)\w', exec_start) == []


def test_the_governor_unit_is_a_root_owned_system_unit():
    """It lives in /etc/systemd/system, owned by root, mode 0644."""
    copy = task(role_tasks('raspberry_pi_firmware'), GOVERNOR_UNIT_TASK)['ansible.builtin.copy']

    assert copy['dest'] == '/etc/systemd/system/raspberry-pi-cpu-governor.service'
    assert (copy['owner'], copy['mode']) == ('root', '0644')


def test_the_governor_unit_is_enabled_and_run_now_and_every_policy_is_checked_after():
    """No policy read, or any not on the governor, fails the run."""
    tasks = role_tasks('raspberry_pi_firmware')
    enable = task(tasks, GOVERNOR_TASKS[3])['ansible.builtin.systemd_service']
    check = task(tasks, GOVERNOR_TASKS[4])
    condition = check['failed_when']

    assert enable['name'] == 'raspberry-pi-cpu-governor'
    assert enable['enabled'] is True
    assert enable['daemon_reload'] is True
    assert 'cpufreq/policy*/scaling_governor' in check['ansible.builtin.shell']['cmd']
    assert holds(condition, raspberry_pi_applied_governors={'stdout_lines': []}, **host_governor())
    assert holds(
        condition,
        raspberry_pi_applied_governors={'stdout_lines': ['performance', 'schedutil']},
        **host_governor(),
    )
    assert not holds(
        condition,
        raspberry_pi_applied_governors={'stdout_lines': ['performance'] * 4},
        **host_governor(),
    )


def host_governor() -> dict[str, str]:
    """Return the governor the checks compare with."""
    return {'raspberry_pi_cpu_governor': 'performance'}


def test_a_changed_unit_is_restarted_so_the_new_governor_applies_now():
    """A new governor must apply on this run, not at the next boot."""
    state = task(role_tasks('raspberry_pi_firmware'), GOVERNOR_TASKS[3])[
        'ansible.builtin.systemd_service'
    ]['state']

    assert render(state, raspberry_pi_governor_unit={'changed': True}) == 'restarted'
    assert render(state, raspberry_pi_governor_unit={'changed': False}) == 'started'


# --- hidapi's source build, on every Pi ----------------------------------------------------


def test_every_pi_gets_what_hidapis_source_build_needs():
    """The libusb and libudev headers, on every OS: uv builds hidapi from source on Linux ARM.

    hidapi's Linux ARM wheels are for Python 3.14 only, so on 3.15 uv compiles it: its hid
    extension finds libusb through pkg-config, its hidraw extension includes libudev.h. Found on
    Raspberry Pi OS, then checked by hand on Ubuntu (the owner, 2026-11-17: "I installed them
    manually and verified that those packages are needed on ubuntu"). libusb-1.0-0-dev, not
    libusb-dev, which is the old libusb 0.1.
    """
    packages = task(
        runner_play_tasks(), 'Install what the checkout, the tests and the source builds need'
    )['ansible.builtin.apt']['name']

    assert {'libusb-1.0-0-dev', 'libudev-dev'} <= set(packages)
    assert 'libusb-dev' not in packages


def test_no_os_group_lists_packages_of_its_own():
    """Every Pi installs one list: no OS needs a package the other doesn't (2026-11-17)."""
    for group in inventory_group('raspberry_pis')['children'].values():
        assert 'raspberry_pi_os_packages' not in group['vars']
    assert "Install what this Pi's OS needs besides" not in [
        each.get('name') for each in plays()[0]['tasks']
    ]


# --- HDMI audio on the Ubuntu Pi 5s --------------------------------------------------------

APPLY_HDMI_AUDIO_PATH = ROLES / 'raspberry_pi_audio' / 'files' / 'apply_hdmi_audio.py'
PIPEWIRE_FIXTURES = PROJECT_ROOT / 'tests' / 'fixtures' / 'pipewire'
HDMI_AUDIO_DROP_IN_TASK = "Install the HDMI audio defaults for every user's WirePlumber"
HDMI_AUDIO_APPLY_TASK = (
    "Set each session's HDMI outputs to the volume, unmuted, with an HDMI default"
)
HDMI_AUDIO_CHECK_TASK = "Check each session's HDMI outputs held"
# Read on the 16 GB Pi 5, 2026-11-20 (its HDMI0 sink, in the deploy user's session)
PI5_HDMI0_SINK = 'alsa_output.platform-107c701400.hdmi.hdmi-stereo'


def audio_tasks() -> list[dict[str, Any]]:
    """Return the audio role's tasks.

    Returns:
        The tasks.

    """
    return role_tasks('raspberry_pi_audio')


def audio_variables(host: str = PI5_16GB, **overrides: Any) -> dict[str, Any]:
    """Return what a host's audio tasks see: the role's defaults and the host's variables.

    The defaults' user list names the play's ci_user and deploy_user, which the play defines.

    Returns:
        The variables.

    """
    defaults = yaml_file(ROLES / 'raspberry_pi_audio' / 'defaults' / 'main.yml')
    variables = {**defaults, **raspberry_pi_hosts()[host], **overrides}
    for name in ('raspberry_pi_hdmi_audio_config',):
        variables[name] = render(variables[name], **variables)
    return variables


def load_apply_hdmi_audio() -> Any:
    """Load the role's HDMI audio script by its path (it is copied to the Pi, not installed).

    Returns:
        The module.

    Raises:
        ImportError: When the file can't be loaded.

    """
    specification = importlib.util.spec_from_file_location(
        'apply_hdmi_audio', APPLY_HDMI_AUDIO_PATH
    )
    if specification is None or specification.loader is None:
        raise ImportError(APPLY_HDMI_AUDIO_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def pw_dump(host: str) -> list[dict[str, Any]]:
    """Return a Pi's captured pw-dump: the deploy user's session, 2026-11-20.

    The capture keeps what the script reads (the audio devices and nodes and the ``default``
    metadata) of ``pw-dump`` run as the deploy user over ssh: on the 16 GB Pi 5, whose seat the
    owner held, HDMI0's sink with HDMI1's card on its ``off`` profile (no display on HDMI1); on
    the 8 GB Pi 5, whose seat the CI user held, no sound card at all (only ``auto_null``).

    Returns:
        The objects.

    """
    path = PIPEWIRE_FIXTURES / f'{host}-deploy-user-pw-dump.json'
    return json.loads(path.read_text(encoding='utf-8'))


class FakePipeWire:
    """A session's PipeWire as pw-dump and wpctl show it, from a capture, and what was run.

    Built on wpctl's contract (src/tools/wpctl.c, 0.5.13): get-volume prints ``Volume: %.2f``
    and `` [MUTED]``; set-volume's ``N%`` is N / 100 on the cubic scale; set-profile brings the
    card's sink (a copy of the captured HDMI0 sink with the card's ``alsa.id``).
    """

    def __init__(
        self,
        objects: list[dict[str, Any]],
        *,
        volumes: dict[int, tuple[float, bool]] | None = None,
        volume_that_sticks: float | None = None,
    ) -> None:
        """Hold the objects, each sink's volume (default: as captured, 1.00 unmuted)."""
        self.objects = json.loads(json.dumps(objects))
        self.volumes = dict(volumes or {})
        self.volume_that_sticks = volume_that_sticks
        self.commands: list[list[str]] = []

    def node(self, node_id: int) -> dict[str, Any]:
        """Return the object with an id."""
        (found,) = [item for item in self.objects if item['id'] == node_id]
        return found

    def run(self, argv: list[str]) -> str:
        """Answer a command as pw-dump or wpctl would.

        Returns:
            Its output.

        Raises:
            AssertionError: For a command the script has no business running.

        """
        self.commands.append(argv)
        match argv:
            case ['pw-dump']:
                return json.dumps(self.objects)
            case ['wpctl', 'get-volume', node_id]:
                level, muted = self.volumes.get(int(node_id), (1.0, False))
                return f'Volume: {level:.2f}{" [MUTED]" if muted else ""}\n'
            case ['wpctl', 'set-mute', node_id, '0']:
                level, _ = self.volumes.get(int(node_id), (1.0, False))
                self.volumes[int(node_id)] = (level, False)
            case ['wpctl', 'set-volume', node_id, percent]:
                _, muted = self.volumes.get(int(node_id), (1.0, False))
                level = int(percent.rstrip('%')) / 100
                if self.volume_that_sticks is not None:
                    level = self.volume_that_sticks
                self.volumes[int(node_id)] = (level, muted)
            case ['wpctl', 'set-default', node_id]:
                self.set_default(str(self.node(int(node_id))['info']['props']['node.name']))
            case ['wpctl', 'set-profile', device_id, _]:
                self.add_sink(card=self.node(int(device_id))['info']['props']['alsa.id'])
            case _:
                message = f'not a command the script may run: {argv}'
                raise AssertionError(message)
        return ''

    def set_default(self, name: str) -> None:
        """Make a sink the session's default."""
        for item in self.objects:
            if item['type'] == 'PipeWire:Interface:Metadata':
                for entry in item['metadata']:
                    if entry['key'] == 'default.audio.sink':
                        entry['value'] = {'name': name}

    def add_sink(self, *, card: str, node_id: int = 90) -> int:
        """Add a sink for a card, as WirePlumber makes one when its profile turns on.

        Returns:
            Its id.

        """
        (template,) = [
            item for item in pw_dump(PI5_16GB) if item['type'] == 'PipeWire:Interface:Node'
        ]
        sink = json.loads(json.dumps(template))
        sink['id'] = node_id
        sink['info']['props']['alsa.id'] = card
        sink['info']['props']['node.name'] = f'alsa_output.{card}.hdmi-stereo'
        self.objects.append(sink)
        return node_id

    def set_profile_available(self, *, card: str) -> None:
        """Offer a card's stereo HDMI profile, as connecting a display does, leaving it off."""
        for item in self.objects:
            if item['info' if 'info' in item else 'props'].get('props', {}).get('alsa.id') == card:
                item['info']['params']['EnumProfile'].append({
                    'index': 2,
                    'name': 'output:hdmi-stereo',
                    'available': 'yes',
                })

    def changes(self) -> list[list[str]]:
        """Return the commands that change something."""
        return [argv for argv in self.commands if argv[0] == 'wpctl' and argv[1] != 'get-volume']


def apply_hdmi_audio(pipewire: FakePipeWire, *, dry_run: bool = False) -> dict[str, Any]:
    """Run the script's apply on a fake session at 75%, never sleeping.

    Returns:
        Its report.

    """
    return load_apply_hdmi_audio().apply(
        volume_percent=75, dry_run=dry_run, run=pipewire.run, sleep=lambda _seconds: None
    )


def test_only_the_ubuntu_pi5s_set_an_hdmi_volume():
    """75% on both Ubuntu Pi 5s (the owner, 2026-11-20: not the procedure's 100%); none elsewhere.

    The procedure was proven on Ubuntu Pi 5s; the Pi 4 and Raspberry Pi OS keep their audio.
    """
    volumes = {
        host: variables.get('raspberry_pi_hdmi_audio_volume_percent')
        for host, variables in raspberry_pi_hosts().items()
    }

    assert {host: volume for host, volume in volumes.items() if volume is not None} == {
        PI5_8GB: 75,
        PI5_16GB: 75,
    }


def test_every_hdmi_audio_task_waits_for_a_volume():
    """No volume named, nothing done: every task of the role waits for it."""
    for found in audio_tasks():
        assert str(found['when']).startswith('raspberry_pi_hdmi_audio_volume_percent is defined'), (
            found['name']
        )


def test_every_hdmi_audio_write_becomes_root():
    """Files under /etc and /usr/local are root's: each task that writes one becomes root."""
    for found in audio_tasks():
        if {'ansible.builtin.copy', 'ansible.builtin.file'} & found.keys():
            assert found['become'] is True, found['name']
            assert found.get('become_user') is None, found['name']


@pytest.mark.parametrize(
    ('overrides', 'accepted'),
    [
        ({}, True),
        ({'raspberry_pi_hdmi_audio_volume_percent': 0}, True),
        ({'raspberry_pi_hdmi_audio_volume_percent': 100}, True),
        ({'raspberry_pi_hdmi_audio_volume_percent': 101}, False),
        ({'raspberry_pi_hdmi_audio_volume_percent': -1}, False),
        ({'raspberry_pi_hdmi_audio_volume_percent': '75'}, False),
        ({'raspberry_pi_hdmi_audio_volume_percent': 0.75}, False),
        ({'raspberry_pi_board': 'pi4'}, False),
        ({'raspberry_pi_os': 'raspberry_pi_os'}, False),
    ],
)
def test_hdmi_audio_settings_the_role_was_not_written_for_are_refused(overrides, accepted):
    """A whole percentage, on an Ubuntu Pi 5: a fraction (0.75) or a Pi 4 is refused."""
    conditions = task(audio_tasks(), 'Refuse HDMI audio settings this role was not written for')[
        'ansible.builtin.assert'
    ]['that']
    variables = audio_variables(**overrides)

    assert all(holds(condition, **variables) for condition in conditions) is accepted


@NEEDS_A_POSIX_SHELL
@pytest.mark.skipif(sys.platform == 'win32', reason='Ansible has no Windows control node')
@pytest.mark.parametrize(
    ('version_output', 'accepted'),
    [
        # wireplumber --version on the Pis, 2026-11-20 (26.04 and 26.10)
        (
            'wireplumber\nCompiled with libwireplumber 0.5.13\nLinked with libwireplumber 0.5.13',
            True,
        ),
        (
            'wireplumber\nCompiled with libwireplumber 0.5.17\nLinked with libwireplumber 0.5.17',
            True,
        ),
        (
            'wireplumber\nCompiled with libwireplumber 0.4.17\nLinked with libwireplumber 0.4.17',
            False,
        ),
        ('', False),
    ],
)
def test_a_wireplumber_older_than_0_5_is_refused(version_output, accepted, tmp_path):
    """The drop-in is SPA-JSON, which 0.5 reads; the check runs in Ansible itself.

    Its ``regex`` test, ``regex_search`` filter and ``version`` test are Ansible's, so the real
    ``ansible-playbook`` runs the role's task as written, on the version lines the Pis print.
    """
    check = dict(task(audio_tasks(), 'Refuse a WirePlumber older than 0.5'))
    del check['when']
    playbook = tmp_path / 'playbook.yml'
    playbook.write_text(
        yaml.safe_dump([
            {
                'hosts': 'localhost',
                'connection': 'local',
                'gather_facts': False,
                'vars': {
                    'ansible_python_interpreter': sys.executable,
                    'raspberry_pi_wireplumber_version': {
                        'stdout': version_output,
                        'stdout_lines': version_output.splitlines(),
                    },
                },
                'tasks': [check],
            }
        ]),
        encoding='utf-8',
    )

    result = run_command(
        command=[
            str(Path(sys.executable).parent / 'ansible-playbook'),
            '--inventory',
            'localhost,',
            str(playbook),
        ],
        environment={
            'PATH': os.environ['PATH'],
            'HOME': str(tmp_path),
            'ANSIBLE_HOME': str(tmp_path / 'ansible'),
            'ANSIBLE_LOCAL_TEMP': str(tmp_path / 'ansible-tmp'),
        },
        timeout_seconds=120,
        capture_output=OutputCapture.TOGETHER,
    )

    assert (result.returncode == 0) is accepted, result.stdout


def hdmi_audio_drop_in(**overrides: Any) -> str:
    """Return the WirePlumber drop-in as the 16 GB Pi 5 gets it.

    Returns:
        The file's text.

    """
    copy = task(audio_tasks(), HDMI_AUDIO_DROP_IN_TASK)['ansible.builtin.copy']
    return render(copy['content'], **audio_variables(**overrides))


def test_the_drop_in_starts_hdmi_sinks_at_75_percent_as_wpctl_reads_it():
    """The default sink volume is linear, the cube of wpctl's 0.75: 0.421875.

    WirePlumber's own default is 0.4 ^ 3, "40% on the cubic scale" (its settings page), and wpctl
    reads volumes on that cubic scale, so 0.421875 reads back as 0.75.
    """
    drop_in = hdmi_audio_drop_in()
    (volume,) = re.findall(
        r'^\s*device\.routes\.default-sink-volume = (\S+)$', drop_in, re.MULTILINE
    )

    assert volume == '0.421875'
    assert round(float(volume) ** (1 / 3), 2) == 0.75
    assert 'wireplumber.settings = {' in drop_in
    assert '75%' in drop_in


def test_the_drop_in_follows_the_inventorys_volume():
    """The volume is the inventory's, not a number written in the role."""
    drop_in = hdmi_audio_drop_in(raspberry_pi_hdmi_audio_volume_percent=40)

    assert 'device.routes.default-sink-volume = 0.064000' in drop_in


def test_the_drop_in_leaves_hdmi_sinks_unmuted_by_naming_no_mute():
    """A route WirePlumber remembers nothing of starts unmuted, so the drop-in sets no mute.

    /usr/share/wireplumber/scripts/device/apply-routes.lua, 0.5.13:
    ``props.mute = props.mute or false``.
    """
    assert 'mute' not in hdmi_audio_drop_in().replace('unmuted', '')


def test_the_drop_in_puts_hdmi0_ahead_of_hdmi1_and_behind_usb():
    """HDMI0's sink, matched by its card's alsa.id, outranks HDMI1's 1000 and no USB card (1100+).

    WirePlumber gives a PCM device 0 priority.session 1000 and a USB card 100 more
    (/usr/share/wireplumber/scripts/monitors/alsa.lua, 0.5.13); both captured HDMI sinks read
    1000. With no default chosen, the highest priority.session wins.
    """
    drop_in = hdmi_audio_drop_in()
    (priority,) = re.findall(r'priority\.session = (\d+)', drop_in)

    assert 'monitor.alsa.rules = [' in drop_in
    assert 'media.class = "Audio/Sink"' in drop_in
    assert 'alsa.id = "vc4hdmi0"' in drop_in
    assert 'vc4hdmi1' not in drop_in
    assert 1000 < int(priority) < 1100
    (captured_sink,) = [
        item for item in pw_dump(PI5_16GB) if item['type'] == 'PipeWire:Interface:Node'
    ]
    assert captured_sink['info']['props']['priority.session'] == 1000
    assert captured_sink['info']['props']['alsa.id'] == 'vc4hdmi0'


def test_the_drop_in_is_a_root_owned_system_wide_fragment():
    """In /etc/wireplumber/wireplumber.conf.d, which every user's WirePlumber reads."""
    copy = task(audio_tasks(), HDMI_AUDIO_DROP_IN_TASK)['ansible.builtin.copy']

    assert render(copy['dest'], **audio_variables()) == (
        '/etc/wireplumber/wireplumber.conf.d/60-glitchygames-hdmi-audio.conf'
    )
    assert (copy['owner'], copy['mode']) == ('root', '0644')


def test_hdmi_audio_is_set_in_the_ci_users_and_the_deploy_users_sessions():
    """The CI user's session and the deploy user's, each with its own remembered volumes.

    The runner's jobs play into the CI user's session; the owner plays in the deploy user's.
    """
    sessions = task(audio_tasks(), 'Read which users have a PipeWire session')

    assert sessions['loop'] == ['{{ ci_user }}', '{{ deploy_user }}']


@pytest.mark.parametrize('name', [HDMI_AUDIO_APPLY_TASK, HDMI_AUDIO_CHECK_TASK])
@pytest.mark.parametrize(
    ('user', 'uid', 'through_sudo'), [('circleci', '1001', True), ('terry', '1000', False)]
)
def test_the_live_tasks_run_as_each_user_in_their_own_session(name, user, uid, through_sudo):
    """Each user in their own runtime directory, and only where their PipeWire listens.

    The CI user is reached through sudo; the deploy user's item runs as the login user
    (become false), the playbook's rule (tests/test_ci_config.py), since Ansible skips sudo
    when the become user is the login user.
    """
    found = task(audio_tasks(), name)
    variables = {
        'ci_user': 'circleci',
        'item': {'item': user, 'stat': {'exists': True}},
        'ansible_facts': {'getent_passwd': {user: ['x', uid]}},
    }

    assert render(found['become'], **variables) == str(through_sudo)
    assert found['become_user'] == '{{ ci_user }}'
    assert render(found['environment']['XDG_RUNTIME_DIR'], **variables) == f'/run/user/{uid}'
    assert "selectattr('stat.exists')" in found['loop']


def test_a_user_with_no_session_is_reported_pending_not_failed():
    """No PipeWire socket, no wpctl: the run says pending and goes on."""
    say = task(audio_tasks(), "Say which users' HDMI audio is pending")

    assert "rejectattr('stat.exists')" in say['loop']
    assert 'pending: no active session for' in say['ansible.builtin.debug']['msg']
    stat = task(audio_tasks(), 'Read which users have a PipeWire session')['ansible.builtin.stat']
    assert (
        render(
            stat['path'],
            item='terry',
            ansible_facts={'getent_passwd': {'terry': ['x', '1000']}},
        )
        == '/run/user/1000/pipewire-0'
    )


@pytest.mark.parametrize(('check_mode', 'dry_run'), [(False, False), (True, True)])
def test_the_apply_task_does_check_mode_through_the_scripts_dry_run(check_mode, dry_run):
    """It always runs (check_mode: false); in check mode it only reports (--dry-run)."""
    found = task(audio_tasks(), HDMI_AUDIO_APPLY_TASK)
    argv = ast.literal_eval(
        render(
            found['ansible.builtin.command']['argv'],
            ansible_check_mode=check_mode,
            **audio_variables(),
        )
    )

    assert found['check_mode'] is False
    assert argv[:4] == [
        '/usr/bin/python3',
        '/usr/local/lib/glitchygames/apply_hdmi_audio.py',
        '--volume-percent',
        '75',
    ]
    assert ('--dry-run' in argv) is dry_run


def test_the_check_fails_while_anything_is_left_to_change():
    """A fresh dry run must find nothing to do, and the script must not report a problem."""
    found = task(audio_tasks(), HDMI_AUDIO_CHECK_TASK)
    condition = found['failed_when']

    assert '--dry-run' in found['ansible.builtin.command']['argv']
    assert holds(
        condition,
        raspberry_pi_hdmi_audio_check={'rc': 0, 'stdout': json.dumps({'actions': ['wpctl x']})},
    )
    assert holds(condition, raspberry_pi_hdmi_audio_check={'rc': 1, 'stdout': '{"actions": []}'})
    assert not holds(
        condition, raspberry_pi_hdmi_audio_check={'rc': 0, 'stdout': '{"actions": []}'}
    )


def test_the_reference_pis_hdmi0_at_100_percent_is_set_to_75_and_its_default_kept():
    """The 16 GB Pi 5 as captured: HDMI0 at 1.00 becomes 0.75; no display on HDMI1 is pending.

    Its default is HDMI0's sink already, a working HDMI default, so it is kept (no set-default).
    """
    pipewire = FakePipeWire(pw_dump(PI5_16GB))

    report = apply_hdmi_audio(pipewire)

    assert pipewire.changes() == [
        ['wpctl', 'set-mute', '73', '0'],
        ['wpctl', 'set-volume', '73', '75%'],
    ]
    assert report['changed'] is True
    assert report['problems'] == []
    hdmi0, hdmi1 = report['ports']
    assert hdmi0 == {
        'port': 'HDMI0',
        'sink': PI5_HDMI0_SINK,
        'before': {'level': 1.0, 'muted': False},
        'after': {'level': 0.75, 'muted': False},
    }
    assert hdmi1['port'] == 'HDMI1'
    assert 'no audio-capable display' in hdmi1['pending']
    assert report['default'] == {'before': PI5_HDMI0_SINK, 'after': PI5_HDMI0_SINK}


def test_a_second_run_changes_nothing():
    """Live settings are compared first: what already holds is not set again."""
    pipewire = FakePipeWire(pw_dump(PI5_16GB), volumes={73: (0.75, False)})

    report = apply_hdmi_audio(pipewire)

    assert pipewire.changes() == []
    assert report['changed'] is False
    assert report['actions'] == []


def test_a_muted_sink_at_the_volume_is_unmuted():
    """Muted at 0.75 is not the deployment's state."""
    pipewire = FakePipeWire(pw_dump(PI5_16GB), volumes={73: (0.75, True)})

    report = apply_hdmi_audio(pipewire)

    assert ['wpctl', 'set-mute', '73', '0'] in pipewire.changes()
    assert report['ports'][0]['after'] == {'level': 0.75, 'muted': False}


def test_a_dry_run_reads_and_changes_nothing():
    """--dry-run lists the commands and runs none of them."""
    pipewire = FakePipeWire(pw_dump(PI5_16GB))

    report = apply_hdmi_audio(pipewire, dry_run=True)

    assert pipewire.changes() == []
    assert report['changed'] is False
    assert report['actions'] == ['wpctl set-mute 73 0', 'wpctl set-volume 73 75%']


def test_a_session_whose_user_does_not_hold_the_seat_is_pending():
    """The 8 GB Pi 5 as captured from the deploy user: no sound card, only auto_null."""
    pipewire = FakePipeWire(pw_dump(PI5_8GB))

    report = apply_hdmi_audio(pipewire)

    assert pipewire.changes() == []
    assert report['ports'] == []
    assert report['problems'] == []
    (pending,) = report['pending']
    assert 'does not hold the seat' in pending


def test_a_default_that_is_not_hdmi_becomes_hdmi0():
    """Not an HDMI default (the null sink): HDMI0's sink becomes the default."""
    pipewire = FakePipeWire(pw_dump(PI5_16GB), volumes={73: (0.75, False)})
    pipewire.set_default('auto_null')

    report = apply_hdmi_audio(pipewire)

    assert pipewire.changes() == [['wpctl', 'set-default', '73']]
    assert report['default'] == {'before': 'auto_null', 'after': PI5_HDMI0_SINK}


def test_an_hdmi1_default_is_kept_when_both_ports_have_sinks():
    """An existing HDMI default is kept, even when HDMI0 is also there."""
    pipewire = FakePipeWire(pw_dump(PI5_16GB), volumes={73: (0.75, False), 90: (0.75, False)})
    pipewire.add_sink(card='vc4hdmi1')
    pipewire.set_default('alsa_output.vc4hdmi1.hdmi-stereo')

    report = apply_hdmi_audio(pipewire)

    assert pipewire.changes() == []
    assert [port['port'] for port in report['ports']] == ['HDMI0', 'HDMI1']
    assert report['default']['after'] == 'alsa_output.vc4hdmi1.hdmi-stereo'


def test_both_ports_are_set_independently():
    """Each sink is set on its own: no mirroring, no combined sink."""
    pipewire = FakePipeWire(pw_dump(PI5_16GB), volumes={90: (0.4, True)})
    pipewire.add_sink(card='vc4hdmi1')

    report = apply_hdmi_audio(pipewire)

    assert pipewire.changes() == [
        ['wpctl', 'set-mute', '73', '0'],
        ['wpctl', 'set-volume', '73', '75%'],
        ['wpctl', 'set-mute', '90', '0'],
        ['wpctl', 'set-volume', '90', '75%'],
    ]
    assert [port['after'] for port in report['ports']] == [{'level': 0.75, 'muted': False}] * 2


def test_an_available_but_inactive_stereo_profile_is_turned_on_and_its_sink_set():
    """A display on HDMI1 with its card still off: the stereo profile is set, then its sink."""
    pipewire = FakePipeWire(pw_dump(PI5_16GB), volumes={73: (0.75, False)})
    pipewire.set_profile_available(card='vc4hdmi1')

    report = apply_hdmi_audio(pipewire)

    assert pipewire.changes() == [
        ['wpctl', 'set-profile', '69', '2'],
        ['wpctl', 'set-mute', '90', '0'],
        ['wpctl', 'set-volume', '90', '75%'],
    ]
    assert report['pending'] == []
    assert report['ports'][1]['after'] == {'level': 0.75, 'muted': False}


def test_a_volume_that_does_not_hold_is_a_problem():
    """A sink that reads back anything but 0.75 unmuted fails the run (exit 1 from main)."""
    pipewire = FakePipeWire(pw_dump(PI5_16GB), volume_that_sticks=0.5)

    report = apply_hdmi_audio(pipewire)

    (problem,) = report['problems']
    assert problem == f'HDMI0 ({PI5_HDMI0_SINK}) reads 0.50, not 0.75 unmuted'


@pytest.mark.parametrize(
    ('line', 'level', 'muted'),
    [('Volume: 0.75\n', 0.75, False), ('Volume: 0.40 [MUTED]\n', 0.40, True)],
)
def test_wpctls_volume_line_is_read(line, level, muted):
    """``Volume: %.2f`` and `` [MUTED]``, as wpctl prints them (src/tools/wpctl.c, 0.5.13)."""
    volume = load_apply_hdmi_audio().parse_volume(line)

    assert (volume.level, volume.muted) == (level, muted)


def test_anything_but_a_volume_line_is_refused():
    """An unexpected wpctl output is an error, never read as some volume."""
    with pytest.raises(ValueError, match='not a wpctl volume line'):
        load_apply_hdmi_audio().parse_volume('Object not found\n')
