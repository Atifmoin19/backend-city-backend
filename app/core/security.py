"""Password hashing, JWT access tokens, and opaque refresh-token helpers."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings
from app.models.enums import Role

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


# Precomputed so failed logins for unknown emails take as long as real ones (no user enumeration)
DUMMY_PASSWORD_HASH = _hasher.hash("timing-equalizer-not-a-real-password")


def create_access_token(user_id: uuid.UUID, role: Role) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role.value,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "type"]},
        )
    except jwt.PyJWTError:
        return None
    return payload if payload.get("type") == "access" else None


def generate_opaque_token() -> str:
    """Random token given to the client. Only its hash is stored."""
    return secrets.token_urlsafe(48)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


ATTEMPT_TOKEN_TTL = timedelta(hours=2)

AttemptMode = Literal["practice", "checkpoint"]


@dataclass(frozen=True)
class AttemptClaims:
    game: str
    seed: int
    version_id: uuid.UUID  # the attempt keeps this version even if a newer one is published
    mode: AttemptMode


def create_attempt_token(
    game_slug: str, seed: int, version_id: uuid.UUID, mode: AttemptMode = "practice"
) -> str:
    """Signed variant claims so the client cannot pick a favorable seed, version or mode."""
    settings = get_settings()
    payload = {
        "type": "attempt",
        "game": game_slug,
        "seed": seed,
        "ver": str(version_id),
        "mode": mode,
        "exp": datetime.now(UTC) + ATTEMPT_TOKEN_TTL,
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), settings.jwt_algorithm)


def decode_attempt_token(token: str) -> AttemptClaims | None:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret.get_secret_value(), algorithms=[settings.jwt_algorithm]
        )
        if payload.get("type") != "attempt" or payload.get("mode") not in (
            "practice",
            "checkpoint",
        ):
            return None
        return AttemptClaims(
            game=str(payload["game"]),
            seed=int(payload["seed"]),
            version_id=uuid.UUID(str(payload["ver"])),
            mode=payload["mode"],
        )
    except (jwt.PyJWTError, KeyError, ValueError):
        return None  # includes tokens issued before versions/modes existed
