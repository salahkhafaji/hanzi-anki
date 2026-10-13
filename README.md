# hanzi-anki

Turn a text file of Chinese words and sentences into an Anki `.apkg` deck with
offline stroke-order animation, pinyin, meaning and audio.

## Usage

    uv run hanzi-anki build

1. Put `all.json` in `data/` (see `data/README.md`).
2. Put your audio files in `input/audio/`.
3. Write entries in `input/words.txt`: `hanzi | pinyin | meaning | audio_file`
4. Run the command, then import `output/hanzi.apkg` into Anki.

## Customize

- Card layout: `templates/`
- Colors and animation speed: `config.toml`

## Credits

- Hanzi Writer (MIT): https://hanziwriter.org
- Stroke data: Make Me a Hanzi (see its license)
