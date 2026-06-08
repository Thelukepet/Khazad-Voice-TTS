"""
Shared voice library loading logic.

Used by both ``omnivoice.py`` and ``voice_lab/library.py`` so that
the directory-scanning + transcript-resolution algorithm is defined once.
"""

# > Standard Library
import re
from pathlib import Path
from typing import Dict, List


def _read_clean_lines(txt_path: Path) -> List[str]:
    """Read lines from a transcript file, stripping quotes and whitespace."""
    if not txt_path.exists():
        return []
    with open(txt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return [re.sub(r"\"", "", line).strip() for line in lines if line.strip()]


def load_voice_library(ref_audio_dir: Path) -> Dict[str, List[Dict]]:
    """Scan *ref_audio_dir* and build the voice library dictionary.

    Directory layout expected::

        ref_audio_dir/
          narrator/
            narrator.txt          <- bulk transcripts (FLAC)
            narrator_wav.txt      <- bulk transcripts (WAV)
            narrator_1.flac
            narrator_1.txt        <- sidecar transcript (priority)
            narrator_2.flac
            quest_narrator.flac
            ...
          dwarf_male/
            dwarf_male.txt
            dwarf_male_1.flac
            ...

    For each audio file the transcript is resolved in this order:

    1. Sidecar ``.txt`` file (same stem as the audio file).
    2. Bulk transcript file by index.

    Returns
    -------
    dict[str, list[dict]]
        ``{ category: [ {id, text, audio, type}, ... ] }``
    """
    library: Dict[str, List[Dict]] = {}
    if not ref_audio_dir.exists():
        return library

    for folder in ref_audio_dir.iterdir():
        if not folder.is_dir():
            continue

        category = folder.name.lower()
        library[category] = []

        flac_lines = _read_clean_lines(folder / f"{category}.txt")
        wav_lines = _read_clean_lines(folder / f"{category}_wav.txt")

        def _add_voices(pattern: str, fallback_lines: List[str]) -> None:
            files = sorted(folder.glob(pattern), key=lambda p: p.name)
            for idx, fpath in enumerate(files):
                transcript = None

                # 1. Sidecar .txt (priority)
                sidecar = fpath.with_suffix(".txt")
                if sidecar.exists():
                    try:
                        raw = sidecar.read_text(encoding="utf-8").strip()
                        clean = re.sub(r"[\"\n]", " ", raw).strip()
                        if len(clean) > 1:
                            transcript = clean
                    except Exception:
                        pass

                # 2. Bulk fallback by index
                if not transcript and fallback_lines:
                    transcript = (
                        fallback_lines[idx]
                        if idx < len(fallback_lines)
                        else fallback_lines[0]
                    )

                if transcript:
                    library[category].append(
                        {
                            "id": len(library[category]),
                            "text": transcript,
                            "audio": str(fpath),
                            "type": fpath.suffix.lower().lstrip("."),
                        }
                    )

        _add_voices("*.flac", flac_lines)
        _add_voices("*.wav", wav_lines)

    return library
