"""Production MFA, encryption, backup, and auth hardening; out of scope for the academic prototype."""
from __future__ import annotations

import base64
import hashlib
import os
import sqlite3
import tempfile
from pathlib import Path


def mfa_fernet():
    """Deferred encrypted-TOTP helper for a future production authentication layer."""
    from cryptography.fernet import Fernet
    secret = os.environ["MEDIGUARD_MFA_KEY"]
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest()))


def create_encrypted_backup(database_path: str | Path, destination: str | Path) -> Path:
    """Deferred encrypted-backup helper for a future production operations layer."""
    from cryptography.fernet import Fernet
    secret = os.environ["MEDIGUARD_BACKUP_KEY"]
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    destination = Path(destination).with_suffix(".enc")
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as temp:
        snapshot = Path(temp.name)
    try:
        source, target = sqlite3.connect(database_path), sqlite3.connect(snapshot)
        with target:
            source.backup(target)
        target.close()
        source.close()
        destination.write_bytes(Fernet(key).encrypt(snapshot.read_bytes()))
    finally:
        snapshot.unlink(missing_ok=True)
    return destination


def restore_encrypted_backup(source: str | Path, destination: str | Path) -> Path:
    """Deferred encrypted-backup restore helper for a future production operations layer."""
    from cryptography.fernet import Fernet
    secret = os.environ["MEDIGUARD_BACKUP_KEY"]
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    destination = Path(destination)
    destination.write_bytes(Fernet(key).decrypt(Path(source).read_bytes()))
    return destination
