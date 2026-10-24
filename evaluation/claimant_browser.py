"""Claimant-first Playwright checks against a fresh, isolated Streamlit app."""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "samples" / "demo_cases"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_claimant_browser_suite() -> dict[str, Any]:
    try:
        import requests
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return {"numerator": 0, "denominator": 8, "pass": False, "reason": str(exc)}

    scratch = tempfile.TemporaryDirectory(prefix="mediguard-claimant-browser-")
    work = Path(scratch.name)
    screenshots = Path(tempfile.mkdtemp(prefix="mediguard-claimant-screenshots-"))
    port = _free_port()
    email_admin = "browser-admin@fictional.test"
    password_admin = "<your-demo-password>"
    env = os.environ.copy()
    env.update({
        "MEDIGUARD_DB_PATH": str(work / "claims.db"),
        "MEDIGUARD_STORAGE_DIR": str(work / "storage"),
        "CHROMA_DIR": str(work / "chroma"),
        "MEDIGUARD_ADMIN_EMAIL": email_admin,
        "MEDIGUARD_ADMIN_PASSWORD": password_admin,
        "MEDIGUARD_TRUSTED_FIXTURES": "false",
        "MEDIGUARD_CORE_DEMO": "false",
        "OLLAMA_HOST": "http://127.0.0.1:1",
        "MAX_FILE_MB": "1",
    })
    log_path = screenshots / "streamlit.log"
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
         "--server.headless=true", f"--server.port={port}", "--server.address=127.0.0.1",
         "--browser.gatherUsageStats=false", "--server.fileWatcherType=none", "--server.maxUploadSize=2"],
        cwd=ROOT, env=env, stdout=log_handle, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    outcomes: list[dict[str, Any]] = []
    reviewer_refresh: dict[str, Any] = {"passed": False, "reason": "not run"}
    failure: str | None = None

    def make_claimant(page: Any, claim_no: str, name: str) -> str:
        page.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")
        page.get_by_text("User — sign in or create account", exact=False).click()
        page.get_by_role("button", name="Continue as user").click()
        page.get_by_role("tab", name="Create account").click()
        email = f"{claim_no.lower()}@fictional.test"
        page.locator('input[aria-label="Full name"]:visible').fill(name)
        page.locator('input[aria-label="Email"]:visible').last.fill(email)
        passwords = page.locator('input[type="password"]:visible')
        p1 = passwords.first
        p1.fill("<your-demo-password>")
        passwords.nth(1).fill("<your-demo-password>")
        page.get_by_role("button", name="Create account").click()
        page.get_by_text("Register claim", exact=False).click()
        page.get_by_role("textbox", name="Claim number").fill(claim_no)
        page.get_by_role("textbox", name="Patient name").fill(name)
        page.get_by_role("textbox", name="Policy number").fill("POL-FICT-001")
        page.get_by_role("textbox", name="Hospital / provider").fill("Fictional City Hospital")
        page.get_by_role("button", name="Save claim and continue").click()
        page.get_by_text("Add your documents", exact=False).first.wait_for(timeout=20000)
        return email

    def upload_files(page: Any, case_dir: Path, include_settlement: bool = True) -> None:
        items = [
            ("Insurance policy", case_dir / "policy.pdf"),
            ("Medical bill and supporting documents", case_dir / "bill.pdf"),
        ]
        if include_settlement:
            items.append(("Insurer settlement letter", case_dir / "settlement.pdf"))
        for label, path in items:
            page.get_by_label(label).locator("input[type=file]").set_input_files(str(path))
            page.wait_for_timeout(450)
        page.get_by_role("button", name="Save documents").click()
        page.get_by_text("document(s) ready for assessment", exact=False).wait_for(timeout=15000)

    def assess(page: Any, *, has_settlement: bool = True) -> str:
        page.get_by_role("button", name="Submit claim for assessment").click()
        result_started = time.perf_counter()
        page.get_by_text("Your claim result", exact=True).wait_for(timeout=60000)
        assess.time_to_first_result_seconds = round(time.perf_counter() - result_started, 3)
        if has_settlement:
            page.get_by_text("Settlement comparison", exact=True).wait_for(timeout=60000)
        else:
            page.get_by_text("Upload the insurer's settlement letter to compare it", exact=False).wait_for(timeout=30000)
        page.wait_for_timeout(500)
        return page.locator("body").inner_text(timeout=10000)

    try:
        health = f"http://127.0.0.1:{port}/_stcore/health"
        for _ in range(90):
            if process.poll() is not None:
                raise RuntimeError(f"Streamlit exited with code {process.returncode}.")
            try:
                if requests.get(health, timeout=1).ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(1)
        else:
            raise TimeoutError("Fresh Streamlit app did not become healthy.")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            pages: dict[str, Any] = {}
            manifests: dict[str, dict[str, Any]] = {}
            for case_name in ("a_match", "b_wrongful_deduction", "c_manual_review"):
                case_dir = CASES / case_name
                manifest = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
                manifests[case_name] = manifest
                page = browser.new_page(viewport={"width": 1440, "height": 1100})
                page.set_default_timeout(45000)
                make_claimant(page, manifest["claim_number"], manifest["patient_name"])
                upload_files(page, case_dir)
                body = assess(page)
                screenshot = screenshots / f"{case_name}-claimant-result.png"
                page.screenshot(path=str(screenshot), full_page=True)
                status_match = (
                    (case_name == "a_match" and ("No discrepancy was identified" in body or "no discrepancy" in body.casefold()))
                    or (case_name == "b_wrongful_deduction" and "possible settlement discrepancy" in body)
                    or (case_name == "c_manual_review" and "Manual review is needed" in body)
                )
                shown = "Pending review" not in body or "because" in body.casefold() or "reason" in body.casefold()
                outcomes.append({"case": case_name, "expected": manifest["expected"]["expected_status"], "actual": body,
                                 "passed": status_match and shown, "result_shown": shown,
                                 "time_to_first_result_seconds": assess.time_to_first_result_seconds,
                                 "screenshot": str(screenshot), "claimant_email": f"{manifest['claim_number'].lower()}@fictional.test"})
                pages[case_name] = page

            # Reviewer confirms the policy created by the claimant's upload;
            # the claimant then refreshes the existing claim and checks that
            # only the badge changes, not its displayed amounts.
            before = pages["a_match"].locator("body").inner_text()
            admin = browser.new_page(viewport={"width": 1440, "height": 1100})
            admin.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")
            admin.get_by_text("Admin — secure sign in", exact=False).click()
            admin.get_by_role("button", name="Continue as admin").click()
            admin.get_by_role("tab", name="Secure sign in").click()
            admin.locator('input[aria-label="Email"]:visible').fill(email_admin)
            admin.locator('input[type="password"]:visible').fill(password_admin)
            admin.get_by_role("button", name="Sign in").click()
            admin.get_by_text("Policy management", exact=False).click()
            admin.get_by_text(re.compile("POL-FICT-001.*policy.pdf")).click()
            for label, value in (("Annual limit (INR)", "500000"), ("Deductible (INR)", "10000"),
                                 ("Co-payment (%)", "10"), ("Room limit per day (INR, optional)", "5000")):
                field = admin.get_by_label(label)
                if field.input_value() == "":
                    field.fill(value)
            for label in ("Annual limit source page", "Deductible source page", "Co-payment source page", "Room limit source page"):
                field = admin.get_by_label(label)
                if field.input_value() in {"0", ""}:
                    field.fill("1")
            admin.get_by_role("button", name="Confirm all terms").click()
            try:
                admin.get_by_text("Status: confirmed", exact=False).wait_for(timeout=5000)
            except Exception:
                admin.get_by_text(re.compile("POL-FICT-001.*policy.pdf")).click()
                admin.get_by_text("Status: confirmed", exact=False).wait_for(timeout=30000)
            reviewer_shot = screenshots / "reviewer-policy-confirmed.png"
            admin.screenshot(path=str(reviewer_shot), full_page=True)
            claimant = pages["a_match"]
            claimant.reload(wait_until="networkidle")
            claimant.get_by_text("User — sign in or create account", exact=False).click()
            claimant.get_by_role("button", name="Continue as user").click()
            claimant.get_by_role("tab", name="Sign in").click()
            claimant.locator('input[aria-label="Email"]:visible').fill("clm-fict-0417@fictional.test")
            claimant.locator('input[type="password"]:visible').fill("<your-demo-password>")
            claimant.get_by_role("button", name="Sign in").click()
            claimant.get_by_role("button", name="Open").click()
            # The badge is repeated in the claim header and comparison panel.
            # Wait for the first visible badge instead of relying on a strict
            # locator that fails when the same status appears twice.
            claimant.get_by_text("Reviewer-confirmed policy terms", exact=False).first.wait_for(timeout=30000)
            after = claimant.locator("body").inner_text()
            refresh_shot = screenshots / "claimant-after-review.png"
            claimant.screenshot(path=str(refresh_shot), full_page=True)
            before_amounts = re.findall(r"INR\s+[\d,]+\.\d{2}", before)
            after_amounts = re.findall(r"INR\s+[\d,]+\.\d{2}", after)
            reviewer_refresh = {
                "passed": "Reviewer-confirmed policy terms" in after and before_amounts == after_amounts,
                "badge_before": "Provisional: terms not yet confirmed" in before,
                "badge_after": "Reviewer-confirmed policy terms" in after,
                "amounts_before": before_amounts,
                "amounts_after": after_amounts,
                "screenshots": [str(reviewer_shot), str(refresh_shot)],
            }
            admin.close()
            for page in pages.values():
                page.close()

            # Each rejected/invalid file case gets a newly registered user and
            # a distinct claim, with no state shared from the demo cases.
            error_dir = screenshots / "upload-fixtures"
            error_dir.mkdir()
            (error_dir / "empty.pdf").write_bytes(b"")
            (error_dir / "wrong_type.pdf").write_bytes(b"not a PDF")
            (error_dir / "oversized.pdf").write_bytes(b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 1))
            (error_dir / "corrupted.pdf").write_bytes(b"%PDF-1.4\nfictional but corrupted")
            (error_dir / "settlement.txt").write_text(
                "FICTIONAL SAMPLE\nClaim Number: CLM-UPLOAD-ERR-3\nBill Total: INR 47000\nAmount Paid: INR 22500\n",
                encoding="utf-8",
            )
            error_cases = (("empty_file", "empty.pdf"), ("wrong_type", "wrong_type.pdf"),
                           ("oversized", "oversized.pdf"), ("corrupted_pdf", "corrupted.pdf"))
            for index, (case_name, filename) in enumerate(error_cases):
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                page.set_default_timeout(30000)
                claim_no = f"CLM-UPLOAD-ERR-{index}"
                make_claimant(page, claim_no, f"Fictional Error {index}")
                if case_name == "corrupted_pdf":
                    for label, path in (
                        ("Insurance policy", CASES / "a_match" / "policy.pdf"),
                        ("Insurer settlement letter", error_dir / "settlement.txt"),
                    ):
                        page.get_by_label(label).locator("input[type=file]").set_input_files(str(path))
                        page.get_by_text(path.name, exact=True).wait_for(timeout=15000)
                uploader = page.get_by_label("Medical bill and supporting documents").locator("input[type=file]")
                uploader.set_input_files(str(error_dir / filename))
                page.get_by_text(filename, exact=True).wait_for(timeout=15000)
                page.wait_for_timeout(750)
                page.get_by_role("button", name="Save documents").click()
                if case_name != "corrupted_pdf":
                    page.get_by_text("One or more files could not be saved", exact=False).wait_for(timeout=15000)
                else:
                    page.get_by_text("document(s) ready for assessment", exact=False).wait_for(timeout=15000)
                body = page.locator("body").inner_text()
                if case_name == "corrupted_pdf" and "document(s) ready for assessment" in body:
                    # It passes upload validation but must fail safely during extraction.
                    body = assess(page)
                safe = "Traceback" not in body and "FileNotFoundError" not in body and "C:\\" not in body
                if case_name == "corrupted_pdf":
                    passed = safe and "Your claim result" in body and any(
                        marker in body.casefold() for marker in ("manual review", "unreadable", "extraction", "missing", "not identified")
                    )
                else:
                    passed = safe and "could not be saved" in body.casefold()
                screenshot = screenshots / f"{case_name}.png"
                page.screenshot(path=str(screenshot), full_page=True)
                outcomes.append({"case": case_name, "passed": passed, "result_shown": passed,
                                 "actual": body[-1200:], "screenshot": str(screenshot)})
                page.close()

            # No-settlement claimant path: calculate the bill/policy result and
            # state plainly that settlement comparison cannot be made yet.
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.set_default_timeout(45000)
            no_settle = manifests["a_match"]
            make_claimant(page, "CLM-UPLOAD-NOSETTLE", "Fictional Missing Settlement")
            upload_files(page, CASES / "a_match", include_settlement=False)
            body = assess(page, has_settlement=False)
            screenshot = screenshots / "missing_settlement.png"
            page.screenshot(path=str(screenshot), full_page=True)
            passed = "settlement" in body.casefold() and "No discrepancy was identified" not in body
            outcomes.append({"case": "missing_settlement", "passed": passed, "result_shown": passed,
                             "actual": body[-1400:], "screenshot": str(screenshot)})
            page.close()
            browser.close()
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        log_handle.close()
        scratch.cleanup()

    passed_count = sum(bool(item.get("passed")) for item in outcomes[:8])
    demo_times = [item["time_to_first_result_seconds"] for item in outcomes if item.get("case") in {"a_match", "b_wrongful_deduction", "c_manual_review"} and item.get("time_to_first_result_seconds") is not None]
    result = {"numerator": passed_count, "denominator": 8, "score": passed_count / 8,
              "pass": passed_count == 8 and reviewer_refresh.get("passed", False),
              "time_to_first_result_seconds": demo_times,
              "max_time_to_first_result_seconds": max(demo_times) if demo_times else None,
              "cases": outcomes, "reviewer_refresh": reviewer_refresh,
              "screenshots_directory": str(screenshots), "failure": failure}
    if failure:
        result["server_log_tail"] = log_path.read_text(encoding="utf-8", errors="replace")[-5000:]
    # Preserve a compact, reproducible record without copying page text or
    # screenshots into the repository.
    from datetime import datetime, timezone
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "numerator": passed_count,
        "denominator": 8,
        "pass": result["pass"],
        "time_to_first_result_seconds": demo_times,
        "max_time_to_first_result_seconds": result["max_time_to_first_result_seconds"],
        "reviewer_refresh": reviewer_refresh,
        "cases": [{key: case.get(key) for key in ("case", "expected", "passed", "result_shown", "screenshot") if key in case}
                  for case in outcomes],
        "screenshots_directory": str(screenshots),
        "failure": failure,
    }
    latest = ROOT / "evaluation" / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "claimant_browser_results.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return result
