"""Tests for the sprite API request models' output_format validation.

Module under test: glitchygames/api/models/sprite_models.py.
"""

import pydantic
import pytest

from glitchygames.api.models.sprite_models import (
    SpriteGenerationRequest,
    SpriteRefinementRequest,
)

CURRENT_TOML = '[sprite]\nname = "heart"\npixels = """\n#\n"""\n'


def _make_request(*, request_class, output_format):
    """Build a request of request_class with the given output_format and minimal other fields.

    Returns:
        BaseModel: The validated request.

    """
    fields = {'prompt': 'a red heart', 'output_format': output_format}
    if request_class is SpriteRefinementRequest:
        fields['current_toml'] = CURRENT_TOML
    return request_class(**fields)


@pytest.mark.parametrize('request_class', [SpriteGenerationRequest, SpriteRefinementRequest])
class TestOutputFormatValidation:
    """Both request models accept 'toml' and/or 'png', and refuse an empty or unknown format."""

    @pytest.mark.parametrize('output_format', [['toml'], ['png'], ['toml', 'png']])
    def test_known_formats_are_accepted(self, request_class, output_format):
        """Any non-empty combination of toml and png is kept as given."""
        request = _make_request(request_class=request_class, output_format=output_format)

        assert request.output_format == output_format

    def test_default_is_both_formats(self, request_class):
        """Without an output_format the request asks for both TOML and PNG."""
        fields = {'prompt': 'a red heart'}
        if request_class is SpriteRefinementRequest:
            fields['current_toml'] = CURRENT_TOML

        assert request_class(**fields).output_format == ['toml', 'png']

    def test_empty_format_list_is_refused(self, request_class):
        """An empty list asks for nothing, so validation fails with the validator's message."""
        with pytest.raises(pydantic.ValidationError, match='must contain at least one format'):
            _make_request(request_class=request_class, output_format=[])

    def test_unknown_format_is_refused(self, request_class):
        """A format other than toml or png fails validation (the Literal type refuses it)."""
        with pytest.raises(pydantic.ValidationError, match="'toml' or 'png'"):
            _make_request(request_class=request_class, output_format=['gif'])
