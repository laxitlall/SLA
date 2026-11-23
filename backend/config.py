"""Central configuration, read once from environment variables.

The same .env files the original db.py loaded are still honoured
(database/atlas-credentials.env and backend/.env). Real environment variables
always win over values in those files.

Secure by default: ENVIRONMENT defaults to "production", which refuses to start
without a real JWT secret and a MongoDB URI, forbids wildcard CORS and never
seeds demo data.
"""

import logging
import os
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / "database" / "atlas-credentials.env")
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger("studyspot.config")

MIN_SECRET_LENGTH = 32
VALID_ENVIRONMENTS = {"development", "test", "production"}
DEV_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be an integer (got {raw!r}).") from None
    if value < minimum:
        raise RuntimeError(f"{name} must be >= {minimum} (got {value}).")
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_list(name: str) -> list[str]:
    return [item.strip() for item in _env(name).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    environment: str
    mongodb_uri: str
    mongodb_db_name: str
    jwt_secret_key: str
    jwt_issuer: str
    jwt_audience: str
    access_token_minutes: int
    refresh_token_days: int
    cors_origins: tuple[str, ...]
    allowed_email_domains: frozenset[str]
    max_failed_logins: int
    lockout_minutes: int
    rate_limit_auth_per_minute: int
    enable_docs: bool
    seed_demo_data: bool
    demo_user_password: str
    detection_image_dir: Path

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


def load_settings() -> Settings:
    environment = _env("ENVIRONMENT", "production").lower()
    if environment not in VALID_ENVIRONMENTS:
        raise RuntimeError(
            f"ENVIRONMENT must be one of {sorted(VALID_ENVIRONMENTS)} (got {environment!r})."
        )

    mongodb_uri = _env("MONGODB_URI")
    if not mongodb_uri or "<username>" in mongodb_uri or "<password>" in mongodb_uri:
        raise RuntimeError(
            "MONGODB_URI is not configured. Set it in backend/.env "
            "(e.g. mongodb://localhost:27017 or your Atlas mongodb+srv:// URI)."
        )

    secret = _env("JWT_SECRET_KEY")
    if not secret:
        if environment == "production":
            raise RuntimeError(
                "JWT_SECRET_KEY must be set. Generate one with: "
                'python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        secret = secrets.token_urlsafe(64)
        logger.warning(
            "JWT_SECRET_KEY is not set; using a random key for this process. "
            "All tokens become invalid on restart."
        )
    elif len(secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(f"JWT_SECRET_KEY must be at least {MIN_SECRET_LENGTH} characters.")

    cors_origins = _env_list("CORS_ORIGINS")
    if not cors_origins and environment != "production":
        cors_origins = list(DEV_CORS_ORIGINS)
    if environment == "production" and "*" in cors_origins:
        raise RuntimeError("CORS_ORIGINS must list explicit origins in production ('*' is not allowed).")

    demo_password = _env("DEMO_USER_PASSWORD")
    seed_demo = _env_bool("SEED_DEMO_DATA", False)
    if seed_demo and environment == "production":
        raise RuntimeError("SEED_DEMO_DATA must not be enabled when ENVIRONMENT=production.")

    return Settings(
        environment=environment,
        mongodb_uri=mongodb_uri,
        mongodb_db_name=_env("MONGODB_DB_NAME", "studyspot"),
        jwt_secret_key=secret,
        jwt_issuer=_env("JWT_ISSUER", "studyspot-iitb"),
        jwt_audience=_env("JWT_AUDIENCE", "studyspot-iitb-api"),
        access_token_minutes=_env_int("ACCESS_TOKEN_MINUTES", 15, minimum=1),
        refresh_token_days=_env_int("REFRESH_TOKEN_DAYS", 7, minimum=1),
        cors_origins=tuple(cors_origins),
        allowed_email_domains=frozenset(d.lower().lstrip("@") for d in _env_list("ALLOWED_EMAIL_DOMAINS")),
        max_failed_logins=_env_int("MAX_FAILED_LOGINS", 5, minimum=1),
        lockout_minutes=_env_int("LOCKOUT_MINUTES", 15, minimum=1),
        # 0 disables the limiter (used by the test-suite).
        rate_limit_auth_per_minute=_env_int("RATE_LIMIT_AUTH_PER_MINUTE", 20, minimum=0),
        enable_docs=_env_bool("ENABLE_DOCS", environment != "production"),
        seed_demo_data=seed_demo,
        demo_user_password=demo_password,
        detection_image_dir=Path(_env("DETECTION_IMAGE_DIR") or BASE_DIR / "detection_images").resolve(),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
