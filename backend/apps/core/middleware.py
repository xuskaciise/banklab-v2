"""Proxy trust gate (see apps/core/net.py)."""

from .net import from_trusted_proxy


class ProxyTrustMiddleware:
    """Drop forwarded-protocol headers unless the request carries the proxy shared secret.

    Must run before SecurityMiddleware (which reads SECURE_PROXY_SSL_HEADER). A no-op when
    `PROXY_SHARED_SECRET` is unset.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not from_trusted_proxy(request):
            request.META.pop("HTTP_X_FORWARDED_PROTO", None)
        return self.get_response(request)
