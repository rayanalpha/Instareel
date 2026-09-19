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


#: Schemes accepted in proxy lists. https:// URLs are normalized to the
#: http protocol (same CONNECT semantics for our checks/uploads).
PROXY_SCHEMES = ("http", "https", "socks4", "socks5")
MAX_IMPORT_LINES = 2000


def parse_proxy_line(line: str, default_protocol: str = "http") -> "tuple[dict | None, str | None]":
    """Parse one proxy-list line into a spec (pure — unit tested).

    Accepted shapes (country suffix optional on any of them):
      host:port | scheme://host:port | user:pass@host:port
      scheme://user:pass@host:port | host:port:user:pass
      ... + " |CC" or " #CC" country tag, "# comment" and blank lines skipped.

    Returns (spec, None) or (None, reason). spec keys: scheme, host, port,
    username, password, country. Callers map https->http for the DB enum.
    """
    import re

    raw = (line or "").strip()
    if not raw or raw.startswith("#"):
        return None, "blank/comment"
    # Trailing country tag: " ... |DE" or " ... #DE" (2 letters only).
    country = ""
    m = re.search(r"\s*[|#]\s*([A-Za-z]{2})\s*$", raw)
    if m:
        country = m.group(1).upper()
        raw = raw[: m.start()].strip()
        if not raw:
            return None, "blank/comment"
    scheme = (default_protocol or "http").lower()
    rest = raw
    if "://" in rest:
        scheme, _, rest = rest.partition("://")
        scheme = scheme.lower()
        if scheme not in PROXY_SCHEMES:
            return None, f"bad scheme '{scheme}'"
    username = password = ""
    hostport = rest
    if "@" in rest:
        auth, _, hostport = rest.rpartition("@")
        if ":" in auth:
            username, _, password = auth.partition(":")
        else:
            username = auth
        if not username:
            return None, "empty username"
    else:
        parts = hostport.split(":")
        # host:port:user:pass (no brackets) — IPv6 must use scheme://[v6]:port.
        if len(parts) == 4 and not hostport.startswith("["):
            hostport, username, password = f"{parts[0]}:{parts[1]}", parts[2], parts[3]
            if not username:
                return None, "empty username"
        elif len(parts) != 2 and not hostport.startswith("["):
            return None, "want host:port or host:port:user:pass"
    hostport = hostport.strip()
    if hostport.startswith("["):
        # [v6]:port
        end = hostport.find("]")
        host = hostport[1:end]
        tail = hostport[end + 1 :]
        port_s = tail[1:] if tail.startswith(":") else ""
    else:
        host, _, port_s = hostport.rpartition(":")
    host = (host or "").strip().strip("[]")
    try:
        port = int((port_s or "").strip())
    except ValueError:
        return None, "bad port"
    if not host:
        return None, "empty host"
    if not 1 <= port <= 65535:
        return None, "port out of range"
    return (
        {"scheme": scheme, "host": host, "port": port,
         "username": username.strip(), "password": password, "country": country},
        None,
    )


def proxy_fingerprint(scheme: str, host: str, port: int) -> str:
    """Dedupe key: normalized scheme + lowercase host + port."""
    scheme = "http" if scheme == "https" else scheme
    return f"{scheme}://{host.lower()}:{port}"


def _tcp_check(url: str, timeout: int = 10) -> tuple[bool, int | None]:
    """Raw TCP connect — fast pre-check, proves the proxy host:port is reachable."""
    from urllib.parse import urlparse

    try:
        parts = urlparse(url if "://" in url else f"http://{url}")
        host, port = parts.hostname, parts.port or 80
        if not host:
            return False, None
        start = time.perf_counter()
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True, int((time.perf_counter() - start) * 1000)
    except Exception:
        return False, None


def _https_via_proxy_check(url: str, timeout: int = 15) -> tuple[bool, int | None]:
    """End-to-end check: real HTTPS GET to Instagram THROUGH the proxy.

    A proxy can accept TCP yet fail TLS/HTTP forwarding, so this is the
    verdict that counts. Any HTTP response below 500 proves the full path
    works (even a login/429 page means the proxy forwarded correctly).
    SOCKS proxies need the httpx socks extra — those keep their TCP verdict.
    """
    from urllib.parse import urlparse

    import httpx

    if urlparse(url).scheme.startswith("socks"):
        return True, None  # caller merges TCP latency

    start = time.perf_counter()
    try:
        with httpx.Client(
            proxy=url, trust_env=False, timeout=timeout, follow_redirects=True
        ) as client:
            resp = client.get(
                "https://www.instagram.com/",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
        ms = int((time.perf_counter() - start) * 1000)
        return (resp.status_code < 500), (ms if resp.status_code < 500 else None)
    except Exception as exc:
        log.info("Proxy end-to-end check failed: %s", exc)
        return False, None


def check_proxy_sync(proxy) -> tuple[bool, int | None]:
    """TCP pre-check + end-to-end HTTPS verification (Celery-safe).

    Returns (healthy, latency_ms) where latency is the end-to-end figure
    when available, else the TCP figure (SOCKS proxies).
    """
    from urllib.parse import urlparse

    url = proxy_url_for(proxy) or proxy.url
    ok, tcp_ms = _tcp_check(url)
    if not ok:
        log.info("Proxy %s unhealthy: TCP connect failed", proxy.id)
        return False, None
    if urlparse(url if "://" in url else f"http://{url}").scheme.startswith("socks"):
        return True, tcp_ms
    ok, e2e_ms = _https_via_proxy_check(url)
    if not ok:
        log.info("Proxy %s unhealthy: end-to-end Instagram check failed", proxy.id)
        return False, None
    return True, e2e_ms


async def check_proxy(proxy) -> tuple[bool, int | None]:
    """Async mirror of check_proxy_sync: TCP pre-check + end-to-end HTTPS."""
    import asyncio
    from urllib.parse import urlparse

    import httpx

    url = proxy_url_for(proxy) or proxy.url
    ok, tcp_ms = _tcp_check(url)
    if not ok:
        log.info("Proxy %s unhealthy: TCP connect failed", proxy.id)
        return False, None
    if urlparse(url if "://" in url else f"http://{url}").scheme.startswith("socks"):
        return True, tcp_ms
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            proxy=url, trust_env=False, timeout=15, follow_redirects=True
        ) as client:
            resp = await client.get(
                "https://www.instagram.com/",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
        ms = int((time.perf_counter() - start) * 1000)
        if resp.status_code >= 500:
            log.info("Proxy %s unhealthy: Instagram returned %s", proxy.id, resp.status_code)
            return False, None
        return True, ms
    except Exception as exc:
        log.info("Proxy %s unhealthy: %s", proxy.id, exc)
        return False, None
