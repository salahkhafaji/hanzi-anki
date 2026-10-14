import json

import pytest

from hanzi_anki.gui import (
    GuiError,
    audio_status,
    check_entry,
    copy_audio,
    entries_to_text,
    friendly_error,
    make_entry,
    merge_pasted,
    run_build,
    save_words,
    validate_entries,
)
from hanzi_anki.parser import parse_words
from hanzi_anki.subdecks import SubdeckError


def entry(hanzi="你好", pinyin="nǐ hǎo", meaning="hello", audio=""):
    return make_entry(hanzi, pinyin, meaning, audio)


# ----- checking entries -----


def test_good_entry_has_no_problems():
    assert check_entry(entry(audio="ni-hao.mp3")) == []


@pytest.mark.parametrize(
    "bad",
    [
        entry(hanzi=""),
        entry(meaning="a | b"),
        entry(audio="folder/ni-hao.mp3"),
        entry(audio="C:ni-hao.mp3"),
        entry(pinyin="a\nb"),
    ],
)
def test_bad_entries_are_found(bad):
    assert check_entry(bad)


def test_validate_empty_list_and_duplicates():
    assert "empty" in validate_entries([])[0]
    errors = validate_entries([entry("你好"), entry("谢谢"), entry("你好")])
    assert len(errors) == 1 and "row 1" in errors[0]


def test_audio_status(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    assert audio_status("", tmp_path) == ""
    assert audio_status("a.mp3", tmp_path) == "ok"
    assert audio_status("b.mp3", tmp_path) == "missing"


# ----- saving -----


def test_save_words_round_trip_and_backup(tmp_path):
    path = tmp_path / "input" / "words.txt"
    entries = [entry("你好", audio="ni-hao.mp3"), entry("谢谢", "xièxie", "thank you", "")]
    save_words(path, entries)
    loaded, warnings = parse_words(path)
    assert warnings == []
    assert [(e.hanzi, e.pinyin, e.meaning, e.audio) for e in loaded] == [
        (e.hanzi, e.pinyin, e.meaning, e.audio) for e in entries
    ]

    save_words(path, entries[:1])  # second save keeps the first file as .bak
    assert (tmp_path / "input" / "words.txt.bak").read_text(encoding="utf-8") == entries_to_text(entries)
    assert not (tmp_path / "input" / "words.txt.tmp").exists()


def test_entry_without_audio_is_written_with_trailing_bar():
    assert "谢谢 | xièxie | thank you |\n" in entries_to_text([entry("谢谢", "xièxie", "thank you")])


# ----- audio files -----


def test_copy_audio_copied_same_and_conflict(tmp_path):
    source = tmp_path / "downloads" / "ni-hao.mp3"
    source.parent.mkdir()
    source.write_bytes(b"one")
    audio_dir = tmp_path / "audio"

    assert copy_audio(source, audio_dir) == ("ni-hao.mp3", "copied")
    assert copy_audio(source, audio_dir) == ("ni-hao.mp3", "same")

    source.write_bytes(b"two")
    assert copy_audio(source, audio_dir) == ("ni-hao.mp3", "conflict")
    assert (audio_dir / "ni-hao.mp3").read_bytes() == b"one"  # nothing was replaced
    assert copy_audio(source, audio_dir, overwrite=True) == ("ni-hao.mp3", "copied")
    assert (audio_dir / "ni-hao.mp3").read_bytes() == b"two"


def test_copy_audio_when_file_is_already_in_the_audio_folder(tmp_path):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    (audio_dir / "a.mp3").write_bytes(b"x")
    assert copy_audio(audio_dir / "a.mp3", audio_dir) == ("a.mp3", "same")


# ----- pasting -----


def test_merge_pasted_adds_updates_and_reports_bad_lines():
    entries = [entry("你好", meaning="old")]
    text = (
        "# comment\n\n"
        "你好 | nǐ hǎo | hello | \n"
        "谢谢 | xièxie | thank you |\n"
        "only one field\n"
        " | x | y | \n"
    )
    added, updated, errors = merge_pasted(entries, text)
    assert (added, updated) == (1, 1)
    assert [e.hanzi for e in entries] == ["你好", "谢谢"]
    assert entries[0].meaning == "hello"
    assert len(errors) == 2 and errors[0].startswith("Line 5")


# ----- the whole build -----


def test_run_build_saves_words_builds_and_remembers_the_number(project):
    _, config = project
    entries = [entry("你好", audio="ni-hao.mp3"), entry("谢谢", "xièxie", "thank you")]
    result, subdeck = run_build(config, entries, "Greetings")

    assert result.deck_title == "Chinese Words::01 Greetings"
    assert result.entries_built == 2 and config.output.is_file()
    assert [e.hanzi for e in parse_words(config.words)[0]] == ["你好", "谢谢"]
    saved = json.loads(config.subdecks_file.read_text(encoding="utf-8"))["subdecks"]
    assert saved["greetings"]["number"] == 1


def test_run_build_reports_all_problems_and_changes_nothing(project):
    _, config = project
    before = config.words.read_text(encoding="utf-8")
    with pytest.raises(GuiError) as caught:
        run_build(config, [entry("你好"), entry("你好")], "A::B")
    assert len(caught.value.messages) == 2  # bad name and duplicate
    assert config.words.read_text(encoding="utf-8") == before
    assert not config.subdecks_file.exists() and not config.output.exists()


def test_failed_build_does_not_use_up_a_number(project):
    _, config = project
    config.all_json.unlink()  # build fails: no stroke data
    with pytest.raises(Exception):
        run_build(config, [entry("你好")], "Greetings")
    assert not config.subdecks_file.exists()


# ----- friendly messages -----


def test_friendly_error_messages():
    assert "access denied" in friendly_error(PermissionError(13, "denied", "hanzi.apkg"))
    assert "hanzi.apkg" in friendly_error(PermissionError(13, "denied", "hanzi.apkg"))
    assert friendly_error(SubdeckError("bad name")) == "bad name"
    assert "UTF-8" in friendly_error(UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad"))
    assert friendly_error(ZeroDivisionError()) is None  # a real bug is not hidden
