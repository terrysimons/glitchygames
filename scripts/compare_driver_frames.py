r"""Compare the frames tests presented on different SDL video drivers (or in repeated runs).

The runs are recorded by the frame fingerprints plugin (glitchygames/testing/frame_fingerprints.py,
loaded with ``-p glitchygames.testing.frame_fingerprints --frame-fingerprints DIRECTORY``); each
run is named ``LABEL=DIRECTORY``, the label being its driver. Every local pytest run uses it to
compare the dummy driver with the native one (tests/driver_comparison.py); ``nox -s
compare-drivers`` compares every configuration with every other (scripts/driver_frame_matrix.py,
built on the same comparisons). The comparisons are the engine's test support
(glitchygames/testing/frame_comparison.py: the suite's own driver comparison, a test plugin,
imports no ``scripts.*``); this is their command line.

Two commands:

  compare   Reads two or more runs. Runs that share a label are repeats on the same driver: a
            test whose frames differ between them is nondeterministic (listed per label, and
            never counted as a driver difference). The first run of each other label is then
            compared with the first run of the first label (the baseline): every test whose
            frame sequence differs (first differing frame, both frame counts, both outcomes),
            and the tests recorded in one of the two runs only. ``--image-request FILE`` writes
            the frames to save as PNG files in a re-run of the differing tests (a
            ``FrameImageRequest``: each test's first differing frame and both final frames).
  images    Reads a re-run of those tests on two drivers (made with ``--frame-images-request``)
            and, for each requested test whose frames still differ, puts both drivers' PNG files
            of each differing frame and a difference image (the baseline frame dimmed to grey,
            differing pixels magenta) in ``--output``, with the count of differing pixels.

Both print a plain-text report and exit ``ExitCode.SUCCESS``: they report, they do not judge.
A missing run directory exits ``MISSING_INPUT``, an unreadable record or request
``UNUSABLE_INPUT``, an output that cannot be written ``CANNOT_WRITE_OUTPUT``.

Usage:
    uv run python scripts/compare_driver_frames.py compare dummy=RUN1 dummy=RUN2 cocoa=RUN3 \\
        --image-request request.json
    uv run python scripts/compare_driver_frames.py images dummy=RERUN1 cocoa=RERUN2 \\
        --request request.json --output differences/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pydantic

from glitchygames.exit_codes import ExitCode
from glitchygames.testing.frame_comparison import (
    LabelledRun,
    compare_labelled_runs,
    comparison_report,
    image_request_for,
    images_report,
)
from glitchygames.testing.frame_fingerprints import FrameImageRequest

if TYPE_CHECKING:
    from collections.abc import Sequence

LABEL_SEPARATOR = '='


def parse_labelled_run(text: str) -> LabelledRun:
    """Parse a ``LABEL=DIRECTORY`` argument.

    Args:
        text: The argument.

    Returns:
        The labelled run.

    Raises:
        argparse.ArgumentTypeError: If the text has no label or no directory.

    """
    label, separator, directory = text.partition(LABEL_SEPARATOR)
    if not separator or not label or not directory:
        message = f'{text!r}: expected LABEL=DIRECTORY (for example dummy=test-results/run-1)'
        raise argparse.ArgumentTypeError(message)
    return LabelledRun(label=label, directory=Path(directory))


def argument_parser() -> argparse.ArgumentParser:
    """Build the command line parser.

    Returns:
        The parser, with the compare and images commands.

    """
    parser = argparse.ArgumentParser(
        description='Compare the frames tests presented on different SDL video drivers'
    )
    commands = parser.add_subparsers(dest='command', required=True)
    compare = commands.add_parser('compare', help='compare runs; list differing tests')
    compare.add_argument(
        'runs',
        nargs='+',
        type=parse_labelled_run,
        metavar='LABEL=DIRECTORY',
        help='fingerprints directories; the first label is the baseline driver',
    )
    compare.add_argument(
        '--image-request',
        type=Path,
        default=None,
        help='write the frames to save in a re-run of the differing tests to this file',
    )
    images = commands.add_parser('images', help="compare a re-run's saved frames")
    images.add_argument(
        'runs',
        nargs=2,
        type=parse_labelled_run,
        metavar='LABEL=DIRECTORY',
        help='the baseline and the other driver re-runs',
    )
    images.add_argument('--request', type=Path, required=True, help='the image request file')
    images.add_argument('--output', type=Path, required=True, help='the report folder')
    return parser


def run(*, arguments: Sequence[str]) -> ExitCode:
    """Run a command and print its report.

    Args:
        arguments: The command line arguments (without the program name).

    Returns:
        The exit code.

    """
    options = argument_parser().parse_args(arguments)
    runs: list[LabelledRun] = options.runs
    try:
        if options.command == 'compare':
            report = run_compare(runs=runs, image_request_path=options.image_request)
        else:
            report = run_images(runs=runs, request_path=options.request, output=options.output)
    except FileNotFoundError as error:
        sys.stderr.write(f'{error}\n')
        return ExitCode.MISSING_INPUT
    except pydantic.ValidationError as error:
        sys.stderr.write(f'unusable record or request: {error}\n')
        return ExitCode.UNUSABLE_INPUT
    except OSError as error:
        sys.stderr.write(f'cannot write the output: {error}\n')
        return ExitCode.CANNOT_WRITE_OUTPUT
    sys.stdout.write(report)
    return ExitCode.SUCCESS


def run_compare(*, runs: Sequence[LabelledRun], image_request_path: Path | None) -> str:
    """Run the compare command.

    Args:
        runs: The labelled runs, the baseline driver's first.
        image_request_path: Where to write the image request, or None.

    Returns:
        The report.

    """
    repeats, drivers = compare_labelled_runs(runs=runs)
    if image_request_path is not None:
        image_request_path.parent.mkdir(parents=True, exist_ok=True)
        image_request_path.write_text(
            image_request_for(drivers=drivers).model_dump_json(indent=2), encoding='utf-8'
        )
    return comparison_report(repeats=repeats, drivers=drivers)


def run_images(*, runs: Sequence[LabelledRun], request_path: Path, output: Path) -> str:
    """Run the images command.

    Args:
        runs: The baseline driver's re-run and the other driver's.
        request_path: The image request the re-runs were made with.
        output: The report folder.

    Returns:
        The report.

    """
    request = FrameImageRequest.model_validate_json(request_path.read_text(encoding='utf-8'))
    baseline, candidate = runs
    return images_report(request=request, baseline=baseline, candidate=candidate, output=output)


def main() -> None:
    """Command line: see the module docstring."""
    sys.exit(run(arguments=sys.argv[1:]))


if __name__ == '__main__':
    main()
