"""Movement utilities for glitchygames."""

import math
from typing import List, Tuple, Union

import pygame

def move_towards(current: List[float], target: List[float], speed: float) -> List[float]:
    """Move a point towards a target at a given speed.
    
    Args:
        current: Current position [x, y]
        target: Target position [x, y]
        speed: Movement speed
        
    Returns:
        New position [x, y]
    """
    dx = target[0] - current[0]
    dy = target[1] - current[1]
    
    # Calculate distance
    distance = math.sqrt(dx * dx + dy * dy)
    
    if distance <= speed or distance == 0:
        # We can reach the target in this step
        return target.copy()
        
    # Normalize the direction and scale by speed
    dx = dx / distance * speed
    dy = dy / distance * speed
    
    return [current[0] + dx, current[1] + dy]
    
def move_in_direction(position: List[float], angle: float, speed: float) -> List[float]:
    """Move a point in a given direction at a given speed.
    
    Args:
        position: Current position [x, y]
        angle: Direction angle in degrees (0 = right, 90 = down)
        speed: Movement speed
        
    Returns:
        New position [x, y]
    """
    # Convert angle to radians
    rad = math.radians(angle)
    
    # Calculate movement vector
    dx = math.cos(rad) * speed
    dy = math.sin(rad) * speed
    
    return [position[0] + dx, position[1] + dy]
    
def follow_path(position: List[float], path: List[List[float]], 
                speed: float, loop: bool = False) -> Tuple[List[float], int]:
    """Move a point along a path of waypoints.
    
    Args:
        position: Current position [x, y]
        path: List of waypoints [[x, y], ...]
        speed: Movement speed
        loop: Whether to loop back to the start when reaching the end
        
    Returns:
        Tuple of (new position [x, y], current waypoint index)
    """
    if not path:
        return position.copy(), -1
        
    # Find the closest waypoint
    min_dist = float('inf')
    closest_idx = 0
    
    for i, waypoint in enumerate(path):
        dx = waypoint[0] - position[0]
        dy = waypoint[1] - position[1]
        dist = dx * dx + dy * dy  # Squared distance is enough for comparison
        
        if dist < min_dist:
            min_dist = dist
            closest_idx = i
            
    # Move towards the next waypoint
    next_idx = (closest_idx + 1) % len(path) if loop else min(closest_idx + 1, len(path) - 1)
    
    if next_idx == closest_idx and not loop:
        # We've reached the end of the path
        return path[closest_idx].copy(), closest_idx
        
    # Move towards the next waypoint
    new_pos = move_towards(position, path[next_idx], speed)
    
    return new_pos, next_idx
    
def apply_friction(velocity: List[float], friction: float) -> List[float]:
    """Apply friction to a velocity vector.
    
    Args:
        velocity: Current velocity [dx, dy]
        friction: Friction coefficient (0-1)
        
    Returns:
        New velocity [dx, dy]
    """
    return [velocity[0] * (1 - friction), velocity[1] * (1 - friction)]
    
def bounce(position: List[float], velocity: List[float], 
           bounds: pygame.Rect, elasticity: float = 1.0) -> Tuple[List[float], List[float]]:
    """Bounce a point off the edges of a rectangle.
    
    Args:
        position: Current position [x, y]
        velocity: Current velocity [dx, dy]
        bounds: Rectangle to bounce within
        elasticity: Bounce elasticity (0-1)
        
    Returns:
        Tuple of (new position [x, y], new velocity [dx, dy])
    """
    new_pos = position.copy()
    new_vel = velocity.copy()
    
    # Check horizontal bounds
    if new_pos[0] < bounds.left:
        new_pos[0] = bounds.left
        new_vel[0] = -new_vel[0] * elasticity
    elif new_pos[0] > bounds.right:
        new_pos[0] = bounds.right
        new_vel[0] = -new_vel[0] * elasticity
        
    # Check vertical bounds
    if new_pos[1] < bounds.top:
        new_pos[1] = bounds.top
        new_vel[1] = -new_vel[1] * elasticity
    elif new_pos[1] > bounds.bottom:
        new_pos[1] = bounds.bottom
        new_vel[1] = -new_vel[1] * elasticity
        
    return new_pos, new_vel