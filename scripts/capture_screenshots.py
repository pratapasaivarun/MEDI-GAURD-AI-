"""Capture real fictional-data app screenshots from an isolated run_demo copy.

Usage: python scripts/capture_screenshots.py
Requires the project dependencies and Playwright Chromium. Screenshots are written
to docs/images/ and contain only the bundled fictional demo cases.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import socket
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "images"
CASES = ROOT / "samples" / "demo_cases"
PASSWORD = "LocalScreenshotOnly-" + os.urandom(12).hex()


def _copy_demo_checkout(destination: Path) -> None:
    ignored = shutil.ignore_patterns(
        ".git", ".env", ".venv", "__pycache__", ".pytest_cache", ".pytest-temp*",
        "data", "tmp", "chroma", "hf-cache", "*.pyc",
    )
    shutil.copytree(ROOT, destination, ignore=ignored, dirs_exist_ok=True)
    shutil.copy2(ROOT / ".env.example", destination / ".env")


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _save(page, name: str, *, full_page: bool = False) -> None:
    page.add_style_tag(content='[data-testid="stToolbar"] { visibility: hidden !important; }')
    path = OUTPUT / name
    page.screenshot(path=str(path), full_page=full_page, animations="disabled")
    try:
        from PIL import Image

        with Image.open(path) as image:
            image.convert("RGB").quantize(colors=192).save(path, optimize=True)
    except ImportError:
        pass
    if path.stat().st_size > 400_000:
        raise RuntimeError(f"Screenshot is larger than 400 KB: {path.name}")


def _open_user_workspace(page, port: int) -> None:
    page.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")
    page.get_by_text("User — sign in or create account", exact=False).click()
    page.get_by_role("button", name="Continue as user").evaluate("element => element.click()")
    page.get_by_role("tab", name="Sign in").wait_for()


def _register_claim(page, case: dict[str, str]) -> None:
    page.get_by_role("tab", name="Create account").click()
    page.locator('input[aria-label="Full name"]:visible').fill(case["patient_name"])
    page.locator('input[aria-label="Email"]:visible').last.fill(
        case["claim_number"].lower() + "@fictional.test"
    )
    passwords = page.locator('input[type="password"]:visible')
    passwords.first.fill(PASSWORD)
    passwords.nth(1).fill(PASSWORD)
    page.get_by_role("button", name="Create account").click()
    page.get_by_text("Register claim", exact=False).click()
    page.get_by_role("textbox", name="Claim number").fill(case["claim_number"])
    page.get_by_role("textbox", name="Patient name").fill(case["patient_name"])
    page.get_by_role("textbox", name="Policy number").fill(case["policy_number"])
    page.get_by_role("textbox", name="Hospital / provider").fill(case["hospital_name"])
    page.get_by_role("button", name="Save claim and continue").click()
    page.get_by_text("Add your documents", exact=False).first.wait_for(timeout=20000)


def _upload_case(page, case_dir: Path) -> None:
    for label, filename in (
        ("Insurance policy", "policy.pdf"),
        ("Medical bill and supporting documents", "bill.pdf"),
        ("Insurer settlement letter", "settlement.pdf"),
    ):
        page.get_by_label(label).locator('input[type="file"]').set_input_files(
            str(case_dir / filename)
        )
        page.wait_for_timeout(250)
    page.get_by_role("button", name="Save documents").click()
    page.get_by_text("3 document(s) ready for assessment", exact=False).wait_for(timeout=20000)


def _assess(page) -> None:
    page.get_by_role("button", name="Submit claim for assessment").click()
    page.get_by_text("Your claim result", exact=True).wait_for(timeout=60000)
    page.get_by_text("Settlement comparison", exact=True).wait_for(timeout=60000)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    with tempfile.TemporaryDirectory(prefix="mediguard-screenshot-demo-") as temp:
        checkout = Path(temp) / "repo"
        _copy_demo_checkout(checkout)
        env = os.environ.copy()
        env["MEDIGUARD_ADMIN_PASSWORD"] = PASSWORD
        env["MEDIGUARD_DEMO_PORT"] = str(port)
        env["OLLAMA_HOST"] = "http://127.0.0.1:1"
        log_path = Path(temp) / "streamlit.log"
        with log_path.open("w", encoding="utf-8") as log:
            server = subprocess.Popen(
                [sys.executable, str(checkout / "run_demo.py")],
                cwd=checkout,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            try:
                import requests

                for _ in range(90):
                    if server.poll() is not None:
                        raise RuntimeError(f"Demo exited early; see {log_path}")
                    try:
                        if requests.get(f"http://127.0.0.1:{port}/_stcore/health", timeout=1).ok:
                            break
                    except requests.RequestException:
                        pass
                    time.sleep(1)
                else:
                    raise TimeoutError(f"Demo did not become healthy; see {log_path}")

                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    context = browser.new_context(
                        viewport={"width": 1440, "height": 900},
                        device_scale_factor=1,
                        color_scheme="light",
                    )
                    page = context.new_page()
                    page.set_default_timeout(45000)
                    _open_user_workspace(page, port)
                    _save(page, "01-login.png")

                    cases = {}
                    for case_name in (
                        "b_wrongful_deduction", "a_match", "c_manual_review"
                    ):
                        import json

                        case_dir = CASES / case_name
                        case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
                        cases[case_name] = case
                        if case_name == "b_wrongful_deduction":
                            _register_claim(page, case)
                            _save(page, "02-upload.png")
                            _upload_case(page, case_dir)
                            _assess(page)
                            _save(page, "03-result-wrongful-deduction.png")
                            appeal = page.get_by_role("button", name="Appeal letter (PDF)")
                            appeal.scroll_into_view_if_needed()
                            _save(page, "04-appeal-download.png")
                        else:
                            new_page = context.new_page()
                            new_page.set_default_timeout(45000)
                            _open_user_workspace(new_page, port)
                            _register_claim(new_page, case)
                            _upload_case(new_page, case_dir)
                            _assess(new_page)
                            _save(
                                new_page,
                                "05-result-match.png" if case_name == "a_match"
                                else "06-manual-review.png",
                            )
                            new_page.close()

                    # Reviewer confirmation screen for the policy edition uploaded
                    # with the fictional claimant case. The stored demo admin uses
                    # the ephemeral password above; the screenshot contains no credentials.
                    reviewer = context.new_page()
                    reviewer.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")
                    reviewer.get_by_text("Admin — secure sign in", exact=False).click()
                    reviewer.get_by_role("button", name="Continue as admin").click()
                    reviewer.get_by_role("tab", name="Secure sign in").click()
                    reviewer.locator('input[aria-label="Email"]:visible').fill("demo@mediguard.local")
                    reviewer.locator('input[type="password"]:visible').fill(PASSWORD)
                    reviewer.get_by_role("button", name="Sign in").click()
                    reviewer.get_by_text("Policy management", exact=False).click()
                    reviewer.get_by_text("POL-FICT-001", exact=False).first.click()
                    reviewer.get_by_role("button", name="Confirm all terms").scroll_into_view_if_needed()
                    main_view = reviewer.locator('[data-testid="stMain"]')
                    main_view.evaluate("element => element.scrollTo(0, element.scrollHeight)")
                    reviewer.wait_for_timeout(400)
                    _save(reviewer, "07-reviewer-confirmation.png", full_page=True)
                    browser.close()
            finally:
                # run_demo.py starts Streamlit as a child process; terminate the
                # full Windows process tree so the temporary checkout is released.
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(server.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                else:
                    server.terminate()
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=5)
                server.wait(timeout=10)
    print(f"Captured seven screenshots to {OUTPUT}")
    for path in sorted(OUTPUT.glob("*.png")):
        print(f"{path.name}: {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
