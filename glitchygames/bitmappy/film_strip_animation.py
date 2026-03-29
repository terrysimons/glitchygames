"""Film strip animation preview delegate.

This module contains animation preview methods for the FilmStripWidget,
including preview initialization, animation timing updates, frame index
calculation, and debug state dumping.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from glitchygames.bitmappy.film_strip import FilmStripWidget
    from glitchygames.sprites import SpriteFrame

LOG = logging.getLogger('game.tools.film_strip')


class FilmStripAnimation:
    """Delegate providing animation preview methods for FilmStripWidget."""

    def __init__(self, widget: FilmStripWidget) -> None:
        """Initialize the animation delegate.

        Args:
            widget: The parent FilmStripWidget instance.

        """
        self.widget = widget

    def initialize_preview_animations(self) -> None:
        """Initialize animation timing for all previews."""
        LOG.debug('FilmStripWidget: _initialize_preview_animations called')

        if not self.widget.animated_sprite:
            LOG.debug(
                'FilmStripWidget: No animated_sprite in _initialize_preview_animations, returning',
            )
            return

        LOG.debug(
            'FilmStripWidget: Initializing preview animations for '
            f'{len(self.widget.animated_sprite.animations)} animations',
        )

        for anim_name, frames in self.widget.animated_sprite.animations.items():
            LOG.debug(
                f"FilmStripWidget: Initializing animation '{anim_name}' with {len(frames)} frames",
            )
            # Initialize timing for this animation
            # For single-frame animations, start with a small time
            # offset to ensure animation advances
            if len(frames) == 1:
                # Single-frame animations need to start with a small time to ensure they advance
                # Small offset to ensure animation starts
                self.widget.preview_animation_times[anim_name] = 0.001
                LOG.debug(
                    'FilmStripWidget: Single-frame animation, setting time to 0.001',
                )
            else:
                self.widget.preview_animation_times[anim_name] = 0.0
                LOG.debug(
                    'FilmStripWidget: Multi-frame animation, setting time to 0.0',
                )
            # Normal speed
            self.widget.preview_animation_speeds[anim_name] = 1.0
            LOG.debug(
                f"FilmStripWidget: Set animation '{anim_name}' speed to 1.0",
            )

            # Extract frame durations
            frame_durations: list[float] = []
            for i, frame in enumerate(frames):
                if hasattr(frame, 'duration'):
                    frame_durations.append(frame.duration)
                    LOG.debug(
                        f'FilmStripWidget: Frame {i} duration: {frame.duration}',
                    )
                else:
                    # Default 1 second
                    frame_durations.append(1.0)
                    LOG.debug(
                        f'FilmStripWidget: Frame {i} using default duration: 1.0',
                    )
            self.widget.preview_frame_durations[anim_name] = frame_durations
            LOG.debug(
                f"FilmStripWidget: Animation '{anim_name}' frame durations: {frame_durations}",
            )

        LOG.debug('FilmStripWidget: Preview animation initialization complete')
        LOG.debug(
            'FilmStripWidget: Final preview_animation_times: '
            f'{self.widget.preview_animation_times}',
        )
        LOG.debug(
            'FilmStripWidget: Final preview_animation_speeds: '
            f'{self.widget.preview_animation_speeds}',
        )
        LOG.debug(
            'FilmStripWidget: Final preview_frame_durations: '
            f'{self.widget.preview_frame_durations}',
        )

    def update_animations(self, dt: float) -> None:
        """Update animation timing for all previews.

        This is the core method that drives the film strip preview animations.
        It advances animation timing independently for each animation, allowing
        multiple film strips to show different animations at different speeds.

        DEBUGGING NOTES:
        - If animations don't advance, check that dt > 0 and is reasonable (0.016 = 60fps)
        - If animations are choppy, verify that this method is called every frame
        - If animations loop incorrectly, check preview_animation_times calculation
        - If animations don't start, verify animated_sprite is set and has animations
        """
        if not self.widget.animated_sprite:
            return

        # Track total time for debugging
        if not hasattr(self.widget, 'debug_start_time'):
            self.widget.debug_start_time = 0.0
        if not hasattr(self.widget, 'debug_last_dump_time'):
            self.widget.debug_last_dump_time = 0.0

        self.widget.debug_start_time += dt

        # Debug dump every 5 seconds
        if (
            self.widget.debug_start_time - self.widget.debug_last_dump_time
            >= self.widget.DEBUG_DUMP_INTERVAL
        ):
            self.dump_animation_debug_state(dt)

        # Update the animated sprite with delta time to advance frames
        # This is the main animation advancement - it updates the sprite's internal
        # frame timing and current_frame property based on elapsed time
        previous_frame = self.widget.animated_sprite.current_frame
        self.widget.animated_sprite.update(dt)

        # Sync the widget's current_frame with the sprite's current_frame
        self.widget.current_frame = self.widget.animated_sprite.current_frame

        # Only mark dirty when the animation frame actually changed,
        # not every frame unconditionally
        if self.widget.animated_sprite.current_frame != previous_frame:
            self.widget.mark_dirty()

        # Update independent timing for each animation preview
        # This allows each film strip to have its own animation timing, independent
        # of the main canvas animation or other film strips
        for anim_name in self.widget.animated_sprite.animations:
            if anim_name not in self.widget.preview_animation_times:
                continue
            # Update animation time based on delta time and animation speed
            # This creates smooth, frame-rate independent animation timing
            speed = self.widget.preview_animation_speeds[anim_name]
            self.widget.preview_animation_times[anim_name] += dt * speed

            # Get total duration of this animation
            # This is the sum of all frame durations in the animation
            total_duration = sum(self.widget.preview_frame_durations.get(anim_name, [1.0]))

            # Loop animation time continuously (no pause)
            # This ensures animations loop seamlessly without gaps
            if total_duration > 0:
                self.widget.preview_animation_times[anim_name] %= total_duration

    def get_current_preview_frame(self, anim_name: str) -> int:
        """Get the current frame index for a preview animation.

        This method calculates which frame should be displayed based on the
        current animation time. It's used by the rendering system to show
        the correct frame in the film strip preview.

        DEBUGGING NOTES:
        - If wrong frames are shown, check that preview_animation_times is advancing
        - If frames don't change, verify update_animations() is being called
        - If animations skip frames, check frame_durations are correct
        - If animations don't loop, verify total_duration calculation

        Returns:
            int: The current preview frame.

        """
        if (
            anim_name not in self.widget.preview_animation_times
            or anim_name not in self.widget.preview_frame_durations
        ):
            return 0

        current_time = self.widget.preview_animation_times[anim_name]
        frame_durations = self.widget.preview_frame_durations[anim_name]

        # CRITICAL: Add bounds checking to prevent invalid frame indices
        if not frame_durations or len(frame_durations) == 0:
            LOG.error(
                f"FilmStripWidget: CRITICAL - No frame durations for animation '{anim_name}'",
            )
            return 0

        # Find which frame we should be showing during animation
        # This implements frame-based animation timing where each frame
        # has a specific duration, and we find which frame corresponds
        # to the current animation time
        accumulated_time = 0.0
        for frame_idx, duration in enumerate(frame_durations):
            if current_time <= accumulated_time + duration:
                # Ensure the frame index is within bounds
                if frame_idx >= len(frame_durations):
                    LOG.error(
                        'FilmStripWidget: CRITICAL - Frame index '
                        f'{frame_idx} out of bounds for '
                        f'{len(frame_durations)} frames',
                    )
                    return max(0, len(frame_durations) - 1)
                return frame_idx
            accumulated_time += duration

        # Fallback to last frame
        # This should rarely happen due to the modulo operation in update_animations
        return max(0, len(frame_durations) - 1)

    @staticmethod
    def get_stale_frame_surface(frame: SpriteFrame) -> pygame.Surface | None:
        """Build a surface from pixel data when the cached image is stale.

        Returns:
            A new surface from pixel data, or None if the image is not stale.

        """
        if not (
            hasattr(frame, '_image_stale')
            and getattr(frame, '_image_stale', False)
            and hasattr(frame, 'pixels')
            and frame.pixels
        ):
            return None

        pixel_data = frame.pixels
        if not pixel_data:
            return None

        # Get dimensions from existing image if available, or calculate from pixels
        if hasattr(frame, 'image') and frame.image:
            width, height = frame.image.get_size()
        else:
            total_pixels = len(pixel_data)
            try:
                width, height = frame.get_size()
            except AttributeError, TypeError:
                # Last resort: assume square (not ideal but prevents crash)
                width = height = int(math.sqrt(total_pixels))

        frame_surface = pygame.Surface((width, height), pygame.SRCALPHA)
        for i, color in enumerate(pixel_data):
            if i < width * height:
                x = i % width
                y = i // width
                frame_surface.set_at((x, y), color)
        return frame_surface

    @staticmethod
    def get_frame_image(frame: SpriteFrame) -> pygame.Surface | None:
        """Get the image surface for a frame.

        Returns:
            pygame.Surface: The frame image.

        """
        # If frame.image is marked as stale (during drag), prefer pixels over cached image
        # This ensures film strip sees real-time updates during drag operations
        stale_surface = FilmStripAnimation.get_stale_frame_surface(frame)
        if stale_surface is not None:
            return stale_surface

        # Normal path: use cached image if available
        if hasattr(frame, 'image') and frame.image:
            return frame.image

        # Fallback: Create a surface from the frame's pixel data
        if hasattr(frame, 'get_pixel_data'):
            pixel_data = frame.get_pixel_data()
            if pixel_data:
                # Get the actual frame dimensions
                width, height = frame.get_size()

                # Create a surface with alpha support from the pixel data
                frame_surface = pygame.Surface((width, height), pygame.SRCALPHA)
                for i, color in enumerate(pixel_data):
                    x = i % width
                    y = i // width
                    frame_surface.set_at((x, y), color)
                return frame_surface

        return None

    def dump_animation_debug_state(self, dt: float) -> None:
        """Dump animation state for debugging (called periodically)."""
        LOG.debug('=' * 80)
        LOG.debug(
            f'FILM STRIP ANIMATION STATE DUMP AT {self.widget.debug_start_time:.1f} SECONDS',
        )
        LOG.debug('=' * 80)
        LOG.debug('FilmStripWidget debug info:')
        LOG.debug(f'  _debug_start_time: {self.widget.debug_start_time}')
        LOG.debug(f'  dt: {dt}')
        LOG.debug(f'  animated_sprite: {self.widget.animated_sprite}')
        LOG.debug(f'  current_animation: {self.widget.current_animation}')
        LOG.debug(f'  current_frame: {self.widget.current_frame}')
        LOG.debug(f'  scroll_offset: {self.widget.scroll_offset}')
        LOG.debug(
            f'  _force_redraw: {getattr(self.widget, "_force_redraw", False)}',
        )
        LOG.debug(
            f'  preview_animation_times: {getattr(self.widget, "preview_animation_times", {})}',
        )
        LOG.debug(
            f'  preview_animation_speeds: {getattr(self.widget, "preview_animation_speeds", {})}',
        )
        LOG.debug(
            f'  preview_frame_durations: {getattr(self.widget, "preview_frame_durations", {})}',
        )

        if self.widget.animated_sprite:
            self.dump_animated_sprite_debug()

        LOG.debug('=' * 80)
        self.widget.debug_last_dump_time = self.widget.debug_start_time

    def dump_animated_sprite_debug(self) -> None:
        """Dump animated sprite debug info."""
        assert self.widget.animated_sprite is not None
        sprite = self.widget.animated_sprite
        LOG.debug('AnimatedSprite debug info:')
        LOG.debug(
            f'  current_animation: {getattr(sprite, "current_animation", "None")}',
        )
        LOG.debug(f'  current_frame: {getattr(sprite, "current_frame", "None")}')
        LOG.debug(f'  is_playing: {getattr(sprite, "is_playing", "None")}')
        LOG.debug(f'  is_looping: {getattr(sprite, "is_looping", "None")}')
        LOG.debug(f'  _is_playing: {getattr(sprite, "_is_playing", "None")}')
        LOG.debug(f'  _is_looping: {getattr(sprite, "_is_looping", "None")}')
        LOG.debug(f'  _frame_timer: {getattr(sprite, "_frame_timer", "None")}')
        LOG.debug(f'  _animations: {getattr(sprite, "_animations", {})}')
        LOG.debug(
            f'  _animation_order: {getattr(sprite, "_animation_order", [])}',
        )
        LOG.debug(
            '  frame_manager.current_animation: '
            f'{getattr(sprite.frame_manager, "current_animation", "None")}',
        )
        LOG.debug(
            '  frame_manager.current_frame: '
            f'{getattr(sprite.frame_manager, "current_frame", "None")}',
        )

        # Dump animation details
        if hasattr(sprite, 'animations') and sprite.animations:
            for anim_name, frames in sprite.animations.items():
                LOG.debug(f"  Animation '{anim_name}':")
                LOG.debug(f'    frame count: {len(frames)}')
                for i, frame in enumerate(frames):
                    LOG.debug(
                        f'    frame {i}: '
                        f'duration={getattr(frame, "duration", "None")}, '
                        f'image={getattr(frame, "image", "None")}',
                    )

        # Dump frame manager state
        if hasattr(sprite, 'frame_manager'):
            frame_mgr = sprite.frame_manager
            LOG.debug('  FrameManager debug info:')
            LOG.debug(
                f'    _current_animation: {getattr(frame_mgr, "_current_animation", "None")}',
            )
            LOG.debug(
                f'    _current_frame: {getattr(frame_mgr, "_current_frame", "None")}',
            )
            LOG.debug(f'    _observers: {getattr(frame_mgr, "_observers", [])}')
