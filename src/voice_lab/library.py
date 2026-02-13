# Imports

# > Standard Library
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional, Dict

# > Third-party Libraries
import soundfile as sf

# --- CONFIGURATION ---
AUDIO_DIR = Path("data/reference_audio")
VOICE_LIBRARY = {}


def read_clean_lines(txt_path: Path) -> List[str]:
    """
    Reads lines from a text file, removing quotes and extraneous whitespace.

    Parameters
    ----------
    txt_path : Path
        The path to the text file to read.

    Returns
    -------
    List[str]
        A list of cleaned string lines. Returns an empty list if file not found
        or an error occurs.
    """
    if not txt_path.exists():
        return []
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return [re.sub(r"\"", "", line).strip() for line in lines if line.strip()]
    except Exception as e:
        print(f"Error reading {txt_path}: {e}")
        return []


def refresh_library() -> None:
    """
    Scans the Reference Audio directory and builds the library cache.
    Replicates the exact matching logic from src/tts/lux.py.

    Populates the global VOICE_LIBRARY dictionary with structure:
    { 'category': [ {'name': filename, 'path': fullpath, 'text': transcript}, ... ] }
    """
    global VOICE_LIBRARY
    VOICE_LIBRARY = {}

    if not AUDIO_DIR.exists():
        return

    for folder in AUDIO_DIR.iterdir():
        if not folder.is_dir():
            continue

        category = folder.name
        samples = []

        # Load Legacy Bulk Transcripts
        flac_lines = read_clean_lines(folder / f"{category}.txt")
        wav_lines = read_clean_lines(folder / f"{category}_wav.txt")

        def add_voices(pattern: str, fallback_lines: List[str]):
            files = sorted(list(folder.glob(pattern)), key=lambda x: x.name)
            for i, fpath in enumerate(files):
                transcript = None

                # 1. Check for specific sidecar .txt file (Priority)
                sidecar_path = fpath.with_suffix(".txt")
                if sidecar_path.exists():
                    try:
                        raw_text = sidecar_path.read_text(encoding="utf-8").strip()
                        # Clean quotes and newlines
                        clean_text = re.sub(r"[\"\n]", " ", raw_text).strip()
                        if len(clean_text) > 1:
                            transcript = clean_text
                    except Exception:
                        pass

                # 2. Fallback to bulk list
                if not transcript and fallback_lines:
                    if i < len(fallback_lines):
                        transcript = fallback_lines[i]
                    else:
                        transcript = fallback_lines[0]

                # 3. Add to library if we found text
                if transcript:
                    samples.append({
                        "name": fpath.name,
                        "path": str(fpath),
                        "text": transcript
                    })

        add_voices("*.flac", flac_lines)
        add_voices("*.wav", wav_lines)

        if samples:
            VOICE_LIBRARY[category] = samples


def get_library_categories() -> List[str]:
    """
    Retrieves a list of available voice categories.

    Returns
    -------
    List[str]
        Keys of the VOICE_LIBRARY dictionary (e.g., 'dwarf_male').
    """
    return list(VOICE_LIBRARY.keys())


def get_samples_for_category(category: str) -> List[str]:
    """
    Retrieves the list of audio filenames for a specific category.

    Parameters
    ----------
    category : str
        The voice category name.

    Returns
    -------
    List[str]
        List of filenames (e.g., 'dwarf_male_1.flac').
    """
    if category not in VOICE_LIBRARY:
        return []
    return [s["name"] for s in VOICE_LIBRARY[category]]


def load_library_sample(category: str, sample_name: str) -> Tuple[Optional[str], str]:
    """
    Returns the file path and transcript for a selected library file.

    Parameters
    ----------
    category : str
        The voice category.
    sample_name : str
        The filename of the sample.

    Returns
    -------
    tuple
        (file_path, transcript_text). Returns (None, "") if not found.
    """
    if category not in VOICE_LIBRARY:
        return None, ""

    for sample in VOICE_LIBRARY[category]:
        if sample["name"] == sample_name:
            return sample["path"], sample["text"]
    return None, ""


def trim_audio(audio_path: str, max_duration: float = 20.0) -> Optional[str]:
    """
    Checks audio duration and trims it if it exceeds the limit.

    Parameters
    ----------
    audio_path : str
        Path to the source audio file.
    max_duration : float
        Maximum allowed duration in seconds.

    Returns
    -------
    str
        Path to the original or trimmed audio file (temp file if trimmed).
    """
    if not audio_path:
        return None
    try:
        data, sr = sf.read(audio_path)
        duration = len(data) / sr
        if duration > max_duration:
            print(f"Trimming audio: {duration:.2f}s -> {max_duration}s")
            max_samples = int(max_duration * sr)
            fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            sf.write(tmp_path, data[:max_samples], sr)
            return tmp_path
        return audio_path
    except:
        return audio_path


def save_voice(ref_audio: str, folder_name: str, voice_name: str, transcript: str) -> str:
    """
    Saves a new voice sample to the library.

    Processing steps:
    1. Trims the audio to 20 seconds.
    2. Converts/Saves as WAV.
    3. Saves the transcript as a sidecar text file (file_name.txt).
    4. Refreshes the library cache.

    Parameters
    ----------
    ref_audio : str
        Path to the uploaded/recorded audio file.
    folder_name : str
        The category folder name (e.g., 'high_elf_female').
    voice_name : str
        The unique name for this voice sample.
    transcript : str
        The text content spoken in the audio.

    Returns
    -------
    str
        Status message indicating success or failure.
    """
    if not ref_audio or not voice_name:
        return "Missing info."

    clean_name = "".join(c for c in voice_name if c.isalnum() or c in (' ', '_')).strip().replace(" ", "_").lower()
    target_dir = AUDIO_DIR / folder_name

    try:
        os.makedirs(target_dir, exist_ok=True)
        target_wav = target_dir / f"{clean_name}.wav"

        # 1. Load Audio
        data, sr = sf.read(ref_audio)

        # 2. Trim to 20s Max
        max_samples = int(20.0 * sr)
        if len(data) > max_samples:
            data = data[:max_samples]

        # 3. Write as WAV (Safe format conversion)
        sf.write(target_wav, data, sr)

        # 4. Save Sidecar Transcript
        if transcript:
            txt_path = target_dir / f"{clean_name}.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(transcript)

        refresh_library()
        return f"Saved to {folder_name}/{clean_name}"
    except Exception as e:
        return f"Error: {e}"


def get_voice_folders() -> List[str]:
    """
    Returns a list of directory names in the audio folder.

    Returns
    -------
    List[str]
        List of folder names.
    """
    if not AUDIO_DIR.exists():
        return []
    return [d.name for d in AUDIO_DIR.iterdir() if d.is_dir()]


# Initialize cache on module load
refresh_library()