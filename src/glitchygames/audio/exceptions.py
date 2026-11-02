"""Audio exceptions.

Every audio error derives from ``GlitchyGamesAudioError`` and keeps the builtin base its callers
already catch (``RuntimeError`` or ``ValueError``).
"""


class GlitchyGamesAudioError(Exception):
    """The base of every audio error."""


class AudioUnavailableError(GlitchyGamesAudioError, RuntimeError):
    """The mixer is not initialized or uses a format the synth cannot produce."""


class SoundRecipeError(GlitchyGamesAudioError, ValueError):
    """A sound recipe is invalid; the message names the recipe and field."""


class SoundRenderError(GlitchyGamesAudioError, RuntimeError):
    """A compile failed (a bug, such as non-finite samples); the message names the sound."""
