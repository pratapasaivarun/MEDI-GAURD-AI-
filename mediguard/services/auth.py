"""Authentication primitives kept independent from Streamlit and storage."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import sqlite3


def hash_password(password: str, salt: bytes | None = None) -> str:
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters.")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return "pbkdf2_sha256$310000$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        algorithm, rounds, salt_text, digest_text = (encoded or "").split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def require_role(user: dict | sqlite3.Row, *roles: str) -> None:
    role = user["role"] if user else None
    if role not in set(roles):
        raise PermissionError("You do not have permission to perform this action.")
