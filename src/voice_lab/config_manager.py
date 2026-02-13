# Imports

# > Standard Library
import re
from pathlib import Path
from typing import Dict, Tuple, Union

# --- FILE PATHS ---
CONFIG_PATH = Path("src/config.py")
ENGINE_PATH = Path("src/engine.py")


def get_current_settings() -> Dict[str, Union[float, int, str]]:
    """
    Reads current settings from config.py and engine.py via Regex.

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
    settings = {}

    # 1. Read src/config.py
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            content = f.read()

            vol_match = re.search(r'DEFAULT_VOLUME\s*=\s*([\d\.]+)', content)
            settings["volume"] = float(vol_match.group(1)) if vol_match else 0.4

            lux_vol_match = re.search(r'LUX_VOLUME\s*=\s*([\d\.]+)', content)
            settings["lux_volume"] = float(lux_vol_match.group(1)) if lux_vol_match else 0.4

            speed_match = re.search(r'TTS_SPEED\s*=\s*([\d\.]+)', content)
            settings["speed"] = float(speed_match.group(1)) if speed_match else 1.1

            steps_match = re.search(r'TTS_WAVE_STEPS\s*=\s*(\d+)', content)
            settings["steps"] = int(steps_match.group(1)) if steps_match else 6

            thresh_match = re.search(r'TEMPLATE_THRESHOLD\s*=\s*([\d\.]+)', content)
            settings["threshold"] = float(thresh_match.group(1)) if thresh_match else 0.5

            tess_match = re.search(r'TESSERACT_CMD\s*=\s*r?"([^"]+)"', content)
            settings["tesseract"] = tess_match.group(
                1) if tess_match else r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    # 2. Read src/engine.py (For Chunk Size)
    if ENGINE_PATH.exists():
        with open(ENGINE_PATH, "r", encoding="utf-8") as f:
            content = f.read()
            chunk_match = re.search(r'if self\.backend_id == "lux":\s+chunk_size\s*=\s*(\d+)', content)
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
    Writes new settings back to the config.py and engine.py files.

    Parameters
    ----------
    vol : float
        The master volume for CPU (Kokoro) TTS.
    lux_vol : float
        The volume for GPU (LuxTTS).
    speed : float
        The TTS speaking speed multiplier.
    steps : int
        Number of diffusion steps for LuxTTS (Quality vs Speed).
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

    # 1. Update Config.py
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        content = re.sub(r'DEFAULT_VOLUME\s*=\s*[\d\.]+', f'DEFAULT_VOLUME = {vol}', content)
        content = re.sub(r'TTS_SPEED\s*=\s*[\d\.]+', f'TTS_SPEED = {speed}', content)
        content = re.sub(r'TTS_WAVE_STEPS\s*=\s*\d+', f'TTS_WAVE_STEPS = {steps}', content)
        content = re.sub(r'TEMPLATE_THRESHOLD\s*=\s*[\d\.]+', f'TEMPLATE_THRESHOLD = {thresh}', content)

        if re.search(r'LUX_VOLUME\s*=', content):
            content = re.sub(r'LUX_VOLUME\s*=\s*[\d\.]+', f'LUX_VOLUME = {lux_vol}', content)
        else:
            content += f"\nLUX_VOLUME = {lux_vol}\n"
            log_msgs.append("➕ Added LUX_VOLUME to config.")

        def repl_tess(m):
            return f'TESSERACT_CMD = r"{tesseract}"'

        content = re.sub(r'TESSERACT_CMD\s*=\s*r?".*?"', repl_tess, content)

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        log_msgs.append("✅ Config.py updated.")

    # 2. Update Engine.py
    if ENGINE_PATH.exists():
        with open(ENGINE_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        pattern = r'(if self\.backend_id == "lux":\s+chunk_size\s*=\s*)(\d+)'
        if re.search(pattern, content):
            content = re.sub(pattern, f'\\g<1>{int(chunk_size)}', content)
            with open(ENGINE_PATH, "w", encoding="utf-8") as f:
                f.write(content)
            log_msgs.append(f"✅ Engine.py updated (Chunk Size: {chunk_size}).")
        else:
            log_msgs.append("⚠️ Could not update Chunk Size in engine.py (Pattern mismatch).")

    return "\n".join(log_msgs), speed, steps