"""Client IP resolution shared by login throttling and the audit log."""

import hmac
import ipaddress

from django.conf import settings

PROXY_HEADER_META = "HTTP_X_BANKLAB_PROXY"


def from_trusted_proxy(request) -> bool:
    """True when proxy headers may be believed.

    Without `settings.PROXY_SHARED_SECRET` every request counts as trusted (the deployment
    must then guarantee the app is only reachable through the proxy). With a secret, the proxy
    must send it in `X-BankLab-Proxy`; a sibling container on a shared network cannot.
    """
    secret = getattr(settings, "PROXY_SHARED_SECRET", "")
    if not secret:
        return True
    sent = request.META.get(PROXY_HEADER_META, "")
    return hmac.compare_digest(sent.encode(), secret.encode())


def client_ip(request) -> str:
    """Best-effort client IP for throttling and auditing.

    `settings.CLIENT_IP_HEADER` (a META key such as HTTP_CF_CONNECTING_IP or HTTP_X_REAL_IP)
    names a header that a trusted reverse proxy sets (and overwrites) on every request. Only
    configure it when the app is reachable exclusively through that proxy, otherwise clients
    can spoof it. Raw X-Forwarded-For chains are never trusted. An empty setting, a missing
    header or an unparsable value falls back to REMOTE_ADDR.
    """
    if request is None:
        return ""
    remote = request.META.get("REMOTE_ADDR", "")
    header = getattr(settings, "CLIENT_IP_HEADER", "")
    if header and from_trusted_proxy(request):
        raw = (request.META.get(header) or "").strip()
        try:
            return str(ipaddress.ip_address(raw))
        except ValueError:
            pass
    return remote
