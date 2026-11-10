"""Two engines with different options, side by side in two engine contexts.

The engine-level counterpart of tests/test_engine_context.py's
``test_two_contexts_hold_two_games_worth_of_state_without_leaking`` (sub-plan 1): two stand-in
games started with different options, stepped in turn, each in its own context, read exactly what
each reads alone (plans/2026-10-27-engine-context-2-engine-state.md, Task 15; the spike's open
question 1). Each reading names its row of the plan's audit (C7-C20). C16 (Bitmappy's controller
manager) is a member's, never imported here; C17 (the unhandled event types logged once under
``--debug-events``) has no reading: its effect is a warning, covered by its collision test and its
isolation check. The steps process events, not frames: a frame step outside its context is
sub-plan 3's, an inner engine sub-plan 7's.
"""

from __future__ import annotations

from typing import Literal

import pygame
from pydantic import BaseModel, ConfigDict

from glitchygames.engine import GameEngine
from glitchygames.engine.game_engine import current_engine
from glitchygames.engine_context import EngineContext
from glitchygames.events.mouse import MouseEventManager
from glitchygames.fonts import FontManager
from glitchygames.performance import AdaptiveClamping
from glitchygames.recording import pending_internal_posts, post_event
from glitchygames.scenes import SceneManager
from glitchygames.sources import install_sources, reset_sources
from glitchygames.sprites import Singleton, Sprite
from glitchygames.sprites.sprite import sprite_counters
from tests.events.test_events_integration import (
    AudioAndControllerRecordingScene,
    ScriptedBatchSources,
    start_engine_with_scene,
)

# Steps each run plays: more than one, so a later step reads what an earlier one left
STEP_COUNT = 3
# The FPS each step's performance sample records
TRACKED_FPS = 60.0
# The sprite each step makes
STEP_SPRITE_WIDTH = 2
STEP_SPRITE_HEIGHT = 1


class FirstStandInScene(AudioAndControllerRecordingScene):
    """The first run's game: a class of its own, so the two runs' game classes differ."""


class SecondStandInScene(AudioAndControllerRecordingScene):
    """The second run's game: a class of its own, so the two runs' game classes differ."""


class StandInRun(BaseModel):
    """One stand-in game's run: its game, options and what it does in its context."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    # The game (a stand-in subclass of AudioAndControllerRecordingScene of its own)
    scene_class: type[AudioAndControllerRecordingScene]
    # The command line's arguments beyond start_engine_with_scene's
    arguments: tuple[str, ...]
    # The font system the run's context sets (C13)
    font_system: Literal['pygame', 'freetype']
    # The scene name the run's performance manager tracks (C14)
    scene_name: str
    # The audio device each step's event names (C10)
    audio_device: int
    # The on_*_event name each step looks up and misses on the engine (C11)
    missing_handler: str
    # The label of the run's singleton (C15)
    singleton_label: str


class EngineReadings(BaseModel):
    """What one step of a run reads, one field per row of the plan's audit."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    # C8: the engine's own options
    target_fps: float
    # C7: the copy of the engine's options held by the context's scene manager
    manager_target_fps: float
    # C9: the engine's game class
    game_class_name: str
    # C20: the game's class keeps no options of its own (they would be the last engine's)
    game_class_keeps_no_options: bool
    # C10: the audio devices of every event the run's scene received, in order
    event_reached_own_scene: tuple[int, ...]
    # C11: the on_*_event names the engine missed
    missing_events: tuple[str, ...]
    # C12: the shared mouse manager is the engine's own
    shared_mouse_manager_is_own: bool
    # C13: the font system
    font_system: str
    # C14: each scene the performance manager tracks, with its sample count
    performance_scenes: tuple[tuple[str, int], ...]
    # C15: the run's singleton kept its label since the run's last constructor call, and
    # Singleton(...) answers with it (identity alone is no proof: a shared singleton would be
    # every run's own)
    singleton_is_own: bool
    # C18: the sprites counted
    sprite_count: int
    # C19: the internal posts no pump has returned yet, at the step's start (the run's previous
    # step's post; a pump forgets every pending post, so read after it the count says nothing)
    pending_post_count: int
    # GameEngine.OPTIONS, the view of the current context's engine's options
    view_target_fps: float | None
    # Sprite.SPRITE_COUNT, the view of the current context's sprite count
    view_sprite_count: int
    # current_engine() answers with the run's own engine
    current_engine_is_own: bool


def set_up_run(
    *, run: StandInRun
) -> tuple[GameEngine, AudioAndControllerRecordingScene, Singleton]:
    """Start a run's engine in the current context, as its game's start would.

    Args:
        run: The run.

    Returns:
        The engine, its active scene and the run's singleton.

    """
    engine, scene = start_engine_with_scene(
        scene_class=run.scene_class, extra_arguments=[*run.arguments, '--no-unhandled-events']
    )
    assert isinstance(scene, AudioAndControllerRecordingScene)
    engine.scene_manager.game_engine = engine
    FontManager.set_font_system(font_system=run.font_system)
    AdaptiveClamping().set_current_scene(scene_name=run.scene_name)
    singleton = Singleton(run.singleton_label)
    return engine, scene, singleton


def performance_scenes() -> tuple[tuple[str, int], ...]:
    """Return each scene the current context's performance manager reports, with its samples.

    Returns:
        (scene name, FPS samples) per scene the shutdown report names, in the order the manager
        first tracked them (0 for a scene with none: its report is a message).

    """
    return tuple(
        (scene_name, statistics.get('total_frames', 0))
        for scene_name, statistics in AdaptiveClamping().get_per_scene_shutdown_stats().items()
    )


def play_step(
    *,
    run: StandInRun,
    engine: GameEngine,
    scene: AudioAndControllerRecordingScene,
    singleton: Singleton,
) -> EngineReadings:
    """Play one step of a run in the current context, touching every row's state.

    Args:
        run: The run.
        engine: The run's engine.
        scene: The run's active scene.
        singleton: The run's singleton.

    Returns:
        What the step read.

    """
    # Read before anything constructs a Singleton or pumps: a Singleton() call sets the
    # instance's args, and a pump forgets every pending post (recording.forget_pending_posts)
    singleton_kept_its_label = singleton.args == (run.singleton_label,)
    pending_post_count = len(pending_internal_posts())
    install_sources(
        sources=ScriptedBatchSources(
            batch=[pygame.event.Event(pygame.AUDIODEVICEADDED, which=run.audio_device, iscapture=0)]
        )
    )
    engine.process_events()
    getattr(engine, run.missing_handler)()
    AdaptiveClamping().track_fps_from_event(fps=TRACKED_FPS)
    post_event(event=pygame.event.Event(pygame.USEREVENT))
    # Leave SDL's queue empty: the post's tracker entry stays pending in this context until this
    # run's next pump (the next step's pending_post_count reads it)
    pygame.event.get(eventtype=pygame.USEREVENT)
    Sprite(x=0, y=0, width=STEP_SPRITE_WIDTH, height=STEP_SPRITE_HEIGHT)
    view_options = GameEngine.OPTIONS
    return EngineReadings(
        target_fps=engine.options['target_fps'],
        manager_target_fps=SceneManager().engine_options['target_fps'],
        game_class_name=engine.game.__name__,
        game_class_keeps_no_options='options' not in vars(run.scene_class),
        event_reached_own_scene=tuple(event.which for event in scene.audio_events_received),
        missing_events=tuple(engine.missing_events),
        shared_mouse_manager_is_own=MouseEventManager() is engine.mouse_manager,
        font_system=FontManager.get_font_system(),
        performance_scenes=performance_scenes(),
        # Constructed with the label again, so the next step finds it kept
        singleton_is_own=singleton_kept_its_label and Singleton(run.singleton_label) is singleton,
        sprite_count=sprite_counters().count,
        pending_post_count=pending_post_count,
        view_target_fps=None if view_options is None else view_options['target_fps'],
        view_sprite_count=Sprite.SPRITE_COUNT,
        current_engine_is_own=current_engine() is engine,
    )


def run_alone(*, run: StandInRun, step_count: int) -> list[EngineReadings]:
    """Play a run's steps alone, in a fresh context of its own.

    Args:
        run: The run.
        step_count: The steps to play.

    Returns:
        Each step's readings.

    """
    with EngineContext(name=f'{run.scene_name} alone').active():
        engine, scene, singleton = set_up_run(run=run)
        readings = [
            play_step(run=run, engine=engine, scene=scene, singleton=singleton)
            for _step in range(step_count)
        ]
        reset_sources()
    return readings


def run_side_by_side(*, runs: list[StandInRun], step_count: int) -> list[list[EngineReadings]]:
    """Set up every run in a context of its own, then play a step of each in turn.

    Args:
        runs: The runs.
        step_count: The steps each run plays.

    Returns:
        Each run's readings, step by step.

    """
    contexts = [EngineContext(name=run.scene_name) for run in runs]
    started: list[tuple[GameEngine, AudioAndControllerRecordingScene, Singleton]] = []
    for run, context in zip(runs, contexts, strict=True):
        with context.active():
            started.append(set_up_run(run=run))
    readings: list[list[EngineReadings]] = [[] for _run in runs]
    for _step in range(step_count):
        for run, context, (engine, scene, singleton), run_readings in zip(
            runs, contexts, started, readings, strict=True
        ):
            with context.active():
                run_readings.append(
                    play_step(run=run, engine=engine, scene=scene, singleton=singleton)
                )
    for context in contexts:
        with context.active():
            reset_sources()
    return readings


def test_two_engines_with_different_options_side_by_side_read_what_each_reads_alone():
    """Two engines started with different options, stepped in turn, read what each reads alone."""
    runs = [
        StandInRun(
            scene_class=FirstStandInScene,
            arguments=('--target-fps', '30'),
            font_system='freetype',
            scene_name='First',
            audio_device=1,
            missing_handler='on_first_missing_event',
            singleton_label='first',
        ),
        StandInRun(
            scene_class=SecondStandInScene,
            arguments=('--target-fps', '50'),
            font_system='pygame',
            scene_name='Second',
            audio_device=2,
            missing_handler='on_second_missing_event',
            singleton_label='second',
        ),
    ]
    alone = [run_alone(run=run, step_count=STEP_COUNT) for run in runs]
    side_by_side = run_side_by_side(runs=runs, step_count=STEP_COUNT)

    assert side_by_side == alone
    assert alone[0] != alone[1]
    # C20 is a fact about each game's class, the same in every reading: it must hold
    assert all(
        reading.game_class_keeps_no_options for run_readings in alone for reading in run_readings
    )
    # The per-run fields differ between the two runs at every step, field by field, so a field
    # that always reads the same value (state shared by both runs) cannot pass unnoticed
    per_run_fields = (
        'game_class_name',  # C9
        'event_reached_own_scene',  # C10
        'missing_events',  # C11
        'font_system',  # C13
        'performance_scenes',  # C14
    )
    for first_reading, second_reading in zip(alone[0], alone[1], strict=True):
        assert [
            field_name
            for field_name in per_run_fields
            if getattr(first_reading, field_name) == getattr(second_reading, field_name)
        ] == []
