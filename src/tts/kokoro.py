# Imports

# > Standard Library
import random
from typing import Tuple

# > Third-party Libraries
import numpy as np
from kokoro import KPipeline

# > Local Dependencies
from src.utils import setup_logger
from src.config import SAMPLE_RATE, TTS_SPEED
from .base import TTSBackend

log = setup_logger(__name__)


class KokoroBackend(TTSBackend):
    """
    Standard CPU-based TTS Backend using the Kokoro model.
    Good for users without powerful NVIDIA GPUs.

    Attributes
    ----------
    pipeline : KPipeline
        The loaded Kokoro inference pipeline.
    samplerate : int
        Audio sample rate (24000 Hz).
    backend_id : str
        Identifier for the backend ('kokoro').
    """

    # Voice mapping constants
    VOICES = {
        "man male": [
            "am_echo",
            "am_eric",
            "am_fenrir",
            "am_liam",
            "am_onyx",
            "am_puck",
            "am_santa",
            "am_michael",
        ],
        "elf male": ["am_onyx", "am_puck"],
        "dwarf male": ["bm_daniel", "am_santa", "am_michael"],
        "hobbit male": ["bm_fable", "bm_george", "bm_lewis"],
        "man female": ["af_alloy", "af_aoede", "af_heart", "af_jessica"],
        "elf female": ["af_bella", "af_kore", "af_nova"],
        "dwarf female": ["af_river", "af_sarah"],
        "hobbit female": ["af_sky", "bf_alice", "bf_emma", "bf_isabella", "bf_lily"],
    }

    RACE_MAP = {
        "Men": "man",
        "Man": "man",
        "Human": "man",
        "Beorning": "man",
        "Elf": "elf",
        "High Elf": "elf",
        "Dwarf": "dwarf",
        "Stout-axe": "dwarf",
        "Hobbit": "hobbit",
        "River Hobbit": "hobbit",
    }

    def __init__(self):
        """
        Initializes the Kokoro pipeline on the CPU.
        """
        log.info("Loading Kokoro Voice Model...")
        try:
            self.backend_id = "kokoro"  # Explicit ID for memory separation
            self.pipeline = KPipeline(lang_code="a", device="cpu")
            self.samplerate = SAMPLE_RATE
            log.info("✅ Voice Model Ready (CPU Mode).")
        except Exception as e:
            log.error(f"Failed to initialize Kokoro: {e}")
            raise

    def pick_voice(self, gender: str, race: str) -> Tuple[str, str]:
        """
        Selects a predefined Kokoro voice profile based on race and gender.
        """
        g_clean = (gender or "male").lower().strip()
        r_clean = (race or "man").strip()

        r_key = self.RACE_MAP.get(r_clean, "man")

        if "narrator" in r_clean.lower() or "narrator" in g_clean.lower():
            return "am_echo", "narrator"

        key = f"{r_key} {g_clean}"

        if key in self.VOICES:
            voice = random.choice(self.VOICES[key])
            return voice, key

        return "am_echo", "fallback"

    def generate(self, text: str, voice_id: str) -> np.ndarray:
        """
        Generates audio using Kokoro.
        """
        generator = self.pipeline(text, voice=voice_id, speed=TTS_SPEED, split_pattern=r"\n+")

        chunks = [audio for _, _, audio in generator if audio is not None]

        if chunks:
            return np.concatenate(chunks).astype(np.float32)

        return np.array([], dtype=np.float32)