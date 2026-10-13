import json
import shutil
from pathlib import Path

import pytest

from hanzi_anki.config import load_config

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def fake_char(radical_strokes=(0,)):
    """Tiny made-up character data in the Hanzi Writer format."""
    return {
        "strokes": ["M 100 100 L 900 100 L 900 200 L 100 200 Z", "M 100 300 L 900 300 L 900 400 L 100 400 Z"],
        "medians": [[[100, 150], [900, 150]], [[100, 350], [900, 350]]],
        "radStrokes": list(radical_strokes),
    }


@pytest.fixture
def project(tmp_path):
    """A temporary project folder with a fake all.json, a few words and audio."""
    (tmp_path / "data").mkdir()
    (tmp_path / "input" / "audio").mkdir(parents=True)
    (tmp_path / "assets").mkdir()

    all_json = {ch: fake_char() for ch in "你好吗我不懂这个字"}
    (tmp_path / "data" / "all.json").write_text(json.dumps(all_json, ensure_ascii=False), encoding="utf-8")

    (tmp_path / "input" / "audio" / "ni-hao.mp3").write_bytes(b"fake mp3")
    (tmp_path / "input" / "words.txt").write_text(
        "你好 | nǐ hǎo | hello | ni-hao.mp3\n"
        "我不懂这个字。 | wǒ bù dǒng zhè ge zì. | I don't understand this character. |\n",
        encoding="utf-8",
    )

    shutil.copy(PROJECT_ROOT / "config.toml", tmp_path / "config.toml")
    shutil.copytree(PROJECT_ROOT / "templates", tmp_path / "templates")
    (tmp_path / "assets" / "hanzi-writer.min.js").write_text("/* fake library */", encoding="utf-8")

    return tmp_path, load_config(tmp_path / "config.toml")
