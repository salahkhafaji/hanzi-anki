"""Tests that open the real window (hidden). Skipped if Tkinter or a display is missing."""

import time

import pytest

tk = pytest.importorskip("tkinter")

from hanzi_anki.gui import App  # noqa: E402


@pytest.fixture
def app(project, monkeypatch):
    _, config = project
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    root.withdraw()
    monkeypatch.setattr("hanzi_anki.gui.messagebox.askyesnocancel", lambda *a, **k: False)
    window = App(root, config)
    yield window
    root.destroy()


def result_text(app):
    return app.result.get("1.0", "end").strip()


def fill(app, hanzi, pinyin="", meaning="", audio=""):
    app.hanzi_var.set(hanzi)
    app.pinyin_var.set(pinyin)
    app.meaning_var.set(meaning)
    app.audio_var.set(audio)


def test_loads_words_and_shows_audio_status(app):
    assert [e.hanzi for e in app.entries] == ["你好", "我不懂这个字。"]
    rows = [app.table.item(i, "values") for i in app.table.get_children()]
    assert rows[0][4] == "ok" and rows[1][4] == "-"


def test_preview_shows_the_deck_name_and_errors(app):
    assert "Type a name" in app.preview.cget("text")
    app.name_var.set("Food")
    assert "Chinese Words::01 Food" in app.preview.cget("text")
    app.name_var.set("A::B")
    assert "::" in app.preview.cget("text")


def test_add_update_move_delete(app):
    fill(app, "谢谢", "xièxie", "thank you")
    app.add_entry()
    assert [e.hanzi for e in app.entries][-1] == "谢谢" and app.dirty
    assert app.root.title().endswith("*")

    fill(app, "谢谢", "xièxie", "thanks")  # same hanzi again
    app.add_entry()
    assert "already in the list" in result_text(app)
    assert len(app.entries) == 3

    app.table.selection_set("2")
    app.on_select()
    assert app.hanzi_var.get() == "谢谢"
    app.meaning_var.set("thanks!")
    app.update_entry()
    assert app.entries[2].meaning == "thanks!"

    app.table.selection_set("2")
    app.move(-1)
    assert [e.hanzi for e in app.entries][1] == "谢谢"

    app.delete_entry()
    assert [e.hanzi for e in app.entries] == ["你好", "我不懂这个字。"]


def test_actions_without_a_selected_row_explain_what_to_do(app):
    app.delete_entry()
    assert "Select a row" in result_text(app)
    app.update_entry()
    assert "Select a row" in result_text(app)


def test_empty_hanzi_is_refused(app):
    fill(app, "", "x", "y")
    app.add_entry()
    assert "hanzi field is empty" in result_text(app)
    assert len(app.entries) == 2


def test_build_without_name_shows_a_clear_message(app):
    kind, text = app._build_now(list(app.entries), "")
    assert kind == "error" and "name is empty" in text


def test_build_in_the_background_then_show_the_result(app):
    app.name_var.set("Greetings")
    app.start_build()
    assert app.busy
    deadline = time.time() + 15
    while app.busy and time.time() < deadline:
        app.root.update()
        time.sleep(0.02)
    assert not app.busy
    text = result_text(app)
    assert "Built Chinese Words::01 Greetings" in text and "Entries built:      2" in text
    assert app.config.output.is_file()
    assert "already exists" in app.preview.cget("text")
    assert not app.dirty


def test_unexpected_error_is_logged_not_shown_as_a_trace(app, monkeypatch):
    def boom(*args, **kwargs):
        raise ZeroDivisionError("bug")

    monkeypatch.setattr("hanzi_anki.gui.run_build", boom)
    kind, text = app._build_now(list(app.entries), "Greetings")
    assert kind == "error" and "unexpected" in text and "Traceback" not in text
    assert "ZeroDivisionError" in (app.config.root / "hanzi-anki-error.log").read_text(encoding="utf-8")


def test_save_writes_the_file(app):
    fill(app, "谢谢", "xièxie", "thank you")
    app.add_entry()
    assert app.save_clicked()
    assert "谢谢" in app.config.words.read_text(encoding="utf-8") and not app.dirty
