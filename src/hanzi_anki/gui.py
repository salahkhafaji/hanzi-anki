"""A small window app: edit the words, pick audio files, build the deck.

Start it with:  uv run hanzi-anki gui

It uses the same code as the command line, and it saves your list to
input/words.txt, so both ways give the same .apkg file.

The file has two parts:
  1. Plain functions (no window needed). They check the input, save files and run
     the build. The tests use them.
  2. The App class, which is only the window.
"""

import contextlib
import filecmp
import io
import os
import queue
import shutil
import subprocess
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

try:  # Tkinter comes with Python. The functions below also work without it.
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter import font as tkfont
except ImportError:  # pragma: no cover
    tk = None

from .audio import find_audio
from .cli import print_summary
from .config import Config, ConfigError, load_config
from .deck import BuildError, BuildResult, build_deck
from .parser import Entry, parse_line, parse_words
from .strokes import StrokeDataError
from .subdecks import SubdeckError, Subdeck, choose_subdeck, deck_title, save_subdeck

WORDS_HEADER = "# hanzi | pinyin | meaning | audio_file"
ERROR_LOG_NAME = "hanzi-anki-error.log"
FIELD_LABELS = ("hanzi", "pinyin", "meaning", "audio")


# ---------------------------------------------------------------------------
# Part 1: plain functions
# ---------------------------------------------------------------------------


class GuiError(Exception):
    """The input has problems. `messages` is a list of plain sentences."""

    def __init__(self, messages: list[str]):
        super().__init__("\n".join(messages))
        self.messages = messages


def make_entry(hanzi: str, pinyin: str, meaning: str, audio: str) -> Entry:
    return Entry(hanzi.strip(), pinyin.strip(), meaning.strip(), audio.strip(), line_number=0)


def check_entry(entry: Entry) -> list[str]:
    """Problems of one entry. An empty list means it is fine."""
    problems = []
    if not entry.hanzi:
        problems.append("The hanzi field is empty.")
    for label, text in zip(FIELD_LABELS, (entry.hanzi, entry.pinyin, entry.meaning, entry.audio)):
        if "|" in text:
            problems.append(f"The {label} field contains '|', which is used to separate the fields.")
        if "\n" in text or "\r" in text:
            problems.append(f"The {label} field must be one line.")
    if any(ch in entry.audio for ch in '/\\:*?"<>'):
        problems.append("The audio field must be a file name only, without a folder.")
    return problems


def validate_entries(entries: list[Entry]) -> list[str]:
    """Problems of the whole list. An empty list means it can be built."""
    errors = []
    if not entries:
        errors.append("The list is empty. Add at least one entry.")
    first_row: dict[str, int] = {}
    for number, entry in enumerate(entries, start=1):
        for problem in check_entry(entry):
            errors.append(f"Row {number} ({entry.hanzi or 'no hanzi'}): {problem}")
        if entry.hanzi in first_row:
            errors.append(f"Row {number}: '{entry.hanzi}' is already in row {first_row[entry.hanzi]}.")
        first_row.setdefault(entry.hanzi, number)
    return errors


def audio_status(audio: str, audio_dir: Path) -> str:
    """'' (no audio), 'ok' or 'missing'. Shown in the table."""
    if not audio:
        return ""
    return "ok" if find_audio(audio, audio_dir) else "missing"


def entries_to_text(entries: list[Entry]) -> str:
    lines = [WORDS_HEADER]
    for e in entries:
        lines.append(f"{e.hanzi} | {e.pinyin} | {e.meaning} | {e.audio}".rstrip())
    return "\n".join(lines) + "\n"


def save_words(path: Path, entries: list[Entry]) -> None:
    """Write words.txt. The old file is kept as words.txt.bak, and the new file
    is written to a temporary file first, so a failure cannot leave half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        shutil.copyfile(path, path.with_name(path.name + ".bak"))
    temp = path.with_name(path.name + ".tmp")
    try:
        temp.write_text(entries_to_text(entries), encoding="utf-8", newline="\n")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def copy_audio(source: Path, audio_dir: Path, overwrite: bool = False) -> tuple[str, str]:
    """Copy an audio file into the audio folder.
    Returns (file name, status). Status is 'copied', 'same' (already there, same
    content) or 'conflict' (a different file with this name exists; nothing copied)."""
    source = Path(source)
    audio_dir = Path(audio_dir)
    audio_dir.mkdir(parents=True, exist_ok=True)
    target = audio_dir / source.name
    if target.exists():
        if source.resolve() == target.resolve() or filecmp.cmp(source, target, shallow=False):
            return source.name, "same"
        if not overwrite:
            return source.name, "conflict"
    shutil.copyfile(source, target)
    return source.name, "copied"


def merge_pasted(entries: list[Entry], text: str) -> tuple[int, int, list[str]]:
    """Add lines in the words.txt format to the list (the list is changed in place).
    A hanzi that is already in the list is updated. Returns (added, updated, errors)."""
    added = updated = 0
    errors: list[str] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            entry = parse_line(line, number)
        except ValueError as error:
            errors.append(f"Line {number}: {error}")
            continue
        problems = check_entry(entry)
        if problems:
            errors.append(f"Line {number}: {problems[0]}")
            continue
        for index, existing in enumerate(entries):
            if existing.hanzi == entry.hanzi:
                entries[index] = entry
                updated += 1
                break
        else:
            entries.append(entry)
            added += 1
    return added, updated, errors


def run_build(config: Config, entries: list[Entry], name: str) -> tuple[BuildResult, Subdeck]:
    """Check everything, save words.txt, build the deck, remember the subdeck number.
    Raises GuiError (list of problems) or the usual build errors."""
    errors = []
    subdeck = None
    try:
        subdeck = choose_subdeck(config.subdecks_file, name, config.first_number)
    except SubdeckError as error:
        errors.append(str(error))
    errors += validate_entries(entries)
    if errors:
        raise GuiError(errors)

    save_words(config.words, entries)
    result = build_deck(config, subdeck)
    save_subdeck(config.subdecks_file, subdeck)  # only after the build worked
    return result, subdeck


def build_report(result: BuildResult) -> str:
    """The same summary the command line prints, as text."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        print_summary(result)
    return buffer.getvalue().strip()


def friendly_error(error: Exception) -> str | None:
    """A plain sentence for errors we expect, or None for a real bug."""
    if isinstance(error, (ConfigError, BuildError, StrokeDataError, SubdeckError)):
        return str(error)
    if isinstance(error, PermissionError):
        name = error.filename or "a file"
        return (
            f"The system would not let the program use '{name}' (access denied). "
            "Close any program that has it open (for example Anki), wait until OneDrive "
            "has finished syncing, and try again."
        )
    if isinstance(error, FileNotFoundError):
        return f"A file or folder was not found: {error.filename or error}"
    if isinstance(error, UnicodeDecodeError):
        return "A text file is not saved as UTF-8. Open it in VS Code and save it again as UTF-8."
    if isinstance(error, OSError):
        return f"A file could not be read or written: {error}"
    return None


def log_error(folder: Path, error: Exception) -> Path:
    """Write the technical details of an unexpected error to a log file."""
    path = Path(folder) / ERROR_LOG_NAME
    details = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S}\n{details}\n")
    return path


def open_path(path: Path) -> None:
    """Open a file or folder with the system's default program."""
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # noqa: S606 (Windows only)
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def enable_dpi_awareness() -> None:
    """Makes the text sharp on Windows screens with scaling."""
    if sys.platform.startswith("win"):
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # not important
            pass


# ---------------------------------------------------------------------------
# Part 2: the window
# ---------------------------------------------------------------------------


class App:
    def __init__(self, root, config: Config):
        self.root = root
        self.config = config
        self.entries: list[Entry] = []
        self.dirty = False
        self.busy = False
        self.last_output: Path | None = None
        self.last_audio_folder: Path | None = None
        self.results = queue.Queue()

        root.geometry("1000x800")
        root.minsize(860, 640)
        self._set_dirty(False)
        self._set_fonts()
        self._build_widgets()
        self._load_words()
        self._update_preview()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ----- setup -----

    def _set_fonts(self) -> None:
        """Use a font that can show Chinese, and make rows high enough for it."""
        available = set(tkfont.families(self.root))
        family = next(
            (
                name
                for name in (
                    "Microsoft YaHei UI",
                    "Microsoft YaHei",
                    "PingFang SC",
                    "Noto Sans CJK SC",
                    "Noto Sans SC",
                    "WenQuanYi Micro Hei",
                )
                if name in available
            ),
            None,
        )
        for font_name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
            font = tkfont.nametofont(font_name)
            font.configure(size=11)
            if family:
                font.configure(family=family)
        line = tkfont.nametofont("TkDefaultFont").metrics("linespace")
        ttk.Style().configure("Treeview", rowheight=line + 10)
        ttk.Style().configure("Big.TButton", padding=(18, 8))

    def _build_widgets(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=2)
        outer.rowconfigure(4, weight=2)

        # 1. Subdeck
        deck = ttk.LabelFrame(outer, text=" 1. Subdeck ", padding=10)
        deck.grid(row=0, column=0, sticky="ew")
        deck.columnconfigure(1, weight=1)
        ttk.Label(deck, text="Name").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.name_var = tk.StringVar()
        self.name_var.trace_add("write", self._update_preview)
        ttk.Entry(deck, textvariable=self.name_var).grid(row=0, column=1, sticky="ew")
        self.preview = ttk.Label(deck, text="")
        self.preview.grid(row=1, column=1, sticky="w", pady=(6, 0))

        # 2. Word list
        words = ttk.LabelFrame(outer, text=" 2. Words (the order here is the order in Anki) ", padding=10)
        words.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        words.columnconfigure(0, weight=1)
        words.rowconfigure(0, weight=1)

        columns = ("hanzi", "pinyin", "meaning", "audio", "file")
        self.table = ttk.Treeview(words, columns=columns, show="headings", selectmode="browse", height=7)
        for column, title, width, stretch in (
            ("hanzi", "Hanzi", 140, False),
            ("pinyin", "Pinyin", 190, False),
            ("meaning", "Meaning", 200, True),
            ("audio", "Audio file", 170, False),
            ("file", "Audio", 80, False),
        ):
            self.table.heading(column, text=title)
            self.table.column(column, width=width, stretch=stretch)
        self.table.tag_configure("missing", foreground="#b91c1c")
        self.table.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(words, orient="vertical", command=self.table.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scroll.set)
        self.table.bind("<<TreeviewSelect>>", self.on_select)

        side = ttk.Frame(words)
        side.grid(row=0, column=2, sticky="n", padx=(10, 0))
        for text, command in (
            ("Move up", lambda: self.move(-1)),
            ("Move down", lambda: self.move(1)),
            ("Delete", self.delete_entry),
            ("Paste lines...", self.paste_dialog),
        ):
            ttk.Button(side, text=text, command=command).pack(fill="x", pady=2)

        # Edit form
        form = ttk.LabelFrame(outer, text=" Add or change an entry ", padding=10)
        form.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.hanzi_var = tk.StringVar()
        self.pinyin_var = tk.StringVar()
        self.meaning_var = tk.StringVar()
        self.audio_var = tk.StringVar()
        for column, (label, var, weight) in enumerate(
            (
                ("Hanzi", self.hanzi_var, 1),
                ("Pinyin", self.pinyin_var, 1),
                ("Meaning", self.meaning_var, 2),
                ("Audio file", self.audio_var, 1),
            )
        ):
            form.columnconfigure(column, weight=weight)
            ttk.Label(form, text=label).grid(row=0, column=column, sticky="w", padx=(0, 6))
            entry = ttk.Entry(form, textvariable=var)
            entry.grid(row=1, column=column, sticky="ew", padx=(0, 6))
            entry.bind("<Return>", lambda event: self.on_enter())
            if label == "Hanzi":
                self.hanzi_entry = entry
        ttk.Button(form, text="Browse...", command=self.browse_audio).grid(row=1, column=4)
        buttons = ttk.Frame(form)
        buttons.grid(row=2, column=0, columnspan=5, sticky="w", pady=(8, 0))
        ttk.Button(buttons, text="Add as new", command=self.add_entry).pack(side="left")
        ttk.Button(buttons, text="Update selected", command=self.update_entry).pack(side="left", padx=6)
        ttk.Button(buttons, text="Clear form", command=self.clear_form).pack(side="left")

        # 3. Build
        actions = ttk.Frame(outer)
        actions.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.build_button = ttk.Button(actions, text="Build deck", style="Big.TButton", command=self.start_build)
        self.build_button.pack(side="left")
        ttk.Button(actions, text="Save words.txt", command=self.save_clicked).pack(side="left", padx=8)
        self.open_anki_button = ttk.Button(actions, text="Open in Anki", command=self.open_in_anki, state="disabled")
        self.open_anki_button.pack(side="right")
        ttk.Button(actions, text="Open output folder", command=self.open_output_folder).pack(side="right", padx=8)

        result_frame = ttk.LabelFrame(outer, text=" Result ", padding=6)
        result_frame.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        self.result = tk.Text(result_frame, height=10, wrap="word", state="disabled", relief="flat")
        self.result.tag_configure("error", foreground="#b91c1c")
        self.result.tag_configure("ok", foreground="#15803d")
        self.result.tag_configure("info", foreground="#374151")
        self.result.grid(row=0, column=0, sticky="nsew")
        result_scroll = ttk.Scrollbar(result_frame, orient="vertical", command=self.result.yview)
        result_scroll.grid(row=0, column=1, sticky="ns")
        self.result.configure(yscrollcommand=result_scroll.set)

    def _load_words(self) -> None:
        if not self.config.words.is_file():
            self.show("No words.txt yet. Add entries above, or paste lines.", "info")
            return
        try:
            self.entries, warnings = parse_words(self.config.words)
        except Exception as error:  # noqa: BLE001 (shown to the person)
            message = friendly_error(error) or f"words.txt could not be read: {error}"
            self.show(f"{message}\nThe file is not changed until you save.", "error")
            return
        self.refresh_table()
        count = f"Loaded {len(self.entries)} entries from {self.config.words.name}."
        if warnings:
            self.show(count + "\n" + "\n".join(warnings), "error")
        else:
            self.show(count, "info")

    # ----- small helpers -----

    def show(self, text: str, kind: str = "info", more: str = "") -> None:
        """Replace the text in the result box. `more` is added below in plain gray."""
        self.result.configure(state="normal")
        self.result.delete("1.0", "end")
        self.result.insert("end", text, kind)
        if more:
            self.result.insert("end", "\n\n" + more, "info")
        self.result.configure(state="disabled")

    def _set_dirty(self, dirty: bool) -> None:
        self.dirty = dirty
        self.root.title("Hanzi Anki" + (" *" if dirty else ""))

    def _update_preview(self, *_args) -> None:
        name = self.name_var.get() if hasattr(self, "name_var") else ""
        if not name.strip():
            self.preview.configure(text="Type a name for the new subdeck.", foreground="#6b7280")
            return
        try:
            subdeck = choose_subdeck(self.config.subdecks_file, name, self.config.first_number)
        except SubdeckError as error:
            self.preview.configure(text=str(error), foreground="#b91c1c")
            return
        state = "new" if subdeck.is_new else "already exists, it will be updated"
        self.preview.configure(
            text=f"Deck in Anki:  {deck_title(self.config.parent_deck, subdeck)}   ({state})",
            foreground="#15803d",
        )

    def refresh_table(self, select: int | None = None) -> None:
        self.table.delete(*self.table.get_children())
        for index, e in enumerate(self.entries):
            status = audio_status(e.audio, self.config.audio_dir)
            label = {"": "-", "ok": "ok", "missing": "missing"}[status]
            tags = ("missing",) if status == "missing" else ()
            self.table.insert("", "end", iid=str(index), values=(e.hanzi, e.pinyin, e.meaning, e.audio, label), tags=tags)
        if select is not None and 0 <= select < len(self.entries):
            self.table.selection_set(str(select))
            self.table.see(str(select))

    def selected_index(self) -> int | None:
        selection = self.table.selection()
        return int(selection[0]) if selection else None

    def read_form(self) -> Entry:
        return make_entry(self.hanzi_var.get(), self.pinyin_var.get(), self.meaning_var.get(), self.audio_var.get())

    def clear_form(self) -> None:
        for var in (self.hanzi_var, self.pinyin_var, self.meaning_var, self.audio_var):
            var.set("")
        self.table.selection_remove(*self.table.selection())
        self.hanzi_entry.focus_set()

    def _problems_for_form(self, entry: Entry, ignore_index: int | None = None) -> list[str]:
        problems = check_entry(entry)
        for index, other in enumerate(self.entries):
            if index != ignore_index and other.hanzi == entry.hanzi and entry.hanzi:
                problems.append(f"'{entry.hanzi}' is already in the list (row {index + 1}). Select it and press 'Update selected'.")
        return problems

    # ----- table actions -----

    def on_select(self, _event=None) -> None:
        index = self.selected_index()
        if index is None:
            return
        e = self.entries[index]
        self.hanzi_var.set(e.hanzi)
        self.pinyin_var.set(e.pinyin)
        self.meaning_var.set(e.meaning)
        self.audio_var.set(e.audio)

    def on_enter(self) -> None:
        if self.selected_index() is None:
            self.add_entry()
        else:
            self.update_entry()

    def add_entry(self) -> None:
        entry = self.read_form()
        problems = self._problems_for_form(entry)
        if problems:
            self.show("Cannot add this entry:\n- " + "\n- ".join(problems), "error")
            return
        self.entries.append(entry)
        self._set_dirty(True)
        self.refresh_table()
        self.clear_form()
        self.show(f"Added '{entry.hanzi}'. The list has {len(self.entries)} entries.", "info")

    def update_entry(self) -> None:
        index = self.selected_index()
        if index is None:
            self.show("Select a row in the table first.", "error")
            return
        entry = self.read_form()
        problems = self._problems_for_form(entry, ignore_index=index)
        if problems:
            self.show("Cannot update this entry:\n- " + "\n- ".join(problems), "error")
            return
        self.entries[index] = entry
        self._set_dirty(True)
        self.refresh_table(select=index)
        self.show(f"Updated '{entry.hanzi}'.", "info")

    def delete_entry(self) -> None:
        index = self.selected_index()
        if index is None:
            self.show("Select a row in the table first.", "error")
            return
        removed = self.entries.pop(index)
        self._set_dirty(True)
        self.refresh_table(select=min(index, len(self.entries) - 1))
        self.show(f"Deleted '{removed.hanzi}'.", "info")

    def move(self, step: int) -> None:
        index = self.selected_index()
        if index is None:
            self.show("Select a row in the table first.", "error")
            return
        target = index + step
        if not 0 <= target < len(self.entries):
            return
        self.entries[index], self.entries[target] = self.entries[target], self.entries[index]
        self._set_dirty(True)
        self.refresh_table(select=target)

    def browse_audio(self) -> None:
        start = self.last_audio_folder or self.config.audio_dir
        chosen = filedialog.askopenfilename(
            title="Choose an audio file",
            initialdir=str(start) if Path(start).is_dir() else None,
            filetypes=[("Audio files", "*.mp3 *.wav *.ogg *.m4a"), ("All files", "*.*")],
        )
        if not chosen:
            return
        source = Path(chosen)
        self.last_audio_folder = source.parent
        try:
            name, status = copy_audio(source, self.config.audio_dir)
            if status == "conflict":
                replace = messagebox.askyesno(
                    "Replace the file?",
                    f"A different file named '{name}' is already in the audio folder.\n\nReplace it?",
                )
                if not replace:
                    return
                name, status = copy_audio(source, self.config.audio_dir, overwrite=True)
        except Exception as error:  # noqa: BLE001
            self._show_exception(error)
            return
        self.audio_var.set(name)
        note = {"copied": "copied into", "same": "is already in"}[status]
        self.show(f"'{name}' {note} {self.config.audio_dir}", "info")

    def paste_dialog(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Paste lines")
        window.geometry("760x420")
        window.transient(self.root)
        ttk.Label(
            window,
            text="Paste lines like:  hanzi | pinyin | meaning | audio_file.mp3\n"
            "A hanzi that is already in the list is updated.",
            padding=10,
        ).pack(anchor="w")
        text = tk.Text(window, wrap="none", height=14)
        text.pack(fill="both", expand=True, padx=10)
        text.focus_set()

        def add_lines() -> None:
            added, updated, errors = merge_pasted(self.entries, text.get("1.0", "end"))
            if added or updated:
                self._set_dirty(True)
                self.refresh_table()
            report = f"Pasted: {added} added, {updated} updated."
            if errors:
                report += f"\n{len(errors)} line(s) skipped:\n- " + "\n- ".join(errors[:10])
                if len(errors) > 10:
                    report += f"\n... and {len(errors) - 10} more"
            self.show(report, "error" if errors else "ok")
            window.destroy()

        row = ttk.Frame(window, padding=10)
        row.pack(fill="x")
        ttk.Button(row, text="Add lines", command=add_lines).pack(side="left")
        ttk.Button(row, text="Cancel", command=window.destroy).pack(side="left", padx=8)

    # ----- save and build -----

    def save_clicked(self) -> bool:
        problems = validate_entries(self.entries) if self.entries else []
        if problems:
            self.show("Fix this before saving:\n- " + "\n- ".join(problems), "error")
            return False
        try:
            save_words(self.config.words, self.entries)
        except Exception as error:  # noqa: BLE001
            self._show_exception(error)
            return False
        self._set_dirty(False)
        self.show(f"Saved {len(self.entries)} entries to {self.config.words}\n(the old file is kept as words.txt.bak)", "ok")
        return True

    def start_build(self) -> None:
        if self.busy:
            return
        self.busy = True
        self.build_button.state(["disabled"])
        self.show("Building, please wait...", "info")
        threading.Thread(target=self._worker, args=(list(self.entries), self.name_var.get()), daemon=True).start()
        self.root.after(100, self._poll)

    def _worker(self, entries: list[Entry], name: str) -> None:
        self.results.put(self._build_now(entries, name))

    def _build_now(self, entries: list[Entry], name: str) -> tuple[str, object]:
        """Runs the build. Returns ('ok', result) or ('error', text). Never raises."""
        try:
            result, _subdeck = run_build(self.config, entries, name)
            return "ok", result
        except GuiError as error:
            return "error", "Cannot build yet:\n- " + "\n- ".join(error.messages)
        except Exception as error:  # noqa: BLE001
            return "error", self._describe_exception(error)

    def _describe_exception(self, error: Exception) -> str:
        message = friendly_error(error)
        if message:
            return message
        try:
            log = log_error(self.config.root, error)
            where = f"Details are saved in {log.name}."
        except OSError:
            where = "The details could not be saved."
        return f"Something unexpected went wrong ({type(error).__name__}). {where}"

    def _show_exception(self, error: Exception) -> None:
        self.show(self._describe_exception(error), "error")

    def _poll(self) -> None:
        try:
            kind, payload = self.results.get_nowait()
        except queue.Empty:
            self.root.after(100, self._poll)
            return
        self._finish(kind, payload)

    def _finish(self, kind: str, payload) -> None:
        self.busy = False
        self.build_button.state(["!disabled"])
        if kind == "error":
            self.show(payload, "error")
            return
        self.last_output = payload.output
        self.open_anki_button.state(["!disabled"])
        self._set_dirty(False)
        self._update_preview()  # the name is known now, so it says "already exists"
        self.refresh_table()
        more = build_report(payload) + "\n\nNow import the file into Anki (button 'Open in Anki')."
        self.show(f"Built {payload.deck_title}", "ok", more)

    # ----- open things -----

    def open_in_anki(self) -> None:
        if not self.last_output or not self.last_output.is_file():
            self.show("Build the deck first.", "error")
            return
        try:
            open_path(self.last_output)
        except Exception as error:  # noqa: BLE001
            self._show_exception(error)

    def open_output_folder(self) -> None:
        folder = self.config.output.parent
        try:
            folder.mkdir(parents=True, exist_ok=True)
            open_path(folder)
        except Exception as error:  # noqa: BLE001
            self._show_exception(error)

    def on_close(self) -> None:
        if self.dirty:
            answer = messagebox.askyesnocancel("Unsaved changes", "Save your changes to words.txt before closing?")
            if answer is None:
                return
            if answer and not self.save_clicked():
                return
        self.root.destroy()


def run_gui(config_path: Path) -> int:
    """Open the window. Returns the exit code."""
    if tk is None:
        print("Error: Tkinter is not available in this Python. Use 'uv run hanzi-anki build' instead.", file=sys.stderr)
        return 1
    enable_dpi_awareness()
    try:
        root = tk.Tk()
    except tk.TclError as error:
        print(f"Error: cannot open a window here ({error}).", file=sys.stderr)
        return 1
    try:
        config = load_config(Path(config_path))
    except ConfigError as error:
        root.withdraw()
        messagebox.showerror("hanzi-anki", str(error))
        root.destroy()
        return 1
    App(root, config)
    root.mainloop()
    return 0
