#!/usr/bin/env python3
"""Glitchy Games Engine scenes module."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, ClassVar, Self

import pygame
from glitchygames import events
from glitchygames.color import BLACK
from glitchygames.events.mouse import MousePointer
from glitchygames.interfaces import SceneInterface, SpriteInterface

if TYPE_CHECKING:
    from collections.abc import Callable

LOG = logging.getLogger('game.scenes')
LOG.addHandler(logging.NullHandler())


class SceneManager(SceneInterface, events.EventManager):
    """Glitchy Games Scene Manager.

    The scene manager is responsible for managing the active scene,
    and for processing events.
    """

    log: ClassVar = LOG
    OPTIONS: ClassVar = {}

    def __init__(self: Self) -> None:
        """Initialize the scene manager.

        Returns:
            None
        """
        super().__init__()

        # Scene manager terminates on self.next_scene = None
        self.screen = pygame.display.get_surface()
        self.update_type = 'update'
        self.fps_refresh_rate = 1000
        self.target_fps = 0
        self.dt = 0
        self.timer = 0
        self._game_engine = None
        self.active_scene = None
        self.next_scene = self.active_scene
        self.previous_scene = self.active_scene
        self.quit_requested = False

        self.clock = pygame.time.Clock()

    @property
    def game_engine(self: Self) -> object:
        """Return the game engine.

        Returns:
            object: The game engine.
        """
        return self._game_engine

    @game_engine.setter
    def game_engine(self: Self, new_engine: object) -> None:
        self._game_engine = new_engine
        if self._game_engine:
            self.OPTIONS = self._game_engine.OPTIONS
            self.update_type = self.OPTIONS['update_type']
            self.fps_refresh_rate = self.OPTIONS['fps_refresh_rate']
            self.target_fps = self.OPTIONS.get('target_fps', 60)
            self.log.info(f'Screen update type: {self.update_type}')
            self.log.info(f'FPS Refresh Rate: {self.fps_refresh_rate}')
            self.log.info(f'Target FPS: {self.target_fps}')

    # This enables collided_sprites in sprites.py, since SceneManager is
    # not a scene, but is the entry point for event proxies.
    @property
    def all_sprites(self: Self) -> pygame.sprite.LayeredDirty | None:
        """Return the active scene's sprite group.

        Returns:
            pygame.sprite.LayeredDirty | None: The active scene's sprite group.
        """
        if self.active_scene:
            return self.active_scene.all_sprites

        return None

    def switch_to_scene(self: Self, next_scene: Scene) -> None:
        """Switch to the next scene.

        Args:
            next_scene (Scene): The next scene to switch to.

        Returns:
            None
        """
        if next_scene != self.active_scene:
            self.dt = 0
            self.timer = 0
            self.log.info(f'Switching to scene "{next_scene}" ' f'from scene "{self.active_scene}"')

            if self.active_scene:
                self.active_scene._screenshot = self.active_scene.screenshot
                self.log.info(f'Cleaning up active scene {self.active_scene}.')
                self.active_scene.cleanup()

            if next_scene:
                self.log.info(f'Setting up new scene {next_scene}.')
                next_scene.setup()

                self.log.info(f'Scene {next_scene.name} event block list: ')

                blocked_events = []

                [
                    blocked_events.append(event) if pygame.event.get_blocked(event) else None
                    for event in events.ALL_EVENTS
                ]

                if not blocked_events:
                    self.log.info('None')

                for event in blocked_events:
                    self.log.info(f'{pygame.event.event_name(event)}: Blocked')

            self.active_scene = next_scene

            if self.active_scene:
                self.active_scene.dt = self.dt
                self.active_scene.timer = self.timer
                self.active_scene.setup()

                caption = ''

                if self.active_scene.NAME:
                    caption = f'{self.active_scene.NAME}'

                if self.active_scene.VERSION:
                    caption += f' v{self.active_scene.VERSION}'

                pygame.display.set_caption(caption, caption)

                self.active_scene.load_resources()

                # Infinite refresh is the default; override it if FPS was configured
                # on the command line, unless the active scene has specific FPS requirements
                if self.target_fps > 0 and self.active_scene.target_fps == 0:
                    self.active_scene.target_fps = self.target_fps

                self.log.info(
                    f'Rendering Scene "{self.active_scene.NAME}({type(self.active_scene)})"'
                    f' at {self.active_scene.target_fps} FPS'
                )

                # This controls how events are marshalled
                self.proxies = [self, self.active_scene]

                # Force a scene redraw
                self.active_scene.dirty = 1

                # Redraw the new scene's background to clear out any artifacts
                self.screen.blit(self.active_scene.background, (0, 0))

                # Per-scene FPS configurability
                self.target_fps = self.active_scene.target_fps

    def play(self: Self) -> None:
        """Play the game."""
        return self.start()

    def start(self: Self) -> None:
        """Start the scene manager.

        Returns:
            None
        """
        previous_time: float = time.perf_counter()
        previous_fps_time: float = previous_time
        current_time: float = previous_time

        while self.active_scene is not None and self.quit_requested is False:
            self.clock.tick(self.target_fps)

            now: float = time.perf_counter()
            self.dt: float = (now - previous_time) * 10.0
            previous_time = current_time

            self.active_scene.dt_tick(self.dt)

            self.game_engine.process_events()

            self.active_scene.update()

            self.active_scene.render(self.screen)

            if self.update_type == 'update':
                pygame.display.update(self.active_scene.rects)
            elif self.update_type == 'flip':
                pygame.display.flip()

            if (current_time - previous_fps_time) * 1000 >= self.OPTIONS['fps_refresh_rate']:
                pygame.event.post(
                    pygame.event.Event(events.FPSEVENT, {'fps': self.clock.get_fps()})
                )

                previous_fps_time = current_time

            self.switch_to_scene(self.active_scene.next_scene)

            current_time = time.perf_counter()

        self.log.info(
            f'Game Quitting: Active Scene: {self.active_scene}, '
            f'Quit Requested: {self.quit_requested}'
        )
        return self.terminate()

    def stop(self: Self) -> None:
        """Stop the game."""
        return self.terminate()

    def terminate(self: Self) -> None:
        """Terminate the scene manager.

        Returns:
            None
        """
        self.switch_to_scene(None)

    def quit(self: Self) -> None:
        """Quit the game.

        Returns:
            None
        """
        return self.quit_game()

    def quit_game(self: Self) -> None:
        """Quit the game.

        Returns:
            None
        """
        # put a quit event in the event queue.
        self.log.info('POSTING QUIT EVENT')
        pygame.event.post(pygame.event.Event(pygame.QUIT, {}))

    def on_quit_event(self: Self, event: events.HashableEvent) -> None:
        """Handle quit events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # QUIT             none
        self.quit_requested = True

    def on_fps_event(self: Self, event: events.HashableEvent) -> None:
        """Handle FPS events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # FPSEVENT is pygame.USEREVENT + 1
        if self.active_scene:
            self.active_scene.on_fps_event(event)

    def on_game_event(self: Self, event: events.HashableEvent) -> None:
        """Handle game events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # GAMEEVENT is pygame.USEREVENT + 2
        # Call the event callback if it's registered.
        try:
            self.game_engine.registered_events[event.subtype](event)
        except KeyError:
            self.log.exception(
                f'Unregistered Event: {event} '
                '(call self.register_game_event(<event subtype>, <event data>))'
            )

    def register_game_event(
        self: Self, event_type: pygame.event.EventType, callback: Callable
    ) -> None:
        """Register a game event.

        Args:
            event_type (pygame.event.EventType): The event type to register.
            callback (Callable): The callback to call when the event is triggered.

        Returns:
            None
        """
        self.game_engine.register_game_event(event_type=event_type, callback=callback)

    # If the game hasn't hooked a call, we should check if the scene manager has.
    #
    # This will allow scenes to get pygame events directly, but we can still
    # hook those events in this engine, or in the subclassed game object, too.
    #
    # This allows maximum flexibility of event processing, with low overhead
    # at the expense of a slight layer violation.
    def __getattr__(self: Self, attr: str) -> Callable:
        """Proxy calls to the active scene.

        Args:
            attr (str): The attribute to proxy.

        Returns:
            Callable: The callable object.
        """
        # Attempt to proxy the call to the active scene.
        if attr.startswith('on_') and attr.endswith('_event'):
            try:
                # Pass it to the active scene for handling
                return getattr(self.active_scene, attr)
            except AttributeError:
                # Pass it to the game engine for suppression
                return getattr(self.game_engine, attr)
        else:
            raise AttributeError(f"'{type(self)}' object has no attribute '{attr}'")

    def handle_event(self, event: events.HashableEvent) -> None:
        """Handle pygame events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # Check for focused sprites first
        if self.active_scene and self.active_scene.all_sprites:
            focused_sprites = [sprite for sprite in self.active_scene.all_sprites
                             if hasattr(sprite, 'active') and sprite.active]

            if focused_sprites and event.type == pygame.KEYDOWN:
                # Let the active scene handle it directly
                self.active_scene.handle_event(event)
                return

        # Only process other events if no focused sprites handled it
        if event.type == pygame.QUIT:
            self.log.info("POSTING QUIT EVENT")
            self.quit_requested = True
        else:
            # Pass to active scene if we have one
            if self.active_scene:
                self.active_scene.handle_event(event)


class Scene(SceneInterface, SpriteInterface, events.AllEventStubs):
    """Scene object base class.

    Subclass this to properly receive on_*_event() messages automatically.
    """

    log = LOG
    FPS = 0
    NAME = 'Unnamed Scene'
    VERSION = '0.0'

    def __init__(
        self: Self, options: dict | None = None, groups: pygame.sprite.LayeredDirty | None = None
    ) -> None:
        """Initialize the scene.

        Args:
            options (dict | None): The options passed to the game.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if options is None:
            options = {}

        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        if self.NAME == 'Unnamed Scene':
            self.NAME = type(self).__name__

        super().__init__()

        # Since SceneManager is a singleton, this will ensure that
        # any non-active scene which gets initialized will simply
        # get a copy of the scene manager, rather than overwriting
        # the active scene.
        #
        # This helps us keep the upper layers clean by not requiring
        # new scenes to care about the SceneManager when being
        # instantiated.
        self.target_fps = 0
        self.fps = 0
        self.dt = 0
        self.dt_timer = 0
        self.dirty = 1
        self.options = options
        self.scene_manager = SceneManager()
        self.name = type(self)
        self._background_color = None
        self.next_scene = self
        self.rects = None
        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

        # http://n0nick.github.io/blog/2012/06/03/quick-dirty-using-pygames-dirtysprite-layered/
        self.all_sprites = groups

        # Initial screen state.

        self.screen = pygame.display.get_surface()
        self.background = pygame.Surface(self.screen.get_size())
        self.background.convert()
        self.background_color = BLACK

        # This allows us to be treated like a sprite
        self.image = self.screen
        self.rect = self.screen.get_rect()

        self.dirty = 1
        # I don't think this will work since init() is called first.
        # for group in groups:
        #    for sprite in self.all_sprites:
        #        group.add(sprite)

    @property
    def screenshot(self: Self) -> pygame.Surface:
        """Return a screenshot of the scene.

        Returns:
            pygame.Surface: The scene screenshot.
        """
        _screenshot = pygame.Surface((self.screen_width, self.screen_height))
        _screenshot.convert()
        _screenshot.blit(self.screen, (0, 0))
        return _screenshot

    @property
    def background_color(self: Self) -> pygame.Color:
        """Return the background color.

        Returns:
            pygame.Color: The background color.
        """
        return self._background_color

    @background_color.setter
    def background_color(self: Self, new_color: tuple) -> None:
        """Set the background color.

        Args:
            new_color (tuple): The new background color.

        Returns:
            None
        """
        self._background_color = new_color
        self.background.fill(self.background_color)
        self.all_sprites.clear(self.screen, self.background)

    def setup(self: Self) -> None:
        """Setup the scene.

        Returns:
            None
        """

    def cleanup(self: Self) -> None:
        """Cleanup the scene.

        Returns:
            None
        """

    def dt_tick(self: Self, dt: float) -> None:
        """Update the scene's delta time.

        Args:
            dt (float): The delta time to update.

        Returns:
            None
        """
        self.dt = dt
        self.dt_timer += self.dt

    def update(self: Self) -> None:
        """Update the active scene.

        Returns:
            None
        """
        # Tweak to enable compound sprites to manage their own subsprites dirty states
        #
        # Ideally we'd just make dirty a property with a setter and getter on each
        # sprite object, but that doesn't work for some reason.
        [sprite.update_nested_sprites() for sprite in self.all_sprites]
        [sprite.update() for sprite in self.all_sprites if sprite.dirty]

        # Make all of the new scene's sprites dirty to force a redraw
        if self.dirty:
            for sprite in self.all_sprites:
                sprite.dirty = 1 if not sprite.dirty else sprite.dirty

    def render(self: Self, screen: pygame.Surface) -> None:
        """Render the active scene.

        Args:
            screen (pygame.Surface): The screen to render to.

        Returns:
            None
        """
        self.rects = self.all_sprites.draw(self.screen)

    def sprites_at_position(self: Self, pos: tuple) -> list[pygame.sprite.Sprite] | None:
        """Return the sprites at a given position.

        Args:
            pos (tuple): The position to check.

        Returns:
            list[pygame.sprite.Sprite] | None: The sprites at the given position.
        """
        mouse = MousePointer(pos=pos)

        return pygame.sprite.spritecollide(sprite=mouse, group=self.all_sprites, dokill=False)

    # def on_active_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle active events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # ACTIVEEVENT      gain, state
    #     self.log.debug(f'{type(self)}: On Active Event {event}')

    # def on_audio_device_added_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle audio device added events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # AUDIODEVICEADDED which, iscapture
    #     self.log.debug(f'{type(self)}: On Audio Device Added Event {event}')

    # def on_audio_device_removed_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle audio device removed events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # AUDIODEVICEREMOVED which, iscapture
    #     self.log.debug(f'{type(self)}: On Audio Device Removed Event {event}')

    # def on_controller_axis_motion_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle controller axis motion events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # CONTROLLERAXISMOTION which, axis, value
    #     self.log.debug(f'{type(self)}: On Controller Axis Motion Event {event}')

    def on_controller_button_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle controller button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # CONTROLLERBUTTONDOWN which, button
        self.log.debug(f'{type(self)}: On Controller Button Down Event {event}')

    def on_controller_button_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle controller button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # CONTROLLERBUTTONUP which, button
        self.log.debug(f'{type(self)}: On Controller Button Up Event {event}')

    # def on_controller_device_added_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle controller device added events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # CONTROLLERDEVICEADDED which
    #     self.log.debug(f'{type(self)}: On Controller Device Added Event {event}')

    # def on_controller_device_remapped_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle controller device remapped events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # CONTROLLERDEVICEREMAPPED which
    #     self.log.debug(f'{type(self)}: On Controller Device Remapped Event {event}')

    # def on_controller_device_removed_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle controller device removed events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # CONTROLLERDEVICEREMOVED which
    #     self.log.debug(f'{type(self)}: On Controller Device Removed Event {event}')

    # def on_controller_touchpad_down_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle controller touchpad down events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # CONTROLLERTOUCHPADDOWN which, touchpad
    #     self.log.debug(f'{type(self)}: On Controller Touchpad Down Event {event}')

    # def on_controller_touchpad_motion_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle controller touchpad motion events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: On Controller Touchpad Motion Event {event}')

    # def on_controller_touchpad_up_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle controller touchpad up events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # CONTROLLERTOUCHPADUP which, touchpad
    #     self.log.debug(f'{type(self)}: On Controller Touchpad Up Event {event}')

    # def on_drop_begin_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle drop begin events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: On Drop Begin Event {event}')

    # def on_drop_complete_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle drop complete events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: On Drop Complete Event {event}')

    # def on_drop_file_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle drop file events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: On Drop File Event {event}')

    # def on_drop_text_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle drop text events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: On Drop Text Event {event}')

    # def on_font_changed_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle font changed events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: On Font Changed Event {event}')

    # def on_game_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle game events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # GAMEEVENT is pygame.USEREVENT + 2
    #     self.log.debug(f'{type(self)}: On Game Event {event}')

    # def on_joy_axis_motion_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle joy axis motion events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # JOYAXISMOTION    joy, axis, value
    #     self.log.debug(f'{type(self)}: On Joy Axis Motion Event {event}')

    # def on_joy_ball_motion_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle joy ball motion events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # JOYBALLMOTION    joy, ball, rel
    #     self.log.debug(f'{type(self)}: On Joy Ball Motion Event {event}')

    def on_joy_button_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle joy button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # JOYBUTTONDOWN    joy, button
        self.log.debug(f'{type(self)}: On Joy Button Down Event {event}')

    def on_joy_button_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle joy button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # JOYBUTTONUP      joy, button
        self.log.debug(f'{type(self)}: On Joy Button Up Event {event}')

    # def on_joy_device_added_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle joy device added events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # JOYDEVICEADDED   which
    #     self.log.debug(f'{type(self)}: On Joy Device Added Event {event}')

    # def on_joy_device_removed_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle joy device removed events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # JOYDEVICEREMOVED which
    #     self.log.debug(f'{type(self)}: On Joy Device Removed Event {event}')

    # def on_joy_hat_motion_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle joy hat motion events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # JOYHATMOTION     joy, hat, value
    #     self.log.debug(f'{type(self)}: On Joy Hat Motion Event {event}')

    # def on_key_down_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle key down events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: On Key Down Event {event}')

    def on_key_up_event(self, event: events.HashableEvent) -> None:
        """Handle key up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)}: On Key Up Event {event}')

        # Check for focused sprites first
        focused_sprites = [sprite for sprite in self.all_sprites
                          if hasattr(sprite, 'active') and sprite.active]

        # Only process quit keys if no sprites are focused
        if not focused_sprites:
            if event.key in {pygame.K_q, pygame.K_ESCAPE}:
                self.log.info("Quit requested")
                # Post a QUIT event to ensure proper cleanup
                pygame.event.post(pygame.event.Event(pygame.QUIT))

    # def on_key_chord_down_event(self: Self, event: events.HashableEvent, keys_down: list) -> None:
    #     """Handle key chord down events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.
    #         keys_down (list): The keys that are currently down.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: On Key Chord Down Event {event}')

    # def on_key_chord_up_event(self: Self, event: events.HashableEvent, keys_up: list) -> None:
    #     """Handle key chord up events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.
    #         keys_up (list): The keys that are currently up.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: On Key Chord Up Event {event}')

    def on_menu_item_event(self: Self, event: events.HashableEvent) -> None:
        """Handle menu item events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        breakpoint()
        # MENUITEM         menu, item
        self.log.debug(f'{type(self)}: On Menu Item Event {event}')

    def on_mouse_button_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f"=== Scene: Mouse Button Down ===")
        self.log.debug(f"Click position: {event.pos}")

        # Get sprites at click position
        collided_sprites = self.sprites_at_position(pos=event.pos)
        self.log.debug(f"Collided sprites: {[type(s).__name__ for s in collided_sprites]}")
        self.log.debug(f"Focusable sprites: {[s for s in collided_sprites if hasattr(s, 'focusable') and s.focusable]}")

        # Find currently focused sprites
        focused_sprites = [sprite for sprite in self.all_sprites
                          if hasattr(sprite, 'active') and sprite.active]
        self.log.debug(f"Currently focused sprites: {[type(s).__name__ for s in focused_sprites]}")

        # If we clicked outside all sprites that can be focused, unfocus them
        if not any(hasattr(sprite, 'focusable') and sprite.focusable for sprite in collided_sprites):
            self.log.debug("Click outside focusable sprites - unfocusing")
            for sprite in focused_sprites:
                if hasattr(sprite, 'active'):
                    self.log.debug(f"Unfocusing {type(sprite).__name__}")
                    sprite.active = False
                    if hasattr(sprite, 'on_focus_lost'):
                        sprite.on_focus_lost()

        # Process the click for collided sprites
        for sprite in collided_sprites:
            if hasattr(sprite, 'on_mouse_button_down_event'):
                sprite.on_mouse_button_down_event(event)

    # def on_mouse_button_up_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle mouse button up events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: On Mouse Button Up Event {event}')

    def on_mouse_drag_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The event trigger.

        Returns:
            None
        """
        self.log.debug(f'{type(self)}: Mouse Drag Event: {event} {trigger}')
        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_mouse_drag_event(event, trigger)

    def on_mouse_drop_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The event trigger.

        Returns:
            None
        """
        self.log.debug(f'{type(self)}: Mouse Drop Event: {event} {trigger}')
        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_mouse_drop_event(event, trigger)

    # def on_mouse_focus_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
    #     """Handle mouse focus events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.
    #         trigger (object): The event trigger.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: Mouse Focus Event: {event} {trigger}')

    def on_left_mouse_drag_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle left mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The event trigger.

        Returns:
            None
        """
        self.log.debug(f'{type(self)}: Left Mouse Drag Event: {event} {trigger}')
        collided_sprites: list | None = self.sprites_at_position(pos=event.pos)

        if collided_sprites:
            collided_sprites[-1].on_left_mouse_drag_event(event, trigger)

    def on_left_mouse_drop_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle left mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The event trigger.

        Returns:
            None
        """
        self.log.debug(f'{type(self)}: Left Mouse Drop Event: {event} {trigger}')
        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_left_mouse_drop_event(event, trigger)

    def on_middle_mouse_drag_event(
        self: Self, event: events.HashableEvent, trigger: object
    ) -> None:
        """Handle middle mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The event trigger.

        Returns:
            None
        """
        self.log.info(f'{type(self)}: Middle Mouse Drag Event: {event} {trigger}')
        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_drag_event(event, trigger)

    def on_middle_mouse_drop_event(
        self: Self, event: events.HashableEvent, trigger: object
    ) -> None:
        """Handle middle mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The event trigger.

        Returns:
            None
        """
        self.log.info(f'{type(self)}: Middle Mouse Drop Event: {event} {trigger}')
        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_drop_event(event, trigger)

    def on_right_mouse_drag_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle right mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The event trigger.

        Returns:
            None
        """
        self.log.info(f'{type(self)}: Right Mouse Drag Event: {event} {trigger}')
        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_right_mouse_drag_event(event, trigger)

    def on_right_mouse_drop_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle right mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The event trigger.

        Returns:
            None
        """
        self.log.info(f'{type(self)}: Right Mouse Drop Event: {event} {trigger}')
        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_right_mouse_drop_event(event, trigger)

    def on_left_mouse_button_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle left mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONUP    pos, button
        self.log.debug(f'{type(self)}: Left Mouse Button Up Event: {event}')

        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_left_mouse_button_up_event(event)

    def on_middle_mouse_button_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle middle mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONUP    pos, button
        self.log.debug(f'{type(self)}: Middle Mouse Button Up Event: {event}')

        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_button_up_event(event)

    def on_right_mouse_button_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle right mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONUP    pos, button
        self.log.info(f'{type(self)}: Right Mouse Button Up Event: {event}')

        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_right_mouse_button_up_event(event)

    def on_left_mouse_button_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle left mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug("=== Scene: Left Mouse Button Down ===")
        self.log.debug(f"Click position: {event.pos}")

        # Get sprites at click position
        collided_sprites = self.sprites_at_position(pos=event.pos)
        self.log.debug(f"Collided sprites: {[type(s).__name__ for s in collided_sprites]}")
        self.log.debug(f"Focusable sprites: {[s for s in collided_sprites if hasattr(s, 'focusable') and s.focusable]}")

        # Find currently focused sprites
        focused_sprites = [sprite for sprite in self.all_sprites
                          if hasattr(sprite, 'active') and sprite.active]
        self.log.debug(f"Currently focused sprites: {[type(s).__name__ for s in focused_sprites]}")

        # If we clicked outside all sprites that can be focused, unfocus them
        if not any(hasattr(sprite, 'focusable') and sprite.focusable for sprite in collided_sprites):
            self.log.debug("Click outside focusable sprites - unfocusing")
            for sprite in focused_sprites:
                if hasattr(sprite, 'active'):
                    self.log.debug(f"Unfocusing {type(sprite).__name__}")
                    sprite.active = False
                    if hasattr(sprite, 'on_focus_lost'):
                        sprite.on_focus_lost()

        # Process the click for collided sprites
        for sprite in collided_sprites:
            if hasattr(sprite, 'on_left_mouse_button_down_event'):
                sprite.on_left_mouse_button_down_event(event)

    def on_middle_mouse_button_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle middle mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONDOWN    pos, button
        self.log.debug(f'{type(self)}: Middle Mouse Button Down Event: {event}')

        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_middle_mouse_button_down_event(event)

    def on_right_mouse_button_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle right mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.info(f'{type(self)}: Right Mouse Button Down Event: {event}')

        collided_sprites = self.sprites_at_position(pos=event.pos)

        for sprite in collided_sprites:
            sprite.on_right_mouse_button_down_event(event)

    # def on_mouse_motion_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle mouse motion events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: Mouse Motion Event: {event}')

    # collided_sprites = self.sprites_at_position(pos=event.pos)

    # for sprite in collided_sprites:
    #     sprite.on_mouse_motion_event(event)

    # def on_mouse_scroll_down_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle mouse scroll down events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: Mouse Scroll Down Event: {event}')

    # def on_mouse_scroll_up_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle mouse scroll up events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: Mouse Scroll Up Event: {event}')

    # def on_mouse_unfocus_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle mouse unfocus events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: Mouse Unfocus Event: {event}')

    # def on_mouse_wheel_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle mouse wheel events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: Mouse Wheel Event: {event}')

    # def on_multi_touch_down_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle multi touch down events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: Multi Touch Down Event: {event}')

    # def on_multi_touch_motion_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle multi touch motion events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: Multi Touch Motion Event: {event}')

    # def on_multi_touch_up_event(self: Self, event: events.HashableEvent) -> None:
    #     """Handle multi touch up events.

    #     Args:
    #         event (pygame.event.Event): The event to handle.

    #     Returns:
    #         None
    #     """
    #     self.log.debug(f'{type(self)}: Multi Touch Up Event: {event}')

    def on_sys_wm_event(self: Self, event: events.HashableEvent) -> None:
        """Handle sys wm events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)}: Sys WM Event: {event}')

    def on_text_editing_event(self: Self, event: events.HashableEvent) -> None:
        """Handle text editing events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)}: Text Editing Event: {event}')

    def on_text_input_event(self: Self, event: events.HashableEvent) -> None:
        """Handle text input events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)}: Text Input Event: {event}')

    def on_touch_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle touch down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # TOUCHBUTTONDOWN  touch, pos, button
        self.log.debug(f'{type(self)}: Touch Down Event: {event}')

    def on_touch_motion_event(self: Self, event: events.HashableEvent) -> None:
        """Handle touch motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # TOUCHMOTION      touch, pos
        self.log.debug(f'{type(self)}: Touch Motion Event: {event}')

    def on_touch_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle touch up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # TOUCHBUTTONUP    touch, pos
        self.log.debug(f'{type(self)}: Touch Up Event: {event}')

    def on_user_event(self: Self, event: events.HashableEvent) -> None:
        """Handle user events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # USEREVENT        code
        self.log.debug(f'{type(self)}: User Event: {event}')

    def on_video_expose_event(self: Self, event: events.HashableEvent) -> None:
        """Handle video expose events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # VIDEOEXPOSE      none
        self.log.debug(f'{type(self)}: Video Expose Event: {event}')

    def on_video_resize_event(self: Self, event: events.HashableEvent) -> None:
        """Handle video resize events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # VIDEORESIZE      size, w, h
        self.log.debug(f'{type(self)}: Video Resize Event: {event}')

    def on_window_close_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window close events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWCLOSE      none
        self.log.debug(f'{type(self)}: Window Close Event: {event}')

    def on_window_enter_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window enter events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWENTER      none
        self.log.debug(f'{type(self)}: Window Enter Event: {event}')

    def on_window_exposed_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window exposed events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWEXPOSED    none
        self.log.debug(f'{type(self)}: Window Exposed Event: {event}')

    def on_window_focus_gained_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window focus gained events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWFOCUSGAINED none
        self.log.debug(f'{type(self)}: Window Focus Gained Event: {event}')

    def on_window_focus_lost_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window focus lost events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWFOCUSLOST  none
        self.log.debug(f'{type(self)}: Window Focus Lost Event: {event}')

    def on_window_hidden_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window hidden events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWHIDDEN     none
        self.log.debug(f'{type(self)}: Window Hidden Event: {event}')

    def on_window_hit_test_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window hit test events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWHITTEST    pos
        self.log.debug(f'{type(self)}: Window Hit Test Event: {event}')

    def on_window_leave_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window leave events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWLEAVE      none
        self.log.debug(f'{type(self)}: Window Leave Event: {event}')

    def on_window_maximized_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window maximized events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWMAXIMIZED  none
        self.log.debug(f'{type(self)}: Window Maximized Event: {event}')

    def on_window_minimized_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window minimized events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWMINIMIZED  none
        self.log.debug(f'{type(self)}: Window Minimized Event: {event}')

    def on_window_moved_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window moved events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWMOVED      pos
        self.log.debug(f'{type(self)}: Window Moved Event: {event}')

    def on_window_resized_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window resized events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWRESIZED    size, w, h
        self.log.debug(f'{type(self)}: Window Resized Event: {event}')

    def on_window_restored_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window restored events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWRESTORED   none
        self.log.debug(f'{type(self)}: Window Restored Event: {event}')

    def on_window_shown_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window shown events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWSHOWN      none
        self.log.debug(f'{type(self)}: Window Shown Event: {event}')

    def on_window_size_changed_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window size changed events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWSIZECHANGED size, w, h
        self.log.debug(f'{type(self)}: Window Size Changed Event: {event}')

    def on_window_take_focus_event(self: Self, event: events.HashableEvent) -> None:
        """Handle window take focus events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWTAKEFOCUS  none
        self.log.debug(f'{type(self)}: Window Take Focus Event: {event}')

    def on_quit_event(self: Self, event: events.HashableEvent) -> None:
        """Handle quit events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # QUIT             none
        self.log.debug(f'{type(self)}: {event}')

    def on_fps_event(self: Self, event: events.HashableEvent) -> None:
        """Handle FPS events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # FPSEVENT is pygame.USEREVENT + 1
        self.log.info(f'Scene "{self.NAME}" ({type(self)}) FPS: {event.fps}')
        self.fps = event.fps

    def load_resources(self: Self) -> None:
        """Load the scene's resources.

        Returns:
            None
        """
        self.log.debug(f'Implement load_resource() in {type(self)}.')

    def on_key_down_event(self, event: events.HashableEvent) -> None:
        """Handle key down events."""
        self.log.debug(f'{type(self)}: On Key Down Event {event}')

        # Find the currently focused sprite
        focused_sprites = [sprite for sprite in self.all_sprites if hasattr(sprite, 'active') and sprite.active]

        if focused_sprites:
            # If we have focused sprites, only they get the events
            for sprite in focused_sprites:
                if hasattr(sprite, 'on_key_down_event'):
                    sprite.on_key_down_event(event)
                    return  # Stop event propagation after handling

        # Only process scene-level key events if no focused sprite handled it
        if event.key == pygame.K_q:
            self.log.info("Quit requested")
            self.quit_requested = True

    def on_text_submit_event(self, text: str) -> None:
        """Handle text submission from MultiLineTextBox.

        Args:
            text (str): The submitted text.

        Returns:
            None
        """
        self.log.info(f"Text submitted: '{text}'")
