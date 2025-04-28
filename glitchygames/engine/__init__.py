"""Game engine module for glitchygames."""

import argparse
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Type, Union

import pygame

LOG = logging.getLogger('game')

class GameEngine:
    """Main game engine class for glitchygames.
    
    This class handles:
    - Game initialization
    - Scene management
    - Main game loop
    - Event routing
    - Performance monitoring
    """
    
    def __init__(
        self,
        game=None,
        icon: Optional[str] = None,
        title: Optional[str] = None,
        args: Optional[List[str]] = None,
    ):
        """Initialize the game engine.
        
        Args:
            game: The main game scene class (uninitialized)
            icon: Path to the game icon
            title: Game title (defaults to game.NAME if available)
            args: Command line arguments (defaults to sys.argv)
        """
        self.running = False
        self.game_class = game
        self.game = None
        self.icon = icon
        self.title = title
        self.clock = None
        self.screen = None
        self.fps_stats = {
            'last_update': 0,
            'frames': 0,
            'current_fps': 0
        }
        
        # Parse arguments
        self.options = self._parse_args(args or sys.argv[1:])
        
        # Configure logging
        self._setup_logging()
        
    def _setup_logging(self):
        """Set up logging based on command line options."""
        if hasattr(self.options, 'log_level'):
            log_level = getattr(logging, self.options.log_level.upper())
            logging.basicConfig(
                level=log_level,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            LOG.debug("Logging initialized at level %s", self.options.log_level)
        
    def _init_pygame(self):
        """Initialize pygame and related subsystems."""
        LOG.debug("Initializing pygame")
        
        # Set video driver if specified
        if hasattr(self.options, 'video_driver') and self.options.video_driver:
            os.environ['SDL_VIDEODRIVER'] = self.options.video_driver
            
        pygame.init()
        self.clock = pygame.time.Clock()
        
        # Set window title
        if self.title is None and hasattr(self.game_class, 'NAME'):
            self.title = f"{self.game_class.NAME}"
            if hasattr(self.game_class, 'VERSION'):
                self.title += f" v{self.game_class.VERSION}"
        
        if self.title:
            pygame.display.set_caption(self.title)
            
        # Set window icon
        if self.icon and os.path.exists(self.icon):
            try:
                icon_surface = pygame.image.load(self.icon)
                pygame.display.set_icon(icon_surface)
            except pygame.error as e:
                LOG.error("Failed to load icon: %s", e)
                
    def _init_screen(self):
        """Initialize the game screen."""
        LOG.debug("Initializing screen")
        
        # Parse resolution
        width, height = map(int, self.options.resolution.split('x'))
        
        # Set display mode
        display_flags = pygame.FULLSCREEN
        if self.options.windowed:
            display_flags = 0
            
        self.screen = pygame.display.set_mode((width, height), display_flags)
        
    def _init_game(self):
        """Initialize the game scene."""
        LOG.debug("Initializing game")
        if self.game_class:
            self.game = self.game_class(options=self.options)
            self.game.engine = self
            self.game.screen = self.screen
            
            # Call the game's init method if it exists
            if hasattr(self.game, 'init') and callable(self.game.init):
                self.game.init()
            
    def _parse_args(self, args: List[str]) -> argparse.Namespace:
        """Parse command line arguments.
        
        Args:
            args: Command line arguments
            
        Returns:
            Parsed arguments namespace
        """
        parser = argparse.ArgumentParser(
            prog=f"{self.game_class.NAME} version {getattr(self.game_class, 'VERSION', '0.0.0')}" 
            if hasattr(self.game_class, 'NAME') else None
        )
        
        # Graphics options
        graphics_group = parser.add_argument_group('Graphics Options')
        graphics_group.add_argument(
            '-f', '--target-fps',
            type=int,
            help='cap the framerate (default: infinite)'
        )
        graphics_group.add_argument(
            '--fps-refresh-rate',
            type=int,
            default=1000,
            help='how often to update the FPS counter in ms (default: 1000)'
        )
        graphics_group.add_argument(
            '-w', '--windowed',
            action='store_true',
            help='run the program in windowed mode'
        )
        graphics_group.add_argument(
            '-r', '--resolution',
            default='1024x768',
            help='the resolution to use (default: 1024x768)'
        )
        graphics_group.add_argument(
            '--use-gfxdraw',
            action='store_true'
        )
        graphics_group.add_argument(
            '--update-type',
            choices=['update', 'flip'],
            default='update',
            help='update or flip (default: update)'
        )
        graphics_group.add_argument(
            '--video-driver',
            choices=[],  # Filled dynamically if needed
            help='video driver to use'
        )
        
        # Font options
        font_group = parser.add_argument_group('Font Options')
        font_group.add_argument('--font-name')
        font_group.add_argument('--font-size', type=int)
        font_group.add_argument('--font-bold', action='store_true')
        font_group.add_argument('--font-italic', action='store_true')
        font_group.add_argument('--font-antialias', action='store_true')
        font_group.add_argument('--font-dpi', type=int)
        
        # Game options
        game_group = parser.add_argument_group('Game Options')
        game_group.add_argument(
            '-l', '--log-level',
            choices=['debug', 'info', 'warning', 'error', 'critical'],
            default='info',
            help='set the logging level'
        )
        game_group.add_argument(
            '--no-unhandled-events',
            action='store_true',
            help='fail on unhandled events'
        )
        game_group.add_argument(
            '-p', '--profile',
            action='store_true',
            help='enable profiling'
        )
        
        # Add game-specific arguments if the game class has an args method
        if hasattr(self.game_class, 'args') and callable(self.game_class.args):
            game_name = getattr(self.game_class, 'NAME', 'Game')
            game_version = getattr(self.game_class, 'VERSION', '0.0.0')
            game_group = parser.add_argument_group(f'{game_name} v{game_version} Options')
            self.game_class.args(game_group)
        
        return parser.parse_args(args)
    
    def _update_fps(self):
        """Update FPS counter."""
        self.fps_stats['frames'] += 1
        current_time = pygame.time.get_ticks()
        
        if current_time - self.fps_stats['last_update'] > self.options.fps_refresh_rate:
            elapsed_time = (current_time - self.fps_stats['last_update']) / 1000.0
            self.fps_stats['current_fps'] = self.fps_stats['frames'] / elapsed_time
            self.fps_stats['frames'] = 0
            self.fps_stats['last_update'] = current_time
            
            if hasattr(self.game, 'on_fps_update'):
                self.game.on_fps_update(self.fps_stats['current_fps'])
    
    def _process_events(self):
        """Process pygame events and route them to the current scene."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return
                
            # Handle ESC and Q to quit
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                    self.running = False
                    return
            
            # Route event to game scene
            if self.game:
                # If the game has a process_events method, use that
                if hasattr(self.game, 'process_events') and callable(self.game.process_events):
                    self.game.process_events(event)
                # Otherwise, try to route to specific event handlers
                else:
                    self._route_event(event)
    
    def _route_event(self, event):
        """Route an event to the appropriate handler in the current scene."""
        if not self.game:
            return
            
        # Map pygame event types to handler method names
        event_handlers = {
            pygame.KEYDOWN: 'on_key_down',
            pygame.KEYUP: 'on_key_up',
            pygame.MOUSEMOTION: 'on_mouse_motion',
            pygame.MOUSEBUTTONDOWN: 'on_mouse_down',
            pygame.MOUSEBUTTONUP: 'on_mouse_up',
            pygame.JOYAXISMOTION: 'on_joy_axis',
            pygame.JOYBALLMOTION: 'on_joy_ball',
            pygame.JOYHATMOTION: 'on_joy_hat',
            pygame.JOYBUTTONDOWN: 'on_joy_button_down',
            pygame.JOYBUTTONUP: 'on_joy_button_up',
        }
        
        handler_name = event_handlers.get(event.type)
        if handler_name and hasattr(self.game, handler_name) and callable(getattr(self.game, handler_name)):
            getattr(self.game, handler_name)(event)
        elif self.options.no_unhandled_events:
            LOG.warning("Unhandled event: %s", event)
    
    def _update(self):
        """Update game state."""
        if self.game and hasattr(self.game, 'update') and callable(self.game.update):
            self.game.update()
    
    def _draw(self):
        """Draw the current scene."""
        if self.game and hasattr(self.game, 'draw') and callable(self.game.draw):
            self.game.draw(self.screen)
            
        # Update the display
        if self.options.update_type == 'flip':
            pygame.display.flip()
        else:
            pygame.display.update()
    
    def start(self):
        """Start the game loop."""
        # Initialize pygame
        self._init_pygame()
        
        # Initialize the screen
        self._init_screen()
        
        # Initialize the game
        self._init_game()
        
        # Start the game loop
        self.running = True
        LOG.info("Starting game loop")
        
        try:
            while self.running:
                # Process events
                self._process_events()
                
                # Update game state
                self._update()
                
                # Draw the scene
                self._draw()
                
                # Update FPS counter
                self._update_fps()
                
                # Cap the framerate if requested
                if self.options.target_fps:
                    self.clock.tick(self.options.target_fps)
                else:
                    self.clock.tick()
        except KeyboardInterrupt:
            LOG.info("Game interrupted by user")
        except Exception as e:
            LOG.exception("Unhandled exception in game loop: %s", e)
        finally:
            LOG.info("Shutting down")
            pygame.quit()
            
    def stop(self):
        """Stop the game loop."""
        self.running = False