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
        raise FileNotFoundError(f"{path} not found: export your Google cookies there first")
    jar = MozillaCookieJar(path)
    # Google's login cookies include session cookies, which load() drops by default.
    jar.load(ignore_discard=True)
    return jar
