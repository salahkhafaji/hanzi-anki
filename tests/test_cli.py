import json
import sys

import pytest

from hanzi_anki.cli import main


def run(monkeypatch, config, *args):
    monkeypatch.setattr(sys, "argv", ["hanzi-anki", "build", "--config", str(config.root / "config.toml"), *args])
    main()


def test_build_with_name_numbers_the_subdeck_and_remembers_it(project, monkeypatch, capsys):
    _, config = project
    run(monkeypatch, config, "--name", "Greetings")
    run(monkeypatch, config, "--name", "Food")
    run(monkeypatch, config, "--name", "greetings")  # same subdeck again

    out = capsys.readouterr().out
    assert out.count("Chinese Words::01 Greetings") == 2
    assert "Chinese Words::02 Food" in out

    saved = json.loads(config.subdecks_file.read_text(encoding="utf-8"))["subdecks"]
    assert {key: item["number"] for key, item in saved.items()} == {"greetings": 1, "food": 2}


def test_failed_build_does_not_use_up_a_number(project, monkeypatch):
    _, config = project
    config.words.unlink()
    with pytest.raises(SystemExit):
        run(monkeypatch, config, "--name", "Greetings")
    assert not config.subdecks_file.exists()


def test_name_is_asked_when_missing(project, monkeypatch, capsys):
    _, config = project
    monkeypatch.setattr("builtins.input", lambda prompt: "Travel")
    run(monkeypatch, config)
    assert "Chinese Words::01 Travel" in capsys.readouterr().out
