"""Opt-in Playwright checks for claimant-facing result presentation.

Run with MEDIGUARD_EVAL_BROWSER=true python -m pytest -q tests/browser/test_claimant_presentation.py
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.skipif(
    os.getenv("MEDIGUARD_EVAL_BROWSER", "false").lower() != "true",
    reason="Set MEDIGUARD_EVAL_BROWSER=true to run the real-browser checks.",
)


@pytest.fixture(scope="module")
def claimant_app(tmp_path_factory):
    root = tmp_path_factory.mktemp("claimant-presentation")
    db_path = root / "app.sqlite3"
    storage_path = root / "private"
    old_env = {key: os.environ.get(key) for key in ("MEDIGUARD_DB_PATH", "MEDIGUARD_STORAGE_DIR", "MEDIGUARD_TRUSTED_FIXTURES", "OLLAMA_HOST")}
    os.environ["MEDIGUARD_DB_PATH"] = str(db_path)
    os.environ["MEDIGUARD_STORAGE_DIR"] = str(storage_path)
    os.environ["MEDIGUARD_TRUSTED_FIXTURES"] = "false"
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:1"

    from mediguard.services import application as app
    from mediguard.engine.models import (
        CategoryComparison, Clause, ComparisonResult, SettlementData, SettlementDeduction,
    )

    app.init_db()
    password = "<your-demo-password>"
    user = dict(app.register_user("browser-claimant@fictional.test", "Fictional Browser Claimant", password))
    names = ("a_match", "b_wrongful_deduction", "c_manual_review")
    claim_labels = {}
    for name in names:
        manifest = json.loads((Path(__file__).parents[2] / "samples" / "demo_cases" / name / "case.json").read_text(encoding="utf-8"))
        claim_id = app.create_claim(
            user["user_id"], manifest["claim_number"], manifest["patient_name"],
            manifest["hospital_name"], manifest["policy_number"], "2026-08-10",
        )
        expected = manifest["expected"]
        is_b = name == "b_wrongful_deduction"
        is_c = name == "c_manual_review"
        rules = {
            "status": "manual_review" if is_c else "partially_approved",
            "policy_terms_review_status": "provisional",
            "claimant_result": {
                "amount_billed": 47000,
                "amount_covered": None if is_c else 22500,
                "amount_claimant_pays": None if is_c else 24500,
                "deductible": 10000,
                "copayment": 2500,
                "amount_excluded_or_limited": 10000,
                "covered_before_cost_sharing": 35000,
            },
            "payable_amount": None if is_c else 22500,
            "deductible": 10000,
            "copayment": 2500,
            "warnings": ["room_limit_applied"],
            "policy_terms_issues": ([{
                "term": "deductible", "page": 1,
                "reason": "Deductible: the 0.60-confidence candidate was not applied, and no current bill line matches it. Confirm this term to check whether the result changes.",
            }] if is_c else []),
            "results": [{"rule_id": "room_limit_applied", "status": "partial", "calculation": "Room charges were limited under the policy.", "amount": 10000}],
            "line_item_results": [],
        }
        with app.db() as conn:
            conn.execute(
                "INSERT INTO rule_evaluations VALUES (?,?,?,?,?,?)",
                (str(uuid.uuid4()), claim_id, "browser-fixture", rules["status"], json.dumps(rules), app.utc_now()),
            )
            conn.execute("UPDATE claims SET status=? WHERE claim_id=?", (rules["status"], claim_id))
            document_hash = ("b" if is_b else "c" if is_c else "a") * 64
            conn.execute(
                "INSERT INTO documents(document_id,claim_id,original_name,stored_path,document_type,size_bytes,sha256,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), claim_id, "fictional-settlement.txt", str(root / "settlement.txt"), "settlement", 1, document_hash, app.utc_now()),
            )
        clause = Clause("Diagnostic investigations are payable during hospitalization.", 1, "coverage")
        categories = ([CategoryComparison(
            "INVESTIGATION", Decimal("3000"), Decimal("0"), Decimal("3000"),
            "EXCESS_DEDUCTION", "Outside pre-hospitalization window",
            "Diagnostic investigations are payable during hospitalization.", clause,
            Decimal("2700"),
        )] if is_b else [])
        comparison = ComparisonResult(
            expected_patient_share=None if is_c else Decimal(str(expected["expected_patient_share"])),
            actual_patient_share=Decimal("27200" if is_b else "24500"),
            possible_difference=None if is_c else Decimal(str(expected["possible_difference"])),
            categories=categories,
            status="manual_review" if is_c else expected["expected_status"],
            review_reasons=["Settlement amount needs reviewer verification."] if is_c else [],
            billed_total=Decimal("47000"),
            actual_insurer_payment=None if is_c else Decimal(str(expected.get("actual_insurer_payment", expected["expected_insurer_payment"]))),
            expected_insurer_payment=None if is_c else Decimal(str(expected["expected_insurer_payment"])),
        )
        settlement = SettlementData(
            manifest["claim_number"],
            None if is_c else Decimal(str(expected.get("actual_insurer_payment", expected["expected_insurer_payment"]))),
            [SettlementDeduction("INVESTIGATION", Decimal("3000"), "Outside pre-hospitalization window")] if is_b else [],
            needs_review=is_c,
            review_reasons=["Amount paid is missing."] if is_c else [],
            bill_total=Decimal("47000"),
        )
        app.save_settlement_comparison(claim_id, document_hash, comparison, settlement)
        claim_labels[name] = f"{manifest['claim_number']} · {manifest['patient_name']}"

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.address", "127.0.0.1", "--server.port", str(port), "--server.headless", "true"],
        cwd=Path(__file__).parents[2], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        import requests
        for _ in range(60):
            try:
                if requests.get(base_url + "/_stcore/health", timeout=1).status_code == 200:
                    break
            except requests.RequestException:
                time.sleep(0.5)
        yield base_url, "browser-claimant@fictional.test", password, claim_labels
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def with_signed_in_page(claimant_app, check):
    base_url, email, password, labels = claimant_app
    failures = []

    def run():
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_default_timeout(7000)
                page.goto(base_url, wait_until="domcontentloaded")
                page.get_by_role("button", name="Continue as user").click()
                page.locator('input[aria-label="Email"]').first.fill(email)
                page.locator('input[aria-label="Password"]').first.fill(password)
                page.get_by_role("button", name="Sign in").click()
                try:
                    page.get_by_text("Welcome back, Fictional Browser Claimant", exact=True).wait_for(timeout=15000)
                except Exception as exc:
                    raise RuntimeError("Sign-in did not reach the dashboard: " + page.locator("body").inner_text()) from exc
                check(page, labels)
                browser.close()
        except BaseException as exc:
            failures.append(exc)

    worker = threading.Thread(target=run)
    worker.start()
    worker.join(timeout=60)
    if worker.is_alive():
        raise TimeoutError("Playwright claimant presentation check exceeded 60 seconds.")
    if failures:
        raise failures[0]


def open_result(page, claim_label):
    selector = page.get_by_label("Choose a claim")
    if selector.count() == 0:
        page.get_by_text("Claim result", exact=False).first.click()
        selector = page.get_by_label("Choose a claim")
    selector = page.get_by_label("Choose a claim")
    claim_number = claim_label.split(" · ", 1)[0]
    selector.fill(claim_number)
    selector.press("ArrowDown")
    selector.press("Enter")
    page.wait_for_function(
        "claimNumber => [...document.querySelectorAll('input[role=combobox]')].some(input => input.getAttribute('aria-label') === 'Choose a claim' && input.value.includes(claimNumber))",
        arg=claim_number,
        timeout=10000,
    )
    page.get_by_role("heading", name="Your claim result").wait_for(timeout=10000)
    page.wait_for_timeout(500)


def test_playwright_possible_discrepancy_next_step_names_amount_and_appeal(claimant_app):
    def check(page, labels):
        open_result(page, labels["b_wrongful_deduction"])
        page.get_by_text("Settlement comparison", exact=True).wait_for(timeout=10000)
        body = page.locator("body").inner_text()
        assert "The settlement differs from the policy-based estimate by INR 2,700.00" in body, body
        assert "Settlement comparison below" in body
        assert "appeal draft" in body.casefold()
        assert "No action is needed" not in body
    with_signed_in_page(claimant_app, check)


def test_playwright_claimant_text_has_no_internal_codes_or_duplicate_term_issue(claimant_app):
    def check(page, labels):
        open_result(page, labels["c_manual_review"])
        page.get_by_text("Deductible: The extracted value has confidence 0.60", exact=False).wait_for(timeout=10000)
        body = page.locator("body").inner_text()
        assert "confidence candidate" not in body.casefold()
        assert "room_limit_applied" not in body
        assert body.count("Deductible: The extracted value has confidence 0.60") == 1
        assert "policy page 1" in body
    with_signed_in_page(claimant_app, check)


def test_playwright_only_wrongful_deduction_has_provisional_appeal_downloads(claimant_app):
    def check(page, labels):
        open_result(page, labels["b_wrongful_deduction"])
        page.get_by_text("PROVISIONAL DRAFT", exact=False).wait_for(timeout=10000)
        pdf_button = page.get_by_role("button", name="Appeal letter (PDF)")
        docx_button = page.get_by_role("button", name="Appeal letter (Word)")
        pdf_button.wait_for(timeout=10000)
        docx_button.wait_for(timeout=10000)
        body = page.locator("body").inner_text()
        assert "PROVISIONAL DRAFT" in body
        with page.expect_download() as pdf_info:
            pdf_button.click()
        pdf_download = pdf_info.value
        assert pdf_download.suggested_filename.endswith(".pdf")
        import fitz
        pdf_text = " ".join(page_text.get_text() for page_text in fitz.open(pdf_download.path()))
        with page.expect_download() as docx_info:
            docx_button.click()
        docx_download = docx_info.value
        assert docx_download.suggested_filename.endswith(".docx")
        from io import BytesIO
        from docx import Document
        docx_text = " ".join(paragraph.text for paragraph in Document(BytesIO(Path(docx_download.path()).read_bytes())).paragraphs)
        assert "PROVISIONAL DRAFT" in pdf_text and "PROVISIONAL DRAFT" in docx_text
        assert "diagnostic lab tests and investigations" in pdf_text.casefold()
        assert "diagnostic lab tests and investigations" in docx_text.casefold()
        assert "co-pay by INR 300" not in pdf_text and "co-pay by INR 300" not in docx_text
        for case_name, result_text in (("a_match", "No discrepancy was identified"), ("c_manual_review", "Manual review is needed")):
            open_result(page, labels[case_name])
            page.get_by_text(result_text, exact=False).wait_for(timeout=10000)
            page.get_by_role("button", name="Appeal letter (PDF)").wait_for(state="detached", timeout=10000)
            page.get_by_role("button", name="Appeal letter (Word)").wait_for(state="detached", timeout=10000)
    with_signed_in_page(claimant_app, check)
