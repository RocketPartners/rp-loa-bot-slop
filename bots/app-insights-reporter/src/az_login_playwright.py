#!/usr/bin/env python3
"""
Automate Azure CLI device-code login via Playwright (headless Chromium).
Handles Microsoft -> Okta federation with TOTP verification.

One-time initialization — run interactively or pass OKTA_TOTP_CODE env var.

Usage:
  python3 az_login_playwright.py
  OKTA_TOTP_CODE=123456 python3 az_login_playwright.py
"""
import os
import sys
import re
import subprocess
import threading
import time

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("playwright not installed. Run: pip install playwright && playwright install chromium", file=sys.stderr)
    sys.exit(1)

AZURE_EMAIL = os.environ.get("AZURE_EMAIL", "")
AZURE_PASSWORD = os.environ.get("AZURE_PASSWORD", "")
OKTA_TOTP_CODE = os.environ.get("OKTA_TOTP_CODE", "")

DEVICE_LOGIN_URL = "https://microsoft.com/devicelogin"


def start_az_login():
    """Start 'az login --use-device-code' and capture the device code."""
    proc = subprocess.Popen(
        ["az", "login", "--use-device-code"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    output_lines = []
    device_code = None
    code_pattern = re.compile(r"enter the code\s+([A-Z0-9]{9})", re.IGNORECASE)

    # Read output until we find the device code
    deadline = time.time() + 30
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()
        output_lines.append(line)
        print(f"  az: {line}", file=sys.stderr)

        match = code_pattern.search(line)
        if match:
            device_code = match.group(1)
            break

    return proc, device_code, output_lines


def automate_login(device_code):
    """Use Playwright to complete the device code flow through Microsoft + Okta."""
    print(f"Device code: {device_code}", file=sys.stderr)
    print("Starting Playwright browser...", file=sys.stderr)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()

        try:
            # Step 1: Navigate to device login page
            print("Navigating to device login page...", file=sys.stderr)
            page.goto(DEVICE_LOGIN_URL, wait_until="networkidle", timeout=30000)

            # Step 2: Enter device code
            print("Entering device code...", file=sys.stderr)
            code_input = page.locator('input[name="otc"]')
            code_input.wait_for(state="visible", timeout=15000)
            code_input.fill(device_code)

            # Click Next/Continue
            page.locator('input[type="submit"], button[type="submit"]').first.click()
            page.wait_for_load_state("networkidle", timeout=15000)

            # Step 3: Microsoft email page (may appear)
            # Sometimes it shows "Is this the account you want to sign in to?" confirmation
            try:
                confirm_btn = page.locator('input[value="Continue"], button:has-text("Continue")')
                if confirm_btn.is_visible(timeout=3000):
                    print("Confirming account...", file=sys.stderr)
                    confirm_btn.click()
                    page.wait_for_load_state("networkidle", timeout=15000)
            except PWTimeout:
                pass

            # Check if we need to enter email on Microsoft login page
            try:
                email_input = page.locator('input[type="email"], input[name="loginfmt"]')
                if email_input.is_visible(timeout=5000):
                    print("Entering email...", file=sys.stderr)
                    email_input.fill(AZURE_EMAIL)
                    page.locator('input[type="submit"], button[type="submit"]').first.click()
                    page.wait_for_load_state("networkidle", timeout=15000)
            except PWTimeout:
                pass

            # Step 4: Okta login page (federated redirect)
            # Wait for Okta page to load — look for username/password fields
            print("Waiting for Okta login page...", file=sys.stderr)
            time.sleep(2)  # Allow redirect to settle

            # Okta username field
            try:
                okta_username = page.locator('input[name="username"], input[name="identifier"], input#okta-signin-username')
                if okta_username.is_visible(timeout=10000):
                    print("Entering Okta username...", file=sys.stderr)
                    okta_username.fill(AZURE_EMAIL)

                    # Some Okta configs have username-first then password on next page
                    next_btn = page.locator('input[type="submit"], button[type="submit"], input#okta-signin-submit')
                    next_btn.first.click()
                    page.wait_for_load_state("networkidle", timeout=10000)
                    time.sleep(1)
            except PWTimeout:
                pass

            # Okta password field
            try:
                okta_password = page.locator('input[name="password"], input[name="credentials.passcode"], input[type="password"]')
                if okta_password.is_visible(timeout=10000):
                    print("Entering Okta password...", file=sys.stderr)
                    okta_password.fill(AZURE_PASSWORD)

                    submit_btn = page.locator('input[type="submit"], button[type="submit"], input#okta-signin-submit')
                    submit_btn.first.click()
                    page.wait_for_load_state("networkidle", timeout=15000)
                    time.sleep(2)
            except PWTimeout:
                print("Password field not found", file=sys.stderr)

            # Step 5: Okta Verify TOTP code
            if OKTA_TOTP_CODE:
                print("Entering TOTP code...", file=sys.stderr)
                time.sleep(2)  # Wait for MFA page

                # Look for TOTP/verification code input
                totp_input = None
                totp_selectors = [
                    'input[name="credentials.passcode"]',
                    'input[name="answer"]',
                    'input[name="verificationCode"]',
                    'input[name="passcode"]',
                    'input[data-se="input-credentials.passcode"]',
                    'input[type="tel"]',
                    'input[autocomplete="one-time-code"]',
                ]

                for selector in totp_selectors:
                    try:
                        el = page.locator(selector)
                        if el.is_visible(timeout=2000):
                            totp_input = el
                            print(f"  Found TOTP input: {selector}", file=sys.stderr)
                            break
                    except PWTimeout:
                        continue

                if totp_input:
                    totp_input.fill(OKTA_TOTP_CODE)
                    verify_btn = page.locator('input[type="submit"], button[type="submit"], button:has-text("Verify"), button:has-text("Sign in")')
                    verify_btn.first.click()
                    page.wait_for_load_state("networkidle", timeout=20000)
                    time.sleep(2)
                else:
                    print("TOTP input field not found — check page state", file=sys.stderr)
                    # Take a screenshot for debugging
                    page.screenshot(path="/tmp/az_login_debug.png")
                    print("Screenshot saved to /tmp/az_login_debug.png", file=sys.stderr)
            else:
                print("No OKTA_TOTP_CODE provided — waiting for manual approval or push notification...", file=sys.stderr)
                # Wait up to 60s for push approval
                time.sleep(60)

            # Step 6: Post-login — Microsoft may ask to stay signed in
            try:
                stay_signed_in = page.locator('input[value="Yes"], button:has-text("Yes")')
                if stay_signed_in.is_visible(timeout=5000):
                    print("Accepting 'Stay signed in'...", file=sys.stderr)
                    stay_signed_in.click()
                    page.wait_for_load_state("networkidle", timeout=10000)
            except PWTimeout:
                pass

            # Check for success
            time.sleep(2)
            page_text = page.text_content("body") or ""
            if "you have signed in" in page_text.lower() or "you can close" in page_text.lower():
                print("Browser auth completed successfully", file=sys.stderr)
            else:
                print(f"Page state unclear — may still be completing...", file=sys.stderr)
                page.screenshot(path="/tmp/az_login_final.png")
                print("Screenshot saved to /tmp/az_login_final.png", file=sys.stderr)

        except Exception as e:
            print(f"Playwright error: {e}", file=sys.stderr)
            try:
                page.screenshot(path="/tmp/az_login_error.png")
                print("Error screenshot saved to /tmp/az_login_error.png", file=sys.stderr)
            except:
                pass
            return False
        finally:
            browser.close()

    return True


def main():
    if not AZURE_EMAIL or not AZURE_PASSWORD:
        print("AZURE_EMAIL and AZURE_PASSWORD env vars required", file=sys.stderr)
        return 1

    # Check if already logged in
    result = subprocess.run(["az", "account", "show"], capture_output=True, text=True)
    if result.returncode == 0:
        print("Already logged in to Azure CLI", file=sys.stderr)
        return 0

    print("Starting Azure CLI device-code login...", file=sys.stderr)

    # Start az login in background
    proc, device_code, _ = start_az_login()

    if not device_code:
        print("Failed to get device code from az login", file=sys.stderr)
        proc.terminate()
        return 1

    # Automate the browser flow
    success = automate_login(device_code)

    # Wait for az login to complete
    print("Waiting for az login to finish...", file=sys.stderr)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        print("az login timed out", file=sys.stderr)
        proc.terminate()
        return 1

    if proc.returncode == 0:
        print("Azure CLI login successful!", file=sys.stderr)
        return 0
    else:
        remaining = proc.stdout.read()
        print(f"az login exited with code {proc.returncode}", file=sys.stderr)
        if remaining:
            print(remaining, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
