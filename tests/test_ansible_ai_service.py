"""The Ansible setup for the local AI service (ansible/ai_service.yml), on a Mac and on Linux.

Its plans are plans/lucid-circuit.md and plans/lucid-circuit-linux.md. Running it takes a real
host and gigabytes of downloads, so these only check what would go wrong quietly: a pin that isn't
exact, two agents on one port, or a model a host can never get.
"""

import configparser
import contextlib
import hashlib
import importlib.util
import itertools
import json
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs the service's rendered scripts under sh
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import jinja2
import pytest
import yaml
from pydantic import BaseModel, ConfigDict

from glitchygames import ai_link, clock
from glitchygames.process import OutputCapture, run_command
from tests.ansible_rendering import (
    Architecture,
    ansible_variables,
    host_architecture,
    render_expression,
    render_template,
    render_value,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytest_mock import MockerFixture

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANSIBLE = PROJECT_ROOT / 'ansible'
ROLES = ANSIBLE / 'roles'
MAC_ROOT_NAME = 'Library/Application Support/GlitchyGames/AI'
# llama.cpp's CPU variants at b12167 (plans/lucid-circuit-linux.md section 4)
ARM_CPU_VARIANTS = [
    'armv8.0_1',
    'armv8.2_1',
    'armv8.2_2',
    'armv8.2_3',
    'armv8.6_1',
    'armv8.6_2',
    'armv9.2_1',
    'armv9.2_2',
]
X86_CPU_VARIANTS = [
    'x64',
    'sse42',
    'sandybridge',
    'ivybridge',
    'piledriver',
    'haswell',
    'skylakex',
    'cannonlake',
    'cascadelake',
    'icelake',
    'cooperlake',
    'zen4',
    'alderlake',
    'sapphirerapids',
]
LINUX_LLAMA_CPP_OPTIONS = {
    'GGML_NATIVE': 'OFF',
    'GGML_BACKEND_DL': 'ON',
    'GGML_CPU_ALL_VARIANTS': 'ON',
    'BUILD_SHARED_LIBS': 'ON',
    'GGML_VULKAN': 'OFF',
    'GGML_OPENMP': 'OFF',
}
FULL_REVISION = re.compile(r'[0-9a-f]{40}')
FULL_SHA256 = re.compile(r'[0-9a-f]{64}')
# Ollama's and exoneris's llama.cpp ports on the owner's Mac
PORTS_OF_OTHER_SERVICES = {11434, 11435, 11437, 11439, 11440}


def role_defaults(*, role: str) -> dict[str, Any]:
    """Read a role's defaults.

    Returns:
        The role's default variables.
    """
    return yaml.safe_load((ROLES / role / 'defaults' / 'main.yml').read_text(encoding='utf-8'))


def test_every_model_is_pinned_exactly():
    """Each model names an immutable revision, a size and a whole SHA-256."""
    defaults = role_defaults(role='ai_models')
    models = {**defaults['ai_models_bonsai'], **defaults['ai_models_qwen']}

    for model in models.values():
        assert FULL_REVISION.fullmatch(model['revision'])
        files = [model['model'], *([model['vision']] if 'vision' in model else [])]
        for model_file in files:
            assert FULL_SHA256.fullmatch(model_file['sha256'])
            assert model_file['bytes'] > 0


def test_llama_cpp_is_pinned_to_a_tag_and_its_commit():
    """A tag that moved is refused, so the pin holds a whole commit."""
    defaults = role_defaults(role='llama_cpp')

    assert re.fullmatch(r'b\d+', defaults['llama_cpp_tag'])
    assert FULL_REVISION.fullmatch(defaults['llama_cpp_commit'])


def test_llama_cpp_links_nothing_a_player_lacks():
    """OpenSSL off: left on, the build links Homebrew's copy, which a player's Mac doesn't have."""
    options = role_defaults(role='llama_cpp')['llama_cpp_base_cmake_options']

    assert options['LLAMA_OPENSSL'] == 'OFF'


def test_every_agent_has_its_own_port_clear_of_other_services():
    """Two agents on one port would leave one failing to start, every time."""
    defaults = role_defaults(role='ai_service')
    ports = [
        *defaults['ai_service_bonsai_ports'].values(),
        *defaults['ai_service_qwen_ports'].values(),
    ]

    assert len(ports) == len(set(ports))
    assert not set(ports) & PORTS_OF_OTHER_SERVICES


def test_every_model_size_has_a_port():
    """A size with no port would fail only when a host selected it."""
    models = role_defaults(role='ai_models')
    service = role_defaults(role='ai_service')

    assert set(models['ai_models_bonsai']) == set(service['ai_service_bonsai_ports'])
    assert set(models['ai_models_qwen']) == set(service['ai_service_qwen_ports'])


def test_the_memory_tiers_catch_every_machine_and_name_real_sizes():
    """The lowest tier starts at zero, so the picker always finds a size."""
    models = role_defaults(role='ai_models')
    tiers = role_defaults(role='ai_service')['ai_service_bonsai_tiers']
    minimums = [tier['minimum_memory_mb'] for tier in tiers]

    assert minimums[0] == 0
    assert minimums == sorted(minimums)
    assert {tier['size'] for tier in tiers} <= set(models['ai_models_bonsai'])


def test_every_run_uses_2b_unless_a_size_was_chosen_by_hand():
    """2B for the foreseeable future (the owner, 2026-11-07), on the owner's Mac and a player's.

    Without the default, a 128 GB Mac would load 27B: the largest size that fits.
    """
    models = role_defaults(role='ai_models')
    service = role_defaults(role='ai_service')
    starts_from_the_default = 'bonsai_override={{ ai_service_default_bonsai_size | quote }}'

    assert service['ai_service_default_bonsai_size'] == '2b'
    assert service['ai_service_default_bonsai_size'] in models['ai_models_bonsai_sizes']
    assert not service['ai_service_bonsai_size'], 'a hand-picked size belongs in selection.env'
    for template in ('ai_service/templates/ai-service.sh.j2', 'ai_package/templates/setup.sh.j2'):
        script = (ROLES / template).read_text(encoding='utf-8')
        assert script.count(starts_from_the_default) == 1, template
        # The user's choice is read after the default, so it wins
        assert script.index(starts_from_the_default) < script.index('. "$config/selection.env"')


def test_the_agents_listen_on_loopback_only():
    """The script is what starts every model server, on the owner's Mac and on a player's."""
    runner = (ROLES / 'ai_service' / 'templates' / 'run-llama-server.sh.j2').read_text(
        encoding='utf-8'
    )

    assert '--host 127.0.0.1' in runner
    assert '0.0.0.0' not in runner  # ruff: ignore[hardcoded-bind-all-interfaces] - the address this checks is absent
    assert '--api-key-file' in runner


def test_no_model_starts_at_login():
    """A plist in LaunchAgents loads at every login, holding gigabytes with no game running."""
    defaults = role_defaults(role='ai_service')
    setup = (ROLES / 'ai_package' / 'templates' / 'setup.sh.j2').read_text(encoding='utf-8')

    assert 'LaunchAgents' not in defaults['ai_service_agents_directory']
    assert 'launchctl bootstrap' not in setup


def test_every_size_has_a_reserved_memory_figure():
    """The script that picks a size has to know what each one costs."""
    models = role_defaults(role='ai_models')
    service = role_defaults(role='ai_service')

    assert set(models['ai_models_bonsai']) == set(service['ai_service_bonsai_reserved_mib'])
    assert set(models['ai_models_qwen']) == set(service['ai_service_qwen_reserved_mib'])


def test_the_api_port_is_its_own_and_clear_of_other_services():
    """Games reach the service here, so it can't share a port with a model or another service."""
    defaults = role_defaults(role='ai_service')
    model_ports = {
        *defaults['ai_service_bonsai_ports'].values(),
        *defaults['ai_service_qwen_ports'].values(),
    }

    assert defaults['ai_service_api_port'] not in model_ports | PORTS_OF_OTHER_SERVICES


def test_the_sidecar_pins_its_python_and_its_docs_script():
    """The sidecar holds a whole Python, so its version and Scalar's bytes are both exact."""
    defaults = role_defaults(role='ai_sidecar')

    assert re.fullmatch(r'\d+\.\d+\.\d+', defaults['ai_sidecar_python_version'])
    assert FULL_SHA256.fullmatch(defaults['ai_sidecar_scalar_sha256'])
    assert re.fullmatch(r'\d+\.\d+\.\d+', defaults['ai_sidecar_scalar_version'])
    assert '@{{ ai_sidecar_scalar_version }}' in defaults['ai_sidecar_scalar_url']


@pytest.mark.parametrize(
    ('system', 'architecture', 'expected_target'),
    [
        ('Darwin', 'arm64', 'macos-aarch64-none'),
        ('Linux', 'aarch64', 'linux-aarch64-gnu'),
        ('Linux', 'x86_64', 'linux-x86_64-gnu'),
    ],
)
def test_the_sidecar_build_matches_the_platform(
    tmp_path: Path,
    system: Literal['Darwin', 'Linux'],
    architecture: Architecture,
    expected_target: str,
):
    """python-build-standalone names its builds by platform and architecture (section 4)."""
    variables = ansible_variables(system=system, architecture=architecture, home=tmp_path)

    assert variables['ai_sidecar_python_build'] == (
        f'cpython-{variables["ai_sidecar_python_version"]}-{expected_target}'
    )


def test_the_sidecar_installs_into_the_package_stage_on_linux_and_the_program_folder_on_a_mac(
    tmp_path: Path,
):
    """Ansible never installs under /opt: Linux builds into the stage the .deb is made from."""
    mac = ansible_variables(system='Darwin', architecture='arm64', home=tmp_path)
    linux = ansible_variables(system='Linux', architecture='aarch64', home=tmp_path)
    stage = f'{tmp_path}/.cache/glitchygames/ai/package/stage/opt/glitchygames/ai'

    assert mac['ai_sidecar_install_directory'] == mac['ai_sidecar_directory']
    assert linux['ai_sidecar_install_directory'] == f'{stage}/sidecar'
    # What the installed service runs from stays the player's path
    assert linux['ai_sidecar_directory'] == '/opt/glitchygames/ai/sidecar'


CORE_FOUNDATION = '/System/Library/Frameworks/CoreFoundation.framework/Versions/A/CoreFoundation'
SYSTEM_CONFIGURATION = (
    '/System/Library/Frameworks/SystemConfiguration.framework/Versions/A/SystemConfiguration'
)
SIDECAR_LDD_TASK = 'Check that the sidecar links only its own libraries and the system libc'
SIDECAR_OTOOL_TASK = 'Check that the sidecar links only its own libraries and the system frameworks'
SIDECAR_LINUX_INSTALL = '/home/pi/.cache/glitchygames/ai/package/stage/opt/glitchygames/ai/sidecar'
SIDECAR_MAC_INSTALL = '/Users/player/Library/Application Support/GlitchyGames/AI/sidecar'
GOOD_SIDECAR_LDD_LINES = [
    '\tlinux-vdso.so.1 (0x0000ffff9a1f0000)',
    f'\tlibpython3.14.so => {SIDECAR_LINUX_INSTALL}/python/bin/../lib/libpython3.14.so (0x1)',
    f'\tlibpydantic.so => {SIDECAR_LINUX_INSTALL}/site/pydantic_core.libs/libx-1a2b.so (0x2)',
    '\tlibm.so.6 => /lib/aarch64-linux-gnu/libm.so.6 (0x0000ffff99500000)',
    '\tlibgcc_s.so.1 => /lib/aarch64-linux-gnu/libgcc_s.so.1 (0x0000ffff99400000)',
    '\tlibc.so.6 => /lib/aarch64-linux-gnu/libc.so.6 (0x0000ffff99200000)',
    '\t/lib/ld-linux-aarch64.so.1 (0x0000ffff9a1f3000)',
]
GOOD_SIDECAR_OTOOL_LINES = [
    '/x/python/bin/python3.14:',
    f'\t{CORE_FOUNDATION} (compat 150)',
    '\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1351.0.0)',
    '\t@rpath/libpython3.14.dylib (compatibility version 3.14.0, current version 3.14.0)',
    '\t@loader_path/../lib/libz.dylib (compatibility version 1.0.0)',
]


def sidecar_check_passes(
    *,
    task_name: str,
    lines: list[str],
    system: Literal['Darwin', 'Linux'],
    tmp_path: Path,
    file_name: str = 'python/bin/python3.14',
) -> bool:
    """Run one of the sidecar role's link assertions on sample `ldd` or `otool -L` output.

    Returns:
        Whether the assertion passes.
    """
    (task,) = [
        task
        for task in walk_tasks(tasks=role_tasks(role='ai_sidecar'))
        if task.get('name') == task_name
    ]
    install_directory = SIDECAR_LINUX_INSTALL if system == 'Linux' else SIDECAR_MAC_INSTALL
    variables = ansible_variables(
        system=system, architecture=host_architecture(system=system), home=tmp_path
    )
    variables['ai_sidecar_install_directory'] = install_directory
    variables['item'] = {
        'item': f'{install_directory}/{file_name}',
        'stdout_lines': lines,
        'stdout': '\n'.join(lines),
        'stderr': '',
    }
    template = tmp_path / 'assertion.j2'
    template.write_text(
        '{{ (' + task['ansible.builtin.assert']['that'].strip() + ') }}', encoding='utf-8'
    )
    return render_template(path=template, variables=variables) == 'True'


def test_the_sidecar_ldd_check_accepts_its_own_and_libc_links_including_unnormalised_paths(
    tmp_path: Path,
):
    """Glibc's ldd prints an RPATH hit as <sidecar>/python/bin/../lib/..., which must pass."""
    assert sidecar_check_passes(
        task_name=SIDECAR_LDD_TASK,
        lines=GOOD_SIDECAR_LDD_LINES,
        system='Linux',
        tmp_path=tmp_path,
    )


@pytest.mark.parametrize(
    'bad_line',
    [
        '\tlibffi.so.8 => not found',
        '\tlibm.so.6 => /usr/local/lib/libm.so.6 (0x0000ffff99600000)',
        '\tlibssl.so.3 => /lib/aarch64-linux-gnu/libssl.so.3 (0x0000ffff99600000)',
        '\tlibpydantic.so => /home/pi/other/site/libpydantic.so (0x2)',
        f'\tlibevil.so => {SIDECAR_LINUX_INSTALL}-other/lib/libevil.so (0x2)',
    ],
)
def test_the_sidecar_ldd_check_refuses_a_missing_foreign_or_usr_local_library(
    tmp_path: Path, bad_line: str
):
    """Anything a player's machine may lack, or that is not the sidecar's own, fails."""
    assert not sidecar_check_passes(
        task_name=SIDECAR_LDD_TASK,
        lines=[*GOOD_SIDECAR_LDD_LINES, bad_line],
        system='Linux',
        tmp_path=tmp_path,
    )


# Real `otool -L` output of python-build-standalone's cpython-3.14.8-macos-aarch64-none
# (the pinned build), read 2026-11-18: a dylib lists its own install name, an absolute path, first
REAL_PYTHON_BINARY_OTOOL_LINES = [
    '/pbs/bin/python3.14:',
    f'\t{CORE_FOUNDATION} (compatibility version 150.0.0)',
    '\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1351.0.0)',
    '\t/usr/lib/libz.1.dylib (compatibility version 1.0.0, current version 1.2.12)',
    '\t/usr/lib/libedit.3.dylib (compatibility version 2.0.0, current version 3.0.0)',
    '\t/usr/lib/libncurses.5.4.dylib (compatibility version 5.4.0, current version 5.4.0)',
    '\t/usr/lib/libpanel.5.4.dylib (compatibility version 5.4.0, current version 5.4.0)',
    f'\t{SYSTEM_CONFIGURATION} (compatibility version 1.0.0)',
]
LIBPYTHON_INSTALL_NAME = (
    '/Users/terry/.local/share/uv/python/cpython-3.14.8-macos-aarch64-none/lib/libpython3.14.dylib'
)
REAL_LIBPYTHON_OTOOL_LINES = [
    '/pbs/lib/libpython3.14.dylib:',
    f'\t{LIBPYTHON_INSTALL_NAME} (compatibility version 3.14.0, current version 3.14.0)',
    '\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1351.0.0)',
    '\t/usr/lib/libz.1.dylib (compatibility version 1.0.0, current version 1.2.12)',
    f'\t{CORE_FOUNDATION} (compatibility version 150.0.0)',
]


@pytest.mark.parametrize(
    ('file_name', 'lines'),
    [
        ('python/bin/python3.14', REAL_PYTHON_BINARY_OTOOL_LINES),
        ('python/lib/libpython3.14.dylib', REAL_LIBPYTHON_OTOOL_LINES),
    ],
)
def test_the_sidecar_otool_check_accepts_a_real_binary_and_dylib_with_its_install_name(
    tmp_path: Path, file_name: str, lines: list[str]
):
    """A dylib's first entry is its own absolute install name, which is not a link."""
    assert sidecar_check_passes(
        task_name=SIDECAR_OTOOL_TASK,
        lines=lines,
        system='Darwin',
        tmp_path=tmp_path,
        file_name=file_name,
    )


def test_the_sidecar_otool_check_still_refuses_a_foreign_link_in_a_dylib(tmp_path: Path):
    """Skipping the install name must not skip the links after it."""
    assert not sidecar_check_passes(
        task_name=SIDECAR_OTOOL_TASK,
        lines=[*REAL_LIBPYTHON_OTOOL_LINES, '\t/opt/homebrew/lib/libx.dylib (compat 1)'],
        system='Darwin',
        tmp_path=tmp_path,
        file_name='python/lib/libpython3.14.dylib',
    )


@pytest.mark.parametrize(
    ('task_name', 'not_an_object_output'),
    [
        ('List what the sidecar links on Linux', 'not a dynamic executable'),
        ('List what the sidecar links on a Mac', '/x/data.so: is not an object file'),
    ],
)
def test_a_file_that_is_not_a_dynamic_object_is_skipped_and_said_so_not_failed(
    tmp_path: Path, task_name: str, not_an_object_output: str
):
    """A data file named *.so must not abort the install; any other failure still does."""
    (task,) = [
        task
        for task in walk_tasks(tasks=role_tasks(role='ai_sidecar'))
        if task.get('name') == task_name
    ]
    registered_name = task['register']
    variables = ansible_variables(system='Linux', architecture='aarch64', home=tmp_path)
    variables['ai_sidecar_install_directory'] = SIDECAR_LINUX_INSTALL
    main_binary = f'{SIDECAR_LINUX_INSTALL}/python/bin/python3.14'
    variables['ai_sidecar_main_binary'] = main_binary

    def fails(*, result: dict[str, Any], item: str) -> bool:
        # Only what Ansible provides: the registered name holds this item's result, and `item`
        return (
            render_expression(
                expression=task['failed_when'],
                variables={**variables, registered_name: result, 'item': item},
            )
            is True
        )

    data_file = f'{SIDECAR_LINUX_INSTALL}/site/x/data.so'
    assert not fails(result={'rc': 1, 'stdout': '', 'stderr': not_an_object_output}, item=data_file)
    assert not fails(result={'rc': 0, 'stdout': not_an_object_output, 'stderr': ''}, item=data_file)
    assert fails(
        result={'rc': 1, 'stdout': '', 'stderr': 'No such file or directory'}, item=data_file
    )
    # The main binary is never skipped
    assert fails(result={'rc': 1, 'stdout': '', 'stderr': not_an_object_output}, item=main_binary)
    assert fails(result={'rc': 0, 'stdout': not_an_object_output, 'stderr': ''}, item=main_binary)
    (say,) = [
        task
        for task in walk_tasks(tasks=role_tasks(role='ai_sidecar'))
        if task.get('name') == 'Say which files were skipped as not dynamic objects'
    ]
    assert 'not a dynamic object' in say['ansible.builtin.debug']['msg']


def test_the_sidecar_check_writes_no_bytecode_into_the_install():
    """On Linux the install is the .deb's stage, so bytecode its check wrote would ship."""
    (task,) = [
        task
        for task in walk_tasks(tasks=role_tasks(role='ai_sidecar'))
        if task.get('name') == 'Check the sidecar uses nothing outside itself'
    ]

    assert task['environment']['PYTHONDONTWRITEBYTECODE'] == '1'


def test_packaging_reads_the_sidecar_from_where_ansible_built_it():
    """On Linux the runtime path does not exist until the .deb is installed."""
    (task,) = [
        task
        for task in walk_tasks(tasks=role_tasks(role='ai_package', file_name='stage.yml'))
        if task.get('name') == 'Stage the sidecar'
    ]
    argv = task['ansible.builtin.command']['argv']

    assert '{{ ai_sidecar_install_directory }}/' in argv
    assert '{{ ai_sidecar_directory }}/' not in argv


def test_the_sidecar_otool_check_accepts_system_and_own_libraries(tmp_path: Path):
    """The Mac's check lets through /usr/lib, /System and the sidecar's own @rpath libraries."""
    assert sidecar_check_passes(
        task_name=SIDECAR_OTOOL_TASK,
        lines=GOOD_SIDECAR_OTOOL_LINES,
        system='Darwin',
        tmp_path=tmp_path,
    )


@pytest.mark.parametrize(
    'bad_line',
    [
        '\t/opt/homebrew/opt/openssl@3/lib/libssl.3.dylib (compatibility version 3.0.0)',
        '\t/usr/local/lib/libz.dylib (compatibility version 1.0.0)',
    ],
)
def test_the_sidecar_otool_check_refuses_a_homebrew_or_usr_local_library(
    tmp_path: Path, bad_line: str
):
    """A library a player's Mac may not have fails the build."""
    assert not sidecar_check_passes(
        task_name=SIDECAR_OTOOL_TASK,
        lines=[*GOOD_SIDECAR_OTOOL_LINES, bad_line],
        system='Darwin',
        tmp_path=tmp_path,
    )


def test_the_engine_never_imports_the_service():
    """The engine reaches the service only over a socket, so a game runs with it absent."""
    engine = PROJECT_ROOT / 'src' / 'glitchygames'
    importers = [
        path
        for path in engine.rglob('*.py')
        if 'glitchygames_ai_service' in path.read_text(encoding='utf-8')
    ]

    assert importers == []


def test_the_smoke_test_reports_each_model():
    """Each model's result is written out: an automatic lint fix once deleted the report."""
    script = (ROLES / 'ai_service' / 'files' / 'smoke_test.py').read_text(encoding='utf-8')

    assert "sys.stdout.write(json.dumps({'model': model['alias'], **result})" in script


def test_a_plist_holds_no_shell_script():
    """A raw & inside a plist's XML makes the whole plist invalid, so the script stays a file."""
    plist = (ROLES / 'ai_service' / 'templates' / 'agent.plist.j2').read_text(encoding='utf-8')

    assert '&' not in plist
    assert '/bin/sh' not in plist


PLAYBOOK = ANSIBLE / 'ai_service.yml'
# The memory, in GB, from which a Linux host runs the models (plans/lucid-circuit-linux.md, 8.2)
LINUX_AI_MEMORY_GB = 16


def inventory_groups() -> dict[str, dict[str, Any]]:
    """Read every group of ansible/inventory.yml, wherever it is written, merged as Ansible does.

    A group may be defined in one place and named as another group's child in a second.

    Returns:
        Each group's hosts (name to host variables), children (names) and variables.
    """
    inventory = yaml.safe_load((ANSIBLE / 'inventory.yml').read_text(encoding='utf-8'))
    groups: dict[str, dict[str, Any]] = {}

    def visit(*, name: str, definition: dict[str, Any] | None) -> None:
        group = groups.setdefault(name, {'hosts': {}, 'children': [], 'vars': {}})
        definition = definition or {}
        for host, host_variables in (definition.get('hosts') or {}).items():
            group['hosts'][host] = group['hosts'].get(host, {}) | (host_variables or {})
        group['vars'] |= definition.get('vars') or {}
        for child, child_definition in (definition.get('children') or {}).items():
            group['children'].append(child)
            visit(name=child, definition=child_definition)

    visit(name='all', definition=inventory['all'])
    return groups


def group_host_names(*, groups: dict[str, dict[str, Any]], group: str) -> set[str]:
    """Name every host in a group, its children's included.

    Returns:
        The host names.
    """
    names = set(groups[group]['hosts'])
    for child in groups[group]['children']:
        names |= group_host_names(groups=groups, group=child)
    return names


def host_variable(*, groups: dict[str, dict[str, Any]], host: str, name: str) -> Any:
    """Read a host's value of a variable: its own, else its nearest group's, else all's.

    Returns:
        The value, or None if nothing sets it.
    """
    holders = [group for group in groups.values() if host in group['hosts']]
    for holder in holders:
        if name in holder['hosts'][host]:
            return holder['hosts'][host][name]
    for holder in holders:
        if name in holder['vars']:
            return holder['vars'][name]
    return groups['all']['vars'].get(name)


def test_every_linux_host_states_its_memory_and_opts_in_at_16_gb():
    """Each Linux host says how much memory it has, and only those with 16 GB or more opt in.

    Nothing in the roles reads a board's name: the inventory says which hosts run the models
    (plans/lucid-circuit-linux.md, 6.9 and 8.2). The Raspberry Pis' group stays off, and each
    16 GB Pi turns the service on for itself.
    """
    groups = inventory_groups()
    linux_hosts = group_host_names(groups=groups, group='linux')

    assert linux_hosts, 'the inventory has no linux group, or it holds no host'
    assert group_host_names(groups=groups, group='raspberry_pis') <= linux_hosts
    assert groups['raspberry_pis']['vars']['ai_enabled'] is False
    for host in sorted(linux_hosts):
        memory = host_variable(groups=groups, host=host, name='host_memory_gb')
        assert type(memory) is int, f'{host} states no integer host_memory_gb: {memory!r}'
        enabled = host_variable(groups=groups, host=host, name='ai_enabled')
        assert enabled is (memory >= LINUX_AI_MEMORY_GB), (
            f'{host}: {memory} GB, ai_enabled {enabled}'
        )
    # The 16 GB Pi 5 is the first Linux host to run the models
    assert host_variable(groups=groups, host='raspberry-pi-5', name='ai_enabled') is True
    assert groups['all']['vars']['ai_enabled'] is True


MAC_SERVICE_ROLES = [
    {'role': 'llama_cpp', 'tags': ['llama_cpp', 'ai_service', 'ai_package', 'ai_validate']},
    {'role': 'ai_models', 'tags': ['ai_models']},
    {'role': 'ai_sidecar', 'tags': ['ai_sidecar', 'ai_service', 'ai_package']},
    {'role': 'ai_service', 'tags': ['ai_service', 'ai_package']},
    {'role': 'ai_package', 'tags': ['ai_package']},
    {'role': 'ai_validate', 'tags': ['never', 'ai_validate']},
    {'role': 'ai_uninstall', 'tags': ['never', 'ai_uninstall']},
]


def test_only_hosts_with_ai_enabled_get_the_ai_service():
    """The hosts are sorted without connecting, then only enabled Macs and Linux hosts get it.

    Checked by hand with ansible-playbook: a host with ai_enabled false is never contacted. Both
    service plays run as the host's user; the Linux one raises to root only for the package.
    """
    sorting_play, mac_play, linux_play = yaml.safe_load(PLAYBOOK.read_text(encoding='utf-8'))

    assert sorting_play['hosts'] == 'all'
    assert sorting_play['gather_facts'] is False
    # Every --tags run needs the groups, or the service plays would match no host
    assert sorting_play['tags'] == ['always']
    (sorting_task,) = sorting_play['tasks']
    assert sorting_task['ansible.builtin.group_by']['key'] == (
        "{{ 'ai_enabled' if ai_enabled | bool else 'ai_disabled' }}"
    )
    assert mac_play['hosts'] == 'macos:&ai_enabled'
    assert mac_play['become'] is False
    assert mac_play['roles'] == MAC_SERVICE_ROLES
    assert linux_play['hosts'] == 'linux:&ai_enabled'
    assert linux_play['become'] is False


def test_the_linux_play_builds_the_package_before_the_service_installs_it():
    """On Linux the service is the installed .deb, so ai_package comes before ai_service.

    Every tag that installs the service builds the package first, and validation and uninstall
    still run only when asked.
    """
    *_, linux_play = yaml.safe_load(PLAYBOOK.read_text(encoding='utf-8'))
    roles = {entry['role']: entry['tags'] for entry in linux_play['roles']}
    order = [entry['role'] for entry in linux_play['roles']]

    assert order == [
        'llama_cpp',
        'ai_models',
        'ai_sidecar',
        'ai_package',
        'ai_service',
        'ai_validate',
        'ai_uninstall',
    ]
    for builder in ('llama_cpp', 'ai_sidecar', 'ai_package'):
        assert {'ai_service', 'ai_package'} <= set(roles[builder]), builder
    assert roles['ai_service'] == ['ai_service']
    assert roles['ai_validate'] == ['never', 'ai_validate']
    assert roles['ai_uninstall'] == ['never', 'ai_uninstall']


# Words naming a board or a CPU model, which no AI role may test for (plans/lucid-circuit-linux.md,
# 6.9): the Pi's board and SoC, and the ARM cores and server CPUs it could be mistaken for
BOARD_OR_CPU_WORDS = re.compile(
    r'raspberry|\bpi ?[45]\b|\brpi|bcm27\d\d|cortex|\ba7[26]\b|neoverse|graviton', re.IGNORECASE
)
# Every way a play could read the host's architecture
ARCHITECTURE_FACT = re.compile(
    r"ansible_(architecture|machine)\b|ansible_facts\s*(\[\s*['\"](architecture|machine)['\"]\s*\]"
    r'|\.(architecture|machine)\b)'
)
AI_ROLES = sorted(
    path.name for path in ROLES.iterdir() if path.name.startswith('ai_') or path.name == 'llama_cpp'
)


def test_no_ai_role_tests_for_a_board():
    """The roles choose by architecture alone, so a new board needs only an inventory entry."""
    board_mentions: list[str] = []
    architecture_reads: list[str] = []
    for role in AI_ROLES:
        for path in sorted((ROLES / role).rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            text = path.read_text(encoding='utf-8')
            where = str(path.relative_to(PROJECT_ROOT))
            board_mentions += [f'{where}: {match}' for match in BOARD_OR_CPU_WORDS.findall(text)]
            architecture_reads += [
                f'{where}: {match.group(0)}'
                for match in ARCHITECTURE_FACT.finditer(text)
                if match.group(0) != "ansible_facts['architecture']"
            ]

    assert AI_ROLES == [
        'ai_models',
        'ai_package',
        'ai_service',
        'ai_sidecar',
        'ai_uninstall',
        'ai_validate',
        'llama_cpp',
    ]
    assert board_mentions == []
    assert architecture_reads == []


# The playbook's and this file's names before the Linux port (plans/ keeps them where they record
# what was true then)
OLD_NAMES = ('macos_ai_service.yml', 'test_ansible_macos_ai_service.py')
GIT_TIMEOUT_SECONDS = 60.0


def test_no_document_names_the_old_playbook():
    """Every live reference follows the rename; only plans/ (history) may keep the old names."""
    completed = run_command(
        command=['git', 'ls-files', '-z'],
        environment=os.environ,
        working_directory=PROJECT_ROOT,
        capture_output=OutputCapture.APART,
        timeout_seconds=GIT_TIMEOUT_SECONDS,
    )
    tracked = [name for name in completed.stdout.split('\0') if name]
    holders = [
        name
        for name in tracked
        if name.endswith(('.md', '.py', '.yml'))
        and not name.startswith(('plans/', '.superpowers/'))
        # This file names them to look for them
        and name != str(Path(__file__).relative_to(PROJECT_ROOT))
        and (PROJECT_ROOT / name).is_file()
        and any(old in (PROJECT_ROOT / name).read_text(encoding='utf-8') for old in OLD_NAMES)
    ]

    assert 'ansible/ai_service.yml' in tracked
    assert holders == []


def walk_tasks(*, tasks: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Yield every task, descending into blocks.

    Yields:
        Each task, a block before the tasks inside it.
    """
    for task in tasks:
        yield task
        yield from walk_tasks(tasks=task.get('block', []))


def role_tasks(*, role: str, file_name: str = 'main.yml') -> list[dict[str, Any]]:
    """Read a role's task file.

    Returns:
        The file's top-level tasks.
    """
    return yaml.safe_load((ROLES / role / 'tasks' / file_name).read_text(encoding='utf-8'))


def rendered_options(
    *,
    system: Literal['Darwin', 'Linux'],
    architecture: Architecture,
    tmp_path: Path,
) -> dict[str, str]:
    """Render the options the platform's llama_cpp task file works out.

    Returns:
        The CMake options of a build on that platform, with the macOS SDK path faked.
    """
    file_name = 'macos.yml' if system == 'Darwin' else 'linux.yml'
    (task,) = [
        task
        for task in walk_tasks(tasks=role_tasks(role='llama_cpp', file_name=file_name))
        if task.get('name') == "Work out this build's options"
    ]
    expression = task['ansible.builtin.set_fact']['llama_cpp_all_cmake_options']
    template = tmp_path / 'options.j2'
    variables = ansible_variables(system=system, architecture=architecture, home=tmp_path)
    variables['llama_cpp_sdk'] = {'stdout': '/sdk'}
    if system == 'Darwin':
        inventory = yaml.safe_load((ANSIBLE / 'inventory.yml').read_text(encoding='utf-8'))
        variables['llama_cpp_cmake_options'] = inventory['all']['children']['macos']['vars'][
            'llama_cpp_cmake_options'
        ]
    # The task's own expression, with its braces taken off, as JSON so the dict comes back whole
    template.write_text(
        '{{ (' + expression.strip().strip('{}') + ') | to_json }}', encoding='utf-8'
    )
    return json.loads(render_template(path=template, variables=variables))


def test_no_role_names_the_old_install_root():
    """Programs and a user's data are two folders on Linux, so one name for both can't stay."""
    holders = [
        path.relative_to(PROJECT_ROOT)
        for path in ANSIBLE.rglob('*')
        if path.is_file() and 'ai_install_root' in path.read_text(encoding='utf-8')
    ]

    assert holders == []


def test_the_mac_roots_are_one_folder_and_unchanged(tmp_path: Path):
    """The Mac keeps its single folder, so nothing already installed moves."""
    variables = ansible_variables(system='Darwin', architecture='arm64', home=tmp_path)
    folder = str(tmp_path / MAC_ROOT_NAME)

    assert variables['ai_program_root'] == folder
    assert variables['ai_user_root'] == folder
    assert variables['ai_cache_root'] == str(tmp_path / 'Library/Caches/GlitchyGames/AI')
    assert variables['ai_log_root'] == str(tmp_path / 'Library/Logs/GlitchyGames/AI')


@pytest.mark.parametrize('architecture', ['aarch64', 'x86_64'])
def test_the_linux_roots_follow_the_design(
    tmp_path: Path, architecture: Literal['aarch64', 'x86_64']
):
    """Programs under /opt (the .deb's), everything of the user's under the XDG folders."""
    variables = ansible_variables(system='Linux', architecture=architecture, home=tmp_path)

    assert variables['ai_program_root'] == '/opt/glitchygames/ai'
    assert variables['ai_user_root'] == str(tmp_path / '.local/share/glitchygames/ai')
    assert variables['ai_cache_root'] == str(tmp_path / '.cache/glitchygames/ai')
    assert variables['ai_log_root'] == str(tmp_path / '.local/state/glitchygames/ai/logs')


def test_the_linux_xdg_folders_win_when_set(tmp_path: Path):
    """A host's XDG folders win, read from its own environment (the controller may be elsewhere)."""
    group_text = (ANSIBLE / 'group_vars' / 'linux.yml').read_text(encoding='utf-8')
    variables = ansible_variables(system='Linux', architecture='aarch64', home=tmp_path)
    variables['ansible_facts']['env'] = {
        'XDG_DATA_HOME': '/data',
        'XDG_CACHE_HOME': '/cache',
        'XDG_STATE_HOME': '/state',
    }

    assert 'lookup(' not in group_text
    # ansible_variables resolved the roots with an empty environment, so render them again
    environment_roots = yaml.safe_load(group_text)
    resolved = {
        name: render_template(
            path=_write(tmp_path / f'{name}.j2', environment_roots[name]),
            variables=variables | {'ai_home': str(tmp_path)},
        )
        for name in ('ai_user_root', 'ai_cache_root', 'ai_log_root')
    }
    assert resolved == {
        'ai_user_root': '/data/glitchygames/ai',
        'ai_cache_root': '/cache/glitchygames/ai',
        'ai_log_root': '/state/glitchygames/ai/logs',
    }


def _write(path: Path, text: str) -> Path:
    """Write a template file.

    Returns:
        The path.
    """
    path.write_text(text, encoding='utf-8')
    return path


def test_every_llama_cpp_build_starts_from_an_empty_directory():
    """A build cut short by a power loss leaves empty objects, which a reused directory trusts."""
    (build_block,) = [
        task for task in role_tasks(role='llama_cpp') if task.get('name') == 'Build llama.cpp'
    ]
    steps = build_block['block']
    names = [step['name'] for step in steps]
    emptying = [
        step
        for step in steps
        if step.get('ansible.builtin.file', {}).get('path') == '{{ llama_cpp_build_directory }}'
        and step['ansible.builtin.file'].get('state') == 'absent'
    ]

    assert len(emptying) == 1
    assert 'when' not in emptying[0]
    assert names.index(emptying[0]['name']) < names.index('Configure the build')


@pytest.mark.parametrize('architecture', ['aarch64', 'x86_64'])
def test_the_linux_llama_cpp_options_name_no_cpu_and_match_on_both_architectures(
    tmp_path: Path, architecture: Literal['aarch64', 'x86_64']
):
    """One build per architecture picks its CPU variant at run time, so no option names a CPU."""
    options = rendered_options(system='Linux', architecture=architecture, tmp_path=tmp_path)
    other = 'x86_64' if architecture == 'aarch64' else 'aarch64'

    assert options == rendered_options(system='Linux', architecture=other, tmp_path=tmp_path)
    assert LINUX_LLAMA_CPP_OPTIONS.items() <= options.items()
    assert 'GGML_CPU_ARM_ARCH' not in options
    assert not [value for value in options.values() if re.search(r'armv|native|x64|haswell', value)]


def test_every_architecture_has_its_variant_list():
    """The post-install check looks for every variant llama.cpp builds for the architecture."""
    variants = role_defaults(role='llama_cpp')['llama_cpp_cpu_variants']

    assert variants == {'aarch64': ARM_CPU_VARIANTS, 'x86_64': X86_CPU_VARIANTS}


def test_the_mac_llama_cpp_options_are_unchanged(tmp_path: Path):
    """The Mac's static Metal build is as it was before the split."""
    options = rendered_options(system='Darwin', architecture='arm64', tmp_path=tmp_path)

    assert options == {
        'CMAKE_BUILD_TYPE': 'Release',
        'BUILD_SHARED_LIBS': 'OFF',
        'LLAMA_OPENSSL': 'OFF',
        'LLAMA_BUILD_TESTS': 'OFF',
        'LLAMA_BUILD_EXAMPLES': 'OFF',
        'LLAMA_BUILD_UI': 'OFF',
        'LLAMA_USE_PREBUILT_UI': 'OFF',
        'GGML_METAL': 'ON',
        'GGML_METAL_EMBED_LIBRARY': 'ON',
        'CMAKE_OSX_ARCHITECTURES': 'arm64',
        'CMAKE_OSX_DEPLOYMENT_TARGET': '14.0',
        'CMAKE_OSX_SYSROOT': '/sdk',
    }


def test_the_linux_runtime_is_staged_for_the_package_not_installed_under_opt(tmp_path: Path):
    """Ansible installs /opt only through the .deb, so the build lands in the package stage."""
    variables = ansible_variables(system='Linux', architecture='aarch64', home=tmp_path)

    assert variables['llama_cpp_install_root'] == (
        f'{tmp_path}/.cache/glitchygames/ai/package/stage/opt/glitchygames/ai'
    )
    # Named once, by ai_package: its path comparisons keep or delete the runtime by it
    group_variables = yaml.safe_load((ANSIBLE / 'group_vars' / 'linux.yml').read_text('utf-8'))
    assert group_variables['llama_cpp_install_root'] == '{{ ai_package_stage_root }}'
    assert variables['llama_cpp_install_root'] == variables['ai_package_stage_root']


LINUX_INSTALL = (
    '/home/pi/.cache/glitchygames/ai/package/stage/opt/glitchygames/ai/runtime/llama.cpp-b12167-abc'
)
GOOD_LDD_LINES = [
    '\tlinux-vdso.so.1 (0x0000ffff9a1f0000)',
    f'\tlibllama.so => {LINUX_INSTALL}/bin/../lib/libllama.so (0x0000ffff99a00000)',
    f'\tlibggml-base.so => {LINUX_INSTALL}/lib/libggml-base.so (0x0000ffff99900000)',
    f'\tlibggml-cpu-armv8.2_2.so => {LINUX_INSTALL}/bin/libggml-cpu-armv8.2_2.so (0x0000ffff998)',
    '\tlibstdc++.so.6 => /lib/aarch64-linux-gnu/libstdc++.so.6 (0x0000ffff99600000)',
    '\tlibm.so.6 => /usr/lib/x86_64-linux-gnu/libm.so.6 (0x0000ffff99500000)',
    '\tlibgcc_s.so.1 => /lib/aarch64-linux-gnu/libgcc_s.so.1 (0x0000ffff99400000)',
    '\tlibc.so.6 => /lib/aarch64-linux-gnu/libc.so.6 (0x0000ffff99200000)',
    '\t/lib/ld-linux-aarch64.so.1 (0x0000ffff9a1f3000)',
]
GOOD_LOAD_LINE = (
    f'load_backend: loaded CPU backend from {LINUX_INSTALL}/bin/libggml-cpu-armv8.2_2.so'
)


def linux_task(*, name: str) -> dict[str, Any]:
    """Find one of linux.yml's tasks by name.

    Returns:
        The task.
    """
    (task,) = [
        task
        for task in walk_tasks(tasks=role_tasks(role='llama_cpp', file_name='linux.yml'))
        if task.get('name') == name
    ]
    return task


def linux_assertion_holds(*, task_name: str, extra: dict[str, Any], tmp_path: Path) -> bool:
    """Evaluate a linux.yml assert task's `that` expression with sample command output.

    Returns:
        Whether the assertion passes.
    """
    expression = linux_task(name=task_name)['ansible.builtin.assert']['that']
    variables = ansible_variables(system='Linux', architecture='aarch64', home=tmp_path)
    variables['llama_cpp_install_directory'] = LINUX_INSTALL
    variables.update(extra)
    template = tmp_path / 'assertion.j2'
    template.write_text('{{ (' + expression.strip() + ') }}', encoding='utf-8')
    return render_template(path=template, variables=variables) == 'True'


def mac_apple_silicon_assertion_holds(*, variables: dict[str, Any]) -> bool:
    """Evaluate the Mac llama_cpp role's Apple Silicon assert, every line of its `that`.

    Returns:
        Whether Ansible's assert would pass on a host with these variables' facts.
    """
    (task,) = [
        task
        for task in walk_tasks(tasks=role_tasks(role='llama_cpp', file_name='macos.yml'))
        if task.get('name') == 'Refuse anything but an Apple Silicon Mac'
    ]
    conditions: list[str] = task['ansible.builtin.assert']['that']
    return all(
        render_expression(expression='{{ ' + condition + ' }}', variables=variables) is True
        for condition in conditions
    )


def test_the_mac_apple_silicon_assert_passes_with_the_helpers_facts(tmp_path: Path):
    """The helper's Darwin facts are a real Apple Silicon Mac's, which reports arm64, not aarch64.

    Facts that a real Mac never reports would let a test pass while the play refuses every Mac.
    """
    mac = ansible_variables(system='Darwin', architecture='arm64', home=tmp_path)
    intel = ansible_variables(system='Darwin', architecture='arm64', home=tmp_path)
    intel['ansible_facts']['architecture'] = 'x86_64'

    assert mac['ansible_facts']['architecture'] == 'arm64'
    assert mac_apple_silicon_assertion_holds(variables=mac)
    assert not mac_apple_silicon_assertion_holds(variables=intel)


@pytest.mark.parametrize(
    ('system', 'architecture'), [('Darwin', 'aarch64'), ('Darwin', 'x86_64'), ('Linux', 'arm64')]
)
def test_the_helper_refuses_facts_no_real_host_reports(
    tmp_path: Path, system: Literal['Darwin', 'Linux'], architecture: Architecture
):
    """A Mac reports arm64; Linux reports aarch64 or x86_64 (ansible-core's setup module)."""
    with pytest.raises(ValueError, match='reports'):
        ansible_variables(system=system, architecture=architecture, home=tmp_path)


def test_the_helper_fails_on_an_undefined_variable_as_ansible_would(tmp_path: Path):
    """A value naming a variable nobody defines fails where it is used, not as its own text.

    Ansible templates a variable when a task uses it, so one that can't be resolved on this
    platform is harmless until then, and an error from then on.
    """
    variables = ansible_variables(
        system='Linux',
        architecture='aarch64',
        home=tmp_path,
        overrides={
            'probe_naming_nothing': 'before {{ no_such_variable }} after',
            'probe_missing_key': "{{ {'aarch64': 1}['riscv64'] }}",
        },
    )

    with pytest.raises(jinja2.UndefinedError, match='no_such_variable'):
        render_value(value='{{ probe_naming_nothing }}', variables=variables)
    with pytest.raises(jinja2.UndefinedError):
        render_value(value='{{ probe_missing_key }}', variables=variables)
    with pytest.raises(jinja2.UndefinedError, match='no_such_variable'):
        render_value(value='a task naming {{ no_such_variable }}', variables=variables)
    with pytest.raises(jinja2.UndefinedError):
        render_expression(expression="{{ {'aarch64': 1}['riscv64'] }}", variables=variables)


def test_the_helper_refuses_variables_that_never_settle(tmp_path: Path):
    """References that never stop changing are an error, not the last pass's half-rendered text."""
    with pytest.raises(RuntimeError, match='probe_'):
        ansible_variables(
            system='Linux',
            architecture='aarch64',
            home=tmp_path,
            overrides={'probe_first': '{{ probe_second }}', 'probe_second': '{{ probe_first }}'},
        )


LDD_TASK = "Check that they link only glibc, libstdc++, libgcc and the runtime's own libraries"
LOAD_TASK = 'Check that it loaded a CPU variant from its own bin/'


def ldd_passes(*, lines: list[str], tmp_path: Path) -> bool:
    """Run the ldd assertion on sample `ldd` output.

    Returns:
        Whether the assertion passes.
    """
    return linux_assertion_holds(
        task_name=LDD_TASK, extra={'item': {'stdout_lines': lines}}, tmp_path=tmp_path
    )


def test_the_ldd_check_accepts_a_real_builds_links_including_unnormalised_rpath_paths(
    tmp_path: Path,
):
    """Glibc's ldd prints an RPATH hit as <runtime>/bin/../lib/..., which must pass."""
    assert ldd_passes(lines=GOOD_LDD_LINES, tmp_path=tmp_path)


@pytest.mark.parametrize(
    'bad_line',
    [
        '\tlibstdc++.so.6 => not found',
        '\tlibstdc++.so.6 => /usr/local/lib/libstdc++.so.6 (0x0000ffff99600000)',
        '\tlibssl.so.3 => /lib/aarch64-linux-gnu/libssl.so.3 (0x0000ffff99600000)',
        '\tlibvulkan.so.1 => /lib/aarch64-linux-gnu/libvulkan.so.1 (0x0000ffff99600000)',
        '\tlibllama.so => not found',
        '\tlibllama.so => /usr/local/lib/libllama.so (0x0000ffff99600000)',
    ],
)
def test_the_ldd_check_refuses_a_missing_foreign_or_usr_local_library(
    tmp_path: Path, bad_line: str
):
    """Anything a player's machine may lack fails the build."""
    assert not ldd_passes(lines=[*GOOD_LDD_LINES, bad_line], tmp_path=tmp_path)


def test_the_cpu_variant_modules_are_checked_and_installed_in_bin(tmp_path: Path):
    """llama-server looks for its variants beside itself, never along the RPATH (b12167)."""
    stat = linux_task(name='Check that every CPU variant for this architecture was built')
    variables = ansible_variables(system='Linux', architecture='aarch64', home=tmp_path)
    variables['llama_cpp_install_directory'] = LINUX_INSTALL
    variables['item'] = 'armv8.2_2'
    template = tmp_path / 'path.j2'
    template.write_text(stat['ansible.builtin.stat']['path'], encoding='utf-8')
    installs = [
        task
        for task in role_tasks(role='llama_cpp', file_name='linux.yml')
        if task.get('name') == 'Install the CPU variant modules beside the binary'
    ]

    assert render_template(path=template, variables=variables) == (
        f'{LINUX_INSTALL}/bin/libggml-cpu-armv8.2_2.so'
    )
    assert installs[0]['ansible.builtin.command']['argv'][-1] == (
        '{{ llama_cpp_install_directory }}/bin/'
    )


def test_the_run_time_check_needs_the_cpu_variant_to_load_from_bin(tmp_path: Path):
    """A variant loads when llama-server's log line names a module in the runtime's bin/."""

    def holds(output: str) -> bool:
        return linux_assertion_holds(
            task_name=LOAD_TASK,
            extra={'llama_cpp_devices': {'stdout': '', 'stderr': output}},
            tmp_path=tmp_path,
        )

    assert holds(f'ggml_backend: x\n{GOOD_LOAD_LINE}\nAvailable devices:')
    assert not holds('Available devices:')
    assert not holds('load_backend: loaded CPU backend from /usr/local/bin/libggml-cpu-x64.so')
    assert not holds(
        f'load_backend: loaded CPU backend from {LINUX_INSTALL}/lib/libggml-cpu-x64.so'
    )


def test_the_glibc_floor_scans_the_binary_and_both_library_folders():
    """The .deb's libc6 floor must count the variant modules in bin/ and the libraries in lib/."""
    task = linux_task(name='Find the newest glibc the build needs')
    command = task['ansible.builtin.shell']['cmd']

    assert 'for file in bin/llama-server bin/*.so* lib/*.so*; do' in command


def test_the_run_time_variant_step_logs_at_the_verbosity_that_shows_the_backend_load():
    """The load_backend line is an INFO message that llama-server's default threshold hides."""
    task = linux_task(name='Run llama-server to see which CPU variant it loads')

    argv = task['ansible.builtin.command']['argv']

    assert argv[argv.index('--log-verbosity') + 1] == '4'
    # Before --list-devices, which the parser may act on and exit at once
    assert argv.index('--log-verbosity') < argv.index('--list-devices')


# The service's scripts, run as rendered for each platform (plans/lucid-circuit-linux.md, 5.3)
TEMPLATES = ROLES / 'ai_service' / 'templates'
PACKAGE_TEMPLATES = ROLES / 'ai_package' / 'templates'
SHELL_TEMPLATES = ['ai-service.sh.j2', 'run-llama-server.sh.j2', 'uninstall.sh.j2', 'setup.sh.j2']
SYSTEMS: list[Literal['Darwin', 'Linux']] = ['Darwin', 'Linux']
ARCHITECTURES: list[Literal['aarch64', 'x86_64']] = ['aarch64', 'x86_64']
# Every system with each architecture it reports
HOST_PLATFORMS: list[tuple[Literal['Darwin', 'Linux'], Architecture]] = [
    ('Darwin', 'arm64'),
    ('Linux', 'aarch64'),
    ('Linux', 'x86_64'),
]
# The inventory's macos value; Linux's is in group_vars/linux.yml
MAC_GPU_LAYERS = 99
# What runs in place of launchd's, systemd's and the package database's tools: each call is
# recorded, asking whether an agent runs says no, and systemd's user manager reports the
# environment in SERVICE_MANAGER_ENVIRONMENT. A test never reaches the real service
SERVICE_TOOL_STUB = """#!/bin/sh
printf '%s %s\\n' "$(basename "$0")" "$*" >> "$SERVICE_TOOL_LOG"
for argument in "$@"; do
    case "$argument" in
        is-active|print) exit 3 ;;
        show-environment) printf '%s' "${SERVICE_MANAGER_ENVIRONMENT:-}"; exit 0 ;;
    esac
done
exit 0
"""
# Stands in for llama-server: prints each argument it was given on its own line
# Stand in for the port tools, refusing any arguments but the ones the scripts must use, and
# printing what the real tool prints for a port in HELD_PORTS (ss -H: no header; lsof: a header
# and exit 0) or nothing for a free one (lsof then exits 1)
SS_STUB = """#!/bin/sh
if [ "$#" -ne 2 ] || [ "$1" != -Hltn ]; then
    echo "unexpected: ss $*" >> "$SERVICE_TOOL_LOG"
    exit 2
fi
port=${2#sport = :}
case "$2" in
    "sport = :$port") ;;
    *) echo "unexpected: ss $*" >> "$SERVICE_TOOL_LOG"; exit 2 ;;
esac
case " $HELD_PORTS " in
    *" $port "*) printf 'LISTEN 0      128        127.0.0.1:%s      0.0.0.0:*\\n' "$port" ;;
esac
exit 0
"""
LSOF_STUB = """#!/bin/sh
port=${2#-iTCP:}
if [ "$#" -ne 3 ] || [ "$1" != -nP ] || [ "$2" != "-iTCP:$port" ] \\
    || [ "$3" != -sTCP:LISTEN ]; then
    echo "unexpected: lsof $*" >> "$SERVICE_TOOL_LOG"
    exit 2
fi
case " $HELD_PORTS " in
    *" $port "*)
        echo 'COMMAND     PID  USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME'
        printf '%s  TCP 127.0.0.1:%s (LISTEN)\\n' \\
            'llama-ser 4242 other    5u  IPv4 0x1234567890abcdef      0t0' "$port"
        exit 0
        ;;
esac
exit 1
"""
LLAMA_SERVER_STUB = """#!/bin/sh
for argument in "$@"; do
    printf '%s\\n' "$argument"
done
"""
needs_a_posix_shell = pytest.mark.skipif(
    sys.platform == 'win32', reason="the service's scripts are POSIX sh"
)


class ServiceHome:
    """One user's home with the service's scripts rendered for a platform, and fake tools."""

    def __init__(self, *, system: Literal['Darwin', 'Linux'], home: Path, tools: Path) -> None:
        """Make the home and the fake tools, and work out the platform's variables."""
        self.system: Literal['Darwin', 'Linux'] = system
        self.home = home
        self.tools = tools
        self.tool_log = tools / 'calls.log'
        home.mkdir(parents=True, exist_ok=True)
        tools.mkdir(parents=True, exist_ok=True)
        self.variables = ansible_variables(
            system=system, architecture=host_architecture(system=system), home=home
        )
        self.variables['llama_cpp_install_directory'] = str(tools / 'runtime')
        if system == 'Darwin':
            self.variables['llama_cpp_gpu_layers'] = MAC_GPU_LAYERS
        for tool in ('launchctl', 'systemctl', 'pkgutil'):
            _write_executable(tools / tool, SERVICE_TOOL_STUB)
        _write_executable(tools / 'runtime' / 'bin' / 'llama-server', LLAMA_SERVER_STUB)
        self.tool_log.write_text('', encoding='utf-8')

    @property
    def user_root(self) -> Path:
        """The folder the variables put the user's data in."""
        return Path(self.variables['ai_user_root'])

    @property
    def config(self) -> Path:
        """The user's config folder."""
        return Path(self.variables['ai_service_config_directory'])

    def script(self, *, template: str) -> Path:
        """Render a service shell template, or the package's setup, into the tools folder.

        Returns:
            The rendered script.
        """
        source = TEMPLATES / template
        if not source.exists():
            source = PACKAGE_TEMPLATES / template
        rendered = self.tools / template.removesuffix('.j2')
        rendered.write_text(
            render_template(
                path=source, variables=self.variables | {'ai_service_agents': self.agents()}
            ),
            encoding='utf-8',
        )
        return rendered

    def run(
        self,
        *,
        template: str,
        arguments: list[str],
        environment: dict[str, str] | None = None,
        unset: tuple[str, ...] = (),
    ) -> subprocess.CompletedProcess[str]:
        """Run a rendered script with this home, its XDG folders and the fake tools first.

        Args:
            template: The template's file name.
            arguments: The script's arguments.
            environment: Variables added to the run's environment, or replacing its own.
            unset: Variables left out of the run's environment.

        Returns:
            The finished run.
        """
        return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - sh and a rendered script, as an argument list
            ['/bin/sh', str(self.script(template=template)), *arguments],
            env=self.environment(extra=environment, unset=unset),
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

    def environment(
        self, *, extra: dict[str, str] | None = None, unset: tuple[str, ...] = ()
    ) -> dict[str, str]:
        """Build a script's environment: this home, its XDG folders and the fake tools first.

        Returns:
            The variables.
        """
        run_environment = {
            'HOME': str(self.home),
            'XDG_DATA_HOME': str(self.home / '.local' / 'share'),
            'XDG_CACHE_HOME': str(self.home / '.cache'),
            'XDG_STATE_HOME': str(self.home / '.local' / 'state'),
            'PATH': os.pathsep.join([str(self.tools), '/usr/bin', '/bin', '/usr/sbin', '/sbin']),
            'SERVICE_TOOL_LOG': str(self.tool_log),
            **(extra or {}),
        }
        return {name: value for name, value in run_environment.items() if name not in unset}

    def tool_calls(self) -> list[str]:
        """Read every call the fake tools saw.

        Returns:
            One line per call: the tool's name and its arguments.
        """
        return self.tool_log.read_text(encoding='utf-8').splitlines()

    def download_every_model(self) -> None:
        """Leave an empty file wherever the picker looks for a model, for every size."""
        models = Path(self.variables['ai_models_directory'])
        models.mkdir(parents=True, exist_ok=True)
        for model in [*self.variables['ai_models_bonsai'].values()]:
            (models / model['model']['file']).touch()
            (models / model['vision']['file']).touch()
        for model in self.variables['ai_models_qwen'].values():
            (models / model['model']['file']).touch()

    def agents(self) -> list[dict[str, Any]]:
        """Work out the agents the ai_service role installs, by running its own set_fact tasks.

        Returns:
            Each agent's description.
        """
        return run_set_fact_tasks(
            tasks=role_tasks(role='ai_service', file_name='list_agents.yml'),
            variables=self.variables,
        )['ai_service_agents']

    def agent(self, *, role: str) -> dict[str, Any]:
        """Find the agent the 2B and 0.6B sizes run for a role, or the API's.

        Returns:
            The agent's description.
        """
        aliases = {'reasoning': 'bonsai-2-2b', 'embedding': 'qwen3-embedding-0.6b', 'api': 'api'}
        (agent,) = [agent for agent in self.agents() if agent['alias'] == aliases[role]]
        return agent

    def write_agent_settings(self, *, agent: dict[str, Any]) -> None:
        """Render an agent's settings where its runner reads them, with its files present."""
        self.config.mkdir(parents=True, exist_ok=True)
        (self.config / f'{agent["label"]}.env').write_text(
            render_template(
                path=TEMPLATES / 'agent.env.j2', variables=self.variables | {'agent': agent}
            ),
            encoding='utf-8',
        )
        Path(self.variables['ai_service_api_key_file']).touch()
        self.download_every_model()

    def llama_server_arguments(
        self, *, role: str, runtime_settings: str | None = None
    ) -> list[str]:
        """Run run-llama-server.sh for a role's agent, with llama-server replaced by the stub.

        Returns:
            The arguments the stub was given.
        """
        agent = self.agent(role=role)
        self.write_agent_settings(agent=agent)
        if runtime_settings is not None:
            (self.config / f'{agent["label"]}.env.runtime').write_text(
                runtime_settings, encoding='utf-8'
            )
        result = self.run(template='run-llama-server.sh.j2', arguments=[agent['label']])
        assert result.returncode == 0, result.stderr
        return result.stdout.splitlines()


def _write_executable(path: Path, text: str) -> None:
    """Write a script others can run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    path.chmod(0o755)


LONE_EXPRESSION = re.compile(r'\s*\{\{(?:(?!\{\{|\}\}).)*\}\}\s*', flags=re.DOTALL)


def set_fact_value(*, expression: Any, variables: dict[str, Any]) -> Any:
    """Work out one set_fact value as Ansible does, failing on a name Ansible wouldn't have.

    A lone expression keeps its type; text around expressions renders to text; a literal (an
    empty list) is taken as written.

    Returns:
        The value.
    """
    if isinstance(expression, str) and LONE_EXPRESSION.fullmatch(expression):
        return render_expression(expression=expression, variables=variables)
    value = render_value(value=expression, variables=variables)
    # render_value leaves a reference it can't resolve as written: that is a missing name here
    assert '{{' not in json.dumps(value), f'unresolved: {value}'
    return value


def run_set_fact_tasks(*, tasks: list[dict[str, Any]], variables: dict[str, Any]) -> dict[str, Any]:
    """Run a task file's set_fact tasks as Ansible would, loops and task variables included.

    Returns:
        The variables, with every fact the tasks set.
    """
    facts = dict(variables)
    for task in walk_tasks(tasks=tasks):
        if 'ansible.builtin.set_fact' not in task:
            continue
        items = (
            render_expression(expression=task['loop'], variables=facts)
            if 'loop' in task
            else [None]
        )
        for item in items:
            scope = facts | {'item': item}
            for name, value in task.get('vars', {}).items():
                scope[name] = render_value(value=value, variables=scope)
            for name, expression in task['ansible.builtin.set_fact'].items():
                facts[name] = set_fact_value(expression=expression, variables=scope)
    return facts


def parse_key_values(*, output: str) -> dict[str, str]:
    """Read ai-service.sh's key=value lines.

    Returns:
        Each key's value.
    """
    return dict(line.split('=', 1) for line in output.splitlines() if '=' in line)


@needs_a_posix_shell
@pytest.mark.parametrize('system', SYSTEMS)
@pytest.mark.parametrize(
    ('environment', 'expected'),
    [
        ({'AI_MEMORY_MB': '16384', 'AI_AVAILABLE_MB': '9216'}, {'bonsai': '2b', 'qwen': '0.6b'}),
        ({'AI_MEMORY_MB': '16384', 'AI_AVAILABLE_MB': '6144'}, {'reason': 'nothing-fits'}),
        ({'AI_MEMORY_MB': '8192', 'AI_AVAILABLE_MB': '6144'}, {'reason': 'nothing-fits'}),
        (
            {'AI_MEMORY_MB': '16384', 'AI_AVAILABLE_MB': '9216', 'AI_BONSAI_SIZE': '4b'},
            {'reason': 'nothing-fits'},
        ),
    ],
)
def test_the_picker_chooses_the_same_on_both_platforms(
    tmp_path: Path,
    system: Literal['Darwin', 'Linux'],
    environment: dict[str, str],
    expected: dict[str, str],
):
    """One choice on every platform: only how memory is read differs (section 6.4)."""
    service = ServiceHome(system=system, home=tmp_path / 'home', tools=tmp_path / 'tools')
    service.download_every_model()

    result = service.run(template='ai-service.sh.j2', arguments=['select'], environment=environment)

    values = parse_key_values(output=result.stdout)
    assert expected.items() <= values.items(), result.stdout + result.stderr
    assert result.returncode == (0 if 'bonsai' in expected else 3)
    assert values['memory_mb'] == environment['AI_MEMORY_MB']
    assert values['free_mb'] == environment['AI_AVAILABLE_MB']
    assert service.tool_calls() == []


@needs_a_posix_shell
@pytest.mark.parametrize('system', SYSTEMS)
def test_a_port_held_by_another_user_exits_4_and_starts_nothing(
    tmp_path: Path, system: Literal['Darwin', 'Linux']
):
    """A start finds a port taken by a real listening socket, exits 4 and starts nothing.

    The port is checked with the platform's own tool (lsof on a Mac, ss on Linux), so each
    rendering runs where its tool is installed: CircleCI's Linux image has neither, and a Mac has
    no ss. The socket is this user's, so this can't show that a Mac's lsof sees another user's
    socket (ss on Linux reads every user's); the stub-driven test below covers the control flow
    on every platform.
    """
    port_tool = 'lsof' if system == 'Darwin' else 'ss'
    if shutil.which(port_tool) is None:
        pytest.skip(f'{port_tool} is not installed here')
    service = ServiceHome(system=system, home=tmp_path / 'home', tools=tmp_path / 'tools')
    service.download_every_model()
    port = service.variables['ai_service_bonsai_ports']['2b']
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # A bind refused means something here already listens there, which is the case under
        # test; if nothing does, the start below finds the port free and the test fails
        with contextlib.suppress(OSError):
            holder.bind(('127.0.0.1', port))
            holder.listen()

        result = service.run(
            template='ai-service.sh.j2',
            arguments=['start'],
            environment={'AI_MEMORY_MB': '16384', 'AI_AVAILABLE_MB': '9216'},
        )
    finally:
        holder.close()

    assert f'reason=port-{port}-in-use' in result.stdout.splitlines(), result.stdout + result.stderr
    assert result.returncode == 4
    starts = [
        call for call in service.tool_calls() if ' start ' in f'{call} ' or 'bootstrap' in call
    ]
    assert starts == []


@needs_a_posix_shell
@pytest.mark.parametrize('system', SYSTEMS)
def test_every_script_runs_from_a_home_with_spaces(
    tmp_path: Path, system: Literal['Darwin', 'Linux']
):
    """A home with spaces and quotes reaches every command whole (Review focus 5)."""
    home = tmp_path / 'a home' / "with 'quotes'"
    service = ServiceHome(system=system, home=home, tools=tmp_path / 'tools')
    service.download_every_model()
    memory = {'AI_MEMORY_MB': '16384', 'AI_AVAILABLE_MB': '9216'}
    neighbour = home / 'kept.txt'
    neighbour.write_text('not the service', encoding='utf-8')

    select = service.run(template='ai-service.sh.j2', arguments=['select'], environment=memory)
    stop = service.run(template='ai-service.sh.j2', arguments=['stop'])
    status = service.run(template='ai-service.sh.j2', arguments=['status'])
    arguments = service.llama_server_arguments(role='reasoning')
    uninstall = service.run(template='uninstall.sh.j2', arguments=[])

    assert parse_key_values(output=select.stdout)['bonsai'] == '2b', select.stderr
    assert (stop.returncode, stop.stderr) == (0, '')
    assert (status.returncode, status.stdout, status.stderr) == (0, '', '')
    assert arguments[arguments.index('--model') + 1].startswith(str(home))
    assert (uninstall.returncode, uninstall.stderr) == (0, '')
    assert not service.config.exists()
    assert neighbour.read_text(encoding='utf-8') == 'not the service'


@needs_a_posix_shell
@pytest.mark.parametrize(('system', 'architecture'), HOST_PLATFORMS)
def test_every_rendered_script_passes_sh_n(
    tmp_path: Path, system: Literal['Darwin', 'Linux'], architecture: Architecture
):
    """Each shell template, and each agent's settings (which a script sources), parses as sh."""
    service = ServiceHome(system=system, home=tmp_path / 'home', tools=tmp_path / 'tools')
    service.variables['ansible_facts']['architecture'] = architecture
    rendered = [service.script(template=template) for template in SHELL_TEMPLATES]
    for agent in service.agents():
        service.write_agent_settings(agent=agent)
        rendered.append(service.config / f'{agent["label"]}.env')

    for script in rendered:
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - sh -n on a rendered file, as an argument list
            ['/bin/sh', '-n', str(script)], capture_output=True, text=True, check=False, timeout=60
        )
        assert (result.returncode, result.stderr) == (0, ''), script.name


def rendered_units(*, tmp_path: Path) -> dict[str, configparser.ConfigParser]:
    """Render every agent's systemd user unit for Linux and parse it.

    Returns:
        Each unit's parsed sections, by its file name.
    """
    service = ServiceHome(system='Linux', home=tmp_path / 'home', tools=tmp_path / 'tools')
    units = {}
    for agent in service.agents():
        unit = configparser.ConfigParser(interpolation=None, strict=True)
        unit.optionxform = str  # ty: ignore[invalid-assignment] - keep systemd's key case
        unit.read_string(
            render_template(
                path=TEMPLATES / 'agent.service.j2', variables=service.variables | {'agent': agent}
            )
        )
        units[f'{agent["label"]}.service'] = unit
    return units


def test_no_agent_unit_starts_at_login(tmp_path: Path):
    """No [Install] section, so nothing is enabled; ai-service.sh starts each when a game asks."""
    units = rendered_units(tmp_path=tmp_path)

    assert units, 'no unit rendered'
    for name, unit in units.items():
        label = name.removesuffix('.service')
        assert not unit.has_section('Install'), name
        assert unit['Service']['Type'] == 'simple'
        assert unit['Service']['Restart'] == 'on-failure'
        assert unit['Service']['RestartSec'] == '10'
        assert (
            unit['Service']['ExecStart'] == f'/opt/glitchygames/ai/bin/run-llama-server.sh {label}'
        )


def test_the_model_units_yield_the_cpu_and_never_use_a_cpuset(tmp_path: Path):
    """CPUWeight=20 on the models, the default on the API, and never AllowedCPUs=."""
    units = rendered_units(tmp_path=tmp_path)
    api_label = ansible_variables(system='Linux', architecture='aarch64', home=tmp_path)[
        'ai_service_api_label'
    ]
    unit_templates = [*ANSIBLE.rglob('*.service*.j2'), *ANSIBLE.rglob('*.conf*.j2')]

    for name, unit in units.items():
        if name == f'{api_label}.service':
            assert 'CPUWeight' not in unit['Service'], name
        else:
            assert unit['Service']['CPUWeight'] == '20', name
    assert TEMPLATES / 'agent.service.j2' in unit_templates
    for template in unit_templates:
        assert 'AllowedCPUs' not in template.read_text(encoding='utf-8'), (
            f'{template}: user services get no cpuset controller, so AllowedCPUs= would be '
            'silently ignored; CPUAffinity= pins (plans/lucid-circuit-linux.md, 6.2)'
        )


@needs_a_posix_shell
@pytest.mark.parametrize('system', SYSTEMS)
def test_run_llama_server_passes_threads_only_when_set(
    tmp_path: Path, system: Literal['Darwin', 'Linux']
):
    """An empty AI_THREADS leaves llama.cpp's default, as on a Mac, where Metal does the work."""
    service = ServiceHome(system=system, home=tmp_path / 'home', tools=tmp_path / 'tools')

    with_threads = service.llama_server_arguments(
        role='reasoning', runtime_settings='AI_THREADS=3\n'
    )
    without = service.llama_server_arguments(role='reasoning', runtime_settings='AI_THREADS=\n')

    assert with_threads[with_threads.index('--threads') + 1] == '3'
    assert '--threads' not in without


def test_the_threads_setting_is_empty_on_a_mac_and_leaves_two_cores_on_linux(tmp_path: Path):
    """Linux's is the host's CPU count less two, at least one; setup.sh writes each machine's."""
    mac = ansible_variables(system='Darwin', architecture='arm64', home=tmp_path)
    linux = ansible_variables(system='Linux', architecture='aarch64', home=tmp_path)

    assert not mac['ai_service_threads']
    assert isinstance(mac['ai_service_threads'], str)
    assert linux['ansible_facts']['processor_vcpus'] == 4
    assert linux['ai_service_threads'] == 2


@needs_a_posix_shell
@pytest.mark.parametrize('system', SYSTEMS)
def test_every_model_runs_an_8_bit_kv_cache_on_every_platform(
    tmp_path: Path, system: Literal['Darwin', 'Linux']
):
    """q8_0 keys and values for both models, with the flash attention a quantized V cache needs."""
    service = ServiceHome(system=system, home=tmp_path / 'home', tools=tmp_path / 'tools')
    eight_bit_cache = ['--cache-type-k', 'q8_0', '--cache-type-v', 'q8_0']

    for role in ('reasoning', 'embedding'):
        arguments = service.llama_server_arguments(role=role)
        pairs = list(itertools.pairwise(arguments))
        assert ('--flash-attn', 'on') in pairs, role
        assert ('--cache-type-k', 'q8_0') in pairs, role
        assert ('--cache-type-v', 'q8_0') in pairs, role
        if role == 'reasoning':
            assert ('--ctx-size', '131072') in pairs
    agent = service.agent(role='api')
    service.write_agent_settings(agent=agent)
    api_settings = (service.config / f'{agent["label"]}.env').read_text(encoding='utf-8')
    assert 'AI_CACHE_TYPE' not in api_settings
    assert not set(eight_bit_cache) & set(api_settings.split())


@needs_a_posix_shell
@pytest.mark.parametrize('system', SYSTEMS)
@pytest.mark.parametrize('role', ['reasoning', 'embedding'])
def test_validation_runs_what_the_service_runs(
    tmp_path: Path, system: Literal['Darwin', 'Linux'], role: str
):
    """ai_validate checks the settings the service runs with (the drift found 2026-11-18).

    Only what the validation exists to vary differs: its port, clear of the agents', and the
    --verbose log it reads.
    """
    service = ServiceHome(system=system, home=tmp_path / 'home', tools=tmp_path / 'tools')
    agent = service.agent(role=role)
    served = service.llama_server_arguments(role=role)
    facts = run_set_fact_tasks(tasks=role_tasks(role='ai_validate'), variables=service.variables)
    (checked,) = [
        model for model in facts['ai_validate_models'] if model['alias'] == agent['alias']
    ]
    validated = list(checked['arguments'])

    validated.remove('--verbose')
    validated[validated.index('--port') + 1] = served[served.index('--port') + 1]
    assert validated == served


@needs_a_posix_shell
@pytest.mark.parametrize('system', SYSTEMS)
def test_run_llama_server_reads_a_named_config_folder_in_place_of_the_users(
    tmp_path: Path, system: Literal['Darwin', 'Linux']
):
    """scripts/ai_model_comparison.py runs a size from settings of its own, beside the installed."""
    service = ServiceHome(system=system, home=tmp_path / 'home', tools=tmp_path / 'tools')
    agent = service.agent(role='reasoning')
    service.write_agent_settings(agent=agent)
    named = tmp_path / 'comparison'
    named.mkdir()
    shutil.copy(service.config / f'{agent["label"]}.env', named / f'{agent["label"]}.env')
    (named / f'{agent["label"]}.env.runtime').write_text('AI_PORT=23239\n', encoding='utf-8')

    result = service.run(template='run-llama-server.sh.j2', arguments=[str(named), agent['label']])

    arguments = result.stdout.splitlines()
    assert result.returncode == 0, result.stderr
    assert arguments[arguments.index('--port') + 1] == '23239'


@needs_a_posix_shell
@pytest.mark.parametrize('system', SYSTEMS)
@pytest.mark.parametrize('port_state', ['held', 'free'])
def test_a_port_the_port_tool_reports_held_stops_the_start(
    tmp_path: Path, system: Literal['Darwin', 'Linux'], port_state: Literal['held', 'free']
):
    """Exit 4 and no start when ss or lsof reports the port held; every agent started when free.

    The port tools are stubs that accept only the arguments the scripts must pass (ss's filter
    `sport = :PORT`, lsof's -nP -iTCP:PORT -sTCP:LISTEN), so this runs on every platform.
    """
    service = ServiceHome(system=system, home=tmp_path / 'home', tools=tmp_path / 'tools')
    _write_executable(service.tools / 'ss', SS_STUB)
    _write_executable(service.tools / 'lsof', LSOF_STUB)
    service.download_every_model()
    port = service.variables['ai_service_bonsai_ports']['2b']

    result = service.run(
        template='ai-service.sh.j2',
        arguments=['start'],
        environment={
            'AI_MEMORY_MB': '16384',
            'AI_AVAILABLE_MB': '9216',
            'HELD_PORTS': str(port) if port_state == 'held' else '',
        },
    )

    calls = service.tool_calls()
    # systemctl --user start LABEL.service, or launchctl bootstrap DOMAIN PLIST
    starts = [
        call
        for call in calls
        if call.split()[1:3] == ['--user', 'start'] or call.split()[1:2] == ['bootstrap']
    ]
    assert not [call for call in calls if call.startswith('unexpected')], calls
    if port_state == 'held':
        assert f'reason=port-{port}-in-use' in result.stdout.splitlines(), result.stdout
        assert result.returncode == 4
        assert starts == []
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'reason=' not in result.stdout
        assert len(starts) == 3, calls


# setup.sh, the one per-user path on Linux (plans/lucid-circuit-linux.md, 6.2 and 6.3), run as
# rendered with the package's share folder staged under tmp_path and fake downloads and cores
DOWNLOAD_BASE_URL = 'https://downloads.test'
# The runtime folder's name in a staged package; any name does, as nothing here builds one
RUNTIME_NAME = 'llama.cpp-test'
# Stands in for curl as setup.sh calls it: serves URL's file from DOWNLOAD_ROOT into --output,
# appending to what's there with --continue-at -, and with CURL_FAILS_AFTER_BYTES set, writes that
# many more bytes and fails as a dropped connection does (curl's exit 18, a partial transfer).
# CURL_DELAY_SECONDS makes each download take that long, so two runs can overlap
CURL_STUB = """#!/bin/sh
printf 'curl %s\\n' "$*" >> "$SERVICE_TOOL_LOG"
sleep "${CURL_DELAY_SECONDS:-0}"
output=""
url=""
resume=false
while [ "$#" -gt 0 ]; do
    case "$1" in
        --output) output=$2; shift ;;
        --continue-at) [ "$2" = - ] && resume=true; shift ;;
        --connect-timeout|--speed-time|--speed-limit|--retry|--retry-delay) shift ;;
        --*) ;;
        *) url=$1 ;;
    esac
    shift
done
source="$DOWNLOAD_ROOT/${url#"$DOWNLOAD_BASE_URL"/}"
[ -f "$source" ] || exit 22
have=0
if [ "$resume" = true ] && [ -f "$output" ]; then
    have=$(wc -c < "$output")
else
    : > "$output"
fi
if [ -n "${CURL_FAILS_AFTER_BYTES:-}" ]; then
    tail -c +"$(( have + 1 ))" "$source" | head -c "$CURL_FAILS_AFTER_BYTES" >> "$output"
    exit 18
fi
tail -c +"$(( have + 1 ))" "$source" >> "$output"
"""
OPENSSL_STUB = """#!/bin/sh
printf 'openssl %s\\n' "$*" >> "$SERVICE_TOOL_LOG"
[ "$*" = 'rand -hex 32' ] || exit 2
echo 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
"""
# Without --all, nproc counts only the cores this process may use, which under the setup unit's own
# CPUAffinity drop-in are the AI's: the stub answers 1 then, so a script counting that way fails
NPROC_STUB = """#!/bin/sh
if [ "${1:-}" = --all ]; then
    echo "$NPROC_ALL"
else
    echo 1
fi
"""
# Where util-linux's flock is missing (a Mac running the Linux rendering), setup.sh's call is
# served by the Mac's lockf on the same descriptor: the same kernel lock (flock(2)), refused with
# the same exit code 75. Any other call is refused, so a changed call is caught
FLOCK_STUB = """#!/bin/sh
if [ "$*" != '--nonblock --conflict-exit-code 75 9' ]; then
    echo "unexpected: flock $*" >> "$SERVICE_TOOL_LOG"
    exit 2
fi
exec /usr/bin/lockf -s -t 0 9
"""


class LinuxSetup:
    """A Linux user's machine as setup.sh finds it at login, with everything outside faked."""

    def __init__(self, *, tmp_path: Path, home: Path | None = None) -> None:
        """Stage the package's share folder, serve the selected models, and stub the tools."""
        self.service = ServiceHome(
            system='Linux', home=home or tmp_path / 'home', tools=tmp_path / 'tools'
        )
        self.program_root = tmp_path / 'opt' / 'glitchygames' / 'ai'
        self.downloads = tmp_path / 'downloads'
        self.cpu_root = tmp_path / 'sys' / 'devices' / 'system' / 'cpu'
        # The user's runtime and temporary folders, where setup.sh must keep no lock
        self.runtime_directory = tmp_path / 'run' / 'user'
        self.runtime_directory.mkdir(parents=True)
        self.temporary_directory = tmp_path / 'tmp'
        self.temporary_directory.mkdir()
        self.core_count = 4
        for tool, stub in (
            ('curl', CURL_STUB),
            ('openssl', OPENSSL_STUB),
            ('nproc', NPROC_STUB),
            ('ss', SS_STUB),
            ('lsof', LSOF_STUB),
        ):
            _write_executable(self.service.tools / tool, stub)
        if shutil.which('flock') is None:
            _write_executable(self.service.tools / 'flock', FLOCK_STUB)
        _write_executable(
            self.program_root / 'runtime' / RUNTIME_NAME / 'bin' / 'llama-server',
            LLAMA_SERVER_STUB,
        )
        self.service.variables['ai_models_base_url'] = DOWNLOAD_BASE_URL
        self.service.variables['ai_models_free_margin_bytes'] = 0
        for model_file in self.selected_model_files():
            self.serve(model_file=model_file, content=f'{model_file["file"]}\n'.encode())
        self.stage_share()

    def selected_model_files(self) -> list[dict[str, Any]]:
        """Name the files the default selection downloads: Bonsai 2B, its vision file, Qwen 0.6B.

        Returns:
            Each file's entry in the variables (its name, bytes and SHA-256), changed in place
            when a test serves other bytes.
        """
        bonsai = self.service.variables['ai_models_bonsai']['2b']
        qwen = self.service.variables['ai_models_qwen']['0.6b']
        return [bonsai['model'], bonsai['vision'], qwen['model']]

    def download_path(self, *, model_file: dict[str, Any]) -> Path:
        """Find where the fake download server keeps a model file.

        Returns:
            The file under the download root, at the path its pinned URL names.

        Raises:
            LookupError: The file is in no pinned model.
        """
        for model in (
            *self.service.variables['ai_models_bonsai'].values(),
            *self.service.variables['ai_models_qwen'].values(),
        ):
            if model_file in (model['model'], model.get('vision')):
                return (
                    self.downloads
                    / model['repository']
                    / 'resolve'
                    / model['revision']
                    / model_file['file']
                )
        message = f'{model_file["file"]} is no pinned model'
        raise LookupError(message)

    def serve(self, *, model_file: dict[str, Any], content: bytes, pinned: bool = True) -> None:
        """Serve a model file's bytes, pinning their size and SHA-256 unless told not to."""
        path = self.download_path(model_file=model_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        if pinned:
            model_file['bytes'] = len(content)
            model_file['sha256'] = hashlib.sha256(content).hexdigest()

    def stage_share(self) -> None:
        """Stage share/agents as ai_package stages it for the .deb: settings with placeholders.

        The package is built on one machine and installed on many, so its settings name the
        user's folder and the program folder by placeholders (ai_package's defaults), which
        setup.sh fills in for each user. The files come from the role's own tasks
        (PackageStaging), so setup.sh is tested against what the package really holds.
        """
        staging = PackageStaging(system='Linux', architecture='aarch64', home=self.service.home)
        program_stage = Path(
            ansible_variables(system='Linux', architecture='aarch64', home=self.service.home)[
                'ai_package_stage_root'
            ]
        )
        share = self.program_root / 'share' / 'agents'
        share.mkdir(parents=True, exist_ok=True)
        settings = [file for file in staging.staged if '/share/agents/' in file.destination]
        assert settings, 'the package stages no settings'
        for file in settings:
            target = self.program_root / Path(file.destination).relative_to(program_stage)
            target.write_text(staging.rendered(file=file), encoding='utf-8')
        # The runtime link the settings name the runtime by
        for file in staging.staged:
            if file.is_link:
                link = self.program_root / Path(file.destination).relative_to(program_stage)
                link.unlink(missing_ok=True)
                link.symlink_to(file.source)

    def set_cores(self, *, count: int, capacities: dict[int, int]) -> None:
        """Make the machine's cores: how many nproc --all counts, and which report a capacity."""
        self.core_count = count
        shutil.rmtree(self.cpu_root, ignore_errors=True)
        for core in range(count):
            (self.cpu_root / f'cpu{core}').mkdir(parents=True)
            if core in capacities:
                (self.cpu_root / f'cpu{core}' / 'cpu_capacity').write_text(
                    f'{capacities[core]}\n', encoding='utf-8'
                )

    def environment(self, *, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Build what setup.sh's run needs beyond the home: the package, the fakes, the memory.

        Returns:
            The variables.
        """
        return {
            'GLITCHYGAMES_AI_PROGRAM_ROOT': str(self.program_root),
            'AI_SYSFS_CPU_ROOT': str(self.cpu_root),
            'NPROC_ALL': str(self.core_count),
            'AI_MEMORY_MB': '16384',
            'AI_AVAILABLE_MB': '9216',
            'DOWNLOAD_ROOT': str(self.downloads),
            'DOWNLOAD_BASE_URL': DOWNLOAD_BASE_URL,
            'XDG_RUNTIME_DIR': str(self.runtime_directory),
            'TMPDIR': str(self.temporary_directory),
            **(extra or {}),
        }

    @property
    def lock(self) -> Path:
        """Name setup.sh's lock: a file in the user root it guards."""
        return self.user_root / 'config' / 'setup.lock'

    def run(
        self,
        *,
        template: str = 'setup.sh.j2',
        arguments: list[str] | None = None,
        extra: dict[str, str] | None = None,
        unset: tuple[str, ...] = (),
    ) -> subprocess.CompletedProcess[str]:
        """Run setup.sh, or another of the service's scripts, as rendered for Linux.

        Returns:
            The finished run.
        """
        return self.service.run(
            template=template,
            arguments=arguments or [],
            environment=self.environment(extra=extra),
            unset=unset,
        )

    @property
    def user_root(self) -> Path:
        """The user's folder when no variable moves it: the XDG data home's."""
        return self.service.home / '.local' / 'share' / 'glitchygames' / 'ai'

    def drop_in(self, *, label: str) -> Path:
        """Name an AI unit's CPU placement drop-in.

        Returns:
            The drop-in's path, in the user's systemd folder.
        """
        return (
            self.service.home
            / '.config'
            / 'systemd'
            / 'user'
            / f'{label}.service.d'
            / 'cpu-placement.conf'
        )

    def ai_unit_labels(self) -> list[str]:
        """Name every AI unit: each model's, the API's and the setup job's.

        Returns:
            The units' labels.
        """
        return [
            *[agent['label'] for agent in self.service.agents()],
            self.service.variables['ai_package_setup_label'],
        ]

    def model_settings(self, *, user_root: Path | None = None) -> dict[str, dict[str, str]]:
        """Read each model agent's settings as sh would, by their labels.

        Returns:
            Each model agent's settings.
        """
        config = (user_root or self.user_root) / 'config'
        settings = {}
        for agent in self.service.agents():
            if agent['role'] == 'api':
                continue
            text = (config / f'{agent["label"]}.env').read_text(encoding='utf-8')
            settings[agent['label']] = {
                name: shlex.split(value)[0] if shlex.split(value) else ''
                for name, value in (
                    line.split('=', 1) for line in text.splitlines() if re.match(r'[A-Z_]+=', line)
                )
            }
        return settings


def test_setup_carries_every_pinned_model(tmp_path: Path):
    """The rendered Linux setup.sh holds each downloaded size's revision and SHA-256 (section 7)."""
    service = ServiceHome(system='Linux', home=tmp_path / 'home', tools=tmp_path / 'tools')
    variables = service.variables

    setup = service.script(template='setup.sh.j2').read_text(encoding='utf-8')

    for size in variables['ai_models_bonsai_sizes']:
        model = variables['ai_models_bonsai'][size]
        assert model['revision'] in setup, size
        assert model['model']['sha256'] in setup, size
        assert model['vision']['sha256'] in setup, size
    for size in variables['ai_models_qwen_sizes']:
        model = variables['ai_models_qwen'][size]
        assert model['revision'] in setup, size
        assert model['model']['sha256'] in setup, size


def file_times(*, root: Path) -> dict[Path, int]:
    """Read the modification time of every file under a folder.

    Returns:
        Each file's time in nanoseconds, by its path.
    """
    return {path: path.stat().st_mtime_ns for path in sorted(root.rglob('*')) if path.is_file()}


@needs_a_posix_shell
def test_setup_on_linux_leaves_a_working_user_root(tmp_path: Path):
    """Models, keys (0600), settings and placement in place, and a second run changes nothing.

    The home has a space, quotes and an ampersand, which every setting must carry whole: the
    runner reads the settings setup.sh wrote and finds the model in them, and service.json parses.
    """
    setup = LinuxSetup(tmp_path=tmp_path, home=tmp_path / 'a home & more' / 'player\'s "den"')
    setup.set_cores(count=4, capacities={})

    first = setup.run()

    assert first.returncode == 0, first.stdout + first.stderr
    models = setup.user_root / 'models'
    for model_file in setup.selected_model_files():
        served = setup.download_path(model_file=model_file).read_bytes()
        assert (models / model_file['file']).read_bytes() == served
    assert not list(models.glob('*.part'))
    config = setup.user_root / 'config'
    for key in ('worker-api-key', 'service-api-key'):
        assert ((config / key).stat().st_mode & 0o777) == 0o600, key
    service_settings = json.loads((config / 'service.json').read_text(encoding='utf-8'))
    assert service_settings['worker_key_file'] == str(config / 'worker-api-key')
    assert service_settings['service_key_file'] == str(config / 'service-api-key')
    assert service_settings['control_script'] == str(setup.program_root / 'bin' / 'ai-service.sh')
    for agent in setup.service.agents():
        assert (config / f'{agent["label"]}.env').is_file(), agent['label']
    reasoning = setup.service.agent(role='reasoning')
    runner = setup.run(template='run-llama-server.sh.j2', arguments=[reasoning['label']])
    arguments = runner.stdout.splitlines()
    assert runner.returncode == 0, runner.stderr
    assert arguments[arguments.index('--model') + 1] == str(models / reasoning['model_file'])
    assert arguments[arguments.index('--mmproj') + 1] == str(models / reasoning['vision_file'])
    # Every file setup.sh wrote is set back in time, so a rewrite shows however coarse the clock
    every_file = file_times(root=setup.service.home)
    for path in every_file:
        os.utime(path, ns=(1_000_000_000, 1_000_000_000))
    before = file_times(root=setup.service.home)

    second = setup.run()

    assert second.returncode == 0, second.stdout + second.stderr
    assert file_times(root=setup.service.home) == before
    downloads = [call for call in setup.service.tool_calls() if call.startswith('curl')]
    assert len(downloads) == len(setup.selected_model_files()), 'the second run downloaded'


class PlacementRow(BaseModel):
    """One machine of section 6.2's table, and where setup.sh must place each part on it."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    cores: int
    # By core; a core missing here reports no cpu_capacity
    capacities: dict[int, int]
    threads: int
    # The AI units' CPUAffinity=, and the placement file's lists; None: nothing placed
    affinity: str | None
    game: list[int] | None
    mirror: list[int] | None
    ai: list[int] | None


PLACEMENT_ROWS = [
    PlacementRow(
        cores=4,
        capacities=dict.fromkeys(range(4), 1024),
        threads=2,
        affinity='2 3',
        game=[0],
        mirror=[1],
        ai=[2, 3],
    ),
    PlacementRow(
        cores=4, capacities={}, threads=2, affinity='2 3', game=[0], mirror=[1], ai=[2, 3]
    ),
    PlacementRow(
        cores=8,
        capacities=dict.fromkeys(range(8), 1024),
        threads=6,
        affinity='2 3 4 5 6 7',
        game=[0],
        mirror=[1],
        ai=[2, 3, 4, 5, 6, 7],
    ),
    # RK3588-style: the little cores numbered first
    PlacementRow(
        cores=8,
        capacities={**dict.fromkeys(range(4), 446), **dict.fromkeys(range(4, 8), 1024)},
        threads=6,
        affinity='0 1 2 3 6 7',
        game=[4],
        mirror=[5],
        ai=[0, 1, 2, 3, 6, 7],
    ),
    # Three tiers: core 7 fastest, 4-6 big, 0-3 little
    PlacementRow(
        cores=8,
        capacities={**dict.fromkeys(range(4), 325), **dict.fromkeys(range(4, 7), 870), 7: 1024},
        threads=6,
        affinity='0 1 2 3 5 6',
        game=[7],
        mirror=[4],
        ai=[0, 1, 2, 3, 5, 6],
    ),
    # The big cores numbered first
    PlacementRow(
        cores=8,
        capacities={**dict.fromkeys(range(4), 1024), **dict.fromkeys(range(4, 8), 446)},
        threads=6,
        affinity='2 3 4 5 6 7',
        game=[0],
        mirror=[1],
        ai=[2, 3, 4, 5, 6, 7],
    ),
    # Only cores 0-1 report a capacity: ranked by number, though core 1 reports the higher
    PlacementRow(
        cores=4,
        capacities={0: 446, 1: 1024},
        threads=2,
        affinity='2 3',
        game=[0],
        mirror=[1],
        ai=[2, 3],
    ),
    PlacementRow(
        cores=3,
        capacities=dict.fromkeys(range(3), 1024),
        threads=1,
        affinity='2',
        game=[0],
        mirror=[1],
        ai=[2],
    ),
    # Two cores: the mirror shares the AI's core, not the game's
    PlacementRow(
        cores=2,
        capacities={0: 446, 1: 1024},
        threads=1,
        affinity='0',
        game=[1],
        mirror=[0],
        ai=[0],
    ),
    PlacementRow(
        cores=1, capacities={0: 1024}, threads=1, affinity=None, game=None, mirror=None, ai=None
    ),
]
PLACEMENT_ROW_NAMES = [
    '4-alike',
    '4-no-capacities',
    '8-alike',
    '8-rk3588-little-first',
    '8-three-tiers',
    '8-big-first',
    '4-only-some-report',
    '3-alike',
    '2-cores',
    '1-core',
]


@needs_a_posix_shell
@pytest.mark.parametrize('row', PLACEMENT_ROWS, ids=PLACEMENT_ROW_NAMES)
def test_setup_gives_the_game_the_mirror_and_the_ai_their_own_cores(
    tmp_path: Path, row: PlacementRow
):
    """The game on the fastest core, the mirror on the next, everything AI on the rest (6.2).

    Ranked by cpu_capacity, ties by number, and by number alone unless every core reports one.
    Every AI unit (both model units, the API, setup) gets the same drop-in. Where one core
    leaves nothing to place, an earlier placement is removed.
    """
    setup = LinuxSetup(tmp_path=tmp_path)
    placement_file = setup.user_root / 'config' / 'cpu-placement.json'
    if row.affinity is None:
        setup.set_cores(count=4, capacities={})
        earlier = setup.run()
        assert earlier.returncode == 0, earlier.stdout + earlier.stderr
        assert placement_file.exists()
        assert all(setup.drop_in(label=label).exists() for label in setup.ai_unit_labels())
    setup.set_cores(count=row.cores, capacities=row.capacities)

    result = setup.run()

    assert result.returncode == 0, result.stdout + result.stderr
    for label, settings in setup.model_settings().items():
        assert settings['AI_THREADS'] == str(row.threads), label
    assert 'systemctl --user daemon-reload' in setup.service.tool_calls()
    if row.affinity is None:
        assert not placement_file.exists()
        for label in setup.ai_unit_labels():
            assert not setup.drop_in(label=label).exists(), label
            assert not setup.drop_in(label=label).parent.exists(), label
        return
    for label in setup.ai_unit_labels():
        unit = configparser.ConfigParser(interpolation=None, strict=True)
        unit.optionxform = str  # ty: ignore[invalid-assignment] - keep systemd's key case
        unit.read_string(setup.drop_in(label=label).read_text(encoding='utf-8'))
        assert unit.sections() == ['Service'], label
        assert dict(unit['Service']) == {'CPUAffinity': row.affinity}, label
    placement = json.loads(placement_file.read_text(encoding='utf-8'))
    assert placement == {'game': row.game, 'mirror': row.mirror, 'ai': row.ai}
    assert [int(core) for core in row.affinity.split()] == placement['ai']
    # The invariants, on every row
    assert not set(placement['game']) & set(placement['ai'])
    named = {*placement['game'], *placement['mirror'], *placement['ai']}
    assert all(0 <= core < row.cores for core in named)
    assert named == set(range(row.cores))
    game_capacity = row.capacities.get(placement['game'][0])
    if game_capacity is not None:
        assert all(row.capacities.get(core, 0) <= game_capacity for core in placement['ai'])


@needs_a_posix_shell
def test_a_failed_download_leaves_no_model_and_retries(tmp_path: Path):
    """Exit 1 with only the .part kept; the next run resumes it and completes (Review focus 3)."""
    setup = LinuxSetup(tmp_path=tmp_path)
    setup.set_cores(count=4, capacities={})
    model_file = setup.selected_model_files()[0]
    models = setup.user_root / 'models'

    failed = setup.run(extra={'CURL_FAILS_AFTER_BYTES': '5'})

    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert not (models / model_file['file']).exists()
    served = setup.download_path(model_file=model_file).read_bytes()
    assert (models / f'{model_file["file"]}.part').read_bytes() == served[:5]

    retried = setup.run()

    assert retried.returncode == 0, retried.stdout + retried.stderr
    assert (models / model_file['file']).read_bytes() == served
    assert not (models / f'{model_file["file"]}.part').exists()
    resumed = [
        call
        for call in setup.service.tool_calls()
        if call.startswith('curl') and call.endswith(model_file['file'])
    ]
    assert '--continue-at -' in resumed[-1]


@needs_a_posix_shell
def test_a_wrong_hash_is_discarded(tmp_path: Path):
    """A download whose bytes don't match the pin leaves neither the model nor its .part."""
    setup = LinuxSetup(tmp_path=tmp_path)
    setup.set_cores(count=4, capacities={})
    model_file = setup.selected_model_files()[0]
    setup.serve(model_file=model_file, content=b'not the pinned bytes\n', pinned=False)
    models = setup.user_root / 'models'

    result = setup.run()

    assert result.returncode == 1, result.stdout + result.stderr
    assert not (models / model_file['file']).exists()
    assert not (models / f'{model_file["file"]}.part').exists()
    assert f'{model_file["file"]} had the wrong SHA-256' in result.stdout


USER_ROOT_CASES = [
    pytest.param({}, id='xdg-unset'),
    pytest.param({'XDG_DATA_HOME': 'xdg data'}, id='xdg-set'),
    pytest.param(
        {'XDG_DATA_HOME': 'xdg data', 'GLITCHYGAMES_AI_USER_ROOT': 'user root'}, id='user-root'
    ),
    pytest.param(
        {'XDG_DATA_HOME': 'xdg data', 'GLITCHYGAMES_AI_INSTALL_ROOT': 'one folder'},
        id='install-root',
    ),
    pytest.param(
        {
            'XDG_DATA_HOME': 'xdg data',
            'GLITCHYGAMES_AI_INSTALL_ROOT': 'one folder',
            'GLITCHYGAMES_AI_USER_ROOT': 'user root',
        },
        id='user-root-over-install-root',
    ),
    # An empty variable is unset, in the engine and in every script
    pytest.param(
        {'XDG_DATA_HOME': 'xdg data', 'GLITCHYGAMES_AI_USER_ROOT': ''}, id='empty-user-root'
    ),
    pytest.param(
        {
            'XDG_DATA_HOME': 'xdg data',
            'GLITCHYGAMES_AI_INSTALL_ROOT': '',
            'GLITCHYGAMES_AI_USER_ROOT': '',
        },
        id='empty-install-and-user-roots',
    ),
    pytest.param(
        {
            'XDG_DATA_HOME': 'xdg data',
            'GLITCHYGAMES_AI_INSTALL_ROOT': 'one folder',
            'GLITCHYGAMES_AI_USER_ROOT': '',
        },
        id='empty-user-root-over-install-root',
    ),
]
USER_ROOT_VARIABLES = (
    'XDG_DATA_HOME',
    'GLITCHYGAMES_AI_USER_ROOT',
    'GLITCHYGAMES_AI_INSTALL_ROOT',
)


@needs_a_posix_shell
@pytest.mark.parametrize('folders', USER_ROOT_CASES)
def test_the_engine_and_the_scripts_agree_on_the_user_root(
    tmp_path: Path,
    folders: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    """One rule for the user's folder (Review focus 1): the engine's, in every script.

    setup.sh fills that folder; ai-service.sh hands it to systemd's user manager before it
    starts a unit, which can't see the shell's variables; and run-llama-server.sh, as the unit
    starts it with only the manager's environment, reads its settings from there.
    """
    setup = LinuxSetup(tmp_path=tmp_path)
    setup.set_cores(count=4, capacities={})
    variables = {name: str(tmp_path / folder) if folder else '' for name, folder in folders.items()}
    mocker.patch.object(ai_link.sys, 'platform', 'linux')
    monkeypatch.setenv('HOME', str(setup.service.home))
    for name in (*USER_ROOT_VARIABLES, ai_link.PROGRAM_ROOT_ENVIRONMENT_VARIABLE):
        monkeypatch.delenv(name, raising=False)
    for name, value in variables.items():
        monkeypatch.setenv(name, value)
    locations = ai_link.service_locations()
    assert locations is not None
    engine_root = locations.user_root
    unset = tuple(name for name in USER_ROOT_VARIABLES if name not in variables)

    filled = setup.run(extra=variables, unset=unset)
    started = setup.run(
        template='ai-service.sh.j2', arguments=['start'], extra=variables, unset=unset
    )

    assert filled.returncode == 0, filled.stdout + filled.stderr
    assert (engine_root / 'config' / 'service.json').is_file()
    assert (engine_root / 'models' / setup.selected_model_files()[0]['file']).is_file()
    assert started.returncode == 0, started.stdout + started.stderr
    calls = setup.service.tool_calls()
    handed_over = f'systemctl --user set-environment GLITCHYGAMES_AI_USER_ROOT={engine_root}'
    first_start = next(index for index, call in enumerate(calls) if ' --user start ' in call)
    assert handed_over in calls[:first_start], calls
    # The unit's run: HOME and what the manager was handed, none of the shell's own folders
    reasoning = setup.service.agent(role='reasoning')
    unit_run = setup.service.run(
        template='run-llama-server.sh.j2',
        arguments=[reasoning['label']],
        environment={'GLITCHYGAMES_AI_USER_ROOT': str(engine_root)},
        unset=('XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME'),
    )
    arguments = unit_run.stdout.splitlines()
    assert unit_run.returncode == 0, unit_run.stderr
    assert arguments[arguments.index('--model') + 1] == str(
        engine_root / 'models' / reasoning['model_file']
    )


@needs_a_posix_shell
@pytest.mark.parametrize(
    ('manager_data_home', 'own_data_home', 'expected'),
    [
        pytest.param('elsewhere', 'xdg data', 'warned', id='different'),
        pytest.param('xdg data', 'xdg data', 'silent', id='same'),
        pytest.param(None, None, 'silent', id='both-unset'),
        pytest.param(None, 'xdg data', 'warned', id='only-this-run-sets-it'),
    ],
)
def test_setup_warns_when_systemd_sees_another_data_home(
    tmp_path: Path,
    manager_data_home: str | None,
    own_data_home: str | None,
    expected: Literal['warned', 'silent'],
):
    """A unit started other than through ai-service.sh would look in the manager's folder."""
    setup = LinuxSetup(tmp_path=tmp_path)
    setup.set_cores(count=4, capacities={})
    manager_environment = f'HOME={setup.service.home}\nLANG=C.UTF-8\n'
    if manager_data_home is not None:
        manager_environment += f'XDG_DATA_HOME={tmp_path / manager_data_home}\n'
    extra = {'SERVICE_MANAGER_ENVIRONMENT': manager_environment}
    if own_data_home is not None:
        extra['XDG_DATA_HOME'] = str(tmp_path / own_data_home)

    result = setup.run(extra=extra, unset=() if own_data_home else ('XDG_DATA_HOME',))

    assert result.returncode == 0, result.stdout + result.stderr
    warnings = [line for line in result.stdout.splitlines() if 'XDG_DATA_HOME' in line]
    assert bool(warnings) is (expected == 'warned'), result.stdout
    assert 'systemctl --user show-environment' in setup.service.tool_calls()


@needs_a_posix_shell
def test_the_user_uninstaller_stops_the_units_and_removes_what_setup_wrote(tmp_path: Path):
    """uninstall.sh, which the package installs as uninstall-user.sh too (6.1, 6.9).

    It stops the user's units, then removes their settings, keys, CPU placement, cache and logs;
    the models stay unless asked for, and then the whole user folder goes.
    """
    setup = LinuxSetup(tmp_path=tmp_path)
    setup.set_cores(count=4, capacities={})
    assert setup.run().returncode == 0
    cache = setup.service.home / '.cache' / 'glitchygames' / 'ai'
    logs = setup.service.home / '.local' / 'state' / 'glitchygames' / 'ai' / 'logs'
    for folder in (cache, logs):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'left.txt').write_text('written by the service\n', encoding='utf-8')
    neighbour = setup.service.home / '.config' / 'systemd' / 'user' / 'kept.service'
    neighbour.write_text('[Service]\n', encoding='utf-8')

    kept_models = setup.run(template='uninstall.sh.j2')

    assert kept_models.returncode == 0, kept_models.stdout + kept_models.stderr
    calls = setup.service.tool_calls()
    stopped = calls.index('systemctl --user stop ai.glitchygames.*.service')
    # systemd forgets the removed drop-ins only when it reloads
    assert 'systemctl --user daemon-reload' in calls[stopped:]
    assert not (setup.user_root / 'config').exists()
    assert not cache.exists()
    assert not logs.exists()
    for label in setup.ai_unit_labels():
        assert not setup.drop_in(label=label).parent.exists(), label
    assert neighbour.exists()
    assert (setup.user_root / 'models').is_dir()

    removed = setup.run(template='uninstall.sh.j2', arguments=['--remove-models'])

    assert removed.returncode == 0, removed.stdout + removed.stderr
    assert not setup.user_root.exists()


# The package: ai_package's tasks, walked as Ansible runs them on one host, give every file the
# package stages and the variables each was rendered with (plans/lucid-circuit-linux.md, 6.7)
class StagedFile(BaseModel):
    """One file or folder an ai_package task puts in the package's stage or scripts."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    task_name: str
    source: str
    destination: str
    variables: dict[str, Any]
    # A symbolic link at the destination, naming the source (ansible.builtin.file, state link)
    is_link: bool = False


class PackageStaging:
    """Walk ai_package's task files for one host, as Ansible would run them, recording each copy.

    Ansible's precedence is kept where it decides what a file holds: a block's and a task's own
    variables lose to a fact set earlier (the llama_cpp role's install directory is one), and an
    include's variables win over both. Only the tasks that stage something are run: template,
    copy, rsync, a link and set_fact, and the imports, includes and blocks around them; a `when`
    on one of those is evaluated, so one naming a value Ansible would not have fails here too.
    """

    def __init__(
        self,
        *,
        system: Literal['Darwin', 'Linux'],
        architecture: Architecture,
        home: Path,
        facts: dict[str, Any] | None = None,
        runtime_name: str = RUNTIME_NAME,
    ) -> None:
        """Set the facts the roles before ai_package leave: llama.cpp's build, the agents."""
        self.system: Literal['Darwin', 'Linux'] = system
        self.architecture: Architecture = architecture
        self.home = home
        variables = ansible_variables(system=system, architecture=architecture, home=home)
        runtime_root = variables['llama_cpp_install_root']
        self.facts: dict[str, Any] = {
            # Set by the llama_cpp role (set_fact), and by its Linux checks
            'llama_cpp_install_directory': f'{runtime_root}/runtime/{runtime_name}',
            'llama_cpp_glibc_version': '2.39',
            'llama_cpp_libstdcxx_version': '14.1.0',
            # Set by the ai_service role (set_fact)
            'ai_service_agents': run_set_fact_tasks(
                tasks=role_tasks(role='ai_service', file_name='list_agents.yml'),
                variables=variables,
            )['ai_service_agents'],
            # The inventory's macos value (Linux's is a group variable)
            **({'llama_cpp_gpu_layers': MAC_GPU_LAYERS} if system == 'Darwin' else {}),
            **(facts or {}),
        }
        self.staged: list[StagedFile] = []
        self._walk(file_name='main.yml', block_variables={}, include_variables={})

    def scope(
        self,
        *,
        block_variables: dict[str, Any],
        include_variables: dict[str, Any],
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Work out the variables one task sees, by Ansible's precedence.

        Returns:
            The variables, every reference resolved.
        """
        return ansible_variables(
            system=self.system,
            architecture=self.architecture,
            home=self.home,
            overrides={
                'playbook_dir': str(ANSIBLE),
                **block_variables,
                **self.facts,
                **include_variables,
                **(extra or {}),
            },
        )

    def _condition_holds(self, *, task: dict[str, Any], variables: dict[str, Any]) -> bool:
        conditions = task.get('when', [])
        for condition in [conditions] if isinstance(conditions, str) else conditions:
            if not render_expression(expression='{{ ' + condition + ' }}', variables=variables):
                return False
        return True

    def _walk(
        self,
        *,
        file_name: str,
        block_variables: dict[str, Any],
        include_variables: dict[str, Any],
    ) -> None:
        for task in role_tasks(role='ai_package', file_name=file_name):
            self._run(
                task=task, block_variables=block_variables, include_variables=include_variables
            )

    def _run(
        self,
        *,
        task: dict[str, Any],
        block_variables: dict[str, Any],
        include_variables: dict[str, Any],
    ) -> None:
        # A task's own variables rank with a block's: both lose to a fact
        own_variables = {**block_variables, **task.get('vars', {})}
        nests = any(
            key in task
            for key in ('block', 'ansible.builtin.import_tasks', 'ansible.builtin.include_tasks')
        )
        if not (nests or self._stages(task=task) or 'ansible.builtin.set_fact' in task):
            return
        variables = self.scope(block_variables=own_variables, include_variables=include_variables)
        if not self._condition_holds(task=task, variables=variables):
            return
        if nests:
            self._descend(
                task=task,
                block_variables=block_variables,
                include_variables=include_variables,
                variables=variables,
            )
        elif 'ansible.builtin.set_fact' in task:
            for name, expression in task['ansible.builtin.set_fact'].items():
                self.facts[name] = render_value(value=expression, variables=variables)
        else:
            self._stage(
                task=task,
                own_variables=own_variables,
                include_variables=include_variables,
                variables=variables,
            )

    @staticmethod
    def _stages(*, task: dict[str, Any]) -> bool:
        argv = task.get('ansible.builtin.command', {}).get('argv', [None])
        return (
            'ansible.builtin.template' in task
            or 'ansible.builtin.copy' in task
            or task.get('ansible.builtin.file', {}).get('state') == 'link'
            or argv[0] == 'rsync'
        )

    def _descend(
        self,
        *,
        task: dict[str, Any],
        block_variables: dict[str, Any],
        include_variables: dict[str, Any],
        variables: dict[str, Any],
    ) -> None:
        own_variables = {**block_variables, **task.get('vars', {})}
        include = task.get('ansible.builtin.include_tasks')
        if 'block' in task:
            for child in task['block']:
                self._run(
                    task=child,
                    block_variables=own_variables,
                    include_variables=include_variables,
                )
        elif 'ansible.builtin.import_tasks' in task:
            # Static: its variables apply to each task as the task's own
            self._walk(
                file_name=task['ansible.builtin.import_tasks'],
                block_variables=own_variables,
                include_variables=include_variables,
            )
        elif include:
            file_name = render_value(
                value=include if isinstance(include, str) else include['file'],
                variables=variables,
            )
            if Path(file_name).is_absolute():
                # Another role's task file (the agents' list): its facts, as Ansible sets them
                tasks = yaml.safe_load(Path(file_name).read_text(encoding='utf-8'))
                facts = run_set_fact_tasks(tasks=tasks, variables=variables)
                for listed in walk_tasks(tasks=tasks):
                    for name in listed.get('ansible.builtin.set_fact', {}):
                        self.facts[name] = facts[name]
                return
            self._walk(
                file_name=file_name,
                block_variables=block_variables,
                # An include's variables win over facts
                include_variables={**include_variables, **task.get('vars', {})},
            )

    def _stage(
        self,
        *,
        task: dict[str, Any],
        own_variables: dict[str, Any],
        include_variables: dict[str, Any],
        variables: dict[str, Any],
    ) -> None:
        command = task.get('ansible.builtin.command')
        if command:
            self.staged.append(
                StagedFile(
                    task_name=task['name'],
                    source=render_value(value=command['argv'][-2], variables=variables),
                    destination=render_value(value=command['argv'][-1], variables=variables),
                    variables=variables,
                )
            )
            return
        link = task.get('ansible.builtin.file')
        if link:
            self.staged.append(
                StagedFile(
                    task_name=task['name'],
                    source=render_value(value=link['src'], variables=variables),
                    destination=render_value(value=link['dest'], variables=variables),
                    variables=variables,
                    is_link=True,
                )
            )
            return
        module = task.get('ansible.builtin.template') or task['ansible.builtin.copy']
        loop_variable = task.get('loop_control', {}).get('loop_var', 'item')
        items = render_value(value=task['loop'], variables=variables) if 'loop' in task else [None]
        for item in items:
            item_variables = (
                variables
                if item is None
                else self.scope(
                    block_variables=own_variables,
                    include_variables=include_variables,
                    extra={loop_variable: item},
                )
            )
            self.staged.append(
                StagedFile(
                    task_name=task['name'],
                    source=render_value(value=module['src'], variables=item_variables),
                    destination=render_value(value=module['dest'], variables=item_variables),
                    variables=item_variables,
                )
            )

    def relative_destinations(self) -> list[str]:
        """Name every staged file by its path under the package folder.

        Returns:
            The paths, sorted.
        """
        package = ansible_variables(
            system=self.system, architecture=self.architecture, home=self.home
        )['ai_package_directory']
        return sorted(str(Path(file.destination).relative_to(package)) for file in self.staged)

    def rendered(self, *, file: StagedFile) -> str:
        """Render a staged template as its task does.

        Returns:
            The text the task writes.
        """
        source = Path(file.source)
        if not source.is_absolute():
            source = PACKAGE_TEMPLATES / source
        return render_template(path=source, variables=file.variables)


# What the Mac's ai_package staged before the .deb shared its tasks (captured from the role at
# 6cd0b28b by PackageStaging): the .pkg's contents must not change
MAC_STAGED_BEFORE_THE_DEB = [
    'distribution.xml',
    'scripts/postinstall',
    f'stage/{MAC_ROOT_NAME}/bin/ai-service.sh',
    f'stage/{MAC_ROOT_NAME}/bin/run-llama-server.sh',
    f'stage/{MAC_ROOT_NAME}/bin/setup.sh',
    f'stage/{MAC_ROOT_NAME}/bin/uninstall.sh',
    f'stage/{MAC_ROOT_NAME}/runtime/{RUNTIME_NAME}/bin/llama-server',
    f'stage/{MAC_ROOT_NAME}/runtime/{RUNTIME_NAME}/notices/llama.cpp-LICENSE',
    f'stage/{MAC_ROOT_NAME}/share/agents/ai.glitchygames.api.env.template',
    f'stage/{MAC_ROOT_NAME}/share/agents/ai.glitchygames.api.plist.template',
    f'stage/{MAC_ROOT_NAME}/share/agents/ai.glitchygames.bonsai-2-27b.llama-cpp.env.template',
    f'stage/{MAC_ROOT_NAME}/share/agents/ai.glitchygames.bonsai-2-27b.llama-cpp.plist.template',
    f'stage/{MAC_ROOT_NAME}/share/agents/ai.glitchygames.bonsai-2-2b.llama-cpp.env.template',
    f'stage/{MAC_ROOT_NAME}/share/agents/ai.glitchygames.bonsai-2-2b.llama-cpp.plist.template',
    f'stage/{MAC_ROOT_NAME}/share/agents/ai.glitchygames.bonsai-2-4b.llama-cpp.env.template',
    f'stage/{MAC_ROOT_NAME}/share/agents/ai.glitchygames.bonsai-2-4b.llama-cpp.plist.template',
    f'stage/{MAC_ROOT_NAME}/share/agents/ai.glitchygames.bonsai-2-9b.llama-cpp.env.template',
    f'stage/{MAC_ROOT_NAME}/share/agents/ai.glitchygames.bonsai-2-9b.llama-cpp.plist.template',
    f'stage/{MAC_ROOT_NAME}/share/agents/ai.glitchygames.qwen3-embedding-0.6b.llama-cpp.env.template',
    f'stage/{MAC_ROOT_NAME}/share/agents/ai.glitchygames.qwen3-embedding-0.6b.llama-cpp.plist.template',
    f'stage/{MAC_ROOT_NAME}/share/agents/service.json.template',
    f'stage/{MAC_ROOT_NAME}/share/notices',
    f'stage/{MAC_ROOT_NAME}/sidecar',
]


def test_the_mac_package_stage_is_unchanged_but_for_the_runtime_link(tmp_path: Path):
    """Sharing the staging with the .deb leaves the .pkg's files as they were, plus one.

    The one is runtime/current, which the settings name the runtime through
    (bugs/2026-11-18-mac-package-settings-name-builders-runtime.md).
    """
    staging = PackageStaging(system='Darwin', architecture='arm64', home=tmp_path)

    assert staging.relative_destinations() == sorted([
        *MAC_STAGED_BEFORE_THE_DEB,
        f'stage/{MAC_ROOT_NAME}/runtime/current',
    ])


def staged_file(*, staging: PackageStaging, relative: str) -> StagedFile:
    """Find the one staged file at a path under the package folder.

    Returns:
        The staged file.
    """
    (found,) = [file for file in staging.staged if file.destination.endswith(f'/{relative}')]
    return found


@pytest.mark.parametrize('architecture', ARCHITECTURES)
def test_the_linux_package_stages_every_unit_script_and_setting(
    tmp_path: Path, architecture: Literal['aarch64', 'x86_64']
):
    """The .deb holds the units, the scripts (one uninstaller), the settings and Debian's files.

    The runtime and the sidecar are built straight into the stage (Tasks 2 and 5), so nothing
    copies them onto themselves.
    """
    staging = PackageStaging(system='Linux', architecture=architecture, home=tmp_path)
    destinations = staging.relative_destinations()
    labels = [agent['label'] for agent in staging.facts['ai_service_agents']]
    program = 'stage/opt/glitchygames/ai'

    expected = {
        'stage/DEBIAN/control',
        'stage/DEBIAN/postinst',
        'stage/DEBIAN/prerm',
        'stage/DEBIAN/postrm',
        'stage/usr/lib/systemd/user/ai.glitchygames.setup.service',
        *[f'stage/usr/lib/systemd/user/{label}.service' for label in labels],
        *[f'{program}/bin/{script}' for script in LINUX_PACKAGE_SCRIPTS],
        *[f'{program}/share/agents/{label}.env.template' for label in labels],
        f'{program}/share/agents/service.json.template',
        f'{program}/share/notices',
        f'{program}/runtime/current',
    }
    assert set(destinations) == expected
    assert len(destinations) == len(expected), 'a file is staged twice'
    assert not [file for file in staging.staged if file.source.rstrip('/') == file.destination]


# The Linux package's bin/: setup.sh's counterpart is uninstall-user.sh, its one uninstaller
LINUX_PACKAGE_SCRIPTS = ['ai-service.sh', 'run-llama-server.sh', 'setup.sh', 'uninstall-user.sh']


def test_the_linux_uninstaller_is_the_users_one(tmp_path: Path):
    """uninstall-user.sh is uninstall.sh as rendered for Linux: one uninstaller (Task 4)."""
    staging = PackageStaging(system='Linux', architecture='aarch64', home=tmp_path)

    uninstaller = staged_file(staging=staging, relative='bin/uninstall-user.sh')

    assert Path(uninstaller.source).name == 'uninstall.sh.j2'


def test_the_linux_settings_name_both_roots_by_their_placeholders(tmp_path: Path):
    """Every setting names the user's folder and the program folder as placeholders.

    setup.sh fills them in for each user (6.3). The llama.cpp runtime's path is a fact the
    llama_cpp role set, which a block's variables would lose to, so a package built that way
    would name the builder's stage.
    """
    staging = PackageStaging(system='Linux', architecture='aarch64', home=tmp_path)
    package = role_defaults(role='ai_package')
    user_placeholder = package['ai_package_user_root_placeholder']
    program_placeholder = package['ai_package_program_root_placeholder']
    settings = [file for file in staging.staged if '/share/agents/' in file.destination]

    assert settings
    for file in settings:
        text = staging.rendered(file=file)
        assert str(tmp_path) not in text, file.destination
        assert '/opt/glitchygames/ai' not in text, file.destination
    reasoning = staging.rendered(
        file=staged_file(
            staging=staging,
            relative='share/agents/ai.glitchygames.bonsai-2-2b.llama-cpp.env.template',
        )
    )
    assert (
        f"AI_LLAMA_SERVER='{program_placeholder}/runtime/current/bin/llama-server'"
        in reasoning.splitlines()
    )
    assert (
        f"AI_MODEL_FILE='{user_placeholder}/models/Ternary-Bonsai-2-2B-Q2_0.gguf'"
        in reasoning.splitlines()
    )
    service = json.loads(
        staging.rendered(
            file=staged_file(staging=staging, relative='share/agents/service.json.template')
        )
    )
    assert service['control_script'] == f'{program_placeholder}/bin/ai-service.sh'
    assert service['worker_key_file'] == f'{user_placeholder}/config/worker-api-key'


def test_the_mac_package_settings_name_the_players_runtime(tmp_path: Path):
    """A player's Mac runs the runtime under their own home: the setting names the placeholder.

    The llama_cpp role's set_fact of the runtime's path once won over the block that set it, so
    the .pkg named the builder's runtime
    (bugs/2026-11-18-mac-package-settings-name-builders-runtime.md).
    """
    staging = PackageStaging(system='Darwin', architecture='arm64', home=tmp_path)
    placeholder = role_defaults(role='ai_package')['ai_package_home_placeholder']

    reasoning = staging.rendered(
        file=staged_file(
            staging=staging,
            relative='share/agents/ai.glitchygames.bonsai-2-2b.llama-cpp.env.template',
        )
    )

    assert str(tmp_path) not in reasoning
    assert (
        f"AI_LLAMA_SERVER='{placeholder}/{MAC_ROOT_NAME}/runtime/current/bin/llama-server'"
        in reasoning.splitlines()
    )


def players_llama_server(*, staging: PackageStaging, home: Path) -> Path:
    """Fill in a staged Mac setting's home placeholder, as setup.sh does, and read llama-server.

    Returns:
        The llama-server path the player's settings name.
    """
    placeholder = role_defaults(role='ai_package')['ai_package_home_placeholder']
    text = staging.rendered(
        file=staged_file(
            staging=staging,
            relative='share/agents/ai.glitchygames.bonsai-2-2b.llama-cpp.env.template',
        )
    ).replace(placeholder, str(home))
    (server,) = [
        shlex.split(line.split('=', 1)[1])[0]
        for line in text.splitlines()
        if line.startswith('AI_LLAMA_SERVER=')
    ]
    return Path(server)


def install_mac_runtime(*, staging: PackageStaging, home: Path, runtime_name: str) -> Path:
    """Lay a build and the package's runtime link into a player's home, as the .pkg does.

    Returns:
        The build's llama-server.
    """
    runtime = home / MAC_ROOT_NAME / 'runtime'
    server = runtime / runtime_name / 'bin' / 'llama-server'
    _write_executable(server, LLAMA_SERVER_STUB)
    (link,) = [file for file in staging.staged if file.is_link]
    target = runtime / Path(link.destination).name
    target.unlink(missing_ok=True)
    target.symlink_to(link.source)
    return server


def test_a_mac_upgrade_that_renames_the_runtime_keeps_the_settings_valid(tmp_path: Path):
    """The .pkg's settings name runtime/current, so a renamed build needs no new settings."""
    home = tmp_path / 'Users' / 'player'
    before = PackageStaging(system='Darwin', architecture='arm64', home=tmp_path / 'builder')
    old_server = install_mac_runtime(staging=before, home=home, runtime_name=RUNTIME_NAME)
    settings_before = players_llama_server(staging=before, home=home)
    assert settings_before.resolve() == old_server.resolve()

    after = PackageStaging(
        system='Darwin',
        architecture='arm64',
        home=tmp_path / 'builder',
        runtime_name='llama.cpp-upgraded',
    )
    new_server = install_mac_runtime(staging=after, home=home, runtime_name='llama.cpp-upgraded')

    assert players_llama_server(staging=after, home=home) == settings_before
    assert settings_before.resolve() == new_server.resolve()


def parse_control(*, text: str) -> dict[str, str]:
    """Read a Debian control file's fields (one paragraph; a continuation line joins its field).

    Returns:
        Each field's value.
    """
    fields: dict[str, str] = {}
    name = ''
    for line in text.splitlines():
        if line.startswith(' '):
            fields[name] += '\n' + line
        else:
            name, value = line.split(':', 1)
            fields[name] = value.strip()
    return fields


@pytest.mark.parametrize(
    ('architecture', 'debian_architecture'), [('aarch64', 'arm64'), ('x86_64', 'amd64')]
)
def test_the_deb_control_follows_the_design(
    tmp_path: Path,
    architecture: Literal['aarch64', 'x86_64'],
    debian_architecture: str,
):
    """Name, version, the host's architecture, and Depends with the build's glibc and C++ floors."""
    staging = PackageStaging(
        system='Linux',
        architecture=architecture,
        home=tmp_path,
        facts={'llama_cpp_glibc_version': '2.41', 'llama_cpp_libstdcxx_version': '13.2.0'},
    )

    control = parse_control(
        text=staging.rendered(file=staged_file(staging=staging, relative='DEBIAN/control'))
    )

    assert control['Package'] == 'glitchygames-ai'
    assert control['Version'] == role_defaults(role='ai_package')['ai_package_version']
    assert control['Architecture'] == debian_architecture
    assert control['Depends'] == (
        'libc6 (>= 2.41), libstdc++6 (>= 13.2.0), libgcc-s1, systemd, curl, openssl, '
        'ca-certificates, coreutils, iproute2'
    )
    assert control['Description']
    assert control['Maintainer'] == 'GlitchyGames <terry.simons@gmail.com>'


@pytest.mark.parametrize(
    ('architecture', 'debian_architecture'), [('aarch64', 'arm64'), ('x86_64', 'amd64')]
)
def test_the_deb_is_named_by_version_and_architecture(
    tmp_path: Path, architecture: Literal['aarch64', 'x86_64'], debian_architecture: str
):
    """glitchygames-ai_<version>_<architecture>.deb, in the package folder under the cache."""
    variables = ansible_variables(system='Linux', architecture=architecture, home=tmp_path)

    assert variables['ai_package_deb_output'] == (
        f'{tmp_path}/.cache/glitchygames/ai/package/'
        f'glitchygames-ai_{variables["ai_package_version"]}_{debian_architecture}.deb'
    )


def test_the_setup_unit_is_the_only_one_enabled(tmp_path: Path):
    """The setup job runs setup.sh at every login; no other unit has an [Install] section."""
    staging = PackageStaging(system='Linux', architecture='aarch64', home=tmp_path)
    units = {}
    for file in staging.staged:
        if '/usr/lib/systemd/user/' in file.destination:
            unit = configparser.ConfigParser(interpolation=None, strict=True)
            unit.optionxform = str  # ty: ignore[invalid-assignment] - keep systemd's key case
            unit.read_string(staging.rendered(file=file))
            units[Path(file.destination).name] = unit

    setup = units.pop('ai.glitchygames.setup.service')

    assert setup['Service']['Type'] == 'oneshot'
    assert setup['Service']['ExecStart'] == '/opt/glitchygames/ai/bin/setup.sh'
    assert setup['Install']['WantedBy'] == 'default.target'
    assert units, 'no agent unit staged'
    for name, unit in units.items():
        assert not unit.has_section('Install'), name


# Stand in for systemctl and loginctl in the maintainer scripts: each call is recorded; systemctl
# fails when its arguments contain SYSTEMCTL_FAILS_ON, and loginctl answers only list-users
# --no-legend, with LOGINCTL_USERS (a failure when it is unset, as with no logind)
MAINTAINER_SYSTEMCTL_STUB = """#!/bin/sh
printf 'systemctl %s\\n' "$*" >> "$SERVICE_TOOL_LOG"
case " $* " in
    *" ${SYSTEMCTL_FAILS_ON:-no such argument} "*) exit 1 ;;
esac
exit 0
"""
LOGINCTL_STUB = """#!/bin/sh
printf 'loginctl %s\\n' "$*" >> "$SERVICE_TOOL_LOG"
if [ "$*" != 'list-users --no-legend' ]; then
    echo "unexpected: loginctl $*" >> "$SERVICE_TOOL_LOG"
    exit 2
fi
[ -n "${LOGINCTL_USERS+set}" ] || exit 1
printf '%s' "$LOGINCTL_USERS"
"""
MAINTAINER_SCRIPTS = ['postinst', 'prerm', 'postrm']


class MaintainerScripts:
    """The .deb's maintainer scripts as rendered for Linux, with systemctl and loginctl faked."""

    def __init__(self, *, tmp_path: Path, architecture: Literal['aarch64', 'x86_64'] = 'aarch64'):
        """Render the scripts with the program folder under tmp_path, and write the fakes."""
        self.program_root = tmp_path / 'opt' / 'glitchygames' / 'ai'
        self.home = tmp_path / 'home'
        self.tools = tmp_path / 'tools'
        self.tool_log = self.tools / 'calls.log'
        self.home.mkdir(parents=True)
        _write_executable(self.tools / 'systemctl', MAINTAINER_SYSTEMCTL_STUB)
        _write_executable(self.tools / 'loginctl', LOGINCTL_STUB)
        self.tool_log.write_text('', encoding='utf-8')
        staging = PackageStaging(
            system='Linux',
            architecture=architecture,
            home=self.home,
            facts={'ai_program_root': str(self.program_root)},
        )
        self.scripts = {name: self.tools / name for name in MAINTAINER_SCRIPTS}
        for name, path in self.scripts.items():
            path.write_text(
                staging.rendered(file=staged_file(staging=staging, relative=f'DEBIAN/{name}')),
                encoding='utf-8',
            )

    def run(
        self, *, script: str, arguments: list[str], environment: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run one maintainer script as dpkg would, with the fakes first on PATH.

        Returns:
            The finished run.
        """
        return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - sh and a rendered script, as an argument list
            ['/bin/sh', str(self.scripts[script]), *arguments],
            env={
                'HOME': str(self.home),
                'PATH': os.pathsep.join([str(self.tools), '/usr/bin', '/bin']),
                'SERVICE_TOOL_LOG': str(self.tool_log),
                **(environment or {}),
            },
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

    def calls(self) -> list[str]:
        """Read every call the fakes saw.

        Returns:
            One line per call.
        """
        return self.tool_log.read_text(encoding='utf-8').splitlines()


SETUP_UNIT = 'ai.glitchygames.setup.service'


@needs_a_posix_shell
def test_postinst_enables_the_setup_job_and_starts_it_for_the_user_who_ran_sudo(tmp_path: Path):
    """Enabled for every user, and started now for the owner, so they needn't log in again (6.2).

    The start doesn't wait for the download: apt would hold dpkg's lock for gigabytes. It says
    the download goes on, and how to follow it.
    """
    scripts = MaintainerScripts(tmp_path=tmp_path)

    result = scripts.run(
        script='postinst', arguments=['configure', ''], environment={'SUDO_USER': 'alice'}
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert scripts.calls() == [
        f'systemctl --global enable {SETUP_UNIT}',
        f'systemctl --user --machine=alice@ start --no-block {SETUP_UNIT}',
    ]
    assert 'background' in result.stdout
    assert f'journalctl --user -u {SETUP_UNIT}' in result.stdout


@needs_a_posix_shell
@pytest.mark.parametrize('sudo_user', [None, '', 'root'])
def test_postinst_without_sudo_user_skips_the_start(tmp_path: Path, sudo_user: str | None):
    """A root login or an unattended install starts nothing, says so, and succeeds (6.2)."""
    scripts = MaintainerScripts(tmp_path=tmp_path)

    result = scripts.run(
        script='postinst',
        arguments=['configure', ''],
        environment={} if sudo_user is None else {'SUDO_USER': sudo_user},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert scripts.calls() == [f'systemctl --global enable {SETUP_UNIT}']
    assert 'next login' in result.stdout


@needs_a_posix_shell
def test_postinst_succeeds_when_the_owners_setup_cannot_start(tmp_path: Path):
    """A user manager that won't take the job fails nothing: it runs at the next login."""
    scripts = MaintainerScripts(tmp_path=tmp_path)

    result = scripts.run(
        script='postinst',
        arguments=['configure', ''],
        environment={'SUDO_USER': 'alice', 'SYSTEMCTL_FAILS_ON': 'start'},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert 'next login' in result.stdout + result.stderr


@needs_a_posix_shell
def test_postinst_fails_when_the_setup_job_cannot_be_enabled(tmp_path: Path):
    """Without the enable no user would ever be set up, so the install says it failed."""
    scripts = MaintainerScripts(tmp_path=tmp_path)

    result = scripts.run(
        script='postinst',
        arguments=['configure', ''],
        environment={'SUDO_USER': 'alice', 'SYSTEMCTL_FAILS_ON': 'enable'},
    )

    assert result.returncode != 0
    assert scripts.calls() == [f'systemctl --global enable {SETUP_UNIT}']


@needs_a_posix_shell
@pytest.mark.parametrize('action', ['abort-upgrade', 'abort-deconfigure'])
def test_postinst_does_nothing_when_dpkg_rolls_back(tmp_path: Path, action: str):
    """Only configure enables and starts: a rollback keeps what the old package set up."""
    scripts = MaintainerScripts(tmp_path=tmp_path)

    result = scripts.run(script='postinst', arguments=[action], environment={'SUDO_USER': 'a'})

    assert result.returncode == 0, result.stdout + result.stderr
    assert scripts.calls() == []


@needs_a_posix_shell
def test_a_failed_removal_leaves_the_setup_job_enabled(tmp_path: Path):
    """A removal's prerm disables the job; if the removal fails, postinst abort-remove enables it.

    The package stays installed, so its setup job must still run at each login.
    """
    scripts = MaintainerScripts(tmp_path=tmp_path)

    removal = scripts.run(script='prerm', arguments=['remove'])
    rollback = scripts.run(script='postinst', arguments=['abort-remove'])

    assert removal.returncode == 0, removal.stderr
    assert rollback.returncode == 0, rollback.stderr
    calls = scripts.calls()
    disabled = calls.index(f'systemctl --global disable {SETUP_UNIT}')
    assert calls[disabled + 1 :] == [f'systemctl --global enable {SETUP_UNIT}']


LOGGED_IN_USERS = '1000 alice no active\n1001 bob yes lingering\n'


@needs_a_posix_shell
@pytest.mark.parametrize('action', ['upgrade', 'remove', 'failed-upgrade', 'deconfigure'])
def test_prerm_stops_every_logged_in_users_units(tmp_path: Path, action: str):
    """Every running ai.glitchygames.* unit of every user stops before the programs change.

    Review focus 4: an upgrade replaces the binaries under running models. Only a removal
    disables the setup job; an upgrade keeps it for the new version.
    """
    scripts = MaintainerScripts(tmp_path=tmp_path)

    result = scripts.run(
        script='prerm', arguments=[action, '0.2.0'], environment={'LOGINCTL_USERS': LOGGED_IN_USERS}
    )

    assert result.returncode == 0, result.stdout + result.stderr
    expected = [
        'loginctl list-users --no-legend',
        'systemctl --user --machine=alice@ stop ai.glitchygames.*',
        'systemctl --user --machine=bob@ stop ai.glitchygames.*',
    ]
    if action == 'remove':
        expected.append(f'systemctl --global disable {SETUP_UNIT}')
    assert scripts.calls() == expected


@needs_a_posix_shell
def test_prerm_succeeds_without_logind_and_when_a_stop_fails(tmp_path: Path):
    """A container with no logind, or a user's manager that won't answer, never blocks dpkg."""
    scripts = MaintainerScripts(tmp_path=tmp_path)

    without_logind = scripts.run(script='prerm', arguments=['upgrade', '0.2.0'])
    failed_stop = scripts.run(
        script='prerm',
        arguments=['remove'],
        environment={'LOGINCTL_USERS': LOGGED_IN_USERS, 'SYSTEMCTL_FAILS_ON': 'stop'},
    )

    assert without_logind.returncode == 0, without_logind.stderr
    assert 'no unit was stopped' in without_logind.stderr
    assert failed_stop.returncode == 0, failed_stop.stderr
    assert "could not stop alice's" in failed_stop.stderr
    assert f'systemctl --global disable {SETUP_UNIT}' in scripts.calls()


@needs_a_posix_shell
def test_prerm_removes_the_bytecode_python_wrote_in_the_program_folder(tmp_path: Path):
    """Python run as root writes __pycache__ beside the sidecar, which dpkg doesn't know of.

    Left there, dpkg -r would leave /opt/glitchygames/ai behind. Nothing else is touched.
    """
    scripts = MaintainerScripts(tmp_path=tmp_path)
    package = scripts.program_root / 'sidecar' / 'site' / 'glitchygames_ai_service'
    package.mkdir(parents=True)
    (package / 'app.py').write_text('', encoding='utf-8')
    (package / '__pycache__').mkdir()
    (package / '__pycache__' / 'app.cpython-314.pyc').write_bytes(b'')
    (scripts.program_root / 'sidecar' / '__pycache__').mkdir()

    result = scripts.run(script='prerm', arguments=['remove'])

    assert result.returncode == 0, result.stderr
    assert not list(scripts.program_root.rglob('__pycache__'))
    assert (package / 'app.py').is_file()


@needs_a_posix_shell
@pytest.mark.parametrize('action', ['remove', 'purge', 'upgrade', 'abort-install'])
def test_postrm_touches_no_home(tmp_path: Path, action: str):
    """Each user's models, keys and settings stay until they run uninstall-user.sh (6.7)."""
    scripts = MaintainerScripts(tmp_path=tmp_path)
    user_root = scripts.home / '.local' / 'share' / 'glitchygames' / 'ai'
    for relative in ('models/model.gguf', 'config/worker-api-key', 'history/console.jsonl'):
        (user_root / relative).parent.mkdir(parents=True, exist_ok=True)
        (user_root / relative).write_text(relative, encoding='utf-8')
    before = {path: path.read_bytes() for path in scripts.home.rglob('*') if path.is_file()}

    result = scripts.run(script='postrm', arguments=[action])

    assert result.returncode == 0, result.stderr
    assert {path: path.read_bytes() for path in scripts.home.rglob('*') if path.is_file()} == before
    assert scripts.calls() == []


@needs_a_posix_shell
@pytest.mark.parametrize('architecture', ARCHITECTURES)
def test_every_maintainer_script_passes_sh_n(
    tmp_path: Path, architecture: Literal['aarch64', 'x86_64']
):
    """postinst, prerm and postrm parse as sh, as the service's scripts do."""
    scripts = MaintainerScripts(tmp_path=tmp_path, architecture=architecture)

    for name, script in scripts.scripts.items():
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - sh -n on a rendered file, as an argument list
            ['/bin/sh', '-n', str(script)], capture_output=True, text=True, check=False, timeout=60
        )
        assert (result.returncode, result.stderr) == (0, ''), name
        assert script.read_text(encoding='utf-8').startswith('#!/bin/sh\n'), name


def deb_contents_line(*, path: str) -> str:
    """Write one line as `dpkg-deb --contents` prints a file.

    Returns:
        The line.
    """
    return f'-rwxr-xr-x root/root     12345 2026-11-18 10:00 .{path}'


def linux_contents_checks() -> list[dict[str, Any]]:
    """Find linux.yml's checks of the built .deb's contents.

    Returns:
        The assert tasks that read the registered listing.
    """
    return [
        task
        for task in walk_tasks(tasks=role_tasks(role='ai_package', file_name='linux.yml'))
        if 'ansible.builtin.assert' in task
        and 'ai_package_deb_contents' in json.dumps(task['ansible.builtin.assert'])
    ]


def deb_contents_pass(*, lines: list[str], staging: PackageStaging) -> bool:
    """Run linux.yml's contents checks on a `dpkg-deb --contents` listing, as Ansible would.

    Each check sees what Ansible gives it: the registered listing, the facts the role set and,
    in a loop, the loop's item.

    Returns:
        Whether every check passes.
    """
    variables = staging.scope(
        block_variables={},
        include_variables={},
        extra={
            'ai_package_deb_contents': {
                'stdout': '\n'.join(lines),
                'stdout_lines': lines,
                'rc': 0,
            }
        },
    )
    checks = linux_contents_checks()
    assert checks, 'linux.yml checks nothing of the .deb'
    for task in checks:
        conditions = task['ansible.builtin.assert']['that']
        items = render_value(value=task['loop'], variables=variables) if 'loop' in task else [None]
        for item in items:
            scope = variables if item is None else variables | {'item': item}
            for condition in [conditions] if isinstance(conditions, str) else conditions:
                if not render_expression(expression='{{ ' + condition + ' }}', variables=scope):
                    return False
    return True


def complete_deb_listing(*, staging: PackageStaging) -> list[str]:
    """List what a complete .deb holds, as the role would build it on that host.

    Returns:
        One `dpkg-deb --contents` line per file.
    """
    program = '/opt/glitchygames/ai'
    runtime = f'{program}/runtime/{RUNTIME_NAME}'
    paths = [
        f'{runtime}/bin/llama-server',
        *[
            f'{runtime}/bin/libggml-cpu-{variant}.so'
            for variant in staging.scope(block_variables={}, include_variables={})[
                'llama_cpp_cpu_variants'
            ][staging.architecture]
        ],
        f'{runtime}/lib/libllama.so',
        f'{runtime}/lib/libggml-base.so',
        f'{runtime}/notices/llama.cpp-LICENSE',
        f'{program}/sidecar/python/bin/python3.14',
        f'{program}/sidecar/site/glitchygames_ai_service/app.py',
        f'{program}/sidecar/scalar.js',
        f'{program}/share/notices/2b/LICENSE',
        f'{program}/share/notices/2b/NOTICE.txt',
    ]
    stage = ansible_variables(system='Linux', architecture=staging.architecture, home=staging.home)[
        'ai_package_stage'
    ]
    for file in staging.staged:
        relative = str(Path(file.destination).relative_to(stage))
        if file.is_link:
            # As dpkg-deb lists a link
            paths.append(f'/{relative} -> {file.source}')
        elif not relative.startswith('DEBIAN/') and not relative.endswith('notices'):
            paths.append(f'/{relative}')
    return [deb_contents_line(path=path) for path in paths]


def test_the_package_never_takes_the_models(tmp_path: Path):
    """Both packages stay small, and the .deb's check of its contents passes only a whole one.

    The .deb holds llama-server, every CPU variant for the architecture, its libraries, the
    sidecar, the licenses and every unit and script, and no model (6.7).
    """
    mac_tasks = (ROLES / 'ai_package' / 'tasks' / 'macos.yml').read_text(encoding='utf-8')
    staging = PackageStaging(system='Linux', architecture='aarch64', home=tmp_path)
    complete = complete_deb_listing(staging=staging)

    assert r"is not search('\.gguf')" in mac_tasks
    assert deb_contents_pass(lines=complete, staging=staging)
    assert not deb_contents_pass(
        lines=[*complete, deb_contents_line(path='/opt/glitchygames/ai/models/x.gguf')],
        staging=staging,
    )
    for index, line in enumerate(complete):
        missing = complete[:index] + complete[index + 1 :]
        assert not deb_contents_pass(lines=missing, staging=staging), f'passes without {line}'


@needs_a_posix_shell
def test_an_upgrade_that_renames_the_runtime_keeps_every_users_settings_valid(tmp_path: Path):
    """Settings name the runtime through runtime/current, which each package points at its build.

    An upgrade to a build of another name (a new llama.cpp tag or options) changes no user's
    settings, and the path they name then reaches the new llama-server: a user who never logs in
    again still runs it (Review focus 4).
    """
    setup = LinuxSetup(tmp_path=tmp_path)
    setup.set_cores(count=4, capacities={})
    assert setup.run().returncode == 0
    reasoning = setup.service.agent(role='reasoning')
    settings_file = setup.user_root / 'config' / f'{reasoning["label"]}.env'
    settings_before = settings_file.read_bytes()
    server = Path(setup.model_settings()[reasoning['label']]['AI_LLAMA_SERVER'])
    old_runtime = setup.program_root / 'runtime' / RUNTIME_NAME
    assert server.resolve() == (old_runtime / 'bin' / 'llama-server').resolve()
    share = setup.program_root / 'share' / 'agents'
    share_before = {path.name: path.read_text(encoding='utf-8') for path in share.iterdir()}

    # The upgrade, as dpkg leaves it: the new package's build and link, the old build gone
    upgraded = PackageStaging(
        system='Linux',
        architecture='aarch64',
        home=setup.service.home,
        runtime_name='llama.cpp-upgraded',
    )
    shutil.rmtree(old_runtime)
    new_runtime = setup.program_root / 'runtime' / 'llama.cpp-upgraded'
    _write_executable(new_runtime / 'bin' / 'llama-server', LLAMA_SERVER_STUB)
    (link,) = [file for file in upgraded.staged if file.is_link]
    assert Path(link.destination).name == 'current'
    (setup.program_root / 'runtime' / 'current').unlink()
    (setup.program_root / 'runtime' / 'current').symlink_to(link.source)
    runner = setup.run(template='run-llama-server.sh.j2', arguments=[reasoning['label']])

    for file in upgraded.staged:
        if '/share/agents/' in file.destination:
            assert upgraded.rendered(file=file) == share_before[Path(file.destination).name]
    assert settings_file.read_bytes() == settings_before
    assert server.resolve() == (new_runtime / 'bin' / 'llama-server').resolve()
    assert runner.returncode == 0, runner.stderr
    assert '--model' in runner.stdout.splitlines(), runner.stdout


def start_setup(*, setup: LinuxSetup, extra: dict[str, str]) -> subprocess.Popen[str]:
    """Start setup.sh as rendered for Linux, in a process group of its own.

    Returns:
        The running setup.
    """
    return subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] - sh and a rendered script, as an argument list
        ['/bin/sh', str(setup.service.script(template='setup.sh.j2'))],
        env=setup.service.environment(extra=setup.environment(extra=extra)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )


def wait_until_downloading(*, setup: LinuxSetup) -> None:
    """Wait until a running setup has called curl, so it holds the lock.

    Raises:
        TimeoutError: It never called curl.
    """
    for _ in range(600):
        if any(call.startswith('curl') for call in setup.service.tool_calls()):
            return
        clock.raw_sleep(0.05)
    message = 'setup never started downloading'
    raise TimeoutError(message)


def assert_no_lock_outside_the_user_root(*, setup: LinuxSetup) -> None:
    """The lock is the user root's file alone: nothing in the runtime or temporary folders."""
    assert setup.lock.is_file()
    assert not list(setup.runtime_directory.iterdir())
    assert not list(setup.temporary_directory.iterdir())


@needs_a_posix_shell
def test_two_setup_runs_at_once_never_both_download(tmp_path: Path):
    """A login's setup job, postinst's and Ansible's may run together: the second leaves at once.

    It says another run is setting up and exits 0, and the first finishes the job: every model
    file is fetched once and no two runs write the same .part file.
    """
    setup = LinuxSetup(tmp_path=tmp_path)
    setup.set_cores(count=4, capacities={})
    first = start_setup(setup=setup, extra={'CURL_DELAY_SECONDS': '1'})
    try:
        wait_until_downloading(setup=setup)
        second = start_setup(setup=setup, extra={})
        second_output, second_errors = second.communicate(timeout=120)
        second_finished_first = first.poll() is None
        first_output, first_errors = first.communicate(timeout=120)
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(first.pid, signal.SIGKILL)
        first.wait(timeout=10)

    assert second.returncode == 0, second_output + second_errors
    assert 'is already running; it finishes the job' in second_output
    assert second_finished_first, 'the second run waited for the first'
    assert first.returncode == 0, first_output + first_errors
    downloads = [call for call in setup.service.tool_calls() if call.startswith('curl')]
    assert len(downloads) == len(setup.selected_model_files()), downloads
    assert not [call for call in setup.service.tool_calls() if call.startswith('unexpected')]
    for model_file in setup.selected_model_files():
        served = setup.download_path(model_file=model_file).read_bytes()
        assert (setup.user_root / 'models' / model_file['file']).read_bytes() == served
    assert_no_lock_outside_the_user_root(setup=setup)


@needs_a_posix_shell
def test_a_run_after_one_that_was_killed_proceeds_at_once(tmp_path: Path):
    """The kernel frees the lock when its holder dies: no lock outlives a crash or a power cut.

    The killed run's whole process group goes, as a power cut takes it; the next run takes the
    lock, resumes the download and finishes.
    """
    setup = LinuxSetup(tmp_path=tmp_path)
    setup.set_cores(count=4, capacities={})
    killed = start_setup(setup=setup, extra={'CURL_DELAY_SECONDS': '30'})
    try:
        wait_until_downloading(setup=setup)
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(killed.pid, signal.SIGKILL)
        killed.communicate(timeout=10)

    result = setup.run()

    assert killed.returncode == -signal.SIGKILL
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'already running' not in result.stdout
    for model_file in setup.selected_model_files():
        served = setup.download_path(model_file=model_file).read_bytes()
        assert (setup.user_root / 'models' / model_file['file']).read_bytes() == served
    assert_no_lock_outside_the_user_root(setup=setup)


def libstdcxx_floor(*, search_output: str, tmp_path: Path) -> str | None:
    """Run llama_cpp's Linux check and record of the libstdc++ floor on objdump's newest versions.

    Each task sees what Ansible gives it: the registered search result and the role's defaults.

    Returns:
        The recorded version, or None when the check refuses the build.
    """
    variables = ansible_variables(system='Linux', architecture='aarch64', home=tmp_path)
    variables['llama_cpp_libstdcxx_search'] = {'stdout': search_output, 'rc': 0}
    check = linux_task(name="Check each is one GCC's ABI list names")['ansible.builtin.assert']
    for condition in check['that']:
        if not render_expression(expression='{{ ' + condition + ' }}', variables=variables):
            return None
    record = linux_task(name='Record the libstdc++ version')
    scope = dict(variables)
    for name, value in record['vars'].items():
        scope[name] = render_value(value=value, variables=scope)
    return render_value(
        value=record['ansible.builtin.set_fact']['llama_cpp_libstdcxx_version'].strip(),
        variables=scope,
    )


@pytest.mark.parametrize(
    ('search_output', 'floor'),
    [
        ('3.4.33 1.3.15', '14.1.0'),
        ('3.4.32 1.3.14', '13.2.0'),
        # GCC 16.1.0 added a CXXABI version and no GLIBCXX one
        ('3.4.34 1.3.17', '16.1.0'),
        ('3.4.28 1.3.12', '9.3.0'),
        ('3.4.30 1.3.9', '12.1.0'),
    ],
)
def test_the_libstdcxx_floor_is_the_newest_gcc_either_version_needs(
    tmp_path: Path, search_output: str, floor: str
):
    """The .deb's libstdc++6 floor is the first GCC whose libstdc++ has both versions."""
    assert libstdcxx_floor(search_output=search_output, tmp_path=tmp_path) == floor


@pytest.mark.parametrize('search_output', ['3.4.35 1.3.15', '3.4.33 1.3.18', '', '3.4.33'])
def test_a_libstdcxx_version_the_table_lacks_is_refused(tmp_path: Path, search_output: str):
    """A build newer than the table, or a search that found nothing, never gets a floor."""
    assert libstdcxx_floor(search_output=search_output, tmp_path=tmp_path) is None


def test_the_libstdcxx_tables_follow_gccs_abi_list():
    """Every symbol version in order, each to a release no older than the one before it."""
    defaults = role_defaults(role='llama_cpp')

    for table, prefix, last in (
        (defaults['llama_cpp_glibcxx_releases'], '3.4', 34),
        (defaults['llama_cpp_cxxabi_releases'], '1.3', 17),
    ):
        assert list(table) == [prefix] + [f'{prefix}.{minor}' for minor in range(1, last + 1)]
        releases = [tuple(int(part) for part in release.split('.')) for release in table.values()]
        assert all(len(release) == 3 for release in releases)
        assert releases == sorted(releases)


# The Linux install (plans/lucid-circuit-linux.md, 5.1, 6.3 and 6.9): Ansible installs the .deb it
# built, runs the installed setup.sh for the owner, waits for setup to finish, then smoke-tests
INSTALL_PACKAGE_TASK = 'Install the package'
REMOVE_PACKAGE_TASK = 'Remove the package'
RUN_SETUP_TASK = 'Run setup for the owner, waiting out a run already going'
SETUP_FINISHED_TASK = 'Check that setup finished, with the models in place'
SMOKE_TEST_TASK = 'Check that the models answer correctly'
RUN_USER_UNINSTALLER_TASK = "Run the owner's uninstaller while the package still holds it"


def named_task(*, role: str, file_name: str, name: str) -> dict[str, Any]:
    """Find one task of a role's task file by name, inside blocks too.

    Returns:
        The task.
    """
    (task,) = [
        task
        for task in walk_tasks(tasks=role_tasks(role=role, file_name=file_name))
        if task.get('name') == name
    ]
    return task


def registered_command(*, rc: int, stdout: str, stderr: str = '') -> dict[str, Any]:
    """A command task's registered result, in the shape ansible.builtin.command gives it.

    Returns:
        The result.
    """
    return {
        'rc': rc,
        'stdout': stdout.rstrip('\n'),
        'stdout_lines': stdout.splitlines(),
        'stderr': stderr.rstrip('\n'),
        'stderr_lines': stderr.splitlines(),
        'changed': False,
        'failed': rc != 0,
    }


def test_on_linux_only_the_package_steps_take_root():
    """The plays run as the user; root is raised for apt alone: build tools and the .deb."""
    raised = sorted(
        (str(path.relative_to(ROLES)), task['name'])
        for path in ROLES.glob('*/tasks/*.yml')
        for task in walk_tasks(tasks=yaml.safe_load(path.read_text(encoding='utf-8')) or [])
        if task.get('become')
    )

    assert raised == [
        ('ai_service/tasks/linux.yml', INSTALL_PACKAGE_TASK),
        ('ai_uninstall/tasks/linux.yml', REMOVE_PACKAGE_TASK),
        ('llama_cpp/tasks/linux.yml', 'Install the build tools'),
    ]


def test_linux_installs_the_package_then_waits_for_setup_then_smoke_tests():
    """The smoke test needs the models, which only a finished setup has.

    The .deb's postinst starts the owner's setup in the background, so Ansible's own run usually
    finds that run holding the lock and leaves at once: the wait sits between the install and the
    smoke test.
    """
    names = [task['name'] for task in role_tasks(role='ai_service', file_name='linux.yml')]

    assert (
        names.index(INSTALL_PACKAGE_TASK)
        < names.index(RUN_SETUP_TASK)
        < names.index(SETUP_FINISHED_TASK)
        < names.index(SMOKE_TEST_TASK)
    )
    setup = named_task(role='ai_service', file_name='linux.yml', name=RUN_SETUP_TASK)
    assert setup['ansible.builtin.command']['argv'] == ['{{ ai_service_bin_directory }}/setup.sh']
    assert setup['register'] == 'ai_service_setup'
    assert 'become' not in setup


def test_both_platforms_list_the_agents_and_run_the_same_smoke_test():
    """One list of agents and one smoke test: only the install between them is the platform's."""
    tasks = role_tasks(role='ai_service')
    platform_include = tasks[-1]['ansible.builtin.include_tasks']
    mac_tasks = role_tasks(role='ai_service', file_name='macos.yml')
    linux_tasks = role_tasks(role='ai_service', file_name='linux.yml')

    assert any(task.get('ansible.builtin.import_tasks') == 'list_agents.yml' for task in tasks)
    assert platform_include == {
        'file': "{{ 'macos' if ansible_facts['system'] == 'Darwin' else 'linux' }}.yml"
    }
    for platform_tasks in (mac_tasks, linux_tasks):
        assert platform_tasks[-1] == {
            'name': SMOKE_TEST_TASK,
            'ansible.builtin.include_tasks': 'smoke_test.yml',
        }


def install_needed(*, status: str, recorded: str, built: str) -> bool:
    """Evaluate the install task's condition with what its registered tasks would hold.

    Returns:
        Whether Ansible installs the package.
    """
    task = named_task(role='ai_service', file_name='linux.yml', name=INSTALL_PACKAGE_TASK)
    return render_expression(
        expression=task['when'],
        variables={
            'ai_service_package_status': registered_command(rc=0 if status else 1, stdout=status),
            'ai_service_installed_package': registered_command(
                rc=0 if recorded else 1, stdout=recorded
            ),
            'ai_service_package': {'stat': {'exists': True, 'checksum': built}},
        },
    )


@pytest.mark.parametrize(
    ('status', 'recorded', 'built', 'installs'),
    [
        # Never installed: dpkg-query knows no such package and nothing was recorded
        ('', '', 'abc', True),
        # Installed from this very .deb
        ('install ok installed', 'abc', 'abc', False),
        # Rebuilt since, at the same version, which apt alone would skip
        ('install ok installed', 'abc', 'def', True),
        # Removed by hand since: only its configuration is left
        ('deinstall ok config-files', 'abc', 'abc', True),
        # Installed, but by something other than this Ansible
        ('install ok installed', '', 'abc', True),
    ],
)
def test_a_rebuilt_package_of_the_same_version_is_installed_again(
    status: str, recorded: str, built: str, *, installs: bool
):
    """A rebuilt .deb keeps its version, so Ansible compares checksums, not versions."""
    assert install_needed(status=status, recorded=recorded, built=built) is installs
    task = named_task(role='ai_service', file_name='linux.yml', name=INSTALL_PACKAGE_TASK)
    assert task['become'] is True
    argv = task['ansible.builtin.command']['argv']
    assert argv[:4] == ['apt-get', 'install', '--yes', '--reinstall']


def setup_retries(*, result: subprocess.CompletedProcess[str]) -> bool:
    """Evaluate the setup task's until condition on a real setup.sh run.

    Returns:
        Whether Ansible runs setup.sh again.
    """
    task = named_task(role='ai_service', file_name='linux.yml', name=RUN_SETUP_TASK)
    registered = registered_command(
        rc=result.returncode, stdout=result.stdout, stderr=result.stderr
    )
    return not render_expression(
        expression=task['until'], variables={'ai_service_setup': registered}
    )


def setup_finished(*, result: subprocess.CompletedProcess[str]) -> tuple[bool, str]:
    """Evaluate the check after setup on a real setup.sh run, with its message.

    Returns:
        Whether the check passes, and what it would say if not.
    """
    task = named_task(role='ai_service', file_name='linux.yml', name=SETUP_FINISHED_TASK)
    variables = ansible_variables(system='Linux', architecture='aarch64', home=Path('/home/pi'))
    variables['ai_service_setup'] = registered_command(
        rc=result.returncode, stdout=result.stdout, stderr=result.stderr
    )
    passes = all(
        render_expression(expression=condition, variables=variables)
        for condition in task['ansible.builtin.assert']['that']
    )
    message = render_value(value=task['ansible.builtin.assert']['fail_msg'], variables=variables)
    return passes, message


@needs_a_posix_shell
def test_ansible_waits_out_a_setup_run_already_going_and_needs_its_own_to_finish(
    tmp_path: Path,
):
    """Exit 0 from a run that found the lock taken means nothing is ready yet.

    The real setup.sh, as Ansible meets it after the postinst started one: the second run's
    output makes Ansible run setup again, and only a run that did the job itself passes the
    check, so the smoke test never starts before the models are here.
    """
    setup = LinuxSetup(tmp_path=tmp_path)
    setup.set_cores(count=4, capacities={})
    first = start_setup(setup=setup, extra={'CURL_DELAY_SECONDS': '1'})
    try:
        wait_until_downloading(setup=setup)
        second = start_setup(setup=setup, extra={})
        second_output, second_errors = second.communicate(timeout=120)
        first_output, first_errors = first.communicate(timeout=120)
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(first.pid, signal.SIGKILL)
        first.wait(timeout=10)
    found_the_lock_taken = subprocess.CompletedProcess(
        args=[], returncode=second.returncode, stdout=second_output, stderr=second_errors
    )
    own_run = setup.run()

    assert found_the_lock_taken.returncode == 0
    assert setup_retries(result=found_the_lock_taken) is True
    assert setup_finished(result=found_the_lock_taken)[0] is False
    assert first.returncode == 0, first_output + first_errors
    assert own_run.returncode == 0, own_run.stdout + own_run.stderr
    assert setup_retries(result=own_run) is False
    assert setup_finished(result=own_run)[0] is True


@needs_a_posix_shell
def test_a_failed_setup_stops_the_install_and_says_why(tmp_path: Path):
    """A download that fails ends the wait at once, and the check names setup's own words."""
    setup = LinuxSetup(tmp_path=tmp_path)
    setup.set_cores(count=4, capacities={})

    failed = setup.run(extra={'CURL_FAILS_AFTER_BYTES': '5'})
    passes, message = setup_finished(result=failed)

    assert failed.returncode == 1
    assert setup_retries(result=failed) is False
    assert passes is False
    assert 'setup.sh failed (exit 1)' in message
    assert 'it resumes on the next run' in message


def test_a_setup_still_running_at_the_timeout_says_so():
    """When another run holds the lock to the end, the message says it was still going."""
    lock_taken = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='setup: another setup run for /home/pi/.local/share/glitchygames/ai is already'
        ' running; it finishes the job\n',
        stderr='',
    )
    defaults = role_defaults(role='ai_service')
    waited = defaults['ai_service_setup_retries'] * defaults['ai_service_setup_delay_seconds']

    passes, message = setup_finished(result=lock_taken)

    assert passes is False
    assert f'still running after {waited} seconds' in message
    assert 'journalctl --user -u ai.glitchygames.setup.service' in message


def test_on_linux_ansible_downloads_no_model_but_fetches_the_notices():
    """setup.sh downloads each user's models; the package still carries the licenses."""
    tasks = role_tasks(role='ai_models')
    (downloads,) = [task for task in tasks if 'block' in task]
    block_names = [task['name'] for task in downloads['block']]
    outside = [task['name'] for task in tasks if 'block' not in task]

    assert downloads['when'] == "ansible_facts['system'] == 'Darwin'"
    assert 'Download and verify the models' in block_names
    assert "Refuse to start a download that won't fit" in block_names
    assert outside == [
        'Make the notices directory',
        "Fetch each Bonsai size's license and notice at its pinned revision",
    ]


def test_linux_validation_checks_the_installed_runtime_and_only_the_downloaded_models(
    tmp_path: Path,
):
    """setup.sh downloads only the selected sizes, so validation checks what is there.

    It runs the server the .deb installed, through the runtime link, at the verbosity that logs
    which CPU variant loaded.
    """
    service = ServiceHome(system='Linux', home=tmp_path / 'home', tools=tmp_path / 'tools')
    facts = run_set_fact_tasks(tasks=role_tasks(role='ai_validate'), variables=service.variables)
    present = {'bonsai-2-2b', 'qwen3-embedding-0.6b'}
    registered = {
        'results': [
            {'item': model, 'stat': {'exists': model['alias'] in present}}
            for model in facts['ai_validate_models']
        ]
    }
    chosen = run_set_fact_tasks(
        tasks=role_tasks(role='ai_validate', file_name='linux.yml'),
        variables=facts | {'ai_validate_present': registered},
    )

    assert [model['alias'] for model in chosen['ai_validate_checked_models']] == [
        'bonsai-2-2b',
        'qwen3-embedding-0.6b',
    ]
    assert chosen['ai_validate_server'] == '/opt/glitchygames/ai/runtime/current/bin/llama-server'
    assert all('--verbose' in model['arguments'] for model in chosen['ai_validate_checked_models'])
    stat_task = named_task(
        role='ai_validate', file_name='linux.yml', name='Find which models setup downloaded'
    )
    model = facts['ai_validate_models'][0]
    path = render_value(value=stat_task['ansible.builtin.stat']['path'], variables={'item': model})
    assert path == model['arguments'][model['arguments'].index('--model') + 1]


def test_the_mac_validation_still_checks_every_model_with_the_build_ansible_installed(
    tmp_path: Path,
):
    """A Mac downloads every size, so every one is checked, with llama_cpp's own build."""
    service = ServiceHome(system='Darwin', home=tmp_path / 'home', tools=tmp_path / 'tools')
    variables = service.variables | {'llama_cpp_install_directory': '/runtime/llama.cpp-b1'}
    facts = run_set_fact_tasks(tasks=role_tasks(role='ai_validate'), variables=variables)
    chosen = run_set_fact_tasks(
        tasks=role_tasks(role='ai_validate', file_name='macos.yml'), variables=facts
    )

    assert chosen['ai_validate_checked_models'] == facts['ai_validate_models']
    assert chosen['ai_validate_server'] == '/runtime/llama.cpp-b1/bin/llama-server'


def test_the_checks_run_on_the_host_not_the_controller():
    """Over SSH the controller's Python and the playbook's folder aren't on the host.

    The checks are copied to the host and run by its own Python, on both platforms.
    """
    runners: list[str] = []
    for role in ('ai_service', 'ai_validate'):
        for path in sorted((ROLES / role / 'tasks').glob('*.yml')):
            for task in walk_tasks(tasks=yaml.safe_load(path.read_text(encoding='utf-8'))):
                argv = task.get('ansible.builtin.command', {}).get('argv', [])
                text = json.dumps(argv)
                if (
                    'ansible_playbook_python' in text
                    or 'role_path' in text
                    or ('playbook_dir' in text)
                ):
                    runners.append(f'{path.name}: {task["name"]}')
    copy = named_task(role='ai_service', file_name='checks.yml', name='Put the checks on the host')

    assert runners == []
    assert copy['ansible.builtin.copy']['src'] == (
        '{{ playbook_dir }}/roles/ai_service/files/{{ item }}'
    )
    assert copy['loop'] == ['smoke_test.py', 'api_smoke_test.py']


def smoke_test_module(*, mocker: MockerFixture) -> Any:
    """Load the smoke test as a module: it is a script beside the role, not a package.

    No bytecode is written beside it, where the role's folder would carry it.

    Returns:
        The module.

    Raises:
        ImportError: Python can't make a module of the file.
    """
    mocker.patch.object(sys, 'dont_write_bytecode', new=True)
    path = ROLES / 'ai_service' / 'files' / 'smoke_test.py'
    specification = importlib.util.spec_from_file_location('smoke_test', path)
    if specification is None or specification.loader is None:
        message = f'cannot load {path}'
        raise ImportError(message)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


# /proc/PID/status as Linux writes it (proc_pid_status(5)): one "Name:<tab>value" per line, memory
# in kB
PROC_STATUS = """Name:\tllama-server
Umask:\t0022
State:\tS (sleeping)
Tgid:\t4242
Pid:\t4242
VmPeak:\t 7654321 kB
VmSize:\t 7600000 kB
VmHWM:\t 3500000 kB
VmRSS:\t 3456789 kB
RssAnon:\t  123456 kB
RssFile:\t 3333333 kB
Threads:\t7
voluntary_ctxt_switches:\t150
"""
# llama.cpp b12167's own words: ggml/src/ggml-backend-reg.cpp:259 and common/common.cpp:445, at
# --log-verbosity 4 or --verbose
SYSTEM_INFO_LINE = (
    'system_info: n_threads = 2 (n_threads_batch = 2) / 4 | CPU : NEON = 1 | ARM_FMA = 1 |'
)


def test_the_check_reports_linux_resident_memory_and_threads(mocker: MockerFixture):
    """Linux has no footprint tool, as a Mac has: /proc gives the resident memory and threads."""
    smoke_test = smoke_test_module(mocker=mocker)

    report = smoke_test.linux_process_report(status_text=PROC_STATUS)

    assert report == {'resident_mib': round(3456789 / 1024, 1), 'process_threads': 7}
    assert smoke_test.linux_process_report(status_text='Name:\tgone\n') == {
        'resident_mib': None,
        'process_threads': None,
    }


def test_the_check_keeps_the_cpu_variant_and_thread_lines_of_the_log(mocker: MockerFixture):
    """The validation's evidence on Linux: which variant loaded, and the threads used."""
    pattern = smoke_test_module(mocker=mocker).LOG_LINES_OF_INTEREST

    assert pattern.search(GOOD_LOAD_LINE)
    assert pattern.search(SYSTEM_INFO_LINE)
    assert not pattern.search('srv  log_server_r: request: GET /health 127.0.0.1 200')


def test_linux_uninstall_runs_the_users_uninstaller_before_removing_the_package():
    """The package holds uninstall-user.sh, so the owner's part goes first, then the package."""
    tasks = role_tasks(role='ai_uninstall', file_name='linux.yml')
    names = [task['name'] for task in tasks]
    uninstaller = named_task(
        role='ai_uninstall', file_name='linux.yml', name=RUN_USER_UNINSTALLER_TASK
    )
    removal = named_task(role='ai_uninstall', file_name='linux.yml', name=REMOVE_PACKAGE_TASK)

    assert names.index(RUN_USER_UNINSTALLER_TASK) < names.index(REMOVE_PACKAGE_TASK)
    assert uninstaller['ansible.builtin.command']['argv'] == (
        "{{ [ai_service_bin_directory ~ '/' ~ ai_package_uninstaller_name]\n"
        "   + (['--remove-models'] if ai_uninstall_models | bool else []) }}"
    )
    assert 'become' not in uninstaller
    assert removal['become'] is True
    assert removal['ansible.builtin.apt'] == {
        'name': '{{ ai_package_deb_name }}',
        'state': 'absent',
    }


def test_no_include_names_its_file_in_a_free_form_argument_with_an_equals_sign():
    """Ansible reads `name=value` in a free-form include as options and refuses the task.

    A platform include written as one string, with `==` in its expression, passed every rendering
    test here and failed only in ansible-playbook --syntax-check; the file: form avoids it.
    """
    free_form = [
        f'{path.relative_to(ROLES)}: {task["name"]}'
        for path in sorted(ROLES.glob('*/tasks/*.yml'))
        for task in walk_tasks(tasks=yaml.safe_load(path.read_text(encoding='utf-8')) or [])
        for key in ('ansible.builtin.include_tasks', 'ansible.builtin.import_tasks')
        if isinstance(task.get(key), str) and '=' in task[key]
    ]

    assert free_form == []


# Ansible's own parser, for what the rendering tests above can't see (a task Ansible refuses at
# parse time, a YAML error). ansible-core isn't one of this project's dependencies: the playbooks
# run through `uvx --from ansible-core` (their headers), so the test takes an installed
# ansible-playbook, else uvx's cached copy with no network, and skips only when neither runs
ANSIBLE_TIMEOUT_SECONDS = 120.0
PLAYBOOKS = sorted(
    path
    for path in ANSIBLE.glob('*.yml')
    # The inventory is the one top-level YAML file that isn't a playbook
    if path.name != 'inventory.yml'
)


def ansible_playbook_command() -> list[str] | None:
    """Find an ansible-playbook that runs, preferring one installed beside this Python.

    Returns:
        The command's first words, or None if no ansible-playbook runs here.
    """
    candidates: list[list[str]] = [
        [str(Path(sys.executable).parent / 'ansible-playbook')],
        ['ansible-playbook'],
    ]
    uvx = shutil.which('uvx')
    if uvx:
        candidates.append([uvx, '--offline', '--from', 'ansible-core', 'ansible-playbook'])
    for candidate in candidates:
        if not (Path(candidate[0]).is_file() or shutil.which(candidate[0])):
            continue
        try:
            completed = run_command(
                command=[*candidate, '--version'],
                environment=os.environ,
                timeout_seconds=ANSIBLE_TIMEOUT_SECONDS,
                capture_output=OutputCapture.TOGETHER,
            )
        except OSError, subprocess.TimeoutExpired:
            continue
        # A version shim (pyenv's) exits 0 without running anything
        if completed.returncode == 0 and 'ansible-playbook [core' in completed.stdout:
            return candidate
    return None


def syntax_check(*, command: list[str], playbook: Path) -> subprocess.CompletedProcess[str]:
    """Run ansible-playbook --syntax-check on a playbook with the repository's inventory.

    Returns:
        The finished run, its output together.
    """
    return run_command(
        command=[*command, '-i', str(ANSIBLE / 'inventory.yml'), str(playbook), '--syntax-check'],
        environment=os.environ | {'ANSIBLE_NOCOLOR': '1'},
        timeout_seconds=ANSIBLE_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=PROJECT_ROOT,
    )


def every_role_file_imported(*, directory: Path) -> Path:
    """Write a playbook that imports every role's task and handler file statically.

    --syntax-check follows a static import but not an include, and the roles reach most of their
    files by include (the platform's file, a loop's), so this makes Ansible parse each one.

    Returns:
        The playbook.
    """
    play = {
        'name': "Parse every role's task and handler files",
        'hosts': 'localhost',
        'gather_facts': False,
        'tasks': [
            {'name': str(path.relative_to(ROLES)), 'ansible.builtin.import_tasks': str(path)}
            for path in sorted(ROLES.glob('*/tasks/*.yml'))
        ],
        'handlers': [
            {'name': str(path.relative_to(ROLES)), 'ansible.builtin.import_tasks': str(path)}
            for path in sorted(ROLES.glob('*/handlers/*.yml'))
        ],
    }
    playbook = directory / 'every_role_file.yml'
    playbook.write_text(yaml.safe_dump([play], sort_keys=False), encoding='utf-8')
    return playbook


@pytest.fixture
def ansible_playbook() -> list[str]:
    """The ansible-playbook to run, or a skip saying why there is none.

    Returns:
        The command's first words.
    """
    command = ansible_playbook_command()
    if command is None:
        pytest.skip(
            'no ansible-playbook runs here: none beside this Python or on PATH, and uvx has no '
            'cached ansible-core (uvx --from ansible-core ansible-playbook --version fetches it)'
        )
    return command


def test_there_are_playbooks_to_check():
    """The syntax check below is parametrized by the playbooks found: an empty list checks none."""
    assert {path.name for path in PLAYBOOKS} >= {'ai_service.yml', 'raspberry_pi_runner.yml'}


@pytest.mark.parametrize('playbook', PLAYBOOKS, ids=[path.name for path in PLAYBOOKS])
def test_every_playbook_passes_ansibles_syntax_check(ansible_playbook: list[str], playbook: Path):
    """Ansible's parser accepts each playbook as written, with the repository's inventory."""
    completed = syntax_check(command=ansible_playbook, playbook=playbook)

    assert completed.returncode == 0, completed.stdout
    assert f'playbook: {playbook}' in completed.stdout


def test_every_role_task_file_passes_ansibles_syntax_check(
    ansible_playbook: list[str], tmp_path: Path
):
    """Each role file reached by an include, which the playbooks' own check never opens, parses.

    Caught here, and by nothing in the rendering tests: a YAML error, an unknown module or
    keyword, and a free-form include whose `==` Ansible reads as options.
    """
    playbook = every_role_file_imported(directory=tmp_path)

    completed = syntax_check(command=ansible_playbook, playbook=playbook)

    assert completed.returncode == 0, completed.stdout
    imported = yaml.safe_load(playbook.read_text(encoding='utf-8'))[0]['tasks']
    assert len(imported) == len(list(ROLES.glob('*/tasks/*.yml'))) > 0
