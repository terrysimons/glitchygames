"""Tests for the debug overlay camera, performance, mode line, hooks and drawing."""

import types

import pygame
import pytest

from glitchygames.camera import Camera2D
from glitchygames.collision.layers import CollisionManager
from glitchygames.debug import overlay as overlay_module
from glitchygames.debug.overlay import DebugOverlay, DebugPanel
from glitchygames.debug.panels import (
    BOUNDS_COLOR,
    GRAPH_BAR_COLOR,
    HUD_LINE_HEIGHT,
    TARGET_LINE_COLOR,
    TEXT_BACKING_PADDING,
    DebugFrameInfo,
    draw_camera_panel,
    draw_mode_line,
    draw_performance_panel,
)

SURFACE_SIZE = (400, 300)
BLACK = (0, 0, 0, 255)
MARKER_COLOR = (255, 0, 255)
PURE_RED = (255, 0, 0)


@pytest.fixture(autouse=True)
def initialized_pygame():
    """Initialise pygame (fonts) for tests that use a real font."""
    pygame.init()


@pytest.fixture
def surface():
    """A real, black surface.

    Returns:
        A pygame.Surface.

    """
    return pygame.Surface(SURFACE_SIZE)


@pytest.fixture
def camera():
    """An unscrolled camera.

    Returns:
        A Camera2D.

    """
    return Camera2D(SURFACE_SIZE[0], SURFACE_SIZE[1])


@pytest.fixture
def font(mocker):
    """A font whose render returns a small real surface.

    Returns:
        A mock font.

    """
    mock_font = mocker.Mock()
    mock_font.render.side_effect = lambda *args, **kwargs: pygame.Surface((4, 4))
    return mock_font


def marker_surface():
    """Build a 4x4 surface filled with MARKER_COLOR (stands in for rendered text).

    Returns:
        A pygame.Surface.

    """
    text_surface = pygame.Surface((4, 4))
    text_surface.fill(MARKER_COLOR)
    return text_surface


def rendered_texts(font):
    """Collect the text strings passed to a mock font's render.

    Returns:
        A list of strings.

    """
    return [call.args[0] for call in font.render.call_args_list]


def non_black_pixel_count(surface, *, area):
    """Count non-black pixels inside an area.

    Returns:
        The number of pixels that are not black.

    """
    return sum(
        1
        for x in range(area.left, area.right)
        for y in range(area.top, area.bottom)
        if surface.get_at((x, y)) != BLACK
    )


def build_frame_info(**overrides):
    """Build a DebugFrameInfo (defaults: 60 FPS target, no voices, rumble, shake or mouse).

    Returns:
        A DebugFrameInfo.

    """
    arguments = {
        'target_fps': 60.0,
        'live_voice_count': None,
        'rumble_levels': (0.0, 0.0),
        'screen_shake_offset': (0.0, 0.0),
        'mouse_position': None,
    }
    arguments.update(overrides)
    return DebugFrameInfo(**arguments)


def pixels_of_color(surface, *, color):
    """Count pixels of an exact RGB colour on the surface.

    Returns:
        The number of matching pixels.

    """
    return sum(
        1
        for x in range(surface.get_width())
        for y in range(surface.get_height())
        if surface.get_at((x, y))[:3] == color
    )


def draw_camera(*, surface, camera, font, screen_offset=(0, 0), **frame_overrides):
    """Call draw_camera_panel with keyword arguments."""
    draw_camera_panel(
        surface=surface,
        camera=camera,
        screen_offset=screen_offset,
        font=font,
        frame_info=build_frame_info(**frame_overrides),
    )


def draw_performance(*, surface, overlay, font, **frame_overrides):
    """Call draw_performance_panel with keyword arguments."""
    draw_performance_panel(
        surface=surface,
        overlay=overlay,
        font=font,
        frame_info=build_frame_info(**frame_overrides),
    )


class TestCameraPanel:
    """Bounds, lead crosshair, mouse world position and shake readout."""

    def test_bound_on_screen_draws_dashed_line(self, surface, camera, font):
        """min_x=0 with the camera at 0 draws a dashed vertical line at screen x=0."""
        camera.set_bounds(min_x=0)
        draw_camera(surface=surface, camera=camera, font=font)
        column = [surface.get_at((0, y)) != BLACK for y in range(20, SURFACE_SIZE[1])]
        assert pixels_of_color(surface, color=BOUNDS_COLOR) > 0
        assert any(column)
        assert not all(column)  # dashed, not solid

    def test_right_edge_is_last_world_pixel_at_the_clamp(self, font):
        """With the camera clamped at max_x=100 on a 200 px screen the line is at x=199."""
        small_surface = pygame.Surface((200, 100))
        small_camera = Camera2D(200, 100)
        small_camera.set_bounds(max_x=100)
        small_camera.world_x = 100
        draw_camera(surface=small_surface, camera=small_camera, font=font)
        assert small_surface.get_at((199, 0))[:3] == BOUNDS_COLOR

    def test_right_edge_off_surface_one_pixel_before_the_clamp(self, font):
        """At world_x=99 the last world pixel (299) is at screen x=200, so nothing is drawn."""
        small_surface = pygame.Surface((200, 100))
        small_camera = Camera2D(200, 100)
        small_camera.set_bounds(max_x=100)
        small_camera.world_x = 99
        draw_camera(surface=small_surface, camera=small_camera, font=font)
        assert pixels_of_color(small_surface, color=BOUNDS_COLOR) == 0

    def test_far_bound_draws_nothing(self, font):
        """A bound far to the right of the visible world draws no line."""
        small_surface = pygame.Surface((200, 100))
        small_camera = Camera2D(200, 100)
        small_camera.set_bounds(max_x=1000)
        draw_camera(surface=small_surface, camera=small_camera, font=font)
        assert pixels_of_color(small_surface, color=BOUNDS_COLOR) == 0

    def test_bottom_edge_is_last_world_pixel_at_the_clamp(self, font):
        """With the camera clamped at max_y=50 on a 100 px screen the line is at y=99."""
        small_surface = pygame.Surface((200, 100))
        small_camera = Camera2D(200, 100)
        small_camera.set_bounds(max_y=50)
        small_camera.world_y = 50
        draw_camera(surface=small_surface, camera=small_camera, font=font)
        assert small_surface.get_at((0, 99))[:3] == BOUNDS_COLOR

    def test_bottom_edge_off_surface_one_pixel_before_the_clamp(self, font):
        """At world_y=49 the last world pixel (149) is at screen y=100, so nothing is drawn."""
        small_surface = pygame.Surface((200, 100))
        small_camera = Camera2D(200, 100)
        small_camera.set_bounds(max_y=50)
        small_camera.world_y = 49
        draw_camera(surface=small_surface, camera=small_camera, font=font)
        assert pixels_of_color(small_surface, color=BOUNDS_COLOR) == 0

    def test_lead_crosshair_drawn_at_lead_plus_offset(self, surface, font):
        """The crosshair centre sits at (lead_x, lead_y) plus the screen offset."""
        lead_camera = Camera2D(SURFACE_SIZE[0], SURFACE_SIZE[1], lead_x=100, lead_y=80)
        draw_camera(surface=surface, camera=lead_camera, font=font, screen_offset=(5, 3))
        assert surface.get_at((105, 83)) != BLACK

    def test_mouse_world_text_is_camera_plus_mouse(self, surface, camera, font):
        """Mouse world position is the camera world position plus the mouse position."""
        camera.world_x = 50
        camera.world_y = 20
        draw_camera(surface=surface, camera=camera, font=font, mouse_position=(10, 5))
        assert any('(60, 25)' in text for text in rendered_texts(font))

    def test_no_mouse_text_when_mouse_missing(self, surface, camera, font):
        """mouse_position=None draws no mouse text."""
        draw_camera(surface=surface, camera=camera, font=font, mouse_position=None)
        assert not any('mouse' in text.lower() for text in rendered_texts(font))

    def test_no_shake_text_when_neither_offset_is_set(self, surface, camera, font):
        """No shake text appears with both offsets zero."""
        draw_camera(surface=surface, camera=camera, font=font)
        assert not any('shake' in text.lower() for text in rendered_texts(font))

    def test_world_shake_text_alone(self, surface, camera, font):
        """A non-zero WORLD shake offset shows a world line and no screen line."""
        camera.shake_effect = types.SimpleNamespace(offset=(1.0, -2.0))
        draw_camera(surface=surface, camera=camera, font=font)
        texts = rendered_texts(font)
        assert any('world shake' in text and '1.0' in text and '-2.0' in text for text in texts)
        assert not any('screen shake' in text for text in texts)

    def test_screen_shake_text_alone(self, surface, camera, font):
        """A non-zero SCREEN shake offset shows a screen line and no world line."""
        draw_camera(surface=surface, camera=camera, font=font, screen_shake_offset=(0.0, 2.0))
        texts = rendered_texts(font)
        assert any('screen shake' in text and '2.0' in text for text in texts)
        assert not any('world shake' in text for text in texts)

    def test_both_shake_texts(self, surface, camera, font):
        """Both offsets non-zero show both lines."""
        camera.shake_effect = types.SimpleNamespace(offset=(3.0, 0.0))
        draw_camera(surface=surface, camera=camera, font=font, screen_shake_offset=(0.0, 2.0))
        texts = rendered_texts(font)
        assert any('world shake' in text for text in texts)
        assert any('screen shake' in text for text in texts)

    def test_mouse_text_drawn_next_to_cursor(self, surface, camera):
        """The mouse world text is blitted at the cursor plus (12, 12), not in the top-left."""
        marker_font = types.SimpleNamespace(render=lambda *args, **kwargs: marker_surface())
        camera.world_x = 50
        draw_camera(surface=surface, camera=camera, font=marker_font, mouse_position=(100, 100))
        assert surface.get_at((112, 112))[:3] == MARKER_COLOR
        assert surface.get_at((4, 4 + 2 * HUD_LINE_HEIGHT))[:3] != MARKER_COLOR

    def test_mouse_text_kept_inside_surface(self, surface, camera):
        """A cursor in the bottom-right corner keeps the text on the surface."""
        marker_font = types.SimpleNamespace(render=lambda *args, **kwargs: marker_surface())
        draw_camera(
            surface=surface,
            camera=camera,
            font=marker_font,
            mouse_position=(SURFACE_SIZE[0] - 1, SURFACE_SIZE[1] - 1),
        )
        assert surface.get_at((SURFACE_SIZE[0] - 2, SURFACE_SIZE[1] - 2))[:3] == MARKER_COLOR

    def test_screen_shake_does_not_change_mouse_world_value(self, surface, camera, font):
        """The mouse world value is camera.world + mouse, unshaken."""
        camera.world_x = 50
        draw_camera(
            surface=surface,
            camera=camera,
            font=font,
            mouse_position=(10, 5),
            screen_shake_offset=(7.0, 7.0),
        )
        assert any('(60, 5)' in text for text in rendered_texts(font))


class TestPerformancePanel:
    """FPS text, the frame-time graph and the optional lines."""

    def test_bar_over_target_frame_time_is_red(self, surface, font):
        """At 60 FPS (16.67 ms) a 17 ms frame draws red and a 16 ms frame does not."""
        slow = DebugOverlay(visible=True)
        slow.record_frame(frame_seconds=0.017)
        draw_performance(surface=surface, overlay=slow, font=font)
        assert pixels_of_color(surface, color=PURE_RED) > 0

        fast_surface = pygame.Surface(SURFACE_SIZE)
        fast = DebugOverlay(visible=True)
        fast.record_frame(frame_seconds=0.016)
        draw_performance(surface=fast_surface, overlay=fast, font=font)
        assert pixels_of_color(fast_surface, color=PURE_RED) == 0

    def test_uncapped_has_no_red_bars(self, surface, font):
        """With no target FPS even a 40 ms frame is not red."""
        overlay = DebugOverlay(visible=True)
        overlay.record_frame(frame_seconds=0.040)
        draw_performance(surface=surface, overlay=overlay, font=font, target_fps=0.0)
        assert pixels_of_color(surface, color=PURE_RED) == 0
        assert pixels_of_color(surface, color=GRAPH_BAR_COLOR) > 0

    def test_target_line_row_for_sixty_and_none_when_uncapped(self, surface, font):
        """At 60 FPS the target line fills one row of the graph; uncapped has no line."""
        overlay = DebugOverlay(visible=True)
        draw_performance(surface=surface, overlay=overlay, font=font, target_fps=60.0)
        graph_left = SURFACE_SIZE[0] - 4 - 200
        graph_bottom = SURFACE_SIZE[1] - 4 - 60 - HUD_LINE_HEIGHT + 60
        line_y = graph_bottom - 1 - round(1000.0 / 60.0 * 60 / 50)
        assert all(
            surface.get_at((x, line_y))[:3] == TARGET_LINE_COLOR
            for x in range(graph_left, graph_left + 200)
        )
        assert not any('uncapped' in text for text in rendered_texts(font))

        font.render.reset_mock()
        uncapped_surface = pygame.Surface(SURFACE_SIZE)
        draw_performance(surface=uncapped_surface, overlay=overlay, font=font, target_fps=0.0)
        assert any('uncapped' in text for text in rendered_texts(font))
        assert pixels_of_color(uncapped_surface, color=TARGET_LINE_COLOR) == 0

    def test_target_line_stays_inside_graph_for_low_targets(self, surface, font):
        """At 10 FPS (100 ms) the graph ceiling grows so the line is still inside the graph."""
        draw_performance(
            surface=surface, overlay=DebugOverlay(visible=True), font=font, target_fps=10.0
        )
        graph_top = SURFACE_SIZE[1] - 4 - 60 - HUD_LINE_HEIGHT
        rows = [
            y
            for y in range(SURFACE_SIZE[1])
            if surface.get_at((SURFACE_SIZE[0] - 10, y))[:3] == TARGET_LINE_COLOR
        ]
        assert len(rows) == 1
        assert graph_top <= rows[0] < graph_top + 60

    def test_frame_time_readout_from_last_frame(self, surface, font):
        """The last recorded frame is shown with one decimal; none recorded shows no readout."""
        overlay = DebugOverlay(visible=True)
        draw_performance(surface=surface, overlay=overlay, font=font)
        assert not any(text.startswith('frame:') for text in rendered_texts(font))
        overlay.record_frame(frame_seconds=0.0165)
        draw_performance(surface=surface, overlay=overlay, font=font)
        assert 'frame: 16.5 ms' in rendered_texts(font)

    def test_voice_line_only_when_count_given(self, surface, font):
        """The live voices line appears only when a count is supplied."""
        overlay = DebugOverlay(visible=True)
        draw_performance(surface=surface, overlay=overlay, font=font, live_voice_count=None)
        assert not any('voices' in text for text in rendered_texts(font))
        draw_performance(surface=surface, overlay=overlay, font=font, live_voice_count=3)
        assert any('voices: 3' in text for text in rendered_texts(font))

    def test_rumble_line_only_when_a_level_is_positive(self, surface, font):
        """The rumble line appears only when either motor level is above zero."""
        overlay = DebugOverlay(visible=True)
        draw_performance(surface=surface, overlay=overlay, font=font, rumble_levels=(0.0, 0.0))
        assert not any('rumble' in text for text in rendered_texts(font))
        draw_performance(surface=surface, overlay=overlay, font=font, rumble_levels=(0.0, 0.5))
        assert any('rumble' in text for text in rendered_texts(font))

    def test_footnote_mentions_overlay_drawing(self, surface, font):
        """The footnote warns that overlay drawing is included in the timings."""
        draw_performance(surface=surface, overlay=DebugOverlay(visible=True), font=font)
        assert any('overlay drawing included' in text for text in rendered_texts(font))


class TestModeLine:
    """The top-centre mode line."""

    @pytest.mark.parametrize(
        ('panel', 'title'),
        [
            (DebugPanel.ALL, 'All'),
            (DebugPanel.COLLISION, 'Collision'),
            (DebugPanel.PHYSICS, 'Physics'),
            (DebugPanel.CAMERA, 'Camera'),
            (DebugPanel.PERFORMANCE, 'Performance'),
        ],
    )
    def test_text_names_the_panel(self, surface, font, panel, title):
        """The mode line names the panel and the keys."""
        draw_mode_line(surface=surface, font=font, panel=panel)
        assert rendered_texts(font) == [f'DEBUG: {title} (F3 off, F4 next)']

    def test_drawn_horizontally_centred(self, surface, mocker):
        """The text is blitted so that it is centred on the surface."""
        text_surface = pygame.Surface((100, 10))
        text_surface.fill((255, 255, 255))
        mock_font = mocker.Mock()
        mock_font.render.return_value = text_surface
        draw_mode_line(surface=surface, font=mock_font, panel=DebugPanel.ALL)
        # The text sits TEXT_BACKING_PADDING below the top edge so its backing stays on screen.
        text_row = TEXT_BACKING_PADDING + 1
        assert surface.get_at((SURFACE_SIZE[0] // 2, text_row))[:3] == (255, 255, 255)
        assert surface.get_at((SURFACE_SIZE[0] // 2 - 60, text_row)) == BLACK

    def test_text_has_a_translucent_dark_backing(self, surface, mocker):
        """Debug text is drawn over a dark backing that dims, but does not hide, the game."""
        surface.fill((200, 200, 200))
        text_surface = pygame.Surface((100, 10), pygame.SRCALPHA)  # fully transparent text
        mock_font = mocker.Mock()
        mock_font.render.return_value = text_surface
        draw_mode_line(surface=surface, font=mock_font, panel=DebugPanel.ALL)
        dimmed = surface.get_at((SURFACE_SIZE[0] // 2, TEXT_BACKING_PADDING + 1))[:3]
        assert all(0 < channel < 200 for channel in dimmed)


class HookScene:
    """A scene with a debug hook and a camera."""

    def __init__(self, *, camera, sprites=()):
        """Initialize the test double."""
        self.camera = camera
        self.all_sprites = list(sprites)
        self.collisions = CollisionManager()
        self.debug_calls = []

    def debug_draw(self, surface, camera):
        """Record the call."""
        self.debug_calls.append((surface, camera))


class HookSprite:
    """A sprite with a debug hook."""

    def __init__(self):
        """Initialize the test double."""
        self.rect = pygame.Rect(0, 0, 10, 10)
        self.debug_calls = []

    def debug_draw(self, surface, camera):
        """Record the call."""
        self.debug_calls.append((surface, camera))


class PlainSprite:
    """A sprite without a debug hook."""

    def __init__(self):
        """Initialize the test double."""
        self.rect = pygame.Rect(30, 30, 10, 10)


class RaisingSprite(HookSprite):
    """A sprite whose hook raises."""

    def debug_draw(self, surface, camera):
        """Record the call and fail.

        Raises:
            RuntimeError: Always.

        """
        self.debug_calls.append((surface, camera))
        message = 'hook failure'
        raise RuntimeError(message)


def draw_overlay(*, overlay, surface, scene, mouse_position=(1, 1)):
    """Call DebugOverlay.draw exactly as the scene manager will.

    Returns:
        None.

    """
    return overlay.draw(
        surface,
        scene=scene,
        screen_offset=(0, 0),
        frame_info=build_frame_info(mouse_position=mouse_position),
    )


class TestOverlayDraw:
    """DebugOverlay.draw: hooks, lazy font and read-only behaviour."""

    def test_hooks_called_once_with_surface_and_camera(self, surface, camera):
        """The scene hook and the hooked sprite are called; the plain sprite is skipped."""
        hooked = HookSprite()
        scene = HookScene(camera=camera, sprites=[hooked, PlainSprite()])
        draw_overlay(overlay=DebugOverlay(visible=True), surface=surface, scene=scene)
        assert scene.debug_calls == [(surface, camera)]
        assert hooked.debug_calls == [(surface, camera)]

    def test_no_hooks_in_performance_mode(self, surface, camera):
        """PERFORMANCE mode calls no hook."""
        hooked = HookSprite()
        scene = HookScene(camera=camera, sprites=[hooked])
        overlay = DebugOverlay(visible=True)
        overlay.panel = DebugPanel.PERFORMANCE
        draw_overlay(overlay=overlay, surface=surface, scene=scene)
        assert scene.debug_calls == []
        assert hooked.debug_calls == []

    def test_raising_hook_logged_once_and_disabled(self, surface, camera, mocker):
        """A hook that raises is logged once, disabled, and the draw keeps going."""
        mock_log = mocker.patch.object(overlay_module, 'log')
        raising = RaisingSprite()
        scene = HookScene(camera=camera, sprites=[raising])
        overlay = DebugOverlay(visible=True)
        draw_overlay(overlay=overlay, surface=surface, scene=scene)
        draw_overlay(overlay=overlay, surface=surface, scene=scene)
        assert len(raising.debug_calls) == 1
        assert mock_log.exception.call_count == 1
        assert len(scene.debug_calls) == 2  # the healthy hook is unaffected

    def test_raising_scene_hook_is_disabled_too(self, surface, camera, mocker):
        """A scene whose own hook raises is logged once and not called again."""
        mock_log = mocker.patch.object(overlay_module, 'log')
        scene = HookScene(camera=camera)

        def raising_hook(hook_surface, hook_camera):
            scene.debug_calls.append((hook_surface, hook_camera))
            message = 'scene hook failure'
            raise RuntimeError(message)

        scene.debug_draw = raising_hook
        overlay = DebugOverlay(visible=True)
        draw_overlay(overlay=overlay, surface=surface, scene=scene)
        draw_overlay(overlay=overlay, surface=surface, scene=scene)
        assert len(scene.debug_calls) == 1
        assert mock_log.exception.call_count == 1

    def test_font_created_once_across_draws(self, surface, camera, mocker):
        """The font is created lazily, on the first draw only."""
        real_font = pygame.font.Font(None, 16)
        mock_font_class = mocker.patch.object(pygame.font, 'Font', return_value=real_font)
        overlay = DebugOverlay(visible=True)
        scene = HookScene(camera=camera)
        draw_overlay(overlay=overlay, surface=surface, scene=scene)
        draw_overlay(overlay=overlay, surface=surface, scene=scene)
        assert mock_font_class.call_count == 1

    def test_full_overlay_draws_with_real_font(self, surface, camera):
        """Drawing every panel with a real font draws pixels and does not raise."""
        camera.set_bounds(min_x=0)
        scene = HookScene(camera=camera, sprites=[PlainSprite()])
        draw_overlay(overlay=DebugOverlay(visible=True), surface=surface, scene=scene)
        assert non_black_pixel_count(surface, area=surface.get_rect()) > 0

    def test_draw_is_read_only(self, surface, camera):
        """Drawing changes no sprite rect, physics state or camera position."""
        body = types.SimpleNamespace(
            velocity_x=50.0, velocity_y=-10.0, world_x=5.0, world_y=6.0, on_ground=True
        )
        sprite = PlainSprite()
        sprite.world_x = 5.0
        sprite.world_y = 6.0
        sprite.physics = body
        sprite.dirty = 0
        camera.world_x = 12.0
        scene = HookScene(camera=camera, sprites=[sprite])
        before = (
            sprite.rect.copy(),
            vars(body).copy(),
            (camera.world_x, camera.world_y),
            sprite.dirty,
        )
        draw_overlay(overlay=DebugOverlay(visible=True), surface=surface, scene=scene)
        after = (
            sprite.rect.copy(),
            vars(body).copy(),
            (camera.world_x, camera.world_y),
            sprite.dirty,
        )
        assert after == before
        assert camera.has_been_applied is False
