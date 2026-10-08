import base64
import hashlib
import hmac
import html
import json
import logging
import secrets
import os
import re
import sqlite3
import time
import uuid
from datetime import date, datetime, timezone
from dataclasses import fields, is_dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from extraction import check_submission_deadline, parse_amount, parse_bill_date, run_extraction
from rules import evaluate_claim
from agents import _ollama_json, confidence_label, explain_comparison, recommend_next_steps, retrieve_policy_evidence, run_claim_workflow, warm_ollama
from policy_index import index_policy_documents, retrieve_policy_evidence as retrieve_indexed_policy_evidence
from extraction import extract_document
from category_names import ROOM_CATEGORY, normalize_category
from policy_terms import extract_policy_terms, terms_from_json
from reports import (build_decision_report,
    build_comparison_appeal_letter_text, build_comparison_appeal_letter_pdf,
    build_comparison_appeal_letter_docx, build_hospital_note_text,
    build_hospital_note_pdf, build_hospital_note_docx)
from comparison import compare as compare_claim_settlement
from models import (CategoryComparison, ClaimResult, Clause, ComparisonResult, LineItem,
                    LineResult, PolicyTerms as TypedPolicyTerms, SettlementData, SettlementDeduction)
from settlement import parse_settlement
from ui.components import (
    _brand_header, _claimant_progress, _line_item_status_label, _page_header,
    _safe_status, _status_badge, _status_color, auth_portal_html, claim_context_html,
    claim_row_html, deterministic_result_header_html, evidence_recommendation_header_html, page_header_html,
)

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
    return os.getenv("MEDIGUARD_CORE_DEMO", "false").lower() == "true"


def dev_show_links() -> bool:
    return os.getenv("MEDIGUARD_DEV_SHOW_LINKS", "false").lower() == "true"


def password_reset_link_for_display(request: dict[str, Any]) -> str | None:
    token = request.get("reset_token")
    if not dev_show_links() or not token:
        return None
    return f"{APP_BASE_URL}/?reset_token={token}"


def _render_password_reset_link(request: dict[str, Any]) -> None:
    link = password_reset_link_for_display(request)
    if link:
        st.code(link)


def reviewer_invitation_link(user: dict | sqlite3.Row, invitation: dict[str, Any]) -> str:
    require_role(user, "admin")
    return f"{APP_BASE_URL}/?setup_token={invitation['setup_token']}"


def trusted_fixtures_enabled() -> bool:
    return os.getenv("MEDIGUARD_TRUSTED_FIXTURES", "false").lower() == "true"


def trusted_fixture_hashes() -> set[str]:
    path = APP_DIR / "config" / "trusted_fixtures.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    hashes = payload.get("sha256", []) if isinstance(payload, dict) else []
    return {str(value).lower() for value in hashes if re.fullmatch(r"[a-fA-F0-9]{64}", str(value))}


def is_trusted_fixture_hash(value: str | None) -> bool:
    return bool(value and value.lower() in trusted_fixture_hashes())


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
    normalized_email = email.strip().lower()
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - 15 * 60
    with db() as conn:
        attempt = conn.execute("SELECT * FROM login_attempts WHERE email=?", (normalized_email,)).fetchone()
        if attempt and attempt["blocked_until"]:
            if datetime.fromisoformat(attempt["blocked_until"]) > now:
                return None
        window_started = datetime.fromisoformat(attempt["window_started"]).timestamp() if attempt else 0
        failed_count = int(attempt["failed_count"]) if attempt and window_started >= cutoff else 0
        if failed_count == 0:
            window_started_iso = now.isoformat()
        else:
            window_started_iso = attempt["window_started"]
        user = conn.execute("SELECT * FROM users WHERE email=?", (normalized_email,)).fetchone()
        valid = bool(user and user["is_active"] and _verify_password(password, user["password_hash"]))
        if valid:
            conn.execute("DELETE FROM login_attempts WHERE email=?", (normalized_email,))
            return user
        failed_count += 1
        blocked_until = (now + __import__("datetime").timedelta(minutes=15)).isoformat() if failed_count >= 5 else None
        conn.execute(
            "INSERT INTO login_attempts(email,failed_count,window_started,blocked_until) VALUES(?,?,?,?) "
            "ON CONFLICT(email) DO UPDATE SET failed_count=excluded.failed_count,window_started=excluded.window_started,blocked_until=excluded.blocked_until",
            (normalized_email, failed_count, window_started_iso, blocked_until),
        )
        return None


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
        logging.getLogger(__name__).info("Password reset token issued for user_id=%s", user["user_id"])
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
        logging.getLogger(__name__).info("Reviewer invitation token issued for user_id=%s", user_id)
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
    storage_dir = get_storage_dir()
    upload_dir = get_upload_dir()
    if storage_dir == APP_DIR or any(part.lower() in {"public", "static"} for part in storage_dir.parts):
        raise RuntimeError("MEDIGUARD_STORAGE_DIR must be a private directory outside public/static paths.")
    storage_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)


def bootstrap_admin_from_env() -> None:
    email = os.getenv("MEDIGUARD_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("MEDIGUARD_ADMIN_PASSWORD", "")
    if not email or not password:
        return
    password_hash = _hash_password(password)
    user_id = hashlib.sha256(email.encode()).hexdigest()[:24]
    with db() as conn:
        conn.execute("INSERT INTO users(user_id,email,display_name,role,password_hash,created_at) VALUES(?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET role='admin', password_hash=excluded.password_hash", (user_id, email, "MediGuard Administrator", "admin", password_hash, utc_now()))


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
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS login_attempts (
                email TEXT PRIMARY KEY,
                failed_count INTEGER NOT NULL DEFAULT 0,
                window_started TEXT NOT NULL,
                blocked_until TEXT
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
            CREATE TABLE IF NOT EXISTS settlement_comparisons (
                claim_id TEXT PRIMARY KEY,
                settlement_document_sha256 TEXT NOT NULL,
                settlement_json TEXT NOT NULL,
                comparison_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(claim_id) REFERENCES claims(claim_id)
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
                policy_version_id TEXT,
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
                page_count INTEGER,
                content_text TEXT NOT NULL,
                indexed_chunks INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                policy_terms_json TEXT,
                terms_review_status TEXT NOT NULL DEFAULT 'pending',
                reviewed_policy_terms_json TEXT,
                terms_reviewed_by TEXT,
                terms_reviewed_at TEXT
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
            CREATE TABLE IF NOT EXISTS claim_extraction_reviews (
                claim_id TEXT NOT NULL,
                field_name TEXT NOT NULL,
                confirmed_value_json TEXT NOT NULL,
                document_id TEXT,
                page_number INTEGER,
                reviewer_id TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(claim_id, field_name),
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
        for column, definition in (("policy_version_id", "TEXT"),):
            try:
                conn.execute(f"ALTER TABLE claims ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError:
                pass
        for column, definition in (("password_hash", "TEXT"), ("is_active", "INTEGER NOT NULL DEFAULT 1"), ("password_set_at", "TEXT"), ("disabled_at", "TEXT")):
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError:
                pass
        for column, definition in (
            ("policy_terms_json", "TEXT"),
            ("page_count", "INTEGER"),
            ("terms_review_status", "TEXT NOT NULL DEFAULT 'pending'"),
            ("reviewed_policy_terms_json", "TEXT"),
            ("terms_reviewed_by", "TEXT"),
            ("terms_reviewed_at", "TEXT"),
        ):
            try:
                conn.execute(f"ALTER TABLE policy_versions ADD COLUMN {column} {definition}")
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


def _validated_upload(uploaded_file, document_type: str | None = None) -> tuple[bytes, str]:
    original_name = Path(uploaded_file.name).name
    extension = Path(original_name).suffix.lower()
    allowed = {".pdf", ".txt"} if document_type == "settlement" else {".pdf", ".png", ".jpg", ".jpeg"}
    if extension not in allowed:
        message = "Settlement letter must be a PDF or UTF-8 text file." if document_type == "settlement" else "Unsupported file type. Upload a PDF, PNG, JPG, or JPEG file."
        raise ValueError(message)
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
    if document_type == "settlement" and extension == ".txt":
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Settlement text must use UTF-8 encoding.") from exc
    return content, original_name


def save_document(claim_id: str, user: dict | sqlite3.Row, uploaded_file, document_type: str) -> None:
    _claim_access(claim_id, user, write=True)
    user_id = user["user_id"]
    content, safe_name = _validated_upload(uploaded_file, document_type=document_type)
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
    allowed = {"network_status", "preauthorization_status", "preauthorization_reference", "waiting_period_status", "source", "trusted", "aggregation_confirmed", "duplicate_suspected"}
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


def apply_claim_extraction_reviews(claim_id: str, normalized: dict) -> dict:
    """Overlay reviewer-confirmed bill values while retaining source provenance."""
    with db() as conn:
        rows = conn.execute(
            "SELECT field_name,confirmed_value_json,document_id,page_number FROM claim_extraction_reviews WHERE claim_id=?",
            (claim_id,),
        ).fetchall()
    reviewed_fields = set()
    for row in rows:
        name = str(row["field_name"])
        try:
            value = json.loads(row["confirmed_value_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        evidence = [{
            "document_id": row["document_id"] or "reviewer-confirmed",
            "source_name": "Reviewer confirmation",
            "page": row["page_number"],
            "method": "reviewer_confirmed",
            "text": "Value confirmed by an authorized reviewer against the source page.",
            "confidence": 100.0,
        }]
        if name == "line_items":
            normalized["line_items"] = value if isinstance(value, list) else []
        else:
            normalized[name] = {"name": name, "value": value, "confidence": 100.0, "needs_review": False, "evidence": evidence}
        reviewed_fields.add(name)
    missing = set(normalized.get("missing_fields") or [])
    for required in ("patient_name", "hospital_name", "total_amount"):
        item = normalized.get(required)
        if item and item.get("value") not in (None, ""):
            missing.discard(required)
        else:
            missing.add(required)
    normalized["missing_fields"] = sorted(missing)
    normalized["review_fields"] = [
        field for field in (normalized.get("review_fields") or [])
        if field not in reviewed_fields
    ]
    if "line_items" in reviewed_fields and normalized.get("line_items"):
        normalized["review_fields"] = [field for field in normalized["review_fields"] if field != "line_items"]
    return normalized


def save_claim_extraction_review(claim_id: str, reviewer_id: str, edits: dict[str, dict[str, Any]]) -> None:
    reviewer = get_user(reviewer_id)
    require_role(reviewer, "reviewer", "admin")
    _claim_access(claim_id, reviewer, write=True)
    allowed = {"patient_name", "hospital_name", "policy_number", "claim_number", "admission_date", "discharge_date", "bill_date", "diagnosis", "total_amount", "line_items"}
    now = utc_now()
    reviewed_names = []
    with db() as conn:
        for name, edit in edits.items():
            if name not in allowed:
                continue
            value = edit.get("value")
            page = int(edit.get("page") or 1)
            if page < 1:
                raise ValueError("Source page must be at least 1.")
            document = conn.execute("SELECT document_type,page_count FROM documents WHERE document_id=? AND claim_id=?", (edit.get("document_id"), claim_id)).fetchone()
            if document is None or document["document_type"] != "medical_bill":
                raise ValueError("Choose a bill document attached to this claim as the source.")
            if document["page_count"] and page > int(document["page_count"]):
                raise ValueError("Source page is beyond the uploaded bill's page count.")
            if name == "line_items":
                clean_items = []
                for item in value or []:
                    description = str(item.get("description") or "").strip()
                    amount = parse_amount(str(item.get("amount") or ""))
                    if not description and amount is None:
                        continue
                    if not description or amount is None or amount <= 0:
                        raise ValueError("Each reviewed bill line needs a description and a positive amount.")
                    item_page = int(item.get("source_page") or page)
                    if item_page < 1 or (document["page_count"] and item_page > int(document["page_count"])):
                        raise ValueError("A line-item source page is outside the bill.")
                    clean_items.append({
                        "description": description[:180],
                        "amount": amount,
                        "category": str(item.get("category") or "other").strip().lower()[:40],
                        "cpt_codes": [],
                        "date": None,
                        "confidence": 100.0,
                        "needs_review": False,
                        "evidence": [{"document_id": edit.get("document_id"), "source_name": "Reviewer confirmation", "page": item_page, "method": "reviewer_confirmed", "text": "Line item confirmed by an authorized reviewer.", "confidence": 100.0}],
                    })
                value = clean_items
            elif name == "total_amount":
                value = parse_amount(str(value or ""))
                if value is None or value <= 0:
                    raise ValueError("Enter a positive bill total before saving the reviewed extraction.")
            else:
                value = str(value or "").strip()
                if not value:
                    continue
            conn.execute(
                "INSERT INTO claim_extraction_reviews(claim_id,field_name,confirmed_value_json,document_id,page_number,reviewer_id,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(claim_id,field_name) DO UPDATE SET confirmed_value_json=excluded.confirmed_value_json,document_id=excluded.document_id,page_number=excluded.page_number,reviewer_id=excluded.reviewer_id,updated_at=excluded.updated_at",
                (claim_id, name, json.dumps(value, ensure_ascii=False), edit.get("document_id"), page, reviewer_id, now),
            )
            if name in {"patient_name", "hospital_name", "policy_number"}:
                if name == "policy_number":
                    conn.execute("UPDATE claims SET policy_number=?,policy_version_id=NULL,updated_at=? WHERE claim_id=?", (str(value), now, claim_id))
                else:
                    conn.execute(f"UPDATE claims SET {name}=?, updated_at=? WHERE claim_id=?", (str(value), now, claim_id))
            reviewed_names.append(name)
        conn.execute(
            "INSERT INTO audit_events VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), claim_id, reviewer_id, "claim_extraction_reviewed", json.dumps({"fields": reviewed_names}), now),
        )


def save_policy_terms_review(version_id: str, reviewer_id: str, values: dict[str, Any], source_pages: dict[str, int], sub_limits: dict[str, Any]) -> str:
    reviewer = get_user(reviewer_id)
    require_role(reviewer, "reviewer", "admin")
    with db() as conn:
        policy = conn.execute("SELECT * FROM policy_versions WHERE version_id=?", (version_id,)).fetchone()
        if policy is None:
            raise ValueError("Policy edition was not found.")
        reviewed = {}
        for name in ("annual_limit", "deductible", "copay_percent", "room_limit_per_day", "waiting_period_months"):
            raw = values.get(name)
            if raw in (None, ""):
                continue
            parsed_number = parse_amount(str(raw))
            if parsed_number is None:
                raise ValueError(f"Enter a numeric value for {name.replace('_', ' ')}.")
            number = float(parsed_number)
            if number < 0:
                raise ValueError(f"{name.replace('_', ' ').title()} cannot be negative.")
            if name == "copay_percent" and number > 100:
                raise ValueError("Co-payment must be between 0 and 100 percent.")
            page = int(source_pages.get(name) or 0)
            if page < 1:
                raise ValueError(f"Add the source page for {name.replace('_', ' ')}.")
            if policy["page_count"] and page > int(policy["page_count"]):
                raise ValueError(f"The source page for {name.replace('_', ' ')} is beyond this policy document.")
            value = int(number) if name == "waiting_period_months" else number
            reviewed[name] = {"term": name, "value": value, "confidence": 1.0, "source_page": page, "source_name": policy["source_name"], "method": "reviewer_confirmed"}
        clean_sub_limits = {}
        for category, amount in (sub_limits or {}).items():
            category = str(category).strip().lower()
            parsed_amount = parse_amount(str(amount))
            if parsed_amount is None:
                raise ValueError(f"Enter a numeric amount for the {category or 'unnamed'} sub-limit.")
            amount = float(parsed_amount)
            if category and amount >= 0:
                clean_sub_limits[category] = amount
        if clean_sub_limits:
            page = int(source_pages.get("sub_limits") or 0)
            if page < 1:
                raise ValueError("Add the source page for the sub-limits.")
            if policy["page_count"] and page > int(policy["page_count"]):
                raise ValueError("The sub-limits source page is beyond this policy document.")
            reviewed["sub_limits"] = {"term": "sub_limits", "value": clean_sub_limits, "confidence": 1.0, "source_page": page, "source_name": policy["source_name"], "method": "reviewer_confirmed"}
        core = {"annual_limit", "deductible", "copay_percent"}
        status = "confirmed" if core.issubset(reviewed) else "pending"
        now = utc_now()
        conn.execute(
            "UPDATE policy_versions SET reviewed_policy_terms_json=?,terms_review_status=?,terms_reviewed_by=?,terms_reviewed_at=? WHERE version_id=?",
            (json.dumps(reviewed, ensure_ascii=False), status, reviewer_id, now if status == "confirmed" else None, version_id),
        )
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), None, reviewer_id, "policy_terms_reviewed", json.dumps({"version_id": version_id, "fields": sorted(reviewed), "status": status}), now))
    return status


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


def link_policy_version_to_claim(claim_id: str, reviewer_id: str, version_id: str) -> None:
    reviewer = get_user(reviewer_id)
    require_role(reviewer, "reviewer", "admin")
    claim = _claim_access(claim_id, reviewer, write=True)
    with db() as conn:
        policy = conn.execute("SELECT * FROM policy_versions WHERE version_id=?", (version_id,)).fetchone()
        if policy is None:
            raise ValueError("Choose an existing policy edition.")
        claim_number = str(claim["policy_number"] or "").strip()
        if claim_number and claim_number.casefold() != str(policy["policy_number"]).strip().casefold():
            raise ValueError("The selected policy number does not match the registered claim. Correct the claim policy number first.")
        now = utc_now()
        conn.execute("UPDATE claims SET policy_number=?,policy_version_id=?,updated_at=? WHERE claim_id=?", (policy["policy_number"], version_id, now, claim_id))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, reviewer_id, "policy_version_linked", json.dumps({"version_id": version_id}), now))


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
    required_terms = {"annual_limit", "deductible", "copay_percent"}
    trusted_terms_confirmed = trusted_fixtures_enabled() and is_trusted_fixture_hash(hashlib.sha256(content).hexdigest()) and required_terms.issubset(extracted_terms["terms_json"])
    reviewed_terms = extracted_terms["terms_json"] if trusted_terms_confirmed else None
    review_status = "confirmed" if trusted_terms_confirmed else "pending"
    terms_reviewer = "trusted_fixture" if trusted_terms_confirmed else None
    terms_reviewed_at = utc_now() if trusted_terms_confirmed else None
    with db() as conn:
        conn.execute("UPDATE policy_versions SET status='archived' WHERE policy_number=?", (policy_number.strip(),))
        conn.execute("INSERT INTO policy_versions(version_id,policy_number,version_label,insurer_name,effective_date,status,source_name,stored_path,page_count,content_text,indexed_chunks,created_at,policy_terms_json,terms_review_status,reviewed_policy_terms_json,terms_reviewed_by,terms_reviewed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (version_id, policy_number.strip(), version_label.strip(), insurer.strip(), effective_date, "active", uploaded_file.name, str(target), page_count, text, indexed["chunks_indexed"], utc_now(), json.dumps(extracted_terms["terms_json"]), review_status, json.dumps(reviewed_terms) if reviewed_terms else None, terms_reviewer, terms_reviewed_at))
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
        if doc["document_type"] == "settlement":
            continue
        try:
            evidence, raw_by_page, page_count = _extract_one(doc)
            payloads.append({
                "document_id": doc["document_id"],
                "source_name": doc["original_name"],
                "document_type": doc["document_type"],
                "sha256": doc["sha256"],
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
    normalized = apply_claim_extraction_reviews(claim_id, normalized)
    # Quality gate: an extraction error or missing line-item structure must not
    # silently continue into financial adjudication.
    extraction_failures = sum(doc["document_type"] != "settlement" for doc in documents) - len(payloads)
    if extraction_failures:
        normalized.setdefault("review_fields", []).append("document_extraction")
    bill_payloads = [payload for payload in payloads if payload.get("document_type") == "medical_bill"]
    policy_payloads = [payload for payload in payloads if payload["document_type"] == "policy"]
    if bill_payloads and normalized.get("total_amount") and not normalized.get("line_items"):
        normalized.setdefault("review_fields", []).append("line_items")
    if policy_payloads:
        policy_id = ((normalized.get("policy_number") or {}).get("value") or claim_id)
        try:
            normalized["policy_index"] = index_policy_documents(policy_payloads, str(policy_id))
            # Core MVP behavior: a policy uploaded with a claim is automatically
            # registered as the active edition for that matching policy number.
            # The advanced Policy Management page remains deferred.
            extracted_terms = extract_policy_terms([item for payload in policy_payloads for item in payload.get("evidence", [])])
            normalized["policy_terms"] = extracted_terms
            extracted_policy_number = str(((normalized.get("policy_number") or {}).get("value") or "")).strip()
            with db() as conn:
                claim_policy = conn.execute("SELECT policy_number FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
            registered_policy_number = str((claim_policy["policy_number"] if claim_policy else "") or "").strip()
            policy_number = extracted_policy_number or registered_policy_number
            if extracted_policy_number and registered_policy_number and extracted_policy_number.casefold() != registered_policy_number.casefold():
                normalized["policy_number_mismatch"] = True
                policy_number = ""
            if policy_number:
                policy_text = "\\n".join(payload.get("text", "") for payload in policy_payloads)
                with db() as conn:
                    existing = conn.execute("SELECT version_id FROM policy_versions WHERE policy_number=? AND status='active' AND content_text=? LIMIT 1", (policy_number, policy_text)).fetchone()
                    if existing:
                        normalized["active_policy_version_id"] = existing["version_id"]
                    else:
                        conn.execute("UPDATE policy_versions SET status='archived' WHERE policy_number=?", (policy_number,))
                        version_id = str(uuid.uuid4())
                        required_terms = {"annual_limit", "deductible", "copay_percent"}
                        trusted_terms_confirmed = trusted_fixtures_enabled() and any(is_trusted_fixture_hash(payload.get("sha256")) for payload in policy_payloads) and required_terms.issubset(extracted_terms["terms_json"])
                        reviewed_terms = extracted_terms["terms_json"] if trusted_terms_confirmed else None
                        review_status = "confirmed" if trusted_terms_confirmed else "pending"
                        terms_reviewer = "trusted_fixture" if trusted_terms_confirmed else None
                        terms_reviewed_at = utc_now() if trusted_terms_confirmed else None
                        policy_page_count = max((int(item.get("page", 1)) for payload in policy_payloads for item in payload.get("evidence", [])), default=1)
                        conn.execute("INSERT INTO policy_versions(version_id,policy_number,version_label,insurer_name,effective_date,status,source_name,stored_path,page_count,content_text,indexed_chunks,created_at,policy_terms_json,terms_review_status,reviewed_policy_terms_json,terms_reviewed_by,terms_reviewed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (version_id, policy_number, "Claim-uploaded policy", "Not specified", "", "active", policy_payloads[0].get("source_name", "policy"), "", policy_page_count, policy_text, int(normalized["policy_index"].get("chunks_indexed", 0)), utc_now(), json.dumps(extracted_terms["terms_json"]), review_status, json.dumps(reviewed_terms) if reviewed_terms else None, terms_reviewer, terms_reviewed_at))
                        normalized["active_policy_version_id"] = version_id
                    conn.execute("UPDATE claims SET policy_number=?,policy_version_id=?,updated_at=? WHERE claim_id=? AND (policy_number IS NULL OR policy_number='' OR policy_number=?)", (policy_number, normalized["active_policy_version_id"], utc_now(), claim_id, policy_number))
                # Retrieval runs with the active edition ID, so store this
                # claim-uploaded policy under that same ID as well.
                index_policy_documents(policy_payloads, normalized["active_policy_version_id"])
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
    room_items = [item for item in line_items if normalize_category(item.get("category")) == ROOM_CATEGORY]
    non_room_total = sum((Decimal(str(item.get("amount", 0) or 0)) for item in line_items if normalize_category(item.get("category")) != ROOM_CATEGORY), Decimal("0"))
    if room_items:
        context.setdefault("room_charge", sum((Decimal(str(item.get("amount", 0) or 0)) for item in room_items), Decimal("0")))
        admission = (normalized.get("admission_date") or {}).get("value")
        discharge = (normalized.get("discharge_date") or {}).get("value")
        if admission and discharge:
            try:
                start = datetime.fromisoformat(str(admission))
                end = datetime.fromisoformat(str(discharge))
                context.setdefault("room_days", max(1, (end - start).days))
            except ValueError:
                pass
        if non_room_total > 0:
            context.setdefault("room_linked_charges", non_room_total)
    # Preserve an explicit reviewer/claimant suspicion as an additional safety
    # gate while still honoring duplicate candidates detected from bill text.
    context["duplicate_suspected"] = bool(context.get("duplicate_suspected")) or bool(normalized.get("duplicate_candidates"))
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
    normalized = apply_claim_extraction_reviews(claim_id, normalized)
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
    if active_policy and active_policy["terms_review_status"] == "confirmed" and active_policy["reviewed_policy_terms_json"]:
        terms_payload = json.loads(active_policy["reviewed_policy_terms_json"])
        terms, missing_terms, confidence = terms_from_json(terms_payload)
        terms.source = terms_payload
        if missing_terms:
            result = {"status": "manual_review", "rule_version": "policy-terms-required", "results": [], "covered_amount": 0.0, "deductible": 0.0, "copayment": 0.0, "payable_amount": 0.0, "warnings": ["Required policy terms missing: " + ", ".join(missing_terms)], "policy_terms_missing": missing_terms, "policy_terms": terms_payload}
        else:
            # Do not pass the newer keyword here: this keeps the Streamlit app
            # compatible with an already-running process that has an older rules.py.
            result = evaluate_claim(total, terms=terms, review_fields=normalized.get("review_fields"), missing_fields=normalized.get("missing_fields"), claim_context=_derived_claim_context(claim_id, user_id, normalized), line_items=normalized.get("line_items"))
        result["policy_terms_confidence"] = confidence
    elif active_policy:
        result = {"status": "manual_review", "rule_version": "policy-terms-review-required", "results": [], "covered_amount": 0.0, "deductible": 0.0, "copayment": 0.0, "payable_amount": 0.0, "warnings": ["Policy terms have not been confirmed by a reviewer. Confirm the applicable policy terms before calculation."], "policy_terms_missing": ["reviewed_policy_terms"], "policy_terms": json.loads(active_policy["policy_terms_json"] or "{}")}
    else:
        result = {"status": "manual_review", "rule_version": "policy-terms-required", "results": [], "covered_amount": 0.0, "deductible": 0.0, "copayment": 0.0, "payable_amount": 0.0, "warnings": ["No matching policy edition is linked to this claim. Link an edition in Claim review first."], "policy_terms_missing": ["active_policy_terms"], "policy_terms": {}}
    result["policy_source"] = f"{active_policy['policy_number']} — {active_policy['version_label']}" if active_policy else "none"
    result = _reconcile_result(result, total)
    result["history_flags"] = check_similar_past_rejections(user_id, result.get("line_item_results") or [], policy_number or "")
    with db() as conn:
        conn.execute("INSERT INTO rule_evaluations VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, result["rule_version"], result["status"], json.dumps(result), utc_now()))
        conn.execute("UPDATE claims SET status=?, updated_at=? WHERE claim_id=?", (result["status"], utc_now(), claim_id))
        conn.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), claim_id, user_id, "rules_evaluated", json.dumps(result), utc_now()))
    return result


def _claim_policy_clause_map(claim_id: str) -> dict[str, Clause]:
    clauses: dict[str, Clause] = {}
    with db() as conn:
        documents = conn.execute("SELECT extracted_json FROM documents WHERE claim_id=? AND document_type='policy'", (claim_id,)).fetchall()
    for document in documents:
        try:
            payload = json.loads(document["extracted_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        for evidence in payload.get("evidence", []):
            text = str(evidence.get("text") or "")
            if not text:
                continue
            match = re.search(r"(Clause\s+([A-Za-z0-9.]+)\s*[:.-]?\s*.*?)(?=Clause\s+[A-Za-z0-9.]+|\Z)", text, re.I | re.S)
            if not match:
                continue
            clause_text = re.sub(r"\s+", " ", match.group(1)).strip()
            clause = Clause(clause_text[:2000], int(evidence.get("page") or 1), match.group(2))
            lowered = clause_text.lower()
            if any(term in lowered for term in ("medicine", "medicines", "pharmacy", "drug")):
                clauses["PHARMACY"] = clause
            if "room" in lowered:
                clauses.setdefault("ROOM", clause)
            if "doctor" in lowered or "nursing" in lowered:
                clauses.setdefault("DOCTOR_NURSING", clause)
    return clauses


def run_settlement_comparison(claim_id: str, user_id: str, normalized: dict, rules: dict) -> tuple[Any, SettlementData]:
    """Build the typed comparison from saved claim documents and rule outputs."""
    user = get_user(user_id)
    claim = _claim_access(claim_id, user)
    documents = claim_documents(claim_id, user)
    settlement_docs = [doc for doc in documents if doc["document_type"] == "settlement"]
    if len(settlement_docs) != 1:
        settlement = SettlementData(None, Decimal("0"), needs_review=True, review_reasons=["Upload exactly one settlement letter before comparison."])
    else:
        path = secure_document_path(settlement_docs[0], user)
        settlement = parse_settlement(path.read_bytes(), settlement_docs[0]["original_name"])

    total_field = normalized.get("total_amount") or {}
    bill_total = Decimal(str(total_field.get("value") or 0))
    if settlement.claim_id is None:
        settlement.needs_review = True
        settlement.review_reasons.append("CLAIM_ID_MISSING: settlement claim reference was not identified.")
    else:
        claim_key = re.sub(r"[\s-]+", "", str(claim["claim_number"] or "")).casefold()
        settlement_key = re.sub(r"[\s-]+", "", settlement.claim_id).casefold()
        if claim_key != settlement_key:
            settlement.needs_review = True
            settlement.review_reasons.append("CLAIM_ID_MISMATCH: settlement claim reference does not match the selected claim.")
    if settlement.bill_total is None:
        settlement.needs_review = True
        settlement.review_reasons.append("SETTLEMENT_TOTAL_MISSING: settlement bill total was not identified.")
    elif abs(settlement.bill_total - bill_total) > Decimal("1"):
        settlement.needs_review = True
        settlement.review_reasons.append("BILL_TOTAL_MISMATCH: settlement bill total does not match the uploaded bill within INR 1.")

    patient = str(((normalized.get("patient_name") or {}).get("value") or ""))
    admission = parse_bill_date((normalized.get("admission_date") or {}).get("value"))
    discharge = parse_bill_date((normalized.get("discharge_date") or {}).get("value"))
    room_days = max(0, (discharge - admission).days) if admission and discharge else None
    typed_items = []
    for item in normalized.get("line_items", []):
        item_date = parse_bill_date(item.get("date") or item.get("expense_date"))
        typed_items.append(LineItem(
            str(item.get("description") or "Unspecified item"),
            normalize_category(item.get("category")),
            Decimal(str(item.get("amount") or 0)),
            item_date,
            str(item.get("source") or "rule"),
            bool(item.get("needs_review")),
        ))
    if not typed_items and bill_total > 0:
        typed_items = [LineItem("Claim total", "OTHER", bill_total, source="user")]
    policy_version = active_policy_for_claim(claim_id, normalized)
    if policy_version and policy_version["reviewed_policy_terms_json"]:
        try:
            terms_payload = json.loads(policy_version["reviewed_policy_terms_json"])
        except (TypeError, json.JSONDecodeError):
            terms_payload = {}
        parsed_terms, _missing, _confidence = terms_from_json(terms_payload)
    else:
        terms_payload = {}
        parsed_terms = None
    policy_text = saved_policy_text(claim_id)
    non_payables = terms_payload.get("non_payable_categories", [])
    if isinstance(non_payables, dict):
        non_payables = non_payables.get("value", [])
    if not non_payables and re.search(r"admission.{0,40}non[- ]?payable|registration.{0,40}non[- ]?payable", policy_text, re.I | re.S):
        non_payables = ["ADMISSION"]
    exclusions = (parsed_terms.source.get("exclusions") or {}).get("value", []) if parsed_terms else []
    if isinstance(exclusions, str):
        exclusions = [exclusions]
    clauses = _claim_policy_clause_map(claim_id)
    typed_terms = TypedPolicyTerms(
        sum_insured=parsed_terms.annual_limit if parsed_terms and parsed_terms.annual_limit is not None else Decimal("0"),
        room_rent_cap_per_day=parsed_terms.room_limit_per_day if parsed_terms else None,
        copay_percent=parsed_terms.copay_percent if parsed_terms and parsed_terms.copay_percent is not None else Decimal("0"),
        non_payable_categories=list(non_payables or []),
        exclusions=list(exclusions or []),
        clauses=clauses,
        proportionate_deduction=bool(re.search(r"proportionate|room[- ]linked", policy_text, re.I)),
    )

    line_results = rules.get("line_item_results") or []
    typed_lines = []
    for index, item in enumerate(typed_items):
        evaluated = line_results[index] if index < len(line_results) else {}
        allowed = Decimal(str(evaluated.get("covered_amount", item.amount)))
        rule_name = str(evaluated.get("applied_rule") or "")
        reason_code = {"non_payable": "NON_PAYABLE", "room_limit": "ROOM_CAP", "proportionate_deduction": "PROPORTIONATE", "exclusion": "EXCLUSION"}.get(rule_name, "REVIEW" if evaluated.get("status") == "needs_review" else "OK")
        clause = clauses.get(item.category)
        typed_lines.append(LineResult(item, allowed, max(Decimal("0"), item.amount - allowed), reason_code, clause))
    typed_claim = ClaimResult(
        lines=typed_lines,
        eligible_total=Decimal(str(rules.get("covered_amount") or 0)),
        copay=Decimal(str(rules.get("copayment") or 0)),
        patient_share=max(Decimal("0"), bill_total - Decimal(str(rules.get("payable_amount") or 0))),
        insurer_share=Decimal(str(rules.get("payable_amount") or 0)),
        status="manual_review" if rules.get("status") == "manual_review" else "computed",
        review_reasons=list(rules.get("warnings") or []),
    )
    comparison = compare_claim_settlement(typed_claim, settlement, typed_terms)
    if len(settlement_docs) == 1:
        save_settlement_comparison(claim_id, settlement_docs[0]["sha256"], comparison, settlement)
    return comparison, settlement


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if is_dataclass(value):
        return {item.name: _json_safe(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def save_settlement_comparison(claim_id: str, document_hash: str, comparison, settlement: SettlementData) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO settlement_comparisons(claim_id,settlement_document_sha256,settlement_json,comparison_json,created_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(claim_id) DO UPDATE SET settlement_document_sha256=excluded.settlement_document_sha256,settlement_json=excluded.settlement_json,comparison_json=excluded.comparison_json,created_at=excluded.created_at",
            (claim_id, document_hash, json.dumps(_json_safe(settlement)), json.dumps(_json_safe(comparison)), utc_now()),
        )


def _load_settlement_data(payload: dict[str, Any]) -> SettlementData:
    deductions = [SettlementDeduction(
        str(row["category"]), Decimal(str(row["amount"])), str(row.get("reason_text", "")), bool(row.get("needs_review", False))
    ) for row in payload.get("deductions", [])]
    return SettlementData(
        payload.get("claim_id"), Decimal(str(payload.get("amount_paid", "0"))), deductions,
        Decimal(str(payload["copay_applied"])) if payload.get("copay_applied") is not None else None,
        bool(payload.get("needs_review", False)), list(payload.get("review_reasons", [])),
        Decimal(str(payload["bill_total"])) if payload.get("bill_total") is not None else None,
    )


def _load_comparison_result(payload: dict[str, Any]) -> ComparisonResult:
    categories = []
    for row in payload.get("categories", []):
        raw_clause = row.get("clause")
        clause = Clause(str(raw_clause["text"]), int(raw_clause["page"]), raw_clause.get("section")) if raw_clause else None
        categories.append(CategoryComparison(
            str(row["category"]), Decimal(str(row["insurer_deducted"])), Decimal(str(row["engine_disallowed"])),
            Decimal(str(row["difference"])), str(row["status"]), str(row.get("insurer_reason", "")),
            str(row.get("engine_reason", "")), clause, Decimal(str(row["payout_effect"])),
        ))
    return ComparisonResult(
        Decimal(str(payload["expected_patient_share"])), Decimal(str(payload["actual_patient_share"])),
        Decimal(str(payload["possible_difference"])), categories, str(payload["status"]),
        list(payload.get("review_reasons", [])), Decimal(str(payload.get("billed_total", "0"))),
        Decimal(str(payload.get("actual_insurer_payment", "0"))), Decimal(str(payload.get("expected_insurer_payment", "0"))),
    )


def load_settlement_comparison(claim_id: str, user: dict | sqlite3.Row):
    _claim_access(claim_id, user)
    with db() as conn:
        saved = conn.execute("SELECT * FROM settlement_comparisons WHERE claim_id=?", (claim_id,)).fetchone()
        settlement_doc = conn.execute("SELECT sha256 FROM documents WHERE claim_id=? AND document_type='settlement' ORDER BY created_at DESC LIMIT 1", (claim_id,)).fetchone()
    if not saved or not settlement_doc or saved["settlement_document_sha256"] != settlement_doc["sha256"]:
        return None
    try:
        settlement_payload = json.loads(saved["settlement_json"])
        comparison_payload = json.loads(saved["comparison_json"])
        return _load_comparison_result(comparison_payload), _load_settlement_data(settlement_payload)
    except (KeyError, TypeError, ValueError, InvalidOperation, json.JSONDecodeError):
        return None


def get_comparison_for_view(claim_id: str, user: dict | sqlite3.Row, session_state=None):
    session_state = st.session_state if session_state is None else session_state
    comparison_key = f"comparison_{claim_id}"
    settlement_key = f"settlement_{claim_id}"
    comparison, settlement = session_state.get(comparison_key), session_state.get(settlement_key)
    if comparison is None or settlement is None:
        stored = load_settlement_comparison(claim_id, user)
        if stored:
            comparison, settlement = stored
            session_state[comparison_key] = comparison
            session_state[settlement_key] = settlement
    return comparison, settlement


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
    return "\n".join(text_parts)


def active_policy_for_claim(claim_id: str, normalized: dict) -> sqlite3.Row | None:
    with db() as conn:
        claim = conn.execute("SELECT policy_number,policy_version_id FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
        if claim and claim["policy_version_id"]:
            linked = conn.execute("SELECT * FROM policy_versions WHERE version_id=?", (claim["policy_version_id"],)).fetchone()
            if linked:
                return linked
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


def _core_demo_user() -> dict[str, Any]:
    """Create the local demo admin only when an explicit password is configured."""
    demo_email = "demo@mediguard.local"
    demo_password = os.getenv("MEDIGUARD_ADMIN_PASSWORD", "")
    if not demo_password:
        raise RuntimeError("Set MEDIGUARD_ADMIN_PASSWORD to create the synthetic demo administrator.")
    demo_id = hashlib.sha256(demo_email.encode("utf-8")).hexdigest()[:24]
    with db() as conn:
        conn.execute(
            "INSERT INTO users(user_id,email,display_name,role,password_hash,is_active,password_set_at,created_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET display_name=excluded.display_name, role='admin', password_hash=excluded.password_hash, is_active=1, password_set_at=excluded.password_set_at",
            (demo_id, demo_email, "Demo Reviewer", "admin", _hash_password(demo_password), 1, utc_now(), utc_now()),
        )
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (demo_id,)).fetchone()
    return dict(row)


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
                rows.append({'Policy Number':v['policy_number'],'Version':v['version_label'],'Effective Date':v['effective_date'],'Status':v['status'].title(),'Term review':v['terms_review_status'].title(),'Indexed Chunks':v['indexed_chunks'],'Candidate Terms':len(terms)})
            st.dataframe(rows,hide_index=True)
            st.markdown('### Confirm policy terms')
            st.caption('For real policies, verify each value against the applicable policy wording or member schedule. An unconfirmed policy remains Manual Review; the language model cannot fill missing contract terms.')
            for version in versions:
                with st.expander(f"{version['policy_number']} · {version['version_label']} · {version['source_name']}"):
                    try:
                        candidates = json.loads(version['policy_terms_json'] or '{}')
                        reviewed = json.loads(version['reviewed_policy_terms_json'] or '{}')
                    except (TypeError, json.JSONDecodeError):
                        candidates, reviewed = {}, {}
                    st.write(f"Page count: {version['page_count'] or 'not recorded'} · Status: {version['terms_review_status']}")
                    st.caption('Candidate terms from deterministic text matching (not reviewer-verified): ' + (', '.join(sorted(candidates)) if candidates else 'none found'))
                    for term_name, term_value in candidates.items():
                        if isinstance(term_value, dict):
                            st.caption(f"{term_name.replace('_', ' ').title()}: {term_value.get('value')} · source page {term_value.get('source_page') or 'unknown'}")
                    with st.form(f"policy_search_{version['version_id']}"):
                        policy_query = st.text_input('Search this policy', placeholder='For example: room limit, waiting period, or exclusions', key=f"policy_query_{version['version_id']}")
                        search_policy = st.form_submit_button('Find clauses')
                    if search_policy and policy_query.strip():
                        try:
                            hits = retrieve_indexed_policy_evidence(policy_query.strip(), version['version_id'], limit=4)
                            if not hits:
                                st.info('No matching clauses found.')
                            for hit in hits:
                                with st.container(border=True):
                                    st.caption(f"Page {hit.get('page', '?')} · {hit.get('section', 'policy')} · relevance distance {hit.get('distance'):.3f}" if isinstance(hit.get('distance'), (int, float)) else f"Page {hit.get('page', '?')} · {hit.get('section', 'policy')}")
                                    st.write(hit.get('text', ''))
                        except Exception as exc:
                            st.error(f'Policy search failed: {exc}')
                    def _term_default(name):
                        current = reviewed.get(name) or candidates.get(name) or {}
                        return str(current.get('value', ''))
                    def _page_default(name):
                        current = reviewed.get(name) or candidates.get(name) or {}
                        return int(current.get('source_page') or 1)
                    with st.form(f"policy_terms_review_{version['version_id']}"):
                        a,b,c = st.columns(3)
                        with a:
                            annual = st.text_input('Annual limit (INR)', value=_term_default('annual_limit'), key=f"annual_{version['version_id']}")
                            annual_page = st.number_input('Annual limit source page', min_value=1, value=_page_default('annual_limit'), step=1, key=f"annual_page_{version['version_id']}")
                            deductible = st.text_input('Deductible (INR)', value=_term_default('deductible'), key=f"deductible_{version['version_id']}")
                            deductible_page = st.number_input('Deductible source page', min_value=1, value=_page_default('deductible'), step=1, key=f"deductible_page_{version['version_id']}")
                        with b:
                            copay = st.text_input('Co-payment (%)', value=_term_default('copay_percent'), key=f"copay_{version['version_id']}")
                            copay_page = st.number_input('Co-payment source page', min_value=1, value=_page_default('copay_percent'), step=1, key=f"copay_page_{version['version_id']}")
                            room_limit = st.text_input('Room limit per day (INR, optional)', value=_term_default('room_limit_per_day'), key=f"room_{version['version_id']}")
                            room_page = st.number_input('Room limit source page', min_value=1, value=_page_default('room_limit_per_day'), step=1, key=f"room_page_{version['version_id']}")
                        with c:
                            waiting = st.text_input('Waiting period (months, optional)', value=_term_default('waiting_period_months'), key=f"waiting_{version['version_id']}")
                            waiting_page = st.number_input('Waiting period source page', min_value=1, value=_page_default('waiting_period_months'), step=1, key=f"waiting_page_{version['version_id']}")
                            sub_default = (reviewed.get('sub_limits') or candidates.get('sub_limits') or {}).get('value', {})
                            sub_text = st.text_area('Sub-limits JSON (optional)', value=json.dumps(sub_default, ensure_ascii=False), key=f"sub_limits_{version['version_id']}")
                            sub_page = st.number_input('Sub-limits source page', min_value=1, value=_page_default('sub_limits'), step=1, key=f"sub_page_{version['version_id']}")
                        submitted_terms = st.form_submit_button('Save and confirm policy terms', type='primary')
                    if submitted_terms:
                        try:
                            sub_value = json.loads(sub_text or '{}')
                            if not isinstance(sub_value, dict):
                                raise ValueError('Sub-limits must be a JSON object of category to amount.')
                            review_status = save_policy_terms_review(
                                version['version_id'], user['user_id'],
                                {'annual_limit': annual, 'deductible': deductible, 'copay_percent': copay, 'room_limit_per_day': room_limit, 'waiting_period_months': waiting},
                                {'annual_limit': int(annual_page), 'deductible': int(deductible_page), 'copay_percent': int(copay_page), 'room_limit_per_day': int(room_page), 'waiting_period_months': int(waiting_page), 'sub_limits': int(sub_page)},
                                sub_value,
                            )
                            if review_status == 'confirmed':
                                st.success('Required policy terms confirmed. The reviewer and source pages were recorded.')
                            else:
                                st.warning('Saved as pending. Add annual limit, deductible, co-payment, and the source page for each before running rules.')
                            st.rerun()
                        except Exception as exc:
                            st.error(f'Policy terms were not saved: {exc}')
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
                invite=create_reviewer_invitation(user,email,name)
                link=reviewer_invitation_link(user, invite)
                st.session_state['pending_reviewer_invite'] = {'link': link, 'user_id': invite['user_id'], 'expires_at': invite['expires_at']}
                st.success('Reviewer invitation created.')
            except Exception as exc: st.error(str(exc))
        pending_invite = st.session_state.get('pending_reviewer_invite')
        if pending_invite:
            require_role(user, 'admin')
            st.markdown('#### Pending reviewer invitation link')
            st.caption(f"Visible only in this signed-in administrator session · expires {pending_invite['expires_at']}")
            st.code(pending_invite['link'])
    with st.container(border=True):
        st.markdown('### Users')
        with db() as conn: users=conn.execute('SELECT user_id,email,display_name,role,is_active,created_at FROM users ORDER BY created_at DESC').fetchall()
        st.dataframe([{'Name':u['display_name'],'Email':u['email'],'Role':u['role'].title(),'Status':'Active' if u['is_active'] else 'Inactive','Created':u['created_at']} for u in users],hide_index=True)
        st.info('User and invitation activity is logged for security and cannot be silently deleted.')


def appeal_draft_available(comparison: Any) -> bool:
    """Compatibility API for callers that gate on appeal evidence."""
    return comparison is not None and getattr(comparison, "status", None) == "possible_discrepancy"


def main() -> None:
    st.set_page_config(page_title='MediGuard AI', page_icon='🛡️', layout='wide', initial_sidebar_state='expanded')
    from ui.styles import APP_CSS
    st.markdown(APP_CSS, unsafe_allow_html=True)
    init_db(); validate_security_config(); bootstrap_admin_from_env()
    st.warning("Prototype. Uses sample data. Not for real patient information. Estimates are not insurer decisions.")
    from ui.auth_pages import _render_welcome, _render_login
    from ui.claim_pages import _render_dashboard, _render_register, _render_claim_submission, _render_claim_review, _render_claimant_result
    if not st.session_state.get('welcome_seen') and not (st.query_params.get('reset_token') or st.query_params.get('setup_token')):
        _render_welcome()
        return
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
