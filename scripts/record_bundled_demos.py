r"""Record the bundled demos: one recipe per demo, one command for all of them.

A bundled demo is a recording a game ships in its package, ``<package>/demos/<name>.jsonl.gz``
(glitchygames/bundled_demos.py), which the Arcade plays on a tile and loops. Every demo's
recipe is a ``DemoRecipe`` in ``DEMO_RECIPES`` below: the scene it plays, the input script
(``MODULE:NAME``, scripts/golden_inputs.py, loaded with ``load_input_script``), how many of the
script's frames to record, and the package and file name the recording goes to. The engine's
scripted-session recorder does the recording (glitchygames/replay/tools/scripted_sessions.py);
this script holds only this repository's policy.

The rules every demo follows:

- It is recorded without a controls tail (a demo ends after its last frame, with no quit), under
  our goldens' seed (``RANDOM_SEED``).
- It ends with no input held: the Arcade loops a demo, so a key, mouse button or pad button held
  at its end would stay stuck when the demo starts again
  (tests/test_record_bundled_demos.py ``test_every_recipe_releases_what_it_presses``).
- A recording session never reaches the AI service (``GLITCHYGAMES_AI_INSTALL_ROOT`` names an
  empty temporary directory for the session, so no service is found and the game builds plain
  host sources) and never a real pad (SDL's joystick drivers are off for the session, as for a
  test run: tests/sdl_defaults.py). A pad a demo needs is a stand-in
  (``DemoRecipe.stand_in_devices``, glitchygames/input/stand_in_devices.py), which the
  recording's header holds and its replay opens again. Both settings are for the session only:
  the environment is put back exactly afterwards (a variable that was unset is unset again).

Commands, from the repository root (``--all`` records every demo):

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.record_bundled_demos \
        --demo paddleslap_rally

PaddleSlap's rally is 450 frames: the script's frames before its pause (frame 450), with the
paddles following the balls, so the loop point shows play and not the pause screen. The
script's placement before frame 449 releases the paddles' keys (it is the pause's preparation),
so the demo ends with nothing held; the committed recording's key events confirm it.

Re-record only deliberately, as the goldens are (scripts/record_scripted_session.py): a
re-recorded demo never matches the one it replaces, and tests/replay/test_bundled_demos.py
replays the committed file.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

from glitchygames.ai_link import INSTALL_ROOT_ENVIRONMENT_VARIABLE
from glitchygames.input.devices import DeviceDescriptor
from glitchygames.replay.tools.golden_traces import (
    RANDOM_SEED,
    GameSceneClasses,
    load_input_script,
)
from glitchygames.replay.tools.scripted_sessions import record_scripted_session
from scripts.demo_inputs import (
    BITMAPPY_DEMO_FRAME_COUNT,
    DT_DEMO_FRAME_COUNT,
    MR_MUNCHER_DEMO_FRAME_COUNT,
    TEXT_INPUT_DEMO_FRAME_COUNT,
)

if TYPE_CHECKING:
    from collections.abc import Generator

# SDL's joystick drivers on macOS, off for a recording session so no real pad reaches a demo
# (the same three, and the same value, as tests/sdl_defaults.py)
SDL_JOYSTICK_DRIVER_VARIABLES = ('SDL_JOYSTICK_HIDAPI', 'SDL_JOYSTICK_MFI', 'SDL_JOYSTICK_IOKIT')
SDL_DRIVER_OFF = '0'
DEMOS_DIRECTORY_NAME = 'demos'
# Read at runtime (not only in an annotation): pydantic builds the recipe's field from it
StandInDevices = tuple[DeviceDescriptor, ...]


class DemoRecipe(BaseModel):
    """How one bundled demo is recorded.

    Attributes:
        scene: The scene class to play, ``'module:Qualname'``.
        script: The input script, ``'module:callable'`` (``load_input_script``).
        frame_count: How many of the script's frames to record.
        package: The import package the demo ships in (its ``demos`` directory holds it).
        name: The demo's file name, ``<name>.jsonl.gz``.
        polled_input: True when the game reads its controls from the frame's polled input.
        input_only_placements: True when the script's placements only steer its own input.
        stand_in_devices: Joysticks and game controllers that exist only in the session.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    scene: str
    script: str
    frame_count: int
    package: str
    name: str
    polled_input: bool = False
    input_only_placements: bool = False
    stand_in_devices: StandInDevices = ()


# In key order (``main --all`` records in sorted key order). Brave Adventurer's two editions are
# started by one launcher, so both demos are in its package, brave_adventurer_modes (the
# launcher's console script replays them)
DEMO_RECIPES: dict[str, DemoRecipe] = {
    'bitmappy_drawing': DemoRecipe(
        scene='bitmappy.editor:BitmapEditorScene',
        script='scripts.demo_inputs:bitmappy_demo_script',
        frame_count=BITMAPPY_DEMO_FRAME_COUNT,
        package='bitmappy',
        name='drawing.jsonl.gz',
    ),
    'brave_adventurer_classic': DemoRecipe(
        scene='brave_adventurer.game:BraveAdventurerScene',
        script='scripts.golden_inputs:brave_adventurer_script',
        frame_count=400,
        package='brave_adventurer_modes',
        name='classic.jsonl.gz',
    ),
    'brave_adventurer_papyrus': DemoRecipe(
        scene='brave_adventurer_papyrus.game:PapyrusBraveAdventurerScene',
        script='scripts.golden_inputs:brave_adventurer_script',
        frame_count=400,
        package='brave_adventurer_modes',
        name='papyrus.jsonl.gz',
    ),
    'clockwork_keep_climb': DemoRecipe(
        scene='clockwork_keep.game:ClockworkKeepScene',
        script='scripts.golden_inputs:clockwork_keep_script',
        frame_count=330,
        package='clockwork_keep',
        name='climb.jsonl.gz',
    ),
    'drawing_fire_battle': DemoRecipe(
        scene='drawing_fire.game:DrawingFireScene',
        script='scripts.golden_inputs:drawing_fire_script',
        frame_count=1600,
        package='drawing_fire',
        name='battle.jsonl.gz',
        polled_input=True,
    ),
    'dt_demo_timing': DemoRecipe(
        scene='dt_demo:Game',
        script='scripts.demo_inputs:dt_demo_script',
        frame_count=DT_DEMO_FRAME_COUNT,
        package='dt_demo',
        name='timing.jsonl.gz',
        polled_input=True,
    ),
    'mr_muncher_chase': DemoRecipe(
        scene='mr_muncher.game:MrMuncherScene',
        script='scripts.demo_inputs:mr_muncher_demo_script',
        frame_count=MR_MUNCHER_DEMO_FRAME_COUNT,
        package='mr_muncher',
        name='chase.jsonl.gz',
    ),
    'paddleslap_rally': DemoRecipe(
        scene='paddleslap:Game',
        script='scripts.golden_inputs:paddleslap_script',
        frame_count=450,
        package='paddleslap',
        name='rally.jsonl.gz',
        input_only_placements=True,
    ),
    'text_input_demo_typing': DemoRecipe(
        scene='text_input_demo:Game',
        script='scripts.demo_inputs:text_input_demo_script',
        frame_count=TEXT_INPUT_DEMO_FRAME_COUNT,
        package='text_input_demo',
        name='typing.jsonl.gz',
    ),
}


def demo_path(*, recipe: DemoRecipe) -> Path:
    """Return where a demo's recording goes: its package's installed ``demos`` directory.

    Args:
        recipe: The demo's recipe.

    Returns:
        ``<package directory>/demos/<name>``. The package is found as the interpreter imports
        it (``importlib.util.find_spec``), which in a development install is the member's source
        directory.

    Raises:
        ModuleNotFoundError: If the recipe's package is not installed.

    """
    specification = importlib.util.find_spec(recipe.package)
    if specification is None or specification.origin is None:
        message = f'{recipe.package!r}: no installed package of that name'
        raise ModuleNotFoundError(message)
    return Path(specification.origin).parent / DEMOS_DIRECTORY_NAME / recipe.name


@contextlib.contextmanager
def recording_session_environment() -> Generator[None]:
    """Keep the AI service and every real pad away from a recording, then put the environment back.

    Sets ``GLITCHYGAMES_AI_INSTALL_ROOT`` to an empty temporary directory (removed afterwards)
    and SDL's three joystick drivers to off. On exit, even after an error, each variable has the
    value it had before, and one that was unset is unset again.

    Yields:
        Nothing: the settings are in the environment while the block runs.

    """
    names = (INSTALL_ROOT_ENVIRONMENT_VARIABLE, *SDL_JOYSTICK_DRIVER_VARIABLES)
    previous_values = {name: os.environ.get(name) for name in names}
    try:
        with tempfile.TemporaryDirectory(prefix='glitchygames-demo-ai-root-') as empty_directory:
            os.environ[INSTALL_ROOT_ENVIRONMENT_VARIABLE] = empty_directory
            for name in SDL_JOYSTICK_DRIVER_VARIABLES:
                os.environ[name] = SDL_DRIVER_OFF
            yield
    finally:
        for name, previous_value in previous_values.items():
            if previous_value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous_value


def record_demo(*, recipe: DemoRecipe) -> Path:
    """Record one bundled demo.

    Args:
        recipe: The demo's recipe.

    Returns:
        The path the recording was written to (``demo_path``).

    """
    path = demo_path(recipe=recipe)
    # A package with no demos yet has no demos directory
    path.parent.mkdir(parents=True, exist_ok=True)
    scene_class = GameSceneClasses({recipe.name: recipe.scene})[recipe.name]
    script = load_input_script(reference=recipe.script)
    with recording_session_environment():
        record_scripted_session(
            scene_class=scene_class,
            script=script,
            frame_count=recipe.frame_count,
            path=path,
            controls_tail=None,
            polled_input=recipe.polled_input,
            input_only_placements=recipe.input_only_placements,
            random_seed=RANDOM_SEED,
            stand_in_devices=recipe.stand_in_devices,
        )
    return path


def main() -> None:
    """Command line: --demo KEY or --all."""
    parser = argparse.ArgumentParser(description='Record the bundled demos through the engine')
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--demo', choices=sorted(DEMO_RECIPES), help='record one demo')
    selection.add_argument('--all', action='store_true', help='record every demo')
    arguments = parser.parse_args()
    keys = sorted(DEMO_RECIPES) if arguments.all else [arguments.demo]
    for key in keys:
        path = record_demo(recipe=DEMO_RECIPES[key])
        sys.stdout.write(f'{key}: {DEMO_RECIPES[key].frame_count} frames -> {path}\n')


if __name__ == '__main__':
    main()
