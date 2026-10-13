"""Load Hanzi Writer character data and build the JSON stored in each card."""

import json
from pathlib import Path


class StrokeDataError(Exception):
    """Raised when all.json cannot be read."""


def load_all_json(path: Path) -> dict:
    """Load all.json (an object keyed by character)."""
    path = Path(path)
    if not path.is_file():
        raise StrokeDataError(
            f"Stroke data not found: {path}\n"
            "Download all.json first. See data/README.md."
        )
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as error:
        raise StrokeDataError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise StrokeDataError(f"{path} must be a JSON object keyed by character")
    return data


def build_strokes_json(chars: list[str], all_data: dict) -> tuple[str, list[str]]:
    """Build the JSON for the hidden Strokes field.

    Result: {"chars": ["你", "好", ...], "data": {"你": {...}, "好": {...}}}
    - "chars" keeps the order and repeats, so the card draws one animation per character.
    - "data" holds each character once, even if it repeats.
    Returns (json_text, missing_characters). Missing characters stay in "chars"
    (the card shows them as plain text) but have no entry in "data".
    """
    data: dict = {}
    missing: list[str] = []
    for ch in chars:
        if ch in data or ch in missing:
            continue
        info = all_data.get(ch)
        if info is None:
            missing.append(ch)
        else:
            data[ch] = {
                "strokes": info["strokes"],
                "medians": info["medians"],
                "radStrokes": info.get("radStrokes", []),
            }
    payload = {"chars": chars, "data": data}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")), missing
