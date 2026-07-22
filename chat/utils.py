def get_client_ip(request):
    """
    Returns the best-guess client IP. Prefers X-Forwarded-For (set by
    most reverse proxies / load balancers) and falls back to
    REMOTE_ADDR. If you deploy behind a proxy that doesn't set this
    header, configure it to do so — otherwise every request will
    appear to come from the proxy's own address.
    """
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")
