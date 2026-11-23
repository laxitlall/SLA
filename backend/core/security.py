"""Password hashing and JWT handling.

Passwords
    Argon2id via argon2-cffi. Hashes created by the original code (unsalted
    SHA-256, 64 hex characters) are still accepted at login and are transparently
    upgraded to Argon2id the first time the user signs in.

Tokens
    Short-lived access tokens and longer-lived refresh tokens, both signed JWTs
    (HS256). The algorithm is pinned on decode, and issuer, audience, expiry and
    token type are all enforced. Refresh tokens are additionally tracked in
    MongoDB so they can be rotated and revoked (see routers/auth.py).
"""

import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Literal

import jwt

from config import get_settings
from core.timeutils import utc_now

ALGORITHM = "HS256"
TokenType = Literal["access", "refresh"]

_LEGACY_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_CLAIMS = ["exp", "iat", "sub", "jti", "type", "iss", "aud"]
_CLOCK_SKEW_SECONDS = 10


class TokenError(Exception):
    """Raised for any invalid, expired or wrong-type token."""


# --------------------------------------------------------------------------- passwords
_hasher = None
_dummy_hash: str | None = None


def _get_hasher():
    # Imported lazily so the token helpers stay usable without argon2 installed.
    global _hasher
    if _hasher is None:
        from argon2 import PasswordHasher

        _hasher = PasswordHasher()  # Argon2id with argon2-cffi's RFC 9106 defaults
    return _hasher


def hash_password(password: str) -> str:
    return _get_hasher().hash(password)


def verify_password(password: str, stored_hash: str) -> tuple[bool, str | None]:
    """Check a password. Returns (is_valid, replacement_hash_or_None).

    A non-None replacement hash means the stored hash is legacy or uses outdated
    parameters and should be replaced with it. CPU-heavy: call it through
    run_in_threadpool from async code.
    """
    if not isinstance(stored_hash, str) or not stored_hash:
        return False, None

    if _LEGACY_SHA256_RE.fullmatch(stored_hash):
        legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
        if hmac.compare_digest(legacy, stored_hash):
            return True, hash_password(password)
        return False, None

    from argon2.exceptions import InvalidHashError, VerificationError

    hasher = _get_hasher()
    try:
        hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False, None
    if hasher.check_needs_rehash(stored_hash):
        return True, hash_password(password)
    return True, None


def get_dummy_hash() -> str:
    """A throw-away hash used to spend the same time on unknown users as on real ones."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password(secrets.token_urlsafe(16))
    return _dummy_hash


# --------------------------------------------------------------------------- tokens
def _encode(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, get_settings().jwt_secret_key, algorithm=ALGORITHM)


def _base_claims(roll_number: str, token_type: TokenType, expires_at: datetime, jti: str) -> dict[str, Any]:
    settings = get_settings()
    return {
        "sub": roll_number,
        "type": token_type,
        "jti": jti,
        "iat": utc_now(),
        "exp": expires_at,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }


def create_access_token(roll_number: str, token_version: int) -> tuple[str, int]:
    """Returns (token, lifetime_in_seconds). `tv` ties the token to the user's
    token_version so a password change / logout-all invalidates it instantly."""
    settings = get_settings()
    expires_at = utc_now() + timedelta(minutes=settings.access_token_minutes)
    claims = _base_claims(roll_number, "access", expires_at, uuid.uuid4().hex)
    claims["tv"] = token_version
    return _encode(claims), settings.access_token_minutes * 60


def create_refresh_token(roll_number: str) -> tuple[str, str, datetime]:
    """Returns (token, jti, expires_at)."""
    settings = get_settings()
    expires_at = utc_now() + timedelta(days=settings.refresh_token_days)
    jti = uuid.uuid4().hex
    return _encode(_base_claims(roll_number, "refresh", expires_at, jti)), jti, expires_at


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Validate signature, algorithm, issuer, audience, expiry and token type."""
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[ALGORITHM],  # pinned: rejects alg=none and algorithm confusion
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            leeway=_CLOCK_SKEW_SECONDS,
            options={"require": _REQUIRED_CLAIMS},
        )
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid or expired token.") from exc
    if claims.get("type") != expected_type:
        raise TokenError("Wrong token type.")
    if not isinstance(claims.get("sub"), str) or not isinstance(claims.get("jti"), str):
        raise TokenError("Malformed token.")
    return claims
