"""Movement utilities for glitchygames."""

import math
from typing import Tuple

class Vector2D:
    """2D vector class for movement calculations."""
    
    def __init__(self, x: float = 0.0, y: float = 0.0):
        """Initialize the vector.
        
        Args:
            x: X component
            y: Y component
        """
        self.x = x
        self.y = y
        
    def __add__(self, other):
        """Add two vectors.
        
        Args:
            other: Vector to add
            
        Returns:
            New vector with the sum
        """
        return Vector2D(self.x + other.x, self.y + other.y)
        
    def __sub__(self, other):
        """Subtract two vectors.
        
        Args:
            other: Vector to subtract
            
        Returns:
            New vector with the difference
        """
        return Vector2D(self.x - other.x, self.y - other.y)
        
    def __mul__(self, scalar):
        """Multiply vector by scalar.
        
        Args:
            scalar: Scalar to multiply by
            
        Returns:
            New vector with the product
        """
        return Vector2D(self.x * scalar, self.y * scalar)
        
    def __truediv__(self, scalar):
        """Divide vector by scalar.
        
        Args:
            scalar: Scalar to divide by
            
        Returns:
            New vector with the quotient
        """
        return Vector2D(self.x / scalar, self.y / scalar)
        
    def __str__(self):
        """Get string representation of the vector.
        
        Returns:
            String representation
        """
        return f"Vector2D({self.x}, {self.y})"
        
    def __repr__(self):
        """Get string representation of the vector.
        
        Returns:
            String representation
        """
        return self.__str__()
        
    def length(self) -> float:
        """Get the length of the vector.
        
        Returns:
            Vector length
        """
        return math.sqrt(self.x * self.x + self.y * self.y)
        
    def normalize(self):
        """Normalize the vector to length 1."""
        length = self.length()
        if length > 0:
            self.x /= length
            self.y /= length
            
    def normalized(self):
        """Get a normalized copy of the vector.
        
        Returns:
            Normalized vector
        """
        result = Vector2D(self.x, self.y)
        result.normalize()
        return result
        
    def dot(self, other) -> float:
        """Calculate dot product with another vector.
        
        Args:
            other: Other vector
            
        Returns:
            Dot product
        """
        return self.x * other.x + self.y * other.y
        
    def angle(self) -> float:
        """Get the angle of the vector in radians.
        
        Returns:
            Angle in radians
        """
        return math.atan2(self.y, self.x)
        
    def rotate(self, angle: float):
        """Rotate the vector by an angle.
        
        Args:
            angle: Angle in radians
        """
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        x = self.x * cos_a - self.y * sin_a
        y = self.x * sin_a + self.y * cos_a
        self.x = x
        self.y = y
        
    def rotated(self, angle: float):
        """Get a rotated copy of the vector.
        
        Args:
            angle: Angle in radians
            
        Returns:
            Rotated vector
        """
        result = Vector2D(self.x, self.y)
        result.rotate(angle)
        return result
        
    def to_tuple(self) -> Tuple[float, float]:
        """Convert vector to tuple.
        
        Returns:
            Tuple representation
        """
        return (self.x, self.y)
        
    @staticmethod
    def from_tuple(t: Tuple[float, float]):
        """Create vector from tuple.
        
        Args:
            t: Tuple representation
            
        Returns:
            New vector
        """
        return Vector2D(t[0], t[1])
        
    @staticmethod
    def from_angle(angle: float, length: float = 1.0):
        """Create vector from angle and length.
        
        Args:
            angle: Angle in radians
            length: Vector length
            
        Returns:
            New vector
        """
        return Vector2D(math.cos(angle) * length, math.sin(angle) * length)

def linear_movement(position: Vector2D, velocity: Vector2D, delta_time: float) -> Vector2D:
    """Calculate linear movement.
    
    Args:
        position: Current position
        velocity: Velocity vector
        delta_time: Time since last update in seconds
        
    Returns:
        New position
    """
    return position + velocity * delta_time

def accelerated_movement(position: Vector2D, velocity: Vector2D, acceleration: Vector2D, delta_time: float) -> Tuple[Vector2D, Vector2D]:
    """Calculate accelerated movement.
    
    Args:
        position: Current position
        velocity: Current velocity
        acceleration: Acceleration vector
        delta_time: Time since last update in seconds
        
    Returns:
        Tuple of (new position, new velocity)
    """
    new_velocity = velocity + acceleration * delta_time
    new_position = position + (velocity + new_velocity) * 0.5 * delta_time
    return new_position, new_velocity

def follow_target(position: Vector2D, target: Vector2D, speed: float, delta_time: float) -> Vector2D:
    """Move towards a target position.
    
    Args:
        position: Current position
        target: Target position
        speed: Movement speed
        delta_time: Time since last update in seconds
        
    Returns:
        New position
    """
    direction = target - position
    distance = direction.length()
    
    if distance <= speed * delta_time:
        return Vector2D(target.x, target.y)
    
    direction.normalize()
    return position + direction * speed * delta_time

def orbit(center: Vector2D, radius: float, angle: float) -> Vector2D:
    """Calculate position on an orbit.
    
    Args:
        center: Center of the orbit
        radius: Orbit radius
        angle: Angle in radians
        
    Returns:
        Position on the orbit
    """
    return Vector2D(
        center.x + radius * math.cos(angle),
        center.y + radius * math.sin(angle)
    )