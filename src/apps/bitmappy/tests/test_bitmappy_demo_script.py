"""Bitmappy's bundled demo script (scripts/demo_inputs.py ``bitmappy_demo_script``).

The demo is recorded at the recorder's resolution (``SCREEN_RESOLUTION``, shared with every
golden), so its click points are written for the editor's layout there: these tests build the
editor at that resolution and check that every click lands where the script means it to, and
that the script, run through the engine, draws its smiley.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts.demo_inputs import (
    BITMAPPY_DEMO_COLOR_PICKS,
    BITMAPPY_DEMO_FACE_COLOR,
    BITMAPPY_DEMO_FACE_ROWS,
    BITMAPPY_DEMO_FEATURE_COLOR,
    BITMAPPY_DEMO_FEATURE_STROKES,
    BITMAPPY_DEMO_FRAME_COUNT,
    BITMAPPY_DEMO_POINTS,
    bitmappy_demo_canvas_point,
    bitmappy_demo_script,
)

from bitmappy.ai_manager import AIManager
from bitmappy.editor import BitmapEditorScene
from glitchygames.replay.tools.golden_traces import RANDOM_SEED, SCREEN_RESOLUTION, record_trace
from tests.display_canvas import show_canvas_on_new_display

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from glitchygames.scenes import Scene

# The fewest pixels the demo's drawing holds, and the fewest colours (the brief of Task 6)
MINIMUM_DRAWN_PIXELS = 20
MINIMUM_DRAWN_COLORS = 2


def build_editor(*, resolution: str) -> BitmapEditorScene:
    """Build a real Bitmappy editor on a display of the given size.

    Args:
        resolution: ``WIDTHxHEIGHT``, as ``--resolution`` takes it.

    Returns:
        The editor (one blank 32x32 frame), laid out for that display.

    """
    width, height = (int(length) for length in resolution.split('x'))
    show_canvas_on_new_display(size=(width, height))
    return BitmapEditorScene(options={})


def test_every_demo_click_lands_on_the_canvas_at_the_recorders_resolution():
    """Every point the demo clicks or drags through is on the canvas, at 800x480."""
    scene = build_editor(resolution=SCREEN_RESOLUTION)
    canvas = scene.canvas.rect
    assert all(canvas.collidepoint(point) for point in BITMAPPY_DEMO_POINTS)


def test_every_demo_click_lands_on_the_canvas_pixel_it_paints():
    """Each stroke's point is inside the square of the canvas pixel the script names."""
    scene = build_editor(resolution=SCREEN_RESOLUTION)
    canvas = scene.canvas
    pixels = [
        *(
            (column, row)
            for row, first, last in BITMAPPY_DEMO_FACE_ROWS
            for column in range(first, last + 1)
        ),
        *(pixel for stroke in BITMAPPY_DEMO_FEATURE_STROKES for pixel in stroke),
    ]
    for column, row in pixels:
        point_x, point_y = bitmappy_demo_canvas_point(column=column, row=row)
        assert (point_x - canvas.rect.x) // canvas.pixel_width == column
        assert (point_y - canvas.rect.y) // canvas.pixel_height == row


def test_every_colour_pick_lands_on_its_slider_at_the_recorders_resolution():
    """The colour picks click the left end of their channel's slider: the channel goes to 0."""
    scene = build_editor(resolution=SCREEN_RESOLUTION)
    sliders = {
        'red': scene.red_slider,
        'green': scene.green_slider,
        'blue': scene.blue_slider,
    }
    for channel, point in BITMAPPY_DEMO_COLOR_PICKS:
        slider = sliders[channel]
        assert slider.rect.collidepoint(point), channel
        assert point[0] <= slider.min_x, channel


def expected_canvas() -> dict[tuple[int, int], tuple[int, int, int]]:
    """Return the colour the demo leaves in each pixel it paints.

    Returns:
        ``(column, row)`` -> RGB: the face's rows in the face colour, then the features over
        them in the feature colour.

    """
    painted = {
        (column, row): BITMAPPY_DEMO_FACE_COLOR
        for row, first, last in BITMAPPY_DEMO_FACE_ROWS
        for column in range(first, last + 1)
    }
    for stroke in BITMAPPY_DEMO_FEATURE_STROKES:
        for pixel in stroke:
            painted[pixel] = BITMAPPY_DEMO_FEATURE_COLOR
    return painted


def test_the_demo_script_draws_its_two_colour_smiley(mocker: MockerFixture):
    """Run through the engine at the recorder's resolution, the script paints exactly its smiley.

    The AI worker is a separate process, which a test does not start (its setup is patched);
    the demo never makes an AI request.
    """
    mocker.patch.object(AIManager, 'setup')
    drawn: dict[tuple[int, int], tuple[int, int, int]] = {}

    def read_the_canvas(*, frame_number: int, scene: Scene, sprite_ids: object) -> None:
        """Keep the colour of every painted (not transparent) canvas pixel after the last frame."""
        del sprite_ids
        if frame_number != BITMAPPY_DEMO_FRAME_COUNT - 1:
            return
        assert isinstance(scene, BitmapEditorScene)
        canvas = scene.canvas
        magenta = (255, 0, 255)
        for index, color in enumerate(canvas.pixels):
            if tuple(color[:3]) != magenta:
                drawn[index % canvas.pixels_across, index // canvas.pixels_across] = tuple(
                    color[:3]
                )

    record_trace(
        scene_class=BitmapEditorScene,
        script=bitmappy_demo_script(),
        frame_count=BITMAPPY_DEMO_FRAME_COUNT,
        random_seed=RANDOM_SEED,
        frame_observer=read_the_canvas,
    )

    assert drawn == expected_canvas()
    assert len(drawn) >= MINIMUM_DRAWN_PIXELS
    assert len(set(drawn.values())) >= MINIMUM_DRAWN_COLORS
