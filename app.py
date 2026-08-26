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
# Reserved for a future signed-token/session layer. It is intentionally not treated as active security yet.
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() == "true"
STORAGE_DIR = Path(os.getenv("MEDIGUARD_STORAGE_DIR", str(DATA_DIR))).resolve()
UPLOAD_DIR = STORAGE_DIR / "uploads"
ALLOWED_ROLES = {"claimant", "reviewer", "admin"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
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


def authenticate_user(email: str, password: str) -> sqlite3.Row | None:
    with db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
    return user if user and user["is_active"] and _verify_password(password, user["password_hash"]) else None


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
                created_at TEXT NOT NULL
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
        for column, definition in (("assigned_reviewer_id", "TEXT"), ("review_priority", "INTEGER NOT NULL DEFAULT 0")):
            try:
                conn.execute(f"ALTER TABLE claims ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError:
                pass
        for column, definition in (("password_hash", "TEXT"), ("is_active", "INTEGER NOT NULL DEFAULT 1"), ("password_set_at", "TEXT"), ("disabled_at", "TEXT")):
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


def claim_documents(claim_id: str, user: dict | sqlite3.Row | None = None):
    if user is not None:
        _claim_access(claim_id, user)
    with db() as conn:
        return conn.execute("SELECT * FROM documents WHERE claim_id=? ORDER BY created_at", (claim_id,)).fetchall()


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
    policy_payloads = [payload for payload, doc in zip(payloads, documents) if doc["document_type"] == "policy"]
    if policy_payloads:
        policy_id = ((normalized.get("policy_number") or {}).get("value") or claim_id)
        try:
            normalized["policy_index"] = index_policy_documents(policy_payloads, str(policy_id))
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


def evaluate_saved_claim(claim_id: str, user_id: str, normalized: dict) -> dict:
    user = get_user(user_id)
    _claim_access(claim_id, user, write=True)
    total = (normalized.get("total_amount") or {}).get("value")
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
            result = evaluate_claim(total, terms=terms, review_fields=normalized.get("review_fields"), missing_fields=normalized.get("missing_fields"))
        result["policy_terms_confidence"] = confidence
    else:
        result = {"status": "manual_review", "rule_version": "policy-terms-required", "results": [], "covered_amount": 0.0, "deductible": 0.0, "copayment": 0.0, "payable_amount": 0.0, "warnings": ["No active policy terms are available. Ingest a policy edition in Policy management first."], "policy_terms_missing": ["active_policy_terms"], "policy_terms": {}}
    result["policy_source"] = f"{active_policy['policy_number']} — {active_policy['version_label']}" if active_policy else "none"
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


def main() -> None:
    st.set_page_config(page_title="Medi Gaurd AI", page_icon="MG", layout="wide")
    init_db()
    validate_security_config()
    bootstrap_admin_from_env()
    st.title("Medi Gaurd AI")
    st.caption("Medical bill and insurance claim verification — MVP foundation")

    with st.sidebar:
        st.header("Local configuration")
        connected, message = ollama_status()
        (st.success if connected else st.warning)(message)
        st.code(f"Model: {OLLAMA_MODEL}\nHost: {OLLAMA_HOST}")
        st.divider()
        st.caption("Final determination should be confirmed by an authorized reviewer.")

    if "user" not in st.session_state:
        setup_token = st.query_params.get("setup_token")
        if setup_token:
            st.subheader("Reviewer account setup")
            st.caption("This one-time setup token expires after 24 hours and is invalidated after successful use.")
            with st.form("reviewer_setup"):
                setup_password = st.text_input("Create password", type="password")
                setup_confirm = st.text_input("Confirm password", type="password")
                setup_submit = st.form_submit_button("Activate reviewer account")
            if setup_submit:
                if setup_password != setup_confirm:
                    st.error("Passwords do not match.")
                else:
                    try:
                        complete_reviewer_setup(setup_token, setup_password)
                        st.query_params.clear()
                        st.success("Reviewer account activated. Sign in with your email and new password.")
                    except ValueError as exc:
                        st.error(str(exc))
            return
        st.subheader("Secure sign-in")
        st.caption("Claimant accounts can self-register. Reviewer and administrator accounts must be provisioned by an administrator or deployment operator.")
        login_tab, register_tab = st.tabs(["Sign in", "Register claimant"])
        with login_tab:
            with st.form("login"):
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Sign in")
            if submitted:
                user_row = authenticate_user(email, password)
                if user_row is None:
                    st.error("Invalid email or password.")
                else:
                    st.session_state.user = dict(user_row)
                    st.rerun()
        with register_tab:
            with st.form("register"):
                reg_email = st.text_input("Email", key="register_email")
                reg_name = st.text_input("Display name", key="register_name")
                reg_password = st.text_input("Password", type="password", key="register_password")
                reg_confirm = st.text_input("Confirm password", type="password", key="register_confirm")
                registered = st.form_submit_button("Create claimant account")
            if registered:
                if reg_password != reg_confirm:
                    st.error("Passwords do not match.")
                else:
                    try:
                        st.session_state.user = dict(register_user(reg_email, reg_name, reg_password))
                        st.success("Account created.")
                        st.rerun()
                    except (ValueError, PermissionError) as exc:
                        st.error(str(exc))
        return

    user = st.session_state.user
    with st.sidebar:
        st.write(f"Signed in as **{user['display_name']}**")
        if st.button("Log out"):
            del st.session_state.user
            st.rerun()

    tabs = st.tabs(["Dashboard", "Register claim", "Claim review", "Policy management"])
    with tabs[0]:
        st.subheader("Your claims")
        claims = user_claims(user["user_id"])
        if not claims:
            st.info("No claims yet. Register your first claim to begin.")
        for claim in claims:
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 3, 1])
                col1.write(f"**{claim['claim_number']}**")
                col2.write(f"Patient: {claim['patient_name']}  ")
                col2.caption(f"Documents: {len(claim_documents(claim['claim_id']))}")
                col3.metric("Status", claim["status"].replace("_", " ").title())
        queue = reviewer_queue(user) if user["role"] in {"reviewer", "admin"} else []
        if queue:
            st.subheader("Reviewer queue")
            st.caption("Claims requiring human confirmation are listed here; automated recommendations never replace reviewer sign-off.")
            queue_rows = [{"claim_number": item["claim_number"], "patient": item["patient_name"], "status": item["status"].replace("_", " ").title(), "assigned_reviewer": item["assigned_reviewer_id"] or "Unassigned", "priority": item["review_priority"]} for item in queue]
            st.dataframe(queue_rows, width="stretch", hide_index=True)
        if user["role"] == "admin":
            with st.expander("Administrator: invite reviewer"):
                st.caption("The setup token is shown only once in this session. Do not copy it into logs or source code.")
                with st.form("admin_reviewer_invitation"):
                    reviewer_email = st.text_input("Reviewer email")
                    reviewer_name = st.text_input("Reviewer display name")
                    invite_submit = st.form_submit_button("Create reviewer invitation")
                if invite_submit:
                    try:
                        invitation = provision_user_role(user, reviewer_email, reviewer_name, "reviewer")
                        st.success("Reviewer account created in inactive state.")
                        st.code(f"{APP_BASE_URL}/?setup_token={invitation['setup_token']}", language="text")
                        st.caption(f"Expires: {invitation['expires_at']}. Share this link securely and do not store the token.")
                    except (ValueError, PermissionError) as exc:
                        st.error(str(exc))

    with tabs[1]:
        st.subheader("Register a new claim")
        with st.form("claim_form"):
            claim_number = st.text_input("Claim number", placeholder="CLM-2026-0001")
            patient = st.text_input("Patient name")
            hospital = st.text_input("Hospital / provider")
            policy = st.text_input("Policy number")
            incident_date = st.date_input("Admission or service date")
            create = st.form_submit_button("Create claim")
        if create:
            if not claim_number or not patient:
                st.error("Claim number and patient name are required.")
            else:
                claim_id = create_claim(user["user_id"], claim_number, patient, hospital, policy, str(incident_date))
                st.session_state.active_claim = claim_id
                st.success(f"Claim {claim_number} created. Continue in the Claim review tab.")

    with tabs[2]:
        st.subheader("Upload claim documents")
        claims = user_claims(user["user_id"], user)
        if not claims:
            st.info("Create a claim first or wait for a claim to be assigned.")
        else:
            options = {f"{c['claim_number']} — {c['patient_name']}": c["claim_id"] for c in claims}
            default = list(options.values()).index(st.session_state.get("active_claim")) if st.session_state.get("active_claim") in options.values() else 0
            selected_label = st.selectbox("Select claim", list(options), index=default)
            claim_id = options[selected_label]
            selected_claim = next((item for item in claims if item["claim_id"] == claim_id), None)
            file_types = ["pdf", "png", "jpg", "jpeg"]
            st.info("Upload each document category separately so the system can distinguish policy evidence from medical bills.")
            policy_files = st.file_uploader("Insurance policy files", type=file_types, accept_multiple_files=True, key="claim_policy_files")
            bill_files = st.file_uploader("Medical bill files", type=file_types, accept_multiple_files=True, key="claim_bill_files")
            other_files = st.file_uploader("Other claim documents", type=file_types, accept_multiple_files=True, key="claim_other_files")
            if st.button("Save uploaded documents", type="primary"):
                all_files = [(item, "policy") for item in (policy_files or [])] + [(item, "medical_bill") for item in (bill_files or [])] + [(item, "other") for item in (other_files or [])]
                if not all_files:
                    st.warning("Select at least one policy, medical-bill, or other document.")
                else:
                    try:
                        for uploaded, document_type in all_files:
                            save_document(claim_id, user, uploaded, document_type)
                        st.success(f"Saved {len(all_files)} document(s) with their correct document types.")
                    except ValueError as exc:
                        st.error(str(exc))
            docs = claim_documents(claim_id)
            if docs:
                st.write("**Saved documents**")
                st.dataframe([dict(d) for d in docs], width="stretch", hide_index=True)
                extraction_errors = [f"{doc['original_name']}: {doc['extraction_error']}" for doc in docs if doc['extraction_error']]
                if extraction_errors:
                    st.error("Extraction errors:\n" + "\n".join(extraction_errors))
                if st.button("Extract and normalize documents", type="primary"):
                    with st.spinner("Extracting text and normalizing claim data..."):
                        try:
                            normalized = process_claim_documents(claim_id, user["user_id"])
                            st.session_state[f"normalized_{claim_id}"] = normalized
                            st.success("Extraction complete. Review the flagged fields before analysis.")
                        except Exception as exc:
                            st.error(f"Extraction failed: {exc}")
                normalized = st.session_state.get(f"normalized_{claim_id}")
                if normalized:
                    st.subheader("Normalized claim data")
                    if normalized["missing_fields"]:
                        st.warning("Missing required fields: " + ", ".join(normalized["missing_fields"]))
                    if normalized["review_fields"]:
                        st.warning("Needs review: " + ", ".join(normalized["review_fields"]))
                    if normalized.get("policy_index"):
                        st.success(f"Indexed {normalized['policy_index']['chunks_indexed']} policy clause(s) in persistent ChromaDB.")
                    if normalized.get("policy_index_error"):
                        st.warning("Policy indexing unavailable: " + normalized["policy_index_error"])
                    fields = []
                    for key in ("patient_name", "hospital_name", "policy_number", "claim_number", "admission_date", "discharge_date", "diagnosis", "total_amount"):
                        item = normalized.get(key)
                        if item:
                            fields.append({"field": key, "value": item["value"], "confidence": item["confidence"], "needs_review": item["needs_review"], "source": item["evidence"][0]["source_name"] if item["evidence"] else ""})
                    st.dataframe(fields, width="stretch", hide_index=True)
                    with st.expander("Reviewer field corrections and evidence confirmation"):
                        st.caption("Use this only when an authorized reviewer has checked the source document. Corrections are audited separately from the automated recommendation.")
                        edit_values = {}
                        for field_name, label in (("patient_name", "Patient name"), ("hospital_name", "Hospital / provider"), ("policy_number", "Policy number"), ("diagnosis", "Diagnosis")):
                            current = (normalized.get(field_name) or {}).get("value", selected_claim[field_name] if selected_claim is not None and field_name in selected_claim.keys() else "")
                            edit_values[field_name] = st.text_input(label, value=str(current or ""), key=f"edit_{field_name}_{claim_id}", disabled=user["role"] not in {"reviewer", "admin"})
                        evidence_confirmed = st.checkbox("I confirmed the corrected fields against the uploaded evidence.", key=f"evidence_confirmed_{claim_id}", disabled=user["role"] not in {"reviewer", "admin"})
                        if st.button("Save field corrections", key=f"save_edits_{claim_id}", disabled=user["role"] not in {"reviewer", "admin"}):
                            if not evidence_confirmed:
                                st.warning("Confirm the source evidence before saving field corrections.")
                            else:
                                try:
                                    save_claim_field_edits(claim_id, user["user_id"], edit_values)
                                    confirmations = [{"field_name": name, "document_id": ((normalized.get(name) or {}).get("evidence") or [{}])[0].get("document_id"), "page_number": ((normalized.get(name) or {}).get("evidence") or [{}])[0].get("page")} for name in edit_values]
                                    confirm_evidence(claim_id, user["user_id"], confirmations)
                                except PermissionError as exc:
                                    st.error(str(exc))
                                    confirmations = []
                                for name, value in edit_values.items():
                                    if normalized.get(name) is not None:
                                        normalized[name]["value"] = value
                                st.session_state[f"normalized_{claim_id}"] = normalized
                                st.success("Reviewer corrections and evidence confirmations saved.")
                    with st.expander("Raw normalized JSON"):
                        st.json(normalized)
                    if st.button("Run deterministic coverage rules", type="primary"):
                        with st.spinner("Calculating deductible, copayment, and policy limits..."):
                            rules = evaluate_saved_claim(claim_id, user["user_id"], normalized)
                            st.session_state[f"rules_{claim_id}"] = rules
                    rules = st.session_state.get(f"rules_{claim_id}")
                    if rules:
                        st.subheader("Deterministic rule result")
                        status = rules["status"].replace("_", " ").title()
                        if status == "Approved":
                            st.success(status)
                        elif status == "Manual Review":
                            st.warning(status)
                        else:
                            st.info(status)
                        metrics = st.columns(4)
                        metrics[0].metric("Covered amount", f"INR {rules['covered_amount']:,.2f}")
                        metrics[1].metric("Deductible", f"INR {rules['deductible']:,.2f}")
                        metrics[2].metric("Copayment", f"INR {rules['copayment']:,.2f}")
                        metrics[3].metric("Payable amount", f"INR {rules['payable_amount']:,.2f}")
                        if rules["warnings"]:
                            st.warning("; ".join(rules["warnings"]))
                        st.dataframe(rules["results"], width="stretch", hide_index=True)
                        st.caption("Rules are deterministic and versioned. Final determination should be confirmed by an authorized reviewer.")
                        if st.button("Run Policy Agent + Decision Agent", type="primary"):
                            status_box = st.status("Starting agent workflow...", expanded=True)
                            started = time.perf_counter()
                            def show_agent_progress(message: str) -> None:
                                status_box.update(label=message, state="running")
                                status_box.write(message)
                            try:
                                status_box.write("Preparing active policy evidence and deterministic results...")
                                workflow = run_agents_for_claim(claim_id, user["user_id"], normalized, rules, progress_callback=show_agent_progress)
                                elapsed = time.perf_counter() - started
                                workflow["elapsed_seconds"] = round(elapsed, 2)
                                st.session_state[f"workflow_{claim_id}"] = workflow
                                status_box.update(label=f"Agent workflow complete in {elapsed:.1f}s", state="complete", expanded=False)
                                st.success(f"Policy Agent and Decision Agent completed in {elapsed:.1f} seconds using {workflow.get('llm_calls', 0)} LLM calls.")
                            except Exception as exc:
                                elapsed = time.perf_counter() - started
                                status_box.update(label=f"Agent workflow failed after {elapsed:.1f}s", state="error", expanded=True)
                                st.error(f"Agent workflow failed after {elapsed:.1f}s: {exc}")
                        workflow = st.session_state.get(f"workflow_{claim_id}")
                        if workflow:
                            findings = workflow.get("policy_findings", {})
                            decision = workflow.get("decision", {})
                            st.subheader("Agent decision")
                            decision_status = decision.get("status", "manual_review").replace("_", " ").title()
                            if decision_status == "Approved":
                                st.success(decision_status)
                            elif decision_status == "Manual Review":
                                st.warning(decision_status)
                            else:
                                st.info(decision_status)
                            st.write("**Reasons**")
                            for reason in decision.get("reasons", []):
                                st.write(f"- {reason}")
                            st.write("**Policy evidence**")
                            evidence = findings.get("retrieved_evidence", [])
                            st.dataframe(evidence, width="stretch", hide_index=True)
                            st.caption(f"Policy source: {workflow.get('policy_source', 'claim-uploaded policy')} · Agent calls used: {workflow.get('llm_calls', 0)} · Elapsed: {workflow.get('elapsed_seconds', 'n/a')}s. Final determination should be confirmed by an authorized reviewer.")
                            with st.expander("Agent workflow JSON"):
                                st.json({"policy_findings": findings, "decision": decision})
                            st.subheader("Authorized reviewer sign-off")
                            st.caption("The agent result is a recommendation. An authorized reviewer must confirm the final determination.")
                            review_status_options = ["approved", "partially_approved", "rejected", "manual_review"]
                            recommendation = decision.get("status", "manual_review")
                            default_review_index = review_status_options.index(recommendation) if recommendation in review_status_options else 3
                            final_status = st.selectbox("Final determination", review_status_options, index=default_review_index, format_func=lambda value: value.replace("_", " ").title(), key=f"review_status_{claim_id}")
                            review_comments = st.text_area("Reviewer comments", key=f"review_comments_{claim_id}", placeholder="Record the evidence checked and reason for confirmation or change.")
                            if st.button("Save reviewer decision", type="primary", key=f"save_review_{claim_id}", disabled=user["role"] not in {"reviewer", "admin"}):
                                if not review_comments.strip():
                                    st.warning("Reviewer comments are required before sign-off.")
                                else:
                                    try:
                                        save_reviewer_decision(claim_id, user["user_id"], recommendation, final_status, review_comments)
                                        st.success("Reviewer decision saved and claim status updated.")
                                    except (PermissionError, ValueError) as exc:
                                        st.error(str(exc))
                            saved_review = latest_reviewer_decision(claim_id)
                            if saved_review:
                                st.info(f"Latest reviewer decision: {saved_review['final_status'].replace('_', ' ').title()} · saved {saved_review['created_at']}")
                            if selected_claim is not None:
                                report_bytes = build_decision_report(dict(selected_claim), normalized, rules, workflow)
                                appeal_text = build_appeal_letter(dict(selected_claim), rules, workflow)
                                export_col1, export_col2, export_col3 = st.columns(3)
                                export_col1.download_button("Download PDF report", data=report_bytes, file_name=f"{selected_claim['claim_number']}_decision_report.pdf", mime="application/pdf", key=f"report_{claim_id}")
                                export_col2.download_button("Download appeal draft", data=appeal_text, file_name=f"{selected_claim['claim_number']}_appeal.txt", mime="text/plain", key=f"appeal_{claim_id}")
                                export_col3.download_button("Download result JSON", data=json.dumps({"normalized": normalized, "rules": rules, "workflow": workflow}, indent=2, default=str), file_name=f"{selected_claim['claim_number']}_result.json", mime="application/json", key=f"json_{claim_id}")


    with tabs[3]:
        st.subheader("Policy management")
        st.caption("Ingest policy editions once, keep historical versions, and compare changes before using an active edition for claim analysis.")
        with st.form("policy_ingestion_form"):
            policy_file = st.file_uploader("Policy PDF or policy photo", type=["pdf", "png", "jpg", "jpeg"], key="policy_management_file")
            policy_number = st.text_input("Policy number", placeholder="POL-HEALTH-45821")
            version_label = st.text_input("Version label", placeholder="2026 Edition")
            insurer = st.text_input("Insurer", placeholder="Example Health Insurance Ltd.")
            effective_date = st.date_input("Effective date")
            ingest = st.form_submit_button("Ingest policy edition", type="primary")
        if ingest:
            if not policy_file or not policy_number or not version_label:
                st.error("Policy file, policy number, and version label are required.")
            else:
                try:
                    result = ingest_policy_version(policy_file, policy_number, version_label, insurer, str(effective_date), user=user)
                    if result["policy_terms"].get("validation_errors"):
                        st.warning("Policy indexed, but term validation requires review: " + "; ".join(result["policy_terms"]["validation_errors"]))
                    elif result["policy_terms"].get("missing_terms"):
                        st.warning("Policy indexed with missing terms: " + ", ".join(result["policy_terms"]["missing_terms"]))
                    else:
                        st.success(f"Policy edition indexed successfully: {result['chunks_indexed']} ChromaDB chunk(s).")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Policy ingestion failed: {exc}")

        versions = policy_versions()
        if not versions:
            st.info("No policy editions have been ingested yet.")
        else:
            st.write("**Stored policy editions**")
            rows = []
            for version in versions:
                try:
                    stored_terms = json.loads(version["policy_terms_json"] or "{}")
                except (TypeError, json.JSONDecodeError):
                    stored_terms = {}
                rows.append({"version_id": version["version_id"], "policy_number": version["policy_number"], "version": version["version_label"], "insurer": version["insurer_name"], "effective_date": version["effective_date"], "status": version["status"], "chunks": version["indexed_chunks"], "terms": ", ".join(stored_terms) or "Needs review"})
            st.dataframe(rows, width="stretch", hide_index=True)
            active_versions = [version for version in versions if version["status"] == "active"]
            for active in active_versions:
                try:
                    active_terms = json.loads(active["policy_terms_json"] or "{}")
                except (TypeError, json.JSONDecodeError):
                    active_terms = {}
                st.caption(f"Active edition: {active['policy_number']} — {active['version_label']} · extracted terms: {', '.join(active_terms) or 'none; rules will require Manual Review'}")
            if active_versions:
                archive_options = {f"{version['policy_number']} — {version['version_label']}": version["version_id"] for version in active_versions}
                archive_label = st.selectbox("Archive an active edition", ["Select an edition"] + list(archive_options), key="archive_policy_select")
                if archive_label != "Select an edition" and st.button("Archive selected edition"):
                    archive_policy_version(archive_options[archive_label], user=user)
                    st.success("Policy edition archived.")
                    st.rerun()

            if len(versions) >= 2:
                st.subheader("Compare policy editions")
                compare_options = {f"{version['policy_number']} — {version['version_label']} ({version['effective_date']})": version for version in versions}
                selected = st.multiselect("Select two editions", list(compare_options), max_selections=2, key="compare_policy_versions")
                if len(selected) == 2 and st.button("Compare selected editions"):
                    older = compare_options[selected[0]]
                    newer = compare_options[selected[1]]
                    from policy_compare import compare_policy_text
                    comparison = compare_policy_text(older["content_text"], newer["content_text"])
                    st.metric("Text similarity", f"{comparison['similarity_percent']}%")
                    st.write(f"Added clauses: {comparison['added_count']} · Removed clauses: {comparison['removed_count']}")
                    if comparison["changed_terms"]:
                        st.write("**Changed terms**")
                        st.dataframe(comparison["changed_terms"], width="stretch", hide_index=True)
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Added**")
                        st.write("\\n".join(comparison["added"]) or "None")
                    with col2:
                        st.write("**Removed**")
                        st.write("\\n".join(comparison["removed"]) or "None")
                    with st.expander("Unified diff"):
                        st.code("\\n".join(comparison["unified_diff"]) or "No textual differences")


if __name__ == "__main__":
    main()
