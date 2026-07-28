from django.conf import settings

from .llm.client import LLMUnavailableError, generate_reply

__all__ = ["LLMUnavailableError", "get_ai_reply"]


def _role_for_llm(role):
    # Our public contract uses "user"/"assistant"; that's already the
    # OpenAI-style role vocabulary OpenRouter expects, so this is a
    # pass-through today. Kept as a function (not inlined) so a future
    # provider with different role names only needs a change here.
    return "assistant" if role == "assistant" else "user"


def build_messages(history, message):
    """
    Turns the validated history (already capped to the most recent
    N messages by the caller) plus the new user message into the
    OpenAI-style `messages` list (excluding the system prompt, which
    is passed separately -- see build_system_instruction).
    """
    messages = [
        {"role": _role_for_llm(turn["role"]), "content": turn["content"]}
        for turn in history
    ]
    messages.append({"role": "user", "content": message})
    return messages


def build_system_instruction(student_prompt):
    """
    Combines the fixed backend system rules with the student's
    personality prompt. The student prompt is ALWAYS appended after
    (and clearly separated from) the fixed rules -- it never replaces
    or precedes them, so it can't override the safety rules above it.
    """
    student_prompt = (student_prompt or "").strip()
    return (
        f"{settings.SYSTEM_RULES}\n\n"
        f"----------------------------\n\n"
        f"STUDENT PERSONALITY\n\n"
        f"{student_prompt}"
    )


def get_ai_reply(prompt, message, history):
    """
    Main entry point used by the view for "template" mode. Returns
    the reply text, or raises LLMUnavailableError (including on
    timeout) so the view can turn that into the standard "AI is
    currently unavailable" response.
    """
    trimmed_history = history[-settings.MAX_HISTORY_MESSAGES:] if history else []
    messages = build_messages(trimmed_history, message)
    system_instruction = build_system_instruction(prompt)

    return generate_reply(system_instruction, messages)
