from django.conf import settings
from rest_framework.permissions import BasePermission


class HasValidProjectKey(BasePermission):
    """
    Requires a valid `X-Project-Key` header on every request. The
    valid key lives in settings.PROJECT_API_KEY (sourced from the
    PROJECT_API_KEY environment variable) and is never echoed back
    in any response or log line.
    """

    message = "Invalid or missing project key."

    def has_permission(self, request, view):
        provided_key = request.headers.get("X-Project-Key", "")
        expected_key = settings.PROJECT_API_KEY

        if not expected_key:
            # Misconfiguration: fail closed rather than silently
            # accepting every request.
            return False

        return _constant_time_compare(provided_key, expected_key)


def _constant_time_compare(a, b):
    # Avoid django.utils.crypto import cost concerns / just reuse it.
    from django.utils.crypto import constant_time_compare

    return constant_time_compare(a or "", b or "")
