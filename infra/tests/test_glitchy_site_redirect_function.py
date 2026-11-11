"""The CloudFront Function's code is the tested JavaScript file, loaded unchanged."""

from __future__ import annotations

from glitchy_site.redirect_function import REDIRECT_FUNCTION_PATH, redirect_function_code


def test_the_function_code_is_the_redirect_file():
    """Both distributions' functions get exactly the file node's tests run."""
    assert REDIRECT_FUNCTION_PATH.name == 'redirect_to_play.js'
    assert redirect_function_code().render() == REDIRECT_FUNCTION_PATH.read_text(encoding='utf-8')
