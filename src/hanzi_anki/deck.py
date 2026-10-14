"""Build the Anki deck and write the .apkg file."""

import hashlib
import html
import json
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import genanki

from .audio import find_audio, media_name, sound_tag
from .config import Config
from .parser import Entry, parse_words, split_characters
from .strokes import build_strokes_json, load_all_json
from .subdecks import Subdeck, deck_title

# Anki keeps media whose name starts with an underscore, even if no card uses it.
HANZI_WRITER_MEDIA_NAME = "_hanzi-writer.min.js"


class BuildError(Exception):
    """Raised when the deck cannot be built."""


@dataclass
class BuildResult:
    output: Path
    deck_title: str = ""
    entries_built: int = 0
    characters_found: set = field(default_factory=set)
    characters_missing: list = field(default_factory=list)
    missing_audio: list = field(default_factory=list)  # (hanzi, file name)
    warnings: list = field(default_factory=list)


def note_guid(subdeck_key: str, hanzi: str) -> str:
    """Stable GUID from the subdeck and the hanzi text.
    Importing the same entry again updates its note. The same hanzi in another
    subdeck is a different note."""
    return genanki.guid_for(subdeck_key, hanzi)


def deck_id_for(title: str) -> int:
    """Stable deck ID made from the full deck name, so every subdeck has its own ID."""
    return int(hashlib.sha256(title.encode("utf-8")).hexdigest()[:12], 16)


def _fill(text: str, values: dict) -> str:
    """Replace %%name%% placeholders."""
    for name, value in values.items():
        text = text.replace(f"%%{name}%%", str(value))
    return text


def render_templates(config: Config) -> tuple[str, str, str]:
    """Read templates/ and return (front, back, css) ready for Anki."""
    folder = config.templates_dir
    try:
        front = (folder / "front.html").read_text(encoding="utf-8")
        back = (folder / "back.html").read_text(encoding="utf-8")
        css = (folder / "style.css").read_text(encoding="utf-8")
        script = (folder / "strokes.js").read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise BuildError(f"Template file not found: {error.filename}") from error

    # Anki would read "{{" in the script as a field tag, so it must not appear.
    if "{{" in script:
        raise BuildError("templates/strokes.js must not contain '{{' (Anki reads it as a field tag)")

    animation_json = json.dumps(config.animation)
    script = _fill(script, {"ANIMATION": animation_json})
    back = _fill(back, {"STROKES_JS": script})
    css = _fill(css, config.colors)

    for name, text in (("back.html", back), ("style.css", css)):
        leftover = re.findall(r"%%\w+%%", text)
        if leftover:
            raise BuildError(f"Unknown placeholder in templates/{name}: {leftover[0]}")

    return front, back, css


def make_model(config: Config) -> genanki.Model:
    front, back, css = render_templates(config)
    return genanki.Model(
        config.model_id,
        "Hanzi Strokes",
        fields=[
            {"name": "Hanzi"},
            {"name": "Pinyin"},
            {"name": "Meaning"},
            {"name": "Audio"},
            {"name": "Strokes"},
        ],
        templates=[{"name": "Card 1", "qfmt": front, "afmt": back}],
        css=css,
    )


def build_deck(config: Config, subdeck: Subdeck) -> BuildResult:
    """Read the input files, build the subdeck and write config.output."""
    if not config.words.is_file():
        raise BuildError(f"Words file not found: {config.words}")
    if not config.hanzi_writer_js.is_file():
        raise BuildError(f"Hanzi Writer script not found: {config.hanzi_writer_js}")

    all_data = load_all_json(config.all_json)
    entries, warnings = parse_words(config.words)

    model = make_model(config)
    title = deck_title(config.parent_deck, subdeck)
    deck = genanki.Deck(deck_id_for(title), title)
    result = BuildResult(output=config.output, deck_title=title, warnings=warnings)
    audio_files: dict[str, Path] = {}  # media name -> path on disk

    for entry in entries:
        note = _make_note(entry, subdeck, model, all_data, config, result, audio_files)
        deck.add_note(note)
        result.entries_built += 1

    _write_package(deck, config, audio_files)
    return result


def _make_note(entry: Entry, subdeck: Subdeck, model, all_data, config, result, audio_files) -> genanki.Note:
    chars = split_characters(entry.hanzi)
    if not chars:
        result.warnings.append(
            f"words line {entry.line_number}: '{entry.hanzi}' has no Chinese characters, "
            "so it will have no animation"
        )
    strokes_json, missing = build_strokes_json(chars, all_data)

    for ch in dict.fromkeys(chars):  # unique characters, in order
        if ch in missing:
            if ch not in result.characters_missing:
                result.characters_missing.append(ch)
                result.warnings.append(
                    f"words line {entry.line_number}: character '{ch}' not found in all.json"
                )
        else:
            result.characters_found.add(ch)

    audio_field = ""
    if entry.audio:
        path = find_audio(entry.audio, config.audio_dir)
        if path is None:
            result.missing_audio.append((entry.hanzi, entry.audio))
            result.warnings.append(
                f"words line {entry.line_number}: audio file '{entry.audio}' not found "
                f"in {config.audio_dir}"
            )
        else:
            audio_files[media_name(entry.audio)] = path
            audio_field = sound_tag(entry.audio)

    fields = [
        html.escape(entry.hanzi),
        html.escape(entry.pinyin),
        html.escape(entry.meaning),
        audio_field,
        # Escaped so the JSON is safe inside the HTML field; the card reads it with textContent.
        html.escape(strokes_json),
    ]
    return genanki.Note(model=model, fields=fields, guid=note_guid(subdeck.key, entry.hanzi))


def _write_package(deck: genanki.Deck, config: Config, audio_files: dict) -> None:
    """genanki takes media names from file names, so copy everything into a
    temporary folder under the final names first."""
    config.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_folder = Path(tmp)
        media_paths = []

        script_copy = tmp_folder / HANZI_WRITER_MEDIA_NAME
        shutil.copyfile(config.hanzi_writer_js, script_copy)
        media_paths.append(str(script_copy))

        for name, source in audio_files.items():
            target = tmp_folder / name
            shutil.copyfile(source, target)
            media_paths.append(str(target))

        package = genanki.Package(deck)
        package.media_files = media_paths
        package.write_to_file(str(config.output))
