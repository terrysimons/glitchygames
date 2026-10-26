"""Tests for bitmappy state management: configuration, setup, AI worker logic."""

import logging

import pytest

from bitmappy.ai_worker import (
    _check_ollama_model_status,
    _create_ai_retry_decorator,
    _create_ollama_config,
    _get_provider_timeout_value,
    _initialize_ai_client,
    _log_capabilities_dump,
    _process_ai_request,
    _set_ollama_env_timeout,
    _setup_ai_worker_logging,
    select_relevant_training_examples,
)
from bitmappy.constants import AI_MODEL, AI_TIMEOUT, ai_training_state
from bitmappy.models import AIRequest, AIResponse
from bitmappy.sprite_inspection import load_ai_training_data


class TestSetupAIWorkerLogging:
    """Test _setup_ai_worker_logging function."""

    def test_returns_logger(self):
        """Test that function returns a Logger instance."""
        log = _setup_ai_worker_logging()
        assert isinstance(log, logging.Logger)
        assert log.name == 'game.ai'

    def test_logger_has_handlers(self):
        """Test that logger has at least one handler after setup."""
        log = _setup_ai_worker_logging()
        assert len(log.handlers) > 0

    def test_a_second_setup_adds_no_second_handler(self, mocker):
        """Setting up twice leaves one handler (the already-set-up branch, in any test order)."""
        mocker.patch.object(logging.getLogger('game.ai'), 'handlers', new=[])

        first_log = _setup_ai_worker_logging()
        second_log = _setup_ai_worker_logging()

        assert second_log is first_log
        assert len(second_log.handlers) == 1


class TestCheckOllamaModelStatus:
    """Test _check_ollama_model_status function."""

    def test_non_ollama_model_returns_downloaded(self):
        """Test that non-ollama models always report as downloaded."""
        log = logging.getLogger('test')
        # Since AI_MODEL is 'anthropic:claude-sonnet-4-5' (not ollama), should return downloaded
        if not AI_MODEL.startswith('ollama:'):
            result = _check_ollama_model_status(log)
            assert result['downloaded'] is True
            assert result['reason'] == 'not_ollama'


class TestCreateOllamaConfig:
    """Test _create_ollama_config function."""

    def test_non_ollama_model_returns_empty(self):
        """Test that non-ollama models return empty config."""
        log = logging.getLogger('test')
        if not AI_MODEL.startswith('ollama:'):
            result = _create_ollama_config(log)
            assert result == {}


class TestSetOllamaEnvTimeout:
    """Test _set_ollama_env_timeout function."""

    def test_non_ollama_model_no_env_set(self):
        """Test that non-ollama models don't set environment variables."""
        import os

        log = logging.getLogger('test')
        original_timeout = os.environ.get('OLLAMA_TIMEOUT')
        if not AI_MODEL.startswith('ollama:'):
            _set_ollama_env_timeout(log)
            # Should not have set the environment variable
            if original_timeout is None:
                assert os.environ.get('OLLAMA_TIMEOUT') is None
            else:
                assert os.environ.get('OLLAMA_TIMEOUT') == original_timeout


class TestGetProviderTimeoutValue:
    """Test _get_provider_timeout_value function."""

    def test_non_ollama_returns_default_timeout(self):
        """Test that non-ollama models return default timeout."""
        log = logging.getLogger('test')
        if not AI_MODEL.startswith('ollama:'):
            result = _get_provider_timeout_value(log)
            assert result == AI_TIMEOUT


class TestClientProviderTimeouts:
    """The real aisuite Client _initialize_ai_client builds carries each provider's timeout.

    aisuite creates its providers lazily from these configurations on the first request.
    """

    def test_non_ollama_model_configures_no_ollama_provider(self, mocker):
        """A hosted model sets up no ollama provider."""
        import aisuite

        mocker.patch('bitmappy.ai_worker.AI_MODEL', 'anthropic:claude-sonnet-4-5')
        client = _initialize_ai_client(logging.getLogger('test'))

        assert isinstance(client, aisuite.Client)
        assert 'ollama' not in client.provider_configs

    def test_anthropic_provider_gets_the_ai_timeout(self, mocker):
        """The Anthropic provider is configured with AI_TIMEOUT."""
        import aisuite

        mocker.patch('bitmappy.ai_worker.AI_MODEL', 'anthropic:claude-sonnet-4-5')
        client = _initialize_ai_client(logging.getLogger('test'))

        assert isinstance(client, aisuite.Client)
        assert client.provider_configs['anthropic'] == {'timeout': AI_TIMEOUT}


class TestInitializeAIClient:
    """Test _initialize_ai_client function."""

    def test_returns_none_when_aisuite_unavailable(self, mocker):
        """Test returns None when aisuite is not available."""
        log = logging.getLogger('test')
        mocker.patch('bitmappy.ai_worker.ai', None)
        result = _initialize_ai_client(log)
        assert result is None


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
