import pytest

from hanzi_anki.subdecks import (
    SubdeckError,
    choose_subdeck,
    clean_name,
    deck_title,
    save_subdeck,
)


def test_first_name_gets_first_number(tmp_path):
    path = tmp_path / "subdecks.json"
    subdeck = choose_subdeck(path, "Greetings", first_number=1)
    assert (subdeck.number, subdeck.is_new, subdeck.label) == (1, True, "01 Greetings")


def test_choosing_does_not_save(tmp_path):
    path = tmp_path / "subdecks.json"
    choose_subdeck(path, "Greetings", 1)
    assert not path.exists()


def test_new_names_count_up_and_known_names_keep_their_number(tmp_path):
    path = tmp_path / "subdecks.json"
    save_subdeck(path, choose_subdeck(path, "Greetings", 1))
    save_subdeck(path, choose_subdeck(path, "Food", 1))

    again = choose_subdeck(path, "  greetings ", 1)  # other letter case and spaces
    assert (again.number, again.is_new, again.label) == (1, False, "01 Greetings")

    third = choose_subdeck(path, "Travel", 1)
    assert third.number == 3


def test_first_number_is_used_for_an_empty_file(tmp_path):
    assert choose_subdeck(tmp_path / "s.json", "Greetings", 12).label == "12 Greetings"


def test_deck_title_with_and_without_parent(tmp_path):
    subdeck = choose_subdeck(tmp_path / "s.json", "Greetings", 3)
    assert deck_title("Chinese Words", subdeck) == "Chinese Words::03 Greetings"
    assert deck_title("", subdeck) == "03 Greetings"


@pytest.mark.parametrize("bad", ["", "   ", "A::B"])
def test_bad_names_are_rejected(bad):
    with pytest.raises(SubdeckError):
        clean_name(bad)


def test_broken_numbers_file_gives_a_clear_error(tmp_path):
    path = tmp_path / "subdecks.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(SubdeckError):
        choose_subdeck(path, "Greetings", 1)
