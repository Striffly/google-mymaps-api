"""The Google session cookies gmymaps sends, stored in a Netscape cookie file."""

import os
from http.cookiejar import MozillaCookieJar
from pathlib import Path


def cookie_file_path():
    """$GMYMAPS_COOKIES, or cookies.txt in the user's config directory."""
    if os.environ.get("GMYMAPS_COOKIES"):
        return Path(os.environ["GMYMAPS_COOKIES"])
    config_dir = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return config_dir / "gmymaps" / "cookies.txt"


def get_cookies(path=None):
    path = Path(path or cookie_file_path())
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: run `python -m gmymaps.login` first")
    jar = MozillaCookieJar(path)
    # Google's login cookies include session cookies, which load() drops by default.
    jar.load(ignore_discard=True)
    return jar


def save_cookies(cookies, path=None):
    """Write CDP cookies (dicts from Storage.getCookies) as a private Netscape cookie file."""
    path = Path(path or cookie_file_path())
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# Netscape HTTP Cookie File"]
    for cookie in cookies:
        domain = cookie["domain"]
        include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
        secure = "TRUE" if cookie["secure"] else "FALSE"
        # An empty expiry marks a session cookie for MozillaCookieJar.
        expires = str(int(cookie["expires"])) if cookie.get("expires", -1) > 0 else ""
        fields = [domain, include_subdomains, cookie["path"], secure, expires, cookie["name"], cookie["value"]]
        lines.append("\t".join(fields))

    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path
