"""The score: the stage's loop, the stage clear and the game over, played on catalog instruments.

Feature plan 11 (plans/2026-11-18-zombies-aint-my-neighbors-11-the-rest-of-the-sounds.md). The
owner (2026-11-18): "stage music creation in the game setup and once we've landed the game we'll
refactor things as needed to pull stuff into the core."

A **cue** is layers played together, each one catalog instrument playing one melody, every layer
exactly as long as its cue (rests included). Each cue is compiled into one sound, an engine
``Mix`` (``glitchygames.audio.mix``): its layers rendered and added at their volumes, cached as
every sound is (the process's memory, then the disk layer, else compiled and written), so the
first request builds it and every later one, in this launch or a later one, gets the built copy
(the owner, 2026-11-18: "if you play a sound that hasnt been built, build it, then play the built
copy. Same as our other caching layer."). The stage's loop is a looping mix, exactly
``LOOP_SECONDS`` long with every tail folded onto its start, so ``play(loop=True)`` repeats it in
time, sample for sample, on one mixer channel.

The score is declared with the effects in ``SOUNDS`` (``SCORE``, on ``RosterScene``), so the
engine builds it while the game starts, during the CRT power-on, before any frame of play; each
scene's ``cue_sound`` then finds it built.

The score is written in beats; ``notes_text`` gives the engine its melody text in seconds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from glitchygames.audio import Mix, MixPart, instruments

if TYPE_CHECKING:
    from glitchygames.audio import AudioEngine, PlayingSound, Sound

# 120 beats a minute, four to the bar
BEAT_SECONDS: Final = 0.5
BAR_BEATS: Final = 4
# The engine's rest
REST: Final = '_'
# Every cue plays on the music bus, above the effects' default priority (50), so a storm of zaps
# never steals it, at full volume: each layer's own volume is mixed into the cue's sound
MUSIC_BUS: Final = 'music'
MUSIC_PRIORITY: Final = 80
MUSIC_VOLUME: Final = 1.0

type Notes = tuple[tuple[str, float], ...]


class Layer(BaseModel):
    """One instrument's part in a cue: its melody, in beats, and its volume."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    instrument: str
    notes: Notes
    volume: float


class Cue(BaseModel):
    """Layers played together, compiled into one sound: a loop, or a sting played once."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    name: str
    seconds: float
    loops: bool
    layers: tuple[Layer, ...]


def _bars(*bars: Notes) -> Notes:
    """Return bars joined into one melody.

    Returns:
        The notes.

    """
    return tuple(note for bar in bars for note in bar)


def _held_bars(*pitches: str) -> Notes:
    """Return whole bars each holding one pitch, lifted a half beat before the next bar.

    Returns:
        The notes.

    """
    return _bars(*(((pitch, BAR_BEATS - 0.5), (REST, 0.5)) for pitch in pitches))


THEREMIN: Final = 'theremin'
ORGAN: Final = 'theatre organ'
BASS: Final = 'double bass pizzicato'
TIMPANI: Final = 'timpani'

# The stage: D minor, eight bars (Dm Dm Bb A, Dm Gm Bb A). A theremin over a theatre organ's
# chords, a pizzicato bass walking in quarters, and timpani on bars 1 and 5 with a pickup of three
# hits into each
LOOP_BARS: Final = 8
LOOP_SECONDS: Final = LOOP_BARS * BAR_BEATS * BEAT_SECONDS
_TIMPANI_PICKUP: Final[Notes] = ((REST, 2), ('A2', 0.5), ('A2', 0.5), ('A2', 1))
_TIMPANI_DOWNBEAT: Final[Notes] = (('D2', 1), (REST, 3))
_EMPTY_BAR: Final[Notes] = ((REST, BAR_BEATS),)
STAGE: Final = Cue(
    name='stage',
    seconds=LOOP_SECONDS,
    loops=True,
    layers=(
        Layer(
            instrument=THEREMIN,
            volume=0.3,
            notes=_bars(
                (('D5', 2), ('A4', 2)),
                (('F5', 1), ('E5', 1), ('D5', 2)),
                (('Bb4', 3), (REST, 1)),
                (('A4', 2), ('C#5', 2)),
                (('D5', 2), ('F5', 2)),
                (('G5', 1.5), ('F5', 0.5), ('D5', 2)),
                (('F5', 2), ('E5', 1), ('D5', 1)),
                (('C#5', 3), (REST, 1)),
            ),
        ),
        Layer(
            instrument=ORGAN,
            volume=0.15,
            notes=_held_bars('A4', 'A4', 'F4', 'E4', 'A4', 'G4', 'F4', 'E4'),
        ),
        Layer(
            instrument=ORGAN,
            volume=0.15,
            notes=_held_bars('F4', 'F4', 'D4', 'C#4', 'F4', 'D4', 'D4', 'C#4'),
        ),
        Layer(
            instrument=BASS,
            volume=0.35,
            notes=_bars(
                (('D2', 1), ('A2', 1), ('D3', 1), ('A2', 1)),
                (('D2', 1), ('A2', 1), ('F2', 1), ('E2', 1)),
                (('Bb1', 1), ('F2', 1), ('Bb2', 1), ('F2', 1)),
                (('A1', 1), ('E2', 1), ('A2', 1), ('C#3', 1)),
                (('D2', 1), ('A2', 1), ('D3', 1), ('A2', 1)),
                (('G2', 1), ('D2', 1), ('G2', 1), ('Bb2', 1)),
                (('Bb1', 1), ('F2', 1), ('Bb2', 1), ('D3', 1)),
                (('A1', 1), ('C#2', 1), ('E2', 1), ('A2', 1)),
            ),
        ),
        Layer(
            instrument=TIMPANI,
            volume=0.3,
            notes=_bars(
                _TIMPANI_DOWNBEAT,
                _EMPTY_BAR,
                _EMPTY_BAR,
                _TIMPANI_PICKUP,
                _TIMPANI_DOWNBEAT,
                _EMPTY_BAR,
                _EMPTY_BAR,
                _TIMPANI_PICKUP,
            ),
        ),
    ),
)

# The stage clear: the minor key's happy ending, D major, as the kids cheer (1.5 s)
STAGE_CLEAR: Final = Cue(
    name='stage-clear',
    seconds=3 * BEAT_SECONDS,
    loops=False,
    layers=(
        Layer(instrument=THEREMIN, volume=0.3, notes=(('D5', 0.5), ('F#5', 0.5), ('A5', 2))),
        Layer(instrument=ORGAN, volume=0.18, notes=(('F#4', 3),)),
        Layer(instrument=ORGAN, volume=0.18, notes=(('D4', 3),)),
        Layer(instrument=TIMPANI, volume=0.35, notes=(('D2', 3),)),
    ),
)

# The game over: dun, dun, DUNNN. Two short organ chords (D minor, then F) and a long one over a
# low C#, the timpani under them and the theremin wailing over the last (3 s)
GAME_OVER: Final = Cue(
    name='game-over',
    seconds=6 * BEAT_SECONDS,
    loops=False,
    layers=(
        Layer(
            instrument=ORGAN,
            volume=0.2,
            notes=(('F4', 0.75), (REST, 0.25), ('A4', 0.75), (REST, 0.25), ('F4', 4)),
        ),
        Layer(
            instrument=ORGAN,
            volume=0.2,
            notes=(('D3', 0.75), (REST, 0.25), ('F3', 0.75), (REST, 0.25), ('C#3', 4)),
        ),
        Layer(
            instrument=TIMPANI,
            volume=0.35,
            notes=(('D2', 0.75), (REST, 0.25), ('D2', 0.75), (REST, 0.25), ('A2', 4)),
        ),
        Layer(instrument=THEREMIN, volume=0.25, notes=((REST, 2), ('D5', 4))),
    ),
)

CUES: Final = (STAGE, STAGE_CLEAR, GAME_OVER)


def notes_text(layer: Layer) -> str:
    """Return a layer's melody as the engine reads one: ``pitch:seconds`` for each note or rest.

    Returns:
        The text.

    """
    return ' '.join(f'{pitch}:{beats * BEAT_SECONDS:g}' for pitch, beats in layer.notes)


def cue_mix(cue: Cue) -> Mix:
    """Return a cue as the engine's mix: a part a layer, a loop exactly the cue's length.

    Returns:
        The mix.

    """
    return Mix(
        name=cue.name,
        parts=tuple(
            MixPart(
                instrument=instruments.get(layer.instrument),
                notes=notes_text(layer),
                volume=layer.volume,
            )
            for layer in cue.layers
        ),
        loop_seconds=cue.seconds if cue.loops else None,
    )


# Every cue's mix, declared in SOUNDS so the engine builds them while the game starts
SCORE: Final = tuple(cue_mix(cue) for cue in CUES)


def cue_sound(audio: AudioEngine, cue: Cue) -> Sound:
    """Return a cue's sound: built on the first request (or read from the disk), the copy after.

    Returns:
        The sound.

    """
    return audio.sound(cue_mix(cue))


def play_cue(cue: Cue, sound: Sound) -> PlayingSound:
    """Play a cue's sound on the music bus, looping if the cue loops.

    Args:
        cue: The cue.
        sound: Its sound (``cue_sound``).

    Returns:
        The playing sound.

    """
    return sound.play(volume=MUSIC_VOLUME, bus=MUSIC_BUS, priority=MUSIC_PRIORITY, loop=cue.loops)


class StageMusic:
    """A stage's score: its loop, started once and looping by itself, and the clear it ends with.

    The stage asks for the sounds in ``setup`` (``prepare``), starts the loop on its first frame
    (``start``), and ends it with the clear (``play_the_clear``).
    """

    def __init__(self, *, loop: Cue = STAGE, clear: Cue = STAGE_CLEAR) -> None:
        """Make the score, its sounds not yet got.

        Args:
            loop: The looping cue.
            clear: The sting the stage ends with.

        """
        self.loop = loop
        self.clear = clear
        self._loop_sound: Sound | None = None
        self._clear_sound: Sound | None = None
        # The loop while it plays
        self._playing: PlayingSound | None = None
        self._started = False

    @property
    def loop_sound(self) -> Sound:
        """The loop's sound (after ``prepare``).

        Raises:
            RuntimeError: Before ``prepare``.

        """
        if self._loop_sound is None:
            message = 'the stage music is not prepared'
            raise RuntimeError(message)
        return self._loop_sound

    @property
    def clear_sound(self) -> Sound:
        """The clear's sound (after ``prepare``).

        Raises:
            RuntimeError: Before ``prepare``.

        """
        if self._clear_sound is None:
            message = 'the stage music is not prepared'
            raise RuntimeError(message)
        return self._clear_sound

    def prepare(self, audio: AudioEngine) -> None:
        """Get the sounds (built ahead by the card, or now).

        Args:
            audio: The audio engine.

        """
        self._loop_sound = cue_sound(audio, self.loop)
        self._clear_sound = cue_sound(audio, self.clear)

    def start(self) -> None:
        """Start the loop, once: it then repeats by itself until the clear."""
        if self._started:
            return
        self._started = True
        self._playing = play_cue(self.loop, self.loop_sound)

    def play_the_clear(self, *, fade: float) -> None:
        """Fade the loop out and play the clear.

        Args:
            fade: Seconds the loop takes to fade.

        """
        if self._playing is not None:
            self._playing.stop(fade=fade)
            self._playing = None
        self._started = True
        play_cue(self.clear, self.clear_sound)
