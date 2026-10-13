"""Find audio files and name them inside the .apkg."""

from pathlib import Path

# Added in front of every audio file name inside the .apkg, so your files cannot
# clash with media from other Anki decks. It is applied in one place only.
AUDIO_PREFIX = "hanzi_"


def media_name(audio_file: str) -> str:
    """Name of the audio file inside Anki's media folder."""
    return AUDIO_PREFIX + audio_file


def find_audio(audio_file: str, audio_dir: Path) -> Path | None:
    """Return the path of the audio file, or None if the field is empty or the
    file does not exist. The name must match exactly, including .mp3."""
    if not audio_file:
        return None
    path = Path(audio_dir) / audio_file
    return path if path.is_file() else None


def sound_tag(audio_file: str) -> str:
    """The text for the Audio field, for example [sound:hanzi_ni-hao.mp3]."""
    return f"[sound:{media_name(audio_file)}]"
