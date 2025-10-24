#!/usr/bin/env python3
"""Onion skinning renderer for canvas rendering.

This module provides rendering functionality for onion skinning frames
in the bitmappy canvas system.
"""

import logging
import pygame
from typing import Dict, Any

LOG = logging.getLogger("game.tools.onion_skinning_renderer")
LOG.addHandler(logging.NullHandler())


def render_onion_skinning_frames(canvas_sprite, current_animation: str, current_frame: int, frames: Dict[str, Any]) -> None:
    """Render onion skinning frames with transparency on the canvas.
    
    Args:
        canvas_sprite: The canvas sprite to render on
        current_animation: Name of the current animation
        current_frame: Index of the current frame
        frames: Dictionary of animation frames
    """
    try:
        from .onion_skinning import get_onion_skinning_manager
        
        onion_manager = get_onion_skinning_manager()
        
        # Get all frames that should be onion skinned
        onion_frames = onion_manager.get_onion_skinned_frames(current_animation, current_frame)
        
        LOG.debug(f"Onion skinning renderer called: animation={current_animation}, frame={current_frame}, onion_frames={onion_frames}")
        
        if not onion_frames:
            LOG.debug("No onion skinning frames to render")
            return  # No onion skinning frames to render
        
        # Create a temporary surface for onion frames
        onion_surface = pygame.Surface((
            canvas_sprite.width,
            canvas_sprite.height,
        ), pygame.SRCALPHA)
        
        # Render each onion frame with transparency
        LOG.debug(f"Rendering {len(onion_frames)} onion frames with transparency {onion_manager.onion_transparency}")
        for frame_idx in onion_frames:
            if frame_idx < len(frames[current_animation]):
                frame = frames[current_animation][frame_idx]
                LOG.debug(f"Rendering onion frame {frame_idx}")
                
                if hasattr(frame, "get_pixel_data"):
                    frame_pixels = frame.get_pixel_data()
                else:
                    frame_pixels = getattr(
                        frame,
                        "pixels",
                        [(255, 0, 255)] * (canvas_sprite.pixels_across * canvas_sprite.pixels_tall),
                    )
                
                # Draw each pixel with transparency
                for i, pixel in enumerate(frame_pixels):
                    x = (i % canvas_sprite.pixels_across) * canvas_sprite.pixel_width
                    y = (i // canvas_sprite.pixels_across) * canvas_sprite.pixel_height
                    
                    # Create semi-transparent pixel
                    alpha = int(255 * onion_manager.onion_transparency)
                    transparent_pixel = (*pixel, alpha)
                    
                    # Draw transparent pixel
                    temp_surface = pygame.Surface((
                        canvas_sprite.pixel_width,
                        canvas_sprite.pixel_height,
                    ), pygame.SRCALPHA)
                    temp_surface.fill(transparent_pixel)
                    onion_surface.blit(temp_surface, (x, y))
        
        # Blit the onion surface to the main canvas
        canvas_sprite.image.blit(onion_surface, (0, 0))
        
    except Exception:
        LOG.exception("Failed to render onion skinning frames")
