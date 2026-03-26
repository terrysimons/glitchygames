"""AI worker infrastructure for Bitmappy sprite generation.

Contains the AI worker process function and all supporting functions
for initializing the AI client, managing timeouts, processing requests,
and selecting training examples.
"""

from __future__ import annotations

import logging
import operator
import time
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from glitchygames.ai import get_sprite_size_hint

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
    AI_MODEL_DOWNLOAD_TIMEOUT,
    AI_TIMEOUT,
    MODEL_DOWNLOAD_TIME_THRESHOLD_SECONDS,
    SPRITE_ASPECT_RATIO_TOLERANCE,
    ai_training_state,
)
from .models import AIRequest, AIResponse

# Try to import aisuite, but don't fail if it's not available.
# Catch AttributeError too — docstring_parser (an aisuite transitive dependency)
# uses ast.NameConstant which was removed in Python 3.14.
try:
    import aisuite as ai
except ImportError, AttributeError:
    ai = None  # ty: ignore[invalid-assignment]

# Try to import backoff for retry logic
try:
    import backoff
except ImportError:
    backoff = None  # ty: ignore[invalid-assignment]

if TYPE_CHECKING:
    import multiprocessing
    from collections.abc import Callable


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


def _create_ollama_config(log: logging.Logger) -> dict[str, Any]:
    """Create ollama-specific configuration with appropriate timeouts.

    Returns:
        dict: The result.

    """
    if not AI_MODEL.startswith('ollama:'):
        return {}

    # Check if model is already downloaded to choose appropriate timeout
    model_status = _check_ollama_model_status(log)
    if model_status['downloaded']:
        timeout_value = AI_TIMEOUT  # Use normal timeout for downloaded models
        log.info('Model already downloaded, using %ss timeout', timeout_value)
    else:
        timeout_value = AI_MODEL_DOWNLOAD_TIMEOUT  # Use longer timeout for download
        log.info('Model needs download, using %ss timeout (30 minutes)', timeout_value)

    # Create ollama-specific configuration
    config = {
        'ollama': {
            'timeout': timeout_value,
            'request_timeout': timeout_value,
            'read_timeout': timeout_value,
        },
    }

    log.info('Created ollama config with %ss timeout', timeout_value)
    return config


def _set_ollama_env_timeout(log: logging.Logger) -> None:
    """Set the OLLAMA_TIMEOUT environment variable based on model download status.

    Args:
        log: Logger instance.

    """
    import os

    if not AI_MODEL.startswith('ollama:'):
        return

    model_status = _check_ollama_model_status(log)
    if model_status['downloaded']:
        ollama_timeout = AI_TIMEOUT
        log.info('Model already downloaded, using %ss timeout', ollama_timeout)
    else:
        ollama_timeout = AI_MODEL_DOWNLOAD_TIMEOUT
        log.info('Model needs download, using %ss timeout (30 minutes)', ollama_timeout)

    os.environ['OLLAMA_TIMEOUT'] = str(ollama_timeout)
    log.info('Set OLLAMA_TIMEOUT environment variable to %s seconds', ollama_timeout)


def _configure_ollama_provider(log: logging.Logger, client: Any) -> None:
    """Apply ollama-specific timeout configuration to the client's providers.

    Args:
        log: Logger instance.
        client: The AI client.

    """
    if not AI_MODEL.startswith('ollama:') or not hasattr(client, '_providers'):
        return

    log.info('Applying additional ollama-specific configuration...')
    timeout_value = AI_MODEL_DOWNLOAD_TIMEOUT

    for provider_name, provider in client._providers.items():
        if 'ollama' not in provider_name.lower():
            continue

        log.info('Configuring ollama provider: %s', provider_name)

        if hasattr(provider, 'timeout'):
            provider.timeout = timeout_value
            log.info('Set ollama provider timeout to %ss', timeout_value)

        if hasattr(provider, 'client') and hasattr(provider.client, 'timeout'):
            provider.client.timeout = timeout_value
            log.info('Set ollama HTTP client timeout to %ss', timeout_value)

        if hasattr(provider, 'client'):
            for timeout_attr in ['request_timeout', 'read_timeout', 'connect_timeout']:
                if hasattr(provider.client, timeout_attr):
                    setattr(provider.client, timeout_attr, timeout_value)
                    log.info('Set ollama %s to %ss', timeout_attr, timeout_value)


def _get_provider_timeout_value(log: logging.Logger) -> int:
    """Get the appropriate timeout value based on model status.

    Args:
        log: Logger instance.

    Returns:
        The timeout value in seconds.

    """
    if AI_MODEL.startswith('ollama:'):
        model_status = _check_ollama_model_status(log)
        if not model_status['downloaded']:
            return AI_MODEL_DOWNLOAD_TIMEOUT
    return AI_TIMEOUT


def _configure_provider_client_timeout(
    log: logging.Logger, provider_name: str, provider: Any, timeout_value: int,
) -> None:
    """Configure timeout on a provider's client and underlying HTTP client.

    Args:
        log: Logger instance.
        provider_name: Name of the provider.
        provider: The provider object.
        timeout_value: Timeout value in seconds.

    """
    if not hasattr(provider, 'client'):
        return

    log.debug(f'Provider client: {type(provider.client)}')
    log.debug(f'Provider client attributes: {dir(provider.client)}')

    if hasattr(provider.client, 'timeout'):
        old_timeout = getattr(provider.client, 'timeout', 'unknown')
        provider.client.timeout = timeout_value
        log.info('Set %ss timeout for %s provider (was: %s)', timeout_value, provider_name, old_timeout)
    elif hasattr(provider.client, '_client') and hasattr(provider.client._client, 'timeout'):
        old_timeout = getattr(provider.client._client, 'timeout', 'unknown')
        provider.client._client.timeout = timeout_value
        log.info(
            'Set %ss timeout for %s provider HTTP client (was: %s)', timeout_value, provider_name, old_timeout,
        )

    # Additional timeout configurations for ollama
    if AI_MODEL.startswith('ollama:'):
        for attr_name in ['request_timeout', 'read_timeout']:
            if hasattr(provider.client, attr_name):
                old_timeout = getattr(provider.client, attr_name, 'unknown')
                setattr(provider.client, attr_name, AI_TIMEOUT)
                log.info('Set %s for %s provider (was: %s)', attr_name, provider_name, old_timeout)


def _configure_client_timeouts(log: logging.Logger, client: Any) -> None:
    """Configure timeouts on all providers in the AI client.

    Args:
        log: Logger instance.
        client: The AI client.

    """
    try:
        log.debug(f'Client type: {type(client)}')
        log.debug(f'Client attributes: {dir(client)}')

        if not hasattr(client, '_providers'):
            log.warning('Client does not have _providers attribute')
            log.info('AI client initialized successfully with %ss timeout', AI_TIMEOUT)
            return

        timeout_value = _get_provider_timeout_value(log)
        log.debug(f'Found {len(client._providers)} providers')

        for provider_name, provider in client._providers.items():
            log.debug(f'Provider {provider_name}: {type(provider)}')
            log.debug(f'Provider attributes: {dir(provider)}')
            _configure_provider_client_timeout(log, provider_name, provider, timeout_value)

        log.info('AI client initialized successfully with %ss timeout', AI_TIMEOUT)
    except Exception as e:
        log.warning('Could not configure timeout: %s', e)
        log.exception('Timeout configuration error details')
        log.info('AI client initialized with default timeout')


def _initialize_ai_client(log: logging.Logger) -> Any:
    """Initialize AI client.

    Returns:
        object: The result.

    """
    if ai is None:
        log.error('aisuite not available - AI features disabled')
        return None

    log.info('aisuite is available')
    log.debug(f'aisuite version: {getattr(ai, "__version__", "unknown")}')

    _set_ollama_env_timeout(log)

    log.info('Initializing AI client...')
    provider_config = _create_ollama_config(log)

    if provider_config:
        log.info('Initializing client with provider config: %s', provider_config)
        client = ai.Client(provider_config)
    else:
        client = ai.Client()

    _configure_ollama_provider(log, client)
    _configure_client_timeouts(log, client)

    log.debug(f'Client type: {type(client)}')
    return client


def _check_ollama_model_status(log: logging.Logger) -> dict[str, Any]:
    """Check if the ollama model is already downloaded and ready.

    Returns:
        dict: The result.

    """
    if not AI_MODEL.startswith('ollama:'):
        return {'downloaded': True, 'reason': 'not_ollama'}

    try:
        import json
        import urllib.request

        # Extract model name from ollama:model_name format
        model_name = AI_MODEL.split(':', 1)[1]

        # Check if model exists locally
        request = urllib.request.Request('http://localhost:11434/api/tags')
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310  # nosec B310 -- hardcoded http://localhost URL
            if response.status == HTTPStatus.OK:
                data = json.loads(response.read().decode())
                models = data.get('models', [])
                for model in models:
                    if model_name in model.get('name', ''):
                        log.info('Model %s is already downloaded', model_name)
                        return {'downloaded': True, 'reason': 'already_downloaded'}

                log.info('Model %s needs to be downloaded', model_name)
                return {'downloaded': False, 'reason': 'needs_download'}
            log.warning(f'Could not check model status: HTTP {response.status}')
            return {'downloaded': False, 'reason': 'api_error'}

    except (OSError, ValueError, KeyError) as e:
        log.warning('Could not check ollama model status: %s', e)
        return {'downloaded': False, 'reason': 'check_failed'}


def _log_capabilities_dump(log: logging.Logger, **fields: object) -> None:
    """Log a formatted model capabilities dump block.

    Args:
        log: Logger instance.
        **fields: Key-value pairs to include in the dump.

    """
    log.debug(f'\n{"=" * 60}')
    log.debug('MODEL CAPABILITIES DUMP')
    log.debug('=' * 60)
    log.debug('Model: %s', AI_MODEL)
    for key, value in fields.items():
        log.debug('%s: %s', key, value)
    log.debug(f'{"=" * 60}\n')


def _parse_capabilities_response(log: logging.Logger, content: str) -> dict[str, Any]:
    """Parse model capabilities from response content.

    Args:
        log: Logger instance.
        content: The model's response content string.

    Returns:
        Dictionary of capabilities.

    """
    try:
        # Try to parse comma-separated values first
        if ',' in content.strip():
            parts = content.strip().split(',')
            if len(parts) == AI_CAPABILITY_RESPONSE_FIELD_COUNT:
                context_size = int(parts[0].strip())
                output_limit = int(parts[1].strip())
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

        # Fallback to single number parsing
        max_tokens = int(content.strip())
        log.info('Detected max tokens: %s', max_tokens)
        _log_capabilities_dump(log, **{'Max Output Tokens': max_tokens, 'Model Response': content})
        return {'max_tokens': max_tokens}
    except ValueError:
        log.warning('Could not parse max tokens from response: %s', content)
        _log_capabilities_dump(
            log, **{'Max Output Tokens': 'Could not parse', 'Model Response': content},
        )
        return {'max_tokens': None, 'raw_response': content}


def _query_model_capabilities(log: logging.Logger, client: Any) -> dict[str, Any]:
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
    log.info('This may take a while if the model needs to be downloaded first...')

    start_time = time.time()
    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=test_messages,
        max_tokens=256,
    )
    duration = time.time() - start_time

    log.info(f'Model capability query completed in {duration:.2f} seconds')
    if duration > MODEL_DOWNLOAD_TIME_THRESHOLD_SECONDS:
        log.info('Model was likely downloaded during this request')

    if hasattr(response, 'choices') and response.choices:
        content = response.choices[0].message.content
        log.info('Model response about capabilities: %s', content)
        return _parse_capabilities_response(log, content)

    _log_capabilities_dump(log, **{'Max Tokens': 'Unknown (no response)'})
    return {'max_tokens': None}


def _get_model_capabilities(log: logging.Logger) -> dict[str, Any]:  # type: ignore[reportUnusedFunction]
    """Query the model's capabilities including max tokens.

    Returns:
        dict: The model capabilities.

    """
    try:
        model_status = _check_ollama_model_status(log)

        if not model_status['downloaded']:
            log.info(f'Model needs to be downloaded: {model_status["reason"]}')
            log.info(f'\n{"=" * 60}')
            log.info('MODEL DOWNLOAD DETECTED')
            log.info('=' * 60)
            log.info('Model: %s', AI_MODEL)
            log.info('Status: Model needs to be downloaded')
            log.info('This may take several minutes depending on model size...')
            log.info(f'{"=" * 60}\n')

        client = _initialize_ai_client(log)

        if client is None:
            log.warning('AI client not available, using default capabilities')
            return {'max_tokens': 8192, 'num_ctx': 65536}

        return _query_model_capabilities(log, client)

    except (ValueError, ConnectionError, TimeoutError) as e:
        log.exception('Failed to query model capabilities')
        _log_capabilities_dump(log, **{'Max Tokens': 'Unknown (query failed)', 'Error': str(e)})
        return {'max_tokens': None}


def _create_ai_retry_decorator(
    log: logging.Logger,
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Create a retry decorator for AI requests with exponential backoff.

    Returns:
        object: The result.

    """
    if backoff is None:
        # If backoff is not available, return a no-op decorator
        def no_op_decorator(func: Callable[..., object]) -> Callable[..., object]:
            return func

        return no_op_decorator

    def giveup_handler(details: dict[str, Any]) -> None:
        """Handle final failure after all retries."""
        log.error(
            f'AI request failed permanently after {details["tries"]} attempts:'
            f' {details["exception"]}',
        )

    def backoff_handler(details: dict[str, Any]) -> None:
        """Handle backoff between retries."""
        log.warning(
            f'AI request failed (attempt {details["tries"]}), retrying in {details["wait"]:.1f}s:'
            f' {details["exception"]}',
        )

    return backoff.on_exception(
        backoff.expo,
        (Exception,),  # Catch all exceptions for retry
        max_tries=AI_MAX_RETRIES,
        base=AI_BASE_DELAY,
        max_value=AI_MAX_DELAY,
        giveup=lambda e: isinstance(e, (ValueError, KeyboardInterrupt, SystemExit)),
        on_giveup=giveup_handler,  # type: ignore[arg-type]
        on_backoff=backoff_handler,  # type: ignore[arg-type]
    )


def _make_ai_api_call(request: AIRequest, client: Any, log: logging.Logger) -> Any:
    """Make the actual API call to the AI service.

    Returns:
        object: The result.

    """
    log.info('Making API call to AI service...')
    log.debug('Using model: %s', AI_MODEL)
    log.debug(f'Request messages count: {len(request.messages)}')
    log.debug('Max input tokens: %s', AI_MAX_INPUT_TOKENS)
    log.debug('Max context tokens: %s', AI_MAX_CONTEXT_SIZE)

    start_time = time.time()

    try:
        # Try to pass timeout parameters directly to the API call
        api_kwargs = {
            'model': AI_MODEL,
            'messages': request.messages,
            'max_tokens': AI_MAX_OUTPUT_TOKENS,  # Use OUTPUT token limit for AI response
        }

        # Add timeout parameters if the client supports them
        if hasattr(client.chat.completions, 'create'):
            # Check if the create method accepts timeout parameters
            import inspect

            sig = inspect.signature(client.chat.completions.create)

            # Try multiple timeout parameter names
            timeout_params = ['timeout', 'request_timeout', 'client_timeout', 'api_timeout']
            timeout_added = False

            for param_name in timeout_params:
                if param_name in sig.parameters:
                    # Use longer timeout for ollama models
                    timeout_value = (
                        AI_MODEL_DOWNLOAD_TIMEOUT if AI_MODEL.startswith('ollama:') else AI_TIMEOUT
                    )
                    api_kwargs[param_name] = timeout_value
                    log.debug('Added %s=%s to API call', param_name, timeout_value)
                    timeout_added = True
                    break

            if not timeout_added:
                log.warning('No timeout parameter found in API call signature')
                log.debug(f'Available parameters: {list(sig.parameters.keys())}')

        log.critical('API call kwargs: %s', api_kwargs)
        response = client.chat.completions.create(**api_kwargs)
    except Exception:
        end_time = time.time()
        duration = end_time - start_time
        log.exception(f'API call failed after {duration:.2f} seconds')
        log.exception('API call failed with exception')
        raise

    end_time = time.time()
    duration = end_time - start_time
    log.info(f'AI response received from API in {duration:.2f} seconds')

    return response


def _process_ai_request(request: AIRequest, client: Any, log: logging.Logger) -> AIResponse:
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
    except Exception:
        log.exception('AI request failed permanently')
        raise


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
    user_request: str, max_examples: int = AI_MAX_TRAINING_EXAMPLES,
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
    relevant_examples = [example for _, example in scored_examples[:max_examples]]

    if len(relevant_examples) < max_examples:
        remaining = [ex for _, ex in scored_examples if ex not in relevant_examples]
        relevant_examples.extend(remaining[: max_examples - len(relevant_examples)])

    return relevant_examples


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
            lines = pixels.strip().split('\n')
            if lines:
                height = len(lines)
                width = len(lines[0])
                return (width, height)

    # Try to get size from first animation frame
    if example.get('animations'):
        first_anim = example['animations'][0]
        if first_anim.get('frame'):
            first_frame = first_anim['frame'][0]
            if 'pixels' in first_frame:
                pixels = first_frame['pixels']
                if isinstance(pixels, str) and '\n' in pixels:
                    lines = pixels.strip().split('\n')
                    if lines:
                        height = len(lines)
                        width = len(lines[0])
                        return (width, height)

    return None


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

    if 'missing [sprite] section' in error_lower:
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

    first_choice: Any = response.choices[0]  # type: ignore[union-attr]
    if not hasattr(first_choice, 'message'):  # type: ignore[arg-type]
        log.error("No 'message' attribute in choice")
        return AIResponse(content=None, error='No message in response choice')

    message = first_choice.message  # type: ignore[reportUnknownMemberType]
    if not hasattr(message, 'content'):  # type: ignore[arg-type]
        log.error("No 'content' attribute in message")
        return AIResponse(content=None, error='No content in response message')

    content = message.content  # type: ignore[reportUnknownMemberType]
    log.info(f'Response content length: {len(content) if content else 0}')  # type: ignore[arg-type]
    return AIResponse(content=content)  # type: ignore[arg-type]


def run_ai_worker(
    request_queue: multiprocessing.Queue[AIRequest | None],
    response_queue: multiprocessing.Queue[tuple[str, AIResponse]],
) -> None:
    """Worker process for handling AI requests.

    Args:
        request_queue: Queue to receive requests from
        response_queue: Queue to send responses to

    Raises:
        ImportError: If aisuite cannot be imported.
        ValueError: If the AI request contains invalid data.
        KeyError: If a required key is missing from the request or response.
        AttributeError: If an expected attribute is missing from an object.
        OSError: If an I/O error occurs during processing.

    """
    log = _setup_ai_worker_logging()

    try:
        client = _initialize_ai_client(log)
        request_count = 0

        request = None
        while True:
            try:
                request = request_queue.get()
                request_count += 1
                log.info('Processing AI request #%s', request_count)

                if request is None:  # Shutdown signal
                    log.info('Received shutdown signal, closing AI worker')
                    break

                ai_response = _process_ai_request(request, client, log)
                response_data = (request.request_id, ai_response)
                response_queue.put(response_data)
                log.info('Response sent successfully')

            except (ValueError, KeyError, AttributeError, OSError) as e:
                log.exception('Error processing AI request')
                if request:
                    response_queue.put((request.request_id, AIResponse(content=None, error=str(e))))
    except ImportError:
        log.exception('Failed to import aisuite')
        raise
    except OSError, ValueError, KeyError, AttributeError:
        log.exception('Fatal error in AI worker process')
        raise
