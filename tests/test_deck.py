import json
import sqlite3
import zipfile
from html import unescape

from hanzi_anki.deck import build_deck, make_model, note_guid, render_templates


def read_package(path, tmp_path):
    folder = tmp_path / "unzipped"
    with zipfile.ZipFile(path) as z:
        z.extractall(folder)
    db = sqlite3.connect(folder / "collection.anki2")
    notes = db.execute("select guid, flds from notes order by id").fetchall()
    media = json.loads((folder / "media").read_text())
    return notes, media


def test_guid_is_stable_and_depends_on_hanzi_only():
    assert note_guid("你好") == note_guid("你好")
    assert note_guid("你好") != note_guid("你好吗")


def test_model_id_comes_from_config(project):
    _, config = project
    assert make_model(config).model_id == config.model_id


def test_rebuild_gives_same_guids(project, tmp_path):
    _, config = project
    build_deck(config)
    first, _ = read_package(config.output, tmp_path / "a")
    build_deck(config)
    second, _ = read_package(config.output, tmp_path / "b")
    assert [g for g, _ in first] == [g for g, _ in second]


def test_build_with_missing_character_and_missing_audio(project, tmp_path):
    root, config = project
    with open(config.words, "a", encoding="utf-8") as f:
        f.write("龘 | dá | many dragons | no-such.mp3\n")
    result = build_deck(config)

    assert result.entries_built == 3
    assert result.characters_missing == ["龘"]
    assert result.missing_audio == [("龘", "no-such.mp3")]
    assert "你" in result.characters_found

    notes, media = read_package(config.output, tmp_path)
    assert sorted(media.values()) == ["_hanzi-writer.min.js", "hanzi_ni-hao.mp3"]
    assert [unescape(n[1].split("\x1f")[0]) for n in notes] == ["你好", "我不懂这个字。", "龘"]

    audio_field = notes[0][1].split("\x1f")[3]
    assert audio_field == "[sound:hanzi_ni-hao.mp3]"
    sentence_json = json.loads(unescape(notes[1][1].split("\x1f")[4]))
    assert sentence_json["chars"] == list("我不懂这个字")  # punctuation skipped


def test_templates_have_no_leftover_placeholders_and_use_config_colors(project):
    _, config = project
    front, back, css = render_templates(config)
    assert "%%" not in back + css
    assert config.colors["radical"] in css
    assert config.colors["stroke_night"] in css
    assert '"speed": 1.5' in back
    assert "{{Strokes}}" in back and "{{Hanzi}}" in front


def test_night_mode_css_covers_anki_and_ankidroid_classes(project):
    _, config = project
    _, _, css = render_templates(config)
    night_block = css[css.index(".nightMode,"):]
    for selector in (".nightMode", ".night_mode", ".card.nightMode", ".nightMode .card"):
        assert selector in night_block
    assert config.colors["outline_night"] in night_block
