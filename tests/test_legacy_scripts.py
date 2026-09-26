"""Execute the repository's existing script-style checks as pytest tests.

The legacy checks contain top-level assertions rather than pytest test
functions. Run each in a separate interpreter so their environment variables,
Streamlit state, and temporary databases cannot leak into other checks.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEGACY_CHECKS = (
    "test_academic_e2e.py",
    "test_audit_regressions.py",
    "test_core_advancements.py",
    "test_demo_scenarios.py",
    "test_end_to_end.py",
    "test_phase5_real_document_quality.py",
    "test_phase6_business_rules.py",
    "test_ui_audit.py",
)


@pytest.mark.parametrize("script_name", LEGACY_CHECKS)
def test_existing_project_check(script_name: str) -> None:
    environment = os.environ.copy()
    environment.setdefault("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    environment.setdefault("HF_HOME", str(ROOT / ".venv" / "hf-cache"))
    environment.setdefault("HF_HUB_OFFLINE", "1")
    completed = subprocess.run(
        [sys.executable, str(ROOT / script_name)],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=900,
        check=False,
    )
    if completed.returncode:
        pytest.fail(
            f"{script_name} exited {completed.returncode}\n"
            f"--- stdout ---\n{completed.stdout[-5000:]}\n"
            f"--- stderr ---\n{completed.stderr[-5000:]}"
        )
    print(completed.stdout)
