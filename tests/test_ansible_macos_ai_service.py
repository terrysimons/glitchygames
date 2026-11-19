"""The Ansible setup for the local AI service (ansible/macos_ai_service.yml).

Its plan is plans/lucid-circuit.md. Running it takes a Mac, gigabytes of downloads and a GPU, so
these only check what would go wrong quietly: a pin that isn't exact, two agents on one port, or a
model a host can never get.
"""

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import pytest
import yaml

from tests.ansible_rendering import ansible_variables, render_template

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
    """The proof a variant loads is llama-server's log line naming a module in the runtime's bin/."""

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
