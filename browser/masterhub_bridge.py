"""Browser-only bridge: post bitmappy's canvas to a MasterHUB web hub in a sibling iframe.

This runs only in the browser bundle (PyScript/Pyodide), where ``js`` and ``pyodide.ffi`` exist, so
it lives here in the browser layer rather than in the type-checked bitmappy package. It builds a
``postMessage`` poster, wires a ``MasterHubPush`` to the editor scene's canvas, and listens for the
hub's messages: a "ready" announcement to re-post the current sprite when the hub (re)connects,
"knob_delta" turns that nudge the editor's R/G/B color channels (the knobs are the picker), and
"fader" moves that set the color's H/S/V/alpha or the onion-skin translucency (the faders).

It also runs a heartbeat: every few seconds it posts a "ping" and expects the hub to answer (a
"pong", or any message at all, is proof of life). If the hub goes quiet it runs the disconnect path
-- ``MasterHubPush.mark_hub_disconnected``, which forgets what was pushed so the next contact
re-handshakes from scratch -- and shows a "not connected" banner that clears when the hub speaks
again.
"""

import js
from bitmappy.masterhub_push import (
    BITMAPPY_SOURCE,
    COLOR_TYPE,
    FADER_COLORS_TYPE,
    FADER_TYPE,
    FRAME_TYPE,
    KEY_TYPE,
    KNOB_COLORS_TYPE,
    KNOB_DELTA_TYPE,
    MasterHubPush,
)
from pyodide.ffi import create_proxy

HUB_SOURCE = 'masterhub-hub'  # the hub's messages to us
READY_TYPE = 'ready'  # the hub is up and wants the current sprite
PING_TYPE = 'ping'  # bitmappy -> hub heartbeat: are you still there?
HEARTBEAT_INTERVAL_MS = 5000  # ping the hub this often
DISCONNECT_AFTER_MS = 12000  # no word from the hub for this long -> treat it as disconnected


def install(scene):
    """Wire the scene's canvas to the sibling MasterHUB hub iframe and attach the push to the scene.

    Posts two ``masterhub-bitmappy`` screen messages (each a ``Uint8Array`` of RGBA pixels plus
    width and height) to ``window.parent`` whenever they change: a ``frame`` (the selected strip's
    playing preview frame, for the dial) and a ``key`` (the idle first frame, for the center key);
    a ``knob_colors`` and a ``fader_colors`` message (each a list of ``[r, g, b]`` triples) carry
    the fixed M003K knob and M005S fader LED legends; and it re-posts all of them when the hub
    announces ``ready`` (so a freshly (re)connected hub shows the sprite and relights the controls).
    """

    def make_poster(message_type):
        def poster(pixels, width, height):
            array = js.Uint8Array.new(len(pixels))
            array.assign(pixels)
            message = js.Object.new()
            message.source = BITMAPPY_SOURCE
            message.type = message_type
            message.pixels = array
            message.width = width
            message.height = height
            js.window.parent.postMessage(message, '*')

        return poster

    def make_colors_poster(message_type):
        def poster(colors):
            array = js.Array.new()
            for color in colors:
                triple = js.Array.new()
                triple.push(color[0])
                triple.push(color[1])
                triple.push(color[2])
                array.push(triple)
            message = js.Object.new()
            message.source = BITMAPPY_SOURCE
            message.type = message_type
            message.colors = array
            js.window.parent.postMessage(message, '*')

        return poster

    def post_color(red, green, blue, alpha):
        message = js.Object.new()
        message.source = BITMAPPY_SOURCE
        message.type = COLOR_TYPE
        message.red = red
        message.green = green
        message.blue = blue
        message.alpha = alpha
        js.window.parent.postMessage(message, '*')

    push = MasterHubPush(
        scene,
        post_dial=make_poster(FRAME_TYPE),
        post_key=make_poster(KEY_TYPE),
        post_knob_colors=make_colors_poster(KNOB_COLORS_TYPE),
        post_fader_colors=make_colors_poster(FADER_COLORS_TYPE),
        post_color=post_color,
    )

    def post_ping():
        message = js.Object.new()
        message.source = BITMAPPY_SOURCE
        message.type = PING_TYPE
        js.window.parent.postMessage(message, '*')

    # The heartbeat's mutable state (a dict so the nested callbacks can rebind its fields).
    heartbeat = {'last_seen': js.Date.now(), 'connected': True}

    def show_disconnected(*, disconnected):
        banner = js.document.getElementById('masterhub-disconnected')
        if banner is None:
            banner = js.document.createElement('div')
            banner.id = 'masterhub-disconnected'
            banner.textContent = 'MasterHUB not connected'
            banner.setAttribute(
                'style',
                'position:fixed;top:0;left:0;right:0;z-index:2147483647;background:#b00020;'
                'color:#fff;font:600 13px system-ui,sans-serif;text-align:center;padding:4px',
            )
            js.document.body.appendChild(banner)
        banner.style.display = 'block' if disconnected else 'none'

    def on_message(event):
        data = event.data
        if not data or data.source != HUB_SOURCE:
            return
        heartbeat['last_seen'] = js.Date.now()  # any word from the hub is proof it is still there
        if not heartbeat['connected']:
            # The hub is back: the next push re-handshakes (mark_hub_disconnected reset the state).
            heartbeat['connected'] = True
            show_disconnected(disconnected=False)
        if data.type == READY_TYPE:
            push.push_now()
        elif data.type == KNOB_DELTA_TYPE:
            # A knob turn from the hub: nudge the color channel that knob drives (the RGB picker).
            push.apply_knob_delta(knob=data.knob, delta=data.delta)
        elif data.type == FADER_TYPE:
            # A fader move from the hub: set its target (H/S/V/alpha of the color, or onion skin).
            push.apply_fader(fader=data.fader, position=data.position)

    def heartbeat_tick():
        post_ping()
        if heartbeat['connected'] and js.Date.now() - heartbeat['last_seen'] > DISCONNECT_AFTER_MS:
            # The hub stopped answering: run the real disconnect path and say so on screen.
            heartbeat['connected'] = False
            push.mark_hub_disconnected()
            show_disconnected(disconnected=True)

    js.window.addEventListener('message', create_proxy(on_message))
    js.window.setInterval(create_proxy(heartbeat_tick), HEARTBEAT_INTERVAL_MS)
    scene.set_masterhub_push(push)
