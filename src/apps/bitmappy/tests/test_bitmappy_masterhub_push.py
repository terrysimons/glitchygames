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
    color: tuple[int, int, int, int] = (0, 0, 0, 255)
    onion_transparency: float = 0.5

    def get_current_color(self) -> tuple[int, int, int, int]:
        return self.color

    def apply_color(self, *, red: int, green: int, blue: int, alpha: int) -> None:
        self.color = (red, green, blue, alpha)

    def set_onion_skin_transparency(self, transparency: float) -> None:
        self.onion_transparency = transparency


def _push_for(scene: _FakeScene) -> MasterHubPush:
    return MasterHubPush(
        scene,
        post_dial=lambda *_: None,
        post_key=lambda *_: None,
        post_knob_colors=lambda *_: None,
        post_fader_colors=lambda *_: None,
        post_color=lambda *_: None,
    )


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
        post_knob_colors=lambda *_: None,
        post_fader_colors=lambda *_: None,
        post_color=lambda *_: None,
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
        post_knob_colors=lambda *_: None,
        post_fader_colors=lambda *_: None,
        post_color=lambda *_: None,
    )
    push.push_now()
    push.push_now()
    assert len(dial_posts) == 2
    assert len(key_posts) == 2


def test_push_posts_the_colorwell_color_on_change():
    """push_if_changed posts the colorwell color when it changes, and dedups when it does not."""
    color_posts: list[tuple[int, int, int, int]] = []
    scene = _scene({})
    scene.color = (10, 20, 30, 255)
    push = MasterHubPush(
        scene,
        post_dial=lambda *_: None,
        post_key=lambda *_: None,
        post_knob_colors=lambda *_: None,
        post_fader_colors=lambda *_: None,
        post_color=lambda red, green, blue, alpha: color_posts.append((red, green, blue, alpha)),
    )
    push.push_if_changed()
    assert color_posts == [(10, 20, 30, 255)]
    push.push_if_changed()  # unchanged -> no new post
    assert len(color_posts) == 1
    scene.color = (40, 50, 60, 128)
    push.push_if_changed()
    assert color_posts[-1] == (40, 50, 60, 128)


def test_push_now_posts_the_colorwell_color_unconditionally():
    """push_now posts the colorwell color even when unchanged (connect / hub 'ready' re-post)."""
    color_posts: list[tuple[int, int, int, int]] = []
    push = MasterHubPush(
        _scene({}),
        post_dial=lambda *_: None,
        post_key=lambda *_: None,
        post_knob_colors=lambda *_: None,
        post_fader_colors=lambda *_: None,
        post_color=lambda red, green, blue, alpha: color_posts.append((red, green, blue, alpha)),
    )
    push.push_now()
    push.push_now()
    assert color_posts == [(0, 0, 0, 255), (0, 0, 0, 255)]


def test_push_now_posts_the_fixed_knob_led_colors():
    """push_now posts the fixed knob LED legend, by knob index: 0 blue, 1 green, 2 red."""
    knob_posts: list[tuple[tuple[int, int, int], ...]] = []
    push = MasterHubPush(
        _scene({'idle': [_frame(RED)]}, selected='idle'),
        post_dial=lambda *_: None,
        post_key=lambda *_: None,
        post_knob_colors=lambda colors: knob_posts.append(tuple(colors)),
        post_fader_colors=lambda *_: None,
        post_color=lambda *_: None,
    )
    push.push_now()
    assert knob_posts == [((0, 0, 255), (0, 255, 0), (255, 0, 0))]  # blue, green, red by index


def test_push_now_posts_the_knob_legend_even_with_an_empty_sprite():
    """The knob legend is independent of the sprite, so it goes out before anything is drawn."""
    knob_posts: list[tuple[tuple[int, int, int], ...]] = []
    push = MasterHubPush(
        _scene({}),
        post_dial=lambda *_: None,
        post_key=lambda *_: None,
        post_knob_colors=lambda colors: knob_posts.append(tuple(colors)),
        post_fader_colors=lambda *_: None,
        post_color=lambda *_: None,
    )
    push.push_now()
    assert knob_posts == [((0, 0, 255), (0, 255, 0), (255, 0, 0))]


def test_push_if_changed_posts_the_knob_legend_once_as_a_safety_net():
    """A missed hub 'ready' would leave the knobs dark, so the first push_if_changed posts them."""
    knob_posts: list[tuple[tuple[int, int, int], ...]] = []
    push = MasterHubPush(
        _scene({'idle': [_frame(RED)]}, selected='idle'),
        post_dial=lambda *_: None,
        post_key=lambda *_: None,
        post_knob_colors=lambda colors: knob_posts.append(tuple(colors)),
        post_fader_colors=lambda *_: None,
        post_color=lambda *_: None,
    )
    push.push_if_changed()
    assert knob_posts == [((0, 0, 255), (0, 255, 0), (255, 0, 0))]  # posted once on the first frame
    push.push_if_changed()  # already posted -> not again per frame
    assert len(knob_posts) == 1


def test_push_now_posts_the_fixed_fader_led_colors():
    """push_now posts the fixed fader LED legend by index, left to right: H/S/V/alpha/onion."""
    fader_posts: list[tuple[tuple[int, int, int], ...]] = []
    push = MasterHubPush(
        _scene({'idle': [_frame(RED)]}, selected='idle'),
        post_dial=lambda *_: None,
        post_key=lambda *_: None,
        post_knob_colors=lambda *_: None,
        post_fader_colors=lambda colors: fader_posts.append(tuple(colors)),
        post_color=lambda *_: None,
    )
    push.push_now()
    assert fader_posts == [
        ((255, 255, 0), (0, 255, 255), (255, 255, 255), (255, 0, 255), (255, 128, 0))
    ]  # hue yellow, saturation cyan, value white, alpha magenta, onion orange, left to right


def test_push_if_changed_posts_the_fader_legend_once_as_a_safety_net():
    """Likewise the fader legend: the first push_if_changed posts it once, later frames do not."""
    fader_posts: list[tuple[tuple[int, int, int], ...]] = []
    push = MasterHubPush(
        _scene({'idle': [_frame(RED)]}, selected='idle'),
        post_dial=lambda *_: None,
        post_key=lambda *_: None,
        post_knob_colors=lambda *_: None,
        post_fader_colors=lambda colors: fader_posts.append(tuple(colors)),
        post_color=lambda *_: None,
    )
    push.push_if_changed()
    assert fader_posts == [
        ((255, 255, 0), (0, 255, 255), (255, 255, 255), (255, 0, 255), (255, 128, 0))
    ]
    push.push_if_changed()  # already posted -> not again per frame
    assert len(fader_posts) == 1


def test_mark_hub_disconnected_makes_the_next_push_a_full_fresh_handshake():
    """The heartbeat's disconnect path forgets pushed state, so the next push re-handshakes."""
    dial_posts: list[object] = []
    knob_posts: list[object] = []
    fader_posts: list[object] = []
    color_posts: list[object] = []
    scene = _scene({'idle': [_frame(RED)]}, selected='idle')
    scene.color = (10, 20, 30, 255)
    push = MasterHubPush(
        scene,
        post_dial=lambda *args: dial_posts.append(args),
        post_key=lambda *_: None,
        post_knob_colors=lambda colors: knob_posts.append(tuple(colors)),
        post_fader_colors=lambda colors: fader_posts.append(tuple(colors)),
        post_color=lambda *args: color_posts.append(args),
    )
    push.push_if_changed()  # first push: legends + dial + color go out
    push.push_if_changed()  # nothing changed, legends already posted -> no new posts
    assert (len(knob_posts), len(fader_posts), len(dial_posts), len(color_posts)) == (1, 1, 1, 1)
    push.mark_hub_disconnected()  # the disconnect path: forget everything pushed
    push.push_if_changed()  # re-handshake: legends re-post, dial and color redraw fresh
    assert (len(knob_posts), len(fader_posts), len(dial_posts), len(color_posts)) == (2, 2, 2, 2)


def test_knob_delta_nudges_the_channel_each_knob_drives():
    """Knob 2 drives R, knob 1 G, knob 0 B; a positive delta raises that channel."""
    scene = _scene({})
    scene.color = (0, 0, 0, 255)
    push = _push_for(scene)
    push.apply_knob_delta(knob=2, delta=5)
    assert scene.color == (5, 0, 0, 255)  # knob 2 -> red
    push.apply_knob_delta(knob=1, delta=10)
    assert scene.color == (5, 10, 0, 255)  # knob 1 -> green
    push.apply_knob_delta(knob=0, delta=3)
    assert scene.color == (5, 10, 3, 255)  # knob 0 -> blue


def test_knob_delta_clamps_to_the_channel_range():
    """A nudge never leaves 0-255: down past 0 clamps to 0, up past 255 clamps to 255."""
    scene = _scene({})
    scene.color = (2, 253, 0, 255)
    push = _push_for(scene)
    push.apply_knob_delta(knob=2, delta=-10)  # R 2 -> 0
    push.apply_knob_delta(knob=1, delta=10)  # G 253 -> 255
    assert scene.color == (0, 255, 0, 255)


def test_knob_delta_leaves_alpha_untouched():
    """The knobs are an RGB picker; a knob turn never changes alpha."""
    scene = _scene({})
    scene.color = (10, 20, 30, 128)
    push = _push_for(scene)
    push.apply_knob_delta(knob=0, delta=5)  # B 30 -> 35
    assert scene.color == (10, 20, 35, 128)


def test_knob_delta_ignores_an_out_of_range_knob():
    """Only knobs 0-2 map to a channel; any other index changes nothing."""
    scene = _scene({})
    scene.color = (10, 20, 30, 255)
    push = _push_for(scene)
    push.apply_knob_delta(knob=3, delta=50)
    assert scene.color == (10, 20, 30, 255)


def test_fader_sets_hue_through_hsv_preserving_the_rest():
    """Fader 0 is hue: at 50% it rotates red to cyan, keeping full saturation, value and alpha."""
    scene = _scene({})
    scene.color = (255, 0, 0, 255)  # HSV (0, 1, 1)
    push = _push_for(scene)
    push.apply_fader(fader=0, position=50)  # hue -> 0.5
    assert scene.color == (0, 255, 255, 255)  # cyan, same S/V/A


def test_fader_sets_saturation():
    """Fader 1 is saturation: at 0% a fully saturated color washes out to white (value kept)."""
    scene = _scene({})
    scene.color = (0, 255, 255, 255)  # HSV (0.5, 1, 1)
    push = _push_for(scene)
    push.apply_fader(fader=1, position=0)  # saturation -> 0
    assert scene.color == (255, 255, 255, 255)


def test_fader_sets_value():
    """Fader 2 is value/brightness: at 0% any color goes to black."""
    scene = _scene({})
    scene.color = (0, 255, 255, 255)
    push = _push_for(scene)
    push.apply_fader(fader=2, position=0)  # value -> 0
    assert scene.color == (0, 0, 0, 255)


def test_fader_sets_alpha_as_a_percent_of_255():
    """Fader 3 is alpha: 0% is transparent, 100% opaque; the RGB is untouched."""
    scene = _scene({})
    scene.color = (10, 20, 30, 255)
    push = _push_for(scene)
    push.apply_fader(fader=3, position=0)
    assert scene.color == (10, 20, 30, 0)
    push.apply_fader(fader=3, position=100)
    assert scene.color == (10, 20, 30, 255)


def test_fader_sets_onion_skin_translucency_as_a_fraction():
    """Fader 4 is the onion-skin translucency: its 0-100 position becomes a 0.0-1.0 fraction."""
    scene = _scene({})
    push = _push_for(scene)
    push.apply_fader(fader=4, position=50)
    assert scene.onion_transparency == 0.5
    push.apply_fader(fader=4, position=100)
    assert scene.onion_transparency == 1.0


def test_fader_clamps_a_position_past_full():
    """A position past 100 is clamped (defensive), so alpha never exceeds 255."""
    scene = _scene({})
    scene.color = (10, 20, 30, 0)
    push = _push_for(scene)
    push.apply_fader(fader=3, position=150)
    assert scene.color == (10, 20, 30, 255)


def test_fader_ignores_an_out_of_range_index():
    """A fader index with no target changes neither the color nor the onion skin."""
    scene = _scene({})
    scene.color = (10, 20, 30, 255)
    push = _push_for(scene)
    push.apply_fader(fader=5, position=100)
    assert scene.color == (10, 20, 30, 255)
    assert scene.onion_transparency == 0.5


def test_push_skips_an_empty_sprite():
    """With no frames at all, a push posts nothing to either screen."""
    dial_posts: list[tuple[bytes, int, int]] = []
    key_posts: list[tuple[bytes, int, int]] = []
    push = MasterHubPush(
        _scene({}),
        post_dial=lambda pixels, width, height: dial_posts.append((pixels, width, height)),
        post_key=lambda pixels, width, height: key_posts.append((pixels, width, height)),
        post_knob_colors=lambda *_: None,
        post_fader_colors=lambda *_: None,
        post_color=lambda *_: None,
    )
    push.push_now()
    assert dial_posts == []
    assert key_posts == []


def test_mirror_is_a_noop_without_a_browser(bitmap_editor):
    """On the first frame off the browser no installer is registered, so nothing is wired."""
    from bitmappy.masterhub import install_masterhub

    install_masterhub(installer=None)  # the no-hub state (the desktop / tests)
    bitmap_editor._mirror_canvas_to_masterhub()
    assert bitmap_editor._masterhub_push is None
    assert bitmap_editor._masterhub_configured is True


def test_mirror_installs_the_registered_masterhub_bridge(bitmap_editor):
    """When the page has registered a bridge installer, the first frame wires it to the scene."""
    from bitmappy.masterhub import install_masterhub

    wired: list[object] = []
    try:
        install_masterhub(installer=wired.append)
        bitmap_editor._mirror_canvas_to_masterhub()
        assert wired == [bitmap_editor]  # the installer got the editor scene, exactly once
        assert bitmap_editor._masterhub_configured is True
    finally:
        install_masterhub(installer=None)


def test_mirror_pushes_through_the_attached_push(bitmap_editor):
    """With a push attached, each frame drives it (posting the dial and the key)."""
    dial_posts: list[tuple[bytes, int, int]] = []
    key_posts: list[tuple[bytes, int, int]] = []
    push = MasterHubPush(
        _scene({'idle': [_frame(RED)]}, selected='idle'),
        post_dial=lambda pixels, width, height: dial_posts.append((pixels, width, height)),
        post_key=lambda pixels, width, height: key_posts.append((pixels, width, height)),
        post_knob_colors=lambda *_: None,
        post_fader_colors=lambda *_: None,
        post_color=lambda *_: None,
    )
    bitmap_editor._masterhub_configured = True  # skip the browser install
    bitmap_editor.set_masterhub_push(push)
    bitmap_editor._mirror_canvas_to_masterhub()
    assert dial_posts == [(bytes(RED), 1, 1)]
    assert key_posts == [(bytes(RED), 1, 1)]


def test_set_masterhub_push_is_idempotent(bitmap_editor):
    """A second attach is ignored; the first push stays (the bridge may run more than once)."""
    first = MasterHubPush(
        _scene({}),
        post_dial=lambda *_: None,
        post_key=lambda *_: None,
        post_knob_colors=lambda *_: None,
        post_fader_colors=lambda *_: None,
        post_color=lambda *_: None,
    )
    second = MasterHubPush(
        _scene({}),
        post_dial=lambda *_: None,
        post_key=lambda *_: None,
        post_knob_colors=lambda *_: None,
        post_fader_colors=lambda *_: None,
        post_color=lambda *_: None,
    )
    bitmap_editor.set_masterhub_push(first)
    bitmap_editor.set_masterhub_push(second)
    assert bitmap_editor._masterhub_push is first


def test_editor_set_onion_skin_transparency(bitmap_editor):
    """The editor seam a fader uses sets the onion-skin manager's translucency (and redraws)."""
    from bitmappy.onion_skinning import get_onion_skinning_manager

    bitmap_editor.set_onion_skin_transparency(0.3)
    assert get_onion_skinning_manager().onion_transparency == 0.3
