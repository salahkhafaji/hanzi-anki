"""Command line: uv run hanzi-anki build"""

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .deck import BuildError, BuildResult, build_deck
from .strokes import StrokeDataError


def print_summary(result: BuildResult) -> None:
    for warning in result.warnings:
        print(f"Warning: {warning}")
    if result.warnings:
        print()

    print("Build summary")
    print(f"  Entries built:      {result.entries_built}")
    print(f"  Characters found:   {len(result.characters_found)} (different characters)")

    if result.characters_missing:
        print(f"  Missing characters: {len(result.characters_missing)}  {' '.join(result.characters_missing)}")
    else:
        print("  Missing characters: 0")

    if result.missing_audio:
        print(f"  Missing audio:      {len(result.missing_audio)}")
        for hanzi, file_name in result.missing_audio:
            print(f"    {hanzi}  ->  {file_name}")
    else:
        print("  Missing audio:      0")

    print(f"  Output: {result.output}")


def main() -> None:
    # Git Bash on Windows may not use UTF-8 for printing; this avoids crashes on Chinese text.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="hanzi-anki", description="Build an Anki deck for Chinese study.")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="read the words file and write the .apkg file")
    build.add_argument("--config", default="config.toml", help="path to config.toml (default: config.toml)")
    args = parser.parse_args()

    try:
        config = load_config(Path(args.config))
        result = build_deck(config)
    except (ConfigError, BuildError, StrokeDataError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    print_summary(result)
