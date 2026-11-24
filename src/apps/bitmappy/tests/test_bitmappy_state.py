"""Tests for bitmappy state management: configuration, setup, AI worker logic."""

import logging

import pytest
from src.apps.bitmappy.tests.training_library_support import use_training_library

from bitmappy.ai_worker import (
    _create_ai_retry_decorator,
    _initialize_ai_client,
    _log_capabilities_dump,
    _process_ai_request,
    _setup_ai_worker_logging,
    select_relevant_training_examples,
)
from bitmappy.constants import AI_TIMEOUT
from bitmappy.models import AIRequest, AIResponse
from bitmappy.sprite_inspection import load_ai_training_data
from bitmappy.training_library import ai_training_library


class TestSetupAIWorkerLogging:
    """Test _setup_ai_worker_logging function."""

    def test_returns_logger(self, mocker):
        """Test that function returns a Logger instance."""
        mocker.patch.object(logging.getLogger('game.ai'), 'handlers', new=[])

        log = _setup_ai_worker_logging()
        assert isinstance(log, logging.Logger)
        assert log.name == 'game.ai'

    def test_logger_has_handlers(self, mocker):
        """Test that logger has at least one handler after setup."""
        mocker.patch.object(logging.getLogger('game.ai'), 'handlers', new=[])

        log = _setup_ai_worker_logging()
        assert len(log.handlers) > 0

    def test_a_second_setup_adds_no_second_handler(self, mocker):
        """Setting up twice leaves one handler (the already-set-up branch, in any test order)."""
        mocker.patch.object(logging.getLogger('game.ai'), 'handlers', new=[])

        first_log = _setup_ai_worker_logging()
        second_log = _setup_ai_worker_logging()

        assert second_log is first_log
        assert len(second_log.handlers) == 1


class TestInitializeAIClient:
    """Test _initialize_ai_client function."""

    def test_returns_the_local_services_client_with_the_ai_timeout(self, mocker):
        """The client comes from create_chat_client, given AI_TIMEOUT."""
        client = mocker.Mock(name='LocalAIClient')
        create_chat_client = mocker.patch(
            'glitchygames.ai.local_service.create_chat_client',
            return_value=client,
        )

        result = _initialize_ai_client(logging.getLogger('test'))

        assert result is client
        create_chat_client.assert_called_once_with(timeout_seconds=AI_TIMEOUT)

    def test_returns_none_when_the_service_is_not_installed(self, mocker):
        """Test returns None when the local AI service is not installed."""
        from glitchygames.ai.local_service import LocalAIServiceNotInstalledError

        mocker.patch(
            'glitchygames.ai.local_service.create_chat_client',
            side_effect=LocalAIServiceNotInstalledError('not installed'),
        )

        assert _initialize_ai_client(logging.getLogger('test')) is None


class TestProcessAIRequest:
    """Test _process_ai_request function."""

    def test_returns_unavailable_when_client_is_none(self):
        """Test returns 'AI features not available' when client is None."""
        log = logging.getLogger('test')
        request = AIRequest(
            prompt='Create a sprite',
            request_id='req_001',
            messages=[{'role': 'user', 'content': 'Create a sprite'}],
        )
        result = _process_ai_request(request, client=None, log=log)
        assert isinstance(result, AIResponse)
        assert result.content == 'AI features not available'


class TestCreateAIRetryDecorator:
    """Test _create_ai_retry_decorator function."""

    def test_returns_callable_decorator(self):
        """Test that function returns a callable decorator."""
        log = logging.getLogger('test')
        decorator = _create_ai_retry_decorator(log)
        assert callable(decorator)

    @pytest.mark.filterwarnings('ignore::DeprecationWarning')
    def test_decorator_preserves_function(self):
        """Test that decorated function is still callable."""
        log = logging.getLogger('test')
        decorator = _create_ai_retry_decorator(log)

        @decorator
        def my_function():
            return 42

        assert callable(my_function)


class TestLogCapabilitiesDump:
    """Test _log_capabilities_dump function."""

    def test_logs_without_error(self):
        """Test that capabilities dump logs without raising errors."""
        log = logging.getLogger('test')
        _log_capabilities_dump(
            log,
            **{'Context Size': 65536, 'Max Output Tokens': 8192},
        )

    def test_logs_with_empty_fields(self):
        """Test logging with no extra fields."""
        log = logging.getLogger('test')
        _log_capabilities_dump(log)


class TestSelectRelevantTrainingExamples:
    """Test select_relevant_training_examples function."""

    def test_returns_all_when_under_limit(self, mocker):
        """Test returns all examples when under the max limit."""
        use_training_library(
            mocker,
            examples=[
                {'name': 'slime', 'sprite_type': 'static', 'has_alpha': False},
                {'name': 'mushroom', 'sprite_type': 'animated', 'has_alpha': True},
            ],
        )
        result = select_relevant_training_examples('create a slime', max_examples=100)
        assert len(result) == 2

    def test_returns_scored_subset_when_over_limit(self, mocker):
        """Test returns scored subset when over the max limit."""
        use_training_library(
            mocker,
            examples=[
                {'name': f'sprite_{i}', 'sprite_type': 'static', 'has_alpha': False}
                for i in range(10)
            ],
        )
        result = select_relevant_training_examples('create a sprite', max_examples=3)
        assert len(result) == 3

    def test_empty_training_data(self, mocker):
        """Test with empty training data."""
        use_training_library(mocker, examples=[])
        result = select_relevant_training_examples('create something')
        assert result == []


class TestAITrainingLibraryState:
    """The installed training library, reset per test by the conftest."""

    def test_every_test_starts_with_no_library_installed(self, mocker, tmp_path):
        """Readers see the empty library and a load installs, for every test.

        Then it leaves a library installed on purpose: any later test on this worker that saw it
        would fail this same check (the conftest's ``fresh_ai_training_library`` empties it).
        """
        assert ai_training_library().examples == ()
        assert ai_training_library().training_format is None
        (tmp_path / 'left_behind.toml').write_text(
            '[sprite]\nname = "left_behind"\npixels = """\n#\n"""\n\n'
            '[colors."#"]\nred = 0\ngreen = 0\nblue = 0\n',
            encoding='utf-8',
        )
        mocker.patch('bitmappy.sprite_inspection.SPRITE_CONFIG_DIR', tmp_path)
        mocker.patch('bitmappy.sprite_inspection.SpriteFactory.load_sprite', side_effect=ValueError)
        assert [example['name'] for example in load_ai_training_data().examples] == ['left_behind']
