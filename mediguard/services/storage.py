"""Local path and upload-validation helpers for the prototype."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def database_path(data_dir: Path) -> Path:
    return Path(os.getenv("MEDIGUARD_DB_PATH", str(data_dir / "mediguard.db"))).resolve()


def storage_path(data_dir: Path) -> Path:
    return Path(os.getenv("MEDIGUARD_STORAGE_DIR", str(data_dir))).resolve()


def open_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def validate_upload(uploaded_file, document_type: str | None, max_file_mb: int) -> tuple[bytes, str]:
    # Browser uploads may include Windows separators even when the server is
    # running on POSIX. Normalize both separator styles before taking basename.
    original_name = Path(str(uploaded_file.name).replace("\\", "/")).name
    extension = Path(original_name).suffix.lower()
    allowed = {".pdf", ".txt"} if document_type == "settlement" else {".pdf", ".png", ".jpg", ".jpeg"}
    if extension not in allowed:
        message = "Settlement letter must be a PDF or UTF-8 text file." if document_type == "settlement" else "Unsupported file type. Upload a PDF, PNG, JPG, or JPEG file."
        raise ValueError(message)
    content = uploaded_file.getvalue()
    if len(content) > max_file_mb * 1024 * 1024:
        raise ValueError(f"File exceeds the {max_file_mb} MB limit.")
    if not content:
        raise ValueError("The uploaded file is empty.")
    signatures = {".pdf": b"%PDF", ".png": b"\x89PNG", ".jpg": b"\xff\xd8", ".jpeg": b"\xff\xd8"}
    if extension in signatures and not content.startswith(signatures[extension]):
        kind = "PDF" if extension == ".pdf" else "PNG" if extension == ".png" else "JPG/JPEG"
        raise ValueError(f"The file extension is {kind}, but the file signature is invalid.")
    if document_type == "settlement" and extension == ".txt":
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Settlement text must use UTF-8 encoding.") from exc
    return content, original_name
