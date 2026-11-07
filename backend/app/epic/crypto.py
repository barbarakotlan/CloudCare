"""Fernet encryption for Epic tokens at rest.

Generate a key with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Rotating EPIC_TOKEN_ENCRYPTION_KEY makes stored connections unreadable; those
patients simply reconnect MyChart.
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken


class TokenCryptoError(Exception):
    """The key is missing/invalid, or a stored value can't be decrypted with it."""


@lru_cache(maxsize=4)
def _fernet(key: str) -> Fernet:
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise TokenCryptoError("EPIC_TOKEN_ENCRYPTION_KEY is not a valid Fernet key") from exc


def validate_key(key: str) -> None:
    if not key:
        raise TokenCryptoError("EPIC_TOKEN_ENCRYPTION_KEY is not set")
    _fernet(key)


def encrypt(value: str, key: str) -> str:
    validate_key(key)
    return _fernet(key).encrypt(value.encode()).decode()


def decrypt(value: str, key: str) -> str:
    validate_key(key)
    try:
        return _fernet(key).decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise TokenCryptoError("Stored Epic token can't be decrypted with the current key") from exc


def encrypt_optional(value: str | None, key: str) -> str | None:
    return encrypt(value, key) if value else None


def decrypt_optional(value: str | None, key: str) -> str | None:
    return decrypt(value, key) if value else None
