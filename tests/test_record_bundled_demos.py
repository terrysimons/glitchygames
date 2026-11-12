"""scripts/record_bundled_demos.py: every bundled demo's recipe and the command that records it.

The recording itself is checked by replaying the committed files
(tests/replay/test_bundled_demos.py). These tests check the recipes: that they name the
expected demos, that none ends with input held (the Arcade loops a demo, so a key held at its
end would stay stuck), that a recording session reaches neither the AI service nor a real pad,
and the command line.
"""

from __future__ import annotations

import os
from pathlib import Path

import pygame
import pytest
from scripts import record_bundled_demos
from scripts.demo_inputs import (
    MR_MUNCHER_DEMO_FRAME_COUNT,
    ReleaseHeldKeyOnFinalFrame,
    mr_muncher_demo_script,
)
from scripts.golden_inputs import mr_muncher_script
from scripts.record_bundled_demos import DEMO_RECIPES, DemoRecipe, demo_path, record_demo

from glitchygames.ai_link import INSTALL_ROOT_ENVIRONMENT_VARIABLE
from glitchygames.bundled_demos import console_script_in_module
from glitchygames.replay.tools.golden_traces import (
    RANDOM_SEED,
    InputScript,
    load_input_script,
    press,
    release,
)
from tests.workspace_expectations import EXPECTED_BUNDLED_DEMOS

JOYSTICK_DRIVER_VARIABLES = ('SDL_JOYSTICK_HIDAPI', 'SDL_JOYSTICK_MFI', 'SDL_JOYSTICK_IOKIT')
DEMO_NAME_FOR_SESSION_TESTS = 'session-test.jsonl.gz'


# Event type -> the kind of input it presses or releases; which attributes name the input
PRESSES = {
    pygame.KEYDOWN: 'key',
    pygame.MOUSEBUTTONDOWN: 'mouse',
    pygame.JOYBUTTONDOWN: 'joystick',
    pygame.CONTROLLERBUTTONDOWN: 'controller',
}
RELEASES = {
    pygame.KEYUP: 'key',
    pygame.MOUSEBUTTONUP: 'mouse',
    pygame.JOYBUTTONUP: 'joystick',
    pygame.CONTROLLERBUTTONUP: 'controller',
}


def held_input(*, event: pygame.event.Event) -> tuple[str | int, ...]:
    """Return the input a press or release event is about, the same for both.

    Args:
        event: A key, mouse button, joystick button or controller button event.

    Returns:
        ``('key', key)``, ``('mouse', button)``, or ``(kind, instance_id, button)`` for a pad.

    """
    kind = PRESSES.get(event.type) or RELEASES[event.type]
    if kind == 'key':
        return (kind, event.key)
    if kind == 'mouse':
        return (kind, event.button)
    return (kind, event.instance_id, event.button)


def held_at_end(*, recipe: DemoRecipe) -> set[tuple[str | int, ...]]:
    """Return what a recipe's scripted events press and never release before its last frame.

    Only the script's own events (``InputScript.key_events``) are walked: a per-frame input and
    a placement depend on the running scene, so a demo's per-frame input must release itself
    (PaddleSlap's releases its tracked keys before the pause, which is after the last frame).

    Args:
        recipe: The demo's recipe.

    Returns:
        ``('key', key)``, ``('mouse', button)``, ``('joystick', instance_id, button)`` and
        ``('controller', instance_id, button)`` for everything held after frame
        ``frame_count - 1``.

    """
    script = load_input_script(reference=recipe.script)
    held: set[tuple[str | int, ...]] = set()
    for frame_number in sorted(script.key_events):
        if frame_number >= recipe.frame_count:
            break
        for event in script.key_events[frame_number]:
            if event.type in PRESSES:
                held.add(held_input(event=event))
            elif event.type in RELEASES:
                held.discard(held_input(event=event))
    return held


def test_the_recipes_are_the_expected_bundled_demos():
    """The recipes record exactly the demos the workspace expects to ship."""
    assert {(recipe.package, recipe.name) for recipe in DEMO_RECIPES.values()} == (
        EXPECTED_BUNDLED_DEMOS
    )


def test_every_recipe_releases_what_it_presses():
    """No demo ends with a key, mouse button or pad button held."""
    for key, recipe in DEMO_RECIPES.items():
        assert held_at_end(recipe=recipe) == set(), key


def test_held_at_end_finds_what_a_script_leaves_pressed(mocker):
    """The check sees a key, a mouse button and a pad button left down, and ignores later frames."""
    script = InputScript()
    script.at(1, press(pygame.K_a), press(pygame.K_b))
    script.at(2, release(pygame.K_b))
    script.at(
        3,
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0)),
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=(0, 0)),
        pygame.event.Event(pygame.MOUSEBUTTONUP, button=3, pos=(0, 0)),
        pygame.event.Event(pygame.JOYBUTTONDOWN, instance_id=7, button=2),
        pygame.event.Event(pygame.JOYBUTTONDOWN, instance_id=7, button=4),
        pygame.event.Event(pygame.JOYBUTTONUP, instance_id=7, button=4),
        pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, instance_id=8, button=0),
        pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, instance_id=8, button=1),
        pygame.event.Event(pygame.CONTROLLERBUTTONUP, instance_id=8, button=1),
    )
    script.at(50, press(pygame.K_c))
    mocker.patch(f'{__name__}.load_input_script', return_value=script)
    recipe = DEMO_RECIPES['paddleslap_rally'].model_copy(update={'frame_count': 10})
    assert held_at_end(recipe=recipe) == {
        ('key', pygame.K_a),
        ('mouse', 1),
        ('joystick', 7, 2),
        ('controller', 8, 0),
    }


class StubSteering:
    """A steering that holds the up arrow from its first call on, as Mr. Muncher's does."""

    def __init__(self) -> None:
        """Start holding nothing."""
        self.held_key: int | None = None

    def __call__(self, _scene: object) -> list[pygame.event.Event]:
        if self.held_key is not None:
            return []
        self.held_key = pygame.K_UP
        return [press(pygame.K_UP)]


def test_the_final_frame_releases_the_key_the_steering_holds():
    """Run to the last frame, the wrapped steering has released everything and pressed nothing."""
    steering = StubSteering()
    wrapper = ReleaseHeldKeyOnFinalFrame(steering=steering, final_frame=5)
    held: set[int] = set()
    for frame_number in range(1, 6):
        for event in wrapper(None):
            if event.type == pygame.KEYDOWN:
                held.add(event.key)
            else:
                assert event.type == pygame.KEYUP
                assert event.scancode == release(event.key).scancode
                held.discard(event.key)
        if frame_number < 5:
            assert held == {pygame.K_UP}
    assert held == set()
    assert steering.held_key is None
    assert wrapper(None) == []


def test_the_final_frame_with_nothing_held_posts_nothing():
    """A steering between a release and a re-press has nothing to release on the last frame."""
    steering = StubSteering()
    wrapper = ReleaseHeldKeyOnFinalFrame(steering=steering, final_frame=1)
    assert wrapper(None) == []


def test_the_mr_muncher_demo_script_is_the_golden_script_with_the_wrapped_steering():
    """Only the per-frame steering differs from the golden script: the same pauses, same events."""
    golden = mr_muncher_script()
    demo = mr_muncher_demo_script()
    assert isinstance(demo.per_frame, ReleaseHeldKeyOnFinalFrame)
    assert demo.per_frame.steering.__class__ is golden.per_frame.__class__
    assert demo.per_frame.final_frame == MR_MUNCHER_DEMO_FRAME_COUNT - 1
    assert demo.key_events.keys() == golden.key_events.keys()
    assert DEMO_RECIPES['mr_muncher_chase'].frame_count == MR_MUNCHER_DEMO_FRAME_COUNT
    assert DEMO_RECIPES['mr_muncher_chase'].script == 'scripts.demo_inputs:mr_muncher_demo_script'


def test_every_demo_is_in_a_package_with_its_console_script():
    """Each recipe's package starts a game: the Arcade tile runs its console script."""
    for key, recipe in DEMO_RECIPES.items():
        assert console_script_in_module(module=recipe.package) is not None, key


def test_a_recipe_is_frozen_and_refuses_unknown_fields():
    """A recipe is data: it cannot change and cannot carry a field it does not know."""
    recipe = DEMO_RECIPES['paddleslap_rally']
    with pytest.raises(ValueError, match='frozen'):
        recipe.frame_count = 1  # ty: ignore[invalid-assignment]
    with pytest.raises(ValueError, match='extra'):
        DemoRecipe.model_validate({**recipe.model_dump(), 'unknown': 1})


def test_a_demo_goes_into_its_packages_demos_directory():
    """The demo's path is in the installed package's demos directory, named by the recipe."""
    path = demo_path(recipe=DEMO_RECIPES['paddleslap_rally'])
    assert path.parent.name == 'demos'
    assert path.parent.parent.name == 'paddleslap'
    assert path.name == 'rally.jsonl.gz'


def test_recording_a_demo_creates_its_demos_directory(mocker, tmp_path):
    """A package with no demos directory yet gets one: the recording is written into it."""
    path = tmp_path / 'not-yet' / 'demos' / 'rally.jsonl.gz'
    mocker.patch('scripts.record_bundled_demos.demo_path', return_value=path)
    mocker.patch('scripts.record_bundled_demos.record_scripted_session')
    record_demo(recipe=DEMO_RECIPES['paddleslap_rally'])
    assert path.parent.is_dir()


def session_recipe() -> DemoRecipe:
    """Return the rally's recipe under a name no committed demo has."""
    return DEMO_RECIPES['paddleslap_rally'].model_copy(update={'name': DEMO_NAME_FOR_SESSION_TESTS})


def record_with_the_recorder_patched(mocker):
    """Record a demo with the engine's recorder patched.

    Args:
        mocker: The pytest-mock fixture.

    Returns:
        ``(the recorder's mock, what the recorder saw of the environment during the session)``.

    """
    recorded = mocker.patch('scripts.record_bundled_demos.record_scripted_session')
    seen: dict[str, object] = {}

    def look_around(**_options: object) -> None:
        root = Path(os.environ[INSTALL_ROOT_ENVIRONMENT_VARIABLE])
        seen['root'] = root
        seen['root_is_an_empty_directory'] = root.is_dir() and not any(root.iterdir())
        seen['drivers'] = {name: os.environ[name] for name in JOYSTICK_DRIVER_VARIABLES}

    recorded.side_effect = look_around
    record_demo(recipe=session_recipe())
    return recorded, seen


def test_a_demo_session_never_reaches_the_ai_service(mocker):
    """The session's AI install root is an empty directory, so no service is found."""
    _recorded, seen = record_with_the_recorder_patched(mocker)
    assert seen['root_is_an_empty_directory']
    assert not Path(str(seen['root'])).exists()


def test_a_demo_session_never_reaches_a_real_pad(mocker):
    """SDL's joystick drivers are off during the session."""
    _recorded, seen = record_with_the_recorder_patched(mocker)
    assert seen['drivers'] == dict.fromkeys(JOYSTICK_DRIVER_VARIABLES, '0')


def test_a_demo_session_puts_the_environment_back(monkeypatch, mocker):
    """A variable that was set gets its value back, and one that was not stays unset."""
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, '/somewhere/else')
    monkeypatch.setenv('SDL_JOYSTICK_HIDAPI', '1')
    monkeypatch.delenv('SDL_JOYSTICK_MFI', raising=False)
    monkeypatch.delenv('SDL_JOYSTICK_IOKIT', raising=False)
    record_with_the_recorder_patched(mocker)
    assert os.environ[INSTALL_ROOT_ENVIRONMENT_VARIABLE] == '/somewhere/else'
    assert os.environ['SDL_JOYSTICK_HIDAPI'] == '1'
    assert 'SDL_JOYSTICK_MFI' not in os.environ
    assert 'SDL_JOYSTICK_IOKIT' not in os.environ


def test_a_demo_session_puts_the_environment_back_after_a_failure(monkeypatch, mocker):
    """A recording that raises still leaves the environment as it found it."""
    monkeypatch.delenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.setenv('SDL_JOYSTICK_HIDAPI', '1')
    recorded = mocker.patch('scripts.record_bundled_demos.record_scripted_session')
    recorded.side_effect = RuntimeError('the recording failed')
    with pytest.raises(RuntimeError, match='the recording failed'):
        record_demo(recipe=session_recipe())
    assert INSTALL_ROOT_ENVIRONMENT_VARIABLE not in os.environ
    assert os.environ['SDL_JOYSTICK_HIDAPI'] == '1'


def test_a_demo_is_recorded_as_a_demo(mocker):
    """The recorder gets the recipe's scene, script and flags, no controls tail, our seed."""
    recipe = session_recipe()
    recorded, _seen = record_with_the_recorder_patched(mocker)
    options = recorded.call_args.kwargs
    assert options['scene_class'].__name__ == 'Game'
    assert options['frame_count'] == recipe.frame_count
    assert options['path'] == demo_path(recipe=recipe)
    assert options['controls_tail'] is None
    assert options['random_seed'] == RANDOM_SEED
    assert options['input_only_placements'] is True
    assert options['polled_input'] is False
    assert options['stand_in_devices'] == ()


def test_main_records_one_demo_or_all(mocker):
    """--demo KEY records one recipe, --all records every one."""
    recorded = mocker.patch('scripts.record_bundled_demos.record_demo')
    mocker.patch('sys.argv', ['record_bundled_demos', '--demo', 'paddleslap_rally'])
    record_bundled_demos.main()
    assert recorded.call_count == 1
    recorded.reset_mock()
    mocker.patch('sys.argv', ['record_bundled_demos', '--all'])
    record_bundled_demos.main()
    assert [call.kwargs['recipe'] for call in recorded.call_args_list] == list(
        DEMO_RECIPES.values()
    )


def test_main_needs_a_demo_or_all(mocker):
    """With neither --demo nor --all there is nothing to record: argparse refuses."""
    mocker.patch('sys.argv', ['record_bundled_demos'])
    with pytest.raises(SystemExit):
        record_bundled_demos.main()
