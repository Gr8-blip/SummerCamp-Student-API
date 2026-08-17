from django.conf import settings
from openai import OpenAI

from .base import LLMProvider


class OpenRouterProvider(LLMProvider):
    """
    OpenRouter exposes an OpenAI-compatible /chat/completions API, so
    we use the official `openai` SDK pointed at OpenRouter's base_url
    instead of a bespoke HTTP client. Any other OpenAI-compatible
    endpoint (a direct OpenAI key, a self-hosted vLLM server, etc.)
    could reuse this exact class with a different base_url/api_key —
    only truly non-OpenAI-shaped APIs (Anthropic's native SDK, etc.)
    would need their own LLMProvider implementation.
    """

    def __init__(self):
        if not settings.OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY is not configured.")
        self._client = OpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
        )

    def complete(self, system_instruction, messages, max_output_tokens):
        # OpenRouter (like OpenAI) wants the system prompt as a
        # regular message with role "system", first in the list.
        payload_messages = [{"role": "system", "content": system_instruction}, *messages]

        # These two headers are optional but recommended by OpenRouter:
        # they attribute usage to your app on https://openrouter.ai
        # rankings/analytics. Harmless to omit if left unset.
        extra_headers = {}
        if settings.OPENROUTER_SITE_URL:
            extra_headers["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
        if settings.OPENROUTER_SITE_NAME:
            extra_headers["X-Title"] = settings.OPENROUTER_SITE_NAME

        response = self._client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=payload_messages,
            max_tokens=max_output_tokens,
            tools=[
                {
                    "type": "openrouter:web_search",
                }
            ],
            extra_headers=extra_headers or None,
        )

        choice = response.choices[0] if response.choices else None
        text = choice.message.content if choice and choice.message else None
        if not text:
            raise RuntimeError("OpenRouter returned an empty response.")
        return text
