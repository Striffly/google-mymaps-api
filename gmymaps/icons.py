"""My Maps icon catalog (ids and French labels, scraped from the editor's icon dialog)."""

import json
import unicodedata
from pathlib import Path

ICONS = json.loads((Path(__file__).parent / "icons.json").read_text(encoding="utf-8"))


def normalize(text):
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def find_icons(query):
    """Icons whose label contains query, ignoring case and accents."""
    wanted = normalize(query)
    return [icon for icon in ICONS if wanted in normalize(icon["label"])]


def icon_id(label):
    """Id of the icon whose label is exactly label (case and accents ignored)."""
    wanted = normalize(label)
    for icon in ICONS:
        if normalize(icon["label"]) == wanted:
            return icon["id"]
    raise KeyError(f"No icon labelled {label!r}")
