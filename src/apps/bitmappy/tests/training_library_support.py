"""Install a training library for one test (bitmappy.training_library).

The installed library is shared, read-only package data that only Bitmappy's ``main()`` loads, so a
test that needs examples installs its own for the test: the conftest's autouse
``fresh_ai_training_state`` empties it again before the next test.
"""

from typing import TYPE_CHECKING, Any, Literal

from bitmappy import training_library
from bitmappy.training_library import TrainingLibrary

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def use_training_library(
    mocker: MockerFixture,
    *,
    examples: list[dict[str, Any]],
    training_format: Literal['toml'] | None = 'toml',
) -> TrainingLibrary:
    """Install a library of ``examples`` for this test.

    Returns:
        The installed library.

    """
    library = TrainingLibrary.of(examples=examples, training_format=training_format)
    mocker.patch.object(training_library._INSTALLED, 'library', library)  # pyright: ignore[reportPrivateUsage]
    return library
