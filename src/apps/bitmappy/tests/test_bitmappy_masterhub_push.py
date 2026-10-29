"""bitmappy.masterhub_push: push the sprite to a sibling MasterHUB hub iframe (browser).

Offline, with fake scene parts and fake posters (no browser, no ``js``): these pin the pure parts --
reading the selected strip's currently-playing preview frame for the dial, the idle first frame for
the center key, flattening to RGBA, and de-duplicating each push -- and that the editor hook is a
no-op off the browser. The browser wiring (the real ``postMessage`` posters and the ``ready``
listener) is browser-only and excluded from coverage.
"""

from dataclasses import dataclass, field

from bitmappy.masterhub_push import MasterHubPush, idle_frame, preview_frame

MAGENTA = (255, 0, 255, 255)
RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)


@dataclass
class _FakeFrame:
    pixels: list[tuple[int, ...]]
    size: tuple[int, int]

    def get_pixel_data(self) -> list[tuple[int, ...]]:
        return self.pixels

    def get_size(self) -> tuple[int, int]:
        return self.size


@dataclass
class _FakeStrip:
    index: int

    def get_current_preview_frame(self, anim_name: str) -> int:
        _ = anim_name
        return self.index


@dataclass
class _FakeSprite:
    animations: dict[str, list[_FakeFrame]]


@dataclass
class _FakeCanvas:
    animated_sprite: _FakeSprite


@dataclass
class _FakeScene:
    canvas: _FakeCanvas
    film_strips: dict[str, _FakeStrip] = field(default_factory=dict)
    selected_animation: str | None = None


def _frame(color: tuple[int, ...], size: tuple[int, int] = (1, 1)) -> _FakeFrame:
    width, height = size
    return _FakeFrame([color] * (width * height), size)


def _scene(
    animations: dict[str, list[_FakeFrame]],
    *,
    film_strips: dict[str, _FakeStrip] | None = None,
    selected: str | None = None,
) -> _FakeScene:
    return _FakeScene(
        canvas=_FakeCanvas(_FakeSprite(animations)),
        film_strips=film_strips or {},
        selected_animation=selected,
    )


def _dial(scene: _FakeScene) -> tuple[bytes, int, int]:
    frame = preview_frame(scene)
    assert frame is not None
    return frame


def _key(scene: _FakeScene) -> tuple[bytes, int, int]:
    frame = idle_frame(scene)
    assert frame is not None
    return frame


def test_preview_frame_reads_the_selected_strips_playing_index():
    """The dial frame is the selected strip's currently-playing preview frame, flattened to RGBA."""
    scene = _scene(
        {'idle': [_frame(RED), _frame(GREEN)]},
        film_strips={'idle': _FakeStrip(1)},  # the preview is on frame 1
        selected='idle',
    )
    pixels, width, height = _dial(scene)
    assert (width, height) == (1, 1)
    assert pixels == bytes(GREEN)  # frame 1, the one the preview is showing


def test_preview_frame_falls_back_to_the_first_animation():
    """With nothing selected, the dial uses the first animation (frame 0 when there is no strip)."""
    scene = _scene({'walk': [_frame(RED)], 'jump': [_frame(GREEN)]})
    pixels, _, _ = _dial(scene)
    assert pixels == bytes(RED)  # 'walk' is first; no strip -> frame 0


def test_preview_frame_clamps_a_stale_index():
    """A preview index past the strip's frames is clamped to the last frame, not an IndexError."""
    scene = _scene(
        {'idle': [_frame(RED), _frame(GREEN)]},
        film_strips={'idle': _FakeStrip(9)},  # beyond the two frames
        selected='idle',
    )
    pixels, _, _ = _dial(scene)
    assert pixels == bytes(GREEN)  # clamped to the last frame


def test_preview_frame_is_none_without_frames():
    """An empty or missing selected animation yields no dial frame."""
    assert preview_frame(_scene({'idle': []}, selected='idle')) is None
    assert preview_frame(_scene({})) is None


def test_idle_frame_is_the_first_animations_first_frame():
    """The center-key reference is always the first animation's first frame."""
    scene = _scene({'idle': [_frame(RED), _frame(GREEN)], 'walk': [_frame(MAGENTA)]})
    pixels, _, _ = _key(scene)
    assert pixels == bytes(RED)  # 'idle' frame 0, regardless of selection or preview


def test_idle_frame_is_none_without_frames():
    """No frames anywhere yields no key reference."""
    assert idle_frame(_scene({})) is None
    assert idle_frame(_scene({'idle': []})) is None


def test_rgb_pixels_are_padded_to_opaque():
    """A pixel stored as RGB (three components) is padded to opaque RGBA."""
    scene = _scene({'idle': [_FakeFrame([(10, 20, 30)], (1, 1))]})
    pixels, _, _ = _dial(scene)
    assert pixels == bytes([10, 20, 30, 255])


def test_push_if_changed_posts_dial_and_key_once_per_change():
    """push_if_changed posts the dial and key when they change, and skips when they do not."""
    dial_posts: list[tuple[bytes, int, int]] = []
    key_posts: list[tuple[bytes, int, int]] = []
    strip = _FakeStrip(0)
    scene = _scene(
        {'idle': [_frame(RED), _frame(GREEN)]}, film_strips={'idle': strip}, selected='idle'
    )
    push = MasterHubPush(
        scene,
        post_dial=lambda pixels, width, height: dial_posts.append((pixels, width, height)),
        post_key=lambda pixels, width, height: key_posts.append((pixels, width, height)),
    )
    push.push_if_changed()
    assert dial_posts == [(bytes(RED), 1, 1)]  # frame 0
    assert key_posts == [(bytes(RED), 1, 1)]  # idle frame 0
    push.push_if_changed()  # nothing changed -> no new posts
    assert len(dial_posts) == 1
    assert len(key_posts) == 1
    strip.index = 1  # the preview advanced: the dial changes, the key reference does not
    push.push_if_changed()
    assert dial_posts[-1] == (bytes(GREEN), 1, 1)
    assert len(dial_posts) == 2
    assert len(key_posts) == 1  # the idle key reference is unchanged


def test_push_now_posts_both_unconditionally():
    """push_now posts the dial and key even when unchanged (used on a hub 'ready')."""
    dial_posts: list[tuple[bytes, int, int]] = []
    key_posts: list[tuple[bytes, int, int]] = []
    scene = _scene({'idle': [_frame(RED)]}, selected='idle')
    push = MasterHubPush(
        scene,
        post_dial=lambda pixels, width, height: dial_posts.append((pixels, width, height)),
        post_key=lambda pixels, width, height: key_posts.append((pixels, width, height)),
    )
    push.push_now()
    push.push_now()
    assert len(dial_posts) == 2
    assert len(key_posts) == 2


def test_push_skips_an_empty_sprite():
    """With no frames at all, a push posts nothing to either screen."""
    dial_posts: list[tuple[bytes, int, int]] = []
    key_posts: list[tuple[bytes, int, int]] = []
    push = MasterHubPush(
        _scene({}),
        post_dial=lambda pixels, width, height: dial_posts.append((pixels, width, height)),
        post_key=lambda pixels, width, height: key_posts.append((pixels, width, height)),
    )
    push.push_now()
    assert dial_posts == []
    assert key_posts == []


def test_mirror_is_a_noop_without_a_browser(bitmap_editor):
    """On the first frame off the browser the bridge is absent, so nothing is wired or pushed."""
    bitmap_editor._mirror_canvas_to_masterhub()
    assert bitmap_editor._masterhub_push is None
    assert bitmap_editor._masterhub_configured is True


def test_mirror_pushes_through_the_attached_push(bitmap_editor):
    """With a push attached, each frame drives it (posting the dial and the key)."""
    dial_posts: list[tuple[bytes, int, int]] = []
    key_posts: list[tuple[bytes, int, int]] = []
    push = MasterHubPush(
        _scene({'idle': [_frame(RED)]}, selected='idle'),
        post_dial=lambda pixels, width, height: dial_posts.append((pixels, width, height)),
        post_key=lambda pixels, width, height: key_posts.append((pixels, width, height)),
    )
    bitmap_editor._masterhub_configured = True  # skip the browser install
    bitmap_editor.set_masterhub_push(push)
    bitmap_editor._mirror_canvas_to_masterhub()
    assert dial_posts == [(bytes(RED), 1, 1)]
    assert key_posts == [(bytes(RED), 1, 1)]


def test_set_masterhub_push_is_idempotent(bitmap_editor):
    """A second attach is ignored; the first push stays (the bridge may run more than once)."""
    first = MasterHubPush(_scene({}), post_dial=lambda *_: None, post_key=lambda *_: None)
    second = MasterHubPush(_scene({}), post_dial=lambda *_: None, post_key=lambda *_: None)
    bitmap_editor.set_masterhub_push(first)
    bitmap_editor.set_masterhub_push(second)
    assert bitmap_editor._masterhub_push is first
