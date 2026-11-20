"""ansible/inventory.yml read as Ansible reads it: hosts in nested groups, variables flowing down.

Shared by the tests that check the Raspberry Pis against the inventory (tests/test_ci_config.py,
tests/test_measure_on_raspberry_pi.py, tests/test_ansible_raspberry_pi_clock.py), so they agree
on which hosts a group holds and what each sees.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from types import ModuleType

INVENTORY_PATH = Path(__file__).resolve().parent.parent / 'ansible' / 'inventory.yml'


def inventory_group(name: str) -> dict[str, Any]:
    """Return one of the inventory's top-level groups, as written.

    Returns:
        The group, parsed.

    """
    inventory = yaml.safe_load(INVENTORY_PATH.read_text(encoding='utf-8'))
    return inventory['all']['children'][name]


def hosts_of_group(
    group: dict[str, Any], *, inherited: dict[str, Any] | None = None
) -> dict[str, dict[str, Any]]:
    """Return a group's hosts and its child groups' hosts, each with its groups' variables.

    Variables flow down as Ansible applies them: a child group's over its parent's, a host's
    own over both.

    Returns:
        Each host's variables, by host name.

    """
    variables = {**(inherited or {}), **(group.get('vars') or {})}
    hosts = {
        name: {**variables, **(host or {})} for name, host in (group.get('hosts') or {}).items()
    }
    for child in (group.get('children') or {}).values():
        # A child named with no body (linux's raspberry_pis) refers to a group written elsewhere,
        # whose hosts that definition already gave
        hosts |= hosts_of_group(child or {}, inherited=variables)
    return hosts


def every_host() -> dict[str, dict[str, Any]]:
    """Return every host in the inventory, with the variables it sees from all down.

    Returns:
        Each host's variables, by host name.

    """
    inventory = yaml.safe_load(INVENTORY_PATH.read_text(encoding='utf-8'))
    return hosts_of_group(inventory['all'])


def _load_natural_order() -> ModuleType:
    """Load the output plugin's ordering module by its path: one natural order for both.

    Returns:
        The module.

    Raises:
        ImportError: When the file can't be loaded.

    """
    path = (
        Path(__file__).resolve().parent.parent / 'ansible' / 'plugin_support' / 'natural_order.py'
    )
    specification = importlib.util.spec_from_file_location('natural_order_support', path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


# 4gb, 8gb, 16gb: the key ansible/callback_plugins/natural_order.py prints hosts by
natural_key = _load_natural_order().natural_key


def raspberry_pi_hosts() -> dict[str, dict[str, Any]]:
    """Return every Raspberry Pi, whatever its OS group, with the variables it sees.

    Returns:
        Each host's variables, by host name.

    """
    return hosts_of_group(inventory_group('raspberry_pis'))
