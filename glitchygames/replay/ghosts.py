"""Ghosts: one sprite's recorded path and looks, drawn beside live play (a time-trial ghost).

A ghost is appearance, not play (plans/2026-10-19-gameplay-replay.md, section 5.5). The rules:

1. Recording: ``GhostRecorder(sprite=..., scene=...)`` is a supervisor
   (glitchygames/supervision.py); it registers itself with ``SceneManager().add_supervisor``
   as it is made and removes itself in ``finish()``, which returns the ``GhostTrack``. At each
   frame's supervisor slot (after the frame's logic and events, before the camera aim and
   positioning) it keeps one ``GhostSample``: the scene's ``game_time``, the sprite's
   ``world_x``/``world_y``, its ``appearance(sprite)`` (``default_appearance``: animation,
   frame, horizontal flip and draw offset of an ``AnimatedSprite``; kept as a read-only copy)
   and whether the game shows it (``not hidden`` for a world-space sprite: its ``visible`` is
   the engine's culling, which says where the camera was, not whether the sprite was shown;
   ``visible`` for any other sprite).
2. Only live frames of its scene are sampled: frames whose active scene is the ``scene`` it was
   given (another scene has its own game time), in which that scene's game time advanced (not
   behind the pause screen, not the frame a resume switches back to it), and never inside a
   playback scope (a demo or an instant replay plays a rebuilt scene;
   glitchygames/replay/playback.py). A recorder made while a scope plays (by the rebuilt
   scene's ``setup()``, say) belongs to the scope: the scene manager removes it when the scope
   ends (glitchygames/supervision.py), and it samples nothing. The recorder reads game state
   only: it draws no randomness, posts no event and records no control event, so recording a
   ghost changes nothing a ``--record-trace`` recording holds or a replay compares.
3. Timing: samples are keyed by ``Scene.game_time``, the sum of the scene's (capped) dt since
   it started, which stops while the scene is paused. A ghost drawn in a later run of the same
   scene shows, at each moment, the last sample not after that run's ``game_time``
   (``GhostTrack.sample_at``), so it lines up with the live run from the scene's start
   whatever the frame rate, and stands still while the game is paused. With the same dt every
   frame, the ghost is drawn exactly where the recorded sprite was drawn.
4. Storing: ``GhostTrack.to_json()`` / ``from_json()`` (frozen pydantic models; unknown fields
   are refused). The game stores tracks, typically in its saves (``glitchygames.state.
   open_saves``): a replay serves the saves the recording saw (a sandbox), so the replayed
   ghost is the recorded one. A track read from anywhere else must be the same file when the
   session is replayed.
5. Drawing: ``GhostSprite(track=..., image_for=...)`` is a world-space sprite
   (``COORDINATE_SPACE = CoordinateSpace.WORLD``): the engine positions and culls it like any
   world sprite and is the only writer of its rect's position. The game sets ``ghost.scene``
   to the scene it adds the ghost to (whose ``game_time`` it follows) and adds it to the
   scene's ``all_sprites``. Its ``world_x``, ``world_y`` and ``draw_offset`` are read from
   the track at the scene's current ``game_time`` whenever they are read, and that read
   brings its image and rect size up to date, so the engine's positioning (which runs before
   ``update()``) places and culls this frame's sample, never the last frame's. Its image is
   ``image_for(sample)`` as a translucent copy (``alpha``), made once per distinct appearance
   (keyed by the appearance's JSON), and the rect takes its size (its top-left stays the
   engine's). With nothing to show (no scene, before the track's first sample, or a sample
   that is not visible) its image is empty (0 x 0), which the engine's culling hides
   (``visible`` 0). ``hidden`` is the game's own flag only, as for every world sprite (set
   ``hidden = True`` to hide it, never ``visible = False``), so saving and restoring it is
   safe. It has no hitbox: never add it to a collision group.
6. In traces: a ghost in ``all_sprites`` is sampled like every sprite (its rect and
   ``visible``), and it is deterministic: its track comes from saves (rule 4) and its position
   from the replayed ``game_time``, so a session with a ghost replays without divergence.
   Inside an instant replay the rebuilt scene adds its own ghost as the live scene did (from
   the sandboxed saves), following its own ``game_time``.
"""

from __future__ import annotations

import bisect
import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Protocol, Self, cast, override

import pygame
from pydantic import BaseModel, ConfigDict, field_serializer, field_validator, model_validator

from glitchygames.scenes import SceneManager
from glitchygames.sprites.animated import AnimatedSprite
from glitchygames.supervision import frozen_json_value, thawed_json_value
from glitchygames.world import CoordinateSpace, is_world_positioned

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.scenes import Scene
    from glitchygames.world import WorldPositioned

# How opaque a ghost is drawn by default (0 transparent, 255 opaque)
DEFAULT_GHOST_ALPHA = 96


class GhostSample(BaseModel):
    """Where and how the recorded sprite was drawn at one moment of its scene's game time."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    # Scene.game_time when the sample was taken (after that frame's logic)
    game_seconds: float
    world_x: float
    world_y: float
    # JSON-safe; default_appearance's keys unless the recorder was given another function.
    # Kept read-only (mappings read-only, lists as tuples): its JSON keys a ghost's image cache
    appearance: Mapping[str, Any]
    # Whether the game showed the sprite (not hidden); the ghost draws nothing when False
    visible: bool

    @field_validator('appearance', mode='before')
    @classmethod
    def _appearance_is_a_mapping(cls, appearance: object) -> object:
        """Refuse an appearance that is not a mapping, naming what an appearance must be.

        A custom ``appearance`` function (GhostRecorder) is the usual source of a wrong value.

        Returns:
            The appearance, for pydantic's own validation.

        Raises:
            ValueError: If the appearance is not a mapping.

        """
        if isinstance(appearance, Mapping):
            return cast('Mapping[str, Any]', appearance)
        message = (
            f'A ghost appearance must be a mapping of JSON values, got {type(appearance).__name__}'
        )
        # A ValueError, not a TypeError: pydantic turns only ValueError (and AssertionError)
        # raised by a validator into a ValidationError
        raise ValueError(message)

    @field_validator('appearance', mode='after')
    @classmethod
    def _read_only_appearance(cls, appearance: Mapping[str, Any]) -> Mapping[str, Any]:
        """Keep a read-only copy of the appearance given, so nobody can change it later.

        Pydantic validates a ``Mapping`` field into a new dict, so the copy is made after it.

        Returns:
            The read-only copy.

        """
        return frozen_json_value(appearance)

    @field_serializer('appearance')
    def _plain_appearance(self: Self, appearance: Mapping[str, Any]) -> dict[str, Any]:
        """Write the appearance as plain JSON types (dicts and lists).

        Returns:
            The plain copy.

        """
        return thawed_json_value(appearance)


class GhostTrack(BaseModel):
    """A recorded sprite's samples, in game-time order."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    samples: tuple[GhostSample, ...]

    @model_validator(mode='after')
    def _check_time_order(self: Self) -> Self:
        """Refuse samples whose game times go backwards (sample_at searches them).

        Returns:
            The track.

        Raises:
            ValueError: If a sample's game time is earlier than the one before it.

        """
        for earlier, later in zip(self.samples, self.samples[1:], strict=False):
            if later.game_seconds < earlier.game_seconds:
                message = (
                    f'Ghost samples must be in time order: {later.game_seconds} follows '
                    f'{earlier.game_seconds}'
                )
                raise ValueError(message)
        return self

    def sample_at(self: Self, *, game_seconds: float) -> GhostSample | None:
        """Return the last sample taken at or before a game time.

        Args:
            game_seconds: The game time of the scene the ghost is drawn in.

        Returns:
            The sample, or None before the first sample (or for an empty track).

        """
        index = bisect.bisect_right(
            self.samples, game_seconds, key=lambda sample: sample.game_seconds
        )
        if index == 0:
            return None
        return self.samples[index - 1]

    def to_json(self: Self) -> dict[str, Any]:
        """Return the track as plain JSON types (for saves).

        Returns:
            ``{'samples': [...]}``, each sample a dict of its fields.

        """
        return self.model_dump(mode='json')

    @classmethod
    def from_json(cls, record: dict[str, Any]) -> GhostTrack:
        """Read a track written by ``to_json``.

        Args:
            record: The JSON record.

        Returns:
            The track.

        """
        return cls.model_validate(record)


def default_appearance(sprite: object) -> dict[str, Any]:
    """Return what a ghost needs to draw an ``AnimatedSprite`` as it looks now.

    Args:
        sprite: The recorded sprite.

    Returns:
        For an ``AnimatedSprite``: its ``animation`` name, ``frame`` index, ``flip_x``
        (``hitbox_flip_x``, set by games that draw it facing left) and ``draw_offset`` (its
        frame anchor's offset, as a list). For any other sprite: ``{}``.

    """
    if not isinstance(sprite, AnimatedSprite):
        return {}
    draw_offset_x, draw_offset_y = sprite.draw_offset
    return {
        'animation': sprite.current_animation,
        'frame': sprite.current_frame,
        'flip_x': bool(sprite.hitbox_flip_x),
        'draw_offset': [draw_offset_x, draw_offset_y],
    }


def images_from_animated_sprite(source: AnimatedSprite) -> Callable[[GhostSample], pygame.Surface]:
    """Return an ``image_for`` that draws a sample with an animated sprite's frames.

    The image is the frame the sample names (``default_appearance``'s ``animation`` and
    ``frame``), flipped horizontally when its ``flip_x`` is true. It is the frame as authored:
    a game that draws its sprite scaled or recoloured passes its own ``image_for``.

    Args:
        source: A sprite with the recorded sprite's animations (the same TOML, say).

    Returns:
        The function a ``GhostSprite`` draws its image with.

    """

    def image_for(sample: GhostSample) -> pygame.Surface:
        """Return the sampled frame's image.

        Returns:
            The frame's surface (a flipped copy when the sample is flipped).

        """
        appearance = sample.appearance
        frames = source.frames[str(appearance['animation'])]
        image = frames[int(appearance['frame'])].image
        if appearance.get('flip_x', False):
            return pygame.transform.flip(image, flip_x=True, flip_y=False)
        return image

    return image_for


class GhostRecorder:
    """A supervisor that samples one sprite once per live frame of its scene (module rules 1-2)."""

    def __init__(
        self: Self,
        *,
        sprite: WorldPositioned,
        scene: Scene,
        appearance: Callable[[object], dict[str, Any]] = default_appearance,
    ) -> None:
        """Start recording ``sprite``: register with the scene manager's supervisor slot.

        Args:
            sprite: The sprite to record (it has world_x and world_y).
            scene: The scene the sprite plays in: only its frames are sampled, keyed by its
                game time.
            appearance: Returns the JSON-safe looks of the sprite for each sample.

        """
        self._sprite = sprite
        self._scene = scene
        self._appearance = appearance
        self._samples: list[GhostSample] = []
        self._track: GhostTrack | None = None
        SceneManager().add_supervisor(supervisor=self)

    def on_frame(self: Self, *, frame_number: int, scene: Scene | None) -> None:
        """Sample the sprite, if this frame ran the recorded scene's logic live.

        Args:
            frame_number: The frame being run (unused: samples are keyed by game time).
            scene: The active scene at the supervisor slot.

        """
        del frame_number
        # A supervisor earlier in the slot may have finished this recorder this frame
        if self._track is not None or scene is not self._scene:
            return
        if SceneManager().playback_session is not None:
            return
        game_seconds = self._scene.game_time
        if self._samples and game_seconds <= self._samples[-1].game_seconds:
            return
        sprite = self._sprite
        if is_world_positioned(sprite):
            shown = not getattr(sprite, 'hidden', False)
        else:
            shown = bool(getattr(sprite, 'visible', True))
        self._samples.append(
            GhostSample(
                game_seconds=game_seconds,
                world_x=sprite.world_x,
                world_y=sprite.world_y,
                appearance=self._appearance(sprite),
                visible=shown,
            )
        )

    def finish(self: Self) -> GhostTrack:
        """Stop recording: leave the supervisor slot and return the track (the same each call).

        Returns:
            The recorded track.

        """
        if self._track is None:
            SceneManager().remove_supervisor(supervisor=self)
            self._track = GhostTrack(samples=tuple(self._samples))
        return self._track


class GameTimed(Protocol):
    """What a ghost reads of the scene it is drawn in."""

    @property
    def game_time(self) -> float:
        """The scene's game time in seconds (Scene.game_time)."""
        ...


class GhostSprite(pygame.sprite.DirtySprite):
    """A translucent world-space sprite that plays a ``GhostTrack`` (module rules 3, 5 and 6).

    Set ``scene`` to the scene the ghost is added to; until then it draws nothing.
    """

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(
        self: Self,
        *,
        track: GhostTrack,
        image_for: Callable[[GhostSample], pygame.Surface],
        alpha: int = DEFAULT_GHOST_ALPHA,
    ) -> None:
        """Create a ghost with no image yet; it draws once its scene reaches the first sample.

        Args:
            track: The recorded track.
            image_for: Returns the image for a sample (``images_from_animated_sprite``); called
                once per distinct appearance.
            alpha: How opaque the ghost is drawn (0-255).

        """
        super().__init__()
        self.scene: GameTimed | None = None
        self._track = track
        self._image_for = image_for
        self._alpha = alpha
        # The game's own flag, as for every world sprite (the engine's culling reads it)
        self.hidden = False
        # The scene and game time the current sample was looked up for
        self._looked_up_for: tuple[GameTimed, float] | None = None
        self._sample: GhostSample | None = None
        # The JSON of the appearance drawn, or None while the empty image is shown
        self._drawn_appearance: str | None = None
        self._images_by_appearance: dict[str, pygame.Surface] = {}
        self._empty_image = pygame.Surface((0, 0))
        self.image = self._empty_image
        self.rect = self._empty_image.get_rect()

    def _current_sample(self: Self) -> GhostSample | None:
        """Return the sample for the scene's current game time, showing its image.

        Returns:
            The sample, or None without a scene or before the track's first sample.

        """
        scene = self.scene
        if scene is None:
            self._sample = None
            self._looked_up_for = None
            self._show_image(appearance_key=None, sample=None)
            return None
        game_seconds = scene.game_time
        looked_up_for = self._looked_up_for
        if (
            looked_up_for is not None
            and looked_up_for[0] is scene
            and looked_up_for[1] == game_seconds
        ):
            return self._sample
        self._looked_up_for = (scene, game_seconds)
        sample = self._track.sample_at(game_seconds=game_seconds)
        self._sample = sample
        if sample is None or not sample.visible:
            self._show_image(appearance_key=None, sample=None)
        else:
            appearance_key = json.dumps(thawed_json_value(sample.appearance), sort_keys=True)
            self._show_image(appearance_key=appearance_key, sample=sample)
        return sample

    def _show_image(self: Self, *, appearance_key: str | None, sample: GhostSample | None) -> None:
        """Show a sample's image, made translucent once per appearance, or the empty image.

        Args:
            appearance_key: The JSON of the sample's appearance, or None for the empty image.
            sample: The sample to draw (None for the empty image).

        """
        if appearance_key == self._drawn_appearance:
            return
        if appearance_key is None or sample is None:
            image = self._empty_image
        else:
            cached_image = self._images_by_appearance.get(appearance_key)
            if cached_image is None:
                cached_image = self._image_for(sample).copy()
                cached_image.set_alpha(self._alpha)
                self._images_by_appearance[appearance_key] = cached_image
            image = cached_image
        self._drawn_appearance = appearance_key
        self.image = image
        # The size follows the image; the engine owns the position (rect.topleft)
        rect = self.rect
        assert rect is not None  # made in __init__
        rect.size = image.get_size()
        if self.dirty == 0:
            self.dirty = 1

    @property
    def world_x(self: Self) -> float:
        """World X of the sample at the scene's game time (0.0 without one)."""
        sample = self._current_sample()
        return 0.0 if sample is None else sample.world_x

    @property
    def world_y(self: Self) -> float:
        """World Y of the sample at the scene's game time (0.0 without one)."""
        sample = self._current_sample()
        return 0.0 if sample is None else sample.world_y

    @property
    def draw_offset(self: Self) -> tuple[int, int]:
        """The sample's ``draw_offset`` appearance (a frame anchor's offset), else (0, 0)."""
        sample = self._current_sample()
        if sample is None or 'draw_offset' not in sample.appearance:
            return (0, 0)
        draw_offset_x, draw_offset_y = sample.appearance['draw_offset']
        return (int(draw_offset_x), int(draw_offset_y))

    @override
    def update(self: Self) -> None:
        """Bring the image up to the scene's game time (the properties are always current)."""
        self._current_sample()

    def update_nested_sprites(self: Self) -> None:
        """Do nothing: Scene.update() calls this on every sprite, and a ghost has none."""
