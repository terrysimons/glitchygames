"""Ansible's output in the hosts' natural order (ansible/callback_plugins/natural_order.py).

Ansible starts each task on every host at once and prints each host's result as it finishes, so
the Pi 5s (faster) printed before the Pi 4 even with ``order: inventory`` (the owner, 2026-11-14:
"some are still sorting 8, 16, 4"). The plugin is Ansible's default output with each task's
results held until the task ends and then printed host by host in natural order (4gb, 8gb,
16gb). Its ordering is ansible/plugin_support/natural_order.py, plain Python with no Ansible
import (Ansible isn't in this project's environment: pyproject.toml), tested here; the plugin is
the thin layer over Ansible's default callback that feeds it.
"""

from __future__ import annotations

import ast
import configparser
import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUPPORT_PATH = PROJECT_ROOT / 'ansible' / 'plugin_support' / 'natural_order.py'
PLUGIN_PATH = PROJECT_ROOT / 'ansible' / 'callback_plugins' / 'natural_order.py'
CONFIG_PATH = PROJECT_ROOT / 'ansible.cfg'
# The default callback's hooks that print a host's result: each must be held, not printed
RESULT_HOOKS = {
    'v2_runner_on_ok',
    'v2_runner_on_failed',
    'v2_runner_on_skipped',
    'v2_runner_on_unreachable',
    'v2_runner_item_on_ok',
    'v2_runner_item_on_failed',
    'v2_runner_item_on_skipped',
}
# The hooks that start something new: each must print what is held first
BOUNDARY_HOOKS = {
    'v2_playbook_on_task_start',
    'v2_playbook_on_handler_task_start',
    'v2_playbook_on_play_start',
    'v2_playbook_on_include',
    'v2_playbook_on_no_hosts_remaining',
    'v2_playbook_on_stats',
}


def load_support() -> ModuleType:
    """Load the ordering module by its path.

    Returns:
        The module.

    Raises:
        ImportError: When the file can't be loaded.

    """
    specification = importlib.util.spec_from_file_location('natural_order_support', SUPPORT_PATH)
    if specification is None or specification.loader is None:
        raise ImportError(SUPPORT_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_results_print_in_natural_order_whatever_order_they_finish():
    """The Pi 5s finish first; the Pi 4's results still print first."""
    support = load_support()
    buffer = support.ResultBuffer()
    printed: list[str] = []
    for host in (
        'raspberry-pi-5-8gb-ubuntu',
        'raspberry-pi-5-16gb-ubuntu',
        'raspberry-pi-4-4gb-ubuntu',
    ):
        buffer.hold(host=host, show=lambda host=host: printed.append(host))

    buffer.release()

    assert printed == [
        'raspberry-pi-4-4gb-ubuntu',
        'raspberry-pi-5-8gb-ubuntu',
        'raspberry-pi-5-16gb-ubuntu',
    ]


def test_a_hosts_own_results_keep_their_order():
    """A loop's items, then the task's result: in the order they came, host by host."""
    support = load_support()
    buffer = support.ResultBuffer()
    printed: list[str] = []
    for host, line in [
        ('raspberry-pi-5-8gb-ubuntu', '8 item 1'),
        ('raspberry-pi-4-4gb-ubuntu', '4 item 1'),
        ('raspberry-pi-5-8gb-ubuntu', '8 item 2'),
        ('raspberry-pi-4-4gb-ubuntu', '4 item 2'),
        ('raspberry-pi-4-4gb-ubuntu', '4 done'),
        ('raspberry-pi-5-8gb-ubuntu', '8 done'),
    ]:
        buffer.hold(host=host, show=lambda line=line: printed.append(line))

    buffer.release()

    assert printed == ['4 item 1', '4 item 2', '4 done', '8 item 1', '8 item 2', '8 done']


def test_released_results_are_not_printed_again():
    """Releasing empties the buffer: the next task starts clean."""
    support = load_support()
    buffer = support.ResultBuffer()
    printed: list[str] = []
    buffer.hold(host='raspberry-pi-4-4gb-ubuntu', show=lambda: printed.append('once'))

    buffer.release()
    buffer.release()

    assert printed == ['once']


def test_the_natural_key_orders_digits_by_value():
    """4gb, 8gb, 16gb, where plain sorting puts 16gb first."""
    support = load_support()
    names = ['raspberry-pi-5-16gb-ubuntu', 'raspberry-pi-4-4gb-ubuntu', 'raspberry-pi-5-8gb-ubuntu']

    assert sorted(names, key=support.natural_key) == [
        'raspberry-pi-4-4gb-ubuntu',
        'raspberry-pi-5-8gb-ubuntu',
        'raspberry-pi-5-16gb-ubuntu',
    ]


def test_the_tests_sort_hosts_with_the_plugins_key():
    """One natural order: the inventory tests use the plugin's own key."""
    from tests import ansible_inventory

    assert ansible_inventory.natural_key(
        'raspberry-pi-5-16gb-ubuntu'
    ) == load_support().natural_key('raspberry-pi-5-16gb-ubuntu')


def plugin_tree() -> ast.Module:
    """Return the plugin's source, parsed (it imports Ansible, so it isn't imported here).

    Returns:
        The module's syntax tree.

    """
    return ast.parse(PLUGIN_PATH.read_text(encoding='utf-8'))


def plugin_methods() -> dict[str, ast.FunctionDef]:
    """Return the plugin class's methods, by name.

    Returns:
        The methods.

    """
    (plugin_class,) = [node for node in plugin_tree().body if isinstance(node, ast.ClassDef)]
    return {node.name: node for node in plugin_class.body if isinstance(node, ast.FunctionDef)}


def calls_in(function: ast.FunctionDef) -> set[str]:
    """Return the attribute names a method calls (``self._buffer.hold`` gives ``hold``).

    Returns:
        The names.

    """
    return {
        node.func.attr
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


@pytest.mark.parametrize('hook', sorted(RESULT_HOOKS))
def test_every_result_is_held(hook):
    """Each hook that prints a host's result holds it instead."""
    assert 'hold' in calls_in(plugin_methods()[hook])


@pytest.mark.parametrize('hook', sorted(BOUNDARY_HOOKS))
def test_whatever_starts_next_prints_the_held_results_first(hook):
    """A new task, handler, play or include, or the recap, releases what is held first."""
    assert 'release' in calls_in(plugin_methods()[hook])


def test_the_plugin_is_a_stdout_callback_named_as_the_config_selects_it():
    """ansible.cfg selects it as Ansible's output and points at its directory."""
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding='utf-8')
    names = {
        node.targets[0].id: node.value.value
        for (plugin_class,) in [[n for n in plugin_tree().body if isinstance(n, ast.ClassDef)]]
        for node in plugin_class.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
    }

    assert names['CALLBACK_TYPE'] == 'stdout'
    assert config['defaults']['stdout_callback'] == names['CALLBACK_NAME'] == 'natural_order'
    assert config['defaults']['callback_plugins'] == 'ansible/callback_plugins'


def test_the_plugin_loads_the_ordering_by_its_path():
    """The plugin finds the ordering module beside its own directory, whatever the working one."""
    source = PLUGIN_PATH.read_text(encoding='utf-8')

    assert "'plugin_support' / 'natural_order.py'" in source
    assert 'Path(__file__)' in source
