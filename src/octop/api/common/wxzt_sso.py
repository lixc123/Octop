"""Server-to-server wxzt SSO exchange helpers.

The browser only carries a short-lived opaque ticket. Octop redeems it over a
configured backend URL using a deployment secret, then issues its normal JWT.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx


def wxzt_origin() -> str:
    return (os.environ.get("OCTOP_WXZT_ORIGIN") or "").strip().rstrip("/")


def exchange_url() -> str:
    configured = (os.environ.get("OCTOP_WXZT_SSO_EXCHANGE_URL") or "").strip()
    return configured or f"{wxzt_origin()}/api/octop/sso/exchange"


def shared_secret() -> str:
    return (os.environ.get("OCTOP_WXZT_SSO_SHARED_SECRET") or "").strip()


def allowed_return_url(value: str | None) -> str:
    """Return a wxzt AI Hub URL or the configured canonical fallback."""
    fallback = (os.environ.get("OCTOP_WXZT_DEFAULT_RETURN_URL") or "").strip()
    if not fallback and wxzt_origin():
        fallback = f"{wxzt_origin()}/ai_hub_layout"
    raw = (value or "").strip()
    if not raw:
        return fallback
    parsed = urlparse(raw)
    origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    if not parsed.scheme or not parsed.netloc or origin != wxzt_origin():
        return fallback
    if parsed.path != "/ai_hub_layout" or parsed.query or parsed.fragment:
        return fallback
    return raw


def allowed_logout_url(value: str | None = None) -> str:
    """Return only the configured wxzt logout endpoint for browser handoff."""
    fallback = f"{wxzt_origin()}/logout" if wxzt_origin() else ""
    raw = (value or "").strip()
    if not raw:
        return fallback
    parsed = urlparse(raw)
    origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    if (
        not parsed.scheme
        or not parsed.netloc
        or origin != wxzt_origin()
        or parsed.path != "/logout"
        or parsed.query
        or parsed.fragment
    ):
        return fallback
    return raw


async def redeem_ticket(code: str) -> dict[str, object]:
    secret = shared_secret()
    url = exchange_url()
    if not secret or not url.startswith(("http://", "https://")):
        raise ValueError("wxzt SSO is not configured")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=3.0)) as client:
            response = await client.post(
                url,
                headers={"X-Octop-SSO-Secret": secret},
                json={"code": code},
            )
    except httpx.HTTPError as exc:
        raise ValueError("wxzt SSO exchange unavailable") from exc
    if response.status_code >= 400:
        raise ValueError("invalid or expired wxzt SSO ticket")
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("invalid wxzt SSO response")
    return payload
