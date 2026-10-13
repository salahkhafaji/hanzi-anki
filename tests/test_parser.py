from hanzi_anki.parser import parse_line, parse_words, split_characters


def test_split_skips_punctuation_spaces_and_latin():
    assert split_characters("你好吗？ Hello, 我！") == ["你", "好", "吗", "我"]


def test_split_keeps_repeated_characters_in_order():
    assert split_characters("谢谢") == ["谢", "谢"]
    assert split_characters("好不好") == ["好", "不", "好"]


def test_split_empty_when_no_chinese():
    assert split_characters("Hello, 123!") == []


def test_parse_line_with_and_without_audio():
    entry = parse_line("你好 | nǐ hǎo | hello | ni-hao.mp3", 1)
    assert (entry.hanzi, entry.pinyin, entry.meaning, entry.audio) == ("你好", "nǐ hǎo", "hello", "ni-hao.mp3")
    assert parse_line("谢谢 | xièxie | thank you |", 2).audio == ""
    assert parse_line("谢谢 | xièxie | thank you", 3).audio == ""


def test_parse_words_skips_comments_blanks_and_bad_lines(tmp_path):
    path = tmp_path / "words.txt"
    path.write_text(
        "\ufeff# my list\n\n你好 | nǐ hǎo | hello |\nbad line\n谢谢 | xièxie | thank you |\n",
        encoding="utf-8",
    )
    entries, warnings = parse_words(path)
    assert [e.hanzi for e in entries] == ["你好", "谢谢"]
    assert len(warnings) == 1 and "line 4" in warnings[0]


def test_duplicate_hanzi_later_line_wins_and_keeps_position(tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("你好 | old | old |\n谢谢 | x | y |\n你好 | nǐ hǎo | hello |\n", encoding="utf-8")
    entries, warnings = parse_words(path)
    assert [e.hanzi for e in entries] == ["你好", "谢谢"]
    assert entries[0].pinyin == "nǐ hǎo"
    assert len(warnings) == 1
