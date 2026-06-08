# Imports

# > Standard Library
from typing import Dict, Tuple, Union

# > Local Dependencies
from src.config.ConfigManager import ConfigManager


def get_current_settings() -> Dict[str, Union[float, int, str]]:
    """
    Reads current settings from ConfigManager (INI).

    Returns
    -------
    dict
        A dictionary containing the current configuration values.
        Keys include:
        - 'volume': float
        - 'omnivoice_volume': float
        - 'speed': float
        - 'steps': int
        - 'threshold': float
        - 'tesseract': str
        - 'chunk_size': int
    """
    cfg = ConfigManager()

    settings = {
        "volume": cfg.config.getfloat("TTSSettings", "default_volume", fallback=0.4),
        "omnivoice_volume": cfg.config.getfloat(
            "TTSSettings", "omnivoice_volume", fallback=0.4
        ),
        "speed": cfg.config.getfloat("TTSSettings", "tts_speed", fallback=1.1),
        "steps": cfg.config.getint("TTSSettings", "tts_wave_steps", fallback=6),
        "threshold": cfg.config.getfloat(
            "Detection", "template_threshold", fallback=0.5
        ),
        "tesseract": cfg.tesseract_cmd,
        "chunk_size": cfg.config.getint(
            "TTSSettings", "omnivoice_chunk_size", fallback=2
        ),
    }

    return settings


def save_settings(
    vol: float,
    omnivoice_vol: float,
    speed: float,
    steps: int,
    thresh: float,
    tesseract: str,
    chunk_size: int,
) -> Tuple[str, float, int]:
    """
    Writes new settings to ConfigManager (INI).

    Parameters
    ----------
    vol : float
        The master volume for CPU (Kokoro) TTS.
    omnivoice_vol : float
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

    # Update all settings via ConfigManager
    cfg.config.set("TTSSettings", "default_volume", str(vol))
    cfg.config.set("TTSSettings", "omnivoice_volume", str(omnivoice_vol))
    cfg.config.set("TTSSettings", "tts_speed", str(speed))
    cfg.config.set("TTSSettings", "tts_wave_steps", str(steps))
    cfg.config.set("TTSSettings", "omnivoice_chunk_size", str(chunk_size))
    cfg.config.set("Detection", "template_threshold", str(thresh))

    # Update tesseract via the property (also saves the file)
    cfg.tesseract_cmd = tesseract

    # Save config to disk
    with open(cfg.config_path, "w") as configfile:
        cfg.config.write(configfile)

    log_msgs.append("✅ Config updated (khazad_config.ini).")
    log_msgs.append(f"✅ Chunk Size set to {chunk_size}.")

    return "\n".join(log_msgs), speed, steps
