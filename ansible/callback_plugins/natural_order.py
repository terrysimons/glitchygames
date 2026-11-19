"""Ansible's default output, with each task's results printed in the hosts' natural order.

Ansible runs a task on every host at once and the default callback prints each host's result
as it finishes, so faster hosts print first whatever the inventory's order (the Pi 5s before the
Pi 4: the owner, 2026-11-14). This callback holds each result under its host and releases them,
host by host in natural order (4gb, 8gb, 16gb), when the next task, handler, play or include
starts, or the recap does. Everything else is the default callback's (the recap itself is listed
by Ansible's own sort). Selected by ansible.cfg at the repository root
(stdout_callback = natural_order).

The ordering is ansible/plugin_support/natural_order.py, plain Python loaded by its path so
this project's tests can run it (Ansible isn't in this project's environment). Tests:
tests/test_ansible_natural_order_output.py.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

from ansible.plugins.callback.default import CallbackModule as DefaultCallbackModule

if TYPE_CHECKING:
    from types import ModuleType

    from ansible.executor.stats import AggregateStats
    from ansible.executor.task_result import CallbackTaskResult
    from ansible.playbook.included_file import IncludedFile
    from ansible.playbook.play import Play
    from ansible.playbook.task import Task

DOCUMENTATION = """
name: natural_order
type: stdout
short_description: the default output, each task's results in the hosts' natural order
description:
  - Ansible's default stdout callback, holding each task's results and printing them host by
    host in natural order (4gb, 8gb, 16gb) when the task ends, not as each host finishes.
extends_documentation_fragment:
  - default_callback
  - result_format_callback
"""


def _load_ordering() -> ModuleType:
    """Load the ordering module beside this plugin's directory, by its path.

    Returns:
        The module.

    Raises:
        ImportError: When the file can't be loaded.

    """
    path = Path(__file__).resolve().parent.parent / 'plugin_support' / 'natural_order.py'
    specification = importlib.util.spec_from_file_location('glitchygames_natural_order', path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


_ORDERING = _load_ordering()


class CallbackModule(DefaultCallbackModule):
    """The default callback, printing each task's results in the hosts' natural order."""

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'natural_order'

    def __init__(self) -> None:
        """Start with nothing held."""
        super().__init__()
        self._buffer = _ORDERING.ResultBuffer()

    # Each result, held under its host

    def v2_runner_on_ok(self, result: CallbackTaskResult) -> None:
        """Hold a host's ok result."""
        self._buffer.hold(
            host=result._host.get_name(),
            show=lambda: super(CallbackModule, self).v2_runner_on_ok(result),
        )

    # Ansible passes ignore_errors by keyword (its strategy's send_callback)
    def v2_runner_on_failed(
        self, result: CallbackTaskResult, *, ignore_errors: bool = False
    ) -> None:
        """Hold a host's failed result."""
        self._buffer.hold(
            host=result._host.get_name(),
            show=lambda: super(CallbackModule, self).v2_runner_on_failed(
                result, ignore_errors=ignore_errors
            ),
        )

    def v2_runner_on_skipped(self, result: CallbackTaskResult) -> None:
        """Hold a host's skipped result."""
        self._buffer.hold(
            host=result._host.get_name(),
            show=lambda: super(CallbackModule, self).v2_runner_on_skipped(result),
        )

    def v2_runner_on_unreachable(self, result: CallbackTaskResult) -> None:
        """Hold a host's unreachable result."""
        self._buffer.hold(
            host=result._host.get_name(),
            show=lambda: super(CallbackModule, self).v2_runner_on_unreachable(result),
        )

    def v2_runner_item_on_ok(self, result: CallbackTaskResult) -> None:
        """Hold a host's ok loop item."""
        self._buffer.hold(
            host=result._host.get_name(),
            show=lambda: super(CallbackModule, self).v2_runner_item_on_ok(result),
        )

    def v2_runner_item_on_failed(self, result: CallbackTaskResult) -> None:
        """Hold a host's failed loop item."""
        self._buffer.hold(
            host=result._host.get_name(),
            show=lambda: super(CallbackModule, self).v2_runner_item_on_failed(result),
        )

    def v2_runner_item_on_skipped(self, result: CallbackTaskResult) -> None:
        """Hold a host's skipped loop item."""
        self._buffer.hold(
            host=result._host.get_name(),
            show=lambda: super(CallbackModule, self).v2_runner_item_on_skipped(result),
        )

    # Whatever starts next prints what is held first

    # Ansible passes is_conditional by keyword (its strategies' send_callback)
    def v2_playbook_on_task_start(self, task: Task, *, is_conditional: bool) -> None:
        """Print the last task's results, then this task's banner as the default does."""
        self._buffer.release()
        super().v2_playbook_on_task_start(task, is_conditional)

    def v2_playbook_on_handler_task_start(self, task: Task) -> None:
        """Print the last task's results, then this handler's banner."""
        self._buffer.release()
        super().v2_playbook_on_handler_task_start(task)

    def v2_playbook_on_play_start(self, play: Play) -> None:
        """Print the last task's results, then this play's banner."""
        self._buffer.release()
        super().v2_playbook_on_play_start(play)

    def v2_playbook_on_include(self, included_file: IncludedFile) -> None:
        """Print the last task's results, then the include."""
        self._buffer.release()
        super().v2_playbook_on_include(included_file)

    def v2_playbook_on_no_hosts_remaining(self) -> None:
        """Print the last task's results, then the notice."""
        self._buffer.release()
        super().v2_playbook_on_no_hosts_remaining()

    def v2_playbook_on_stats(self, stats: AggregateStats) -> None:
        """Print the last task's results, then the recap."""
        self._buffer.release()
        super().v2_playbook_on_stats(stats)
