from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """
    Minimal interface every LLM backend must implement. Keeping this
    thin (one method, plain-Python types in/out) is what lets
    chat/llm/client.py stay provider-agnostic — swapping OpenRouter
    for a direct OpenAI key, Anthropic, or anything else later means
    writing one new class here, not touching client.py, services.py,
    or views.py.
    """

    @abstractmethod
    def complete(self, system_instruction: str, messages: list[dict], max_output_tokens: int) -> str:
        """
        `messages` is a list of {"role": "user"|"assistant", "content": str}
        in chronological order (history + the new message), NOT
        including the system prompt — that's passed separately via
        `system_instruction` since not every provider's SDK takes it
        the same way.

        Must return the reply text, or raise any exception on
        failure — chat/llm/client.py is responsible for catching
        provider-specific exceptions and normalizing them into
        LLMUnavailableError, so provider implementations don't need
        their own try/except for that.
        """
        raise NotImplementedError
