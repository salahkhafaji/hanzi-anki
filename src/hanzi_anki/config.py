"""Read config.toml into a simple Config object."""

import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(Exception):
    """Raised when config.toml is missing or incomplete."""


@dataclass
class Config:
    root: Path  # folder that contains config.toml; all relative paths start here
    parent_deck: str  # existing deck in Anki; the new subdeck goes inside it
    deck_name: str  # default subdeck name
    first_number: int
    model_id: int
    all_json: Path
    words: Path
    audio_dir: Path
    output: Path
    subdecks_file: Path
    animation: dict  # width, height, speed, delay_between_strokes, delay_between_loops
    colors: dict  # stroke, stroke_night, radical, outline, outline_night, highlight
    templates_dir: Path
    hanzi_writer_js: Path


def _section(data: dict, name: str) -> dict:
    if name not in data or not isinstance(data[name], dict):
        raise ConfigError(f"config.toml: missing section [{name}]")
    return data[name]


def _value(section: dict, section_name: str, key: str):
    if key not in section:
        raise ConfigError(f"config.toml: missing '{key}' in [{section_name}]")
    return section[key]


def load_config(config_path: Path) -> Config:
    config_path = Path(config_path)
    if not config_path.is_file():
        raise ConfigError(f"Config file not found: {config_path}")

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    root = config_path.resolve().parent
    deck = _section(data, "deck")
    paths = _section(data, "paths")
    animation = _section(data, "animation")
    colors = _section(data, "colors")

    for key in ("width", "height", "speed", "delay_between_strokes", "delay_between_loops"):
        _value(animation, "animation", key)
    for key in ("stroke", "stroke_night", "radical", "outline", "outline_night", "highlight"):
        _value(colors, "colors", key)

    return Config(
        root=root,
        parent_deck=str(_value(deck, "deck", "parent")).strip(),
        deck_name=_value(deck, "deck", "name"),
        first_number=int(_value(deck, "deck", "first_number")),
        model_id=int(_value(deck, "deck", "model_id")),
        all_json=root / _value(paths, "paths", "all_json"),
        words=root / _value(paths, "paths", "words"),
        audio_dir=root / _value(paths, "paths", "audio_dir"),
        output=root / _value(paths, "paths", "output"),
        subdecks_file=root / _value(paths, "paths", "subdecks"),
        animation=dict(animation),
        colors=dict(colors),
        templates_dir=root / "templates",
        hanzi_writer_js=root / "assets" / "hanzi-writer.min.js",
    )
