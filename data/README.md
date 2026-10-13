# data/

Put `all.json` here. It is **not committed** to git (see `.gitignore`).

`all.json` is one JSON object keyed by character. Each entry has `strokes`, `medians`
and `radStrokes` (the Hanzi Writer data format), for example the key `"懂"`.

## Where to get the data

The data comes from [Make Me a Hanzi](https://github.com/skishore/makemeahanzi), prepared for
Hanzi Writer in [hanzi-writer-data](https://github.com/chanind/hanzi-writer-data).
That package contains one file per character (for example `懂.json`), so you need to merge
the files into one `all.json`:

1. Get the package files, for example: `npm pack hanzi-writer-data`, then unpack the `.tgz`.
2. Run this from the project folder (change `SOURCE` to the unpacked `package` folder):

```python
import json
from pathlib import Path

SOURCE = Path("path/to/package")  # folder with 懂.json, 你.json, ...
data = {}
for file in SOURCE.glob("*.json"):
    if file.name != "package.json":
        data[file.stem] = json.loads(file.read_text(encoding="utf-8"))

Path("data/all.json").write_text(
    json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
)
print(len(data), "characters written")
```

Version 2.0.1 of the package gave about 9,570 characters (a file of about 30 MB).

## License

The data has a mixed license (Arphic Public License and LGPL). Read `ARPHICPL.TXT` in the package and
the license notes in the Make Me a Hanzi repository before you redistribute it.
