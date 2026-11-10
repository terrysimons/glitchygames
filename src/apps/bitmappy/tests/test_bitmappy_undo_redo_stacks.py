"""UndoRedoManager's stacks, through the command API the editor uses (BUGS.md #251).

Every step the editor records is a command (``push_command``, ``push_frame_command``; the
classes in ``bitmappy/history/commands.py``). These tests drive the manager with a recording
command, so each branch of its stacks is checked as the editor reaches it: queries, pushes,
undo and redo (succeeding, failing, raising), the per-frame stacks, the history limit, clearing,
and the collapse of a frame creation followed by its own selection. They replace the tests of
the legacy ``add_operation`` layer, removed with it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self, cast

import pytest

from bitmappy.history import OperationType, UndoRedoManager
from bitmappy.history.commands import FrameAddCommand, FrameSelectionCommand

if TYPE_CHECKING:
    from bitmappy.history.commands import EditorContext

# An outcome a recorded step answers: True, False, or an exception to raise
StepOutcome = bool | Exception


class RecordedCommand:
    """A command that records its steps and answers each with the outcome it was given."""

    def __init__(
        self: Self,
        description: str,
        *,
        operation_type: OperationType = OperationType.CANVAS_PIXEL_CHANGE,
        undo_outcome: StepOutcome = True,
        execute_outcome: StepOutcome = True,
        **attributes: Any,
    ) -> None:
        """Make the command.

        Args:
            description: Its description (the undo and redo labels).
            operation_type: Its operation type.
            undo_outcome: What ``undo`` answers (an exception is raised).
            execute_outcome: What ``execute`` answers (an exception is raised).
            **attributes: More attributes (what the frame create/select collapse reads).

        """
        self.description = description
        self.operation_type = operation_type
        self.timestamp = 0.0
        self.undo_outcome = undo_outcome
        self.execute_outcome = execute_outcome
        self.steps: list[str] = []
        for name, value in attributes.items():
            setattr(self, name, value)

    def execute(self: Self) -> bool:
        """Record the step and answer its outcome.

        Returns:
            The outcome given (an exception given is raised instead).

        """
        self.steps.append('execute')
        if isinstance(self.execute_outcome, Exception):
            raise self.execute_outcome
        return self.execute_outcome

    def undo(self: Self) -> bool:
        """Record the step and answer its outcome.

        Returns:
            The outcome given (an exception given is raised instead).

        """
        self.steps.append('undo')
        if isinstance(self.undo_outcome, Exception):
            raise self.undo_outcome
        return self.undo_outcome


@pytest.fixture
def manager() -> UndoRedoManager:
    """A manager with room for three steps per stack.

    Returns:
        The manager.

    """
    return UndoRedoManager(max_history=3)


class TestQueries:
    """What can be undone or redone, and the labels for it."""

    def test_an_empty_manager_has_nothing_to_undo_or_redo(self, manager):
        assert not manager.can_undo()
        assert not manager.can_redo()
        assert manager.get_undo_description() is None
        assert manager.get_redo_description() is None
        assert not manager.can_undo_frame('idle', 0)
        assert not manager.can_redo_frame('idle', 0)

    def test_the_labels_name_the_next_steps(self, manager):
        manager.push_command(RecordedCommand('paint'))
        manager.push_command(RecordedCommand('fill'))
        manager.undo()

        assert manager.get_undo_description() == 'paint'
        assert manager.get_redo_description() == 'fill'

    def test_nothing_can_be_undone_or_redone_during_an_undo(self, manager):
        manager.push_command(RecordedCommand('paint'))
        manager.push_frame_command('idle', 0, RecordedCommand('stroke'))
        manager.is_undoing = True
        manager.is_redoing = True

        assert not manager.can_undo()
        assert not manager.can_redo()
        assert not manager.can_undo_frame('idle', 0)
        assert not manager.can_redo_frame('idle', 0)

    def test_a_frames_stacks_exist_once_a_step_was_pushed_for_it(self, manager):
        manager.push_frame_command('idle', 0, RecordedCommand('stroke'))

        assert manager.can_undo_frame('idle', 0)
        assert not manager.can_redo_frame('idle', 0)
        assert not manager.can_undo_frame('idle', 1)

    def test_the_current_frame_is_where_the_editor_is(self, manager):
        manager.set_current_frame('walk', 2)

        assert manager.current_frame == ('walk', 2)


class TestPushing:
    """A new step goes on the undo stack and clears what could be redone."""

    def test_a_new_step_clears_the_redo_stack(self, manager):
        manager.push_command(RecordedCommand('paint'))
        manager.undo()
        assert manager.can_redo()

        manager.push_command(RecordedCommand('fill'))

        assert not manager.can_redo()
        assert manager.at_head_of_history

    def test_a_step_pushed_during_an_undo_is_ignored(self, manager):
        manager.is_undoing = True

        manager.push_command(RecordedCommand('paint'))

        assert manager.undo_stack == []

    def test_the_oldest_step_goes_past_the_history_limit(self, manager):
        for name in ('one', 'two', 'three', 'four'):
            manager.push_command(RecordedCommand(name))

        assert [command.description for command in manager.undo_stack] == ['two', 'three', 'four']

    def test_a_frames_oldest_step_goes_past_the_history_limit(self, manager):
        for name in ('one', 'two', 'three', 'four'):
            manager.push_frame_command('idle', 0, RecordedCommand(name))

        assert [command.description for command in manager.frame_undo_stacks['idle', 0]] == [
            'two',
            'three',
            'four',
        ]

    def test_a_new_frame_step_clears_that_frames_redo_stack(self, manager):
        manager.push_frame_command('idle', 0, RecordedCommand('stroke'))
        manager.undo_frame('idle', 0)

        manager.push_frame_command('idle', 0, RecordedCommand('line'))

        assert not manager.can_redo_frame('idle', 0)

    def test_a_frame_step_pushed_during_an_undo_keeps_the_redo_stack(self, manager):
        manager.push_frame_command('idle', 0, RecordedCommand('stroke'))
        manager.undo_frame('idle', 0)
        manager.is_undoing = True

        manager.push_frame_command('idle', 0, RecordedCommand('line'))

        assert manager.frame_redo_stacks['idle', 0]


class TestUndoAndRedo:
    """Undo and redo move a step between the stacks; a failed step is never lost."""

    def test_undo_then_redo_moves_the_step_back_and_forth(self, manager):
        command = RecordedCommand('paint')
        manager.push_command(command)

        assert manager.undo()
        assert not manager.at_head_of_history
        assert manager.redo()

        assert command.steps == ['undo', 'execute']
        assert manager.undo_stack == [command]
        assert manager.at_head_of_history

    def test_redo_short_of_the_newest_step_is_not_at_the_head(self, manager):
        manager.push_command(RecordedCommand('paint'))
        manager.push_command(RecordedCommand('fill'))
        manager.undo()
        manager.undo()

        manager.redo()

        assert not manager.at_head_of_history

    def test_nothing_to_undo_or_redo_answers_false(self, manager):
        assert not manager.undo()
        assert not manager.redo()

    @pytest.mark.parametrize('outcome', [False, RuntimeError('broken')], ids=['false', 'raises'])
    def test_a_failed_undo_keeps_the_step_to_undo(self, manager, outcome):
        command = RecordedCommand('paint', undo_outcome=outcome)
        manager.push_command(command)

        assert not manager.undo()

        assert manager.undo_stack == [command]
        assert not manager.is_undoing

    @pytest.mark.parametrize('outcome', [False, RuntimeError('broken')], ids=['false', 'raises'])
    def test_a_failed_redo_keeps_the_step_to_redo(self, manager, outcome):
        command = RecordedCommand('paint', execute_outcome=outcome)
        manager.push_command(command)
        manager.undo()

        assert not manager.redo()

        assert manager.redo_stack == [command]
        assert not manager.is_redoing


class TestFrameUndoAndRedo:
    """Each frame keeps its own steps, undone and redone apart from the global ones."""

    def test_a_frames_step_undoes_and_redoes(self, manager):
        command = RecordedCommand('stroke')
        manager.push_frame_command('idle', 0, command)

        assert manager.undo_frame('idle', 0)
        assert manager.can_redo_frame('idle', 0)
        assert manager.redo_frame('idle', 0)

        assert command.steps == ['undo', 'execute']
        assert manager.frame_undo_stacks['idle', 0] == [command]

    def test_a_frame_with_no_steps_answers_false(self, manager):
        assert not manager.undo_frame('idle', 0)
        assert not manager.redo_frame('idle', 0)

    def test_a_frame_step_waits_while_another_undo_runs(self, manager):
        command = RecordedCommand('stroke')
        manager.push_frame_command('idle', 0, command)
        manager.undo_frame('idle', 0)
        manager.push_frame_command('idle', 1, RecordedCommand('line'))
        manager.is_redoing = True

        assert not manager.undo_frame('idle', 1)
        assert not manager.redo_frame('idle', 0)
        assert command.steps == ['undo']

    @pytest.mark.parametrize('outcome', [False, RuntimeError('broken')], ids=['false', 'raises'])
    def test_a_failed_frame_undo_keeps_the_step(self, manager, outcome):
        command = RecordedCommand('stroke', undo_outcome=outcome)
        manager.push_frame_command('idle', 0, command)

        assert not manager.undo_frame('idle', 0)

        assert manager.frame_undo_stacks['idle', 0] == [command]

    @pytest.mark.parametrize('outcome', [False, RuntimeError('broken')], ids=['false', 'raises'])
    def test_a_failed_frame_redo_keeps_the_step(self, manager, outcome):
        command = RecordedCommand('stroke', execute_outcome=outcome)
        manager.push_frame_command('idle', 0, command)
        manager.undo_frame('idle', 0)

        assert not manager.redo_frame('idle', 0)

        assert manager.frame_redo_stacks['idle', 0] == [command]


class TestClearingHistory:
    """A new sprite starts a new history: every stack empties, the current frame stays."""

    def test_every_stack_is_emptied_and_the_current_frame_kept(self, manager):
        manager.push_command(RecordedCommand('paint'))
        manager.push_command(RecordedCommand('fill'))
        manager.undo()
        manager.push_frame_command('idle', 0, RecordedCommand('stroke'))
        manager.set_current_frame('idle', 0)

        manager.clear_history()

        assert (manager.undo_stack, manager.redo_stack) == ([], [])
        assert (manager.frame_undo_stacks, manager.frame_redo_stacks) == ({}, {})
        assert manager.at_head_of_history
        assert manager.current_frame == ('idle', 0)


def _frame_added(animation: str, frame: int) -> RecordedCommand:
    """Return a film strip frame creation, as FrameAddCommand names its frame.

    Returns:
        The command.

    """
    return RecordedCommand(
        'add frame',
        operation_type=OperationType.FILM_STRIP_FRAME_ADD,
        animation_name=animation,
        frame_index=frame,
    )


def _frame_selected(animation: str, frame: int) -> RecordedCommand:
    """Return a frame selection, as FrameSelectionCommand names its frame.

    Returns:
        The command.

    """
    return RecordedCommand(
        'select frame',
        operation_type=OperationType.FRAME_SELECTION,
        new_animation=animation,
        new_frame=frame,
    )


class TestFrameCreateSelectCollapse:
    """Creating a frame selects it: that selection is no undo step of its own."""

    def test_the_editors_own_commands_collapse(self, manager):
        """The real commands, so the attribute names the collapse reads are theirs."""
        editor = cast('EditorContext', object())
        manager.push_command(FrameAddCommand(editor, 1, 'idle', {}))

        manager.push_command(FrameSelectionCommand(editor, 'idle', 0, 'idle', 1))

        assert [type(command) for command in manager.undo_stack] == [FrameAddCommand]

    def test_the_new_frames_own_selection_is_dropped(self, manager):
        manager.push_command(_frame_added('idle', 1))

        manager.push_command(_frame_selected('idle', 1))

        assert [command.description for command in manager.undo_stack] == ['add frame']

    def test_selecting_another_frame_is_kept(self, manager):
        manager.push_command(_frame_added('idle', 1))

        manager.push_command(_frame_selected('idle', 0))

        assert len(manager.undo_stack) == 2

    def test_a_selection_after_any_other_step_is_kept(self, manager):
        manager.push_command(RecordedCommand('paint'))

        manager.push_command(_frame_selected('idle', 1))

        assert len(manager.undo_stack) == 2

    def test_a_lone_selection_is_kept(self, manager):
        manager.push_command(_frame_selected('idle', 1))

        assert len(manager.undo_stack) == 1
