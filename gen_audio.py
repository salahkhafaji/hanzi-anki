"""
Generate Mandarin mp3 files for hanzi-anki using edge-tts.

Reads input/words.txt, where each line is:
    hanzi | pinyin | meaning | audio_file.mp3
Speaks the hanzi (column 1) and saves it under the name in column 4.
Existing files are skipped (so your course recordings are kept).

Run from the project root:
    uv run --no-project --python 3.12 --with edge-tts gen_audio.py input/words.txt input/audio

Options:
    --dry-run     show what would be generated, no internet, no files written
    --overwrite   regenerate files even if they exist
    --voice V     default zh-CN-YunxiNeural
    --rate R      default -20%   (both "--rate -20%" and "--rate=-20%" work)

Internet is needed only while generating. The mp3 files then work offline.
"""
import argparse
import asyncio
import pathlib
import sys


def fix_rate_arg(argv):
    """Let '--rate -20%' work by turning it into '--rate=-20%'."""
    out, i = [], 0
    while i < len(argv):
        if argv[i] == "--rate" and i + 1 < len(argv):
            out.append(f"--rate={argv[i + 1]}")
            i += 2
        else:
            out.append(argv[i])
            i += 1
    return out


def parse_line(line):
    """Return (hanzi, audio_file) or None if the line should be ignored."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    cols = [c.strip() for c in line.split("|")]
    hanzi = cols[0]
    audio = cols[3] if len(cols) >= 4 else ""
    return hanzi, audio


async def make_one(text, out_path, voice, rate, retries=3):
    import edge_tts

    for attempt in range(1, retries + 1):
        try:
            await edge_tts.Communicate(text, voice, rate=rate).save(str(out_path))
            return True
        except Exception as e:
            if attempt == retries:
                print(f"  FAILED: {text!r} ({e})", file=sys.stderr)
                if out_path.exists():
                    out_path.unlink()  # never leave a broken half file
                return False
            await asyncio.sleep(1.5 * attempt)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("words_file")
    ap.add_argument("out_dir")
    ap.add_argument("--voice", default="zh-CN-YunxiNeural")
    ap.add_argument("--rate", default="-20%")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args(fix_rate_arg(sys.argv[1:]))

    out_dir = pathlib.Path(args.out_dir)
    text = pathlib.Path(args.words_file).read_text(encoding="utf-8-sig")

    todo, existing, no_name = [], [], []
    for raw in text.splitlines():
        parsed = parse_line(raw)
        if parsed is None:
            continue
        hanzi, audio = parsed
        if not audio:
            no_name.append(hanzi)
            continue
        out = out_dir / pathlib.Path(audio).name  # no folders, just the file name
        if out.is_file() and out.stat().st_size > 0 and not args.overwrite:
            existing.append(audio)
        else:
            todo.append((hanzi, out))

    print(f"voice={args.voice} rate={args.rate}")
    print(f"to generate: {len(todo)} | already exist (skipped): {len(existing)} "
          f"| no audio file name in column 4: {len(no_name)}")
    for h in no_name:
        print(f"  no name, skipped: {h}")

    if args.dry_run:
        for hanzi, out in todo:
            print(f"  would create {out.name}  <-  {hanzi}")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(args.concurrency)
    results = []

    async def worker(hanzi, out):
        async with sem:
            ok = await make_one(hanzi, out, args.voice, args.rate)
        if ok:
            print(f"ok  {out.name}  <-  {hanzi}")
        results.append(ok)

    await asyncio.gather(*(worker(h, o) for h, o in todo))
    print(f"\nGenerated {sum(results)}, failed {results.count(False)}")


if __name__ == "__main__":
    asyncio.run(main())
