"""The ``sound-render`` and ``sound-migrate`` tools: a sound to a WAV file, and v0 recipes to v1.

Both run no game (registry.py's ``TOOLS``):

- **sound-render** (``mygame --sound-render SOURCE --sound-output PATH [--sample-format F]``, or
  ``glitchygames sound-render ...``): compiles SOURCE (a sound file and the sound in it,
  ``sounds/pickups.toml#coin``, or a WAV/OGG file) as a game's ``audio.sound`` would, with no
  mixer running, and writes it with ``glitchygames.audio.render_to_file`` (offline: no audio
  device; the compiled buffer bit for bit). An OGG file needs a mixer to decode, so it is
  refused here (UNUSABLE_INPUT).
- **sound-migrate** (``mygame --sound-migrate FILE [--migrated-output PATH]``, or
  ``glitchygames sound-migrate ...``): rewrites a version 0 recipe file (``[recipes.<name>]``) as
  a version 1 sound file (feature spec 9.1; impl spec 10.4), written with ``tomli_w`` beside it as
  ``<stem>.v1.toml`` (or at PATH; never over FILE). Each recipe becomes an instrument and a sound
  of the same name: each tone a source (``tone_1``...: its wave or white noise, its start pitch,
  its pitch curve, its filter and its volume as the source's level), the tones' shared envelope
  the instrument's (linear, as version 0's), the recipe's ``peak`` the instrument's normalization
  (version 1 normalizes to -1 dBFS, so the sound's volume is the recipe's ``volume`` x ``peak`` /
  that level, the same loudness), and the sound held for the tones' duration less the release
  (version 0's release ends inside the duration; version 1's follows the held part). Migrated
  sounds follow the version 1 renderer (band-limited waves, its envelope stages, its noise seed),
  so they are close to the recipe, not equal to it: impl spec 10.4 checks them by listening.

  A recipe version 1 cannot say yet is refused, every such field named with the milestone that
  would make it migratable (or that none plans it), and nothing is written (games keep their
  version 0 files, which compile bit-identically through the legacy renderer): a tone that starts
  late (``offset``; per-tone offsets arrive in M4), a ``tremolo`` (LFOs arrive in M4),
  ``distortion`` (no version 1 form), both filters on one tone, tones held for different
  durations or with different envelopes (a version 1 sound has one length and the instrument one
  envelope), a tone not longer than its envelope's stages, more than four tones, a tone or
  recipe louder than a version 1 level or volume can be (1). The written file is loaded as a
  version 1 file before it replaces anything, so a value version 1 refuses (a sustain level
  above 1) is reported as the loader reports it.

Exit codes (``ExitCode``): ``SUCCESS``; ``MISSING_INPUT`` when the sound or recipe file does not
exist; ``UNUSABLE_INPUT`` when it cannot be read, is not what the tool takes or cannot be
migrated; ``OPTIONS_REFUSED`` when the migrated file would overwrite its input;
``CANNOT_WRITE_OUTPUT`` when the output cannot be written.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import tomli_w

from glitchygames.audio.accounting import AudioAccountant
from glitchygames.audio.assets import (
    CURRENT_SCHEMA_VERSION,
    INSTRUMENT_SEPARATOR,
    LEGACY_SCHEMA_VERSION,
    SOUND_FILE_KIND,
    load_sound_file,
)
from glitchygames.audio.exceptions import SoundAssetError, SoundRenderError
from glitchygames.audio.instrument import MAXIMUM_SOURCES, UNPITCHED_REFERENCE_HZ
from glitchygames.audio.library import CacheMode, SoundLibrary
from glitchygames.audio.offline import render_to_file
from glitchygames.audio.pitch import Tuning
from glitchygames.audio.render import NORMALIZED_PEAK
from glitchygames.audio.synth import Waveform
from glitchygames.audio.waves import current_wave_registry
from glitchygames.exit_codes import ExitCode
from glitchygames.output_files import output_refusal, write_aside_then_replace

if TYPE_CHECKING:
    import argparse

    from glitchygames.audio.assets import SoundFile
    from glitchygames.audio.recipes import SoundRecipe, Tone
    from glitchygames.replay.tools.registry import Tool
    from glitchygames.scenes import Scene

# The file sound-migrate writes beside FILE: <stem>.v1.toml
MIGRATED_SUFFIX: Final[str] = '.v1.toml'
# Version 0 waveforms and their version 1 waves (noise is a source of its own kind)
VERSION_1_WAVES: Final[dict[Waveform, str]] = {
    Waveform.SINE: 'sine',
    Waveform.SQUARE: 'square',
    Waveform.SAWTOOTH: 'saw',
    Waveform.TRIANGLE: 'triangle',
}
VERSION_1_NOISE: Final[str] = 'white'
# Version 0 envelopes are linear ramps (synth.apply_envelope)
VERSION_0_ENVELOPE_CURVE: Final[str] = 'linear'
SOURCE_NAME_PREFIX: Final[str] = 'tone_'
HIGHEST_LEVEL: Final[float] = 1.0


def sound_render(*, source: str, output: Path, sample_format: str) -> ExitCode:
    """Render a sound to a WAV file offline.

    Args:
        source: ``FILE#name`` (a sound file and the sound in it) or a WAV/OGG file.
        output: The WAV file to write.
        sample_format: ``int16`` or ``float32``.

    Returns:
        The exit code (see the module docstring).
    """
    sound_path = Path(source.partition(INSTRUMENT_SEPARATOR)[0])
    if not sound_path.is_file():
        sys.stderr.write(f'{sound_path}: no such sound file\n')
        return ExitCode.MISSING_INPUT
    refusal = output_refusal(path=output)
    if refusal is not None:
        sys.stderr.write(f'{refusal}\n')
        return ExitCode.CANNOT_WRITE_OUTPUT
    library = SoundLibrary(
        cache=CacheMode.RAM,
        accountant=AudioAccountant(),
        waves=current_wave_registry(),
        tuning_source=Tuning,
    )
    try:
        sound = library.sound(source, scene_sound_directory=None)
    except KeyError as error:
        sys.stderr.write(f'{source}: {error.args[0]}\n')
        return ExitCode.UNUSABLE_INPUT
    except (SoundAssetError, SoundRenderError, ValueError) as error:
        sys.stderr.write(f'{source}: {error}\n')
        return ExitCode.UNUSABLE_INPUT
    try:
        report = render_to_file(sound, output, sample_format=sample_format)
    except OSError as error:
        sys.stderr.write(f'{output} cannot be written ({error.strerror or error})\n')
        return ExitCode.CANNOT_WRITE_OUTPUT
    sys.stdout.write(
        f'wrote {report.path}: {report.frames} frames at {sound.sample_rate} Hz, '
        f'peak {report.peak:.3f}, {report.clip_count} samples clipped\n'
    )
    return ExitCode.SUCCESS


def sound_render_on_the_game(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
    """Run ``--sound-render SOURCE`` on a game (the game takes no part).

    Args:
        options: The game's parsed options (``sound_render``, ``sound_output``,
            ``sample_format``).
        game: The game (unused).

    Returns:
        ``sound_render``'s exit code.
    """
    del game
    return sound_render(
        source=options['sound_render'],
        output=Path(options['sound_output']),
        sample_format=options['sample_format'],
    )


def sound_render_command(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames sound-render SOURCE --sound-output PATH [--sample-format F]``.

    Args:
        tool: The sound-render tool (unused).
        arguments: The subcommand's parsed arguments.
        game_arguments: Always empty (the tool runs no game).

    Returns:
        ``sound_render``'s exit code.
    """
    del tool, game_arguments
    return sound_render(
        source=arguments.sound_render,
        output=Path(arguments.sound_output),
        sample_format=arguments.sample_format,
    )


def migrated_path(*, path: Path) -> Path:
    """Where ``sound-migrate`` writes a file's version 1 form by default.

    Args:
        path: The version 0 file.

    Returns:
        ``<stem>.v1.toml`` beside it.
    """
    return path.with_name(f'{path.stem}{MIGRATED_SUFFIX}')


def sound_migrate(*, path: Path, output: Path | None) -> ExitCode:  # ruff: ignore[too-many-return-statements] - one exit per refusal, in the order the docstring lists them
    """Rewrite a version 0 recipe file as a version 1 sound file.

    Args:
        path: The version 0 file.
        output: Where to write the version 1 file (None: ``migrated_path``).

    Returns:
        The exit code (see the module docstring).
    """
    if not path.is_file():
        sys.stderr.write(f'{path}: no such recipe file\n')
        return ExitCode.MISSING_INPUT
    destination = migrated_path(path=path) if output is None else output
    if destination.resolve() == path.resolve():
        sys.stderr.write(
            f'{destination}: would overwrite the file it migrates; give another --migrated-output\n'
        )
        return ExitCode.OPTIONS_REFUSED
    try:
        sound_file = load_sound_file(path)
    except SoundAssetError as error:
        sys.stderr.write(f'{error}\n')
        return ExitCode.UNUSABLE_INPUT
    if sound_file.version != LEGACY_SCHEMA_VERSION:
        sys.stderr.write(f'{path} is already a version {sound_file.version} sound file\n')
        return ExitCode.UNUSABLE_INPUT
    problems = migration_problems(sound_file)
    if problems:
        sys.stderr.write(f'{path} cannot be migrated to version {CURRENT_SCHEMA_VERSION} yet:\n')
        sys.stderr.writelines(f'  {problem}\n' for problem in problems)
        return ExitCode.UNUSABLE_INPUT
    refusal = output_refusal(path=destination)
    if refusal is not None:
        sys.stderr.write(f'{refusal}\n')
        return ExitCode.CANNOT_WRITE_OUTPUT
    text = tomli_w.dumps(migrated_document(sound_file))

    def write_checked(aside: Path) -> None:
        aside.write_text(text, encoding='utf-8')
        # Load what was written as a version 1 file before it replaces anything
        load_sound_file(aside)

    try:
        write_aside_then_replace(destination=destination, write=write_checked)
    except SoundAssetError as error:
        sys.stderr.write(f'{path}: the migrated file would not load: {error}\n')
        return ExitCode.UNUSABLE_INPUT
    except OSError as error:
        sys.stderr.write(f'{destination} cannot be written ({error.strerror or error})\n')
        return ExitCode.CANNOT_WRITE_OUTPUT
    sys.stdout.write(f'wrote {destination}: {len(sound_file.sounds)} sounds\n')
    return ExitCode.SUCCESS


def sound_migrate_on_the_game(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
    """Run ``--sound-migrate FILE`` on a game (the game takes no part).

    Args:
        options: The game's parsed options (``sound_migrate``, ``migrated_output``).
        game: The game (unused).

    Returns:
        ``sound_migrate``'s exit code.
    """
    del game
    output = options['migrated_output']
    return sound_migrate(
        path=Path(options['sound_migrate']),
        output=Path(output) if output is not None else None,
    )


def sound_migrate_command(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames sound-migrate FILE [--migrated-output PATH]``.

    Args:
        tool: The sound-migrate tool (unused).
        arguments: The subcommand's parsed arguments.
        game_arguments: Always empty (the tool runs no game).

    Returns:
        ``sound_migrate``'s exit code.
    """
    del tool, game_arguments
    output = arguments.migrated_output
    return sound_migrate(
        path=Path(arguments.sound_migrate),
        output=Path(output) if output is not None else None,
    )


def migration_problems(sound_file: SoundFile) -> list[str]:
    """Name every field of a version 0 file that version 1 cannot say yet.

    Args:
        sound_file: The loaded version 0 file.

    Returns:
        One line per problem (``recipes.<name>.tones[i].<field>: why``), in file order.
    """
    problems: list[str] = []
    for entry in sound_file.sounds.values():
        assert entry.legacy_recipe is not None  # every entry of a version 0 file is a recipe
        problems.extend(_recipe_problems(entry.legacy_recipe))
    return problems


def _recipe_problems(recipe: SoundRecipe) -> list[str]:
    """Name every field of one recipe that version 1 cannot say yet.

    Returns:
        The problems.
    """
    where = f'recipes.{recipe.name}'
    tones = recipe.tones
    if not tones:
        return [
            (
                f'{where}.tones: a version 1 instrument needs at least one source in every '
                'milestone; give a tone'
            )
        ]
    problems: list[str] = []
    if len(tones) > MAXIMUM_SOURCES:
        problems.append(
            f'{where}.tones: {len(tones)} tones; a version 1 instrument has at most '
            f'{MAXIMUM_SOURCES} sources, and no milestone raises that'
        )
    for index, tone in enumerate(tones):
        problems.extend(_tone_problems(tone, first=tones[0], where=f'{where}.tones[{index}]'))
    volume = _sound_volume(recipe)
    if volume > HIGHEST_LEVEL:
        problems.append(
            f'{where}.volume: {recipe.volume} at peak {recipe.peak} needs a version 1 volume of '
            f'{volume:.3f}, above {HIGHEST_LEVEL}, which no milestone allows'
        )
    return problems


def _tone_problems(tone: Tone, *, first: Tone, where: str) -> list[str]:
    """Name every field of one tone that a version 1 source cannot say.

    Returns:
        The problems.
    """
    problems: list[str] = []
    if tone.offset > 0.0:  # never negative: Tone refuses that
        problems.append(
            f'{where}.offset: {tone.offset} s needs per-tone offsets, which version 1 sound '
            'files gain in M4'
        )
    if tone.tremolo is not None:
        problems.append(
            f'{where}.tremolo: needs a tremolo LFO, which version 1 sound files gain in M4'
        )
    if tone.distortion is not None:
        problems.append(
            f'{where}.distortion: needs per-tone distortion, which no milestone gives version 1 '
            "sound files (drive is the whole instrument's, and shapes differently)"
        )
    if tone.low_pass_cutoff is not None and tone.high_pass_cutoff is not None:
        problems.append(
            f'{where}.high_pass_cutoff: needs a second filter on one tone (it has a low-pass '
            'too), which no milestone gives version 1 sources (one filter each)'
        )
    if tone.volume > HIGHEST_LEVEL:
        problems.append(
            f'{where}.volume: {tone.volume}; a version 1 source level is at most '
            f'{HIGHEST_LEVEL}, and no milestone raises that'
        )
    envelope = tone.envelope
    stages = envelope.attack + envelope.decay + envelope.release
    if tone.duration != first.duration:
        problems.append(
            f'{where}.duration: {tone.duration} s, but tones[0] is held {first.duration} s; '
            'needs per-tone lengths, which no milestone gives version 1 sound files yet (a sound '
            'has one length)'
        )
    elif envelope.release >= tone.duration or stages > tone.duration:
        problems.append(
            f'{where}.duration: {tone.duration} s must be longer than its envelope '
            f'(attack, decay and release: {stages} s); version 1 never cuts an envelope short, '
            'in any milestone'
        )
    if envelope != first.envelope:
        problems.append(
            f"{where}.envelope: differs from tones[0]'s; needs one envelope per tone, which no "
            'milestone gives version 1 instruments yet (one amplifier envelope)'
        )
    return problems


def _sound_volume(recipe: SoundRecipe) -> float:
    """The version 1 volume that plays a recipe as loud: its volume, at its peak, at -1 dBFS.

    Returns:
        The volume.
    """
    return recipe.volume * recipe.peak / NORMALIZED_PEAK


def migrated_document(sound_file: SoundFile) -> dict[str, Any]:
    """Build the version 1 document of a version 0 file whose recipes can all be migrated.

    Args:
        sound_file: The loaded version 0 file (``migration_problems`` finds none in it).

    Returns:
        The TOML document: the header, an instrument and a sound per recipe, by name.

    Raises:
        ValueError: When a recipe cannot be migrated (naming each problem).
    """
    problems = migration_problems(sound_file)
    if problems:
        raise ValueError('\n'.join(problems))
    instruments: dict[str, Any] = {}
    sounds: dict[str, Any] = {}
    for name, entry in sound_file.sounds.items():
        recipe = entry.legacy_recipe
        assert recipe is not None
        instruments[name] = _instrument_table(recipe)
        sounds[name] = _sound_table(recipe, instrument=name)
    return {
        'glitchygames': {'kind': SOUND_FILE_KIND, 'version': CURRENT_SCHEMA_VERSION},
        'instruments': instruments,
        'sounds': sounds,
    }


def _instrument_table(recipe: SoundRecipe) -> dict[str, Any]:
    """A recipe's ``[instruments.<name>]`` table.

    Returns:
        The table.
    """
    envelope = recipe.tones[0].envelope
    return {
        'envelope': {
            'attack': envelope.attack,
            'decay': envelope.decay,
            'sustain': envelope.sustain_level,
            'release': envelope.release,
            'curve': VERSION_0_ENVELOPE_CURVE,
        },
        'normalize': True,
        'sources': {
            f'{SOURCE_NAME_PREFIX}{index}': _source_table(tone)
            for index, tone in enumerate(recipe.tones, start=1)
        },
    }


def _source_table(tone: Tone) -> dict[str, Any]:
    """A tone's ``[instruments.<name>.sources.tone_<n>]`` table.

    Returns:
        The table.
    """
    table: dict[str, Any]
    if tone.waveform is Waveform.NOISE:
        # Version 0 noise ignores its frequencies
        table = {'noise': VERSION_1_NOISE}
    else:
        table = {'wave': VERSION_1_WAVES[tone.waveform], 'pitch': float(tone.start_frequency)}
        if tone.end_frequency is not None:
            table['pitch_curve'] = {
                'to': float(tone.end_frequency),
                'seconds': tone.duration,
                'easing': tone.easing,
            }
    if tone.low_pass_cutoff is not None:
        table['filter'] = {'type': 'low_pass', 'cutoff': float(tone.low_pass_cutoff)}
    elif tone.high_pass_cutoff is not None:
        table['filter'] = {'type': 'high_pass', 'cutoff': float(tone.high_pass_cutoff)}
    table['level'] = tone.volume
    return table


def _sound_table(recipe: SoundRecipe, *, instrument: str) -> dict[str, Any]:
    """A recipe's ``[sounds.<name>]`` table.

    The sound's pitch is its first pitched tone's (every source has its own fixed pitch, so this
    only names the note); an all-noise recipe gets the unpitched reference, so its noise runs at
    its own rate and the sound is held for its length.

    Returns:
        The table.
    """
    first = recipe.tones[0]
    pitched = [tone for tone in recipe.tones if tone.waveform is not Waveform.NOISE]
    pitch = float(pitched[0].start_frequency) if pitched else UNPITCHED_REFERENCE_HZ
    return {
        'instrument': instrument,
        'pitch': pitch,
        'length': first.duration - first.envelope.release,
        'volume': _sound_volume(recipe),
    }
