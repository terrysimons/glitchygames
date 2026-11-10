"""The Ansible setup for the local AI service (ansible/macos_ai_service.yml).

Its plan is plans/lucid-circuit.md. Running it takes a Mac, gigabytes of downloads and a GPU, so
these only check what would go wrong quietly: a pin that isn't exact, two agents on one port, or a
model a host can never get.
"""

import re
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROLES = PROJECT_ROOT / 'ansible' / 'roles'
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
