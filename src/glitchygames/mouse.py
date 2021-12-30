import logging

import pygame

from glitchygames.events import MouseEvents
from glitchygames.events import ResourceManager
from glitchygames.sprites import collided_sprites

LOG = logging.getLogger('game.mouse')
LOG.addHandler(logging.NullHandler())


class MouseManager(ResourceManager):
    class MouseProxy(MouseEvents, ResourceManager):
        def __init__(self, game=None):
            """
            Pygame mouse event proxy.

            MouseProxy facilitates key handling by bridging mouse events between
            pygame and your game.

            Args:
            ----
            game - The game instance.

            """
            super().__init__(game)
            self.mouse_state = {}
            self.mouse_dragging = False
            self.mouse_dropping = False
            self.current_focus = None
            self.previous_focus = None
            self.focus_locked = False

            self.game = game
            self.proxies = [self.game, pygame.mouse]

        def on_mouse_motion_event(self, event):
            self.mouse_state[event.type] = event
            self.game.on_mouse_motion_event(event)

            sprite = collided_sprites(self.game, event=event, index=-1)

            if sprite:
                self.log.debug(f'{type(self)}: Mouse Motion: {event}')
                sprite[0].on_mouse_motion_event(event)

                # # See if we're focused on the same sprite.
                # if self.current_focus != collided_sprite:
                #     # Newly focused object can "see" what the previously focused object was.
                #     #
                #     # Will be "None" if nothing is focused.
                #     #
                #     # We can use this to enable drag and drop.
                #     #
                #     # This will take care of the unfocus event, too.
                #     self.on_mouse_focus_event(event, collided_sprite)
                #     collided_sprite.on_mouse_enter_event(event)
                # else:
                #     # Otherwise, pass motion event to the focused sprite
                #     # so it can handle sub-components if it wants to.
                # self.current_focus.on_mouse_motion_event(event)
            # elif self.current_focus:
            #     # If we're focused on a sprite but the collide sprites list is empty, then
            #     # we're moving from a focus to empty space, and we should send an unfocus event.
            #     self.current_focus.on_mouse_exit_event(event)
            #     self.on_mouse_unfocus_event(event, self.current_focus)

            # Caller can check the buttons.
            # Note: This probably doesn't work right because
            # we aren't keeping track of button states.
            # We should be looking at all mouse states and emitting appropriately.
            for trigger in self.mouse_state.values():
                if trigger.type == pygame.MOUSEBUTTONDOWN:
                    self.on_mouse_drag_event(event, trigger)
                    self.mouse_dragging = True

        def on_mouse_drag_event(self, event, trigger):
            self.log.debug(f'{type(self)}: Mouse Drag: {event}')
            self.game.on_mouse_drag_event(event, trigger)

            # if self.focus_locked:
            #     if self.current_focus:
            #         self.current_focus.on_mouse_drag_event(event, trigger)
            #     elif self.previous_focus:
            #         self.previous_focus.on_mouse_drag_event(event, trigger)

            if trigger.button == 1:
                self.on_left_mouse_drag_event(event, trigger)
            if trigger.button == 2:
                self.on_middle_mouse_drag_event(event, trigger)
            if trigger.button == 3:
                self.on_right_mouse_drag_event(event, trigger)
            if trigger.button == 4:
                # This doesn't really make sense.
                pass
            if trigger.button == 5:
                # This doesn't really make sense.
                pass

        def on_mouse_drop_event(self, event, trigger):
            self.log.debug(f'{type(self)}: Mouse Drop: {event} {trigger}')
            self.mouse_dropping = True
            self.game.on_mouse_drop_event(event, trigger)

            # if self.focus_locked:
            #     if self.current_focus:
            #         self.current_focus.on_mouse_drop_event(event, trigger)
            #     elif self.previous_focus:
            #         self.previous_focus.on_mouse_drop_event(event, trigger)

            if trigger.button == 1:
                self.on_left_mouse_drop_event(event, trigger)
            if trigger.button == 2:
                self.on_middle_mouse_drop_event(event, trigger)
            if trigger.button == 3:
                self.on_right_mouse_drop_event(event, trigger)
            if trigger.button == 4:
                # This doesn't really make sense.
                pass
            if trigger.button == 5:
                # This doesn't really make sense.
                pass

            self.mouse_dropping = False

        def on_left_mouse_drag_event(self, event, trigger):
            self.game.on_left_mouse_drag_event(event, trigger)

            # if self.focus_locked:
            #     if self.current_focus:
            #         self.current_focus.on_left_mouse_drag_event(event, trigger)
            #     elif self.previous_focus:
            #         self.previous_focus.on_left_mouse_drag_event(event, trigger)

        def on_left_mouse_drop_event(self, event, trigger):
            self.game.on_left_mouse_drag_up_event(event, trigger)

            # if self.focus_locked:
            #     if self.current_focus:
            #         self.current_focus.on_left_mouse_drop_event(event, trigger)
            #     elif self.previous_focus:
            #         self.previous_focus.on_left_mouse_drop_event(event, trigger)

        def on_middle_mouse_drag_event(self, event, trigger):
            self.game.on_middle_mouse_drag_down_event(event, trigger)

            # if self.focus_locked:
            #     if self.current_focus:
            #         self.current_focus.on_middle_mouse_drag_event(event, trigger)
            #     elif self.previous_focus:
            #         self.previous_focus.on_middle_mouse_drag_event(event, trigger)

        def on_middle_mouse_drop_event(self, event, trigger):
            self.game.on_middle_mouse_drag_up_event(event, trigger)

            # if self.focus_locked:
            #     if self.current_focus:
            #         self.current_focus.on_middle_mouse_drop_event(event, trigger)
            #     elif self.previous_focus:
            #         self.previous_focus.on_middle_mouse_drop_event(event, trigger)

        def on_right_mouse_drag_event(self, event, trigger):
            self.game.on_right_mouse_drag_down_event(event, trigger)

            # if self.focus_locked:
            #     if self.current_focus:
            #         self.current_focus.on_right_mouse_drag_event(event, trigger)
            #     elif self.previous_focus:
            #         self.previous_focus.on_right_mouse_drag_event(event, trigger)

        def on_right_mouse_drop_event(self, event, trigger):
            self.game.on_right_mouse_drag_up_event(event, trigger)

            # if self.focus_locked:
            #     if self.current_focus:
            #         self.current_focus.on_right_mouse_drop_event(event, trigger)
            #     elif self.previous_focus:
            #         self.previous_focus.on_right_mouse_drop_event(event, trigger)

        def on_mouse_focus_event(self, event, entering_focus):
            # Send a leave focus event for the old focus.
            # if not self.focus_locked:
            self.on_mouse_unfocus_event(event, self.current_focus)

            # We've entered a new object.
            self.current_focus = entering_focus

            # Send an enter event for the new focus.
            entering_focus.on_mouse_focus_event(event, self.current_focus)

            self.log.info(f'Entered Focus: {self.current_focus}')
            # else:
            #     self.log.info(f'Focus Locked: {self.previous_focus}')

        def on_mouse_unfocus_event(self, event, leaving_focus):
            self.previous_focus = leaving_focus

            if leaving_focus:
                leaving_focus.on_mouse_unfocus_event(event)
                self.current_focus = None

                self.log.info(f'Left Focus: {self.previous_focus}')

        def on_mouse_button_up_event(self, event):
            self.mouse_state[event.button] = event
            self.game.on_mouse_button_up_event(event)

            if event.button == 1:
                self.on_left_mouse_button_up_event(event)
            if event.button == 2:
                self.on_middle_mouse_button_up_event(event)
            if event.button == 3:
                self.on_right_mouse_button_up_event(event)
            if event.button == 4:
                # This doesn't really make sense.
                pass
            if event.button == 5:
                # This doesn't really make sense.
                pass

            if self.mouse_dragging:
                # The mouse up location is also the trigger.
                self.mouse_dragging = False
                self.game.on_mouse_drop_event(event=event, trigger=event)

            # Whatever was locked gets unlocked.
            # self.focus_locked = False

        def on_left_mouse_button_up_event(self, event):
            self.game.on_left_mouse_button_up_event(event)

        def on_middle_mouse_button_up_event(self, event):
            self.game.on_middle_mouse_button_up_event(event)

        def on_right_mouse_button_up_event(self, event):
            self.game.on_right_mouse_button_up_event(event)

        def on_mouse_button_down_event(self, event):
            self.mouse_state[event.button] = event

            # Whatever was clicked on gets lock.
            # if self.current_focus:
            #     # TODO: Fix - Disabling for debugging.
            #     self.focus_locked = False

            if event.button == 1:
                self.on_left_mouse_button_down_event(event)
            if event.button == 2:
                self.on_middle_mouse_button_down_event(event)
            if event.button == 3:
                self.on_right_mouse_button_down_event(event)
            if event.button == 4:
                self.on_mouse_scroll_down_event(event)
            if event.button == 5:
                self.on_mouse_scroll_up_event(event)

            self.game.on_mouse_button_down_event(event)

        def on_left_mouse_button_down_event(self, event):
            self.game.on_left_mouse_button_down_event(event)

        def on_middle_mouse_button_down_event(self, event):
            self.game.on_middle_mouse_button_down_event(event)

        def on_right_mouse_button_down_event(self, event):
            self.game.on_right_mouse_button_down_event(event)

        def on_mouse_scroll_down_event(self, event):
            self.game.on_mouse_scroll_down_event(event)

        def on_mouse_scroll_up_event(self, event):
            self.game.on_mouse_scroll_up_event(event)

    def __init__(self, game=None):
        """
        Mouse event manager.

        MouseManager interfaces GameEngine with MouseManager.MouseManagerProxy.

        Args:
        ----
        game - The game instance.

        """
        super().__init__(game=game)
        self.proxies = [MouseManager.MouseProxy(game=game)]
