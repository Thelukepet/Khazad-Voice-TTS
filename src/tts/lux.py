# Imports

# > Standard Library
import sys
import re
import random
import time
from pathlib import Path

# > Third-party Libraries
import numpy as np

# > Local Dependencies
from src.utils import setup_logger
from src.config import DEVICE, REF_AUDIO_DIR, TTS_SPEED, TTS_WAVE_STEPS
from .base import TTSBackend

log = setup_logger(__name__)


class LuxBackend(TTSBackend):
    """
    High-quality Voice Cloning Backend using LuxTTS (GPU only).
    Requires a 'LuxTTS' folder in the project root.

    Attributes
    ----------
    tts : LuxTTS
        The LuxTTS model instance.
    voice_library : dict
        A dictionary mapping categories (e.g. 'elf_male') to lists of reference audio files.
    samplerate : int
        Audio sample rate (48000 Hz for LuxTTS).
    """

    def __init__(self):
        """
        Initializes the LuxTTS model on the GPU and loads the voice library.

        Raises
        ------
        ImportError
            If the LuxTTS submodule is missing or cannot be imported.
        """
        log.info(f"Loading LuxTTS Model on {DEVICE}...")

        # --- Import Logic Fix ---
        # Navigate up from src/tts/lux.py -> src/tts -> src -> root
        project_root = Path(__file__).resolve().parent.parent.parent
        lux_path = project_root / "LuxTTS"

        if lux_path.exists() and str(lux_path) not in sys.path:
            sys.path.append(str(lux_path))

        try:
            # Try direct import first, then fallback to folder structure import
            try:
                from zipvoice.luxvoice import LuxTTS
            except ImportError:
                from LuxTTS.zipvoice.luxvoice import LuxTTS
        except ImportError as e:
            raise ImportError(
                f"Could not import LuxTTS. Checked '{lux_path}'. Error: {e}"
            )

        self.tts = LuxTTS("YatharthS/LuxTTS", device="cuda")
        self.samplerate = 48000
        self.voice_library = self._load_voice_library()

        total_voices = sum(len(v) for v in self.voice_library.values())
        log.info(f"✅ LuxTTS Ready. Loaded {total_voices} reference voices.")

        self._warmup()

    def _warmup(self):
        """
        Runs a short, silent generation to compile PyTorch CUDA graphs.
        This prevents lag on the very first generation.
        """
        log.info("🔥 Warming up LuxTTS (takes ~10s for first run)...")
        try:
            if "narrator" in self.voice_library:
                voice_id = "narrator|0"
            elif self.voice_library:
                # Pick the first available voice
                first_cat = list(self.voice_library.keys())[0]
                voice_id = f"{first_cat}|0"
            else:
                log.warning("⚠️ No voices found for warmup.")
                return

            t0 = time.time()
            self.generate("Warmup.", voice_id, warmup=True)
            t1 = time.time()
            log.info(f"🔥 Warmup Complete in {t1 - t0:.2f}s.")
        except Exception as e:
            log.warning(f"⚠️ Warmup failed (non-critical): {e}")

    def _read_clean_lines(self, txt_path: Path) -> list[str]:
        """
        Reads a text file and removes quotes and whitespace.

        Parameters
        ----------
        txt_path : Path
            Path to the text file.

        Returns
        -------
        list[str]
            List of cleaned lines from the file.
        """
        if not txt_path.exists():
            return []

        with open(txt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        return [re.sub(r"\"", "", line).strip() for line in lines if line.strip()]

    def _load_voice_library(self) -> dict:
        """
        Scans the 'data/reference_audio' directory for .wav/.flac files and transcripts.

        Returns
        -------
        dict
            Structure: { 'category': [ {'id': 0, 'audio': path, 'text': transcript}, ... ] }
        """
        library = {}
        if not REF_AUDIO_DIR.exists():
            log.warning(f"Reference Audio dir not found: {REF_AUDIO_DIR}")
            return library

        for folder in REF_AUDIO_DIR.iterdir():
            if not folder.is_dir():
                continue

            category = folder.name.lower()
            library[category] = []

            # Load transcripts
            flac_lines = self._read_clean_lines(folder / f"{category}.txt")
            wav_lines = self._read_clean_lines(folder / f"{category}_wav.txt")

            # Process FLACs
            flacs = sorted(list(folder.glob("*.flac")), key=lambda x: x.name)
            for i, fpath in enumerate(flacs):
                if not flac_lines:
                    continue
                text = flac_lines[i] if i < len(flac_lines) else flac_lines[0]
                library[category].append(
                    {
                        "id": len(library[category]),
                        "text": text,
                        "audio": str(fpath),
                        "type": "flac",
                    }
                )

            # Process WAVs
            wavs = sorted(list(folder.glob("*.wav")), key=lambda x: x.name)
            for i, fpath in enumerate(wavs):
                if not wav_lines:
                    continue
                text = wav_lines[i] if i < len(wav_lines) else wav_lines[0]
                library[category].append(
                    {
                        "id": len(library[category]),
                        "text": text,
                        "audio": str(fpath),
                        "type": "wav",
                    }
                )

        return library

    def pick_voice(self, gender: str, race: str) -> tuple[str, str]:
        """
        Selects a reference audio file for voice cloning.

        Parameters
        ----------
        gender : str
            NPC gender.
        race : str
            NPC race.

        Returns
        -------
        tuple[str, str]
            (voice_id, category_key). voice_id format is 'category|index'.
        """
        g_clean = (gender or "").lower().strip()
        r_clean = (race or "").lower().strip()

        # Construct category key (e.g., 'dwarf_male')
        if "narrator" in r_clean or "narrator" in g_clean:
            key = "narrator"
        else:
            key = f"{r_clean}_{g_clean}"

        # Fallback logic
        if key not in self.voice_library or not self.voice_library[key]:
            if "narrator" in self.voice_library and self.voice_library["narrator"]:
                key = "narrator"
            else:
                return "default", "fallback"

        # Pick a random sample from the category for variety
        sample = random.choice(self.voice_library[key])
        voice_id = f"{key}|{sample['id']}"

        return voice_id, key

    def generate(self, text: str, voice_id: str, warmup: bool = False) -> np.ndarray:
        """
        Clones the reference voice to speak the given text.

        Parameters
        ----------
        text : str
            Text to speak.
        voice_id : str
            Format: 'category|index' (e.g., 'elf_female|3').
        warmup : bool, optional
            If True, suppresses log output.

        Returns
        -------
        np.ndarray
            Audio waveform.
        """
        if "|" not in voice_id:
            return np.array([], dtype=np.float32)

        category, idx_str = voice_id.split("|")
        try:
            idx = int(idx_str)
            ref_data = self.voice_library[category][idx]
        except (ValueError, IndexError, KeyError):
            log.error(f"Invalid voice_id: {voice_id}")
            return np.array([], dtype=np.float32)

        ref_audio = ref_data["audio"]
        ref_text = ref_data["text"]

        if not warmup:
            log.info(
                f"🎙️ Cloning [{category}] (Source: {Path(ref_audio).name}): {text[:50]}..."
            )

        try:
            # Encode the reference audio for style transfer
            encoded_prompt = self.tts.encode_prompt(
                ref_audio, text=ref_text, rms=0.01, duration=1000
            )

            # Generate speech
            wav_tensor = self.tts.generate_speech(
                text,
                encoded_prompt,
                num_steps=TTS_WAVE_STEPS,
                speed=TTS_SPEED,
                t_shift=0.9
            )

            # Handle Tensor vs Numpy array
            if hasattr(wav_tensor, "detach"):
                wav = wav_tensor.detach().cpu().numpy().squeeze()
            else:
                wav = wav_tensor.numpy().squeeze()

            return wav.astype(np.float32)

        except Exception as e:
            log.error(f"Generation failed: {e}")
            return np.array([], dtype=np.float32)
