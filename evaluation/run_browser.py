"""Run the three fictional demo cases through Streamlit with Playwright.

The app uses a temporary SQLite/storage/Chroma directory. Screenshots are saved
outside the repository in the system temporary directory.
"""
from __future__ import annotations

import json
import os
import socket
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
    })
    log_handle = server_log.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
         "--server.headless=true", f"--server.port={port}", "--server.address=127.0.0.1",
         "--browser.gatherUsageStats=false", "--server.fileWatcherType=none"],
        cwd=ROOT, env=env, stdout=log_handle, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    results: list[dict[str, Any]] = []
    failure_details: dict[str, str] = {}
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
            page.get_by_text(edition_label).wait_for(timeout=45000)
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

            expected = {
                "a_match": {"claim_number": "CLM-FICT-0417", "patient": "Ananya Sample", "status": "no_discrepancy", "difference": "INR 0.00", "appeal": False},
                "b_wrongful_deduction": {"claim_number": "CLM-FICT-0418", "patient": "Bhavna Sample", "status": "possible_discrepancy", "difference": "INR 2,700.00", "appeal": True},
                "c_manual_review": {"claim_number": "CLM-FICT-0419", "patient": "Chandra Sample", "status": "manual_review", "difference": "Pending review", "appeal": False},
            }
            for case_name, label in expected.items():
                case_dir = DEMO_CASES / case_name
                page.get_by_text("Register claim", exact=False).click()
                page.get_by_role("textbox", name="Claim number").fill(label["claim_number"])
                page.get_by_role("textbox", name="Patient name").fill(label["patient"])
                page.get_by_role("textbox", name="Policy number").fill("POL-FICT-001")
                page.get_by_role("textbox", name="Hospital / provider").fill("Fictional City Hospital")
                page.locator("input[type=date]").fill("2026-08-10")
                page.get_by_role("button", name="Save claim and continue").click()
                page.get_by_text("Claim review", exact=True).first.click()
                # The review page retains the previously selected claim after
                # registering another one; explicitly select this case's ID.
                page.get_by_label("Selected claim").click()
                page.get_by_role("option", name=f"{label['claim_number']} · {label['patient']}").click()
                page.get_by_role("tab", name="2 · Add documents").click()
                page.get_by_label("Policy documents").locator("input[type=file]").set_input_files(str(case_dir / "policy.pdf"))
                page.get_by_label("Medical bill / supporting documents").locator("input[type=file]").set_input_files(str(case_dir / "bill.pdf"))
                page.get_by_label("Insurer settlement letter").locator("input[type=file]").set_input_files(str(case_dir / "settlement.pdf"))
                page.get_by_role("button", name="Save uploaded documents").click()
                try:
                    page.get_by_text("Saved 3 document(s).", exact=True).wait_for(timeout=30000)
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
                if page.get_by_role("button", name="Run settlement comparison").count():
                    page.get_by_role("button", name="Run settlement comparison").click()
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
                body = page.locator("body").inner_text()
                appeal_available = page.get_by_role("button", name="Appeal letter (PDF)").count() == 1
                status_ok = {
                    "a_match": "No discrepancy was identified" in body,
                    "b_wrongful_deduction": "possible settlement discrepancy" in body,
                    "c_manual_review": "An appeal draft is not available while this comparison needs manual review." in body,
                }[case_name]
                difference_ok = label["difference"] in body
                result = {"case": case_name, "expected_status": label["status"], "status_match": status_ok,
                          "expected_difference": label["difference"], "difference_match": difference_ok,
                          "expected_appeal": label["appeal"], "actual_appeal": appeal_available,
                          "appeal_match": appeal_available == label["appeal"],
                          "passed": status_ok and difference_ok and appeal_available == label["appeal"],
                          "screenshot": str(screenshot_dir / f"{case_name}.png")}
                page.screenshot(path=result["screenshot"], full_page=True)
                results.append(result)
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
    return {"numerator": passed, "denominator": 3, "score": passed / 3,
            "target": "all three demo cases and appeal gating", "pass": passed == 3,
            "cases": results, "screenshots_directory": str(screenshot_dir),
            "note": "Upload and reviewer-confirmed policy terms were exercised in a temporary local app instance."}


def main() -> int:
    result = run_browser_suite()
    print(json.dumps(result, indent=2))
    return 0 if result.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
