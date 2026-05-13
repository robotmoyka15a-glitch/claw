"""Security helpers for claw.

1. CSRF protection via X-Claw-Token header.
2. .env encryption (optional, requires `cryptography` package).
3. Log sanitisation — masks tokens/keys in log records.
4. In-process token-bucket rate limiter per IP.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import re
import secrets
import time

from fastapi import HTTPException, Request, status


# ── 1. CSRF ──────────────────────────────────────────────────────────────────

_SESSION_TOKEN: str = secrets.token_hex(32)


def get_session_token() -> str:
    return _SESSION_TOKEN


def require_csrf(request: Request) -> None:
    """FastAPI dependency. Skip safe methods; validate X-Claw-Token on mutating ones."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    token = request.headers.get("X-Claw-Token", "")
    if not hmac.compare_digest(token, _SESSION_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid X-Claw-Token header",
        )


# ── 2. .env encryption ───────────────────────────────────────────────────────

_ENC_PREFIX = "enc:"


def _derive_key(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000, dklen=32)


def encrypt_value(plaintext: str, password: str) -> str:
    """Return enc:<base64(salt+nonce+tag+ct)> ready to store in .env."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        raise RuntimeError("pip install cryptography  to enable .env encryption") from None
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(password, salt)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    blob = salt + nonce + ct
    return _ENC_PREFIX + base64.b64encode(blob).decode()


def decrypt_value(stored: str, password: str) -> str:
    if not stored.startswith(_ENC_PREFIX):
        return stored
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        raise RuntimeError("pip install cryptography  to decrypt .env values") from None
    blob = base64.b64decode(stored[len(_ENC_PREFIX):])
    salt, nonce, ct = blob[:16], blob[16:28], blob[28:]
    return AESGCM(_derive_key(password, salt)).decrypt(nonce, ct, None).decode()


def decrypt_env_if_needed(value: str) -> str:
    """Transparently decrypt if CLAW_MASTER_PASSWORD is set."""
    if not value.startswith(_ENC_PREFIX):
        return value
    pw = os.environ.get("CLAW_MASTER_PASSWORD", "")
    if not pw:
        logging.getLogger("claw.security").warning(
            "Encrypted .env value found but CLAW_MASTER_PASSWORD not set — value ignored."
        )
        return ""
    return decrypt_value(value, pw)


# ── 3. Log sanitisation ───────────────────────────────────────────────────────

_SENSITIVE = [
    re.compile(r"(access_token=)[^\s&\"']+", re.I),
    re.compile(r"(token[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9_\-:\.]{12,}", re.I),
    re.compile(r"(key[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9_\-\.]{16,}", re.I),
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", re.I),
    re.compile(r"(sk-)[A-Za-z0-9]{8,}", re.I),
]


class SanitisedFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        for pat in _SENSITIVE:
            text = pat.sub(r"\g<1>***", text)
        return text


def install_sanitised_logging() -> None:
    fmt = SanitisedFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    for handler in logging.root.handlers:
        handler.setFormatter(fmt)


# ── 4. Token-bucket rate limiter ──────────────────────────────────────────────

class _Bucket:
    __slots__ = ("tokens", "last_ts")
    def __init__(self, cap: float) -> None:
        self.tokens = cap; self.last_ts = time.monotonic()


class RateLimiter:
    def __init__(self, rate: float = 30.0, burst: float = 60.0) -> None:
        self._rate = rate; self._burst = burst
        self._buckets: dict[str, _Bucket] = {}

    def _ip(self, r: Request) -> str:
        fwd = r.headers.get("x-forwarded-for")
        return fwd.split(",")[0].strip() if fwd else (r.client.host if r.client else "127.0.0.1")

    def check(self, request: Request) -> None:
        ip = self._ip(request)
        now = time.monotonic()
        b = self._buckets.setdefault(ip, _Bucket(self._burst))
        b.tokens = min(self._burst, b.tokens + (now - b.last_ts) * self._rate)
        b.last_ts = now
        if b.tokens < 1.0:
            raise HTTPException(status_code=429, detail="Too many requests")
        b.tokens -= 1.0


_limiter = RateLimiter()


def rate_limit(request: Request) -> None:
    """FastAPI dependency."""
    _limiter.check(request)
