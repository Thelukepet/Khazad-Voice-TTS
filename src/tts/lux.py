# Imports

# > Standard Library
import sys
import re
import random
import time
from pathlib import Path
from typing import Tuple, Dict, List

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
    """

    def __init__(self):
        """
        Initializes the LuxTTS model on the GPU and loads the voice library.
        """
        log.info(f"Loading LuxTTS Model on {DEVICE}...")

        project_root = Path(__file__).resolve().parent.parent.parent
        lux_path = project_root / "LuxTTS"

        if lux_path.exists() and str(lux_path) not in sys.path:
            sys.path.append(str(lux_path))

        try:
            try:
                from zipvoice.luxvoice import LuxTTS
            except ImportError:
                from LuxTTS.zipvoice.luxvoice import LuxTTS
        except ImportError as e:
            raise ImportError(
                f"Could not import LuxTTS. Checked '{lux_path}'. Error: {e}"
            )

        self.backend_id = "lux"  # Explicit ID for memory separation
        self.tts = LuxTTS("YatharthS/LuxTTS", device="cuda")
        self.samplerate = 48000
        self.voice_library = self._load_voice_library()
        self.prompt_cache = {}

        total_voices = sum(len(v) for v in self.voice_library.values())
        log.info(f"✅ LuxTTS Ready. Loaded {total_voices} reference voices.")

        self._warmup()

    def _warmup(self):
        """
        Runs a short, silent generation to compile PyTorch CUDA graphs.
        """
        log.info("🔥 Warming up LuxTTS (takes ~10s for first run)...")
        try:
            if "narrator" in self.voice_library:
                voice_id = "narrator|0"
            elif self.voice_library:
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

    def _read_clean_lines(self, txt_path: Path) -> List[str]:
        if not txt_path.exists():
            return []
        with open(txt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return [re.sub(r"\"", "", line).strip() for line in lines if line.strip()]

    def _load_voice_library(self) -> Dict:
        library = {}
        if not REF_AUDIO_DIR.exists():
            log.warning(f"Reference Audio dir not found: {REF_AUDIO_DIR}")
            return library

        for folder in REF_AUDIO_DIR.iterdir():
            if not folder.is_dir():
                continue

            category = folder.name.lower()
            library[category] = []

            flac_lines = self._read_clean_lines(folder / f"{category}.txt")
            wav_lines = self._read_clean_lines(folder / f"{category}_wav.txt")

            def add_voices(pattern, fallback_lines):
                files = sorted(list(folder.glob(pattern)), key=lambda x: x.name)
                for i, fpath in enumerate(files):
                    transcript = None
                    sidecar_path = fpath.with_suffix(".txt")
                    if sidecar_path.exists():
                        try:
                            raw_text = sidecar_path.read_text(encoding="utf-8").strip()
                            clean_text = re.sub(r"[\"\n]", " ", raw_text).strip()
                            if len(clean_text) > 1:
                                transcript = clean_text
                        except Exception:
                            pass

                    if not transcript and fallback_lines:
                        if i < len(fallback_lines):
                            transcript = fallback_lines[i]
                        else:
                            transcript = fallback_lines[0]

                    if transcript:
                        library[category].append(
                            {
                                "id": len(library[category]),
                                "text": transcript,
                                "audio": str(fpath),
                                "type": fpath.suffix.lower().replace(".", ""),
                            }
                        )

            add_voices("*.flac", flac_lines)
            add_voices("*.wav", wav_lines)

        return library

    def pick_voice(self, gender: str, race: str) -> Tuple[str, str]:
        g_clean = (gender or "").lower().strip()
        r_clean = (race or "").lower().strip()

        if "narrator" in r_clean or "narrator" in g_clean:
            key = "narrator"
        else:
            key = f"{r_clean}_{g_clean}"

        if key not in self.voice_library or not self.voice_library[key]:
            if "narrator" in self.voice_library and self.voice_library["narrator"]:
                key = "narrator"
            else:
                return "default", "fallback"

        sample = random.choice(self.voice_library[key])
        voice_id = f"{key}|{sample['id']}"
        return voice_id, key

    def generate(self, text: str, voice_id: str, warmup: bool = False) -> np.ndarray:
        if "|" not in voice_id:
            return np.array([], dtype=np.float32)

        category, idx_str = voice_id.split("|")
        try:
            idx = int(idx_str)
            ref_data = self.voice_library[category][idx]
        except (ValueError, IndexError, KeyError):
            log.error(f"Invalid voice_id: {voice_id}")
            return np.array([], dtype=np.float32)

        if not warmup:
            log.info(f"🎙️ Cloning [{category}] (Source: {Path(ref_data['audio']).name})...")

        try:
            if voice_id in self.prompt_cache:
                encoded_prompt = self.prompt_cache[voice_id]
            else:
                encoded_prompt = self.tts.encode_prompt(
                    ref_data["audio"],
                    text=ref_data["text"],
                    rms=0.01,
                    duration=1000
                )
                self.prompt_cache[voice_id] = encoded_prompt

            wav_tensor = self.tts.generate_speech(
                text,
                encoded_prompt,
                num_steps=TTS_WAVE_STEPS,
                speed=TTS_SPEED,
                t_shift=0.9
            )

            if hasattr(wav_tensor, "detach"):
                wav = wav_tensor.detach().cpu().numpy().squeeze()
            else:
                wav = wav_tensor.numpy().squeeze()

            return wav.astype(np.float32)

        except Exception as e:
            log.error(f"Generation failed: {e}")
            return np.array([], dtype=np.float32)