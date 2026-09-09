import base64
import hashlib
import hmac
import json
import secrets
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from extraction import run_extraction
from rules import evaluate_claim
from agents import run_claim_workflow, warm_ollama
from policy_index import index_policy_documents
from extraction import extract_document
from policy_compare import compare_policy_text
from policy_terms import extract_policy_terms, terms_from_json
from reports import build_decision_report, build_appeal_letter

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
DB_PATH = Path(os.getenv("MEDIGUARD_DB_PATH", str(DATA_DIR / "mediguard.db"))).resolve()
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "ibm/granite4.1:8b")
MAX_PAGES = int(os.getenv("MAX_DOCUMENT_PAGES", "10"))
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "15"))
APP_ENV = os.getenv("APP_ENV", "development").lower()
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8505").rstrip("/")
MFA_ENCRYPTION_KEY = os.getenv("MEDIGUARD_MFA_KEY", os.getenv("MEDIGUARD_BACKUP_KEY", ""))
# Reserved for a future signed-token/session layer. It is intentionally not treated as active security yet.
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() == "true"
# Core-demo mode keeps the claim adjudication path usable without login.
# Set MEDIGUARD_CORE_DEMO=false later to restore login/MFA.
CORE_DEMO_MODE = os.getenv("MEDIGUARD_CORE_DEMO", "true").lower() == "true"
STORAGE_DIR = Path(os.getenv("MEDIGUARD_STORAGE_DIR", str(DATA_DIR))).resolve()
UPLOAD_DIR = STORAGE_DIR / "uploads"
ALLOWED_ROLES = {"claimant", "reviewer", "admin"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _hash_password(password: str, salt: bytes | None = None) -> str:
    if len(password) < 10:
        raise ValueError("Password must be at least 10 characters.")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return "pbkdf2_sha256$310000$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def _verify_password(password: str, encoded: str | None) -> bool:
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


def _claim_access(claim_id: str, user: dict | sqlite3.Row, write: bool = False) -> sqlite3.Row:
    with db() as conn:
        claim = conn.execute("SELECT * FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
    if claim is None:
        raise PermissionError("Claim not found.")
    role = user["role"]
    eligible_review_statuses = {"ready_for_review", "manual_review", "partially_approved", "rejected"}
    allowed = role == "admin" or claim["user_id"] == user["user_id"] or (role == "reviewer" and claim["assigned_reviewer_id"] == user["user_id"]) or (role == "reviewer" and claim["assigned_reviewer_id"] is None and claim["status"] in eligible_review_statuses)
    if write and role == "claimant" and claim["user_id"] != user["user_id"]:
        allowed = False
    if not allowed:
        raise PermissionError("You are not authorized to access this claim.")
    return claim


def authenticate_password(email: str, password: str) -> sqlite3.Row | None:
    with db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
    return user if user and user["is_active"] and _verify_password(password, user["password_hash"]) else None


def _mfa_fernet():
    encryption_key = os.getenv("MEDIGUARD_MFA_KEY") or os.getenv("MEDIGUARD_BACKUP_KEY") or MFA_ENCRYPTION_KEY
    if len(encryption_key) < 32:
        raise RuntimeError("MEDIGUARD_MFA_KEY or MEDIGUARD_BACKUP_KEY must be configured with at least 32 characters before MFA can be enabled.")
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(hashlib.sha256(encryption_key.encode("utf-8")).digest())
    return Fernet(key)


def authenticate_user(email: str, password: str, totp_code: str | None = None) -> sqlite3.Row | None:
    user = authenticate_password(email, password)
    if user is None:
        return None
    if user["mfa_enabled"]:
        if not totp_code or not verify_totp(user, totp_code):
            return None
    return user


def begin_totp_enrollment(user: dict | sqlite3.Row) -> dict[str, str]:
    if not user or not user["is_active"]:
        raise PermissionError("Active authentication is required to enable MFA.")
    import pyotp
    secret = pyotp.random_base32()
    encrypted = _mfa_fernet().encrypt(secret.encode("utf-8")).decode("ascii")
    with db() as conn:
        conn.execute("UPDATE users SET mfa_secret_encrypted=?, mfa_enabled=0 WHERE user_id=?", (encrypted, user["user_id"]))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), None, user["user_id"], "mfa_enrollment_started", json.dumps({"user_id": user["user_id"]}), utc_now()))
    uri = pyotp.TOTP(secret).provisioning_uri(name=user["email"], issuer_name="Medi Gaurd AI")
    return {"secret": secret, "otpauth_uri": uri}


def verify_totp(user: dict | sqlite3.Row, code: str) -> bool:
    if not user or not user["mfa_secret_encrypted"]:
        return False
    import pyotp
    try:
        secret = _mfa_fernet().decrypt(user["mfa_secret_encrypted"].encode("ascii")).decode("utf-8")
        return pyotp.TOTP(secret).verify(str(code).strip(), valid_window=1)
    except Exception:
        return False


def complete_totp_enrollment(user: dict | sqlite3.Row, code: str) -> sqlite3.Row:
    require_role(user, "claimant", "reviewer", "admin")
    current = get_user(user["user_id"])
    if not current or not verify_totp(current, code):
        raise ValueError("The MFA code is invalid or expired.")
    with db() as conn:
        conn.execute("UPDATE users SET mfa_enabled=1 WHERE user_id=?", (user["user_id"],))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), None, user["user_id"], "mfa_enabled", json.dumps({"user_id": user["user_id"]}), utc_now()))
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user["user_id"],)).fetchone()


def disable_totp(user: dict | sqlite3.Row) -> sqlite3.Row:
    current = get_user(user["user_id"])
    require_role(current, "claimant", "reviewer", "admin")
    with db() as conn:
        conn.execute("UPDATE users SET mfa_enabled=0, mfa_secret_encrypted=NULL WHERE user_id=?", (user["user_id"],))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), None, user["user_id"], "mfa_disabled", json.dumps({"user_id": user["user_id"]}), utc_now()))
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user["user_id"],)).fetchone()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_password_reset_request(email: str, expiry_hours: int = 1) -> dict[str, str | None]:
    email = email.strip().lower()
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires_at = (now + __import__("datetime").timedelta(hours=expiry_hours)).isoformat()
    with db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user is None or not user["is_active"]:
            # Keep the response non-disclosing. The local demo returns no token
            # for unknown/inactive accounts, while the UI shows one generic message.
            return {"email": email, "reset_token": None, "expires_at": None}
        conn.execute("UPDATE password_reset_tokens SET used_at=COALESCE(used_at, ?) WHERE user_id=? AND used_at IS NULL", (utc_now(), user["user_id"]))
        reset_id = str(uuid.uuid4())
        conn.execute("INSERT INTO password_reset_tokens(reset_id,user_id,token_hash,expires_at,used_at,created_at) VALUES(?,?,?,?,?,?)", (reset_id, user["user_id"], _token_hash(token), expires_at, None, utc_now()))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), None, user["user_id"], "password_reset_requested", json.dumps({"reset_id": reset_id, "expires_at": expires_at}), utc_now()))
    return {"email": email, "reset_token": token, "expires_at": expires_at}


def complete_password_reset(token: str, password: str) -> sqlite3.Row:
    if not token or len(token) < 20:
        raise ValueError("The password-reset token is invalid or incomplete.")
    password_hash = _hash_password(password)
    now = datetime.now(timezone.utc)
    with db() as conn:
        reset = conn.execute("SELECT * FROM password_reset_tokens WHERE token_hash=?", (_token_hash(token),)).fetchone()
        if reset is None or reset["used_at"] is not None:
            raise ValueError("The password-reset token is invalid or has already been used.")
        if datetime.fromisoformat(reset["expires_at"]) <= now:
            raise ValueError("The password-reset token has expired. Request a new reset link.")
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (reset["user_id"],)).fetchone()
        if user is None or not user["is_active"]:
            raise ValueError("The account is unavailable.")
        conn.execute("UPDATE users SET password_hash=?, password_set_at=? WHERE user_id=?", (password_hash, utc_now(), reset["user_id"]))
        conn.execute("UPDATE password_reset_tokens SET used_at=? WHERE reset_id=?", (utc_now(), reset["reset_id"]))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), None, reset["user_id"], "password_reset_completed", json.dumps({"reset_id": reset["reset_id"]}), utc_now()))
        return conn.execute("SELECT * FROM users WHERE user_id=?", (reset["user_id"],)).fetchone()


def create_reviewer_invitation(actor: dict | sqlite3.Row, email: str, display_name: str, expiry_hours: int = 24) -> dict[str, Any]:
    require_role(actor, "admin")
    email = email.strip().lower()
    if "@" not in email or not display_name.strip():
        raise ValueError("A valid reviewer email and display name are required.")
    user_id = hashlib.sha256(email.encode()).hexdigest()[:24]
    now = datetime.now(timezone.utc)
    expires_at = (now + __import__("datetime").timedelta(hours=expiry_hours)).isoformat()
    token = secrets.token_urlsafe(32)
    with db() as conn:
        conn.execute("INSERT INTO users(user_id,email,display_name,role,password_hash,is_active,password_set_at,disabled_at,created_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET display_name=excluded.display_name, role='reviewer', password_hash=NULL, is_active=0, password_set_at=NULL, disabled_at=NULL", (user_id, email, display_name.strip(), "reviewer", None, 0, None, None, utc_now()))
        conn.execute("UPDATE reviewer_invitations SET used_at=COALESCE(used_at, ?) WHERE user_id=? AND used_at IS NULL", (utc_now(), user_id))
        invitation_id = str(uuid.uuid4())
        conn.execute("INSERT INTO reviewer_invitations(invitation_id,user_id,token_hash,expires_at,used_at,created_by,created_at) VALUES(?,?,?,?,?,?,?)", (invitation_id, user_id, _token_hash(token), expires_at, None, actor["user_id"], utc_now()))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), None, actor["user_id"], "reviewer_invitation_created", json.dumps({"user_id": user_id, "email": email, "expires_at": expires_at}), utc_now()))
    return {"invitation_id": invitation_id, "user_id": user_id, "email": email, "expires_at": expires_at, "setup_token": token}


def complete_reviewer_setup(token: str, password: str) -> sqlite3.Row:
    if not token or len(token) < 20:
        raise ValueError("The setup token is invalid or incomplete.")
    password_hash = _hash_password(password)
    now = datetime.now(timezone.utc)
    with db() as conn:
        invitation = conn.execute("SELECT * FROM reviewer_invitations WHERE token_hash=?", (_token_hash(token),)).fetchone()
        if invitation is None or invitation["used_at"] is not None:
            raise ValueError("The setup token is invalid or has already been used.")
        if datetime.fromisoformat(invitation["expires_at"]) <= now:
            raise ValueError("The setup token has expired. Request a new invitation.")
        user = conn.execute("SELECT * FROM users WHERE user_id=?", (invitation["user_id"],)).fetchone()
        if user is None or user["role"] != "reviewer":
            raise ValueError("The reviewer account is unavailable.")
        conn.execute("UPDATE users SET password_hash=?, is_active=1, password_set_at=?, disabled_at=NULL WHERE user_id=?", (password_hash, utc_now(), invitation["user_id"]))
        conn.execute("UPDATE reviewer_invitations SET used_at=? WHERE invitation_id=?", (utc_now(), invitation["invitation_id"]))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), None, invitation["user_id"], "reviewer_account_activated", json.dumps({"invitation_id": invitation["invitation_id"]}), utc_now()))
        return conn.execute("SELECT * FROM users WHERE user_id=?", (invitation["user_id"],)).fetchone()


def provision_reviewer(actor: dict | sqlite3.Row, email: str, display_name: str) -> dict[str, Any]:
    return create_reviewer_invitation(actor, email, display_name)


def set_user_role(actor: dict | sqlite3.Row, user_id: str, role: str) -> sqlite3.Row:
    require_role(actor, "admin")
    if role not in ALLOWED_ROLES or role == "admin":
        raise ValueError("Only claimant and reviewer roles can be assigned here.")
    with db() as conn:
        conn.execute("UPDATE users SET role=? WHERE user_id=?", (role, user_id))
        updated = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if updated is None:
            raise ValueError("User not found.")
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), None, actor["user_id"], "user_role_changed", json.dumps({"user_id": user_id, "role": role}), utc_now()))
        return updated


def disable_user(actor: dict | sqlite3.Row, user_id: str) -> None:
    require_role(actor, "admin")
    with db() as conn:
        conn.execute("UPDATE users SET is_active=0, disabled_at=? WHERE user_id=?", (utc_now(), user_id))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), None, actor["user_id"], "user_disabled", json.dumps({"user_id": user_id}), utc_now()))


def register_user(email: str, display_name: str, password: str, role: str = "claimant") -> sqlite3.Row:
    email = email.strip().lower()
    if "@" not in email or not display_name.strip():
        raise ValueError("A valid email and display name are required.")
    if role not in ALLOWED_ROLES or role != "claimant":
        raise PermissionError("Self-registration is limited to claimant accounts.")
    password_hash = _hash_password(password)
    user_id = hashlib.sha256(email.encode()).hexdigest()[:24]
    with db() as conn:
        try:
            conn.execute("INSERT INTO users(user_id,email,display_name,role,password_hash,is_active,password_set_at,disabled_at,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (user_id, email, display_name.strip(), role, password_hash, 1, utc_now(), None, utc_now()))
        except sqlite3.IntegrityError as exc:
            raise ValueError("An account with this email already exists.") from exc
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def get_or_create_user(email: str, display_name: str) -> sqlite3.Row:
    user_id = hashlib.sha256(email.lower().encode()).hexdigest()[:24]
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO users(user_id,email,display_name,role,password_hash,created_at) VALUES(?,?,?,?,?,?)", (user_id, email.lower(), display_name.strip() or email.split("@")[0], "claimant", _hash_password(secrets.token_urlsafe(24)), utc_now()))
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def get_user(user_id: str) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def validate_security_config() -> None:
    # SESSION_SECRET is not validated here because the current Streamlit app does
    # not sign sessions or tokens. A future token implementation must add its own
    # fail-closed validation before this setting is used.
    if STORAGE_DIR == APP_DIR or any(part.lower() in {"public", "static"} for part in STORAGE_DIR.parts):
        raise RuntimeError("MEDIGUARD_STORAGE_DIR must be a private directory outside public/static paths.")
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def bootstrap_admin_from_env() -> None:
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or not password:
        return
    password_hash = _hash_password(password)
    user_id = hashlib.sha256(email.encode()).hexdigest()[:24]
    with db() as conn:
        conn.execute("INSERT INTO users(user_id,email,display_name,role,password_hash,created_at) VALUES(?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET role='admin', password_hash=excluded.password_hash", (user_id, email, "Medi Gaurd Administrator", "admin", password_hash, utc_now()))


def provision_user_role(actor: dict | sqlite3.Row, email: str, display_name: str, role: str) -> dict[str, Any]:
    require_role(actor, "admin")
    if role != "reviewer":
        raise ValueError("This setup flow provisions reviewer accounts only.")
    return create_reviewer_invitation(actor, email, display_name)


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'claimant',
                password_hash TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                password_set_at TEXT,
                disabled_at TEXT,
                mfa_enabled INTEGER NOT NULL DEFAULT 0,
                mfa_secret_encrypted TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                reset_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );
            CREATE TABLE IF NOT EXISTS reviewer_invitations (
                invitation_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );
            CREATE TABLE IF NOT EXISTS claims (
                claim_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                claim_number TEXT NOT NULL,
                patient_name TEXT NOT NULL,
                hospital_name TEXT,
                policy_number TEXT,
                incident_date TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                adjudication_context_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                original_name TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                document_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                page_count INTEGER,
                processing_status TEXT NOT NULL DEFAULT 'uploaded',
                extracted_json TEXT,
                extraction_error TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(claim_id) REFERENCES claims(claim_id)
            );
            CREATE TABLE IF NOT EXISTS policy_versions (
                version_id TEXT PRIMARY KEY,
                policy_number TEXT NOT NULL,
                version_label TEXT NOT NULL,
                insurer_name TEXT,
                effective_date TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                source_name TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                content_text TEXT NOT NULL,
                indexed_chunks INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                policy_terms_json TEXT
            );
            CREATE TABLE IF NOT EXISTS rule_evaluations (
                evaluation_id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                rule_version TEXT NOT NULL,
                status TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(claim_id) REFERENCES claims(claim_id)
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                claim_id TEXT,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reviewer_decisions (
                review_id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                reviewer_id TEXT NOT NULL,
                automated_status TEXT NOT NULL,
                final_status TEXT NOT NULL,
                comments TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(claim_id) REFERENCES claims(claim_id)
            );
            CREATE TABLE IF NOT EXISTS reviewer_field_edits (
                edit_id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                reviewer_id TEXT NOT NULL,
                field_name TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(claim_id) REFERENCES claims(claim_id)
            );
            CREATE TABLE IF NOT EXISTS evidence_confirmations (
                confirmation_id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                reviewer_id TEXT NOT NULL,
                field_name TEXT NOT NULL,
                document_id TEXT,
                page_number INTEGER,
                confirmed_at TEXT NOT NULL,
                FOREIGN KEY(claim_id) REFERENCES claims(claim_id)
            );
            """
        )
        # Lightweight migration for databases created by the foundation milestone.
        for column, definition in (("extracted_json", "TEXT"), ("extraction_error", "TEXT")):
            try:
                conn.execute(f"ALTER TABLE documents ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError:
                pass
        for column, definition in (("assigned_reviewer_id", "TEXT"), ("review_priority", "INTEGER NOT NULL DEFAULT 0"), ("adjudication_context_json", "TEXT")):
            try:
                conn.execute(f"ALTER TABLE claims ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError:
                pass
        for column, definition in (("password_hash", "TEXT"), ("is_active", "INTEGER NOT NULL DEFAULT 1"), ("password_set_at", "TEXT"), ("disabled_at", "TEXT"), ("mfa_enabled", "INTEGER NOT NULL DEFAULT 0"), ("mfa_secret_encrypted", "TEXT")):
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError:
                pass
        try:
            conn.execute("ALTER TABLE policy_versions ADD COLUMN policy_terms_json TEXT")
        except sqlite3.OperationalError:
            pass


def get_or_create_user(email: str, display_name: str) -> sqlite3.Row:
    user_id = hashlib.sha256(email.lower().encode()).hexdigest()[:24]
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(user_id,email,display_name,created_at) VALUES(?,?,?,?)",
            (user_id, email.lower(), display_name.strip() or email.split("@")[0], utc_now()),
        )
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def create_claim(user_id: str, claim_number: str, patient_name: str, hospital: str, policy: str, date: str) -> str:
    claim_id = str(uuid.uuid4())
    now = utc_now()
    with db() as conn:
        conn.execute(
            "INSERT INTO claims(claim_id,user_id,claim_number,patient_name,hospital_name,policy_number,incident_date,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (claim_id, user_id, claim_number, patient_name, hospital, policy, date, "draft", now, now),
        )
        conn.execute(
            "INSERT INTO audit_events VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), claim_id, user_id, "claim_created", "Claim registered", now),
        )
    return claim_id


def _validated_upload(uploaded_file) -> tuple[bytes, str]:
    original_name = Path(uploaded_file.name).name
    extension = Path(original_name).suffix.lower()
    if extension not in {".pdf", ".png", ".jpg", ".jpeg"}:
        raise ValueError("Unsupported file type. Upload a PDF, PNG, JPG, or JPEG file.")
    content = uploaded_file.getvalue()
    if len(content) > MAX_FILE_MB * 1024 * 1024:
        raise ValueError(f"File exceeds the {MAX_FILE_MB} MB limit.")
    if not content:
        raise ValueError("The uploaded file is empty.")
    if extension == ".pdf" and not content.startswith(b"%PDF"):
        raise ValueError("The file extension is PDF, but the file signature is invalid.")
    if extension in {".png"} and not content.startswith(b"\x89PNG"):
        raise ValueError("The file extension is PNG, but the file signature is invalid.")
    if extension in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8"):
        raise ValueError("The file extension is JPG/JPEG, but the file signature is invalid.")
    return content, original_name


def save_document(claim_id: str, user: dict | sqlite3.Row, uploaded_file, document_type: str) -> None:
    _claim_access(claim_id, user, write=True)
    user_id = user["user_id"]
    content, safe_name = _validated_upload(uploaded_file)
    document_id = str(uuid.uuid4())
    claim_dir = UPLOAD_DIR / claim_id
    claim_dir.mkdir(parents=True, exist_ok=True)
    safe_name = safe_name.replace(" ", "_")
    target = claim_dir / f"{document_id}_{safe_name}"
    target.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    with db() as conn:
        conn.execute(
            "INSERT INTO documents(document_id,claim_id,original_name,stored_path,document_type,size_bytes,sha256,page_count,processing_status,extracted_json,extraction_error,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (document_id, claim_id, uploaded_file.name, str(target), document_type, len(content), digest, None, "uploaded", None, None, utc_now()),
        )
        conn.execute("UPDATE claims SET updated_at=? WHERE claim_id=?", (utc_now(), claim_id))
        conn.execute(
            "INSERT INTO audit_events VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), claim_id, user_id, "document_uploaded", uploaded_file.name, utc_now()),
        )


def user_claims(user_id: str, user: dict | sqlite3.Row | None = None):
    with db() as conn:
        if user and user["role"] == "admin":
            return conn.execute("SELECT * FROM claims ORDER BY created_at DESC").fetchall()
        if user and user["role"] == "reviewer":
            return conn.execute("SELECT * FROM claims WHERE assigned_reviewer_id=? OR (assigned_reviewer_id IS NULL AND status IN ('ready_for_review','manual_review')) ORDER BY updated_at ASC", (user_id,)).fetchall()
        return conn.execute("SELECT * FROM claims WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()


def load_adjudication_context(claim_id: str, user: dict | sqlite3.Row) -> dict[str, Any]:
    claim = _claim_access(claim_id, user)
    try:
        payload = json.loads(claim["adjudication_context_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        payload = {}
    return payload if isinstance(payload, dict) else {}


def save_adjudication_context(claim_id: str, actor: dict | sqlite3.Row, context: dict[str, Any]) -> None:
    _claim_access(claim_id, actor, write=True)
    allowed = {"network_status", "preauthorization_status", "preauthorization_reference", "waiting_period_status", "source", "trusted", "aggregation_confirmed"}
    clean = {key: context.get(key) for key in allowed if key in context}
    if clean.get("network_status") not in {None, "in_network", "out_of_network", "unknown"}:
        raise ValueError("Invalid network status.")
    if clean.get("preauthorization_status") not in {None, "confirmed", "not_confirmed", "unknown"}:
        raise ValueError("Invalid pre-authorization status.")
    if clean.get("waiting_period_status") not in {None, "satisfied", "not_satisfied", "unknown"}:
        raise ValueError("Invalid waiting-period status.")
    if actor["role"] not in {"reviewer", "admin"}:
        clean["trusted"] = False
        clean["aggregation_confirmed"] = False
        clean["source"] = "claimant_asserted"
    elif clean.get("trusted") is True:
        clean["source"] = "reviewer_confirmed" if actor["role"] == "reviewer" else "admin_confirmed"
    with db() as conn:
        conn.execute("UPDATE claims SET adjudication_context_json=?, updated_at=? WHERE claim_id=?", (json.dumps(clean), utc_now(), claim_id))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, actor["user_id"], "adjudication_context_updated", json.dumps(clean), utc_now()))


def claim_documents(claim_id: str, user: dict | sqlite3.Row | None = None):
    if user is not None:
        _claim_access(claim_id, user)
    with db() as conn:
        return conn.execute("SELECT * FROM documents WHERE claim_id=? ORDER BY created_at", (claim_id,)).fetchall()


def _secure_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise RuntimeError("Unable to remove protected document storage.") from exc


def read_document_bytes(document_id: str, actor: dict | sqlite3.Row) -> tuple[bytes, str, str]:
    with db() as conn:
        document = conn.execute("SELECT * FROM documents WHERE document_id=?", (document_id,)).fetchone()
    if document is None:
        raise PermissionError("Document not found or unavailable.")
    path = secure_document_path(document, actor)
    return path.read_bytes(), document["original_name"], document["document_type"]


def delete_document(document_id: str, actor: dict | sqlite3.Row) -> None:
    require_role(actor, "admin")
    with db() as conn:
        document = conn.execute("SELECT * FROM documents WHERE document_id=?", (document_id,)).fetchone()
        if document is None:
            raise ValueError("Document not found.")
        path = secure_document_path(document, actor)
        _secure_unlink(path)
        conn.execute("DELETE FROM documents WHERE document_id=?", (document_id,))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), document["claim_id"], actor["user_id"], "document_deleted", json.dumps({"document_id": document_id, "original_name": document["original_name"]}), utc_now()))


def purge_expired_documents(actor: dict | sqlite3.Row, retention_days: int) -> int:
    require_role(actor, "admin")
    if retention_days < 1:
        raise ValueError("Retention must be at least one day.")
    cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(days=retention_days)
    with db() as conn:
        documents = conn.execute("SELECT * FROM documents WHERE created_at < ?", (cutoff.isoformat(),)).fetchall()
    for document in documents:
        delete_document(document["document_id"], actor)
    return len(documents)


def create_encrypted_backup(actor: dict | sqlite3.Row, destination: str | Path) -> Path:
    require_role(actor, "admin")
    backup_key = os.getenv("MEDIGUARD_BACKUP_KEY", "")
    if len(backup_key) < 32:
        raise RuntimeError("MEDIGUARD_BACKUP_KEY must be configured with at least 32 characters for encrypted backups.")
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError("Install cryptography before creating encrypted backups.") from exc
    key = base64.urlsafe_b64encode(hashlib.sha256(backup_key.encode("utf-8")).digest())
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix != ".enc":
        destination = destination.with_suffix(destination.suffix + ".enc")
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as temp:
        temp_path = Path(temp.name)
    try:
        source = sqlite3.connect(DB_PATH)
        target = sqlite3.connect(temp_path)
        with target:
            source.backup(target)
        target.close()
        source.close()
        encrypted = Fernet(key).encrypt(temp_path.read_bytes())
        destination.write_bytes(encrypted)
    finally:
        temp_path.unlink(missing_ok=True)
    with db() as conn:
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), None, actor["user_id"], "encrypted_backup_created", json.dumps({"destination": str(destination.name)}), utc_now()))
    return destination


def restore_encrypted_backup(actor: dict | sqlite3.Row, source: str | Path, destination: str | Path | None = None) -> Path:
    require_role(actor, "admin")
    backup_key = os.getenv("MEDIGUARD_BACKUP_KEY", "")
    if len(backup_key) < 32:
        raise RuntimeError("MEDIGUARD_BACKUP_KEY must be configured with at least 32 characters for encrypted backups.")
    from cryptography.fernet import Fernet, InvalidToken
    key = base64.urlsafe_b64encode(hashlib.sha256(backup_key.encode("utf-8")).digest())
    source = Path(source).resolve()
    destination = Path(destination or (source.with_suffix(".restored.sqlite"))).resolve()
    try:
        plaintext = Fernet(key).decrypt(source.read_bytes())
    except InvalidToken as exc:
        raise ValueError("Encrypted backup authentication failed.") from exc
    destination.write_bytes(plaintext)
    return destination


def reviewer_queue(user: dict | sqlite3.Row | None = None):
    if user is not None:
        require_role(user, "reviewer", "admin")
    with db() as conn:
        if user and user["role"] == "reviewer":
            return conn.execute("SELECT * FROM claims WHERE status IN ('ready_for_review','manual_review','partially_approved','rejected') AND (assigned_reviewer_id IS NULL OR assigned_reviewer_id=?) ORDER BY review_priority DESC, updated_at ASC", (user["user_id"],)).fetchall()
        return conn.execute("SELECT * FROM claims WHERE status IN ('ready_for_review','manual_review','partially_approved','rejected') ORDER BY review_priority DESC, updated_at ASC").fetchall()


def assign_claim(claim_id: str, reviewer_id: str, actor_id: str) -> None:
    reviewer = get_user(reviewer_id)
    actor = get_user(actor_id)
    require_role(reviewer, "reviewer", "admin")
    require_role(actor, "reviewer", "admin")
    claim = _claim_access(claim_id, actor)
    if actor["role"] == "reviewer" and (reviewer_id != actor_id or claim["assigned_reviewer_id"] not in (None, actor_id)):
        raise PermissionError("Only administrators may assign a claim to another reviewer.")
    if actor["role"] == "reviewer" and claim["assigned_reviewer_id"] is None and claim["status"] not in {"ready_for_review", "manual_review", "partially_approved", "rejected"}:
        raise PermissionError("Only eligible review claims can be self-claimed.")
    now = utc_now()
    with db() as conn:
        conn.execute("UPDATE claims SET assigned_reviewer_id=?, status=CASE WHEN status IN ('draft','extracted') THEN 'ready_for_review' ELSE status END, updated_at=? WHERE claim_id=?", (reviewer_id, now, claim_id))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, actor_id, "reviewer_assigned", json.dumps({"reviewer_id": reviewer_id}), now))


def save_claim_field_edits(claim_id: str, reviewer_id: str, edits: dict[str, Any]) -> None:
    reviewer = get_user(reviewer_id)
    require_role(reviewer, "reviewer", "admin")
    _claim_access(claim_id, reviewer, write=True)
    now = utc_now()
    allowed = {"patient_name", "hospital_name", "policy_number", "incident_date"}
    with db() as conn:
        for field_name, new_value in edits.items():
            if field_name not in allowed or str(new_value).strip() == "":
                continue
            old = conn.execute(f"SELECT {field_name} FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
            if old is None or str(old[field_name]) == str(new_value):
                continue
            conn.execute(f"UPDATE claims SET {field_name}=?, updated_at=? WHERE claim_id=?", (str(new_value).strip(), now, claim_id))
            conn.execute("INSERT INTO reviewer_field_edits VALUES (?,?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, reviewer_id, field_name, str(old[field_name] or ""), str(new_value).strip(), now))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, reviewer_id, "claim_fields_edited", json.dumps(edits), now))


def confirm_evidence(claim_id: str, reviewer_id: str, confirmations: list[dict[str, Any]]) -> None:
    reviewer = get_user(reviewer_id)
    require_role(reviewer, "reviewer", "admin")
    _claim_access(claim_id, reviewer, write=True)
    now = utc_now()
    with db() as conn:
        for item in confirmations:
            conn.execute("INSERT INTO evidence_confirmations VALUES (?,?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, reviewer_id, str(item.get("field_name", "")), item.get("document_id"), item.get("page_number"), now))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, reviewer_id, "evidence_confirmed", json.dumps(confirmations), now))


def reopen_claim(claim_id: str, reviewer_id: str, reason: str) -> None:
    reviewer = get_user(reviewer_id)
    require_role(reviewer, "reviewer", "admin")
    _claim_access(claim_id, reviewer, write=True)
    if not reason.strip():
        raise ValueError("A reason is required to reopen a claim.")
    now = utc_now()
    with db() as conn:
        conn.execute("UPDATE claims SET status='manual_review', updated_at=? WHERE claim_id=?", (now, claim_id))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, reviewer_id, "claim_reopened", reason.strip(), now))


def policy_versions():
    with db() as conn:
        return conn.execute("SELECT * FROM policy_versions ORDER BY policy_number, effective_date DESC, created_at DESC").fetchall()


def active_policy_versions():
    with db() as conn:
        return conn.execute("SELECT * FROM policy_versions WHERE status='active' ORDER BY policy_number, effective_date DESC").fetchall()


def ingest_policy_version(uploaded_file, policy_number: str, version_label: str, insurer: str, effective_date: str, user: dict | sqlite3.Row | None = None) -> dict:
    if user is not None:
        require_role(user, "admin")
    content, safe_name = _validated_upload(uploaded_file)
    version_id = str(uuid.uuid4())
    target_dir = STORAGE_DIR / "policies"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{version_id}_{safe_name.replace(' ', '_')}"
    target.write_bytes(content)
    evidence, raw_by_page, page_count = extract_document(target, version_id, uploaded_file.name)
    text = "\\n".join(item.text for item in evidence)
    payload = {"document_id": version_id, "source_name": uploaded_file.name, "text": text, "evidence": [item.to_dict() for item in evidence], "raw_by_page": raw_by_page}
    indexed = index_policy_documents([payload], version_id)
    extracted_terms = extract_policy_terms(evidence)
    with db() as conn:
        conn.execute("UPDATE policy_versions SET status='archived' WHERE policy_number=?", (policy_number.strip(),))
        conn.execute("INSERT INTO policy_versions(version_id,policy_number,version_label,insurer_name,effective_date,status,source_name,stored_path,content_text,indexed_chunks,created_at,policy_terms_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (version_id, policy_number.strip(), version_label.strip(), insurer.strip(), effective_date, "active", uploaded_file.name, str(target), text, indexed["chunks_indexed"], utc_now(), json.dumps(extracted_terms["terms_json"])))
    return {"version_id": version_id, "page_count": page_count, "policy_terms": extracted_terms, **indexed}


def archive_policy_version(version_id: str, user: dict | sqlite3.Row | None = None) -> None:
    if user is not None:
        require_role(user, "admin")
    with db() as conn:
        conn.execute("UPDATE policy_versions SET status='archived' WHERE version_id=?", (version_id,))


def process_claim_documents(claim_id: str, user_id: str) -> dict:
    user = get_user(user_id)
    _claim_access(claim_id, user, write=True)
    documents = claim_documents(claim_id, user)
    payloads = []
    for doc in documents:
        try:
            evidence, raw_by_page, page_count = _extract_one(doc)
            payloads.append({
                "document_id": doc["document_id"],
                "source_name": doc["original_name"],
                "document_type": doc["document_type"],
                "text": "\\n".join(item.text for item in evidence),
                "evidence": [item.to_dict() for item in evidence],
                "raw_by_page": raw_by_page,
            })
            with db() as conn:
                conn.execute("UPDATE documents SET page_count=?, processing_status=?, extracted_json=?, extraction_error=NULL WHERE document_id=?", (page_count, "extracted", json.dumps(payloads[-1]), doc["document_id"]))
        except Exception as exc:
            with db() as conn:
                conn.execute("UPDATE documents SET processing_status=?, extraction_error=? WHERE document_id=?", ("needs_review", str(exc), doc["document_id"]))
    normalized = run_extraction(payloads)
    # Quality gate: an extraction error or missing line-item structure must not
    # silently continue into financial adjudication.
    extraction_failures = len(documents) - len(payloads)
    if extraction_failures:
        normalized.setdefault("review_fields", []).append("document_extraction")
    bill_payloads = [payload for payload in payloads if payload.get("document_type") == "medical_bill"]
    if bill_payloads and normalized.get("total_amount") and not normalized.get("line_items"):
        normalized.setdefault("review_fields", []).append("line_items")
    policy_payloads = [payload for payload, doc in zip(payloads, documents) if doc["document_type"] == "policy"]
    if policy_payloads:
        policy_id = ((normalized.get("policy_number") or {}).get("value") or claim_id)
        try:
            normalized["policy_index"] = index_policy_documents(policy_payloads, str(policy_id))
            # Core MVP behavior: a policy uploaded with a claim is automatically
            # registered as the active edition for that matching policy number.
            # The advanced Policy Management page remains deferred.
            extracted_terms = extract_policy_terms([item for payload in policy_payloads for item in payload.get("evidence", [])])
            policy_number = str(((normalized.get("policy_number") or {}).get("value") or "")).strip()
            if policy_number:
                policy_text = "\\n".join(payload.get("text", "") for payload in policy_payloads)
                with db() as conn:
                    existing = conn.execute("SELECT version_id FROM policy_versions WHERE policy_number=? AND status='active' AND content_text=? LIMIT 1", (policy_number, policy_text)).fetchone()
                    if existing:
                        normalized["active_policy_version_id"] = existing["version_id"]
                    else:
                        conn.execute("UPDATE policy_versions SET status='archived' WHERE policy_number=?", (policy_number,))
                        version_id = str(uuid.uuid4())
                        conn.execute("INSERT INTO policy_versions(version_id,policy_number,version_label,insurer_name,effective_date,status,source_name,stored_path,content_text,indexed_chunks,created_at,policy_terms_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (version_id, policy_number, "Claim-uploaded policy", "Not specified", "", "active", policy_payloads[0].get("source_name", "policy"), "", policy_text, int(normalized["policy_index"].get("chunks_indexed", 0)), utc_now(), json.dumps(extracted_terms["terms_json"])))
                        normalized["active_policy_version_id"] = version_id
                normalized["policy_terms"] = extracted_terms
        except Exception as exc:
            normalized["policy_index_error"] = str(exc)
    with db() as conn:
        conn.execute("UPDATE claims SET status=?, updated_at=? WHERE claim_id=?", ("ready_for_review" if normalized["review_fields"] or normalized["missing_fields"] else "extracted", utc_now(), claim_id))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, user_id, "documents_extracted", json.dumps({"review_fields": normalized["review_fields"], "missing_fields": normalized["missing_fields"]}), utc_now()))
    return normalized


def secure_document_path(doc: sqlite3.Row, user: dict | sqlite3.Row) -> Path:
    _claim_access(doc["claim_id"], user)
    candidate = Path(doc["stored_path"]).resolve()
    try:
        candidate.relative_to(STORAGE_DIR)
    except ValueError as exc:
        raise PermissionError("Document path is outside the private storage root.") from exc
    if not candidate.is_file():
        raise FileNotFoundError("Stored document is unavailable.")
    return candidate


def _extract_one(doc):
    from extraction import extract_document
    candidate = Path(doc["stored_path"]).resolve()
    try:
        candidate.relative_to(STORAGE_DIR)
    except ValueError as exc:
        raise PermissionError("Document path is outside the private storage root.") from exc
    return extract_document(candidate, doc["document_id"], doc["original_name"])


def _derived_claim_context(claim_id: str, user_id: str, normalized: dict) -> dict[str, Any]:
    user = get_user(user_id)
    context = load_adjudication_context(claim_id, user)
    line_items = normalized.get("line_items") or []
    room_items = [item for item in line_items if item.get("category") == "room"]
    non_room_total = sum(float(item.get("amount", 0) or 0) for item in line_items if item.get("category") != "room")
    if room_items:
        context.setdefault("room_charge", sum(float(item.get("amount", 0) or 0) for item in room_items))
        admission = (normalized.get("admission_date") or {}).get("value")
        discharge = (normalized.get("discharge_date") or {}).get("value")
        if admission and discharge:
            try:
                start = datetime.fromisoformat(str(admission))
                end = datetime.fromisoformat(str(discharge))
                context.setdefault("room_days", max(1, (end - start).days + 1))
            except ValueError:
                pass
        if non_room_total > 0:
            context.setdefault("room_linked_charges", non_room_total)
    context["duplicate_suspected"] = bool(normalized.get("duplicate_candidates"))
    context["multiple_bills"] = int(normalized.get("multiple_bill_count") or 0) > 1
    context["aggregation_confirmed"] = bool(context.get("aggregation_confirmed"))
    context["diagnosis"] = ((normalized.get("diagnosis") or {}).get("value") or context.get("diagnosis", ""))
    context["in_network"] = True if context.get("network_status") == "in_network" and context.get("trusted") else False if context.get("network_status") == "out_of_network" and context.get("trusted") else None
    context["preauthorization_obtained"] = True if context.get("preauthorization_status") == "confirmed" and context.get("trusted") else False if context.get("preauthorization_status") == "not_confirmed" and context.get("trusted") else None
    context["waiting_period_satisfied"] = True if context.get("waiting_period_status") == "satisfied" and context.get("trusted") else False if context.get("waiting_period_status") == "not_satisfied" and context.get("trusted") else None
    return context


def _reconcile_result(result: dict[str, Any], billed_amount: Any) -> dict[str, Any]:
    """Fail closed when the persisted financial result does not reconcile."""
    billed = float(billed_amount or 0)
    covered = float(result.get("covered_amount", 0) or 0)
    deductible = float(result.get("deductible", 0) or 0)
    copayment = float(result.get("copayment", 0) or 0)
    payable = float(result.get("payable_amount", 0) or 0)
    expected = max(0.0, round(covered - deductible - copayment, 2))
    errors = []
    if billed < 0 or covered < 0 or deductible < 0 or copayment < 0 or payable < 0:
        errors.append("Negative financial amount detected.")
    if covered > billed + 0.01:
        errors.append("Covered amount exceeds billed amount.")
    if deductible > covered + 0.01 or copayment > max(0.0, covered - deductible) + 0.01:
        errors.append("Deductible or copayment exceeds the eligible amount.")
    if abs(payable - expected) > 0.01:
        errors.append("Payable amount does not reconcile with covered amount, deductible, and copayment.")
    result["claimant_responsibility"] = round(max(0.0, billed - payable), 2)
    result["claimant_result"] = {"amount_billed": round(billed, 2), "amount_covered": round(payable, 2), "amount_claimant_pays": round(max(0.0, billed - payable), 2), "status": result.get("status", "manual_review"), "reason": (result.get("warnings") or ["See reviewer analysis."])[0]}
    if errors:
        result["status"] = "manual_review"
        result.setdefault("warnings", []).extend(["calculation_reconciliation_failed", *errors])
    result["claimant_result"]["status"] = result.get("status", "manual_review")
    return result


def _policy_mismatch(claim_id: str, normalized: dict) -> tuple[str | None, str | None]:
    with db() as conn:
        claim = conn.execute("SELECT policy_number FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
    claim_number = str(claim["policy_number"]).strip() if claim and claim["policy_number"] else None
    extracted_number = ((normalized.get("policy_number") or {}).get("value"))
    extracted_number = str(extracted_number).strip() if extracted_number else None
    if claim_number and extracted_number and claim_number.casefold() != extracted_number.casefold():
        return None, f"Claim policy number {claim_number} does not match extracted policy number {extracted_number}."
    return extracted_number or claim_number, None


def evaluate_saved_claim(claim_id: str, user_id: str, normalized: dict) -> dict:
    user = get_user(user_id)
    _claim_access(claim_id, user, write=True)
    total = (normalized.get("total_amount") or {}).get("value")
    policy_number, mismatch = _policy_mismatch(claim_id, normalized)
    if mismatch:
        result = {"status": "manual_review", "rule_version": "policy-match-required", "results": [], "covered_amount": 0.0, "deductible": 0.0, "copayment": 0.0, "payable_amount": 0.0, "warnings": [mismatch], "policy_terms_missing": ["matching_policy"], "policy_terms": {}}
        result["policy_source"] = "none"
        result = _reconcile_result(result, total)
        with db() as conn:
            conn.execute("INSERT INTO rule_evaluations VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, result["rule_version"], result["status"], json.dumps(result), utc_now()))
            conn.execute("UPDATE claims SET status=?, updated_at=? WHERE claim_id=?", (result["status"], utc_now(), claim_id))
        return result
    active_policy = active_policy_for_claim(claim_id, normalized)
    if active_policy and active_policy["policy_terms_json"]:
        terms_payload = json.loads(active_policy["policy_terms_json"])
        terms, missing_terms, confidence = terms_from_json(terms_payload)
        terms.source = terms_payload
        if missing_terms:
            result = {"status": "manual_review", "rule_version": "policy-terms-required", "results": [], "covered_amount": 0.0, "deductible": 0.0, "copayment": 0.0, "payable_amount": 0.0, "warnings": ["Required policy terms missing: " + ", ".join(missing_terms)], "policy_terms_missing": missing_terms, "policy_terms": terms_payload}
        else:
            # Do not pass the newer keyword here: this keeps the Streamlit app
            # compatible with an already-running process that has an older rules.py.
            result = evaluate_claim(total, terms=terms, review_fields=normalized.get("review_fields"), missing_fields=normalized.get("missing_fields"), claim_context=_derived_claim_context(claim_id, user_id, normalized))
        result["policy_terms_confidence"] = confidence
    else:
        result = {"status": "manual_review", "rule_version": "policy-terms-required", "results": [], "covered_amount": 0.0, "deductible": 0.0, "copayment": 0.0, "payable_amount": 0.0, "warnings": ["No active policy terms are available. Ingest a policy edition in Policy management first."], "policy_terms_missing": ["active_policy_terms"], "policy_terms": {}}
    result["policy_source"] = f"{active_policy['policy_number']} — {active_policy['version_label']}" if active_policy else "none"
    result = _reconcile_result(result, total)
    with db() as conn:
        conn.execute("INSERT INTO rule_evaluations VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, result["rule_version"], result["status"], json.dumps(result), utc_now()))
        conn.execute("UPDATE claims SET status=?, updated_at=? WHERE claim_id=?", (result["status"], utc_now(), claim_id))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, user_id, "rules_evaluated", json.dumps(result), utc_now()))
    return result


def saved_policy_text(claim_id: str) -> str:
    text_parts = []
    for doc in claim_documents(claim_id):
        if doc["document_type"] != "policy" or not doc["extracted_json"]:
            continue
        try:
            payload = json.loads(doc["extracted_json"])
            text_parts.append(payload.get("text", ""))
        except json.JSONDecodeError:
            continue
    return "\\n".join(text_parts)


def active_policy_for_claim(claim_id: str, normalized: dict) -> sqlite3.Row | None:
    with db() as conn:
        claim = conn.execute("SELECT policy_number FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
        claim_policy_number = claim["policy_number"] if claim else None
        extracted_policy_number = ((normalized.get("policy_number") or {}).get("value"))
        policy_number = extracted_policy_number or claim_policy_number
        if policy_number:
            row = conn.execute("SELECT * FROM policy_versions WHERE policy_number=? AND status='active' ORDER BY effective_date DESC, created_at DESC LIMIT 1", (str(policy_number),)).fetchone()
            if row:
                return row
        return None


def run_agents_for_claim(claim_id: str, user_id: str, normalized: dict, rules: dict, progress_callback=None) -> dict:
    user = get_user(user_id)
    _claim_access(claim_id, user, write=True)
    active_policy = active_policy_for_claim(claim_id, normalized)
    if active_policy:
        policy_text = active_policy["content_text"]
        policy_id = active_policy["version_id"]
        policy_source = f"{active_policy['policy_number']} — {active_policy['version_label']}"
    else:
        policy_text = saved_policy_text(claim_id)
        policy_id = str(((normalized.get("policy_number") or {}).get("value")) or claim_id)
        policy_source = "claim-uploaded policy"
    if not policy_text.strip():
        raise ValueError("No usable policy evidence found. Ingest an active edition in Policy management or upload and extract a policy document in Claim review.")
    if not st.session_state.get("ollama_warmed"):
        warm_ollama()
        st.session_state["ollama_warmed"] = True
    workflow = run_claim_workflow(normalized, policy_text, rules, policy_id=policy_id, progress_callback=progress_callback)
    workflow["policy_source"] = policy_source
    decision = workflow.get("decision", {})
    with db() as conn:
        conn.execute("UPDATE claims SET status=?, updated_at=? WHERE claim_id=?", (decision.get("status", "manual_review"), utc_now(), claim_id))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, user_id, "agents_completed", json.dumps({"llm_calls": workflow.get("llm_calls", 0), "decision": decision}), utc_now()))
    return workflow


def save_reviewer_decision(claim_id: str, reviewer_id: str, automated_status: str, final_status: str, comments: str) -> None:
    reviewer = get_user(reviewer_id)
    require_role(reviewer, "reviewer", "admin")
    _claim_access(claim_id, reviewer, write=True)
    if final_status not in {"approved", "partially_approved", "rejected", "manual_review"}:
        raise ValueError("Invalid reviewer decision status.")
    now = utc_now()
    with db() as conn:
        conn.execute("INSERT INTO reviewer_decisions VALUES (?,?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, reviewer_id, automated_status, final_status, comments.strip(), now))
        conn.execute("UPDATE claims SET status=?, updated_at=? WHERE claim_id=?", (final_status, now, claim_id))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, reviewer_id, "reviewer_decision", json.dumps({"automated_status": automated_status, "final_status": final_status, "comments": comments.strip()}), now))


def latest_reviewer_decision(claim_id: str):
    with db() as conn:
        return conn.execute("SELECT * FROM reviewer_decisions WHERE claim_id=? ORDER BY created_at DESC LIMIT 1", (claim_id,)).fetchone()


def ollama_status() -> tuple[bool, str]:
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        if response.ok:
            models = [m.get("name") for m in response.json().get("models", [])]
            if OLLAMA_MODEL in models:
                return True, f"Connected — {OLLAMA_MODEL} available"
            return True, f"Connected — configured model not found locally ({OLLAMA_MODEL})"
        return False, f"Ollama returned HTTP {response.status_code}"
    except requests.RequestException as exc:
        return False, f"Ollama unavailable: {exc}"


def _status_badge(status: str) -> str:
    return status.replace('_', ' ').title()



def _status_badge(status: str) -> str:
    return status.replace('_', ' ').title()


def _status_color(status: str) -> str:
    return {
        'approved': '#168a57', 'partially_approved': '#b77908',
        'manual_review': '#b77908', 'rejected': '#c23b3b',
        'ready_for_review': '#b77908', 'extracted': '#2f6fb0',
        'draft': '#667085',
    }.get(status, '#667085')


def _brand_header() -> None:
    st.markdown('''
    <div class="mg-brand-head">
      <div class="mg-shield">✚</div>
      <div><div class="mg-brand-name">Medi Gaurd AI</div>
      <div class="mg-brand-sub">AI-Powered Medical Insurance Claim Adjudication</div></div>
    </div>''', unsafe_allow_html=True)


def _core_demo_user() -> dict[str, Any]:
    """Create or load a local admin-shaped actor for the temporary core demo."""
    demo_email = "demo@mediguard.local"
    demo_id = hashlib.sha256(demo_email.encode("utf-8")).hexdigest()[:24]
    with db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(user_id,email,display_name,role,is_active,created_at) VALUES(?,?,?,?,?,?)",
            (demo_id, demo_email, "Demo Reviewer", "admin", 1, utc_now()),
        )
        conn.execute("UPDATE users SET display_name=?, role='admin', is_active=1 WHERE user_id=?", ("Demo Reviewer", demo_id))
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (demo_id,)).fetchone()
    return dict(row)


def _render_login() -> None:
    left, right = st.columns([1.05, 1.35], gap='large')
    with left:
        st.markdown('''<div class="mg-landing">
        <div class="mg-shield large">✚</div><h1>Medi Gaurd AI</h1>
        <p class="mg-tagline">AI-Powered Medical Insurance<br/>Claim Adjudication</p>
        <p class="mg-promise">Faster. Transparent. Accurate.</p>
        <div class="mg-illustration">▣<br/><span>✓  ✓  ✓</span><br/>▱  🛡</div>
        </div>''', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="mg-auth-title">Welcome back</div><div class="mg-auth-copy">Sign in to continue to your account</div>', unsafe_allow_html=True)
        login_tab, register_tab, reset_tab = st.tabs(['Sign in', 'Create account', 'Reset password'])
        with login_tab:
            with st.form('login'):
                email = st.text_input('Email', placeholder='you@example.com')
                password = st.text_input('Password', type='password')
                st.checkbox('Remember me', value=True)
                submitted = st.form_submit_button('Sign in', type='primary', use_container_width=True)
            if submitted:
                user_row = authenticate_password(email, password)
                if user_row is None:
                    st.error("That email or password doesn't match our records.")
                elif user_row['mfa_enabled']:
                    st.session_state.pending_mfa_user = {'user_id': user_row['user_id']}
                    st.rerun()
                else:
                    st.session_state.user = dict(user_row)
                    st.session_state.page = 'Dashboard'
                    st.rerun()
        with register_tab:
            with st.form('register'):
                name = st.text_input('Full name')
                email = st.text_input('Email', key='reg_email')
                p1 = st.text_input('Password', type='password')
                p2 = st.text_input('Confirm password', type='password')
                st.caption('Use at least 10 characters. New self-registered accounts are Claimants.')
                submitted = st.form_submit_button('Create account', type='primary', use_container_width=True)
            if submitted:
                try:
                    if p1 != p2: raise ValueError('Passwords do not match.')
                    st.session_state.user = dict(register_user(email, name, p1))
                    st.session_state.page = 'Dashboard'; st.rerun()
                except (ValueError, PermissionError) as exc: st.error(str(exc))
        with reset_tab:
            st.caption('For privacy, this response does not reveal whether an email exists.')
            with st.form('reset_request'):
                email = st.text_input('Account email', key='reset_email')
                submitted = st.form_submit_button('Send reset link', type='primary', use_container_width=True)
            if submitted:
                request = create_password_reset_request(email)
                st.success('If an active account exists, reset instructions have been generated.')
                if request['reset_token']: st.code(f"{APP_BASE_URL}/?reset_token={request['reset_token']}")


def _render_sidebar(user: dict) -> str:
    with st.sidebar:
        _brand_header()
        st.markdown('<div class="mg-nav-label">WORKSPACE</div>', unsafe_allow_html=True)
        # Core MVP navigation: advanced policy administration and admin pages
        # remain in the source but are intentionally hidden until later.
        pages = ['Dashboard', 'Register claim', 'Claim review', 'Claim result']
        current = st.session_state.get('page', 'Dashboard')
        if current not in pages: current = 'Dashboard'
        page = st.radio('Workspace', pages, index=pages.index(current), format_func=lambda x: {'Dashboard':'▦  Dashboard','Register claim':'＋  Register Claim','Claim review':'▤  Claim Review','Claim result':'✓  Claim Result','Policy management':'◈  Policy Management','Admin panel':'♙  Admin Panel'}.get(x,x), label_visibility='collapsed')
        st.markdown('<div class="mg-sidebar-spacer"></div>', unsafe_allow_html=True)
        st.markdown('<div class="mg-nav-label">ACCOUNT</div>', unsafe_allow_html=True)
        st.caption(f"Signed in as {user['display_name']}")
        st.caption(f"Role: {user['role'].title()}")
        if st.button('↪  Sign out', use_container_width=True):
            st.session_state.clear(); st.rerun()
        st.markdown('<div class="mg-sidebar-foot">Final determination must be confirmed by an authorized reviewer.</div>', unsafe_allow_html=True)
    st.session_state.page = page
    return page


def _claimant_result_for_claim(claim_id: str, user: dict) -> dict[str, Any] | None:
    """Return only claimant-safe amounts and explanation; hide raw agent/reviewer data."""
    rules = st.session_state.get(f"rules_{claim_id}")
    workflow = st.session_state.get(f"workflow_{claim_id}") or {}
    if not rules:
        with db() as conn:
            row = conn.execute("SELECT result_json FROM rule_evaluations WHERE claim_id=? ORDER BY created_at DESC LIMIT 1", (claim_id,)).fetchone()
        if row:
            try:
                rules = json.loads(row["result_json"])
            except (TypeError, json.JSONDecodeError):
                rules = None
    if not rules and not workflow:
        return None
    decision = workflow.get("decision") or {}
    status = decision.get("status") or ((rules or {}).get("status", "manual_review"))
    claimant = (rules or {}).get("claimant_result") or {}
    billed = float(claimant.get("amount_billed", 0) or 0)
    covered = float(claimant.get("amount_covered", (rules or {}).get("payable_amount", 0)) or 0)
    responsibility = float(claimant.get("amount_claimant_pays", max(0, billed - covered)) or 0)
    reasons = decision.get("reasons") or (rules or {}).get("warnings") or []
    reason = str(reasons[0]) if reasons else "Your claim has been processed and the result is ready to review."
    return {"status": status, "amount_billed": billed, "amount_covered": covered, "amount_claimant_pays": responsibility, "reason": reason, "requires_human_review": status == "manual_review", "rules": rules or {}}


def _render_claimant_result(user: dict) -> None:
    claims = user_claims(user["user_id"], user)
    st.markdown('<div class="mg-eyebrow">CLAIMS / RESULT</div><h1>Your Claim Result</h1><p class="mg-subtitle">A simple summary of what the policy review found.</p>', unsafe_allow_html=True)
    if not claims:
        st.info("You do not have a claim yet.")
        if st.button("Register a claim", type="primary"):
            st.session_state.page = "Register claim"; st.rerun()
        return
    options = {f"{c['claim_number']} · {c['patient_name']}": c['claim_id'] for c in claims}
    default = next((i for i, value in enumerate(options.values()) if value == st.session_state.get("active_claim")), 0)
    selected = st.selectbox("Choose a claim", list(options), index=default, key="claimant_result_selector")
    claim_id = options[selected]
    st.session_state.active_claim = claim_id
    claim = next(c for c in claims if c["claim_id"] == claim_id)
    result = _claimant_result_for_claim(claim_id, user)
    st.markdown(f"<div class='mg-context'><b>{claim['claim_number']}</b> · {claim['patient_name']} · {claim['policy_number'] or 'Policy number pending'} <span class='mg-pill' style='color:{_status_color((result or {}).get('status', claim['status']))}'>{_status_badge((result or {}).get('status', claim['status']))}</span></div>", unsafe_allow_html=True)
    if not result:
        st.info("Your documents have not been analyzed yet.")
        if st.button("Continue claim review", type="primary"):
            st.session_state.page = "Claim review"; st.rerun()
        return
    status = result["status"]
    if status == "manual_review":
        st.warning("Your claim is under review. Some information must be confirmed before a final result can be issued.")
    elif status == "approved":
        st.success("Your claim has been approved based on the current policy information.")
    elif status == "partially_approved":
        st.warning("Your claim is partially covered. Some charges were limited or excluded under the policy.")
    elif status == "rejected":
        st.error("Your claim is not covered under the current policy result.")
    a, b, c = st.columns(3)
    with a: st.metric("Amount billed", f"INR {result['amount_billed']:,.2f}")
    with b: st.metric("Insurance covers", f"INR {result['amount_covered']:,.2f}")
    with c: st.metric("You may pay", f"INR {result['amount_claimant_pays']:,.2f}")
    with st.container(border=True):
        st.markdown("### What this means")
        st.write(result["reason"])
        if result["requires_human_review"]:
            st.caption("This is not a final determination. An authorized reviewer must confirm the result.")
        else:
            st.caption("This is decision-support information. Final determination should be confirmed by an authorized reviewer.")
    rules = result.get("rules", {})
    with st.expander("View amount details"):
        st.write(f"Covered amount before deductions: INR {float(rules.get('covered_amount', 0) or 0):,.2f}")
        st.write(f"Deductible: INR {float(rules.get('deductible', 0) or 0):,.2f}")
        st.write(f"Copayment: INR {float(rules.get('copayment', 0) or 0):,.2f}")
        warnings = rules.get("warnings") or []
        if warnings:
            st.write("Policy notes: " + "; ".join(str(item) for item in warnings))
    if st.button("Back to dashboard"):
        st.session_state.page = "Dashboard"; st.rerun()


def _render_dashboard(user: dict) -> None:
    claims = user_claims(user['user_id'], user)
    review_count = sum(1 for c in claims if c['status'] in {'manual_review','ready_for_review','partially_approved'})
    approved = sum(1 for c in claims if c['status'] == 'approved')
    st.markdown(f'<div class="mg-eyebrow">DASHBOARD</div><h1>Welcome back, {user["display_name"]}!</h1><p class="mg-subtitle">Here’s what’s happening with your claims.</p>', unsafe_allow_html=True)
    a,b,c = st.columns(3)
    with a: st.metric('Total Claims', len(claims))
    with b: st.metric('Needing Action', review_count)
    with c: st.metric('Approved Claims', approved)
    with st.container(border=True):
        st.markdown('<div class="mg-section-title">Your Claims</div>', unsafe_allow_html=True)
        if not claims:
            st.info("You haven't registered a claim yet. Register your first claim to get started.")
            if st.button('Register a claim', type='primary'): st.session_state.page = 'Register claim'; st.rerun()
        else:
            cols = st.columns(2)
            for i, claim in enumerate(claims[:8]):
                with cols[i % 2]:
                    with st.container(border=True):
                        st.markdown(f"**{claim['claim_number']}**  <span class='mg-pill' style='color:{_status_color(claim['status'])}'>{_status_badge(claim['status'])}</span>", unsafe_allow_html=True)
                        st.caption(f"{claim['patient_name']} · {claim['hospital_name'] or 'Provider not entered'}")
                        x,y = st.columns([3,1])
                        claim_total = claim['total_amount'] if 'total_amount' in claim.keys() else None
                        x.write(f"INR {float(claim_total or 0):,.2f}" if claim_total else 'Amount pending')
                        if y.button('Open', key=f"open_{claim['claim_id']}"):
                            st.session_state.active_claim = claim['claim_id']; st.session_state.page = 'Claim review'; st.rerun()
    if user['role'] in {'reviewer','admin'}:
        queue = reviewer_queue(user)
        with st.container(border=True):
            st.markdown('<div class="mg-section-title">Review queue</div>', unsafe_allow_html=True)
            if queue:
                st.dataframe([{'Claim': c['claim_number'], 'Patient': c['patient_name'], 'Status': _status_badge(c['status']), 'Priority': c['review_priority'] if 'review_priority' in c.keys() else 0} for c in queue], use_container_width=True, hide_index=True)
            else: st.info('No claims are waiting for review.')


def _render_register(user: dict) -> None:
    st.markdown('<div class="mg-eyebrow">CLAIMS</div><h1>Register a New Claim</h1><p class="mg-subtitle">Enter claim and patient details to get started.</p>', unsafe_allow_html=True)
    with st.container(border=True):
        left,right = st.columns(2, gap='large')
        with left:
            st.markdown('### Claim Details')
            claim_number = st.text_input('Claim number', placeholder='CLM-2026-0001')
            patient = st.text_input('Patient name', placeholder='Full name')
            policy = st.text_input('Policy number', placeholder='POL-DEMO-2026-001', help='Enter exactly as shown on your policy document.')
        with right:
            st.markdown('### Service Details')
            hospital = st.text_input('Hospital / provider', placeholder='Hospital name')
            incident_date = st.date_input('Admission or service date')
            st.selectbox('Claim type', ['Hospitalization', 'Day care', 'Outpatient'])
        st.divider()
        if st.button('Register & continue to documents', type='primary', use_container_width=True):
            if not claim_number.strip() or not patient.strip(): st.error('Claim number and patient name are required.')
            else:
                claim_id = create_claim(user['user_id'], claim_number, patient, hospital, policy, str(incident_date))
                st.session_state.active_claim = claim_id; st.session_state.page = 'Claim review'; st.success('Claim registered. Continue to upload documents.'); st.rerun()


def _render_claim_review(user: dict) -> None:
    claims = user_claims(user['user_id'], user)
    st.markdown('<div class="mg-eyebrow">CLAIMS / REVIEW</div><h1>Claim Review</h1>', unsafe_allow_html=True)
    if not claims:
        st.info('No claims yet. Register a claim to start the workflow.'); return
    options = {f"{c['claim_number']} · {c['patient_name']}": c['claim_id'] for c in claims}
    labels = list(options); default = next((i for i,v in enumerate(options.values()) if v == st.session_state.get('active_claim')), 0)
    selected = st.selectbox('Selected claim', labels, index=default); claim_id = options[selected]; st.session_state.active_claim = claim_id
    selected_claim = next(c for c in claims if c['claim_id'] == claim_id)
    st.markdown(f"<div class='mg-context'><b>{selected_claim['claim_number']}</b> · {selected_claim['patient_name']} <span class='mg-pill' style='color:{_status_color(selected_claim['status'])}'>{_status_badge(selected_claim['status'])}</span></div>", unsafe_allow_html=True)
    tabs = st.tabs(['① Select claim', '② Upload documents', '③ Extract & normalize', '④ Analyze claim'])
    with tabs[1]:
        st.markdown('### Upload Documents')
        pcol,bcol = st.columns(2)
        with pcol: policy_files = st.file_uploader('Policy documents', type=['pdf','png','jpg','jpeg'], accept_multiple_files=True, key=f'pol_{claim_id}')
        with bcol: bill_files = st.file_uploader('Medical bill / supporting documents', type=['pdf','png','jpg','jpeg'], accept_multiple_files=True, key=f'bill_{claim_id}')
        if st.button('Save uploaded documents', type='primary', use_container_width=True):
            files = [(f,'policy') for f in (policy_files or [])] + [(f,'medical_bill') for f in (bill_files or [])]
            if not files: st.warning('Upload at least one policy or medical bill.')
            else:
                try:
                    for uploaded, kind in files: save_document(claim_id, user, uploaded, kind)
                    st.success(f'Saved {len(files)} document(s).'); st.rerun()
                except (ValueError, PermissionError) as exc: st.error(str(exc))
        docs = claim_documents(claim_id, user)
        if docs: st.dataframe([{'File':d['original_name'],'Type':d['document_type'].replace('_',' ').title(),'Status':d['processing_status']} for d in docs], use_container_width=True, hide_index=True)
        else: st.info('Your saved documents will appear here.')
    docs = claim_documents(claim_id, user)
    with tabs[2]:
        normalized = st.session_state.get(f'normalized_{claim_id}')
        if st.button('Run extraction', type='primary', use_container_width=True):
            with st.status('Reading documents and normalizing fields...', expanded=True) as status:
                try:
                    normalized = process_claim_documents(claim_id, user['user_id']); st.session_state[f'normalized_{claim_id}'] = normalized; status.update(label='Extraction complete', state='complete')
                except Exception as exc: status.update(label='Extraction failed', state='error'); st.error(str(exc))
        if normalized:
            missing = normalized.get('missing_fields',[]) + normalized.get('review_fields',[])
            if missing: st.warning('Some fields need your input before analysis: ' + ', '.join(missing))
            fields=[]
            for key in ('patient_name','hospital_name','policy_number','claim_number','admission_date','discharge_date','diagnosis','total_amount'):
                item=normalized.get(key)
                if item: fields.append({'Field':key.replace('_',' ').title(),'Value':item['value'],'Confidence':round(float(item['confidence']),1),'Review':'Yes' if item['needs_review'] else 'No'})
            a,b,c = st.columns(3); a.metric('Fields extracted', len(fields)); b.metric('Missing / review', len(missing)); c.metric('Line items', len(normalized.get('line_items',[])))
            with st.expander('Extracted summary', expanded=True): st.dataframe(fields, use_container_width=True, hide_index=True)
            with st.expander(f"Line items ({len(normalized.get('line_items',[]))})"): st.dataframe([{k:i.get(k) for k in ('description','amount','category','confidence','needs_review')} for i in normalized.get('line_items',[])], use_container_width=True, hide_index=True)
            with st.expander('Field-by-field evidence'): st.json(normalized)
        else: st.info('Run extraction after saving documents.')
    with tabs[3]:
        normalized = st.session_state.get(f'normalized_{claim_id}')
        rules = st.session_state.get(f'rules_{claim_id}')
        if not normalized: st.warning('Complete extraction before analysis.'); return
        if st.button('Run deterministic coverage rules', type='primary', use_container_width=True):
            with st.status('Applying policy rules...', expanded=True) as status:
                try: rules=evaluate_saved_claim(claim_id,user['user_id'],normalized); st.session_state[f'rules_{claim_id}']=rules; status.update(label='Rules complete',state='complete')
                except Exception as exc: status.update(label='Rules failed',state='error'); st.error(str(exc))
        if rules:
            st.markdown(f"### Deterministic result <span class='mg-pill' style='color:{_status_color(rules['status'])}'>{_status_badge(rules['status'])}</span>", unsafe_allow_html=True)
            a,b,c,d=st.columns(4); a.metric('Covered',f"INR {rules.get('covered_amount',0):,.2f}"); b.metric('Deductible',f"INR {rules.get('deductible',0):,.2f}"); c.metric('Copayment',f"INR {rules.get('copayment',0):,.2f}"); d.metric('Payable',f"INR {rules.get('payable_amount',0):,.2f}")
            if rules.get('warnings'): st.warning('; '.join(rules['warnings']))
            with st.expander('Why this result? Rule trace', expanded=True): st.dataframe(rules.get('results',[]), use_container_width=True, hide_index=True)
            workflow=st.session_state.get(f'workflow_{claim_id}')
            if st.button('Run Policy Agent + Decision Agent', type='primary', use_container_width=True):
                with st.status('Retrieving policy evidence...', expanded=True) as status:
                    try:
                        started=time.perf_counter(); workflow=run_agents_for_claim(claim_id,user['user_id'],normalized,rules,progress_callback=lambda msg: status.write(msg)); workflow['elapsed_seconds']=round(time.perf_counter()-started,2); st.session_state[f'workflow_{claim_id}']=workflow; status.update(label='Two-agent analysis complete',state='complete')
                    except Exception as exc: status.update(label='Agent workflow failed',state='error'); st.error(str(exc))
            if workflow:
                decision=workflow.get('decision',{}); st.markdown(f"### Recommendation <span class='mg-pill' style='color:{_status_color(decision.get('status','manual_review'))}'>{_status_badge(decision.get('status','manual_review'))}</span>", unsafe_allow_html=True)
                for reason in decision.get('reasons',[]): st.write(f'• {reason}')
                st.caption(f"Policy source: {workflow.get('policy_source','none')} · LLM calls: {workflow.get('llm_calls',0)} · Time: {workflow.get('elapsed_seconds','n/a')}s")
                with st.expander('Policy evidence and agent reasoning'): st.json({'decision':decision,'policy_findings':workflow.get('policy_findings',{})})
                if user['role'] in {'reviewer','admin'}:
                    with st.container(border=True):
                        st.markdown('### Reviewer Sign-off')
                        final=st.selectbox('Final determination',['approved','partially_approved','rejected','manual_review'],format_func=_status_badge,key=f'final_{claim_id}')
                        comments=st.text_area('Reviewer comments',key=f'comments_{claim_id}')
                        if st.button('Confirm sign-off',key=f'save_final_{claim_id}',type='primary'):
                            if not comments.strip(): st.warning('Reviewer comments are required.')
                            else: save_reviewer_decision(claim_id,user['user_id'],decision.get('status','manual_review'),final,comments); st.success('Reviewer decision saved and audited.')
        else: st.info('Run deterministic rules before starting the agents.')
    st.caption('Decision support only. Final determination must be confirmed by an authorized reviewer.')


def _render_policy_management(user: dict) -> None:
    if user['role'] not in {'reviewer','admin'}: st.info('Policy Management is available to Reviewers and Administrators.'); return
    st.markdown('<div class="mg-eyebrow">POLICY & RULES</div><h1>Policy Management</h1><p class="mg-subtitle">Ingest, manage and compare policy editions.</p>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('### Ingest New Policy Edition')
        with st.form('policy_ingestion_form'):
            policy_file=st.file_uploader('Policy document',type=['pdf','png','jpg','jpeg']); a,b,c=st.columns(3)
            with a: policy_number=st.text_input('Policy number',placeholder='POL-DEMO-2026-001'); version_label=st.text_input('Version label',placeholder='2026 Edition')
            with b: insurer=st.text_input('Insurer',placeholder='Example Health Insurance Ltd.'); effective_date=st.date_input('Effective date')
            with c: st.info('The active edition supplies authoritative rule terms.'); submitted=st.form_submit_button('Ingest & activate edition',type='primary',use_container_width=True)
        if submitted:
            try:
                if not policy_file or not policy_number.strip() or not version_label.strip(): raise ValueError('Policy file, policy number and version label are required.')
                result=ingest_policy_version(policy_file,policy_number,version_label,insurer,str(effective_date),user=user); st.success(f"Active edition created with {result['chunks_indexed']} evidence chunks."); st.rerun()
            except Exception as exc: st.error(f'Policy ingestion failed: {exc}')
    versions=policy_versions()
    with st.container(border=True):
        st.markdown('### Policy Editions')
        if not versions: st.info('No policy editions have been ingested yet.')
        else:
            rows=[]
            for v in versions:
                try: terms=json.loads(v['policy_terms_json'] or '{}')
                except (TypeError,json.JSONDecodeError): terms={}
                rows.append({'Policy Number':v['policy_number'],'Version':v['version_label'],'Effective Date':v['effective_date'],'Status':v['status'].title(),'Indexed Chunks':v['indexed_chunks'],'Extracted Terms':len(terms)})
            st.dataframe(rows,use_container_width=True,hide_index=True)
            active=[v for v in versions if v['status']=='active']
            if active and user['role']=='admin':
                chosen=st.selectbox('Archive an active edition',['Select an edition']+[f"{v['policy_number']} — {v['version_label']}" for v in active])
                if chosen!='Select an edition' and st.button('Archive edition'): archive_policy_version(next(v['version_id'] for v in active if f"{v['policy_number']} — {v['version_label']}"==chosen),user=user); st.success('Edition archived.'); st.rerun()


def _render_admin_panel(user: dict) -> None:
    require_role(user,'admin')
    st.markdown('<div class="mg-eyebrow">ADMINISTRATION</div><h1>Admin Panel</h1><p class="mg-subtitle">Manage reviewer access and user accounts.</p>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('### Reviewer Invitations')
        with st.form('invite_reviewer'):
            a,b=st.columns([1,1]); name=a.text_input('Name'); email=b.text_input('Email address'); sent=st.form_submit_button('Send invite',type='primary')
        if sent:
            try:
                invite=create_reviewer_invitation(user,email,name); st.success('Invitation created.'); st.code(f"{APP_BASE_URL}/?setup_token={invite['setup_token']}")
            except Exception as exc: st.error(str(exc))
    with st.container(border=True):
        st.markdown('### Users')
        with db() as conn: users=conn.execute('SELECT user_id,email,display_name,role,is_active,created_at FROM users ORDER BY created_at DESC').fetchall()
        st.dataframe([{'Name':u['display_name'],'Email':u['email'],'Role':u['role'].title(),'Status':'Active' if u['is_active'] else 'Inactive','Created':u['created_at']} for u in users],use_container_width=True,hide_index=True)
        st.info('User and invitation activity is logged for security and cannot be silently deleted.')


def main() -> None:
    st.set_page_config(page_title='Medi Gaurd AI', page_icon='🛡️', layout='wide', initial_sidebar_state='expanded')
    st.markdown('''<style>
    :root{--navy:#06285b;--navy2:#0b3b78;--blue:#1167dc;--bg:#f4f8fd;--border:#dce6f1;--text:#12213d}
    .stApp{background:var(--bg);color:var(--text)} .block-container{max-width:1440px;padding:1.7rem 2.4rem 3rem}
    [data-testid="stSidebar"]{background:linear-gradient(180deg,var(--navy),#071c42);border:0} [data-testid="stSidebar"] *{color:#f6f9ff!important}
    [data-testid="stSidebar"] .stRadio label{padding:.55rem .75rem;border-radius:8px;font-weight:600} [data-testid="stSidebar"] .stRadio label:hover{background:#114a98}
    .mg-brand-head{display:flex;gap:.65rem;align-items:center;padding:.2rem 0 1.5rem}.mg-brand-name{font-weight:800;font-size:1.22rem}.mg-brand-sub{font-size:.63rem;opacity:.78;line-height:1.25}.mg-shield{width:2.05rem;height:2.05rem;border:2px solid #fff;border-radius:9px;display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff}.mg-shield.large{width:4rem;height:4rem;border:3px solid #1467d6;color:#1467d6;font-size:2rem;margin:auto}
    .mg-nav-label,.mg-eyebrow{font-size:.7rem;letter-spacing:.13em;font-weight:800;color:#7b8ca5!important}.mg-sidebar-spacer{height:36vh}.mg-sidebar-foot{font-size:.68rem;opacity:.72;border-top:1px solid #2c5284;padding-top:1rem;margin-top:1rem}
    h1{letter-spacing:-.04em;color:var(--text)} .mg-eyebrow{color:#2f6fb0!important;margin-bottom:.25rem}.mg-subtitle{color:#63728a;font-size:1.02rem;margin-top:-.8rem;margin-bottom:1.4rem}.mg-section-title{font-size:1.08rem;font-weight:800;margin-bottom:1rem}.mg-auth-title{font-size:1.7rem;font-weight:800;margin-top:5vh}.mg-auth-copy{color:#68758b;margin-bottom:1.4rem}.mg-landing{background:#eaf3ff;border-radius:16px;padding:4rem 2rem 2.2rem;text-align:center;margin-top:2rem;min-height:550px}.mg-landing h1{color:#123d78;font-size:2.25rem}.mg-tagline{font-weight:650;line-height:1.55}.mg-promise{font-size:1.1rem;font-weight:700;margin:2rem 0;color:#1b4c8d}.mg-illustration{font-size:7rem;color:#2771d7;line-height:1.05;opacity:.78}.mg-illustration span{font-size:1.5rem;letter-spacing:1rem}.stButton>button{border-radius:8px;min-height:2.55rem;font-weight:700}.stButton>button[kind="primary"]{background:var(--blue);border-color:var(--blue)} [data-testid="stMetric"]{background:#fff;border:1px solid var(--border);border-radius:12px;padding:1rem 1.1rem;box-shadow:0 2px 8px #193b6510}.stMetric label{color:#66758c}.stMetric [data-testid="stMetricValue"]{color:var(--text);font-weight:800}.stTextInput input,.stTextArea textarea,.stDateInput input,.stSelectbox div[data-baseweb="select"]>div{border-radius:8px;border-color:#cbd8e8;background:#fff}.stForm,.st-key-policy_ingestion_form{border:0}.mg-context{background:#fff;border:1px solid var(--border);border-radius:10px;padding:.85rem 1rem;margin:1rem 0}.mg-pill{font-size:.75rem;font-weight:800;margin-left:.5rem}.mg-section-title+div{margin-top:.2rem}
    </style>''', unsafe_allow_html=True)
    init_db(); validate_security_config(); bootstrap_admin_from_env()
    if CORE_DEMO_MODE and 'user' not in st.session_state:
        st.session_state.user = _core_demo_user()
        st.session_state.page = 'Dashboard'
    if 'user' not in st.session_state:
        pending=st.session_state.get('pending_mfa_user')
        if pending:
            st.markdown('<div class="mg-eyebrow">SECURE SIGN IN</div><h1>Authenticator verification</h1><p class="mg-subtitle">Enter the 6-digit code from your authenticator app.</p>',unsafe_allow_html=True)
            with st.form('mfa_login'):
                code=st.text_input('Authenticator code',max_chars=6); submitted=st.form_submit_button('Verify and sign in',type='primary')
            if submitted:
                current=get_user(pending['user_id'])
                if current and verify_totp(current,code): st.session_state.user=dict(current); st.session_state.pop('pending_mfa_user',None); st.session_state.page='Dashboard'; st.rerun()
                else: st.error('The authenticator code is invalid or expired.')
            return
        _render_login(); return
    user=st.session_state.user; page=_render_sidebar(user)
    if page=='Dashboard': _render_dashboard(user)
    elif page=='Register claim': _render_register(user)
    elif page=='Claim review': _render_claim_review(user)
    elif page=='Claim result': _render_claimant_result(user)
    elif page=='Policy management': _render_policy_management(user)
    elif page=='Admin panel': _render_admin_panel(user)


if __name__ == '__main__':
    main()
