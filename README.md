# hanzi-anki

Turn a text file of Chinese words and sentences into one `.apkg` file for Anki.
Each card shows a stroke-order animation for every Chinese character, plus pinyin,
meaning and audio. It works fully offline, on desktop and on phone.

## Setup

You need [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer.

1. Download `all.json` and put it in `data/` (see [data/README.md](data/README.md)).
2. Put your mp3 files in `input/audio/`.
3. Write your list in `input/words.txt`.

## Build

```bash
uv run hanzi-anki build --name "Greetings"
```

The result is `output/hanzi.apkg`. In Anki use **File → Import**, or open the file on your phone.
If you leave out `--name`, the tool asks for it (press Enter to use `name` from `config.toml`).
To use another config file: `uv run hanzi-anki build --config path/to/config.toml`.

After each build you get a short summary: entries built, characters found,
missing characters and missing audio.

## Window app

```bash
uv run hanzi-anki gui
```

A small window to type the subdeck name, edit the word list, choose audio files and build the deck.

- The name box shows the full deck name and number before you build.
- The table shows every entry. Rows with a missing audio file are red. The order in the table is the order in Anki.
- **Browse...** copies the audio file into `input/audio/` for you.
- **Paste lines...** adds many lines at once in the `words.txt` format.
- **Build deck** saves `input/words.txt` and builds `output/hanzi.apkg`, the same as the command line.
  The previous `words.txt` is kept as `words.txt.bak`. Comment lines (`#`) are not kept when the window saves.
- Mistakes are shown in plain words in the Result box. Unexpected errors are written to
  `hanzi-anki-error.log` next to `config.toml`.

The window needs Tkinter, which comes with Python from uv. The command line does not need it.

## Subdecks

Every build creates one numbered subdeck inside your existing deck, for example
`Chinese Words::03 Greetings`.

- `parent` in `config.toml` is the name of your deck in Anki. It must match exactly,
  including capital letters and spaces, or Anki makes a new deck next to the old one.
- You give the subdeck name with `--name`. The tool puts a number in front of it, so Anki
  (which sorts subdecks by name) shows them in order.
- Numbers are remembered in `data/subdecks.json`. A new name gets the next number. A name you
  used before keeps its number (letter case does not matter), so a rebuild updates the same
  subdeck. Keep this file: if you lose it, the numbering starts again.
- `first_number` in `config.toml` is the number of the very first subdeck.
- A failed build does not use up a number.
- Anki cannot choose the deck at import time. The deck name is stored inside the `.apkg`.

## words.txt format

One entry per line, fields separated by ` | `:

```
hanzi | pinyin | meaning | audio_file
```

```
懂 | dǒng | to understand | dong.mp3
你好吗 | nǐ hǎo ma | are you okay? | ni-hao-ma.mp3
我不懂这个字。 | wǒ bù dǒng zhè ge zì. | I don't understand this character. | wo-bu-dong-zhe-ge-zi.mp3
谢谢 | xièxie | thank you |
```

- An entry can be a character, a word or a sentence. Cards keep the order of the file.
- The audio field may be empty (keep the last `|`, or leave it out).
- Empty lines and lines starting with `#` are ignored.
- Only Chinese characters get an animation. Punctuation, spaces, digits and Latin letters are skipped.
- If the same hanzi appears twice in one file, the later line replaces the earlier one.

## Audio

The name in the 4th field must match a file in `input/audio/` exactly, including `.mp3`.
A missing file gives a warning and the card is built without audio.
Inside the `.apkg` the files are renamed with the prefix `hanzi_` (for example
`hanzi_ni-hao.mp3`) so they cannot clash with media from other decks.
The prefix is the `AUDIO_PREFIX` constant in `src/hanzi_anki/audio.py`.

## Customize

| What | Where |
| --- | --- |
| Card layout | `templates/front.html`, `templates/back.html` |
| Card style | `templates/style.css` |
| Animation code | `templates/strokes.js` |
| Colors, animation size and speed, parent deck | `config.toml` |
| The window app (`hanzi-anki gui`) | `src/hanzi_anki/gui.py` |

Colors live only in `config.toml`. Night mode uses `stroke_night` and `outline_night`.
Templates use `%%name%%` placeholders that the build fills in from `config.toml`.
Do not write `{{` in `strokes.js`: Anki reads it as a field tag.

## Re-importing

`model_id` in `config.toml` is fixed, each subdeck has its own ID made from its full name, and each
note's GUID is made from the subdeck name and the hanzi text. So when you import a new build of the
same subdeck, Anki updates existing cards instead of duplicating them. You can fix pinyin or
meaning and import again. Do not change `model_id` or `parent`.
The same hanzi in a different subdeck is a separate card.
If you change the card templates and Anki still shows the old layout after import, delete
the "Hanzi Strokes" note type's old version or check **Tools → Manage Note Types**.

## How it works

- `assets/hanzi-writer.min.js` is added to the `.apkg` as the media file `_hanzi-writer.min.js`.
- The stroke data of each character is stored in the hidden `Strokes` field of its note as JSON.
  The card passes it to Hanzi Writer with the `charDataLoader` option. There are no network requests.
- Hanzi Writer's `radicalColor` highlights the radical. The data marks only one radical per character.
- A character missing from `all.json` is shown as plain text on the card, and reported in the summary.

## Tests

```bash
uv run pytest
```

## Licenses and credits

- This project: see [LICENSE](LICENSE).
- [Hanzi Writer](https://hanziwriter.org/) is MIT licensed. Its script is included in `assets/`
  together with its license (`assets/hanzi-writer.LICENSE`).
- The stroke data (`all.json`) comes from [Make Me a Hanzi](https://github.com/skishore/makemeahanzi)
  and is **not** included in this repository. It has a mixed license (Arphic Public License and
  LGPL for different parts). Read their license notes before you share `.apkg` files that contain it.
