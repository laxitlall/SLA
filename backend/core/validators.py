"""Input validation helpers. Standard library only, so they are easy to unit-test."""

import re

# Roll numbers look like 26M0821. Be permissive about the exact shape but strict
# about the alphabet, so values are always safe to use in queries and logs.
ROLL_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{3,19}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128  # also caps the work an attacker can force the hasher to do


def normalize_roll(value: str) -> str:
    """Upper-case and validate a roll number. Raises ValueError if malformed."""
    roll = value.strip().upper()
    if not ROLL_RE.fullmatch(roll):
        raise ValueError("Invalid roll number format.")
    return roll


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 254 or not EMAIL_RE.fullmatch(email):
        raise ValueError("Enter a valid email address.")
    return email


def validate_password_strength(password: str, *, roll_number: str | None = None) -> str:
    """Enforce the password policy. Raises ValueError with a user-facing message."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Password must be at most {PASSWORD_MAX_LENGTH} characters long.")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one letter and one number.")
    if roll_number and roll_number.lower() in password.lower():
        raise ValueError("Password must not contain your roll number.")
    return password
