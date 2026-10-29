"""bitmappy.masterhub_push: push the edited canvas to a sibling MasterHUB hub iframe (browser).

Offline, with a fake canvas and a fake poster (no browser, no ``js``): these pin the pure parts --
turning the canvas pixels into flat RGBA, de-duplicating a push, forcing one on demand -- and that
the setup is a no-op off the browser. The browser wiring (the real ``postMessage`` poster and the
``ready`` listener) is browser-only and excluded from coverage.
"""

from dataclasses import dataclass

from bitmappy.masterhub_push import MasterHubPush, canvas_rgba

MAGENTA = (255, 0, 255, 255)
RED = (255, 0, 0, 255)


@dataclass
class _FakeCanvas:
    pixels: list[tuple[int, ...]]
    pixels_across: int
    pixels_tall: int


def test_canvas_rgba_is_flat_rgba_with_dimensions():
    """canvas_rgba returns the pixels as flat RGBA bytes plus the native width and height."""
    pixels, width, height = canvas_rgba(_FakeCanvas([MAGENTA, RED], 2, 1))
    assert (width, height) == (2, 1)
    assert pixels == bytes([255, 0, 255, 255, 255, 0, 0, 255])  # magenta kept; the hub keys it


def test_canvas_rgba_pads_rgb_pixels_to_opaque():
    """A pixel stored as RGB (three components) is padded to opaque RGBA."""
    pixels, _, _ = canvas_rgba(_FakeCanvas([(10, 20, 30)], 1, 1))
    assert pixels == bytes([10, 20, 30, 255])


def test_push_if_changed_posts_once_per_change():
    """push_if_changed posts when the pixels differ from the last post, and skips when unchanged."""
    posts: list[tuple[bytes, int, int]] = []
    canvas = _FakeCanvas([RED], 1, 1)
    push = MasterHubPush(
        canvas, poster=lambda pixels, width, height: posts.append((pixels, width, height))
    )
    push.push_if_changed()
    push.push_if_changed()  # unchanged -> no second post
    assert posts == [(bytes([255, 0, 0, 255]), 1, 1)]
    canvas.pixels = [MAGENTA]  # a pixel changed
    push.push_if_changed()
    assert len(posts) == 2


def test_push_now_posts_unconditionally():
    """push_now posts the current canvas even when unchanged (used on a hub 'ready')."""
    posts: list[tuple[bytes, int, int]] = []
    canvas = _FakeCanvas([RED], 1, 1)
    push = MasterHubPush(
        canvas, poster=lambda pixels, width, height: posts.append((pixels, width, height))
    )
    push.push_now()
    push.push_now()
    assert len(posts) == 2


def test_mirror_is_a_noop_without_a_browser(bitmap_editor):
    """On the first frame off the browser the bridge is absent, so nothing is wired or pushed."""
    bitmap_editor._mirror_canvas_to_masterhub()
    assert bitmap_editor._masterhub_push is None
    assert bitmap_editor._masterhub_configured is True


def test_mirror_pushes_the_canvas_when_a_push_is_attached(bitmap_editor):
    """With a push attached, each frame posts the canvas through it."""
    posts: list[tuple[bytes, int, int]] = []
    push = MasterHubPush(
        _FakeCanvas([RED], 1, 1),
        poster=lambda pixels, width, height: posts.append((pixels, width, height)),
    )
    bitmap_editor._masterhub_configured = True  # skip the browser install
    bitmap_editor.set_masterhub_push(push)
    bitmap_editor._mirror_canvas_to_masterhub()
    assert posts == [(bytes([255, 0, 0, 255]), 1, 1)]


def test_set_masterhub_push_is_idempotent(bitmap_editor):
    """A second attach is ignored; the first push stays (the bridge may run more than once)."""
    first = MasterHubPush(_FakeCanvas([RED], 1, 1), poster=lambda *_: None)
    second = MasterHubPush(_FakeCanvas([MAGENTA], 1, 1), poster=lambda *_: None)
    bitmap_editor.set_masterhub_push(first)
    bitmap_editor.set_masterhub_push(second)
    assert bitmap_editor._masterhub_push is first
