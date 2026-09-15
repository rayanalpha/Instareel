"""Proxy helpers: URL building + health checks (async + sync variants)."""
import logging
import socket
import time

from app.core.security import decrypt_secret

log = logging.getLogger("igfunnel.proxy")


def proxy_url_for(proxy) -> str | None:
    if proxy is None:
        return None
    base = proxy.url
    if proxy.username:
        pwd = decrypt_secret(proxy.password_enc) or ""
        scheme, _, rest = base.partition("://")
        auth = proxy.username + (f":{pwd}" if pwd else "")
        return f"{scheme}://{auth}@{rest}"
    return base


def check_proxy_sync(proxy) -> tuple[bool, int | None]:
    """Blocking TCP-connect check (Celery-safe). Returns (healthy, latency_ms)."""
    from urllib.parse import urlparse

    url = proxy_url_for(proxy) or proxy.url
    try:
        parts = urlparse(url if "://" in url else f"http://{url}")
        host, port = parts.hostname, parts.port or 80
        if not host:
            return False, None
        start = time.perf_counter()
        sock = socket.create_connection((host, port), timeout=10)
        sock.close()
        return True, int((time.perf_counter() - start) * 1000)
    except Exception as exc:
        log.info("Proxy %s unhealthy: %s", proxy.id, exc)
        return False, None


async def check_proxy(proxy) -> tuple[bool, int | None]:
    """TCP-connect check. Returns (healthy, latency_ms)."""
    import asyncio
    from urllib.parse import urlparse

    url = proxy_url_for(proxy) or proxy.url
    try:
        parts = urlparse(url if "://" in url else f"http://{url}")
        host, port = parts.hostname, parts.port or 80
        if not host:
            return False, None
        start = time.perf_counter()
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=10)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True, int((time.perf_counter() - start) * 1000)
    except Exception as exc:
        log.info("Proxy %s unhealthy: %s", proxy.id, exc)
        return False, None
