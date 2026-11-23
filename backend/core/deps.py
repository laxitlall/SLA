"""Reusable FastAPI dependencies for authentication and authorisation."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from core.security import TokenError, decode_token
from core.validators import normalize_roll
from database.db import db_instance, strip_internal

# auto_error=False so a missing header produces our own consistent 401 below.
# tokenUrl lets the Swagger "Authorize" button log in through /api/auth/token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def unauthorized(detail: str = "Could not validate credentials.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(token: Annotated[str | None, Depends(oauth2_scheme)]) -> dict:
    """Resolve the bearer access token to the (safe) user document.

    The user is re-read from MongoDB on every request, so deleted accounts and
    tokens issued before a password change / logout-all stop working immediately.
    """
    if not token:
        raise unauthorized("Not authenticated.")
    try:
        claims = decode_token(token, "access")
    except TokenError:
        raise unauthorized() from None

    user = await db_instance.get_user_auth(claims["sub"])
    if not user:
        raise unauthorized()
    if claims.get("tv") != user.get("token_version", 0):
        raise unauthorized("Session expired. Please log in again.")
    return strip_internal(user)


CurrentUser = Annotated[dict, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return user


AdminUser = Annotated[dict, Depends(require_admin)]


def normalize_roll_or_422(value: str) -> str:
    """Normalise a roll number taken from a URL path; malformed -> 422."""
    try:
        return normalize_roll(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid roll number format."
        ) from None


def ensure_self(current: dict, roll_number: str) -> str:
    """Require that `roll_number` is the authenticated user; returns it normalised.

    The original API trusted roll numbers sent by the client. They are still
    accepted (so existing clients keep working) but must now match the token.
    """
    roll = normalize_roll_or_422(roll_number)
    if roll != current["roll_number"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You can only perform this action for your own account."
        )
    return roll
