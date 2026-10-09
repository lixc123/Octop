"""Framework-free wxzt window binding and navigation helpers."""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import re
from urllib.parse import urlsplit


def strict_wxzt_origin(value: str) -> str:
    if not value or len(value) > 2048 or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        raise ValueError("invalid wxzt origin")
    if any(c in value for c in "\\?#%"):
        raise ValueError("invalid wxzt origin")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.path not in {"", "/"}
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("invalid wxzt origin")
    host = parsed.hostname
    port = parsed.port
    if not host or port == 0 or parsed.netloc.endswith(":"):
        raise ValueError("invalid wxzt origin")
    try:
        address = ipaddress.ip_address(host)
        host = f"[{address.compressed}]" if address.version == 6 else str(address)
    except ValueError:
        host = host.encode("idna").decode("ascii").lower()
        if len(host) > 253 or not all(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in host.split(".")
        ):
            raise ValueError("invalid wxzt origin") from None
    suffix = f":{port}" if port and port != (443 if parsed.scheme == "https" else 80) else ""
    return f"{parsed.scheme}://{host}{suffix}"


def credential_hash(value: str) -> str:
    return (
        base64.urlsafe_b64encode(hashlib.sha256(value.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
