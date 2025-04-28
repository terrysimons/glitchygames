#!/usr/bin/env python3
"""Simple game example using glitchygames."""

import argparse
import logging
import random
import sys

import pygame

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite
from glitchygames.color import RED, GREEN, BLUE, YELLOW, WHITE, BLACK

LOG = logging.getLogger('game')

class Player(Sprite):
    """Player sprite."""
    
    def __init__(self, position=(0, 0), *groups):
        """Initialize the player.
        
        Args:
            position: Initial position
            *groups: Sprite groups to add this sprite to
        """
        # Create a simple player image
        image = pygame.Surface((32, 32), pygame.SRCALPHA)
        pygame.draw.circle(image, RED, (16, 16), 16)
        
        super().__init__(image=image, position=position, *groups)
        self.speed = 5
        
    def update(self):
        """Update the player's state."""
        super().update()
        
        # Keep player on screen
        screen_rect = pygame.display.get_surface().get_rect()
        if self.rect.left < 0:
            self.position.x = self.rect.width / 2
        elif self.rect.right > screen_rect.right:
            self.position.x = screen_rect.right - self.rect.width / 2
            
        if self.rect.top < 0:
            self.position.y = self.rect.height / 2
        elif self.rect.bottom > screen_rect.bottom:
            self.position.y = screen_rect.bottom - self.rect.height / 2
            
        self.update_rect()

class Enemy(Sprite):
    """Enemy sprite."""
    
    def __init__(self, position=(0, 0), *groups):
        """Initialize the enemy.
        
        Args:
            position: Initial position
            *groups: Sprite groups to add this sprite to
        """
        # Create a simple enemy image
        image = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.rect(image, BLUE, (0, 0, 24, 24))
        
        super().__init__(image=image, position=position, *groups)
        self.speed = random.uniform(1, 3)
        
    def update(self):
        """Update the enemy's state."""
        super().update()
        
        # Move downward
        self.position.y += self.speed
        
        # Remove if off screen
        if self.position.y > pygame.display.get_surface().get_height() + 50:
            self.kill()
            
        self.update_rect()

class Bullet(Sprite):
    """Bullet sprite."""
    
    def __init__(self, position=(0, 0), *groups):
        """Initialize the bullet.
        
        Args:
            position: Initial position
            *groups: Sprite groups to add this sprite to
        """
        # Create a simple bullet image
        image = pygame.Surface((8, 16), pygame.SRCALPHA)
        pygame.draw.rect(image, YELLOW, (0, 0, 8, 16))
        
        super().__init__(image=image, position=position, *groups)
        self.speed = 10
        
    def update(self):
        """Update the bullet's state."""
        super().update()
        
        # Move upward
        self.position.y -= self.speed
        
        # Remove if off screen
        if self.position.y < -50:
            self.kill()
            
        self.update_rect()

class SimpleGame(Scene):
    """Simple game scene."""
    
    NAME = "Simple Game"
    VERSION = "0.1.0"
    
    def __init__(self, options=None, groups=None):
        """Initialize the game scene.
        
        Args:
            options: Command line options
            groups: Sprite groups
        """
        super().__init__(options=options, groups=groups)
        
        self.background_color = BLACK
        self.score = 0
        self.game_over = False
        self.spawn_timer = 0
        self.spawn_interval = 1000  # ms
        
        # Create sprite groups
        self.all_sprites = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        
        # Create player
        self.player = Player(
            position=(400, 550),
            groups=[self.all_sprites]
        )
        
        # Font for score display
        self.font = pygame.font.Font(None, 36)
        
    def update(self):
        """Update the game state."""
        if self.game_over:
            return
            
        # Update all sprites
        self.all_sprites.update()
        
        # Spawn enemies
        current_time = pygame.time.get_ticks()
        if current_time - self.spawn_timer > self.spawn_interval:
            self.spawn_timer = current_time
            self.spawn_enemy()
            
        # Check for collisions
        # Bullets hitting enemies
        hits = pygame.sprite.groupcollide(self.bullets, self.enemies, True, True)
        for bullet, enemies_hit in hits.items():
            self.score += len(enemies_hit)
            
        # Enemies hitting player
        hits = pygame.sprite.spritecollide(self.player, self.enemies, False)
        if hits:
            self.game_over = True
            LOG.info("Game over! Final score: %s", self.score)
        
    def draw(self, surface):
        """Draw the game scene.
        
        Args:
            surface: Surface to draw on
        """
        # Clear the screen
        surface.fill(self.background_color)
        
        # Draw all sprites
        self.all_sprites.draw(surface)
        
        # Draw score
        score_text = f"Score: {self.score}"
        score_surface = self.font.render(score_text, True, WHITE)
        surface.blit(score_surface, (10, 10))
        
        # Draw game over message
        if self.game_over:
            game_over_text = "Game Over! Press R to restart"
            game_over_surface = self.font.render(game_over_text, True, RED)
            text_rect = game_over_surface.get_rect(center=(surface.get_width() // 2, surface.get_height() // 2))
            surface.blit(game_over_surface, text_rect)
        
    def on_key_down(self, event):
        """Handle key down events.
        
        Args:
            event: Pygame KEYDOWN event
        """
        super().on_key_down(event)
        
        if self.game_over:
            if event.key == pygame.K_r:
                self.reset_game()
            return
            
        if event.key == pygame.K_SPACE:
            self.shoot()
        
    def on_key_up(self, event):
        """Handle key up events.
        
        Args:
            event: Pygame KEYUP event
        """
        super().on_key_up(event)
        
    def update(self):
        """Update the game state."""
        if self.game_over:
            return
            
        # Update all sprites
        self.all_sprites.update()
        
        # Handle player movement
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.player.position.x -= self.player.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.player.position.x += self.player.speed
        
        # Update player rect
        self.player.update_rect()
        
        # Spawn enemies
        current_time = pygame.time.get_ticks()
        if current_time - self.spawn_timer > self.spawn_interval:
            self.spawn_timer = current_time
            self.spawn_enemy()
            
        # Check for collisions
        # Bullets hitting enemies
        hits = pygame.sprite.groupcollide(self.bullets, self.enemies, True, True)
        for bullet, enemies_hit in hits.items():
            self.score += len(enemies_hit)
            
        # Enemies hitting player
        hits = pygame.sprite.spritecollide(self.player, self.enemies, False)
        if hits:
            self.game_over = True
            LOG.info("Game over! Final score: %s", self.score)
        
    def spawn_enemy(self):
        """Spawn a new enemy."""
        x = random.randint(20, pygame.display.get_surface().get_width() - 20)
        enemy = Enemy(
            position=(x, -20),
            groups=[self.all_sprites, self.enemies]
        )
        
    def shoot(self):
        """Shoot a bullet."""
        bullet = Bullet(
            position=(self.player.position.x, self.player.position.y - 20),
            groups=[self.all_sprites, self.bullets]
        )
        
    def reset_game(self):
        """Reset the game state."""
        self.score = 0
        self.game_over = False
        self.spawn_timer = pygame.time.get_ticks()
        
        # Clear all sprites
        self.all_sprites.empty()
        self.enemies.empty()
        self.bullets.empty()
        
        # Create player
        self.player = Player(
            position=(400, 550),
            groups=[self.all_sprites]
        )
        
    @classmethod
    def args(cls, parser):
        """Add command line arguments for this scene.
        
        Args:
            parser: ArgumentParser to add arguments to
        """
        parser.add_argument(
            '--difficulty',
            choices=['easy', 'normal', 'hard'],
            default='normal',
            help='game difficulty'
        )

def main():
    """Main entry point."""
    GameEngine(
        game=SimpleGame,
        title="Simple Game Example"
    ).start()

if __name__ == "__main__":
    main()