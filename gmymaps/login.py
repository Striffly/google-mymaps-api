"""Sign in to Google in a dedicated Chromium profile and save the cookies gmymaps needs.

    python -m gmymaps.login                          temporary profile, deleted afterwards
    python -m gmymaps.login --profile DIR            keep the profile to refresh cookies later
    python -m gmymaps.login --profile DIR --refresh  re-export cookies headless, no window

Your everyday browser is never read: only the dedicated profile's google.com cookies are saved.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
import websocket

from .cookies import cookie_file_path, save_cookies

LOGIN_URL = "https://accounts.google.com/ServiceLogin?continue=https://www.google.com/maps/d/u/0/"
BROWSERS = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
COMMON_FLAGS = ("--no-first-run", "--no-default-browser-check")


def find_browser(explicit):
    for candidate in ([explicit] if explicit else BROWSERS):
        path = shutil.which(candidate)
        if path:
            return path
    sys.exit(f"No Chromium-based browser found (tried {', '.join(BROWSERS)}); pass --browser")


def sign_in(browser, profile):
    # No remote debugging here: Google refuses sign-ins from browsers controlled over CDP.
    print("A Chromium window opens: sign in to Google, wait for My Maps to load, then close the window.")
    subprocess.run([browser, f"--user-data-dir={profile}", *COMMON_FLAGS, LOGIN_URL], check=False)


def wait_for_devtools_port(profile, timeout=20):
    """Chromium writes its port to DevToolsActivePort when started with --remote-debugging-port=0."""
    port_file = Path(profile) / "DevToolsActivePort"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_file.exists() and port_file.read_text().strip():
            return int(port_file.read_text().splitlines()[0])
        time.sleep(0.2)
    sys.exit("Headless Chromium did not start (is the profile still open in another window?)")


def read_google_cookies(browser, profile):
    (Path(profile) / "DevToolsActivePort").unlink(missing_ok=True)
    process = subprocess.Popen(
        [browser, "--headless=new", f"--user-data-dir={profile}", "--remote-debugging-port=0", *COMMON_FLAGS],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        port = wait_for_devtools_port(profile)
        browser_ws = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=5).json()["webSocketDebuggerUrl"]
        connection = websocket.create_connection(browser_ws, timeout=10)
        connection.send(json.dumps({"id": 1, "method": "Storage.getCookies"}))
        cookies = json.loads(connection.recv())["result"]["cookies"]
        connection.close()
    finally:
        process.terminate()
        process.wait(timeout=10)

    return [cookie for cookie in cookies if is_google_cookie(cookie)]


def is_google_cookie(cookie):
    domain = cookie["domain"].lstrip(".")
    return domain == "google.com" or domain.endswith(".google.com")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", help="Chromium profile directory to keep (default: a temporary one)")
    parser.add_argument("--refresh", action="store_true", help="skip the sign-in window, export from --profile")
    parser.add_argument("--browser", help="Chromium-based browser executable")
    parser.add_argument("--output", help=f"cookie file (default: {cookie_file_path()})")
    args = parser.parse_args()

    if args.refresh and not args.profile:
        parser.error("--refresh needs the --profile used to sign in")

    browser = find_browser(args.browser)
    profile = args.profile or tempfile.mkdtemp(prefix="gmymaps-profile-")
    try:
        if not args.refresh:
            sign_in(browser, profile)
        cookies = read_google_cookies(browser, profile)
    finally:
        if not args.profile:
            shutil.rmtree(profile, ignore_errors=True)

    if not any(cookie["name"] == "SID" for cookie in cookies):
        sys.exit("No Google session found in the profile: sign-in did not complete")
    path = save_cookies(cookies, args.output)
    print(f"Saved {len(cookies)} Google cookies to {path}")


if __name__ == "__main__":
    main()
