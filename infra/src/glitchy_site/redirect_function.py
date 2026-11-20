"""The viewer-request CloudFront Function both distributions run, as CDK function code.

The JavaScript is ``functions/redirect_to_play.js`` (its comments say what it does; node tests
in ``infra/tests/functions/``). Each distribution builds its own ``cloudfront.Function`` from
this code: a function associated with another distribution can't be used on a flat-rate plan.
"""

from __future__ import annotations

from pathlib import Path

from aws_cdk import aws_cloudfront as cloudfront

REDIRECT_FUNCTION_PATH = Path(__file__).resolve().parent / 'functions' / 'redirect_to_play.js'


def redirect_function_code() -> cloudfront.FunctionCode:
    """Return the redirect function's code, read from its file.

    Returns:
        The code, for a ``cloudfront.Function``'s ``code``.

    """
    return cloudfront.FunctionCode.from_file(file_path=str(REDIRECT_FUNCTION_PATH))
