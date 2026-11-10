"""Tests for bitmappy state management: configuration, setup, AI worker logic."""

import logging

import pytest

from bitmappy.ai_worker import (
    _create_ai_retry_decorator,
    _initialize_ai_client,
    _log_capabilities_dump,
    _process_ai_request,
    _setup_ai_worker_logging,
    select_relevant_training_examples,
)
from bitmappy.constants import AI_TIMEOUT, ai_training_state
from bitmappy.models import AIRequest, AIResponse
from bitmappy.sprite_inspection import load_ai_training_data


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

    def test_returns_all_when_under_limit(self):
        """Test returns all examples when under the max limit."""
        original_data = ai_training_state['data']
        try:
            ai_training_state['data'] = [
                {'name': 'slime', 'sprite_type': 'static', 'has_alpha': False},
                {'name': 'mushroom', 'sprite_type': 'animated', 'has_alpha': True},
            ]
            result = select_relevant_training_examples('create a slime', max_examples=100)
            assert len(result) == 2
        finally:
            ai_training_state['data'] = original_data

    def test_returns_scored_subset_when_over_limit(self):
        """Test returns scored subset when over the max limit."""
        original_data = ai_training_state['data']
        try:
            ai_training_state['data'] = [
                {'name': f'sprite_{i}', 'sprite_type': 'static', 'has_alpha': False}
                for i in range(10)
            ]
            result = select_relevant_training_examples('create a sprite', max_examples=3)
            assert len(result) == 3
        finally:
            ai_training_state['data'] = original_data

    def test_empty_training_data(self):
        """Test with empty training data."""
        original_data = ai_training_state['data']
        try:
            ai_training_state['data'] = []
            result = select_relevant_training_examples('create something')
            assert result == []
        finally:
            ai_training_state['data'] = original_data


class TestAITrainingState:
    """Test the ai_training_state global state management."""

    def test_initial_state_has_data_list(self):
        """Test that initial state has a data list."""
        assert isinstance(ai_training_state['data'], list)

    def test_initial_format_can_be_set(self):
        """Test that format field exists in initial state."""
        assert 'format' in ai_training_state


class TestLoadAITrainingData:
    """Test load_ai_training_data function."""

    def test_raises_type_error_if_data_not_list(self):
        """Test that TypeError is raised if data is not a list."""
        original_data = ai_training_state['data']
        try:
            ai_training_state['data'] = 'not_a_list'
            with pytest.raises(TypeError, match='must be a list'):
                load_ai_training_data()
        finally:
            ai_training_state['data'] = original_data
