import json

from conftest import fake_char
from hanzi_anki.strokes import build_strokes_json


def test_missing_character_is_reported_not_crashing():
    text, missing = build_strokes_json(["你", "龘"], {"你": fake_char()})
    payload = json.loads(text)
    assert missing == ["龘"]
    assert payload["chars"] == ["你", "龘"]  # still shown on the card, as plain text
    assert "龘" not in payload["data"]


def test_repeated_character_stored_once_but_drawn_twice():
    text, missing = build_strokes_json(["谢", "谢"], {"谢": fake_char()})
    payload = json.loads(text)
    assert payload["chars"] == ["谢", "谢"]
    assert list(payload["data"]) == ["谢"]
    assert missing == []


def test_radical_strokes_are_kept():
    text, _ = build_strokes_json(["你"], {"你": fake_char(radical_strokes=(0, 1))})
    assert json.loads(text)["data"]["你"]["radStrokes"] == [0, 1]
