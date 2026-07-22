from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def custom_exception_handler(exc, context):
    """
    Wraps DRF's default exception handler so validation errors (400),
    permission errors (403), throttling (429), etc. all come back as
    a flat, predictable {"error": "..."} body instead of DRF's
    default nested field-error structure. Keeps the frontend contract
    simple for students.
    """
    response = drf_exception_handler(exc, context)

    if response is None:
        return None

    detail = response.data

    if isinstance(detail, dict) and "detail" in detail and len(detail) == 1:
        message = str(detail["detail"])
    elif isinstance(detail, dict):
        # Field validation errors, e.g. {"message": ["This field may not be blank."]}
        first_field = next(iter(detail))
        first_error = detail[first_field]
        if isinstance(first_error, list) and first_error:
            message = str(first_error[0])
        else:
            message = str(first_error)
    elif isinstance(detail, list) and detail:
        message = str(detail[0])
    else:
        message = str(detail)

    response.data = {"error": message}
    return response
