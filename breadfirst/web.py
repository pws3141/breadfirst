from __future__ import annotations

import httpx

REPO_URL = "https://github.com/pws3141/breadfirst"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    f"(KHTML, like Gecko) Chrome/130 Safari/537.36 Breadfirst (+{REPO_URL})"
)


def get(url: str, *, headers: dict | None = None, params: dict | None = None) -> str:
    """GET a URL as text, retrying once on network errors or 5xx."""
    h = {"User-Agent": USER_AGENT, "Accept-Language": "de-DE,de;q=0.9"}
    h.update(headers or {})
    last_exc: Exception | None = None
    for _ in range(2):
        try:
            r = httpx.get(url, headers=h, params=params, timeout=20, follow_redirects=True)
            r.raise_for_status()
            return r.text
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500:
                raise
            last_exc = exc
        except httpx.TransportError as exc:
            last_exc = exc
    assert last_exc is not None
    raise last_exc
