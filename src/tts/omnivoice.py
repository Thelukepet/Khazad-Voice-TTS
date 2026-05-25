# Imports

# > Standard Library
import random
import re
import time
from pathlib import Path
from typing import Dict, List, Tuple

# > Third-party Libraries
import numpy as np
import torch

from src.config.ConfigManager import ConfigManager

# > Local Dependencies
from src.utils import setup_logger

from .base import TTSBackend

log = setup_logger(__name__)


class OmniVoiceBackend(TTSBackend):
    """
    High-quality Voice Cloning Backend using OmniVoice (GPU only).
    """

    def __init__(self):
        """
        Initializes the OmniVoice model on the GPU and loads the voice library.
        """
        log.info("Loading OmniVoice Model on cuda:0...")

        from omnivoice import OmniVoice

        self.backend_id = "omnivoice"
        self.tts = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice",
            device_map="cuda:0",
            dtype=torch.float16,
        )
        self.samplerate = 24000
        _cfg = ConfigManager()
        self._ref_audio_dir = Path(_cfg.get_str("Paths", "ref_audio_dir"))
        self._tts_speed = _cfg.get_float("TTSSettings", "tts_speed", fallback=1.1)
        self._tts_wave_steps = _cfg.get_int(
            "TTSSettings", "tts_wave_steps", fallback=16
        )
        self.voice_library = self._load_voice_library()

        total_voices = sum(len(v) for v in self.voice_library.values())
        log.info(f"OmniVoice ready. Loaded {total_voices} reference voices.")

        self._warmup()

    def _warmup(self):
        """
        Runs a short, silent generation to compile PyTorch CUDA graphs.
        """
        log.info("Warming up OmniVoice (takes ~10s for first run)...")
        try:
            if "narrator" in self.voice_library:
                voice_id = "narrator|0"
            elif self.voice_library:
                first_cat = list(self.voice_library.keys())[0]
                voice_id = f"{first_cat}|0"
            else:
                log.warning("No voices found for warmup.")
                return

            t0 = time.time()
            self.generate("Warmup.", voice_id, warmup=True)
            t1 = time.time()
            log.info(f"Warmup complete in {t1 - t0:.2f}s.")
        except Exception as e:
            log.warning(f"Warmup failed (non-critical): {e}")

    def _read_clean_lines(self, txt_path: Path) -> List[str]:
        if not txt_path.exists():
            return []
        with open(txt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return [re.sub(r"\"", "", line).strip() for line in lines if line.strip()]

    def _load_voice_library(self) -> Dict:
        library = {}
        if not self._ref_audio_dir.exists():
            log.warning(f"Reference Audio dir not found: {self._ref_audio_dir}")
            return library

        for folder in self._ref_audio_dir.iterdir():
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

    def pick_narrator_voice(self) -> Tuple[str, str]:
        """
        Returns the dedicated narrator voice (narrator_3.flac).

        Falls back to any available narrator voice, or "default" if none exist.

        Returns
        -------
        tuple[str, str]
            (voice_id, category) for the narrator voice.
        """
        if "narrator" not in self.voice_library or not self.voice_library["narrator"]:
            return "default", "fallback"

        # Prefer narrator_3.flac
        for entry in self.voice_library["narrator"]:
            if Path(entry["audio"]).name == "narrator_3.flac":
                return f"narrator|{entry['id']}", "narrator"

        # Fallback to any narrator voice
        sample = self.voice_library["narrator"][0]
        return f"narrator|{sample['id']}", "narrator"

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
            log.info(f"Cloning [{category}] (source: {Path(ref_data['audio']).name})")

        try:
            result = self.tts.generate(
                text=text,
                ref_audio=ref_data["audio"],
                ref_text=ref_data["text"],
                num_step=self._tts_wave_steps,
                speed=self._tts_speed,
            )
            audio = result[0]
            if isinstance(audio, torch.Tensor):
                wav = audio.detach().cpu().numpy().squeeze()
            else:
                wav = np.asarray(audio).squeeze()
            return wav.astype(np.float32)
        except Exception as e:
            log.error(f"Generation failed: {e}")
            return np.array([], dtype=np.float32)
