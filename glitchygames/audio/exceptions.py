"""Audio exceptions."""


class AudioUnavailableError(RuntimeError):
    """The mixer is not initialized or uses a format the synth cannot produce."""


class SoundRecipeError(ValueError):
    """A sound recipe is invalid; the message names the recipe and field."""
