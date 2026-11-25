"""Feature flags: which features a run wants and can have.

plans/2026-11-24-feature-flags-and-lucid-circuit-switch.md is the design. Rules:

1. A flag is declared once, in ``FEATURE_FLAGS`` (``declare_flags`` refuses a wrong declaration
   as this module is imported). Each is an option of every game, ``--NAME`` / ``--no-NAME``,
   generated from its declaration (``add_flag_arguments``).
2. ``flag_state(name=...)`` answers for the current engine context, at each call: read it where
   it is used, never at import. A flag is off, with the reason, when it is unavailable here
   (whatever was asked), else when its parent is off (whatever was asked), else as its option
   was given, else as its default.
3. A flag says whether a feature is wanted and possible, no more. Whether a run may use it now
   stays the feature's own decision (``ai_link.create_link``: never with ``--headless``, never
   in a replay, only where the service is installed), which fails closed: options that hold no
   answer for the flag turn nothing on there.
4. A flag is local to the run: each engine keeps what its own command line asked
   (``take_flag_options``, before it reads a recording), and ``REPLAY_LOCAL_OPTIONS`` holds every
   flag's option, so a recording never sets one.
5. What a context was asked is only what was typed: a flag left at its default was not asked.

   - **Before any engine is made in it**, and with options that do not hold the flag (an older
     caller's, a test's), nothing was asked: the declared default answers, still subject to rule
     2's availability and parent. The default is the decision for a run nobody said anything
     about, and rule 3 keeps it from acting by itself.
   - **Before its own engine**, a launcher and a game's ``args()`` run: they see the default, or
     what an earlier engine in the context was asked. Read a flag there and it is not this run's.
   - **After a run** it stays as that run asked, until the next engine made in the context
     replaces it. The engine stops being current before its scenes clean up, and a clean-up must
     not find a feature on that the player turned off.
   - **An engine that fails as it is made** never ran: what was asked before it is put back.
   - **An inner game** (glitchygames/inner_game.py) has a context of its own, and its engine reads
     its own command line, which holds the outer game's arguments, then its host's: so
     ``--no-lucid-circuit`` on the outer game reaches each inner one, and a host's own wins.
   - **A thread** sees the default context unless started with a copied one (rule 5 of
     glitchygames/engine_context.py).

Every ``flags=`` parameter is for tests of declarations there are none of yet: production code
never passes it.

This module imports nothing of the engine but the context, so any module may import it.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable, Mapping, MutableMapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, ConfigDict, model_validator

from glitchygames.engine_context import ContextSlot, current_context

if TYPE_CHECKING:
    from glitchygames.replay.tools.registry import ArgumentContainer

# None when the feature can be on here, else why it cannot
Availability = Callable[[], str | None]
FlagDeclarations = Mapping[str, 'FeatureFlag']

FEATURE_FLAG_GROUP_TITLE = 'Feature Flags'
KEBAB_CASE_NAME = re.compile(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*')
LUCID_CIRCUIT = 'lucid-circuit'
# argparse.BooleanOptionalAction's prefix: a flag named with it would be another flag's "off"
OFF_PREFIX = 'no-'


class FeatureFlagDeclarationError(ValueError):
    """A flag's declaration is wrong (rule 1)."""


class UndeclaredFeatureFlagError(LookupError):
    """A flag nobody declared was asked for."""


class FlagOptionError(TypeError):
    """A run's options hold an answer for a flag that is not True, False or None."""


def available_everywhere() -> str | None:
    """Say that a feature can be on wherever the engine runs.

    Returns:
        None.

    """
    return None


class FeatureFlag(BaseModel):
    """One flag's declaration (read-only).

    Attributes:
        name: Unique, in kebab case: its option is ``--NAME`` / ``--no-NAME``.
        summary: The option's help text.
        default: Whether it is on when nothing is asked.
        parent: The flag that must be on for this one to be, or None.
        availability: Asked at each read: None, or the reason it cannot be on here.
        recorded: False: local to the run (rule 4). True is refused until a flag needs it.

    """

    model_config = ConfigDict(frozen=True, extra='forbid', strict=True)

    name: str
    summary: str
    default: bool
    parent: str | None = None
    availability: Availability = available_everywhere
    recorded: bool = False


class FlagState(BaseModel):
    """Whether a flag is on (read-only).

    Attributes:
        on: True when the feature is wanted and possible.
        reason: Why it is off; None when it is on.

    """

    model_config = ConfigDict(frozen=True, extra='forbid', strict=True)

    on: bool
    reason: str | None = None

    @model_validator(mode='after')
    def check_the_reason_is_given_exactly_when_off(self: Self) -> Self:
        """Refuse a flag off without a reason, or on with one.

        Returns:
            The state.

        Raises:
            ValueError: If it is either.

        """
        if self.on and self.reason is not None:
            message = f'a flag that is on has no reason to be off ({self.reason!r})'
            raise ValueError(message)
        if not self.on and not self.reason:
            message = 'a flag that is off needs the reason'
            raise ValueError(message)
        return self


def declare_flags(*declarations: FeatureFlag) -> dict[str, FeatureFlag]:
    """Check the declarations together, and return them by name.

    Args:
        declarations: The flags.

    Returns:
        The flags by name, in the order given.

    Raises:
        FeatureFlagDeclarationError: If a name is not kebab case, starts with ``no-`` or is
            declared twice, a parent is undeclared, a flag is its own ancestor, or one is
            declared recorded.

    """
    flags: dict[str, FeatureFlag] = {}
    for flag in declarations:
        message = _declaration_refusal(flag=flag)
        if message is None and flag.name in flags:
            message = f'Feature flag {flag.name!r} is declared twice'
        if message is not None:
            raise FeatureFlagDeclarationError(message)
        flags[flag.name] = flag
    for flag in flags.values():
        _refuse_wrong_ancestors(flag=flag, flags=flags)
    return flags


def _declaration_refusal(*, flag: FeatureFlag) -> str | None:
    """Return what is wrong with one declaration by itself, or None.

    Returns:
        The message, or None.

    """
    if KEBAB_CASE_NAME.fullmatch(flag.name) is None:
        return f'Feature flag {flag.name!r} is not kebab case'
    if flag.name.startswith(OFF_PREFIX):
        return (
            f'Feature flag {flag.name!r} starts with {OFF_PREFIX}, as the option that turns a '
            'flag off does'
        )
    if flag.recorded:
        return (
            f'Feature flag {flag.name!r} is declared recorded, which is not built: every flag is '
            'local to the run'
        )
    return None


def _refuse_wrong_ancestors(*, flag: FeatureFlag, flags: FlagDeclarations) -> None:
    """Follow a flag's parents to the top.

    Raises:
        FeatureFlagDeclarationError: If one is undeclared, or is met twice.

    """
    lineage = [flag.name]
    # Bounded by the number of flags: whoever has that many ancestors has met one twice
    for _ in flags:
        descendant = flags[lineage[-1]]
        if descendant.parent is None:
            return
        if descendant.parent not in flags:
            message = (
                f'Feature flag {descendant.name!r} has an undeclared parent, {descendant.parent!r}'
            )
            raise FeatureFlagDeclarationError(message)
        lineage.append(descendant.parent)
    met_twice = lineage[-1]
    upward = lineage[-2::-1]
    cycle = [*reversed(upward[: upward.index(met_twice) + 1]), met_twice]
    message = f'Feature flag {met_twice!r} is its own parent: {" -> ".join(cycle)}'
    raise FeatureFlagDeclarationError(message)


def lucid_circuit_availability() -> str | None:
    """Say whether Lucid Circuit can be on here: it runs in processes of its own.

    Returns:
        None, or that a browser page cannot start processes.

    """
    if sys.platform == 'emscripten':
        return 'unavailable in the browser, which cannot start processes'
    return None


# Every flag (rule 1): read-only
FEATURE_FLAGS: FlagDeclarations = MappingProxyType(
    declare_flags(
        FeatureFlag(
            name=LUCID_CIRCUIT,
            summary=(
                'Lucid Circuit, the local AI: it needs the AI service installed, and is never '
                'used with --headless or in a replay'
            ),
            default=True,
            availability=lucid_circuit_availability,
        )
    )
)


class FlagOptions:
    """What a context's latest engine was asked (rule 5), by option name.

    A plain class, not a frozen model: it is changed in place.

    Attributes:
        asked: The options typed; empty before any engine. Replaced, never changed in place.

    """

    def __init__(self: Self) -> None:
        """Start with nothing asked."""
        self.asked: Mapping[str, bool] = {}


FLAG_OPTIONS_SLOT: ContextSlot[FlagOptions] = ContextSlot(
    name='glitchygames.feature_flags.options', factory=FlagOptions
)


def option_name(*, flag_name: str) -> str:
    """Return the name a flag's option has in a run's options (``lucid_circuit``).

    Args:
        flag_name: The flag's name.

    Returns:
        The option's name: argparse's, from ``--NAME``.

    """
    return flag_name.replace('-', '_')


def add_flag_arguments(
    *, parser: ArgumentContainer, flags: FlagDeclarations = FEATURE_FLAGS
) -> None:
    """Add ``--NAME`` / ``--no-NAME`` for every flag.

    Args:
        parser: The parser or group to add them to.
        flags: The declared flags.

    """
    for flag in flags.values():
        notes = f'default: {"on" if flag.default else "off"}'
        if flag.parent is not None:
            notes = f'{notes}; off with --{OFF_PREFIX}{flag.parent}'
        parser.add_argument(
            f'--{flag.name}',
            # argparse formats help with %
            help=f'{flag.summary} ({notes})'.replace('%', '%%'),
            action=argparse.BooleanOptionalAction,
            # None: not typed. take_flag_options notes that, then puts the flag's default here
            default=None,
        )


def take_flag_options(
    *, options: MutableMapping[str, Any], flags: FlagDeclarations = FEATURE_FLAGS
) -> None:
    """Make these options the current context's answer to what was asked (rule 5).

    Called by each engine as it is made, with its own command line. They replace an earlier
    engine's whole: a flag they do not hold, or hold as None (not typed), was not asked. Each
    they hold as None then becomes its default, so a run logs and records a plain true or false;
    one they do not hold stays missing (rule 3 fails closed on it).

    Args:
        options: The run's options, changed in place.
        flags: The declared flags.

    Raises:
        FlagOptionError: If an answer is neither a bool nor None; nothing is then changed.

    """
    for flag in flags.values():
        answer = options.get(option_name(flag_name=flag.name))
        if answer is not None and not isinstance(answer, bool):
            message = f'--{flag.name}: expected True, False or None, not {answer!r}'
            raise FlagOptionError(message)
    asked: dict[str, bool] = {}
    for flag in flags.values():
        name = option_name(flag_name=flag.name)
        if name not in options:
            continue
        if options[name] is None:
            options[name] = flag.default
        else:
            asked[name] = options[name]
    current_context().value(slot=FLAG_OPTIONS_SLOT).asked = asked


def flag_state(*, name: str, flags: FlagDeclarations = FEATURE_FLAGS) -> FlagState:
    """Return whether a flag is on in the current engine context (rule 2).

    Args:
        name: The flag's name (``'lucid-circuit'``).
        flags: The declared flags.

    Returns:
        The state, with the reason when it is off.

    Raises:
        UndeclaredFeatureFlagError: If no flag has this name.

    """
    if name not in flags:
        message = f'No feature flag named {name!r} is declared'
        raise UndeclaredFeatureFlagError(message)
    flag = flags[name]
    unavailable = flag.availability()
    if unavailable is not None:
        return FlagState(on=False, reason=unavailable)
    if flag.parent is not None:
        parent_state = flag_state(name=flag.parent, flags=flags)
        if not parent_state.on:
            return FlagState(on=False, reason=f'{flag.parent} is off: {parent_state.reason}')
    asked = current_context().value(slot=FLAG_OPTIONS_SLOT).asked
    typed = asked.get(option_name(flag_name=name))
    if typed is True or (typed is None and flag.default):
        return FlagState(on=True)
    if typed is not None:
        return FlagState(on=False, reason=f'turned off by --{OFF_PREFIX}{name}')
    return FlagState(on=False, reason=f'off by default; --{name} turns it on')


def flag_state_lines(*, flags: FlagDeclarations = FEATURE_FLAGS) -> list[str]:
    """Return each flag's state in the current context, for the log of a run's start.

    Args:
        flags: The declared flags.

    Returns:
        ``NAME = on`` or ``NAME = off: REASON``, sorted by name.

    """
    lines: list[str] = []
    for name in sorted(flags):
        state = flag_state(name=name, flags=flags)
        lines.append(f'{name} = {"on" if state.on else f"off: {state.reason}"}')
    return lines
