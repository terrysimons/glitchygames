"""Browser-only bridge: post bitmappy's canvas to a MasterHUB web hub in a sibling iframe.

This runs only in the browser bundle (PyScript/Pyodide), where ``js`` and ``pyodide.ffi`` exist, so
it lives here in the browser layer rather than in the type-checked bitmappy package. It builds a
``postMessage`` poster, wires a ``MasterHubPush`` to the editor scene's canvas, and listens for the
hub's "ready" announcement to re-post the current sprite when the hub (re)connects.
"""

import js
from bitmappy.masterhub_push import BITMAPPY_SOURCE, FRAME_TYPE, MasterHubPush
from pyodide.ffi import create_proxy

HUB_SOURCE = 'masterhub-hub'  # the hub's messages to us
READY_TYPE = 'ready'  # the hub is up and wants the current sprite


def install(scene):
    """Wire the scene's canvas to the sibling MasterHUB hub iframe and attach the push to the scene.

    Posts a ``masterhub-bitmappy`` ``frame`` (a ``Uint8Array`` of RGBA pixels plus width and height)
    to ``window.parent`` whenever the canvas changes, and re-posts the current sprite when the hub
    announces ``ready`` (so a freshly (re)connected hub shows what is being drawn).
    """

    def poster(pixels, width, height):
        array = js.Uint8Array.new(len(pixels))
        array.assign(pixels)
        message = js.Object.new()
        message.source = BITMAPPY_SOURCE
        message.type = FRAME_TYPE
        message.pixels = array
        message.width = width
        message.height = height
        js.window.parent.postMessage(message, '*')

    push = MasterHubPush(scene.canvas, poster=poster)

    def on_message(event):
        data = event.data
        if data and data.source == HUB_SOURCE and data.type == READY_TYPE:
            push.push_now()

    js.window.addEventListener('message', create_proxy(on_message))
    scene.set_masterhub_push(push)
