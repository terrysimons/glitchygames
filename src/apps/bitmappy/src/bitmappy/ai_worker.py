"""AI worker infrastructure for Bitmappy sprite generation.

Contains the AI worker process function and all supporting functions
for initializing the AI client, managing timeouts, processing requests,
and selecting training examples.
"""

from __future__ import annotations

import logging
import operator
import signal
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from glitchygames import clock
from glitchygames.ai import get_sprite_size_hint
from glitchygames.ai.sprite_generator import PIXEL_ROWS_ERROR_PREFIX
from glitchygames.sprites.pixel_utils import normalize_pixel_rows

from .constants import (
    AI_BASE_DELAY,
    AI_CAPABILITY_RESPONSE_FIELD_COUNT,
    AI_MAX_CONTEXT_SIZE,
    AI_MAX_DELAY,
    AI_MAX_INPUT_TOKENS,
    AI_MAX_OUTPUT_TOKENS,
    AI_MAX_RETRIES,
    AI_MAX_TRAINING_EXAMPLES,
    AI_MODEL,
    AI_TIMEOUT,
    RETRYABLE_CLIENT_ERROR_STATUS_CODES,
    SPRITE_ASPECT_RATIO_TOLERANCE,
    ai_training_state,
)
from .models import AIRequest, AIResponse

if TYPE_CHECKING:
    import multiprocessing
    from collections.abc import Callable

    import tenacity

    from glitchygames.ai.local_service import ChatClient, ChatResponse


def _setup_ai_worker_logging() -> logging.Logger:
    """Set up logging for AI worker process.

    Returns:
        logging.Logger: The result.

    """
    log = logging.getLogger('game.ai')

    if not log.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        log.addHandler(handler)

    log.info('AI worker process initializing...')
    log.debug('AI_MODEL: %s', AI_MODEL)
    log.debug('AI_TIMEOUT: %s', AI_TIMEOUT)
    return log


def _initialize_ai_client(log: logging.Logger) -> ChatClient | None:
    """Initialize the client for the local AI service.

    Returns:
        The AI client, or None when the service isn't installed here.

    """
    # Imported here, not with the module: a browser build, which has no AI, never needs it
    from glitchygames.ai.local_service import (
        LocalAIServiceNotInstalledError,
        create_chat_client,
    )

    log.info('Initializing AI client...')
    try:
        client = create_chat_client(timeout_seconds=AI_TIMEOUT)
    except LocalAIServiceNotInstalledError:
        log.exception('AI features disabled')
        return None
    log.info('AI client initialized')
    return client


def _log_capabilities_dump(log: logging.Logger, **fields: object) -> None:
    """Log a formatted model capabilities dump block.

    Args:
        log: Logger instance.
        **fields: Key-value pairs to include in the dump.

    """
    log.debug('\n%s', '=' * 60)
    log.debug('MODEL CAPABILITIES DUMP')
    log.debug('=' * 60)
    log.debug('Model: %s', AI_MODEL)
    for key, value in fields.items():
        log.debug('%s: %s', key, value)
    log.debug('%s\n', '=' * 60)


def _parse_capabilities_response(log: logging.Logger, content: str) -> dict[str, Any]:
    """Parse model capabilities from response content.

    Args:
        log: Logger instance.
        content: The model's response content string.

    Returns:
        Dictionary of capabilities.

    """
    # Either "context_size,output_limit" or a single max token count; anything else (a part
    # that is not a number, more parts) cannot be parsed
    try:
        numbers = [int(part.strip()) for part in content.strip().split(',')]
    except ValueError:
        numbers = []

    if len(numbers) == AI_CAPABILITY_RESPONSE_FIELD_COUNT:
        context_size, output_limit = numbers
        log.info('Detected context size: %s, output limit: %s', context_size, output_limit)
        _log_capabilities_dump(
            log,
            **{
                'Context Size': context_size,
                'Max Output Tokens': output_limit,
                'Model Response': content,
            },
        )
        return {
            'max_tokens': output_limit,
            'context_size': context_size,
            'output_limit': output_limit,
        }

    if len(numbers) == 1:
        [max_tokens] = numbers
        log.info('Detected max tokens: %s', max_tokens)
        _log_capabilities_dump(log, **{'Max Output Tokens': max_tokens, 'Model Response': content})
        return {'max_tokens': max_tokens}

    log.warning('Could not parse max tokens from response: %s', content)
    _log_capabilities_dump(
        log,
        **{'Max Output Tokens': 'Could not parse', 'Model Response': content},
    )
    return {'max_tokens': None, 'raw_response': content}


def _query_model_capabilities(log: logging.Logger, client: ChatClient) -> dict[str, Any]:
    """Send a test request to query model capabilities.

    Args:
        log: Logger instance.
        client: The AI client.

    Returns:
        Dictionary of capabilities.

    """
    test_messages = [
        {
            'role': 'user',
            'content': (
                'Please tell me your capabilities:\n'
                '1. What is your maximum context window size (input tokens)?\n'
                '2. What is your maximum output token limit for a single response?\n'
                'Please respond with just two numbers separated by a comma, like: '
                'context_size,output_limit'
            ),
        },
    ]

    log.info('Querying model capabilities...')

    start_time = clock.measured_seconds()
    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=test_messages,
        max_tokens=256,
    )
    duration = clock.measured_seconds() - start_time

    log.info('Model capability query completed in %.2f seconds', duration)

    if hasattr(response, 'choices') and response.choices:
        content = response.choices[0].message.content
        log.info('Model response about capabilities: %s', content)
        # A message with no content (None) is no answer, like a response with no choices
        if content is not None:
            return _parse_capabilities_response(log, content)

    _log_capabilities_dump(log, **{'Max Tokens': 'Unknown (no response)'})
    return {'max_tokens': None}


def _get_model_capabilities(log: logging.Logger) -> dict[str, Any]:  # type: ignore[reportUnusedFunction]
    """Query the model's capabilities including max tokens.

    Returns:
        dict: The model capabilities.

    """
    try:
        client = _initialize_ai_client(log)

        if client is None:
            log.warning('AI client not available, using default capabilities')
            return {'max_tokens': 8192, 'num_ctx': 65536}

        return _query_model_capabilities(log, client)

    except (ValueError, ConnectionError, TimeoutError) as e:
        log.exception('Failed to query model capabilities')
        _log_capabilities_dump(log, **{'Max Tokens': 'Unknown (query failed)', 'Error': str(e)})
        return {'max_tokens': None}


def _is_non_retryable_ai_error(error: BaseException) -> bool:
    """Decide whether an AI request error should stop the retry loop immediately.

    HTTP 4xx errors from the service (bad request, auth, not found) will fail the same way
    every time, so retrying them only delays the error message.
    Request timeouts (408), conflicts (409), and rate limits (429) are transient and
    are still retried.

    Args:
        error: The exception raised by the API call.

    Returns:
        bool: True if retrying cannot help.

    """
    if isinstance(error, (ValueError, KeyboardInterrupt, SystemExit)):
        return True

    status_code = getattr(error, 'status_code', None)
    if not isinstance(status_code, int):
        return False

    return (
        HTTPStatus.BAD_REQUEST <= status_code < HTTPStatus.INTERNAL_SERVER_ERROR
        and status_code not in RETRYABLE_CLIENT_ERROR_STATUS_CODES
    )


def _create_ai_retry_decorator(
    log: logging.Logger,
    *,
    sleep: Callable[[float], None] | None = None,
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Create a retry decorator for AI requests with exponential backoff.

    A retryable error (a server error, a timeout, rate limiting) is retried up to
    AI_MAX_RETRIES attempts in all, waiting AI_BASE_DELAY, then twice that, and so on, at most
    AI_MAX_DELAY; a non-retryable one (``_is_non_retryable_ai_error``) is raised at once. The
    last error is raised when the attempts run out. (tenacity replaced backoff, whose decorator
    calls ``asyncio.iscoroutinefunction``, deprecated in Python 3.14; its ``base=AI_BASE_DELAY``
    of 1.0 was the exponent's base, so every wait had been about 1 second.)

    Args:
        log: The worker's logger, for each retry and the final give-up.
        sleep: The wait between attempts (tenacity's ``sleep``; tests pass one that does not
            wait). None is the engine's raw sleep (glitchygames/clock.py), looked up at each
            wait, so tenacity never sleeps through its own ``time.sleep`` and a patch on
            ``glitchygames.clock.raw_sleep`` reaches it.

    Returns:
        The decorator.

    """
    # Imported here, when an AI request is made, not with the module: Bitmappy then imports
    # where tenacity is not installed (a browser build), with only AI requests unavailable
    import tenacity

    def wait_between_attempts(seconds: float) -> None:
        (clock.raw_sleep if sleep is None else sleep)(seconds)

    def should_retry(error: BaseException) -> bool:
        if _is_non_retryable_ai_error(error):
            log.error('AI request failed permanently (not retryable): %s', error)
            return False
        return True

    def log_retry(retry_state: tenacity.RetryCallState) -> None:
        wait = retry_state.next_action.sleep if retry_state.next_action else 0.0
        error = retry_state.outcome.exception() if retry_state.outcome else None
        log.warning(
            'AI request failed (attempt %s), retrying in %.1fs: %s',
            retry_state.attempt_number,
            wait,
            error,
        )

    def give_up(retry_state: tenacity.RetryCallState) -> object:
        error = retry_state.outcome.exception() if retry_state.outcome else None
        log.error(
            'AI request failed permanently after %s attempts: %s', retry_state.attempt_number, error
        )
        # Raise the last attempt's own error, as before (not tenacity's RetryError)
        assert retry_state.outcome is not None
        return retry_state.outcome.result()

    return tenacity.retry(
        stop=tenacity.stop_after_attempt(AI_MAX_RETRIES),
        wait=tenacity.wait_exponential(multiplier=AI_BASE_DELAY, max=AI_MAX_DELAY),
        retry=tenacity.retry_if_exception(should_retry),
        before_sleep=log_retry,
        retry_error_callback=give_up,
        sleep=wait_between_attempts,
    )


def _make_ai_api_call(
    request: AIRequest,
    client: ChatClient,
    log: logging.Logger,
) -> ChatResponse:
    """Make the actual API call to the AI service.

    Returns:
        The model's chat completion.

    """
    log.info('Making API call to AI service...')
    log.debug('Using model: %s', AI_MODEL)
    log.debug('Request messages count: %s', len(request.messages))
    log.debug('Max input tokens: %s', AI_MAX_INPUT_TOKENS)
    log.debug('Max context tokens: %s', AI_MAX_CONTEXT_SIZE)

    start_time = clock.measured_seconds()

    # Only logs the failure (with its duration) and re-raises it: the retry decorator and
    # _process_ai_request decide what happens to any error
    try:
        api_arguments = _build_ai_api_arguments(request=request, log=log)
        response = client.chat.completions.create(**api_arguments)
    except Exception:
        end_time = clock.measured_seconds()
        duration = end_time - start_time
        # One record with the traceback, not two (BUGS.md #178 item 8)
        log.exception('API call failed after %.2f seconds', duration)
        raise

    end_time = clock.measured_seconds()
    duration = end_time - start_time
    log.info('AI response received from API in %.2f seconds', duration)

    return response


def _build_ai_api_arguments(*, request: AIRequest, log: logging.Logger) -> dict[str, Any]:
    """Build the keyword arguments of the API call.

    Args:
        request: The AI request.
        log: Logger instance.

    Returns:
        The keyword arguments for ``client.chat.completions.create``.

    """
    api_kwargs: dict[str, Any] = {
        'model': AI_MODEL,
        'messages': request.messages,
        'max_tokens': AI_MAX_OUTPUT_TOKENS,  # Use OUTPUT token limit for AI response
    }
    # Diagnostics (the whole request, prompt included), not an event of any severity
    log.debug('API call kwargs: %s', api_kwargs)
    return api_kwargs


def _process_ai_request(
    request: AIRequest,
    client: ChatClient | None,
    log: logging.Logger,
) -> AIResponse:
    """Process a single AI request with retry logic.

    Returns:
        AIResponse: The result.

    """
    # Check if AI client is available
    if client is None:
        log.warning('AI client not available, returning empty response')
        return AIResponse(content='AI features not available')

    # Create retry decorator for this request
    retry_decorator = _create_ai_retry_decorator(log)

    # Apply retry decorator to the API call function
    @retry_decorator
    def _retryable_api_call() -> object:
        return _make_ai_api_call(request, client, log)

    try:
        response = _retryable_api_call()
        return _extract_response_content(response, log)
    except Exception as error:
        # LocalAIServiceError and whatever else a request raises. Re-raising it would escape
        # the worker loop's except clause, kill the worker process, and leave the UI waiting
        # forever,
        # so report the failure back to the UI as an error response instead.
        log.exception('AI request failed permanently')
        return AIResponse(content=None, error=f'{type(error).__name__}: {error}')


def _score_size_match(requested_size: tuple[int, int], example: dict[str, Any]) -> int:
    """Score how well an example's size matches the requested size.

    Args:
        requested_size: Requested (width, height).
        example: Training example dict.

    Returns:
        Score: 5 for exact, 3 for close, 1 for same aspect ratio, 0 otherwise.

    """
    example_size = _extract_example_size(example)
    if not example_size:
        return 0

    req_width, req_height = requested_size
    ex_width, ex_height = example_size

    if req_width == ex_width and req_height == ex_height:
        return 5
    if (
        abs(req_width - ex_width) <= req_width * 0.25
        and abs(req_height - ex_height) <= req_height * 0.25
    ):
        return 3
    if abs((req_width / req_height) - (ex_width / ex_height)) < SPRITE_ASPECT_RATIO_TOLERANCE:
        return 1
    return 0


# What a request word that is one of an example's tags (or a word of one) adds to its score:
# more than a word of its name (+5), since a tag says what the example is
TAG_WORD_SCORE = 8

_ANIMATED_KEYWORDS = frozenset(['animated', 'animation', 'frame', 'walk', 'run', 'idle'])
_STATIC_KEYWORDS = frozenset(['static', 'single', 'one'])
_COLOR_KEYWORDS = frozenset([
    'red',
    'blue',
    'green',
    'yellow',
    'orange',
    'purple',
    'pink',
    'brown',
    'black',
    'white',
])


def _score_training_example(
    example: dict[str, Any],
    user_lower: str,
    user_words: set[str],
    *,
    wants_alpha: bool,
    requested_size: tuple[int, int] | None,
) -> int:
    """Score a single training example for relevance to user request.

    Args:
        example: Training example dict.
        user_lower: Lowercased user request.
        user_words: Set of words from the user request.
        wants_alpha: Whether the user wants alpha/transparency.
        requested_size: Requested (width, height) or None.

    Returns:
        Relevance score (higher is better).

    """
    score = 0
    name = example.get('name', '').lower()
    sprite_type = example.get('sprite_type', '').lower()
    has_alpha = example.get('has_alpha', False)

    # Animation type matching (+10 for exact match)
    if any(kw in user_lower for kw in _ANIMATED_KEYWORDS) and sprite_type == 'animated':
        score += 10
    if any(kw in user_lower for kw in _STATIC_KEYWORDS) and sprite_type == 'static':
        score += 10

    # Size matching
    if requested_size:
        score += _score_size_match(requested_size, example)

    # Tag matching (+8 per request word that is a tag or a word of one): a tag says what the
    # example is, so it counts before a word of its name (sprites/tags.py; tags are lowercase)
    tag_words = {word for tag in example.get('tags', []) for word in tag.split()}
    score += len(user_words & tag_words) * TAG_WORD_SCORE

    # Name keyword matching (+5 per matching word)
    score += len(user_words & set(name.split())) * 5

    # Alpha usage matching
    if wants_alpha and has_alpha:
        score += 3
    elif not wants_alpha and not has_alpha:
        score += 1

    # Color keyword hints (+2 each)
    for color in _COLOR_KEYWORDS:
        if color in user_lower and color in name:
            score += 2

    return score


def select_relevant_training_examples(
    user_request: str,
    max_examples: int = AI_MAX_TRAINING_EXAMPLES,
) -> list[dict[str, Any]]:
    """Select the most relevant training examples based on user request.

    Returns:
        list: The result.

    """
    training_data = ai_training_state['data']
    if not isinstance(training_data, list):
        return []

    if len(training_data) <= max_examples:
        return training_data

    user_lower = user_request.lower()
    requested_size = get_sprite_size_hint(user_request)
    user_words = set(user_lower.split())
    wants_alpha = any(
        kw in user_lower for kw in ['alpha', 'transparent', 'transparency', 'translucent']
    )

    scored_examples: list[tuple[float, dict[str, Any]]] = []
    for example in training_data:
        score = _score_training_example(
            example,
            user_lower,
            user_words,
            wants_alpha=wants_alpha,
            requested_size=requested_size,
        )
        scored_examples.append((score, example))

    scored_examples.sort(key=operator.itemgetter(0), reverse=True)
    # There are more examples than max_examples (fewer returned above), so this takes
    # exactly max_examples of them
    return [example for _, example in scored_examples[:max_examples]]


def _extract_example_size(example: dict[str, Any]) -> tuple[int, int] | None:
    """Extract sprite dimensions from training example.

    Args:
        example: Training example dictionary

    Returns:
        (width, height) tuple or None if size cannot be determined

    """
    # Try to get size from pixels field (static sprites)
    if 'pixels' in example:
        pixels = example['pixels']
        if isinstance(pixels, str) and '\n' in pixels:
            return _pixel_grid_size(pixels)

    # Try to get size from first animation frame
    if example.get('animations'):
        first_anim = example['animations'][0]
        if first_anim.get('frame'):
            first_frame = first_anim['frame'][0]
            if 'pixels' in first_frame:
                pixels = first_frame['pixels']
                if isinstance(pixels, str) and '\n' in pixels:
                    return _pixel_grid_size(pixels)

    return None


def _pixel_grid_size(pixels: str) -> tuple[int, int] | None:
    """Return the (width, height) the loader gives a pixels block (normalize_pixel_rows).

    The palette doesn't change the size, so none is passed.

    Returns:
        tuple[int, int] | None: The block's width and height, or None when it has no rows (the
            loader skips it, and a 0x0 size would divide by zero in _score_size_match).

    """
    normalized = normalize_pixel_rows(pixels, ())
    if not normalized.rows:
        return None
    return (normalized.width, normalized.height)


# The repair kinds normalize_pixel_rows and palette_key_problems report, each with its
# correction for the retry prompt
PIXEL_ROWS_CORRECTIONS = (
    (
        'row widths differ',
        (
            'CRITICAL: every row of a frame must have the same number of characters, one '
            'palette glyph per pixel. Count each row.'
        ),
    ),
    (
        'blank line between rows',
        'CRITICAL: no blank lines inside a frame; every line between the quotes is a row.',
    ),
    (
        'glyphs not in the palette',
        'CRITICAL: define every glyph you use in [colors], including the transparent one.',
    ),
    (
        'palette keys that are not one code point',
        'CRITICAL: every [colors] key must be exactly one character.',
    ),
)


def _pixel_rows_corrections(error_lower: str) -> str:
    """Return one correction per kind of pixel-row repair named in the error.

    Returns:
        str: The corrections, one per line.

    """
    return '\n'.join(
        correction
        for repair_kind, correction in PIXEL_ROWS_CORRECTIONS
        if repair_kind in error_lower
    )


def build_retry_prompt(original_prompt: str, validation_error: str) -> str:
    """Build a targeted retry prompt based on validation error.

    Args:
        original_prompt: Original user request
        validation_error: Error message from validate_ai_response()

    Returns:
        Enhanced prompt with specific corrections

    """
    # Base prompt
    retry_prompt = original_prompt + '\n\n'

    # Add specific corrections based on error type
    error_lower = validation_error.lower()

    if PIXEL_ROWS_ERROR_PREFIX.lower() in error_lower:
        retry_prompt += _pixel_rows_corrections(error_lower)
    elif 'missing [sprite] section' in error_lower:
        retry_prompt += 'CRITICAL: You must include a [sprite] section at the beginning.'
    elif 'missing [colors] section' in error_lower:
        retry_prompt += (
            'CRITICAL: You must include [colors] sections defining every color used in pixels.'
        )
    elif 'truncated' in error_lower or 'incomplete' in error_lower:
        retry_prompt += (
            'IMPORTANT: Previous response was cut off. '
            'Reduce detail, use fewer frames, or make it smaller to fit within token limits.'
        )
    elif 'mixed' in error_lower and 'format' in error_lower:
        retry_prompt += (
            "CRITICAL: For animated sprites, do NOT include 'pixels' in [sprite] section. "
            'Only include pixels in [[animation.frame]] sections.'
        )
    elif 'comma' in error_lower:
        retry_prompt += (
            'CRITICAL: Color values must use separate fields (red = X, green = Y, blue = Z), '
            'NOT comma-separated tuples.'
        )
    elif 'markdown' in error_lower:
        retry_prompt += (
            'CRITICAL: Return ONLY raw TOML, no markdown code blocks (```), no explanations.'
        )
    elif 'empty' in error_lower:
        retry_prompt += 'CRITICAL: You must generate sprite content, not an empty or error message.'
    else:
        # Generic retry message
        retry_prompt += (
            f'IMPORTANT: Previous attempt had an error: '
            f'{validation_error}. Please fix and try again.'
        )

    return retry_prompt


def _extract_response_content(response: object, log: logging.Logger) -> AIResponse:
    """Extract content from AI response.

    Returns:
        AIResponse: The result.

    """
    if not hasattr(response, 'choices') or not response.choices:  # type: ignore[union-attr]
        log.error('No choices in response or empty choices')
        return AIResponse(content=None, error='No choices in response')

    first_choice: Any = response.choices[0]  # type: ignore[union-attr] # ty: ignore[not-subscriptable]
    if not hasattr(first_choice, 'message'):  # type: ignore[arg-type]
        log.error("No 'message' attribute in choice")
        return AIResponse(content=None, error='No message in response choice')

    message = first_choice.message  # type: ignore[reportUnknownMemberType]
    if not hasattr(message, 'content'):  # type: ignore[arg-type]
        log.error("No 'content' attribute in message")
        return AIResponse(content=None, error='No content in response message')

    content = message.content  # type: ignore[reportUnknownMemberType]
    log.info('Response content length: %s', len(content) if content else 0)  # type: ignore[arg-type]
    return AIResponse(content=content)  # type: ignore[arg-type]


def run_ai_worker_process(
    request_queue: multiprocessing.Queue[AIRequest | None],
    response_queue: multiprocessing.Queue[tuple[str, AIResponse]],
) -> None:
    """Run the AI worker as the editor's background process (AIManager's Process target).

    Ctrl-C in a terminal sends SIGINT to the whole process group. The worker ignores it so it
    is not killed by KeyboardInterrupt and instead exits on the shutdown message the editor
    sends while it shuts down (AIManager.cleanup). terminate() (SIGTERM) still stops it.

    Args:
        request_queue: Queue to receive requests from (None asks the worker to exit).
        response_queue: Queue to send responses to.

    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    run_ai_worker(request_queue, response_queue)


def _serve_ai_requests(
    *,
    request_queue: multiprocessing.Queue[AIRequest | None],
    response_queue: multiprocessing.Queue[tuple[str, AIResponse]],
    client: ChatClient | None,
    log: logging.Logger,
) -> None:
    """Answer requests until the shutdown message (None) arrives.

    A request that fails with ValueError, KeyError, AttributeError or OSError is answered
    with an error response and the worker goes on; any other error ends the worker. A failed
    read of the request queue also ends it: a closed or broken queue never recovers, and
    retrying it logged the same error forever (BUGS.md #178 item 7).

    Args:
        request_queue: Queue to receive requests from
        response_queue: Queue to send responses to
        client: The AI client, or None when AI is unavailable.
        log: Logger instance.

    """
    request_count = 0
    while True:
        try:
            request = request_queue.get()
        except ValueError, OSError, EOFError:
            log.exception('The AI request queue cannot be read; stopping the AI worker')
            break
        request_count += 1
        log.info('Processing AI request #%s', request_count)
        if request is None:  # Shutdown signal
            log.info('Received shutdown signal, closing AI worker')
            break
        try:
            _answer_ai_request(
                request=request,
                response_queue=response_queue,
                client=client,
                log=log,
            )
        except (ValueError, KeyError, AttributeError, OSError) as e:
            log.exception('Error processing AI request')
            response_queue.put((request.request_id, AIResponse(content=None, error=str(e))))


def _answer_ai_request(
    *,
    request: AIRequest,
    response_queue: multiprocessing.Queue[tuple[str, AIResponse]],
    client: ChatClient | None,
    log: logging.Logger,
) -> None:
    """Process one request and send its response.

    Args:
        request: The request (the shutdown message, None, never reaches here).
        response_queue: Queue to send the response to.
        client: The AI client, or None when AI is unavailable.
        log: Logger instance.

    """
    ai_response = _process_ai_request(request, client, log)
    response_data = (request.request_id, ai_response)
    response_queue.put(response_data)
    log.info('Response sent successfully')


def run_ai_worker(
    request_queue: multiprocessing.Queue[AIRequest | None],
    response_queue: multiprocessing.Queue[tuple[str, AIResponse]],
) -> None:
    """Worker process for handling AI requests.

    Args:
        request_queue: Queue to receive requests from
        response_queue: Queue to send responses to

    Raises:
        ImportError: If the AI client cannot be imported.
        ValueError: If the AI request contains invalid data.
        KeyError: If a required key is missing from the request or response.
        AttributeError: If an expected attribute is missing from an object.
        OSError: If an I/O error occurs during processing.

    """
    log = _setup_ai_worker_logging()

    try:
        client = _initialize_ai_client(log)
        _serve_ai_requests(
            request_queue=request_queue,
            response_queue=response_queue,
            client=client,
            log=log,
        )
    except ImportError:
        log.exception('Failed to import the AI client')
        raise
    except OSError, ValueError, KeyError, AttributeError:
        log.exception('Fatal error in AI worker process')
        raise
