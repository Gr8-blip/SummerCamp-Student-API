import concurrent.futures

from django.conf import settings
from google import genai
from google.genai import types


class GeminiUnavailableError(Exception):
    """Raised whenever we can't get a usable reply from Gemini in time."""


_client = None


def _get_client():
    """
    Lazily builds a single shared genai.Client using the server-side
    API key. The key is read once from settings (which itself reads
    it from the environment / .env) and is never passed through any
    request/response body or log line.
    """
    global _client
    if _client is None:
        if not settings.GEMINI_API_KEY:
            raise GeminiUnavailableError("GEMINI_API_KEY is not configured.")
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _role_for_gemini(role):
    # Gemini's SDK uses "user" and "model"; our public contract uses
    # "user" and "assistant" to match common chat-API conventions.
    return "model" if role == "assistant" else "user"


def build_contents(history, message):
    """
    Turns the validated history (already capped to the most recent
    N messages by the caller) plus the new user message into the
    `contents` list the genai SDK expects.
    """
    contents = []
    for turn in history:
        contents.append(
            types.Content(
                role=_role_for_gemini(turn["role"]),
                parts=[types.Part.from_text(text=turn["content"])],
            )
        )
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=message)],
        )
    )
    return contents


def build_system_instruction(student_prompt):
    """
    Combines the fixed backend system rules with the student's
    personality prompt. The student prompt is ALWAYS appended after
    (and clearly separated from) the fixed rules — it never replaces
    or precedes them, so it can't override the safety rules above it.
    """
    student_prompt = (student_prompt or "").strip()
    return (
        f"{settings.SYSTEM_RULES}\n\n"
        f"----------------------------\n\n"
        f"STUDENT PERSONALITY\n\n"
        f"{student_prompt}"
    )


def _call_gemini(system_instruction, contents):
    client = _get_client()
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=settings.GEMINI_MAX_OUTPUT_TOKENS,
        ),
    )
    text = getattr(response, "text", None)
    if not text:
        raise GeminiUnavailableError("Gemini returned an empty response.")
    return text


def get_ai_reply(prompt, message, history):
    """
    Main entry point used by the view. Returns the reply text, or
    raises GeminiUnavailableError (including on timeout) so the view
    can turn that into the standard "AI is currently unavailable"
    response.
    """
    trimmed_history = history[-settings.MAX_HISTORY_MESSAGES:] if history else []
    contents = build_contents(trimmed_history, message)
    system_instruction = build_system_instruction(prompt)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_call_gemini, system_instruction, contents)
        try:
            return future.result(timeout=settings.GEMINI_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError as exc:
            raise GeminiUnavailableError("Gemini request timed out.") from exc
        except Exception as exc:  # noqa: BLE001 - normalize any SDK error
            raise GeminiUnavailableError(str(exc)) from exc
