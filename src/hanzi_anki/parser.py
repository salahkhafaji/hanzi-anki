"""Read words.txt and split entries into characters."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Entry:
    hanzi: str
    pinyin: str
    meaning: str
    audio: str  # file name from the 4th field, or "" if empty
    line_number: int


def is_chinese_character(ch: str) -> bool:
    """True for Chinese characters (CJK ideographs). Punctuation, spaces,
    digits and Latin letters are not Chinese characters."""
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF  # main block
        or 0x3400 <= code <= 0x4DBF  # extension A
        or 0x20000 <= code <= 0x2A6DF  # extension B
        or 0xF900 <= code <= 0xFAFF  # compatibility ideographs
        or ch == "\u3007"  # 〇
    )


def split_characters(text: str) -> list[str]:
    """Return the Chinese characters of text in order. Repeats are kept."""
    return [ch for ch in text if is_chinese_character(ch)]


def parse_line(line: str, line_number: int) -> Entry:
    """Parse 'hanzi | pinyin | meaning | audio'. The audio field is optional.
    Raises ValueError if the line is not valid."""
    parts = [part.strip() for part in line.split("|")]
    if len(parts) < 3 or len(parts) > 4:
        raise ValueError("expected 'hanzi | pinyin | meaning | audio_file'")
    if len(parts) == 3:
        parts.append("")
    hanzi, pinyin, meaning, audio = parts
    if not hanzi:
        raise ValueError("the hanzi field is empty")
    return Entry(hanzi, pinyin, meaning, audio, line_number)


def parse_words(path: Path) -> tuple[list[Entry], list[str]]:
    """Read the words file. Returns (entries, warnings).
    Bad lines are skipped with a warning. If the same hanzi appears twice,
    the later line replaces the earlier one (same card, same GUID)."""
    entries: dict[str, Entry] = {}  # a dict keeps the order of first appearance
    warnings: list[str] = []

    # utf-8-sig also reads files that Windows Notepad saved with a BOM
    with open(path, encoding="utf-8-sig") as f:
        for line_number, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                entry = parse_line(line, line_number)
            except ValueError as error:
                warnings.append(f"words line {line_number}: skipped, {error}")
                continue
            if entry.hanzi in entries:
                first = entries[entry.hanzi].line_number
                warnings.append(
                    f"words line {line_number}: '{entry.hanzi}' already on line {first}; "
                    "the later line replaces the earlier one"
                )
            entries[entry.hanzi] = entry

    return list(entries.values()), warnings
