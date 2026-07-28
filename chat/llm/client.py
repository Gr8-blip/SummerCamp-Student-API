import concurrent.futures

from django.conf import settings


class LLMUnavailableError(Exception):
    """Raised whenever we can't get a usable reply from the LLM in time."""


_provider = None


def _get_provider():
    """
    Lazily builds and caches a single provider instance. Which
    provider class gets used is the only thing that changes if you
    swap OpenRouter for something else later — everything below this
    function is provider-agnostic.
    """
    global _provider
    if _provider is None:
        from .providers.openrouter import OpenRouterProvider

        try:
            _provider = OpenRouterProvider()
        except Exception as exc:  # noqa: BLE001 - normalize provider init failures too
            raise LLMUnavailableError(str(exc)) from exc
    return _provider


def generate_reply(system_instruction, messages, max_output_tokens=None, timeout_seconds=None):
    """
    The one entry point every mode's prompt-building code calls.
    Runs the provider call on a worker thread so we can enforce our
    own timeout regardless of what the underlying SDK does
    internally, and normalizes ANY failure (timeout, auth error, rate
    limit, empty response, network error) into LLMUnavailableError so
    callers only ever need to handle one exception type.
    """
    max_output_tokens = max_output_tokens or settings.LLM_MAX_OUTPUT_TOKENS
    timeout_seconds = timeout_seconds or settings.LLM_TIMEOUT_SECONDS

    provider = _get_provider()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(provider.complete, system_instruction, messages, max_output_tokens)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            raise LLMUnavailableError("LLM request timed out.") from exc
        except LLMUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize any provider/SDK error
            raise LLMUnavailableError(str(exc)) from exc
