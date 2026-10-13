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
uv run hanzi-anki build
```

The result is `output/hanzi.apkg`. In Anki use **File → Import**, or open the file on your phone.
To use another config file: `uv run hanzi-anki build --config path/to/config.toml`.

After each build you get a short summary: entries built, characters found,
missing characters and missing audio.

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
- If the same hanzi appears twice, the later line replaces the earlier one.

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
| Colors, animation size and speed, deck name | `config.toml` |

Colors live only in `config.toml`. Night mode uses `stroke_night` and `outline_night`.
Templates use `%%name%%` placeholders that the build fills in from `config.toml`.
Do not write `{{` in `strokes.js`: Anki reads it as a field tag.

## Re-importing

`deck_id` and `model_id` in `config.toml` are fixed, and each note's GUID is made from its hanzi text.
So when you import a new build, Anki updates existing cards instead of duplicating them.
You can fix pinyin or meaning and import again. Do not change `deck_id` or `model_id`.
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
