"""Slider and color well management for the Bitmappy editor.

Handles slider setup, hover effects, text input, color sampling, and all
slider-related UI interactions. Extracted from BitmapEditorScene to reduce
class complexity.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pygame

from glitchygames import events
from glitchygames.color import (
    MAX_COLOR_CHANNEL_VALUE,
    RGBA_COMPONENT_COUNT,
)
from glitchygames.sprites import (
    BitmappySprite,
)
from glitchygames.ui import (
    ColorWellSprite,
    SliderSprite,
    TabControlSprite,
    TextSprite,
)

from .constants import (
    LOG,
    MAX_COLOR_VALUE,
    MIN_COLOR_VALUE,
)

if TYPE_CHECKING:
    from .protocols import EditorContext


class SliderManager:
    """Manages slider and color well UI for the Bitmappy editor.

    Handles slider creation, hover effects, text input, color sampling,
    and all slider-related interactions. Operates on editor state via the
    editor reference passed at construction time.
    """

    def __init__(self, editor: EditorContext) -> None:
        """Initialize the SliderManager.

        Args:
            editor: The editor context providing access to shared state.

        """
        self.editor = editor
        self.log = logging.getLogger('game.tools.bitmappy.slider_manager')
        self.log.addHandler(logging.NullHandler())

        # State owned by SliderManager (labels and bounding boxes)
        self.alpha_label: TextSprite | None = None
        self.red_label: TextSprite | None = None
        self.green_label: TextSprite | None = None
        self.blue_label: TextSprite | None = None

        self.alpha_slider_bbox: BitmappySprite | None = None
        self.red_slider_bbox: BitmappySprite | None = None
        self.green_slider_bbox: BitmappySprite | None = None
        self.blue_slider_bbox: BitmappySprite | None = None

    # ──────────────────────────────────────────────────────────────────────
    # Setup
    # ──────────────────────────────────────────────────────────────────────

    def setup_sliders_and_color_well(self) -> None:
        """Set up the color sliders and color well."""
        # First create the sliders
        slider_height = 9
        slider_width = 256
        slider_x = 13  # Moved 3 pixels to the right
        label_padding = 10  # Padding between slider and label
        well_padding = 20  # Padding between labels and color well

        # Create the sliders - positioned so blue slider bottom touches screen bottom
        # Account for bounding box height (slider_height + 4) in positioning
        # Blue slider bottom should be at screen_height - 2 (one pixel up from last visible row)
        bbox_height = slider_height + 4
        blue_slider_y = (
            self.editor.screen_height - slider_height - 2
        )  # Bottom edge at screen_height - 2
        green_slider_y = blue_slider_y - bbox_height  # Use bounding box height for spacing
        red_slider_y = green_slider_y - bbox_height  # Use bounding box height for spacing
        alpha_slider_y = red_slider_y - bbox_height  # Alpha slider above red slider

        slider_y_positions = {
            'alpha': alpha_slider_y,
            'red': red_slider_y,
            'green': green_slider_y,
            'blue': blue_slider_y,
        }

        self._create_slider_labels(
            slider_x=slider_x,
            slider_height=slider_height,
            slider_y_positions=slider_y_positions,
        )

        self._create_slider_sprites(
            slider_x=slider_x,
            slider_width=slider_width,
            slider_height=slider_height,
            slider_y_positions=slider_y_positions,
        )

        self._create_slider_bounding_boxes(
            slider_x=slider_x,
            slider_width=slider_width,
            slider_height=slider_height,
            slider_y_positions=slider_y_positions,
        )

        # Create the color well positioned to the right of the text labels
        # Calculate x position to the right of the text labels
        # Text labels are at: slider_x + slider_width + label_padding
        text_label_x = slider_x + slider_width + label_padding
        color_well_x = text_label_x + well_padding  # Add padding after text labels

        self._create_color_well_and_tab_control(
            color_well_x=color_well_x,
            red_slider_y=red_slider_y,
            blue_slider_y=blue_slider_y,
            slider_height=slider_height,
        )

        self._configure_slider_text_boxes(
            text_label_x=text_label_x,
            color_well_x=color_well_x,
        )

        self._initialize_slider_values()

    def _create_slider_labels(
        self,
        *,
        slider_x: int,
        slider_height: int,
        slider_y_positions: dict[str, int],
    ) -> None:
        """Create text labels for each color slider.

        Args:
            slider_x: X position of sliders
            slider_height: Height of each slider
            slider_y_positions: Dict mapping color names to Y positions

        """
        # Create text labels for each slider
        label_x = (
            slider_x - 13
        )  # Position labels to the left of sliders (moved 7 pixels right total)
        label_width = 16  # Width for text labels
        label_height = 16  # Height for text labels

        from glitchygames.fonts import FontManager

        monospace_config = {'font_name': 'Courier', 'font_size': 14}

        # Alpha slider label
        self.alpha_label = TextSprite(
            text='A',
            x=label_x - 2,  # Move A label 2 pixels left (same as R and G)
            y=slider_y_positions['alpha'] + (slider_height - label_height) // 2,
            width=label_width,
            height=label_height,
            background_color=(0, 0, 0, 0),  # Transparent background
            text_color=(255, 255, 255),  # White text
            alpha=0,  # Transparent
            groups=self.editor.all_sprites,
        )
        # Set monospaced font for the label
        self.alpha_label.font = FontManager.get_font(font_config=monospace_config)

        # Red slider label
        self.red_label = TextSprite(
            text='R',
            x=label_x - 2,  # Move R label 2 pixels left
            y=slider_y_positions['red'] + (slider_height - label_height) // 2,
            width=label_width,
            height=label_height,
            background_color=(0, 0, 0, 0),  # Transparent background
            text_color=(255, 255, 255),  # White text
            alpha=0,  # Transparent
            groups=self.editor.all_sprites,
        )
        # Set monospaced font for the label
        self.red_label.font = FontManager.get_font(font_config=monospace_config)

        # Green slider label
        self.green_label = TextSprite(
            text='G',
            x=label_x - 2,  # Move G label 2 pixels left
            y=slider_y_positions['green'] + (slider_height - label_height) // 2,
            width=label_width,
            height=label_height,
            background_color=(0, 0, 0, 0),  # Transparent background
            text_color=(255, 255, 255),  # White text
            alpha=0,  # Transparent
            groups=self.editor.all_sprites,
        )
        # Set monospaced font for the label
        self.green_label.font = FontManager.get_font(font_config=monospace_config)

        # Blue slider label
        self.blue_label = TextSprite(
            text='B',
            x=label_x - 1,  # Adjust B label 1 pixel left to align with R and G
            y=slider_y_positions['blue'] + (slider_height - label_height) // 2,
            width=label_width,
            height=label_height,
            background_color=(0, 0, 0, 0),  # Transparent background
            text_color=(255, 255, 255),  # White text
            alpha=0,  # Transparent
            groups=self.editor.all_sprites,
        )
        # Set monospaced font for the label
        self.blue_label.font = FontManager.get_font(font_config=monospace_config)

    def _create_slider_sprites(
        self,
        *,
        slider_x: int,
        slider_width: int,
        slider_height: int,
        slider_y_positions: dict[str, int],
    ) -> None:
        """Create the ARGB slider sprites.

        Args:
            slider_x: X position of sliders
            slider_width: Width of each slider
            slider_height: Height of each slider
            slider_y_positions: Dict mapping color names to Y positions

        """
        self.editor.alpha_slider = SliderSprite(
            name='A',
            x=slider_x,
            y=slider_y_positions['alpha'],
            width=slider_width,
            height=slider_height,
            parent=self.editor,  # type: ignore[reportArgumentType] # ty: ignore[invalid-argument-type]  # BitmapEditorScene satisfies SliderProtocol at runtime
            groups=self.editor.all_sprites,
        )

        self.editor.red_slider = SliderSprite(
            name='R',
            x=slider_x,
            y=slider_y_positions['red'],
            width=slider_width,
            height=slider_height,
            parent=self.editor,  # type: ignore[reportArgumentType] # ty: ignore[invalid-argument-type]  # BitmapEditorScene satisfies SliderProtocol at runtime
            groups=self.editor.all_sprites,
        )

        self.editor.green_slider = SliderSprite(
            name='G',
            x=slider_x,
            y=slider_y_positions['green'],
            width=slider_width,
            height=slider_height,
            parent=self.editor,  # type: ignore[reportArgumentType] # ty: ignore[invalid-argument-type]  # BitmapEditorScene satisfies SliderProtocol at runtime
            groups=self.editor.all_sprites,
        )

        self.editor.blue_slider = SliderSprite(
            name='B',
            x=slider_x,
            y=slider_y_positions['blue'],
            width=slider_width,
            height=slider_height,
            parent=self.editor,  # type: ignore[reportArgumentType] # ty: ignore[invalid-argument-type]  # BitmapEditorScene satisfies SliderProtocol at runtime
            groups=self.editor.all_sprites,
        )

    def _create_slider_bounding_boxes(
        self,
        *,
        slider_x: int,
        slider_width: int,
        slider_height: int,
        slider_y_positions: dict[str, int],
    ) -> None:
        """Create bounding boxes around the sliders for hover effects (initially hidden).

        Args:
            slider_x: X position of sliders
            slider_width: Width of each slider
            slider_height: Height of each slider
            slider_y_positions: Dict mapping color names to Y positions

        """
        bbox_configs = [
            ('alpha_slider_bbox', 'Alpha Slider BBox', slider_y_positions['alpha']),
            ('red_slider_bbox', 'Red Slider BBox', slider_y_positions['red']),
            ('green_slider_bbox', 'Green Slider BBox', slider_y_positions['green']),
            ('blue_slider_bbox', 'Blue Slider BBox', slider_y_positions['blue']),
        ]

        for attr_name, bbox_name, bbox_y in bbox_configs:
            bbox_sprite = BitmappySprite(
                x=slider_x - 2,
                y=bbox_y - 2,
                width=slider_width + 4,
                height=slider_height + 4,
                name=bbox_name,
                groups=self.editor.all_sprites,
            )
            # Create transparent surface (no border initially)
            bbox_sprite.image = pygame.Surface(
                (slider_width + 4, slider_height + 4),
                pygame.SRCALPHA,
            )
            bbox_sprite.visible = False  # Start hidden
            # Update bounding box position to match slider position
            bbox_sprite.rect.y = bbox_y - 2
            setattr(self, attr_name, bbox_sprite)

    def _create_color_well_and_tab_control(
        self,
        *,
        color_well_x: int,
        red_slider_y: int,
        blue_slider_y: int,
        slider_height: int,
    ) -> None:
        """Create the color well and format tab control.

        Args:
            color_well_x: X position for the color well
            red_slider_y: Y position of the red slider
            blue_slider_y: Y position of the blue slider
            slider_height: Height of each slider

        """
        # Position colorwell so its top y matches R slider's top y
        # and its bottom y is shorter than blue slider's bottom y
        blue_slider_bottom_y = blue_slider_y + slider_height
        color_well_y = red_slider_y - 5  # Add some padding above
        color_well_height = (
            blue_slider_bottom_y - color_well_y
        ) + 2  # 2 pixels taller than B slider's bottom y

        # Calculate canvas right edge position
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            canvas_right_x = self.editor.canvas.pixels_across * self.editor.canvas.pixel_width
        else:
            # Fallback for tests or when canvas isn't initialized yet
            canvas_right_x = self.editor.screen_width - 20
        # Set colorwell width so its right edge aligns with canvas right edge
        color_well_width = canvas_right_x - color_well_x
        # Ensure minimum width to prevent invalid surface creation
        color_well_width = max(color_well_width, 50)
        # Ensure minimum height to prevent invalid surface creation (reduced from 50)
        color_well_height = max(color_well_height, 20)

        self.editor.color_well = ColorWellSprite(
            name='Color Well',
            x=color_well_x,
            y=color_well_y,  # Top y matches R slider's top y
            width=color_well_width,
            height=color_well_height,  # Height spans from R top to G bottom
            parent=self.editor,
            groups=self.editor.all_sprites,
        )

        # Create tab control positioned above the color well
        tab_control_width = color_well_width  # Match the color well width
        tab_control_height = 20
        tab_control_x = (
            color_well_x + (color_well_width - tab_control_width) // 2
        )  # Center horizontally
        tab_control_y = (
            color_well_y - tab_control_height
        )  # Position so bottom touches top of color well

        self.editor.tab_control = TabControlSprite(
            name='Format Tab Control',
            x=tab_control_x,
            y=tab_control_y,
            width=tab_control_width,
            height=tab_control_height,
            parent=self.editor,  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]  # BitmapEditorScene implements TabProtocol
            groups=self.editor.all_sprites,
        )

    def _configure_slider_text_boxes(
        self,
        *,
        text_label_x: int,
        color_well_x: int,
    ) -> None:
        """Configure slider text box widths and heights to fit the layout.

        Args:
            text_label_x: X position of the text labels
            color_well_x: X position of the color well

        """
        # Initialize slider input format (default to decimal)
        self.editor.slider_input_format = '%d'

        # Update text box widths to fit between slider end and color well start
        text_box_width = color_well_x - text_label_x + 4  # Make 4 pixels wider
        # Shrink text boxes vertically by 4 pixels
        text_box_height = 16  # Original was 20, now 16 (4 pixels smaller)

        for slider in (
            self.editor.alpha_slider,
            self.editor.red_slider,
            self.editor.green_slider,
            self.editor.blue_slider,
        ):
            slider.text_sprite.width = text_box_width
            slider.text_sprite.height = text_box_height
            # Force text sprites to update with new dimensions
            slider.text_sprite.update_text(slider.text_sprite.text)

    def _initialize_slider_values(self) -> None:
        """Initialize slider default values and sync with color well."""
        self.editor.alpha_slider.value = 255
        self.editor.red_slider.value = 0
        self.editor.blue_slider.value = 0
        self.editor.green_slider.value = 0

        self.editor.color_well.active_color = (
            self.editor.red_slider.value,
            self.editor.green_slider.value,
            self.editor.blue_slider.value,
            self.editor.alpha_slider.value,
        )

        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            self.editor.canvas.active_color = self.editor.color_well.active_color  # type: ignore[assignment]

    # ──────────────────────────────────────────────────────────────────────
    # Hover effects
    # ──────────────────────────────────────────────────────────────────────

    def _is_slider_hovered(self, slider_name: str, mouse_pos: tuple[int, int]) -> bool:
        """Check if the mouse is hovering over a slider.

        Args:
            slider_name: The slider attribute name (e.g., "alpha_slider")
            mouse_pos: The current mouse position (x, y)

        Returns:
            True if the mouse is hovering over the slider.

        """
        return hasattr(self.editor, slider_name) and getattr(
            self.editor,
            slider_name,
        ).rect.collidepoint(mouse_pos)

    def _is_slider_text_hovered(self, slider_name: str, mouse_pos: tuple[int, int]) -> bool:
        """Check if the mouse is hovering over a slider's text sprite.

        Uses absolute coordinates for text sprites.

        Args:
            slider_name: The slider attribute name (e.g., "alpha_slider")
            mouse_pos: The current mouse position (x, y)

        Returns:
            True if the mouse is hovering over the slider's text sprite.

        """
        if not hasattr(self.editor, slider_name):
            return False
        slider = getattr(self.editor, slider_name)
        return hasattr(slider, 'text_sprite') and slider.text_sprite.rect.collidepoint(mouse_pos)

    def _draw_alpha_slider_gradient_border(self, bbox: BitmappySprite) -> None:
        """Draw a gradient border on the alpha slider bounding box.

        The gradient goes from right (opaque) to left (transparent).

        Args:
            bbox: The alpha slider bounding box sprite

        """
        bbox.image.fill((0, 0, 0, 0))  # Clear surface

        # Draw individual pixels to create gradient effect
        width = bbox.rect.width
        height = bbox.rect.height

        # Draw border pixels with fixed gradient from right (255) to left (0)
        for x in range(int(width)):
            # Calculate opacity based on position: right side = 255, left side = 0
            pixel_alpha = int((255 * x) / width) if width > 0 else 0
            pixel_color = (pixel_alpha, 0, pixel_alpha, pixel_alpha)  # RGBA

            # Draw top and bottom border lines
            if x < width - 1:  # Don't draw the last pixel to avoid overlap
                bbox.image.set_at((x, 0), pixel_color)  # Top border
                bbox.image.set_at((x, height - 1), pixel_color)  # Bottom border

        # Draw left and right border lines
        for y in range(int(height)):
            # Left border (transparent)
            bbox.image.set_at((0, y), (0, 0, 0, 0))  # Transparent
            # Right border (opaque magenta)
            right_color = (255, 0, 255, 255)
            bbox.image.set_at((width - 1, y), right_color)

        bbox.visible = True
        bbox.dirty = 1

    def _update_slider_bbox_hover(
        self,
        bbox_attr: str,
        *,
        is_hovered: bool,
        border_color: tuple[int, int, int],
    ) -> None:
        """Update a slider bounding box border based on hover state.

        Args:
            bbox_attr: The bounding box attribute name (e.g., "red_slider_bbox")
            is_hovered: Whether the mouse is currently hovering over the slider
            border_color: The RGB color for the border

        """
        if not hasattr(self, bbox_attr):
            return

        bbox = getattr(self, bbox_attr)
        if is_hovered and not bbox.visible:
            bbox.image.fill((0, 0, 0, 0))  # Clear surface
            pygame.draw.rect(
                bbox.image,
                border_color,
                (0, 0, bbox.rect.width, bbox.rect.height),
                2,
            )
            bbox.visible = True
            bbox.dirty = 1
        elif not is_hovered and bbox.visible:
            bbox.image.fill((0, 0, 0, 0))  # Clear surface
            bbox.visible = False
            bbox.dirty = 1

    def _update_slider_text_hover_border(self, slider_name: str, *, is_text_hovered: bool) -> None:
        """Update a slider text sprite's white hover border.

        Args:
            slider_name: The slider attribute name (e.g., "red_slider")
            is_text_hovered: Whether the mouse is hovering over the text sprite

        """
        if not (
            hasattr(self.editor, slider_name)
            and hasattr(getattr(self.editor, slider_name), 'text_sprite')
        ):
            return

        text_sprite = getattr(self.editor, slider_name).text_sprite
        if is_text_hovered:
            # Add white border to text sprite
            if not hasattr(text_sprite, 'hover_border_added'):
                # Create a white border by drawing on the text sprite's image
                pygame.draw.rect(
                    text_sprite.image,
                    (255, 255, 255),
                    (0, 0, text_sprite.rect.width, text_sprite.rect.height),
                    2,
                )
                text_sprite.hover_border_added = True
                text_sprite.dirty = 1
        # Remove white border
        elif hasattr(text_sprite, 'hover_border_added') and text_sprite.hover_border_added:
            # Force text sprite to redraw without border
            text_sprite.update_text(text_sprite.text)
            text_sprite.hover_border_added = False
            text_sprite.dirty = 1

    def update_slider_hover_effects(self, mouse_pos: tuple[int, int]) -> None:
        """Update slider hover effects based on mouse position.

        Args:
            mouse_pos: The current mouse position (x, y)

        """
        # Check if mouse is hovering over any slider
        alpha_hover = self._is_slider_hovered('alpha_slider', mouse_pos)
        red_hover = self._is_slider_hovered('red_slider', mouse_pos)
        green_hover = self._is_slider_hovered('green_slider', mouse_pos)
        blue_hover = self._is_slider_hovered('blue_slider', mouse_pos)

        # Update alpha slider border (uses gradient, not solid border)
        if self.alpha_slider_bbox is not None:
            if alpha_hover and not self.alpha_slider_bbox.visible:
                self._draw_alpha_slider_gradient_border(self.alpha_slider_bbox)
            elif not alpha_hover and self.alpha_slider_bbox.visible:
                # Hide alpha border
                self.alpha_slider_bbox.image.fill((0, 0, 0, 0))  # Clear surface
                self.alpha_slider_bbox.visible = False
                self.alpha_slider_bbox.dirty = 1

        # Update colored slider borders
        self._update_slider_bbox_hover(
            'red_slider_bbox',
            is_hovered=red_hover,
            border_color=(255, 0, 0),
        )
        self._update_slider_bbox_hover(
            'green_slider_bbox',
            is_hovered=green_hover,
            border_color=(0, 255, 0),
        )
        self._update_slider_bbox_hover(
            'blue_slider_bbox',
            is_hovered=blue_hover,
            border_color=(0, 0, 255),
        )

        # Update text box hover effects (white borders)
        # Check if mouse is hovering over any slider text boxes (use absolute coordinates)
        slider_names = ['alpha_slider', 'red_slider', 'green_slider', 'blue_slider']
        for slider_name in slider_names:
            text_hovered = self._is_slider_text_hovered(slider_name, mouse_pos)
            self._update_slider_text_hover_border(slider_name, is_text_hovered=text_hovered)

    # ──────────────────────────────────────────────────────────────────────
    # Events
    # ──────────────────────────────────────────────────────────────────────

    def on_slider_event(self, event: events.HashableEvent, trigger: events.HashableEvent) -> None:
        """Handle the slider event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (HashableEvent): The slider trigger (typically a SliderSprite).

        Raises:
            None

        """
        value = trigger.value

        self.log.debug('Slider: event: %s, trigger: %s value: %s', event, trigger, value)

        if value < MIN_COLOR_VALUE:
            value = MIN_COLOR_VALUE
            trigger.value = MIN_COLOR_VALUE  # pyright: ignore[reportAttributeAccessIssue] # ty: ignore[unresolved-attribute]
        elif value > MAX_COLOR_VALUE:
            value = MAX_COLOR_VALUE
            trigger.value = MAX_COLOR_VALUE  # pyright: ignore[reportAttributeAccessIssue] # ty: ignore[unresolved-attribute]

        if trigger.name == 'R':
            self.editor.red_slider.value = value
            self.log.debug('Updated red slider to: %s', value)
        elif trigger.name == 'G':
            self.editor.green_slider.value = value
            self.log.debug('Updated green slider to: %s', value)
        elif trigger.name == 'B':
            self.editor.blue_slider.value = value
            self.log.debug('Updated blue slider to: %s', value)
        elif trigger.name == 'A':
            self.editor.alpha_slider.value = value
            self.log.debug('Updated alpha slider to: %s', value)

        # Update slider text to reflect current tab format
        # This handles slider clicks - text input is handled by SliderSprite itself
        self._update_slider_text_format()

        # Debug: Log current slider values
        self.log.debug(
            f'Current slider values - R: {self.editor.red_slider.value}, '
            f'G: {self.editor.green_slider.value}, B: {self.editor.blue_slider.value}, A:'
            f' {self.editor.alpha_slider.value}',
        )

        self.editor.color_well.active_color = (
            self.editor.red_slider.value,
            self.editor.green_slider.value,
            self.editor.blue_slider.value,
            self.editor.alpha_slider.value,
        )
        self.editor.canvas.active_color = (  # type: ignore[assignment]
            self.editor.red_slider.value,
            self.editor.green_slider.value,
            self.editor.blue_slider.value,
            self.editor.alpha_slider.value,
        )

    def on_color_well_event(self, _event: events.HashableEvent, _trigger: object) -> None:
        """Handle the color well event."""
        self.log.info('COLOR WELL EVENT')

    def _update_slider_text_format(self, tab_format: str | None = None) -> None:
        """Update slider text display format.

        Args:
            tab_format (str): The format to use ("%X" for hex, "%d" for decimal).
                             If None, uses the current slider_input_format.

        """
        if tab_format is None:
            tab_format = getattr(self.editor, 'slider_input_format', '%d')

        if hasattr(self.editor, 'red_slider') and hasattr(self.editor.red_slider, 'text_sprite'):
            if tab_format == '%X':
                # Convert to hex
                self.editor.red_slider.text_sprite.text = f'{self.editor.red_slider.value:02X}'
            else:
                # Convert to decimal
                self.editor.red_slider.text_sprite.text = str(self.editor.red_slider.value)
            self.editor.red_slider.text_sprite.update_text(self.editor.red_slider.text_sprite.text)

        if hasattr(self.editor, 'green_slider') and hasattr(
            self.editor.green_slider,
            'text_sprite',
        ):
            if tab_format == '%X':
                # Convert to hex
                self.editor.green_slider.text_sprite.text = f'{self.editor.green_slider.value:02X}'
            else:
                # Convert to decimal
                self.editor.green_slider.text_sprite.text = str(self.editor.green_slider.value)
            self.editor.green_slider.text_sprite.update_text(
                self.editor.green_slider.text_sprite.text,
            )

        if hasattr(self.editor, 'blue_slider') and hasattr(self.editor.blue_slider, 'text_sprite'):
            if tab_format == '%X':
                # Convert to hex
                self.editor.blue_slider.text_sprite.text = f'{self.editor.blue_slider.value:02X}'
            else:
                # Convert to decimal
                self.editor.blue_slider.text_sprite.text = str(self.editor.blue_slider.value)
            self.editor.blue_slider.text_sprite.update_text(
                self.editor.blue_slider.text_sprite.text,
            )

    # ──────────────────────────────────────────────────────────────────────
    # Interaction
    # ──────────────────────────────────────────────────────────────────────

    def detect_clicked_slider(self, mouse_pos: tuple[int, int]) -> str | None:
        """Detect which slider text box was clicked.

        Args:
            mouse_pos: The mouse position (x, y)

        Returns:
            The name of the clicked slider ("red", "green", "blue") or None.

        """
        slider_names = ['red', 'green', 'blue']
        for name in slider_names:
            slider_attr = f'{name}_slider'
            if (
                hasattr(self.editor, slider_attr)
                and hasattr(getattr(self.editor, slider_attr), 'text_sprite')
                and getattr(self.editor, slider_attr).text_sprite.rect.collidepoint(mouse_pos)
            ):
                return name
        return None

    def commit_and_deactivate_slider(
        self,
        slider: SliderSprite,
        clicked_slider: str | None,
        slider_name: str,
    ) -> None:
        """Commit the slider text value and deactivate the text sprite.

        Commits the current text input on a slider's text sprite, parsing as hex or
        decimal as appropriate, then deactivates the text sprite.

        Args:
            slider: The slider object with text_sprite attribute
            clicked_slider: Name of the slider that was clicked, or None
            slider_name: Name of this slider ("red", "green", "blue")

        """
        if not (
            hasattr(slider, 'text_sprite')
            and slider.text_sprite.is_active
            and (clicked_slider != slider_name or clicked_slider is None)
        ):
            return

        # Commit any uncommitted value before deactivating
        if not slider.text_sprite.text.strip():
            # If empty, restore original value
            slider.text_sprite.text = str(slider.original_value)
        else:
            # Try to commit the current text value - parse as hex if contains letters, otherwise
            # decimal
            try:
                text = slider.text_sprite.text.strip().lower()
                # Parse as hex if contains hex letters, otherwise decimal
                new_value = int(text, 16) if any(c in 'abcdef' for c in text) else int(text)

                if 0 <= new_value <= MAX_COLOR_CHANNEL_VALUE:
                    slider.value = new_value
                    # Update original value for future validations
                    slider.original_value = new_value
                    # Convert text to appropriate format based on selected tab
                    LOG.debug(
                        f'DEBUG: Current slider_input_format: {self.editor.slider_input_format}',
                    )
                    if self.editor.slider_input_format == '%X':
                        slider.text_sprite.text = f'{new_value:02X}'
                        LOG.debug(
                            f'DEBUG: Converting {new_value} to hex: {slider.text_sprite.text}',
                        )
                    else:
                        slider.text_sprite.text = str(new_value)
                        LOG.debug(
                            f'DEBUG: Converting {new_value} to decimal: {slider.text_sprite.text}',
                        )
                    slider.text_sprite.update_text(slider.text_sprite.text)
                    slider.text_sprite.dirty = 2  # Force redraw
                else:
                    # Invalid range, restore original
                    slider.text_sprite.text = str(slider.original_value)
            except ValueError:
                # Invalid input, restore original
                slider.text_sprite.text = str(slider.original_value)

        slider.text_sprite.is_active = False
        slider.text_sprite.update_text(slider.text_sprite.text)

    def handle_slider_text_input(self, event: events.HashableEvent) -> bool | None:
        """Handle text input for active slider text boxes.

        Args:
            event: The key down event.

        Returns:
            True if escape was pressed (consume event), None if handled but not escape,
            or False if no slider text box was active.

        """
        sliders = ['red_slider', 'green_slider', 'blue_slider', 'alpha_slider']
        for slider_name in sliders:
            slider = getattr(self.editor, slider_name, None)
            if (
                slider is not None
                and hasattr(slider, 'text_sprite')
                and slider.text_sprite.is_active
            ):
                slider.text_sprite.on_key_down_event(event)
                # If escape was pressed, consume the event to prevent game quit
                if event.key == pygame.K_ESCAPE:
                    return True
                return None
        return False

    # ──────────────────────────────────────────────────────────────────────
    # Color API
    # ──────────────────────────────────────────────────────────────────────

    def get_current_color(self) -> tuple[int, ...]:
        """Get the current color from the color picker.

        Returns:
            tuple: The current color.

        """
        # Get color from sliders if available
        if (
            hasattr(self.editor, 'red_slider')
            and hasattr(self.editor, 'green_slider')
            and hasattr(self.editor, 'blue_slider')
        ):
            try:
                red = int(self.editor.red_slider.value)
                green = int(self.editor.green_slider.value)
                blue = int(self.editor.blue_slider.value)
                self.log.debug(
                    'DEBUG: _get_current_color() returning color from sliders: (%s, %s, %s)',
                    red,
                    green,
                    blue,
                )
            except (ValueError, AttributeError) as e:
                self.log.debug('DEBUG: _get_current_color() error getting slider values: %s', e)
            else:
                return (red, green, blue)

        # Default to white if sliders not available
        self.log.debug('DEBUG: _get_current_color() sliders not available, returning white')
        return (255, 255, 255)

    def update_color_well_from_sliders(self) -> None:
        """Update the color well with current slider values."""
        self.log.debug('DEBUG: _update_color_well_from_sliders called')
        if hasattr(self.editor, 'color_well') and self.editor.color_well:
            # Get current slider values
            red_value = self.editor.red_slider.value if hasattr(self.editor, 'red_slider') else 0
            green_value = (
                self.editor.green_slider.value if hasattr(self.editor, 'green_slider') else 0
            )
            blue_value = self.editor.blue_slider.value if hasattr(self.editor, 'blue_slider') else 0
            alpha_value = (
                self.editor.alpha_slider.value if hasattr(self.editor, 'alpha_slider') else 0
            )

            self.log.debug(
                'DEBUG: Slider values - R:%s, G:%s, B:%s, A:%s',
                red_value,
                green_value,
                blue_value,
                alpha_value,
            )
            self.log.debug(
                f'DEBUG: Color well before update: {self.editor.color_well.active_color}',
            )

            # Update color well
            self.editor.color_well.active_color = (red_value, green_value, blue_value, alpha_value)

            # Force color well to redraw
            if hasattr(self.editor.color_well, 'dirty'):
                self.editor.color_well.dirty = 1

            # Also dirty the main scene to ensure redraw
            self.editor.dirty = 1

            # Force color well to update its display
            if hasattr(self.editor.color_well, 'force_redraw'):
                self.editor.color_well.force_redraw()  # type: ignore[union-attr] # ty: ignore[call-non-callable]

            self.log.debug(
                'DEBUG: Updated color well to (%s, %s, %s)',
                red_value,
                green_value,
                blue_value,
            )
        else:
            self.log.debug('DEBUG: No color_well found or color_well is None')

    def sample_color_from_screen(self, screen_pos: tuple[int, int]) -> None:
        """Sample color directly from the screen (RGB only, ignores alpha).

        Args:
            screen_pos: Screen coordinates (x, y) to sample from

        """
        try:
            # Sample directly from the screen
            assert self.editor.screen is not None
            color = self.editor.screen.get_at(screen_pos)

            # Handle both RGB and RGBA screen formats
            if len(color) == RGBA_COMPONENT_COUNT:
                red, green, blue, _ = color  # Ignore alpha from screen
            else:
                red, green, blue = color
            alpha = 255  # Screen has no meaningful alpha, default to opaque

            self.log.info(
                'Screen pixel sampled - Red: %s, Green: %s, Blue: %s, Alpha: %s (default)',
                red,
                green,
                blue,
                alpha,
            )

            # Update all sliders with the sampled RGB values and default alpha
            trigger = events.HashableEvent(0, name='R', value=red)
            self.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

            trigger = events.HashableEvent(0, name='G', value=green)
            self.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

            trigger = events.HashableEvent(0, name='B', value=blue)
            self.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

            trigger = events.HashableEvent(0, name='A', value=alpha)
            self.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

            self.log.info(
                'Updated sliders with screen color R:%s, G:%s, B:%s, A:%s',
                red,
                green,
                blue,
                alpha,
            )

        except Exception:
            self.log.exception('Error sampling color from screen')

    # ──────────────────────────────────────────────────────────────────────
    # Controller check
    # ──────────────────────────────────────────────────────────────────────

    def is_any_controller_in_slider_mode(self) -> bool:
        """Check if any controller is currently in slider mode.

        Returns:
            True if at least one controller is in a slider mode.

        """
        if not hasattr(self.editor, 'mode_switcher'):
            return False

        for controller_id in self.editor.mode_switcher.controller_modes:
            controller_mode = self.editor.mode_switcher.get_controller_mode(controller_id)
            if controller_mode and controller_mode.value in {
                'r_slider',
                'g_slider',
                'b_slider',
            }:
                return True
        return False

    # ──────────────────────────────────────────────────────────────────────
    # Tab change handling
    # ──────────────────────────────────────────────────────────────────────

    def on_tab_change_event(self, tab_format: str) -> None:
        """Handle tab control format change.

        Args:
            tab_format (str): The selected format ("%d" or "%H")

        """
        self.log.info('Tab control changed to format: %s', tab_format)

        # Store the current format for slider text input
        self.editor.slider_input_format = tab_format

        # Update slider text display format if they have values
        self._update_slider_text_format(tab_format)
