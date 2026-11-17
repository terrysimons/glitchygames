"""The sprite requests (api/sprite_requests.py): the work the routes and the client share.

The AI service stands in through ``FakeAIClient`` (its chat client's contract); the renderer is
real except where a test makes it fail.
"""

from __future__ import annotations

import base64

import pytest

from glitchygames.api.models import SpriteGenerationRequest
from glitchygames.api.sprite_requests import (
    SpriteRequestRefusedError,
    extract_frames_response,
    extract_toml_frames_response,
    generate_response,
)
from glitchygames.services import RendererService, SpriteGenerationService
from glitchygames.services.config import ServiceConfig
from glitchygames.services.renderer_service import RenderedFrame, RenderResult
from tests.services.stand_in_ai_client import FakeAIClient

STATIC_SPRITE = """[sprite]
name = "heart"
pixels = \"\"\"
##
##
\"\"\"
[colors."#"]
red = 255
green = 0
blue = 0
"""

# Two frames: the animation's 0.25 s, then a frame overriding it with 0.5 s
TWO_FRAME_SPRITE = """[sprite]
name = "blink"

[[animation]]
namespace = "blink"
frame_interval = 0.25

[[animation.frame]]
pixels = \"\"\"
#.
.#
\"\"\"

[[animation.frame]]
frame_interval = 0.5
pixels = \"\"\"
.#
#.
\"\"\"

[colors."#"]
red = 255
green = 0
blue = 0

[colors."."]
red = 255
green = 0
blue = 255
"""


def _services(*, reply: str | Exception) -> tuple[SpriteGenerationService, RendererService]:
    """A sprite service whose AI answers ``reply``, and a real renderer.

    Returns:
        Both.
    """
    generation_service = SpriteGenerationService(ServiceConfig(ai_model='model-x'))
    generation_service._client = FakeAIClient(reply=reply)
    return generation_service, RendererService()


def test_a_failed_generation_is_an_unsuccessful_response():
    """The service's error is the response's; no sprite comes back."""
    generation_service, renderer_service = _services(reply='no sprite here')

    response = generate_response(
        SpriteGenerationRequest(prompt='a heart', output_format=['toml']),
        generation_service=generation_service,
        renderer_service=renderer_service,
    )

    assert response.success is False
    assert response.error
    assert response.toml_content is None


def test_toml_only_returns_the_toml_and_no_image():
    """The default format: the sprite file's text, nothing rendered."""
    generation_service, renderer_service = _services(reply=STATIC_SPRITE)

    response = generate_response(
        SpriteGenerationRequest(prompt='a heart', output_format=['toml']),
        generation_service=generation_service,
        renderer_service=renderer_service,
    )

    assert response.success is True
    assert response.toml_content is not None
    assert 'name = "heart"' in response.toml_content
    assert response.png_base64 is None


def test_png_only_with_rendering_failing_is_unsuccessful(mocker):
    """Nothing usable comes back, so the response says it failed (review focus 4)."""
    generation_service, renderer_service = _services(reply=STATIC_SPRITE)
    mocker.patch.object(
        renderer_service, 'render_from_toml', return_value=RenderResult(success=False, error='x')
    )

    response = generate_response(
        SpriteGenerationRequest(prompt='a heart', output_format=['png']),
        generation_service=generation_service,
        renderer_service=renderer_service,
    )

    assert (response.success, response.error) == (False, 'PNG rendering failed')


def test_an_absolute_output_path_is_refused(tmp_path):
    """Files are only ever saved under the allowed root."""
    generation_service, renderer_service = _services(reply=STATIC_SPRITE)

    with pytest.raises(SpriteRequestRefusedError, match='Absolute output paths'):
        generate_response(
            SpriteGenerationRequest(
                prompt='a heart',
                output_format=['toml'],
                output_path=str(tmp_path.resolve() / 'elsewhere'),
            ),
            generation_service=generation_service,
            renderer_service=renderer_service,
        )


def test_an_apng_without_the_png_signature_is_unsuccessful():
    """Bytes that are not a PNG come back as a failure naming the signature, never raised."""
    response = extract_frames_response(apng_base64=base64.b64encode(b'not a png').decode())

    assert response.success is False
    assert response.error is not None
    assert 'PNG signature' in response.error


def test_a_toml_sprites_frames_come_back_with_their_animation_and_timing():
    """Each frame rendered, in order, with its animation, its place and its own delay."""
    response = extract_toml_frames_response(
        toml_content=TWO_FRAME_SPRITE, renderer_service=RendererService()
    )

    assert response.success is True
    assert response.frame_count == 2
    assert [
        (frame.index, frame.animation_index, frame.animation_frame_index, frame.delay_ms)
        for frame in response.frames
    ] == [(0, 0, 0, 250), (1, 0, 1, 500)]
    assert all(
        base64.b64decode(frame.png_base64).startswith(b'\x89PNG') for frame in response.frames
    )
    assert (response.width, response.height) == (2, 2)
    assert response.total_duration_ms == 750


def test_a_static_toml_sprite_is_one_frame_timed_as_the_loader_times_it():
    """A still sprite is one frame; its delay is the loader's default, as for any frame."""
    response = extract_toml_frames_response(
        toml_content=STATIC_SPRITE, renderer_service=RendererService()
    )

    assert response.success is True
    assert [(frame.index, frame.delay_ms) for frame in response.frames] == [(0, 500)]


ONE_FRAME_ANIMATION = """[sprite]
name = "glint"

[[animation]]
namespace = "glint"
frame_interval = 0.3

[[animation.frame]]
pixels = "#"

[colors."#"]
red = 255
green = 255
blue = 0
"""


def test_a_one_frame_animation_keeps_its_interval():
    """One frame of an [[animation]] is still timed: its frame_interval, not 0."""
    response = extract_toml_frames_response(
        toml_content=ONE_FRAME_ANIMATION, renderer_service=RendererService()
    )

    assert response.success is True
    assert [(frame.index, frame.delay_ms) for frame in response.frames] == [(0, 300)]


@pytest.mark.parametrize(
    'toml_content',
    [
        '[sprite]\nname = "x"\nanimation = 5\n',
        'animation = 5\n',
        ONE_FRAME_ANIMATION.replace('frame_interval = 0.3', 'frame_interval = "fast"'),
    ],
    ids=['animation is a number', 'a bare animation number', 'frame_interval is text'],
)
def test_a_sprite_file_of_the_wrong_shape_is_unsuccessful(toml_content):
    """Valid TOML that is not a valid sprite fails as a response, never raised (rule 4)."""
    response = extract_toml_frames_response(
        toml_content=toml_content, renderer_service=RendererService()
    )

    assert response.success is False
    assert response.error


def test_a_frame_the_renderer_cannot_time_is_unsuccessful(mocker):
    """A frame whose duration the renderer reports as not known (None) is refused, not raised.

    The sprite file schema refuses a ``frame_interval`` that is not a number before anything
    renders, so None is the one untimed frame left to refuse here.
    """
    renderer_service = RendererService()
    mocker.patch.object(
        renderer_service,
        'render_from_toml',
        return_value=RenderResult(
            success=True,
            width=8,
            height=8,
            rendered_frames=[
                RenderedFrame(
                    animation_index=0, frame_index=0, png_base64='', duration_seconds=None
                )
            ],
        ),
    )

    response = extract_toml_frames_response(
        toml_content=ONE_FRAME_ANIMATION, renderer_service=renderer_service
    )

    assert response.success is False
    assert response.error is not None
    assert 'frame 0 of animation 0' in response.error


def test_toml_that_is_not_a_sprite_is_unsuccessful():
    """A .toml that parses but holds no sprite comes back as a failure, never raised."""
    response = extract_toml_frames_response(
        toml_content='title = "not a sprite"\n', renderer_service=RendererService()
    )

    assert response.success is False
    assert response.error is not None
    assert response.error.startswith('Invalid sprite file')


def test_text_that_is_not_a_sprite_is_unsuccessful():
    """A .toml that is not a sprite comes back as a failure, never raised."""
    response = extract_toml_frames_response(
        toml_content='this is = not [a sprite', renderer_service=RendererService()
    )

    assert response.success is False
    assert response.error
