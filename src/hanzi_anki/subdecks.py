"""Subdeck names and numbers.

Anki sorts subdecks by name, so every subdeck gets a number in front of its name
("03 Greetings"). The numbers are remembered in a small JSON file, so a name keeps
the same number every time you build it again.
"""

import json
from dataclasses import dataclass
from pathlib import Path


class SubdeckError(Exception):
    """Raised when a subdeck name is not valid or the numbers file is broken."""


@dataclass
class Subdeck:
    name: str  # the name as it was typed the first time
    number: int
    is_new: bool  # True if this name had no number yet

    @property
    def key(self) -> str:
        """Same name in any letter case is the same subdeck."""
        return self.name.casefold()

    @property
    def label(self) -> str:
        """The name with its number, for example '03 Greetings'."""
        return f"{self.number:02d} {self.name}"


def clean_name(name: str) -> str:
    name = " ".join(name.split())  # trim and collapse spaces
    if not name:
        raise SubdeckError("The subdeck name is empty.")
    if "::" in name:
        raise SubdeckError("The subdeck name must not contain '::' (Anki uses it for levels).")
    return name


def deck_title(parent: str, subdeck: Subdeck) -> str:
    """Full deck name for Anki, for example 'Chinese Words::03 Greetings'."""
    return f"{parent}::{subdeck.label}" if parent else subdeck.label


def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data["subdecks"]
    except (ValueError, KeyError, TypeError) as error:
        raise SubdeckError(f"Cannot read {path}. Fix the file or delete it.") from error


def choose_subdeck(path: Path, name: str, first_number: int) -> Subdeck:
    """Find the number of a subdeck, or give the next free number to a new name.
    Nothing is saved here. Call save_subdeck() after the build worked."""
    name = clean_name(name)
    known = _load(path)

    entry = known.get(name.casefold())
    if entry:
        return Subdeck(name=entry["name"], number=entry["number"], is_new=False)

    numbers = [item["number"] for item in known.values()]
    number = max(numbers) + 1 if numbers else first_number
    return Subdeck(name=name, number=number, is_new=True)


def save_subdeck(path: Path, subdeck: Subdeck) -> None:
    known = _load(path)
    known[subdeck.key] = {"name": subdeck.name, "number": subdeck.number}
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"subdecks": known}, ensure_ascii=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")
