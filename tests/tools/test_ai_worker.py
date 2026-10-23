"""Tests for glitchygames.bitmappy.ai_worker.

The AI client is always a local fake standing in for aisuite's client (the network boundary):
no test sends a real AI request or opens a connection.
"""

import inspect
import logging
import queue
from http import HTTPStatus
from types import SimpleNamespace

import pytest

from glitchygames.bitmappy import ai_worker
from glitchygames.bitmappy.constants import AI_MODEL_DOWNLOAD_TIMEOUT, AI_TIMEOUT
from glitchygames.bitmappy.models import AIRequest, AIResponse

LOG = logging.getLogger('test.ai_worker')
OLLAMA_MODEL = 'ollama:tiny-model'


@pytest.fixture(autouse=True)
def isolate_the_ai_worker_logger(mocker):
    """Keep the stderr handler a worker run adds to 'game.ai' out of later tests.

    run_ai_worker is a child process's entry point and adds its own stderr handler to the
    'game.ai' logger (_setup_ai_worker_logging). Run in the test process, that handler would
    outlive the test and print every later 'game.ai' record past pytest's log capture.
    """
    worker_logger = logging.getLogger('game.ai')
    mocker.patch.object(worker_logger, 'handlers', new=[])


def _response_with_content(content: str | None) -> SimpleNamespace:
    """Build a chat completion response with one choice holding ``content``.

    Returns:
        An object shaped like an aisuite chat completion response.

    """
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class FakeCompletions:
    """The ``chat.completions`` part of an AI client, recording each create() call."""

    def __init__(self, *, response: object = None, error: BaseException | None = None) -> None:
        """Answer every create() with ``response``, or raise ``error``."""
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def create(self, *, model: str, messages: list, max_tokens: int, timeout: float = 0) -> object:
        """Record the call and answer it.

        Returns:
            The configured response.

        """
        self.calls.append({
            'model': model,
            'messages': messages,
            'max_tokens': max_tokens,
            'timeout': timeout,
        })
        if self.error is not None:
            raise self.error
        return self.response


class FakeCompletionsWithoutTimeout(FakeCompletions):
    """Completions whose create() accepts no timeout parameter."""

    def create(self, *, model: str, messages: list, max_tokens: int) -> object:  # type: ignore[override]
        """Record the call and answer it.

        Returns:
            The configured response.

        """
        self.calls.append({'model': model, 'messages': messages, 'max_tokens': max_tokens})
        return self.response


def _client_with(completions: object) -> SimpleNamespace:
    """Build a fake AI client around ``completions``.

    Returns:
        An object with ``chat.completions``.

    """
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def _request(request_id: str = 'request-1') -> AIRequest:
    """Build an AI request with one user message.

    Returns:
        The request.

    """
    messages = [{'role': 'user', 'content': 'a red ball'}]
    return AIRequest(prompt=str(messages), request_id=request_id, messages=messages)


class TestConfigureOllamaProvider:
    """Test _configure_ollama_provider."""

    def test_only_ollama_providers_get_the_download_timeout(self, mocker):
        """Ollama providers and their HTTP clients get the long timeout; others are untouched."""
        mocker.patch.object(ai_worker, 'AI_MODEL', OLLAMA_MODEL)
        ollama_client = SimpleNamespace(
            timeout=1,
            request_timeout=1,
            read_timeout=1,
            connect_timeout=1,
        )
        ollama_provider = SimpleNamespace(timeout=1, client=ollama_client)
        other_provider = SimpleNamespace(timeout=1, client=SimpleNamespace(timeout=1))
        client = SimpleNamespace(_providers={'Ollama': ollama_provider, 'openai': other_provider})

        ai_worker._configure_ollama_provider(LOG, client)

        assert ollama_provider.timeout == AI_MODEL_DOWNLOAD_TIMEOUT
        assert vars(ollama_client) == dict.fromkeys(
            ['timeout', 'request_timeout', 'read_timeout', 'connect_timeout'],
            AI_MODEL_DOWNLOAD_TIMEOUT,
        )
        assert other_provider.timeout == 1
        assert other_provider.client.timeout == 1

    def test_providers_without_timeouts_are_left_without_them(self, mocker):
        """A provider or client that has no timeout attributes does not gain any."""
        mocker.patch.object(ai_worker, 'AI_MODEL', OLLAMA_MODEL)
        bare_client = SimpleNamespace()
        provider_with_bare_client = SimpleNamespace(client=bare_client)
        provider_without_client = SimpleNamespace()
        client = SimpleNamespace(
            _providers={'ollama': provider_with_bare_client, 'ollama2': provider_without_client},
        )

        ai_worker._configure_ollama_provider(LOG, client)

        assert vars(provider_with_bare_client) == {'client': bare_client}
        assert vars(bare_client) == {}
        assert vars(provider_without_client) == {}

    def test_non_ollama_model_changes_nothing(self, mocker):
        """With a hosted model, ollama providers are not reconfigured."""
        mocker.patch.object(ai_worker, 'AI_MODEL', 'anthropic:model')
        provider = SimpleNamespace(timeout=1)

        ai_worker._configure_ollama_provider(LOG, SimpleNamespace(_providers={'ollama': provider}))

        assert provider.timeout == 1


class TestConfigureProviderClientTimeout:
    """Test _configure_provider_client_timeout."""

    def test_inner_http_client_gets_the_timeout(self, mocker):
        """A client without its own timeout passes it to its inner _client."""
        mocker.patch.object(ai_worker, 'AI_MODEL', 'anthropic:model')
        inner_client = SimpleNamespace(timeout=5)
        provider = SimpleNamespace(client=SimpleNamespace(_client=inner_client))

        ai_worker._configure_provider_client_timeout(LOG, 'anthropic', provider, 42)

        assert inner_client.timeout == 42

    def test_client_without_any_timeout_is_unchanged(self, mocker):
        """A client with neither a timeout nor an inner client gains nothing."""
        mocker.patch.object(ai_worker, 'AI_MODEL', 'anthropic:model')
        provider = SimpleNamespace(client=SimpleNamespace())

        ai_worker._configure_provider_client_timeout(LOG, 'anthropic', provider, 42)

        assert vars(provider.client) == {}

    def test_ollama_sets_request_and_read_timeouts_present_on_the_client(self, mocker):
        """For ollama, request_timeout and read_timeout are set where the client has them."""
        mocker.patch.object(ai_worker, 'AI_MODEL', OLLAMA_MODEL)
        provider_client = SimpleNamespace(timeout=1, read_timeout=1)
        provider = SimpleNamespace(client=provider_client)

        ai_worker._configure_provider_client_timeout(LOG, 'ollama', provider, 42)

        assert vars(provider_client) == {'timeout': 42, 'read_timeout': AI_TIMEOUT}


class TestQueryModelCapabilities:
    """Test _query_model_capabilities."""

    def test_two_numbers_give_context_size_and_output_limit(self, mocker):
        """A 'context,output' answer is parsed into both limits."""
        completions = FakeCompletions(response=_response_with_content('200000,64000'))

        capabilities = ai_worker._query_model_capabilities(LOG, _client_with(completions))

        assert capabilities == {
            'max_tokens': 64000,
            'context_size': 200000,
            'output_limit': 64000,
        }
        assert completions.calls[0]['max_tokens'] == 256

    def test_slow_answer_is_reported_as_a_likely_download(self, mocker, caplog):
        """A query slower than the download threshold logs that the model was downloaded."""
        mocker.patch.object(ai_worker, 'measured_seconds', side_effect=[0.0, 120.0])
        completions = FakeCompletions(response=_response_with_content('4096'))

        with caplog.at_level(logging.INFO, logger=LOG.name):
            capabilities = ai_worker._query_model_capabilities(LOG, _client_with(completions))

        assert capabilities == {'max_tokens': 4096}
        assert 'Model was likely downloaded during this request' in caplog.messages

    def test_response_without_choices_has_unknown_max_tokens(self):
        """An empty answer leaves max_tokens unknown."""
        completions = FakeCompletions(response=SimpleNamespace(choices=[]))

        assert ai_worker._query_model_capabilities(LOG, _client_with(completions)) == {
            'max_tokens': None,
        }

    def test_message_without_content_has_unknown_max_tokens(self):
        """A choice whose message has no content (aisuite's Message.content is None) is no answer.

        It used to reach _parse_capabilities_response, which raised AttributeError on None.
        """
        completions = FakeCompletions(response=_response_with_content(None))

        assert ai_worker._query_model_capabilities(LOG, _client_with(completions)) == {
            'max_tokens': None,
        }


class TestParseCapabilitiesResponse:
    """Test ai_worker._parse_capabilities_response's unparseable answers."""

    @pytest.mark.parametrize('content', ['65536,8192,1', 'lots,8192', '8192,', ''])
    def test_anything_but_one_or_two_numbers_cannot_be_parsed(self, content):
        """Three numbers, a word or an empty part give no max tokens and keep the answer."""
        assert ai_worker._parse_capabilities_response(LOG, content) == {
            'max_tokens': None,
            'raw_response': content,
        }


class TestGetModelCapabilities:
    """Test _get_model_capabilities."""

    def test_without_a_client_uses_default_capabilities(self, mocker):
        """When aisuite is unavailable the defaults are returned."""
        mocker.patch.object(
            ai_worker,
            '_check_ollama_model_status',
            return_value={'downloaded': False, 'reason': 'needs_download'},
        )
        mocker.patch.object(ai_worker, '_initialize_ai_client', return_value=None)

        assert ai_worker._get_model_capabilities(LOG) == {'max_tokens': 8192, 'num_ctx': 65536}

    def test_with_a_client_queries_the_model(self, mocker):
        """With a client, the model is asked for its limits."""
        mocker.patch.object(
            ai_worker,
            '_check_ollama_model_status',
            return_value={'downloaded': True, 'reason': 'not_ollama'},
        )
        completions = FakeCompletions(response=_response_with_content('1024'))
        mocker.patch.object(
            ai_worker,
            '_initialize_ai_client',
            return_value=_client_with(completions),
        )

        assert ai_worker._get_model_capabilities(LOG) == {'max_tokens': 1024}

    def test_connection_failure_gives_unknown_max_tokens(self, mocker):
        """A connection error while querying is logged and yields unknown limits."""
        mocker.patch.object(
            ai_worker,
            '_check_ollama_model_status',
            return_value={'downloaded': True, 'reason': 'not_ollama'},
        )
        completions = FakeCompletions(error=ConnectionError('refused'))
        mocker.patch.object(
            ai_worker,
            '_initialize_ai_client',
            return_value=_client_with(completions),
        )

        assert ai_worker._get_model_capabilities(LOG) == {'max_tokens': None}


class TestIsNonRetryableAiError:
    """Test _is_non_retryable_ai_error."""

    def test_value_error_is_not_retried(self):
        """Bad input fails the same way every time."""
        assert ai_worker._is_non_retryable_ai_error(ValueError('bad')) is True

    def test_error_without_an_integer_status_is_retried(self):
        """A status code that is not an integer says nothing, so the error is retried."""
        error = RuntimeError('odd')
        error.status_code = 'unknown'  # type: ignore[attr-defined]

        assert ai_worker._is_non_retryable_ai_error(error) is False

    @pytest.mark.parametrize(
        ('status_code', 'non_retryable'),
        [
            (HTTPStatus.BAD_REQUEST, True),
            (HTTPStatus.NOT_FOUND, True),
            (HTTPStatus.TOO_MANY_REQUESTS, False),
            (HTTPStatus.REQUEST_TIMEOUT, False),
            (HTTPStatus.INTERNAL_SERVER_ERROR, False),
        ],
    )
    def test_client_errors_stop_except_transient_ones(self, status_code, non_retryable):
        """4xx errors give up, except timeouts, conflicts and rate limits; 5xx retry."""
        error = RuntimeError('http')
        error.status_code = int(status_code)  # type: ignore[attr-defined]

        assert ai_worker._is_non_retryable_ai_error(error) is non_retryable


class TestMakeAiApiCall:
    """Test _make_ai_api_call."""

    def test_timeout_parameter_gets_the_normal_timeout(self, mocker):
        """A create() that takes a timeout is called with AI_TIMEOUT for hosted models."""
        mocker.patch.object(ai_worker, 'AI_MODEL', 'anthropic:model')
        expected_response = _response_with_content('[sprite]')
        completions = FakeCompletions(response=expected_response)

        response = ai_worker._make_ai_api_call(_request(), _client_with(completions), LOG)

        assert response is expected_response
        assert completions.calls == [
            {
                'model': 'anthropic:model',
                'messages': _request().messages,
                'max_tokens': ai_worker.AI_MAX_OUTPUT_TOKENS,
                'timeout': AI_TIMEOUT,
            },
        ]

    def test_the_api_call_arguments_are_logged_at_debug_level(self, mocker, caplog):
        """The request's arguments (the whole prompt) are diagnostics, not a critical event."""
        mocker.patch.object(ai_worker, 'AI_MODEL', 'anthropic:model')
        completions = FakeCompletions(response=_response_with_content('[sprite]'))

        with caplog.at_level(logging.DEBUG, logger=LOG.name):
            ai_worker._make_ai_api_call(_request(), _client_with(completions), LOG)

        argument_records = [
            record for record in caplog.records if record.getMessage().startswith('API call kwargs')
        ]
        assert [record.levelno for record in argument_records] == [logging.DEBUG]

    def test_ollama_gets_the_download_timeout(self, mocker):
        """Ollama models get the long timeout, since the first call may download the model."""
        mocker.patch.object(ai_worker, 'AI_MODEL', OLLAMA_MODEL)
        completions = FakeCompletions(response=_response_with_content('x'))

        ai_worker._make_ai_api_call(_request(), _client_with(completions), LOG)

        assert completions.calls[0]['timeout'] == AI_MODEL_DOWNLOAD_TIMEOUT

    def test_create_without_a_timeout_parameter_is_called_without_one(self):
        """A create() with no timeout parameter is called with only the basic arguments."""
        completions = FakeCompletionsWithoutTimeout(response=_response_with_content('x'))

        ai_worker._make_ai_api_call(_request(), _client_with(completions), LOG)

        assert set(completions.calls[0]) == {'model', 'messages', 'max_tokens'}
        assert 'timeout' not in inspect.signature(completions.create).parameters

    def test_failed_call_is_reraised(self):
        """An error from the API propagates to the retry logic."""
        completions = FakeCompletions(error=ConnectionError('down'))

        with pytest.raises(ConnectionError, match='down'):
            ai_worker._make_ai_api_call(_request(), _client_with(completions), LOG)

    def test_completions_without_create_fails(self):
        """A client with no create() cannot make the call."""
        with pytest.raises(AttributeError):
            ai_worker._make_ai_api_call(_request(), _client_with(SimpleNamespace()), LOG)


class RetryableError(Exception):
    """An error the retry decorator retries (a server error, by status code)."""

    status_code = HTTPStatus.INTERNAL_SERVER_ERROR


def _retrying(*, outcomes: list[object]) -> tuple[object, list[float], list[int]]:
    """Decorate a call that answers ``outcomes`` in turn (raising the exceptions among them).

    Returns:
        The decorated call, the waits it would sleep (recorded, not slept) and its call count.

    """
    waits: list[float] = []
    calls: list[int] = []

    def api_call() -> object:
        calls.append(len(calls) + 1)
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    decorated = ai_worker._create_ai_retry_decorator(LOG)(api_call)
    decorated.retry.sleep = waits.append  # type: ignore[attr-defined]
    return decorated, waits, calls


class TestCreateAiRetryDecorator:
    """Test _create_ai_retry_decorator: exponential retries of retryable AI errors."""

    def test_a_retryable_error_is_retried_with_exponential_waits(self):
        """Server errors are retried after AI_BASE_DELAY, then twice that, and so on."""
        decorated, waits, calls = _retrying(
            outcomes=[RetryableError('busy'), RetryableError('busy'), 'answer']
        )

        assert decorated() == 'answer'
        assert len(calls) == 3
        assert waits == [ai_worker.AI_BASE_DELAY, 2 * ai_worker.AI_BASE_DELAY]

    def test_it_gives_up_after_the_last_attempt_and_reraises(self, caplog):
        """After AI_MAX_RETRIES attempts the last error is raised and the give-up is logged."""
        decorated, waits, calls = _retrying(
            outcomes=[RetryableError(f'busy {index}') for index in range(ai_worker.AI_MAX_RETRIES)]
        )

        with caplog.at_level(logging.ERROR, logger=LOG.name), pytest.raises(RetryableError):
            decorated()

        assert len(calls) == ai_worker.AI_MAX_RETRIES
        assert len(waits) == ai_worker.AI_MAX_RETRIES - 1
        assert all(wait <= ai_worker.AI_MAX_DELAY for wait in waits)
        assert 'failed permanently' in caplog.text

    def test_a_non_retryable_error_is_not_retried(self):
        """A client error (bad request) is raised at once, with no wait."""
        decorated, waits, calls = _retrying(outcomes=[ValueError('bad request')])

        with pytest.raises(ValueError, match='bad request'):
            decorated()

        assert len(calls) == 1
        assert waits == []


class TestProcessAiRequest:
    """Test _process_ai_request."""

    def test_successful_call_returns_the_content(self):
        """The first choice's content is returned."""
        completions = FakeCompletions(response=_response_with_content('[sprite]\nname = "x"'))

        response = ai_worker._process_ai_request(_request(), _client_with(completions), LOG)

        assert response == AIResponse(content='[sprite]\nname = "x"')

    def test_api_error_becomes_an_error_response(self):
        """An error from the API is reported back as an error response, not raised."""
        completions = FakeCompletions(error=ValueError('bad request'))

        response = ai_worker._process_ai_request(_request(), _client_with(completions), LOG)

        assert response == AIResponse(content=None, error='ValueError: bad request')
        assert len(completions.calls) == 1


class TestExtractExampleSizeBranches:
    """Branches of _extract_example_size for animated examples."""

    def test_first_frame_without_pixels_has_no_size(self):
        """An animation whose first frame has no pixels gives no size."""
        example = {'animations': [{'frame': [{'frame_index': 0}]}]}

        assert ai_worker._extract_example_size(example) is None

    def test_single_line_frame_pixels_have_no_size(self):
        """Frame pixels without a newline are not a grid."""
        example = {'animations': [{'frame': [{'pixels': '####'}]}]}

        assert ai_worker._extract_example_size(example) is None

    def test_animation_without_frames_has_no_size(self):
        """An animation with an empty frame list gives no size."""
        assert ai_worker._extract_example_size({'animations': [{'frame': []}]}) is None


class TestRunAiWorker:
    """Test the worker loop, run in-process with thread queues."""

    def test_requests_are_answered_until_the_shutdown_message(self, mocker):
        """Each request gets a response tagged with its id; None stops the loop."""
        completions = FakeCompletions(response=_response_with_content('[sprite]'))
        mocker.patch.object(
            ai_worker,
            '_initialize_ai_client',
            return_value=_client_with(completions),
        )
        request_queue: queue.Queue = queue.Queue()
        response_queue: queue.Queue = queue.Queue()
        request_queue.put(_request('first'))
        request_queue.put(_request('second'))
        request_queue.put(None)

        ai_worker.run_ai_worker(request_queue, response_queue)  # type: ignore[arg-type]

        assert response_queue.get_nowait() == ('first', AIResponse(content='[sprite]'))
        assert response_queue.get_nowait() == ('second', AIResponse(content='[sprite]'))
        assert response_queue.empty()

    def test_request_error_is_answered_with_an_error_response(self, mocker):
        """An error while processing a request sends that request an error response."""
        mocker.patch.object(ai_worker, '_initialize_ai_client', return_value=None)
        mocker.patch.object(ai_worker, '_process_ai_request', side_effect=KeyError('missing'))
        request_queue: queue.Queue = queue.Queue()
        response_queue: queue.Queue = queue.Queue()
        request_queue.put(_request('broken'))
        request_queue.put(None)

        ai_worker.run_ai_worker(request_queue, response_queue)  # type: ignore[arg-type]

        assert response_queue.get_nowait() == (
            'broken',
            AIResponse(content=None, error="'missing'"),
        )
        assert response_queue.empty()

    def test_queue_error_before_any_request_sends_nothing(self, mocker):
        """A failed read with no request yet has no one to answer."""
        mocker.patch.object(ai_worker, '_initialize_ai_client', return_value=None)

        class FailingOnceQueue:
            """A request queue whose first get() fails, then asks for shutdown."""

            def __init__(self) -> None:
                self.reads = 0

            def get(self) -> None:
                self.reads += 1
                if self.reads == 1:
                    msg = 'queue broken'
                    raise OSError(msg)

        response_queue: queue.Queue = queue.Queue()

        ai_worker.run_ai_worker(FailingOnceQueue(), response_queue)  # type: ignore[arg-type]

        assert response_queue.empty()

    def test_queue_error_after_a_request_does_not_answer_it_again(self, mocker):
        """A failed read after an answered request sends that request nothing more.

        The request read before the failure used to be answered a second time, with the
        queue's error.
        """
        mocker.patch.object(ai_worker, '_initialize_ai_client', return_value=None)

        class FailingSecondReadQueue:
            """A request queue that gives one request, fails once, then asks for shutdown."""

            def __init__(self) -> None:
                self.reads = 0

            def get(self) -> AIRequest | None:
                self.reads += 1
                if self.reads == 1:
                    return _request('first')
                if self.reads == 2:
                    msg = 'queue broken'
                    raise OSError(msg)
                return None

        response_queue: queue.Queue = queue.Queue()

        ai_worker.run_ai_worker(FailingSecondReadQueue(), response_queue)  # type: ignore[arg-type]

        assert response_queue.get_nowait() == (
            'first',
            AIResponse(content='AI features not available'),
        )
        assert response_queue.empty()

    def test_client_initialization_failure_is_fatal(self, mocker):
        """An OSError while creating the client ends the worker with that error."""
        mocker.patch.object(ai_worker, '_initialize_ai_client', side_effect=OSError('no client'))

        with pytest.raises(OSError, match='no client'):
            ai_worker.run_ai_worker(queue.Queue(), queue.Queue())  # type: ignore[arg-type]
