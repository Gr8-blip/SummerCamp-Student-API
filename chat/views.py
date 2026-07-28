import logging
import time

from django.conf import settings
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import HasValidProjectKey
from .serializers import ChatRequestSerializer
from .services import LLMUnavailableError, get_ai_reply
from .utils import get_client_ip

logger = logging.getLogger("chat")


def _rate_limit_key(group, request):
    return get_client_ip(request)


@api_view(["POST"])
@permission_classes([HasValidProjectKey])
@ratelimit(key=_rate_limit_key, rate=settings.CHAT_RATE_LIMIT, method="POST", block=False)
def chat_view(request):
    """
    POST /api/chat/

    Validates the request, merges the fixed backend system rules with
    the student's personality prompt, forwards the (trimmed)
    conversation to Gemini 2.5 Flash, and returns only:

        {"reply": "..."}

    Never persists anything — fully stateless per request.
    """
    start_time = time.monotonic()
    client_ip = get_client_ip(request)

    # django-ratelimit sets this flag rather than raising, since we
    # configured block=False above — that lets us return our own
    # {"error": ...} body with a 429 status instead of Django's
    # default PermissionDenied/403 page.
    if getattr(request, "limited", False):
        _log_request(client_ip, start_time, status_code=429)
        return Response(
            {"error": "Rate limit exceeded. Please slow down and try again shortly."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    serializer = ChatRequestSerializer(data=request.data)
    if not serializer.is_valid():
        _log_request(client_ip, start_time, status_code=400)
        # Reuse the same flattening logic as the global exception
        # handler so both paths return a consistent {"error": ...} shape.
        first_field = next(iter(serializer.errors))
        first_error = serializer.errors[first_field]
        message = str(first_error[0]) if isinstance(first_error, list) else str(first_error)
        return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    try:
        reply = get_ai_reply(
            prompt=data.get("prompt", ""),
            message=data["message"],
            history=data.get("history", []),
        )
    except LLMUnavailableError as exc:
        logger.error("LLM call failed: %s", exc)
        _log_request(client_ip, start_time, status_code=503)
        return Response(
            {"error": "The AI is currently unavailable. Please try again."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    _log_request(client_ip, start_time, status_code=200)
    return Response({"reply": reply}, status=status.HTTP_200_OK)


def _log_request(client_ip, start_time, status_code):
    elapsed_ms = round((time.monotonic() - start_time) * 1000, 1)
    # Only timestamp (added automatically by the formatter), IP,
    # status, and response time are logged. Never log headers, the
    # request body, the Gemini API key, or the project key.
    logger.info("ip=%s status=%s response_time_ms=%s", client_ip, status_code, elapsed_ms)
