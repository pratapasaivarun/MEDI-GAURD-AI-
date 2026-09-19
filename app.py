import base64
import hashlib
import hmac
import json
import secrets
import os
import sqlite3
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from extraction import check_submission_deadline, run_extraction
from rules import evaluate_claim
from agents import _ollama_json, confidence_label, recommend_next_steps, retrieve_policy_evidence, run_claim_workflow, warm_ollama
from policy_index import index_policy_documents
from extraction import extract_document
from policy_terms import extract_policy_terms, terms_from_json
from reports import build_appeal_letter_pdf, build_decision_report

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
# Granite is installed locally and is the project's sole configured model.
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "ibm/granite4.1:8b")
MAX_PAGES = int(os.getenv("MAX_DOCUMENT_PAGES", "10"))
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "15"))
APP_ENV = os.getenv("APP_ENV", "development").lower()
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8505").rstrip("/")
# The academic prototype uses a local demo identity; production authentication is deferred.
ALLOWED_ROLES = {"claimant", "reviewer", "admin"}


def get_db_path() -> Path:
    return Path(os.getenv("MEDIGUARD_DB_PATH", str(DATA_DIR / "mediguard.db"))).resolve()


def get_storage_dir() -> Path:
    return Path(os.getenv("MEDIGUARD_STORAGE_DIR", str(DATA_DIR))).resolve()


def get_upload_dir() -> Path:
    return get_storage_dir() / "uploads"


def core_demo_mode() -> bool:
    return os.getenv("MEDIGUARD_CORE_DEMO", "true").lower() == "true"


def _claim_warning_message(value: Any) -> str:
    if str(value) == "line_item_reconciliation_failed":
        return "Itemized charges could not be reconciled to the bill total, so the aggregate bill total was used for this calculation."
    return str(value)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
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


def get_user(user_id: str) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def validate_security_config() -> None:
    # SESSION_SECRET is not validated here because the current Streamlit app does
    # not sign sessions or tokens. A future token implementation must add its own
    # fail-closed validation before this setting is used.
    storage_dir = get_storage_dir()
    upload_dir = get_upload_dir()
    if storage_dir == APP_DIR or any(part.lower() in {"public", "static"} for part in storage_dir.parts):
        raise RuntimeError("MEDIGUARD_STORAGE_DIR must be a private directory outside public/static paths.")
    storage_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)


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
    digest = hashlib.sha256(content).hexdigest()
    with db() as conn:
        duplicate = conn.execute(
            "SELECT document_id FROM documents WHERE claim_id=? AND document_type=? AND sha256=? LIMIT 1",
            (claim_id, document_type, digest),
        ).fetchone()
    if duplicate:
        raise ValueError(f"This {document_type.replace('_', ' ')} is already attached to the claim.")
    document_id = str(uuid.uuid4())
    claim_dir = get_upload_dir() / claim_id
    claim_dir.mkdir(parents=True, exist_ok=True)
    safe_name = safe_name.replace(" ", "_")
    target = claim_dir / f"{document_id}_{safe_name}"
    target.write_bytes(content)
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
    target_dir = get_storage_dir() / "policies"
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
    policy_payloads = [payload for payload in payloads if payload["document_type"] == "policy"]
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
                # Retrieval runs with the active edition ID, so store this
                # claim-uploaded policy under that same ID as well.
                index_policy_documents(policy_payloads, normalized["active_policy_version_id"])
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
        candidate.relative_to(get_storage_dir())
    except ValueError as exc:
        raise PermissionError("Document path is outside the private storage root.") from exc
    if not candidate.is_file():
        raise FileNotFoundError("Stored document is unavailable.")
    return candidate


def _extract_one(doc):
    from extraction import extract_document
    candidate = Path(doc["stored_path"]).resolve()
    try:
        candidate.relative_to(get_storage_dir())
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
    claimant_responsibility = round(max(0.0, billed - payable), 2)
    deductible_amount = round(max(0.0, deductible), 2)
    copayment_amount = round(max(0.0, copayment), 2)
    excluded_amount = round(max(0.0, claimant_responsibility - deductible_amount - copayment_amount), 2)
    result["claimant_responsibility"] = claimant_responsibility
    result["claimant_result"] = {"amount_billed": round(billed, 2), "amount_covered": round(payable, 2), "amount_not_covered": claimant_responsibility, "amount_excluded_or_limited": excluded_amount, "deductible": deductible_amount, "copayment": copayment_amount, "amount_claimant_pays": claimant_responsibility, "status": result.get("status", "manual_review"), "reason": (result.get("warnings") or ["See reviewer analysis."])[0]}
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

def check_similar_past_rejections(claimant_id: str, current_line_items: list, policy_id: str) -> list[dict]:
    from difflib import SequenceMatcher
    flags = []
    with db() as conn:
        rows = conn.execute("SELECT c.incident_date, c.status, r.result_json FROM claims c JOIN rule_evaluations r ON r.claim_id=c.claim_id WHERE c.user_id=? AND c.policy_number=? ORDER BY r.created_at DESC", (claimant_id, policy_id)).fetchall()
    for current_index, current in enumerate(current_line_items or []):
        if not isinstance(current, dict) or current.get("status") not in {"excluded", "partial"}: continue
        description = " ".join(str(current.get("description") or "").lower().split())
        for row in rows:
            try: past_items = json.loads(row["result_json"]).get("line_item_results") or []
            except (TypeError, json.JSONDecodeError): continue
            matched = next((past for past in past_items if isinstance(past, dict) and past.get("status") in {"excluded", "partial"} and past.get("applied_rule") == current.get("applied_rule") and SequenceMatcher(None, description, " ".join(str(past.get("description") or "").lower().split())).ratio() > 0.85), None)
            if matched:
                past_date = str(row["incident_date"] or "unknown date")
                flags.append({"item_index": current_index, "past_claim_date": past_date, "past_status": str(matched.get("status")), "note": f"A similar item was rejected on {past_date} for the same reason ({current.get('applied_rule')})."})
                break
    return flags


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
            result = evaluate_claim(total, terms=terms, review_fields=normalized.get("review_fields"), missing_fields=normalized.get("missing_fields"), claim_context=_derived_claim_context(claim_id, user_id, normalized), line_items=normalized.get("line_items"))
        result["policy_terms_confidence"] = confidence
    else:
        result = {"status": "manual_review", "rule_version": "policy-terms-required", "results": [], "covered_amount": 0.0, "deductible": 0.0, "copayment": 0.0, "payable_amount": 0.0, "warnings": ["No active policy terms are available. Ingest a policy edition in Policy management first."], "policy_terms_missing": ["active_policy_terms"], "policy_terms": {}}
    result["policy_source"] = f"{active_policy['policy_number']} — {active_policy['version_label']}" if active_policy else "none"
    result = _reconcile_result(result, total)
    result["history_flags"] = check_similar_past_rejections(user_id, result.get("line_item_results") or [], policy_number or "")
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
        try:
            warm_ollama()
            st.session_state["ollama_warmed"] = True
        except requests.RequestException:
            # Let the workflow persist its manual-review fallback if inference fails.
            pass
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
            return False, f"Connected — configured model not found locally ({OLLAMA_MODEL})"
        return False, f"Ollama returned HTTP {response.status_code}"
    except requests.RequestException as exc:
        return False, f"Ollama unavailable: {exc}"


def _status_badge(status: str) -> str:
    return status.replace('_', ' ').title()


def _line_item_status_label(status: Any) -> str:
    """Return a compact, readable status cue for claimant-facing item rows."""
    return {
        "covered": ":green[:material/check_circle: Covered]",
        "partial": ":orange[:material/pie_chart: Partially covered]",
        "excluded": ":red[:material/cancel: Excluded]",
        "needs_review": ":orange[:material/rate_review: Needs review]",
    }.get(str(status), str(status or "Needs review").replace("_", " ").title())


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
      <div class="mg-logo-mark" aria-label="Medi Gaurd AI logo">
        <svg viewBox="0 0 64 64" role="img" aria-hidden="true"><path d="M32 5 54 13v16c0 14.5-9.4 25.2-22 30C19.4 54.2 10 43.5 10 29V13L32 5Z" fill="currentColor"/><path d="M32 16v30M20 31h24" stroke="#073b3a" stroke-width="5" stroke-linecap="round"/><path d="M22 42c3.1 4.2 8.4 6.9 10 7.5 1.6-.6 6.9-3.3 10-7.5" fill="none" stroke="#073b3a" stroke-width="3" stroke-linecap="round"/></svg>
      </div>
      <div><div class="mg-brand-name">Medi Gaurd AI</div>
      <div class="mg-brand-sub">Evidence-led claim decisions</div></div>
    </div>''', unsafe_allow_html=True)


def _page_header(eyebrow: str, title: str, subtitle: str, icon: str) -> None:
    """Use one consistent, lightweight page hierarchy across the prototype UI."""
    st.markdown(
        f'''<div class="mg-page-header">
        <div class="mg-header-icon">{icon}</div>
        <div><div class="mg-eyebrow">{eyebrow}</div><h1>{title}</h1>
        <p class="mg-subtitle">{subtitle}</p></div></div>''',
        unsafe_allow_html=True,
    )


def _core_demo_user() -> dict[str, Any]:
    """Create the password-protected local admin used by the synthetic demo."""
    demo_email = "demo@mediguard.local"
    demo_password = os.getenv("DEMO_ADMIN_PASSWORD", "Mediguard@2026")
    demo_id = hashlib.sha256(demo_email.encode("utf-8")).hexdigest()[:24]
    with db() as conn:
        conn.execute(
            "INSERT INTO users(user_id,email,display_name,role,password_hash,is_active,password_set_at,created_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET display_name=excluded.display_name, role='admin', password_hash=excluded.password_hash, is_active=1, password_set_at=excluded.password_set_at",
            (demo_id, demo_email, "Demo Reviewer", "admin", _hash_password(demo_password), 1, utc_now(), utc_now()),
        )
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (demo_id,)).fetchone()
    return dict(row)


def _render_welcome() -> None:
    """Opening screen only; it does not alter login or claim workflow state."""
    st.markdown('''<div class="mg-opening">
      <div class="mg-opening-orb orb-one"></div><div class="mg-opening-orb orb-two"></div>
      <div class="mg-opening-logo"><svg viewBox="0 0 64 64" aria-hidden="true"><path d="M32 5 54 13v16c0 14.5-9.4 25.2-22 30C19.4 54.2 10 43.5 10 29V13L32 5Z" fill="currentColor"/><path d="M32 16v30M20 31h24" stroke="#073b3a" stroke-width="5" stroke-linecap="round"/><path d="M22 42c3.1 4.2 8.4 6.9 10 7.5 1.6-.6 6.9-3.3 10-7.5" fill="none" stroke="#073b3a" stroke-width="3" stroke-linecap="round"/></svg></div>
      <div class="mg-opening-brand">MEDI GAURD AI</div>
      <h1>Healthcare claims,<br><em>made understandable.</em></h1>
      <p>Upload documents, understand coverage, and make every decision with evidence you can review.</p>
      <div class="mg-opening-chips"><span>🩺 Care-first</span><span>📄 Evidence-led</span><span>🔐 Privacy-aware</span></div>
    </div>''', unsafe_allow_html=True)
    st.markdown('<div class="mg-role-label">CHOOSE YOUR WORKSPACE</div>', unsafe_allow_html=True)
    entry = st.radio(
        'Choose your workspace',
        ['User / claimant', 'Admin / reviewer'],
        horizontal=True,
        label_visibility='collapsed',
        format_func=lambda role: '👤 User — sign in or create account' if role == 'User / claimant' else '🛡️ Admin — secure sign in',
    )
    _, action, _ = st.columns([1, 1, 1])
    with action:
        label = 'Continue as user' if entry == 'User / claimant' else 'Continue as admin'
        if st.button(label, type='primary', icon=':material/arrow_forward:', use_container_width=True):
            st.session_state.entry_role = 'claimant' if entry == 'User / claimant' else 'staff'
            st.session_state.welcome_seen = True
            st.rerun()
    st.caption('Built for clearer conversations between patients, providers, and reviewers.')


def _render_login() -> None:
    reset_token = st.query_params.get('reset_token')
    setup_token = st.query_params.get('setup_token')
    if reset_token or setup_token:
        st.subheader('Reset password' if reset_token else 'Set up reviewer account')
        with st.form('complete_account_setup'):
            password = st.text_input('New password', type='password')
            confirmation = st.text_input('Confirm new password', type='password')
            submitted = st.form_submit_button('Save password', type='primary')
        if submitted:
            try:
                if password != confirmation:
                    raise ValueError('Passwords do not match.')
                if reset_token:
                    complete_password_reset(reset_token, password)
                else:
                    complete_reviewer_setup(setup_token, password)
                st.query_params.clear()
                st.success('Password saved. You can now sign in.')
            except ValueError as exc:
                st.error(str(exc))
        if st.button('Back to sign in'):
            st.query_params.clear()
            st.rerun()
        return
    staff_portal = st.session_state.get('entry_role') == 'staff'
    left, right = st.columns([1.1, 1], gap='large')
    with left:
        st.markdown('''<div class="mg-landing">
        <div class="mg-landing-badge">✨ Evidence-first claim support</div>
        <div class="mg-landing-art" aria-hidden="true"><span>🩺</span><span>📄</span><span>🛡️</span><span>💚</span></div>
        <div class="mg-shield large">M</div><h1>Clarity for every claim.</h1>
        <p class="mg-tagline">Bring your bill and policy together in one guided, evidence-led review.</p>
        <div class="mg-landing-points"><span>📄 Extract</span><span>🔎 Verify</span><span>✓ Decide</span></div>
        <p class="mg-promise">Transparent calculations. Human confirmation.</p>
        </div>''', unsafe_allow_html=True)
    with right:
        portal_title = 'Admin sign in' if staff_portal else 'Welcome back'
        portal_copy = 'Use your authorized administrator or reviewer credentials.' if staff_portal else 'Sign in to continue your claim review.'
        portal_label = 'ADMINISTRATOR PORTAL' if staff_portal else 'USER WORKSPACE'
        st.markdown(f'<div class="mg-auth-kicker">{portal_label}</div><div class="mg-auth-title">{portal_title}</div><div class="mg-auth-copy">{portal_copy}</div>', unsafe_allow_html=True)
        if staff_portal:
            login_tab, reset_tab = st.tabs(['Secure sign in', 'Reset password'])
        else:
            login_tab, register_tab, reset_tab = st.tabs(['Sign in', 'Create account', 'Reset password'])
        with login_tab:
            with st.form('login'):
                email = st.text_input('Email', placeholder='you@example.com')
                password = st.text_input('Password', type='password')
                st.checkbox('Remember me', value=True)
                submitted = st.form_submit_button('Sign in', type='primary')
            if submitted:
                user_row = authenticate_password(email, password)
                if user_row is None:
                    st.error("That email or password doesn't match our records.")
                elif staff_portal and user_row['role'] not in {'admin', 'reviewer'}:
                    st.error('These credentials are for a user account. Select the User workspace to continue.')
                elif not staff_portal and user_row['role'] != 'claimant':
                    st.error('These credentials are for an administrator or reviewer. Select the Admin workspace to continue.')
                elif user_row['mfa_enabled']:
                    st.session_state.pending_mfa_user = {'user_id': user_row['user_id']}
                    st.rerun()
                else:
                    st.session_state.user = dict(user_row)
                    st.session_state.page = 'Dashboard'
                    st.rerun()
        if not staff_portal:
            with register_tab:
                with st.form('register'):
                    name = st.text_input('Full name')
                    email = st.text_input('Email', key='reg_email')
                    p1 = st.text_input('Password', type='password')
                    p2 = st.text_input('Confirm password', type='password')
                    st.caption('Use at least 10 characters. New self-registered accounts are Claimants.')
                    submitted = st.form_submit_button('Create account', type='primary')
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
                submitted = st.form_submit_button('Send reset link', type='primary')
            if submitted:
                request = create_password_reset_request(email)
                st.success('If an active account exists, reset instructions have been generated.')
                if request['reset_token']: st.code(f"{APP_BASE_URL}/?reset_token={request['reset_token']}")
        if st.button('← Choose a different workspace', key='change_workspace'):
            st.session_state.pop('entry_role', None)
            st.session_state.welcome_seen = False
            st.rerun()


def _render_sidebar(user: dict) -> str:
    with st.sidebar:
        _brand_header()
        st.markdown('<div class="mg-nav-label">WORKSPACE</div>', unsafe_allow_html=True)
        if user['role'] == 'claimant':
            pages = ['Dashboard', 'Register claim', 'Submit documents', 'Claim result']
        else:
            pages = ['Dashboard', 'Claim review', 'Policy management']
            pages.insert(2, 'Claim result')
            if user['role'] == 'admin':
                pages.insert(1, 'Register claim')
                pages.append('Admin panel')
        current = st.session_state.get('page', 'Dashboard')
        if current not in pages: current = 'Dashboard'
        labels = {
            'Dashboard': ':material/dashboard: Dashboard',
            'Register claim': ':material/add_circle: Register claim',
            'Submit documents': ':material/upload_file: Submit documents',
            'Claim review': ':material/fact_check: Claim review',
            'Claim result': ':material/task_alt: Claim result',
            'Policy management': ':material/policy: Policy management',
            'Admin panel': ':material/admin_panel_settings: Admin panel',
        }
        page = st.radio('Workspace', pages, index=pages.index(current), format_func=lambda x: labels[x], label_visibility='collapsed')
        st.markdown('<div class="mg-sidebar-spacer"></div>', unsafe_allow_html=True)
        st.markdown('<div class="mg-nav-label">ACCOUNT</div>', unsafe_allow_html=True)
        st.caption(f"Signed in as {user['display_name']}")
        st.caption(f"Role: {user['role'].title()}")
        if st.button('↪  Sign out'):
            st.session_state.clear(); st.rerun()
        st.markdown('<div class="mg-sidebar-foot">Final determination must be confirmed by an authorized reviewer.</div>', unsafe_allow_html=True)
    st.session_state.page = page
    return page


def _claimant_result_for_claim(claim_id: str, user: dict) -> dict[str, Any] | None:
    """Return only claimant-safe amounts and explanation; hide raw agent/reviewer data."""
    claim = _claim_access(claim_id, user)
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
    status = claim["status"] if claim["status"] in {"approved", "partially_approved", "rejected", "manual_review"} else (decision.get("status") or ((rules or {}).get("status", "manual_review")))
    claimant = (rules or {}).get("claimant_result") or {}
    billed = float(claimant.get("amount_billed", 0) or 0)
    covered = float(claimant.get("amount_covered", (rules or {}).get("payable_amount", 0)) or 0)
    responsibility = float(claimant.get("amount_claimant_pays", max(0, billed - covered)) or 0)
    deductible = float(claimant.get("deductible", (rules or {}).get("deductible", 0)) or 0)
    copayment = float(claimant.get("copayment", (rules or {}).get("copayment", 0)) or 0)
    excluded_or_limited = float(claimant.get("amount_excluded_or_limited", 0) or 0)
    not_paid = float(claimant.get("amount_not_covered", responsibility) or 0)
    reasons = decision.get("reasons") or (rules or {}).get("warnings") or []
    reason = _claim_warning_message(reasons[0]) if reasons else "Your claim has been processed and the result is ready to review."
    return {
        "status": status,
        "amount_billed": billed,
        "amount_covered": covered,
        "amount_claimant_pays": responsibility,
        "amount_not_covered": not_paid,
        "deductible": deductible,
        "copayment": copayment,
        "amount_excluded_or_limited": excluded_or_limited,
        "reason": reason,
        "requires_human_review": status == "manual_review",
        "rules": rules or {},
    }


def _render_claimant_result(user: dict) -> None:
    claims = user_claims(user["user_id"], user)
    _page_header('CLAIM OUTCOME', 'Your claim result', 'A simple view of the policy review, your estimated responsibility, and next steps.', '✓')
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
    st.markdown(f"<div class='mg-context'><div><b>{claim['claim_number']}</b><div class='mg-card-copy'>{claim['patient_name']} · {claim['policy_number'] or 'Policy number pending'}</div></div><span class='mg-pill mg-pill-{(result or {}).get('status', claim['status'])}'>{_status_badge((result or {}).get('status', claim['status']))}</span></div>", unsafe_allow_html=True)
    if not result:
        st.info("Your documents have not been analyzed yet.")
        if st.button("Continue claim review", type="primary"):
            st.session_state.page = "Submit documents" if user['role'] == 'claimant' else "Claim review"; st.rerun()
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
    with st.container(horizontal=True, horizontal_alignment='left'):
        st.metric("Total bill", f"INR {result['amount_billed']:,.2f}", border=True)
        st.metric("Covered by insurance", f"INR {result['amount_covered']:,.2f}", border=True)
        st.metric("Your responsibility", f"INR {result['amount_claimant_pays']:,.2f}", border=True)
    with st.container(horizontal=True, horizontal_alignment='left'):
        st.metric("Excluded / policy-limited", f"INR {result['amount_excluded_or_limited']:,.2f}", border=True)
        st.metric("Deductible", f"INR {result.get('deductible', 0):,.2f}", border=True)
        st.metric("Copayment", f"INR {result.get('copayment', 0):,.2f}", border=True)
    with st.container(border=True):
        st.markdown("### What this means for you")
        st.write(result["reason"])
        st.write(
            f"The claimant responsibility of INR {result['amount_claimant_pays']:,.2f} includes "
            f"INR {result['deductible']:,.2f} deductible and INR {result['copayment']:,.2f} copayment. "
            f"INR {result['amount_excluded_or_limited']:,.2f} is excluded or limited by the policy."
        )
        st.caption("Deductible and copayment are policy cost-sharing amounts, not rejected charges. Excluded or policy-limited amounts are charges the policy does not pay.")
        if result["requires_human_review"]:
            st.caption("This is not a final determination. An authorized reviewer must confirm the result.")
        else:
            st.caption("This is decision-support information. Final determination should be confirmed by an authorized reviewer.")
    rules = result.get("rules", {})
    workflow = st.session_state.get(f"workflow_{claim_id}") or {}
    # Persisted claim status includes agent failures and reviewer sign-off, even
    # after a new browser session loses its cached workflow.
    workflow = {**workflow, "decision": {**workflow.get("decision", {}), "status": result["status"]}}
    normalized = st.session_state.get(f"normalized_{claim_id}") or {}
    if rules.get("line_item_reconciliation_failed"):
        st.info(str(rules.get("line_item_notice") or _claim_warning_message("line_item_reconciliation_failed")))
    with st.expander("View amount breakdown", expanded=True):
        st.write(f"Covered amount before deductions: INR {float(rules.get('covered_amount', 0) or 0):,.2f}")
        st.write(f"Deductible: INR {float(result.get('deductible', 0) or 0):,.2f}")
        st.write(f"Copayment: INR {float(result.get('copayment', 0) or 0):,.2f}")
        st.write(f"Excluded or policy-limited amount: INR {float(result.get('amount_excluded_or_limited', 0) or 0):,.2f}")
        st.caption("Claimant responsibility equals deductible, copayment, and any excluded or policy-limited amount.")
        adjustments = []
        for item in rules.get("results", []):
            if item.get("status") in {"partial", "fail"}:
                adjustments.append({"Policy check": str(item.get("rule_id", "")).replace("_", " ").title(), "Effect": item.get("calculation", "Policy adjustment applied"), "Amount affected": item.get("amount")})
        if adjustments:
            st.markdown("#### Items or rules affecting coverage")
            st.dataframe(adjustments, hide_index=True)
        warnings = rules.get("warnings") or []
        if warnings:
            st.write("Calculation notes: " + "; ".join(_claim_warning_message(item) for item in warnings))
    billing_anomalies = normalized.get("billing_anomalies") or {}
    bill_date_value = (normalized.get("bill_date") or {}).get("value")
    try:
        bill_date = date.fromisoformat(str(bill_date_value).replace("/", "-")) if bill_date_value else None
    except ValueError:
        bill_date = None
    submission_deadline = check_submission_deadline(bill_date)
    if submission_deadline:
        st.warning(submission_deadline["warning"])
    duplicate_flags = billing_anomalies.get("duplicates") or normalized.get("duplicate_candidates") or []
    outlier_flags = billing_anomalies.get("price_outliers") or []
    if duplicate_flags or outlier_flags:
        anomaly_messages = []
        for duplicate in duplicate_flags[:3]:
            left = (duplicate.get("left") or {}).get("description") or "an item"
            right = (duplicate.get("right") or {}).get("description") or "another item"
            anomaly_messages.append(f"Possible duplicate charge: {left} and {right}.")
        for outlier in outlier_flags[:3]:
            item = outlier.get("item") or {}
            anomaly_messages.append(f"Price check: {item.get('description') or 'An item'} — {outlier.get('reason') or 'unusual amount'}.")
        st.warning("Billing checks need review:\n\n" + "\n\n".join(anomaly_messages))
    line_item_results = rules.get("line_item_results") or []
    if line_item_results:
        source_items = normalized.get("line_items") or []
        notes_by_index: dict[int, str] = {}
        for note in (workflow.get("decision") or {}).get("line_item_notes") or []:
            if not isinstance(note, dict):
                continue
            try:
                item_index = int(note.get("item_index"))
            except (TypeError, ValueError):
                continue
            note_text = str(note.get("note") or "").strip()
            if 0 <= item_index < len(line_item_results) and note_text:
                notes_by_index[item_index] = note_text
        rows = []
        for index, item_result in enumerate(line_item_results):
            source_item = source_items[index] if index < len(source_items) and isinstance(source_items[index], dict) else {}
            rows.append({
                "Description": str(source_item.get("description") or item_result.get("description") or "Line item"),
                "Amount claimed": float(source_item.get("amount") or item_result.get("amount") or 0),
                "Amount approved": float(item_result.get("covered_amount") or 0),
                "Status": _line_item_status_label(item_result.get("status")),
                "Applied rule": str(item_result.get("applied_rule") or "standard").replace("_", " ").title(),
                "Note": " ".join(part for part in [notes_by_index.get(index, ""), *[str(flag.get("note")) for flag in rules.get("history_flags", []) if flag.get("item_index") == index]] if part),
            })
        with st.expander("Item-wise verification", expanded=False):
            st.caption("Each charge is checked against the available policy terms before claim-level deductible and copayment are applied.")
            st.dataframe(
                rows,
                hide_index=True,
                column_config={
                    "Amount claimed": st.column_config.NumberColumn(format="INR %.2f"),
                    "Amount approved": st.column_config.NumberColumn(format="INR %.2f"),
                    "Status": st.column_config.MarkdownColumn(),
                },
            )
    recommendations = recommend_next_steps(
        workflow.get("decision") or {},
        {**rules, "billing_anomalies": billing_anomalies, "submission_deadline": submission_deadline or {}},
    )
    if recommendations:
        with st.container(border=True):
            st.markdown("### Recommended next steps")
            for index, recommendation in enumerate(recommendations):
                if recommendation.startswith("If your appeal is not resolved"):
                    st.info(recommendation, icon=":material/account_balance:")
                else:
                    st.write(f":material/arrow_forward: {recommendation}")
            confidence = (workflow.get("decision") or {}).get("confidence")
            if confidence is not None:
                st.caption(f"Decision confidence: {float(confidence):.2f} ({confidence_label(float(confidence))})")
            st.caption("This is decision-support information, not legal or insurance advice.")
    with st.container(border=True):
        st.markdown("### Download your claim documents")
        st.caption("Use the decision report to understand the calculation. Use the appeal-letter draft when you need to request a formal review.")
        report_col, appeal_col = st.columns(2, gap="medium")
        with report_col:
            st.download_button(
                "Download decision report (PDF)",
                data=build_decision_report(dict(claim), normalized, rules, workflow),
                file_name=f"{claim['claim_number']}-decision-report.pdf",
                mime="application/pdf",
                icon=":material/download:",
                type="primary",
                use_container_width=True,
                help="A clear summary of the current claim outcome, amounts, reasons, and next steps.",
            )
        with appeal_col:
            st.download_button(
                "Download appeal-letter draft (PDF)",
                data=build_appeal_letter_pdf(dict(claim), rules, workflow),
                file_name=f"{claim['claim_number']}-appeal-letter-draft.pdf",
                mime="application/pdf",
                icon=":material/description:",
                use_container_width=True,
                help="A professional draft you can review and personalize before sending to an insurer.",
            )
    _render_claim_assistant(claim_id, normalized, result, workflow)
    if st.button("Back to dashboard"):
        st.session_state.page = "Dashboard"; st.rerun()


def _render_claim_assistant(claim_id: str, normalized: dict[str, Any], result: dict[str, Any], workflow: dict[str, Any]) -> None:
    """A claimant-facing, evidence-bounded question interface for one claim."""
    with st.container(border=True):
        st.subheader('💬 Ask about this claim', anchor=False)
        st.caption('Ask in plain language. Answers are grounded only in this claim’s documents and decision data. ✨')
        _render_claim_assistant_chat(claim_id, normalized, result, workflow)


def _inr(value: Any) -> str:
    return f"INR {float(value or 0):,.2f}"


def _claim_answer_from_saved_data(question: str, result: dict[str, Any], normalized: dict[str, Any], evidence: list[dict[str, Any]]) -> str | None:
    """Answer stable claim facts without depending on model availability."""
    asked = question.lower().strip()
    amount_words = ("how much", "amount", "claim got", "claim receive", "claim received", "payable", "paid", "payout", "covered", "insurance pay", "insurance cover")
    if any(word in asked for word in amount_words):
        return (
            f"The insurance-covered payable amount is {_inr(result.get('amount_covered'))}. "
            f"The total bill is {_inr(result.get('amount_billed'))}, and the claimant responsibility is {_inr(result.get('amount_claimant_pays'))}."
        )
    if "deductible" in asked:
        return f"The deductible is {_inr(result.get('deductible'))}. It is included in the claimant responsibility."
    if "copay" in asked or "co-pay" in asked:
        return f"The copayment is {_inr(result.get('copayment'))}. It is included in the claimant responsibility."
    if any(word in asked for word in ("excluded", "not covered", "limited")):
        return f"The excluded or policy-limited amount is {_inr(result.get('amount_excluded_or_limited'))}."
    if any(word in asked for word in ("status", "approved", "decision", "result")):
        status = _status_badge(str(result.get('status', 'manual_review')))
        return f"The current claim status is {status}. {result.get('reason') or 'An authorized reviewer should confirm the final determination.'}"
    if "patient" in asked:
        patient = normalized.get('patient_name', {})
        patient = patient.get('value') if isinstance(patient, dict) else patient
        return f"The claim patient is {patient}." if patient else None
    if any(word in asked for word in ("hospital", "provider")):
        hospital = normalized.get('hospital_name', {})
        hospital = hospital.get('value') if isinstance(hospital, dict) else hospital
        return f"The listed provider is {hospital}." if hospital else None
    if any(word in asked for word in ("policy", "coverage", "waiting period", "room limit")) and evidence:
        source = evidence[0]
        clause = str(source.get('text', '')).strip().replace('\n', ' ')
        citation = str(source.get('clause_id') or 'retrieved policy evidence')
        if clause:
            return f"The most relevant policy evidence ({citation}) says: {clause[:550]}"
    return None


def _render_claim_assistant_chat(claim_id: str, normalized: dict[str, Any], result: dict[str, Any], workflow: dict[str, Any]) -> None:
    """The interactive portion is kept separate to retain the result card structure."""
    history_key = f'claim_questions_{claim_id}'
    st.session_state.setdefault(history_key, [])
    for message in st.session_state[history_key]:
        with st.chat_message(message['role']):
            st.write(message['content'])
    with st.form(f'claim_question_form_{claim_id}', border=False):
        question = st.text_input('Your question', placeholder='Why is my claim under review?', key=f'claim_question_input_{claim_id}')
        asked = st.form_submit_button('Ask AI assistant', type='primary', icon=':material/send:')
    if not asked or not question.strip():
        return
    st.session_state[history_key].append({'role': 'user', 'content': question})
    with st.chat_message('user'):
        st.write(question)
    with st.chat_message('assistant', avatar=':material/psychology:'):
        evidence: list[dict[str, Any]] = []
        try:
            evidence = workflow.get('policy_evidence') or retrieve_policy_evidence(saved_policy_text(claim_id), normalized, limit=3, query=question)
        except Exception:
            evidence = []
        answer = _claim_answer_from_saved_data(question, result, normalized, evidence)
        if answer is None:
            try:
                snippets = '\n'.join(f"- {str(item.get('text', ''))[:500]}" for item in evidence)
                if not snippets:
                    raise ValueError('No policy evidence is available for this claim.')
                answer = str(_ollama_json(
                    'You are a medical-insurance claim assistant. Answer only from the supplied claim result and policy evidence. Be concise, use plain language, do not invent coverage, and recommend manual review when evidence is insufficient. The answer field must contain a complete, non-empty answer.',
                    f"Question: {question}\n\nClaim result: {json.dumps(result, ensure_ascii=False)}\n\nPolicy evidence:\n{snippets}",
                    agent_name='claimant_assistant',
                    response_schema={'type': 'object', 'properties': {'answer': {'type': 'string'}}, 'required': ['answer']},
                ).get('answer', '')).strip()
                if not answer:
                    raise ValueError('The assistant did not return an answer.')
            except Exception:
                answer = 'I cannot verify that from the available claim evidence. Please request a manual review so an authorized reviewer can confirm it.'
        st.write(answer)
    st.session_state[history_key].append({'role': 'assistant', 'content': answer})


def _render_dashboard(user: dict) -> None:
    claims = user_claims(user['user_id'], user)
    review_count = sum(1 for c in claims if c['status'] in {'manual_review','ready_for_review','partially_approved'})
    approved = sum(1 for c in claims if c['status'] == 'approved')
    _page_header('OVERVIEW', f'Welcome back, {user["display_name"]}', 'See the status of every claim, then move directly to the next step.', '◈')
    st.markdown('<div class="mg-welcome-note"><span>👋</span><div><b>Your claims, made clearer.</b><small>Track progress, review evidence, and take the next step with confidence.</small></div><span class="mg-welcome-spark">✦</span></div>', unsafe_allow_html=True)
    with st.container(horizontal=True, horizontal_alignment='left'):
        st.metric('Total claims', len(claims), border=True)
        st.metric('Needs attention', review_count, border=True)
        st.metric('Approved claims', approved, border=True)
    with st.container(border=True):
        st.markdown('<div class="mg-section-title">Your claims</div><p class="mg-card-copy">Open a claim to continue the guided review.</p>', unsafe_allow_html=True)
        if not claims:
            st.info("You haven't registered a claim yet. Register your first claim to get started.")
            if st.button('Register a claim', type='primary'): st.session_state.page = 'Register claim'; st.rerun()
        else:
            cols = st.columns(2, gap='medium')
            for i, claim in enumerate(claims[:8]):
                with cols[i % 2]:
                    with st.container(border=True):
                        st.markdown(f"<div class='mg-claim-row'><div><b>{claim['claim_number']}</b><div class='mg-card-copy'>{claim['patient_name']} · {claim['hospital_name'] or 'Provider pending'}</div></div><span class='mg-pill mg-pill-{claim['status']}'>{_status_badge(claim['status'])}</span></div>", unsafe_allow_html=True)
                        x,y = st.columns([3,1])
                        saved_result = _claimant_result_for_claim(claim['claim_id'], user)
                        claim_total = saved_result['amount_billed'] if saved_result else None
                        x.write(f"INR {float(claim_total or 0):,.2f}" if claim_total else 'Amount pending')
                        if y.button('Open', key=f"open_{claim['claim_id']}"):
                            st.session_state.active_claim = claim['claim_id']
                            st.session_state.page = 'Submit documents' if user['role'] == 'claimant' else 'Claim review'
                            st.rerun()
    if user['role'] in {'reviewer','admin'}:
        queue = reviewer_queue(user)
        with st.container(border=True):
            st.markdown('<div class="mg-section-title">Review queue</div><p class="mg-card-copy">Claims awaiting an authorized review.</p>', unsafe_allow_html=True)
            if queue:
                st.dataframe([{'Claim': c['claim_number'], 'Patient': c['patient_name'], 'Status': _status_badge(c['status']), 'Priority': c['review_priority'] if 'review_priority' in c.keys() else 0} for c in queue], hide_index=True)
            else: st.info('No claims are waiting for review.')


def _render_register(user: dict) -> None:
    _page_header('NEW CLAIM', 'Register a claim', 'Start with the essentials. You can attach the bill and policy in the next step.', '+')
    with st.container(border=True):
        st.markdown('<div class="mg-section-title">📝 Claim details</div><p class="mg-card-copy">Fields marked by the workflow are checked against uploaded documents later.</p>', unsafe_allow_html=True)
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
            st.caption('Prototype workflow: inpatient hospitalization claims.')
        st.divider()
        if st.button('Save claim and continue', type='primary', icon=':material/arrow_forward:'):
            if not claim_number.strip() or not patient.strip(): st.error('Claim number and patient name are required.')
            else:
                claim_id = create_claim(user['user_id'], claim_number, patient, hospital, policy, str(incident_date))
                st.session_state.active_claim = claim_id
                st.session_state.page = 'Submit documents' if user['role'] == 'claimant' else 'Claim review'
                st.success('Claim registered. Continue to upload documents.')
                st.rerun()


def _render_claim_submission(user: dict) -> None:
    """Claimant-only submission flow; internal extraction and rules remain hidden."""
    require_role(user, 'claimant')
    claims = user_claims(user['user_id'], user)
    _page_header('DOCUMENTS', 'Submit claim documents', 'Add the policy and bill. We will extract the key details and show a clear result.', '↑')
    if not claims:
        st.info('Register a claim first, then return here to add documents.')
        if st.button('Register a claim', type='primary', icon=':material/add_circle:'):
            st.session_state.page = 'Register claim'; st.rerun()
        return
    options = {f"{claim['claim_number']} · {claim['patient_name']}": claim['claim_id'] for claim in claims}
    labels = list(options)
    default = next((i for i, value in enumerate(options.values()) if value == st.session_state.get('active_claim')), 0)
    selected = st.selectbox('Choose a claim', labels, index=default, key='claimant_submission_selector')
    claim_id = options[selected]
    st.session_state.active_claim = claim_id
    with st.container(border=True):
        st.markdown('<div class="mg-section-title">📎 1. Add your documents</div><p class="mg-card-copy">PDF, PNG, or JPG up to the configured size limit. Upload at least one policy and one bill.</p>', unsafe_allow_html=True)
        st.caption("Privacy notice: documents are stored in this prototype's configured private local storage and processed locally for this claim. Upload only what is needed for your assessment.")
        upload_columns = st.columns(2, gap='medium')
        with upload_columns[0]:
            policy_files = st.file_uploader('Insurance policy', type=['pdf', 'png', 'jpg', 'jpeg'], accept_multiple_files=True, key=f'claimant_policy_{claim_id}')
        with upload_columns[1]:
            bill_files = st.file_uploader('Medical bill and supporting documents', type=['pdf', 'png', 'jpg', 'jpeg'], accept_multiple_files=True, key=f'claimant_bill_{claim_id}')
        if st.button('Save documents', type='primary', icon=':material/save:'):
            files = [(file, 'policy') for file in (policy_files or [])] + [(file, 'medical_bill') for file in (bill_files or [])]
            if not files:
                st.warning('Upload at least one medical bill or policy document.')
            else:
                try:
                    for uploaded, kind in files:
                        save_document(claim_id, user, uploaded, kind)
                    st.success('Documents saved. Submit them when you are ready for assessment.')
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))
    documents = claim_documents(claim_id, user)
    if documents:
        st.caption(f'{len(documents)} document(s) ready for assessment.')
        if st.button('Submit claim for assessment', type='primary', icon=':material/send:'):
            with st.status('Checking your documents and policy…', expanded=True) as status:
                try:
                    normalized = process_claim_documents(claim_id, user['user_id'])
                    rules = evaluate_saved_claim(claim_id, user['user_id'], normalized)
                    st.session_state[f'normalized_{claim_id}'] = normalized
                    st.session_state[f'rules_{claim_id}'] = rules
                    if rules['status'] == 'manual_review':
                        status.update(label='Your claim needs a manual review.', state='complete')
                    else:
                        workflow = run_agents_for_claim(claim_id, user['user_id'], normalized, rules, progress_callback=status.write)
                        st.session_state[f'workflow_{claim_id}'] = workflow
                        status.update(label='Assessment complete.', state='complete')
                    st.session_state.page = 'Claim result'
                    st.rerun()
                except Exception as exc:
                    status.update(label='Assessment needs attention.', state='error')
                    st.error('We could not complete the assessment. Your claim has been kept for review. ' + str(exc))
    else:
        st.info('Upload a policy and a medical bill to begin.')


def _render_claim_review(user: dict) -> None:
    require_role(user, 'reviewer', 'admin')
    claims = user_claims(user['user_id'], user)
    _page_header('REVIEW WORKSPACE', 'Claim review', 'Move from documents to evidence, calculations, and an authorized decision in four clear steps.', '◫')
    if not claims:
        st.info('No claims yet. Register a claim to start the workflow.'); return
    options = {f"{c['claim_number']} · {c['patient_name']}": c['claim_id'] for c in claims}
    labels = list(options); default = next((i for i,v in enumerate(options.values()) if v == st.session_state.get('active_claim')), 0)
    selected = st.selectbox('Selected claim', labels, index=default); claim_id = options[selected]; st.session_state.active_claim = claim_id
    selected_claim = next(c for c in claims if c['claim_id'] == claim_id)
    st.markdown(f"<div class='mg-context'><div><b>{selected_claim['claim_number']}</b><div class='mg-card-copy'>{selected_claim['patient_name']} · {selected_claim['hospital_name'] or 'Provider pending'}</div></div><span class='mg-pill mg-pill-{selected_claim['status']}'>{_status_badge(selected_claim['status'])}</span></div>", unsafe_allow_html=True)
    tabs = st.tabs(['1 · Choose claim', '2 · Add documents', '3 · Check extraction', '4 · Calculate & review'])
    with tabs[0]:
        st.markdown('### Your review path')
        path_columns = st.columns(4, gap='small')
        for column, icon, title, detail in zip(path_columns, [':material/folder_open:', ':material/upload_file:', ':material/document_scanner:', ':material/calculate:'], ['Choose', 'Add', 'Check', 'Decide'], ['Select the claim above.', 'Upload bill and policy.', 'Confirm extracted fields.', 'Run rules and sign off.']):
            with column:
                with st.container(border=True):
                    st.markdown(f'{icon}\n\n**{title}**\n\n{detail}')
    with tabs[1]:
        st.markdown('### Add source documents')
        st.caption('Keep policy and bill separate so the evidence trail stays clear.')
        pcol,bcol = st.columns(2)
        with pcol: policy_files = st.file_uploader('Policy documents', type=['pdf','png','jpg','jpeg'], accept_multiple_files=True, key=f'pol_{claim_id}')
        with bcol: bill_files = st.file_uploader('Medical bill / supporting documents', type=['pdf','png','jpg','jpeg'], accept_multiple_files=True, key=f'bill_{claim_id}')
        if st.button('Save uploaded documents', type='primary'):
            files = [(f,'policy') for f in (policy_files or [])] + [(f,'medical_bill') for f in (bill_files or [])]
            if not files: st.warning('Upload at least one policy or medical bill.')
            else:
                try:
                    for uploaded, kind in files: save_document(claim_id, user, uploaded, kind)
                    st.success(f'Saved {len(files)} document(s).'); st.rerun()
                except (ValueError, PermissionError) as exc: st.error(str(exc))
        docs = claim_documents(claim_id, user)
        if docs: st.dataframe([{'File':d['original_name'],'Type':d['document_type'].replace('_',' ').title(),'Status':_status_badge(d['processing_status'])} for d in docs], hide_index=True)
        else: st.info('Your saved documents will appear here.')
    docs = claim_documents(claim_id, user)
    with tabs[2]:
        normalized = st.session_state.get(f'normalized_{claim_id}')
        if st.button('Run extraction', type='primary'):
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
                if item: fields.append({'Field':key.replace('_',' ').title(),'Value':str(item['value']),'Confidence':round(float(item['confidence']),1),'Review':'Yes' if item['needs_review'] else 'No'})
            with st.container(horizontal=True, horizontal_alignment='left'):
                st.metric('Fields extracted', len(fields), border=True)
                st.metric('Needs review', len(missing), border=True)
                st.metric('Line items', len(normalized.get('line_items',[])), border=True)
            with st.expander('Extracted summary', expanded=True): st.dataframe(fields, hide_index=True)
            with st.expander(f"Line items ({len(normalized.get('line_items',[]))}"): st.dataframe([{k:i.get(k) for k in ('description','amount','category','confidence','needs_review')} for i in normalized.get('line_items',[])], hide_index=True)
            with st.expander('Field-by-field evidence'): st.json(normalized)
        else: st.info('Run extraction after saving documents.')
    with tabs[3]:
        normalized = st.session_state.get(f'normalized_{claim_id}')
        rules = st.session_state.get(f'rules_{claim_id}')
        if not normalized: st.warning('Complete extraction before analysis.'); return
        if st.button('Run deterministic coverage rules', type='primary'):
            with st.status('Applying policy rules...', expanded=True) as status:
                try: rules=evaluate_saved_claim(claim_id,user['user_id'],normalized); st.session_state[f'rules_{claim_id}']=rules; status.update(label='Rules complete',state='complete')
                except Exception as exc: status.update(label='Rules failed',state='error'); st.error(str(exc))
        if rules:
            st.markdown(f"<div class='mg-section-title'>Deterministic result <span class='mg-pill mg-pill-{rules['status']}'>{_status_badge(rules['status'])}</span></div>", unsafe_allow_html=True)
            with st.container(horizontal=True, horizontal_alignment='left'):
                st.metric('Covered',f"INR {rules.get('covered_amount',0):,.2f}", border=True)
                st.metric('Deductible',f"INR {rules.get('deductible',0):,.2f}", border=True)
                st.metric('Copayment',f"INR {rules.get('copayment',0):,.2f}", border=True)
                st.metric('Payable',f"INR {rules.get('payable_amount',0):,.2f}", border=True)
            if rules.get('warnings'): st.warning('; '.join(rules['warnings']))
            with st.expander('Why this result? Rule trace', expanded=True): st.dataframe(rules.get('results',[]), hide_index=True)
            workflow=st.session_state.get(f'workflow_{claim_id}')
            if st.button('Run Policy Agent + Decision Agent', type='primary'):
                with st.status('Retrieving policy evidence...', expanded=True) as status:
                    st.caption('Local AI processing can take 1–2 minutes on CPU. Keep this page open while it completes.')
                    try:
                        started=time.perf_counter(); workflow=run_agents_for_claim(claim_id,user['user_id'],normalized,rules,progress_callback=lambda msg: status.write(msg)); workflow['elapsed_seconds']=round(time.perf_counter()-started,2); st.session_state[f'workflow_{claim_id}']=workflow; status.update(label='Two-agent analysis complete',state='complete')
                    except Exception as exc: status.update(label='Agent workflow failed',state='error'); st.error(str(exc))
            if workflow:
                decision=workflow.get('decision',{}); st.markdown(f"<div class='mg-section-title'>Evidence-based recommendation <span class='mg-pill mg-pill-{decision.get('status','manual_review')}'>{_status_badge(decision.get('status','manual_review'))}</span></div>", unsafe_allow_html=True)
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
    _page_header('POLICY LIBRARY', 'Policy management', 'Ingest the active policy edition that supplies evidence and deterministic coverage terms.', '≡')
    with st.container(border=True):
        st.markdown('### Ingest New Policy Edition')
        with st.form('policy_ingestion_form'):
            policy_file=st.file_uploader('Policy document',type=['pdf','png','jpg','jpeg']); a,b,c=st.columns(3)
            with a: policy_number=st.text_input('Policy number',placeholder='POL-DEMO-2026-001'); version_label=st.text_input('Version label',placeholder='2026 Edition')
            with b: insurer=st.text_input('Insurer',placeholder='Example Health Insurance Ltd.'); effective_date=st.date_input('Effective date')
            with c: st.info('The active edition supplies authoritative rule terms.'); submitted=st.form_submit_button('Ingest & activate edition',type='primary')
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
            st.dataframe(rows,hide_index=True)
            active=[v for v in versions if v['status']=='active']
            if active and user['role']=='admin':
                chosen=st.selectbox('Archive an active edition',['Select an edition']+[f"{v['policy_number']} — {v['version_label']}" for v in active])
                if chosen!='Select an edition' and st.button('Archive edition'): archive_policy_version(next(v['version_id'] for v in active if f"{v['policy_number']} — {v['version_label']}"==chosen),user=user); st.success('Edition archived.'); st.rerun()


def _render_admin_panel(user: dict) -> None:
    require_role(user,'admin')
    _page_header('ADMINISTRATION', 'Team access', 'Manage reviewer access and view the accounts available in this local prototype.', '◉')
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
        st.dataframe([{'Name':u['display_name'],'Email':u['email'],'Role':u['role'].title(),'Status':'Active' if u['is_active'] else 'Inactive','Created':u['created_at']} for u in users],hide_index=True)
        st.info('User and invitation activity is logged for security and cannot be silently deleted.')


def main() -> None:
    st.set_page_config(page_title='Medi Gaurd AI', page_icon='🛡️', layout='wide', initial_sidebar_state='expanded')
    st.markdown('''<style>
    :root { --ink:#102a2b; --muted:#5d7474; --teal:#0f766e; --teal-dark:#073b3a; --mint:#dff6f1; --line:#cfe1df; --paper:#ffffff; --canvas:#f4f8f8; }
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background:var(--canvas); color:var(--ink); }
    .block-container { max-width:1280px; padding:2.4rem 3rem 4rem; }
    [data-testid="stSidebar"] { background:linear-gradient(180deg,#073b3a 0%,#0b504e 100%); }
    [data-testid="stSidebarContent"] { padding:1.6rem 1.05rem; }
    [data-testid="stSidebar"] * { color:#effffd!important; }
    [data-testid="stSidebar"] .stRadio label { padding:.68rem .78rem; border-radius:12px; margin:.13rem 0; font-size:.9rem; transition:background .18s ease; }
    [data-testid="stSidebar"] .stRadio label:hover { background:rgba(255,255,255,.1); }
    [data-testid="stSidebar"] .stRadio label:has(input:checked) { background:rgba(94,234,212,.18); box-shadow:inset 3px 0 #5eead4; }
    .mg-brand-head { display:flex; gap:.72rem; align-items:center; padding:.15rem .35rem 1.65rem; }
    .mg-brand-name { font-size:1.08rem; font-weight:800; letter-spacing:-.02em; }
    .mg-brand-sub { font-size:.69rem; opacity:.78; margin-top:.12rem; }
    .mg-logo-mark { width:2.35rem; height:2.35rem; display:grid; place-items:center; color:#5eead4!important; filter:drop-shadow(0 8px 18px rgba(0,0,0,.22)); }.mg-logo-mark svg { width:100%; height:100%; }
    .mg-shield { width:2.3rem; height:2.3rem; display:grid; place-items:center; border-radius:13px; background:#5eead4; color:#073b3a!important; font-weight:800; box-shadow:0 8px 24px rgba(0,0,0,.18); }
    .mg-nav-label, .mg-eyebrow, .mg-auth-kicker { font-size:.68rem; letter-spacing:.14em; font-weight:800; color:var(--teal); }
    .mg-nav-label { color:#9fe9dc!important; opacity:.78; padding:.25rem .35rem; }
    .mg-sidebar-spacer { height:24vh; }.mg-sidebar-foot { font-size:.7rem; opacity:.78; border-top:1px solid rgba(255,255,255,.18); padding:1rem .35rem 0; margin-top:1rem; }
    .mg-page-header { display:flex; gap:1rem; align-items:flex-start; margin:.15rem 0 2rem; }
    .mg-header-icon { width:3rem; height:3rem; display:grid; place-items:center; flex:0 0 auto; border-radius:15px; color:#0f766e; background:var(--mint); font-size:1.3rem; }
    h1 { color:var(--ink); letter-spacing:-.045em; margin:0 0 .18rem!important; } h2,h3 { color:var(--ink); }
    .mg-subtitle { color:var(--muted); font-size:1rem; margin:0; max-width:760px; line-height:1.55; }
    .mg-section-title { color:var(--ink); font-size:1.12rem; font-weight:800; letter-spacing:-.015em; margin-bottom:.25rem; }.mg-card-copy { color:var(--muted); font-size:.84rem; line-height:1.45; margin:.15rem 0 .8rem; }
    [data-testid="stMetric"], [data-testid="stVerticalBlockBorderWrapper"] { background:var(--paper); border-color:var(--line)!important; border-radius:16px!important; box-shadow:0 10px 28px rgba(18,71,68,.045); }
    [data-testid="stMetric"] { min-width:190px; padding:1.05rem 1.15rem; } [data-testid="stMetricLabel"] { color:var(--muted); font-size:.8rem; } [data-testid="stMetricValue"] { color:var(--ink); font-weight:800; }
    .mg-context { display:flex; justify-content:space-between; align-items:center; gap:1rem; background:linear-gradient(100deg,#fff,#f8fcfb); border:1px solid var(--line); border-radius:15px; padding:.9rem 1rem; margin:1rem 0 1.4rem; }
    .mg-claim-row { display:flex; justify-content:space-between; align-items:flex-start; gap:.6rem; }
    .mg-pill { display:inline-flex; align-items:center; border-radius:999px; padding:.28rem .58rem; font-size:.71rem; font-weight:800; white-space:nowrap; }
    .mg-pill-approved { color:#167052; background:#dcfce7; }.mg-pill-partially_approved,.mg-pill-manual_review,.mg-pill-ready_for_review { color:#9a5d00; background:#fef3c7; }.mg-pill-rejected { color:#b42318; background:#fee4e2; }.mg-pill-extracted { color:#1d4ed8; background:#dbeafe; }.mg-pill-draft { color:#475569; background:#e2e8f0; }
    .stButton>button { min-height:2.65rem; padding:.55rem 1rem; border-radius:12px; font-weight:700; transition:transform .16s ease, box-shadow .16s ease; }.stButton>button:hover { transform:translateY(-1px); box-shadow:0 8px 16px rgba(15,118,110,.12); }
    .stButton>button[kind="primary"] { background:var(--teal); border-color:var(--teal); }.stButton>button[kind="primary"]:hover { background:#0b625c; border-color:#0b625c; }
    [data-testid="stTabs"] [role="tab"] { font-weight:700; color:var(--muted); padding:.8rem 1rem; } [data-testid="stTabs"] [aria-selected="true"] { color:var(--teal)!important; border-bottom-color:var(--teal)!important; }
    [data-testid="stExpander"] { border:1px solid var(--line); border-radius:14px; background:#fff; overflow:hidden; }
    [data-testid="stFileUploaderDropzone"] { background:#f9fdfc; border:1.5px dashed #8bc5bb; border-radius:14px; padding:1.25rem; }
    .stTextInput input,.stTextArea textarea,.stDateInput input,[data-baseweb="select"]>div { background:#fff!important; border-color:#bcd7d2!important; border-radius:11px!important; }
    .stTextInput input:focus,.stTextArea textarea:focus,.stDateInput input:focus { border-color:var(--teal)!important; box-shadow:0 0 0 3px rgba(15,118,110,.12)!important; }
    [data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:12px; overflow:hidden; }
    .mg-landing { position:relative; overflow:hidden; min-height:540px; border-radius:24px; padding:3.2rem 2.5rem; background:radial-gradient(circle at 80% 20%,#b9f3e7 0,transparent 28%),linear-gradient(145deg,#073b3a,#0f766e); color:#effffd; box-shadow:0 20px 48px rgba(7,59,58,.2); }.mg-landing h1 { color:#fff; margin-top:2.2rem!important; font-size:3rem; max-width:460px; }.mg-landing-badge { display:inline-block; padding:.42rem .7rem; border-radius:999px; background:rgba(255,255,255,.12); font-size:.78rem; }.mg-landing-art { position:absolute; right:1.3rem; bottom:1.4rem; width:155px; height:145px; pointer-events:none; }.mg-landing-art span { position:absolute; display:grid; place-items:center; width:58px; height:58px; border-radius:19px; background:rgba(255,255,255,.13); border:1px solid rgba(255,255,255,.18); box-shadow:0 12px 26px rgba(0,0,0,.13); font-size:1.65rem; animation:mg-float 4.6s ease-in-out infinite; }.mg-landing-art span:nth-child(1){top:6px;left:15px}.mg-landing-art span:nth-child(2){top:44px;right:4px;animation-delay:-1.1s}.mg-landing-art span:nth-child(3){bottom:0;left:0;animation-delay:-2.3s}.mg-landing-art span:nth-child(4){bottom:3px;right:36px;animation-delay:-3.2s}.mg-landing .large { margin:2.5rem 0 0; width:3.5rem; height:3.5rem; font-size:1.45rem; background:#fff; }.mg-tagline { max-width:390px; line-height:1.65; color:#d9fbf5; font-size:1.02rem; }.mg-landing-points { display:flex; gap:.55rem; flex-wrap:wrap; margin:2.1rem 0 1.5rem; }.mg-landing-points span { padding:.42rem .6rem; border:1px solid rgba(255,255,255,.18); border-radius:10px; font-size:.77rem; }.mg-promise { color:#bdf4e9; font-weight:700; }
    .mg-welcome-note { display:flex; align-items:center; gap:.65rem; max-width:675px; padding:.7rem .9rem; margin:-.8rem 0 1.3rem; border:1px solid #c8e8e1; border-radius:14px; background:linear-gradient(90deg,#edfcf8,#f8fffd); color:#245b58; }.mg-welcome-note>span:first-child { display:grid; place-items:center; width:2rem; height:2rem; border-radius:10px; background:#d5f7ef; font-size:1.05rem; }.mg-welcome-note b { display:block; font-size:.83rem; }.mg-welcome-note small { display:block; margin-top:.12rem; color:var(--muted); font-size:.76rem; }.mg-welcome-spark { margin-left:auto; color:#0f766e; font-size:1.15rem; animation:mg-pulse 2.4s ease-in-out infinite; }
    @keyframes mg-float { 0%,100%{transform:translateY(0) rotate(0)}50%{transform:translateY(-7px) rotate(3deg)} } @keyframes mg-pulse { 0%,100%{transform:scale(1);opacity:.7}50%{transform:scale(1.24);opacity:1} }
    .mg-auth-title { color:var(--ink); font-size:2rem; font-weight:800; letter-spacing:-.04em; margin-top:2.6rem; }.mg-auth-copy { color:var(--muted); margin:.45rem 0 1.5rem; }
    .mg-opening { position:relative; overflow:hidden; max-width:930px; min-height:570px; margin:3vh auto 0; padding:5.2rem 8%; border-radius:30px; background:radial-gradient(circle at 80% 18%,rgba(130,246,221,.29),transparent 20%),radial-gradient(circle at 12% 90%,rgba(35,149,142,.25),transparent 26%),linear-gradient(140deg,#073b3a,#0c5d59); color:#effffd; box-shadow:0 26px 70px rgba(7,59,58,.22); text-align:center; }.mg-opening-logo { position:relative; z-index:1; display:grid; place-items:center; width:86px; height:86px; margin:0 auto 1.35rem; border-radius:27px; background:#5eead4; color:#0b4d4a; box-shadow:0 13px 32px rgba(0,0,0,.2); }.mg-opening-logo svg { width:66px; height:66px; }.mg-opening-brand { position:relative; z-index:1; color:#a8f1e3; font-size:.73rem; letter-spacing:.2em; font-weight:800; }.mg-opening h1 { position:relative; z-index:1; max-width:720px; margin:1.1rem auto .85rem!important; color:#fff; font-size:clamp(2.7rem,6vw,5rem); line-height:1.02; }.mg-opening h1 em { font-style:normal; color:#7ae6d3; }.mg-opening p { position:relative; z-index:1; max-width:560px; margin:0 auto; color:#d9fbf5; font-size:1.08rem; line-height:1.65; }.mg-opening-chips { position:relative; z-index:1; display:flex; justify-content:center; gap:.55rem; flex-wrap:wrap; margin-top:2.15rem; }.mg-opening-chips span { padding:.52rem .76rem; border:1px solid rgba(255,255,255,.18); border-radius:999px; background:rgba(255,255,255,.09); font-size:.8rem; }.mg-opening-orb { position:absolute; border-radius:999px; background:rgba(111,234,210,.12); filter:blur(1px); }.orb-one { width:280px; height:280px; right:-95px; top:-80px; }.orb-two { width:180px; height:180px; left:-50px; bottom:-70px; }.mg-role-label { margin:1.25rem auto .35rem; color:#0f766e; text-align:center; font-size:.7rem; font-weight:800; letter-spacing:.14em; }.mg-role-label + div [role="radiogroup"] { justify-content:center; gap:.5rem; }.mg-role-label + div [role="radio"] { border:1px solid #bcded7; border-radius:12px; padding:.6rem .75rem; background:#fff; font-weight:700; }.mg-role-label + div [role="radio"]:has(input:checked) { border-color:#0f766e; background:#eafaf6; color:#0b625c; }.mg-opening + div .stButton { max-width:250px; margin:1.35rem auto .35rem; }.mg-opening + div .stButton button { min-height:3.2rem; font-size:1rem; }
    @media(max-width:800px) { .block-container{padding:1.25rem 1rem 3rem}.mg-page-header{margin-bottom:1.3rem}.mg-header-icon{width:2.5rem;height:2.5rem}.mg-landing{min-height:auto;padding:2.2rem 1.5rem}.mg-landing h1{font-size:2.3rem}.mg-landing-art{opacity:.54;transform:scale(.82);transform-origin:bottom right}.mg-welcome-note small{font-size:.7rem}.mg-opening{min-height:500px;margin:1vh auto 0;padding:4rem 1.35rem;border-radius:22px}.mg-opening p{font-size:.98rem}.mg-sidebar-spacer{height:12vh;} }
    </style>''', unsafe_allow_html=True)
    init_db(); validate_security_config(); bootstrap_admin_from_env()
    if not st.session_state.get('welcome_seen') and not (st.query_params.get('reset_token') or st.query_params.get('setup_token')):
        _render_welcome()
        return
    if core_demo_mode():
        _core_demo_user()
    if 'user' not in st.session_state:
        _render_login(); return
    user=st.session_state.user; page=_render_sidebar(user)
    if page=='Dashboard': _render_dashboard(user)
    elif page=='Register claim': _render_register(user)
    elif page=='Submit documents': _render_claim_submission(user)
    elif page=='Claim review': _render_claim_review(user)
    elif page=='Claim result': _render_claimant_result(user)
    elif page=='Policy management': _render_policy_management(user)
    elif page=='Admin panel': _render_admin_panel(user)


if __name__ == '__main__':
    main()
