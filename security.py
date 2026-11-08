"""Password hashing (PBKDF2-SHA256, standard library only).

Stored format:  pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

ITERATIONS = 600_000
PREFIX = "pbkdf2_sha256"


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
    return f"{PREFIX}${iterations}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        prefix, iters, salt, expected = stored.strip().split("$")
        if prefix != PREFIX:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(digest.hex(), expected)
    except Exception:  # noqa: BLE001 - malformed hash => deny
        return False
