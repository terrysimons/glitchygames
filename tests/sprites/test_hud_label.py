"""glitchygames/sprites/hud_label.py: a line of HUD text as a sprite, rendered when it changes.

The pixel tests draw the labels with a real ``LayeredDirty`` group onto a surface and compare it
with what Brave Adventurer's and Clockwork Keep's HUDs drew before they became sprites: each
text rendered and blitted straight onto the screen, its shadow first.
"""

from __future__ import annotations

import pydantic
import pygame
import pytest

from glitchygames.fonts import font_manager
from glitchygames.sprites import RootSprite
from glitchygames.sprites.hud_label import HudAnchor, HudLabel, HudLabelStyle
from glitchygames.world import CoordinateSpace, is_world_positioned

TEXT_COLOR = (255, 255, 255)
SHADOW_COLOR = (0, 0, 0)
BACKGROUND = (40, 90, 160)
SCREEN_WIDTH = 800
HUD_LAYER = 9


@pytest.fixture
def font() -> pygame.font.Font:
    """Return the font both games' HUDs use.

    Returns:
        The default font at 28 points.

    """
    return pygame.font.Font(None, 28)


@pytest.fixture
def group() -> pygame.sprite.LayeredDirty:
    """Return an empty sprite group, as a scene holds its sprites.

    Returns:
        The group.

    """
    return pygame.sprite.LayeredDirty()


def _label(font, group, *, text='Score: 0', position=(10, 10), **look) -> HudLabel:
    return HudLabel(
        groups=group,
        text=text,
        position=position,
        style=HudLabelStyle(font=font, color=TEXT_COLOR, **look),
    )


def _drawn(group: pygame.sprite.LayeredDirty) -> bytes:
    surface = pygame.Surface((SCREEN_WIDTH, 60))
    surface.fill(BACKGROUND)
    group.draw(surface)
    return pygame.image.tobytes(surface, 'RGB')


def _blitted(font, *blits: tuple[str, tuple[int, int], tuple[int, int, int]]) -> bytes:
    """Return a surface with each text rendered and blitted straight on, as the HUDs did."""
    surface = pygame.Surface((SCREEN_WIDTH, 60))
    surface.fill(BACKGROUND)
    antialias = font_manager.FontManager.antialias()
    for text, position, color in blits:
        surface.blit(font.render(text, antialias, color), position)
    return pygame.image.tobytes(surface, 'RGB')


class TestRendering:
    """A label renders its text once, and again only when the text changes."""

    def test_a_label_renders_once_and_not_again_while_its_text_is_unchanged(
        self, font, group, mocker
    ):
        render_line = mocker.spy(font_manager, 'render_line')
        label = _label(font, group)
        label.text = 'Score: 0'
        label.text = 'Score: 0'
        assert render_line.call_count == 1

    def test_a_label_renders_again_when_its_text_changes(self, font, group, mocker):
        label = _label(font, group)
        render_line = mocker.spy(font_manager, 'render_line')
        label.text = 'Score: 100'
        render_line.assert_called_once_with(font=font, text='Score: 100', color=TEXT_COLOR)
        assert label.text == 'Score: 100'
        # The rendered line's size (pygame's Font.size can report a shorter height)
        assert (
            label.rect.size
            == font.render('Score: 100', antialias=True, color=TEXT_COLOR).get_size()
        )

    def test_its_shadow_follows_its_text(self, font, group):
        label = _label(font, group, shadow_color=SHADOW_COLOR)
        label.text = 'Score: 250'
        assert label.shadow is not None
        assert label.shadow.text == 'Score: 250'


class TestAnchors:
    """Where a label sits as its width changes."""

    def test_top_left_keeps_its_left_edge(self, font, group):
        label = _label(font, group, position=(SCREEN_WIDTH - 110, 10))
        label.text = 'Lives: 10'
        assert label.rect.topleft == (SCREEN_WIDTH - 110, 10)

    @pytest.mark.parametrize('text', ['Floor: The Gatehouse', 'Floor: Gears', 'Floor: X'])
    def test_top_center_centres_as_clockwork_did(self, font, group, text):
        """(screen width - text width) // 2: a pixel left of rect.centerx for an odd width."""
        label = _label(font, group, position=(SCREEN_WIDTH // 2, 10), anchor=HudAnchor.TOP_CENTER)
        label.text = text
        assert label.rect.topleft == ((SCREEN_WIDTH - font.size(text)[0]) // 2, 10)

    def test_top_right_keeps_its_right_edge(self, font, group):
        label = _label(font, group, position=(SCREEN_WIDTH - 10, 10), anchor=HudAnchor.TOP_RIGHT)
        label.text = 'Lives: 3'
        assert label.rect.topright == (SCREEN_WIDTH - 10, 10)
        label.text = 'Lives: 30'
        assert label.rect.topright == (SCREEN_WIDTH - 10, 10)

    def test_the_shadow_keeps_its_offset_and_its_labels_anchor(self, font, group):
        label = _label(
            font,
            group,
            position=(SCREEN_WIDTH // 2, 10),
            anchor=HudAnchor.TOP_CENTER,
            shadow_color=SHADOW_COLOR,
            shadow_offset=(1, 1),
        )
        label.text = 'Floor: The Gatehouse'
        assert label.shadow is not None
        assert label.shadow.rect.topleft == (label.rect.left + 1, label.rect.top + 1)


class TestPixels:
    """The labels draw exactly the pixels the HUDs' direct blits drew."""

    def test_brave_and_clockworks_hud_draws_the_same_pixels(self, font, group):
        floor_text = 'Floor: The Gatehouse'
        for text, position, anchor in (
            ('Score: 1250', (10, 10), HudAnchor.TOP_LEFT),
            ('Lives: 3', (SCREEN_WIDTH - 110, 10), HudAnchor.TOP_LEFT),
            (floor_text, (SCREEN_WIDTH // 2, 10), HudAnchor.TOP_CENTER),
        ):
            _label(
                font,
                group,
                text=text,
                position=position,
                anchor=anchor,
                shadow_color=SHADOW_COLOR,
                layer=HUD_LAYER,
            )
        floor_x = (SCREEN_WIDTH - font.size(floor_text)[0]) // 2
        assert _drawn(group) == _blitted(
            font,
            ('Score: 1250', (11, 11), SHADOW_COLOR),
            ('Score: 1250', (10, 10), TEXT_COLOR),
            ('Lives: 3', (SCREEN_WIDTH - 109, 11), SHADOW_COLOR),
            ('Lives: 3', (SCREEN_WIDTH - 110, 10), TEXT_COLOR),
            (floor_text, (floor_x + 1, 11), SHADOW_COLOR),
            (floor_text, (floor_x, 10), TEXT_COLOR),
        )

    @pytest.mark.parametrize('antialias', [True, False])
    def test_the_pixels_follow_the_engines_antialiasing(self, font, group, mocker, antialias):
        mocker.patch.object(font_manager.FontManager, 'antialias', return_value=antialias)
        _label(font, group, text='Score: 7', position=(10, 10), shadow_color=SHADOW_COLOR)
        assert _drawn(group) == _blitted(
            font, ('Score: 7', (11, 11), SHADOW_COLOR), ('Score: 7', (10, 10), TEXT_COLOR)
        )


class TestTheSprite:
    """What kind of sprite a label is, and where it sits in its group."""

    def test_the_shadow_sits_just_under_its_label_in_the_same_layer(self, font, group):
        other = _label(font, group, text='Other', layer=HUD_LAYER)
        label = _label(font, group, shadow_color=SHADOW_COLOR, layer=HUD_LAYER)
        assert group.sprites() == [other, label.shadow, label]
        assert group.get_layer_of_sprite(label) == HUD_LAYER
        assert group.get_layer_of_sprite(label.shadow) == HUD_LAYER

    def test_a_label_without_a_shadow_color_has_no_shadow(self, font, group):
        label = _label(font, group)
        assert label.shadow is None
        assert group.sprites() == [label]

    def test_a_shadowed_label_lists_its_shadow_then_itself_as_the_group_draws_them(
        self, font, group
    ):
        label = _label(font, group, shadow_color=SHADOW_COLOR, layer=HUD_LAYER)
        assert label.shadow is not None
        assert label.sprites_in_draw_order == (label.shadow, label)
        assert list(label.sprites_in_draw_order) == group.sprites()

    def test_a_label_without_a_shadow_lists_only_itself(self, font, group):
        label = _label(font, group)
        assert label.sprites_in_draw_order == (label,)
        assert list(label.sprites_in_draw_order) == group.sprites()

    def test_a_label_is_screen_space_redrawn_every_frame_and_a_root_sprite(self, font, group):
        label = _label(font, group)
        assert isinstance(label, RootSprite)
        assert not is_world_positioned(label)
        assert getattr(label, 'COORDINATE_SPACE', CoordinateSpace.SCREEN) is CoordinateSpace.SCREEN
        assert label.dirty == 2

    def test_a_label_draws_above_lower_layers(self, font, group):
        label = _label(font, group, layer=HUD_LAYER)
        below = _label(font, group, text='Below', layer=HUD_LAYER - 1)
        assert group.sprites() == [below, label]


class TestTheStyle:
    """A label's look (font, colors, anchor, shadow, layer) is one frozen value."""

    def test_a_style_cannot_be_changed_once_made(self, font):
        style = HudLabelStyle(font=font, color=TEXT_COLOR)
        field = 'color'
        with pytest.raises(pydantic.ValidationError) as raised:
            setattr(style, field, SHADOW_COLOR)
        assert [(error['type'], error['loc']) for error in raised.value.errors()] == [
            ('frozen_instance', ('color',))
        ]
        assert style.color == TEXT_COLOR

    def test_a_style_refuses_a_setting_it_does_not_know(self, font):
        # Every known setting is valid, so the unknown one is the only error
        with pytest.raises(pydantic.ValidationError) as raised:
            HudLabelStyle.model_validate({
                'font': font,
                'color': TEXT_COLOR,
                'outline_color': SHADOW_COLOR,
            })
        assert [(error['type'], error['loc']) for error in raised.value.errors()] == [
            ('extra_forbidden', ('outline_color',))
        ]

    def test_the_defaults_are_top_left_unshadowed_on_layer_zero(self, font):
        style = HudLabelStyle(font=font, color=TEXT_COLOR)
        assert style.anchor is HudAnchor.TOP_LEFT
        assert style.shadow_color is None
        assert style.shadow_offset == (1, 1)
        assert style.layer == 0

    def test_the_shadow_shares_the_look_but_its_color_and_has_no_shadow_of_its_own(
        self, font, group
    ):
        style = HudLabelStyle(
            font=font,
            color=TEXT_COLOR,
            anchor=HudAnchor.TOP_RIGHT,
            shadow_color=SHADOW_COLOR,
            shadow_offset=(2, 3),
            layer=HUD_LAYER,
        )
        label = HudLabel(groups=group, text='Lives: 3', position=(700, 10), style=style)
        assert label.style is style
        assert label.shadow is not None
        assert label.shadow.style == HudLabelStyle(
            font=font, color=SHADOW_COLOR, anchor=HudAnchor.TOP_RIGHT, layer=HUD_LAYER
        )
        assert label.shadow.shadow is None
        assert (label.shadow.rect.right, label.shadow.rect.top) == (702, 13)
