"""The Ansible setup for the local AI service (ansible/macos_ai_service.yml).

Its plan is plans/lucid-circuit.md. Running it takes a Mac, gigabytes of downloads and a GPU, so
these only check what would go wrong quietly: a pin that isn't exact, two agents on one port, or a
model a host can never get.
"""

import configparser
import contextlib
import itertools
import json
import os
import re
import shutil
import socket
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs the service's rendered scripts under sh
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import pytest
import yaml

from tests.ansible_rendering import (
    ansible_variables,
    render_expression,
    render_template,
    render_value,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

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


def test_the_package_never_takes_the_models():
    """The package stays small, and the check for a model in its payload stays."""
    tasks = (ROLES / 'ai_package' / 'tasks' / 'main.yml').read_text(encoding='utf-8')

    assert r"is not search('\.gguf')" in tasks


def test_the_ai_service_is_on_by_default_and_off_on_the_raspberry_pis():
    """Every host gets the service unless its platform turns ai_enabled off, as the Pis do."""
    inventory = yaml.safe_load(
        (PROJECT_ROOT / 'ansible' / 'inventory.yml').read_text(encoding='utf-8'),
    )
    raspberry_pis = inventory['all']['children']['raspberry_pis']

    assert inventory['all']['vars']['ai_enabled'] is True
    assert raspberry_pis['vars']['ai_enabled'] is False
    # No Pi turns it back on for itself
    assert all('ai_enabled' not in host for host in raspberry_pis['hosts'].values())


def test_only_hosts_with_ai_enabled_get_the_ai_service():
    """The hosts are sorted without connecting, then only enabled Macs get the service.

    Checked by hand with ansible-playbook: a host with ai_enabled false is never contacted.
    """
    sorting_play, service_play = yaml.safe_load(
        (PROJECT_ROOT / 'ansible' / 'macos_ai_service.yml').read_text(encoding='utf-8'),
    )

    assert sorting_play['hosts'] == 'all'
    assert sorting_play['gather_facts'] is False
    # Every --tags run needs the groups, or the service play would match no host
    assert sorting_play['tags'] == ['always']
    (sorting_task,) = sorting_play['tasks']
    assert sorting_task['ansible.builtin.group_by']['key'] == (
        "{{ 'ai_enabled' if ai_enabled | bool else 'ai_disabled' }}"
    )
    assert service_play['hosts'] == 'macos:&ai_enabled'


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
    architecture: Literal['aarch64', 'x86_64'],
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
    variables = ansible_variables(system='Darwin', architecture='aarch64', home=tmp_path)
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
    options = rendered_options(system='Darwin', architecture='aarch64', tmp_path=tmp_path)

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
SHELL_TEMPLATES = ['ai-service.sh.j2', 'run-llama-server.sh.j2', 'uninstall.sh.j2']
SYSTEMS: list[Literal['Darwin', 'Linux']] = ['Darwin', 'Linux']
ARCHITECTURES: list[Literal['aarch64', 'x86_64']] = ['aarch64', 'x86_64']
# The inventory's macos value; Linux's is in group_vars/linux.yml
MAC_GPU_LAYERS = 99
# What runs in place of launchd's, systemd's and the package database's tools: each call is
# recorded, and asking whether an agent runs says no. A test never reaches the real service
SERVICE_TOOL_STUB = """#!/bin/sh
printf '%s %s\\n' "$(basename "$0")" "$*" >> "$SERVICE_TOOL_LOG"
for argument in "$@"; do
    case "$argument" in
        is-active|print) exit 3 ;;
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
        self.variables = ansible_variables(system=system, architecture='aarch64', home=home)
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
        """Render one of the service's shell templates into the tools folder.

        Returns:
            The rendered script.
        """
        rendered = self.tools / template.removesuffix('.j2')
        rendered.write_text(
            render_template(path=TEMPLATES / template, variables=self.variables),
            encoding='utf-8',
        )
        return rendered

    def run(
        self, *, template: str, arguments: list[str], environment: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run a rendered script with this home, its XDG folders and the fake tools first.

        Returns:
            The finished run.
        """
        return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - sh and a rendered script, as an argument list
            ['/bin/sh', str(self.script(template=template)), *arguments],
            env={
                'HOME': str(self.home),
                'XDG_DATA_HOME': str(self.home / '.local' / 'share'),
                'XDG_CACHE_HOME': str(self.home / '.cache'),
                'XDG_STATE_HOME': str(self.home / '.local' / 'state'),
                'PATH': os.pathsep.join([
                    str(self.tools),
                    '/usr/bin',
                    '/bin',
                    '/usr/sbin',
                    '/sbin',
                ]),
                'SERVICE_TOOL_LOG': str(self.tool_log),
                **(environment or {}),
            },
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

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
        return run_set_fact_tasks(tasks=role_tasks(role='ai_service'), variables=self.variables)[
            'ai_service_agents'
        ]

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
                facts[name] = render_expression(expression=expression, variables=scope)
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
@pytest.mark.parametrize('system', SYSTEMS)
@pytest.mark.parametrize('architecture', ARCHITECTURES)
def test_every_rendered_script_passes_sh_n(
    tmp_path: Path, system: Literal['Darwin', 'Linux'], architecture: Literal['aarch64', 'x86_64']
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
    mac = ansible_variables(system='Darwin', architecture='aarch64', home=tmp_path)
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
