# Imports

# > Standard Library
import re
from pathlib import Path
from typing import Dict, Tuple, Union

# > Internal
from src.config.ConfigManager import ConfigManager

# --- FILE PATHS ---
ENGINE_PATH = Path("src/engine.py")


def get_current_settings() -> Dict[str, Union[float, int, str]]:
    """
    Reads current settings from ConfigManager (INI) and engine.py (chunk_size).

    Returns
    -------
    dict
        A dictionary containing the current configuration values.
        Keys include:
        - 'volume': float
        - 'lux_volume': float
        - 'speed': float
        - 'steps': int
        - 'threshold': float
        - 'tesseract': str
        - 'chunk_size': int
    """
    cfg = ConfigManager()

    settings = {
        "volume": cfg.config.getfloat("TTSSettings", "default_volume", fallback=0.4),
        "lux_volume": cfg.config.getfloat("TTSSettings", "lux_volume", fallback=0.4),
        "speed": cfg.config.getfloat("TTSSettings", "tts_speed", fallback=1.1),
        "steps": cfg.config.getint("TTSSettings", "tts_wave_steps", fallback=6),
        "threshold": cfg.config.getfloat(
            "Detection", "template_threshold", fallback=0.5
        ),
        "tesseract": cfg.tesseract_cmd,
    }

    # Read src/engine.py (For Chunk Size)
    if ENGINE_PATH.exists():
        with open(ENGINE_PATH, "r", encoding="utf-8") as f:
            content = f.read()
            chunk_match = re.search(
                r'if self\.backend_id == "lux":\s+chunk_size\s*=\s*(\d+)', content
            )
            settings["chunk_size"] = int(chunk_match.group(1)) if chunk_match else 2

    return settings


def save_settings(
    vol: float,
    lux_vol: float,
    speed: float,
    steps: int,
    thresh: float,
    tesseract: str,
    chunk_size: int,
) -> Tuple[str, float, int]:
    """
    Writes new settings to ConfigManager (INI) and engine.py (chunk_size).

    Parameters
    ----------
    vol : float
        The master volume for CPU (Kokoro) TTS.
    lux_vol : float
        The volume for GPU (OmniVoice).
    speed : float
        The TTS speaking speed multiplier.
    steps : int
        Number of diffusion steps for OmniVoice (Quality vs Speed).
    thresh : float
        The template matching confidence threshold for visual detection.
    tesseract : str
        The absolute path to the tesseract.exe binary.
    chunk_size : int
        Number of sentences to batch before streaming audio (1 or 2).

    Returns
    -------
    tuple
        A tuple containing:
        - log_msg (str): A summary log of what was updated.
        - speed (float): The speed value (returned for UI updates).
        - steps (int): The steps value (returned for UI updates).
    """
    log_msgs = []

    cfg = ConfigManager()

    # 1. Update INI config via ConfigManager
    cfg.config.set("TTSSettings", "default_volume", str(vol))
    cfg.config.set("TTSSettings", "lux_volume", str(lux_vol))
    cfg.config.set("TTSSettings", "tts_speed", str(speed))
    cfg.config.set("TTSSettings", "tts_wave_steps", str(steps))
    cfg.config.set("Detection", "template_threshold", str(thresh))

    # Update tesseract via the property (also saves the file)
    cfg.tesseract_cmd = tesseract

    log_msgs.append("✅ Config updated (khazad_config.ini).")

    # 2. Update Engine.py (Chunk Size)
    if ENGINE_PATH.exists():
        with open(ENGINE_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        pattern = r'(if self\.backend_id == "lux":\s+chunk_size\s*=\s*)(\d+)'
        if re.search(pattern, content):
            content = re.sub(pattern, f"\\g<1>{int(chunk_size)}", content)
            with open(ENGINE_PATH, "w", encoding="utf-8") as f:
                f.write(content)
            log_msgs.append(f"✅ Engine.py updated (Chunk Size: {chunk_size}).")
        else:
            log_msgs.append(
                "⚠️ Could not update Chunk Size in engine.py (Pattern mismatch)."
            )

    return "\n".join(log_msgs), speed, steps
