#!/usr/bin/env python3
"""Simple example game for glitchygames."""

import argparse
import logging
import random
from typing import List, Tuple

import pygame

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite
from glitchygames.ui import Button, Label, Panel

LOG = logging.getLogger('game')

class Player(Sprite):
    """Player sprite that can be controlled with arrow keys."""
    
    def __init__(self, position=(100, 100), *groups):
        """Initialize the player.
        
        Args:
            position: Initial position
            *groups: Sprite groups to add this sprite to
        """
        # Create a simple player image
        image = pygame.Surface((32, 32))
        image.fill((0, 255, 0))  # Green square
        
        super().__init__(image=image, position=position, *groups)
        
        self.speed = 5
        
    def update(self):
        """Update the player's state."""
        # Get keyboard state
        keys = pygame.key.get_pressed()
        
        # Reset velocity
        self.velocity = [0, 0]
        
        # Apply movement based on arrow keys
        if keys[pygame.K_LEFT]:
            self.velocity[0] = -self.speed
        if keys[pygame.K_RIGHT]:
            self.velocity[0] = self.speed
        if keys[pygame.K_UP]:
            self.velocity[1] = -self.speed
        if keys[pygame.K_DOWN]:
            self.velocity[1] = self.speed
            
        # Call the parent update method to apply velocity
        super().update()
        
class Enemy(Sprite):
    """Enemy sprite that moves randomly."""
    
    def __init__(self, position=(0, 0), *groups):
        """Initialize the enemy.
        
        Args:
            position: Initial position
            *groups: Sprite groups to add this sprite to
        """
        # Create a simple enemy image
        image = pygame.Surface((32, 32))
        image.fill((255, 0, 0))  # Red square
        
        super().__init__(image=image, position=position, *groups)
        
        self.speed = 2
        self.direction_timer = 0
        self.direction_change_time = 30  # Change direction every 30 frames
        
    def update(self):
        """Update the enemy's state."""
        # Change direction periodically
        self.direction_timer += 1
        if self.direction_timer >= self.direction_change_time:
            self.direction_timer = 0
            self.velocity[0] = random.uniform(-self.speed, self.speed)
            self.velocity[1] = random.uniform(-self.speed, self.speed)
            
        # Call the parent update method to apply velocity
        super().update()
        
        # Wrap around the screen
        if self.position[0] < -32:
            self.position[0] = 800
        elif self.position[0] > 800:
            self.position[0] = -32
            
        if self.position[1] < -32:
            self.position[1] = 600
        elif self.position[1] > 600:
            self.position[1] = -32
            
class SimpleGame(Scene):
    """Simple game scene with a player and enemies."""
    
    NAME = "Simple Game"
    VERSION = "0.1.0"
    
    def __init__(self, options):
        """Initialize the game scene.
        
        Args:
            options: Command line options
        """
        # Create sprite groups
        groups = {
            'all': pygame.sprite.Group(),
            'player': pygame.sprite.Group(),
            'enemies': pygame.sprite.Group(),
        }
        
        super().__init__(options, groups)
        
        self.background_color = (0, 0, 128)  # Dark blue
        self.score = 0
        self.game_over = False
        
    def init(self):
        """Initialize the game scene."""
        LOG.info("Initializing game scene")
        
        # Create the player
        self.player = Player(position=(400, 300), groups=[self.groups['all'], self.groups['player']])
        
        # Create some enemies
        for _ in range(10):
            x = random.randint(0, 800)
            y = random.randint(0, 600)
            Enemy(position=(x, y), groups=[self.groups['all'], self.groups['enemies']])
            
        # Create UI elements
        self.score_label = Label(
            rect=pygame.Rect(10, 10, 200, 30),
            text=f"Score: {self.score}",
            text_color=(255, 255, 255),
            align='left'
        )
        
        # Create a restart button (hidden initially)
        self.restart_button = Button(
            rect=pygame.Rect(350, 300, 100, 40),
            text="Restart",
            callback=self.restart_game,
            visible=False
        )
        
    def restart_game(self):
        """Restart the game."""
        LOG.info("Restarting game")
        
        # Reset game state
        self.score = 0
        self.game_over = False
        
        # Update score label
        self.score_label.text = f"Score: {self.score}"
        
        # Hide the restart button
        self.restart_button.visible = False
        
        # Clear sprite groups
        for group in self.groups.values():
            group.empty()
            
        # Recreate the player and enemies
        self.player = Player(position=(400, 300), groups=[self.groups['all'], self.groups['player']])
        
        for _ in range(10):
            x = random.randint(0, 800)
            y = random.randint(0, 600)
            Enemy(position=(x, y), groups=[self.groups['all'], self.groups['enemies']])
            
    def update(self):
        """Update the game state."""
        if self.game_over:
            # Only process UI events when game is over
            events = pygame.event.get()
            self.restart_button.update(events)
            return
            
        # Update all sprites
        super().update()
        
        # Check for collisions between player and enemies
        collisions = pygame.sprite.spritecollide(self.player, self.groups['enemies'], True)
        
        if collisions:
            # Increase score for each enemy hit
            self.score += len(collisions)
            self.score_label.text = f"Score: {self.score}"
            
            # Create new enemies to replace the ones that were removed
            for _ in range(len(collisions)):
                x = random.randint(0, 800)
                y = random.randint(0, 600)
                Enemy(position=(x, y), groups=[self.groups['all'], self.groups['enemies']])
                
        # Check if all enemies are gone
        if not self.groups['enemies']:
            self.game_over = True
            self.restart_button.visible = True
            
    def draw(self, surface):
        """Draw the game scene.
        
        Args:
            surface: Surface to draw on
        """
        # Draw the background
        surface.fill(self.background_color)
        
        # Draw all sprites
        self.groups['all'].draw(surface)
        
        # Draw UI elements
        self.score_label.draw(surface)
        
        if self.game_over:
            # Draw game over message
            font = pygame.font.SysFont(None, 48)
            text = font.render("Game Over!", True, (255, 255, 255))
            text_rect = text.get_rect(center=(400, 200))
            surface.blit(text, text_rect)
            
            # Draw restart button
            self.restart_button.draw(surface)
            
    @classmethod
    def args(cls, parser):
        """Add game-specific command line arguments.
        
        Args:
            parser: Argument parser to add arguments to
        """
        parser.add_argument('--enemy-count', type=int, default=10,
                            help='Number of enemies to spawn')
        parser.add_argument('--player-speed', type=float, default=5.0,
                            help='Player movement speed')
        
def main():
    """Main entry point for the game."""
    GameEngine(game=SimpleGame).start()
    
if __name__ == "__main__":
    main()