"""Run the three fictional demo cases through Streamlit with Playwright.

The app uses a temporary SQLite/storage/Chroma directory. Screenshots are saved
outside the repository in the system temporary directory.
"""
from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEMO_CASES = ROOT / "samples" / "demo_cases"


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_browser_suite() -> dict[str, Any]:
    try:
        import requests
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return {"numerator": 0, "denominator": 0, "score": None, "target": "3/3 cases and appeal gating",
                "pass": None, "status": "NOT RUN", "reason": f"Browser dependency unavailable: {exc}"}

    work = tempfile.TemporaryDirectory(prefix="mediguard-browser-eval-")
    work_path = Path(work.name)
    screenshot_dir = Path(tempfile.mkdtemp(prefix="mediguard-eval-screenshots-"))
    server_log = screenshot_dir / "streamlit.log"
    port = _port()
    password = "EvalOnly-" + os.urandom(10).hex() + "!"
    env = os.environ.copy()
    env.update({
        "OLLAMA_HOST": "http://127.0.0.1:1",
        "MEDIGUARD_EVAL_LIVE": "false",
        "MEDIGUARD_CORE_DEMO": "false",
        "MEDIGUARD_TRUSTED_FIXTURES": "false",
        "MEDIGUARD_ADMIN_EMAIL": "evaluation-admin@fictional.test",
        "MEDIGUARD_ADMIN_PASSWORD": password,
        "MEDIGUARD_DB_PATH": str(work_path / "claims.db"),
        "MEDIGUARD_STORAGE_DIR": str(work_path / "storage"),
        "CHROMA_DIR": str(work_path / "chroma"),
        "MAX_FILE_MB": "1",
    })
    log_handle = server_log.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
         "--server.headless=true", f"--server.port={port}", "--server.address=127.0.0.1",
         "--browser.gatherUsageStats=false", "--server.fileWatcherType=none", "--server.maxUploadSize=2"],
        cwd=ROOT, env=env, stdout=log_handle, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    results: list[dict[str, Any]] = []
    failure_details: dict[str, str] = {}

    def wait_for_saved_documents(claim_number: str, expected_count: int) -> bool:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                with sqlite3.connect(work_path / "claims.db") as connection:
                    row = connection.execute(
                        "SELECT COUNT(*) FROM documents d JOIN claims c ON c.claim_id=d.claim_id WHERE c.claim_number=?",
                        (claim_number,),
                    ).fetchone()
                if row and row[0] == expected_count:
                    return True
            except sqlite3.Error:
                pass
            time.sleep(0.2)
        return False
    try:
        health_url = f"http://127.0.0.1:{port}/_stcore/health"
        ready = False
        for _ in range(90):
            if process.poll() is not None:
                raise RuntimeError(f"Streamlit exited with code {process.returncode} before health check.")
            try:
                if requests.get(health_url, timeout=1).ok:
                    ready = True
                    break
            except requests.RequestException:
                pass
            time.sleep(1)
        if not ready:
            raise TimeoutError("Streamlit did not become healthy within 90 seconds.")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.set_default_timeout(45000)
            page.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")
            page.get_by_text("Admin — secure sign in").click()
            page.get_by_role("button", name="Continue as admin").click()
            page.get_by_placeholder("you@example.com").fill(env["MEDIGUARD_ADMIN_EMAIL"])
            page.get_by_label("Password").first.fill(password)
            page.get_by_role("button", name="Sign in").click()
            page.get_by_text("Policy management", exact=False).click()
            policy_file = DEMO_CASES / "a_match" / "policy.pdf"
            page.locator("input[type=file]").set_input_files(str(policy_file))
            page.get_by_placeholder("POL-DEMO-2026-001").fill("POL-FICT-001")
            page.get_by_placeholder("2026 Edition").fill("Fictional 2026")
            page.get_by_placeholder("Example Health Insurance Ltd.").fill("Fictional Sample Insurer")
            page.get_by_role("button", name="Ingest & activate edition").click()
            edition_label = "POL-FICT-001 · Fictional 2026 · policy.pdf"
            try:
                page.get_by_text(edition_label).wait_for(timeout=45000)
            except Exception:
                failure_details["policy_page_tail"] = page.locator("body").inner_text(timeout=5000)[-4000:]
                failure_details["policy_screenshot"] = str(screenshot_dir / "policy-ingestion-failure.png")
                page.screenshot(path=failure_details["policy_screenshot"], full_page=True, timeout=10000)
                raise
            page.get_by_text(edition_label).click()
            page.get_by_role("button", name="Save and confirm policy terms").click()
            try:
                page.get_by_text("Status: confirmed").wait_for(timeout=60000)
            except Exception:
                try:
                    failure_details["policy_page_tail"] = page.locator("body").inner_text(timeout=5000)[-4000:]
                    failure_details["policy_failure_screenshot"] = str(screenshot_dir / "policy-confirmation-failure.png")
                    page.screenshot(path=failure_details["policy_failure_screenshot"], full_page=True, timeout=10000)
                except Exception as diagnostic_error:
                    failure_details["diagnostic_capture_error"] = f"{type(diagnostic_error).__name__}: {diagnostic_error}"
                raise
            page.screenshot(path=str(screenshot_dir / "policy-confirmed.png"), full_page=True)
            page.close()

            def fresh_admin_page() -> Any:
                isolated_page = browser.new_page(viewport={"width": 1440, "height": 1000})
                isolated_page.set_default_timeout(45000)
                isolated_page.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")
                isolated_page.get_by_text("Admin — secure sign in").click()
                isolated_page.get_by_role("button", name="Continue as admin").click()
                isolated_page.get_by_placeholder("you@example.com").fill(env["MEDIGUARD_ADMIN_EMAIL"])
                isolated_page.get_by_label("Password").first.fill(password)
                isolated_page.get_by_role("button", name="Sign in").click()
                isolated_page.get_by_text("Policy management", exact=False).wait_for(timeout=20000)
                return isolated_page

            def register_claim(isolated_page: Any, claim_number: str, patient_name: str) -> None:
                isolated_page.get_by_text("Register claim", exact=False).click()
                isolated_page.get_by_role("textbox", name="Claim number").fill(claim_number)
                isolated_page.get_by_role("textbox", name="Patient name").fill(patient_name)
                isolated_page.get_by_role("textbox", name="Policy number").fill("POL-FICT-001")
                isolated_page.get_by_role("textbox", name="Hospital / provider").fill("Fictional City Hospital")
                isolated_page.locator("input[type=date]").fill("2026-08-10")
                isolated_page.get_by_role("button", name="Save claim and continue").click()
                isolated_page.get_by_label("Selected claim").wait_for(timeout=30000)

            expected = {
                "a_match": {"claim_number": "CLM-FICT-0417", "patient": "Ananya Sample", "status": "no_discrepancy", "difference": "INR 0.00", "appeal": False},
                "b_wrongful_deduction": {"claim_number": "CLM-FICT-0418", "patient": "Bhavna Sample", "status": "possible_discrepancy", "difference": "INR 2,700.00", "appeal": True},
                "c_manual_review": {"claim_number": "CLM-FICT-0419", "patient": "Chandra Sample", "status": "manual_review", "difference": "Pending review", "appeal": False},
            }
            only_case = os.getenv("MEDIGUARD_BROWSER_ONLY", "").strip()
            if only_case:
                expected = {key: value for key, value in expected.items() if key == only_case}
            for case_name, label in expected.items():
                page = fresh_admin_page()
                case_dir = DEMO_CASES / case_name
                register_claim(page, label["claim_number"], label["patient"])
                page.get_by_label("Selected claim").click()
                page.get_by_role("option", name=f"{label['claim_number']} · {label['patient']}").click()
                page.get_by_role("tab", name="2 · Add documents").click()
                page.get_by_label("Policy documents").locator("input[type=file]").set_input_files(str(case_dir / "policy.pdf"))
                page.get_by_label("Medical bill / supporting documents").locator("input[type=file]").set_input_files(str(case_dir / "bill.pdf"))
                page.get_by_label("Insurer settlement letter").locator("input[type=file]").set_input_files(str(case_dir / "settlement.pdf"))
                page.get_by_role("button", name="Save uploaded documents").click()
                try:
                    # The success message is followed immediately by st.rerun;
                    # check the persisted result rather than a transient toast.
                    if not wait_for_saved_documents(label["claim_number"], 3):
                        raise TimeoutError("Three uploaded documents were not persisted for this claim.")
                except Exception:
                    try:
                        failure_details["upload_page_tail"] = page.locator("body").inner_text(timeout=5000)[-4000:]
                        failure_details["upload_screenshot"] = str(screenshot_dir / f"{case_name}-upload-failure.png")
                        page.screenshot(path=failure_details["upload_screenshot"], full_page=True, timeout=10000)
                    except Exception as diagnostic_error:
                        failure_details["diagnostic_capture_error"] = f"{type(diagnostic_error).__name__}: {diagnostic_error}"
                    raise
                page.get_by_role("tab", name="3 · Check extraction").click()
                page.get_by_role("button", name="Run extraction").click()
                page.get_by_text("Extraction complete").wait_for(timeout=60000)
                if page.get_by_role("button", name="Save reviewer-confirmed bill details").count():
                    page.get_by_role("button", name="Save reviewer-confirmed bill details").click()
                page.get_by_role("tab", name="4 · Calculate & review").click()
                if page.get_by_role("button", name="Link edition to this claim").count():
                    page.get_by_role("button", name="Link edition to this claim").click()
                    page.get_by_text("Term review: confirmed").wait_for(timeout=20000)
                page.get_by_role("button", name="Run deterministic coverage rules").click()
                page.get_by_text("Rules complete").wait_for(timeout=30000)
                page.get_by_role("tab", name="5 · Compare settlement & draft letters").click()
                compare_button = page.get_by_role("button", name="Run settlement comparison")
                compare_button.wait_for(state="visible", timeout=30000)
                compare_button.click()
                try:
                    page.get_by_text("Settlement comparison", exact=True).wait_for(timeout=60000)
                except Exception:
                    try:
                        failure_details["visible_page_tail"] = page.locator("body").inner_text(timeout=5000)[-4000:]
                        failure_details["failure_screenshot"] = str(screenshot_dir / "failure.png")
                        page.screenshot(path=failure_details["failure_screenshot"], full_page=True, timeout=10000)
                    except Exception as diagnostic_error:
                        failure_details["diagnostic_capture_error"] = f"{type(diagnostic_error).__name__}: {diagnostic_error}"
                    raise
                terminal_text = (
                    "Review documents" if label["appeal"] else
                    "An appeal draft is not available while this comparison needs manual review."
                    if case_name == "c_manual_review" else
                    "No appeal draft is available because no possible settlement discrepancy was identified."
                )
                # The heading and top-level result appear before the remaining
                # widgets in the same Streamlit rerun. Wait for the terminal
                # result section before checking downloads or taking evidence.
                try:
                    page.get_by_text(terminal_text, exact=False).wait_for(timeout=30000)
                except Exception:
                    failure_details["terminal_page_tail"] = page.locator("body").inner_text(timeout=5000)[-3000:]
                    failure_details["terminal_screenshot"] = str(screenshot_dir / f"{case_name}-terminal-failure.png")
                    page.screenshot(path=failure_details["terminal_screenshot"], full_page=True, timeout=10000)
                    raise
                body = page.locator("body").inner_text()
                appeal_link = page.get_by_text("Appeal letter (PDF)", exact=True)
                appeal_available = appeal_link.count() == 1
                appeal_download = None
                if appeal_available:
                    with page.expect_download(timeout=15000) as download_info:
                        appeal_link.click()
                    appeal_download = download_info.value.suggested_filename
                status_ok = {
                    "a_match": "No discrepancy was identified" in body,
                    "b_wrongful_deduction": "possible settlement discrepancy" in body,
                    "c_manual_review": "An appeal draft is not available while this comparison needs manual review." in body,
                }[case_name]
                difference_ok = label["difference"] in body
                result = {"case": case_name, "expected_status": label["status"], "status_match": status_ok,
                          "expected_difference": label["difference"], "difference_match": difference_ok,
                          "expected_appeal": label["appeal"], "actual_appeal": appeal_available,
                          "appeal_download": appeal_download,
                          "appeal_text_present": "Appeal letter (PDF)" in body,
                          "download_widget_count": page.locator('[data-testid="stDownloadButton"]').count(),
                          "appeal_match": appeal_available == label["appeal"],
                          "passed": status_ok and difference_ok and appeal_available == label["appeal"],
                          "screenshot": str(screenshot_dir / f"{case_name}.png")}
                page.screenshot(path=result["screenshot"], full_page=True)
                results.append(result)
                page.close()

            # Invalid-upload and missing-document checks use a separate
            # Playwright page/session and a unique claim for each scenario.
            upload_scenarios = ["empty_file", "wrong_type", "oversized", "corrupted_pdf", "missing_settlement"]
            if only_case in upload_scenarios:
                upload_scenarios = [only_case]
            elif only_case:
                upload_scenarios = []
            upload_assets = screenshot_dir / "upload_fixtures"
            upload_assets.mkdir()
            (upload_assets / "empty.pdf").write_bytes(b"")
            (upload_assets / "wrong_type.pdf").write_bytes(b"FICTIONAL SAMPLE: this is not a PDF")
            (upload_assets / "oversized.pdf").write_bytes(b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 1))
            (upload_assets / "corrupted.pdf").write_bytes(b"%PDF-1.4\nFICTIONAL SAMPLE - intentionally corrupted PDF")
            claim_ids = {
                "empty_file": ("CLM-EVAL-EMPTY", "Empty Upload Sample"),
                "wrong_type": ("CLM-EVAL-WRONGTYPE", "Wrong Type Sample"),
                "oversized": ("CLM-EVAL-OVERSIZE", "Oversized Upload Sample"),
                "corrupted_pdf": ("CLM-EVAL-CORRUPT", "Corrupted PDF Sample"),
                "missing_settlement": ("CLM-EVAL-NOSETTLE", "Missing Settlement Sample"),
            }
            for scenario in upload_scenarios:
                page = fresh_admin_page()
                claim_number, patient_name = claim_ids[scenario]
                register_claim(page, claim_number, patient_name)
                page.get_by_role("tab", name="2 · Add documents").click()
                bill_input = page.get_by_label("Medical bill / supporting documents").locator("input[type=file]")
                if scenario == "missing_settlement":
                    bill_input.set_input_files(str(DEMO_CASES / "a_match" / "bill.pdf"))
                    page.get_by_role("button", name="Save uploaded documents").click()
                    if not wait_for_saved_documents(claim_number, 1):
                        raise TimeoutError("The bill upload was not persisted for the missing-settlement check.")
                    page.get_by_role("tab", name="5 · Compare settlement & draft letters").click()
                    missing_message = "Upload and save the insurer settlement letter in Add documents first."
                    try:
                        page.get_by_text(missing_message, exact=False).wait_for(timeout=15000)
                    except Exception:
                        failure_details["missing_settlement_body"] = page.locator("body").inner_text(timeout=5000)[-2000:]
                        failure_details["missing_settlement_screenshot"] = str(screenshot_dir / "missing-settlement-debug.png")
                        page.screenshot(path=failure_details["missing_settlement_screenshot"], full_page=True, timeout=10000)
                        raise
                    body = page.locator("body").inner_text()
                    passed = missing_message in body
                    appeal_shown = page.get_by_text("Appeal letter (PDF)", exact=True).count() > 0
                    passed = passed and not appeal_shown
                else:
                    filename = {
                        "empty_file": "empty.pdf", "wrong_type": "wrong_type.pdf",
                        "oversized": "oversized.pdf", "corrupted_pdf": "corrupted.pdf",
                    }[scenario]
                    bill_input.set_input_files(str(upload_assets / filename))
                    page.get_by_role("button", name="Save uploaded documents").click()
                    if scenario == "corrupted_pdf":
                        if not wait_for_saved_documents(claim_number, 1):
                            raise TimeoutError("The corrupted PDF upload was not persisted.")
                        page.get_by_role("tab", name="3 · Check extraction").click()
                        page.get_by_role("button", name="Run extraction").click()
                        try:
                            page.get_by_text("Extraction failed", exact=True).wait_for(timeout=20000)
                        except Exception:
                            pass
                        body = page.locator("body").inner_text()
                        passed = (
                            "Extraction failed" in body
                            or "Extraction complete" in body
                            or "Document extraction did not finish. Check the uploaded files and try again." in body
                        ) and "Traceback" not in body and "FileNotFoundError" not in body
                    else:
                        body = page.locator("body").inner_text()
                        try:
                            page.get_by_text("One or more files could not be saved. Check the supported file type, size and file contents.", exact=True).wait_for(timeout=15000)
                            body = page.locator("body").inner_text()
                            passed = True
                        except Exception:
                            body = page.locator("body").inner_text()
                            # Streamlit itself can reject a payload at its
                            # configured upload ceiling before app validation.
                            safe_size_rejection = any(text in body.casefold() for text in (
                                "file is too large", "maximum file size", "exceeds the maximum", "15 mb",
                                "one or more files could not be saved. check the supported file type, size and file contents.",
                            ))
                            passed = safe_size_rejection
                screenshot = str(screenshot_dir / f"{scenario}.png")
                page.screenshot(path=screenshot, full_page=True)
                results.append({"case": scenario, "passed": passed, "screenshot": screenshot,
                                "expected": "friendly validation or safe missing-settlement state",
                                "actual": "passed" if passed else body[-1200:]})
                page.close()
            browser.close()
    except Exception as exc:
        results.append({"case": "browser_setup_or_flow", "passed": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        **failure_details,
                        "server_log_tail": server_log.read_text(encoding="utf-8", errors="replace")[-6000:] if server_log.exists() else ""})
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        # Streamlit can leave a child process holding Chroma files on Windows.
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False)
        log_handle.close()
        try:
            work.cleanup()
        except PermissionError:
            # The evaluation result and screenshots are more important than
            # immediate removal of a temporary directory locked by the OS.
            import shutil
            shutil.rmtree(work_path, ignore_errors=True)

    passed = sum(bool(row.get("passed")) for row in results)
    return {"numerator": passed, "denominator": 8, "score": passed / 8,
            "target": "3 demo cases and 5 upload/error cases", "pass": passed == 8,
            "cases": results, "screenshots_directory": str(screenshot_dir),
            "note": "Upload and reviewer-confirmed policy terms were exercised in a temporary local app instance."}


def main() -> int:
    result = run_browser_suite()
    print(json.dumps(result, indent=2))
    return 0 if result.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
