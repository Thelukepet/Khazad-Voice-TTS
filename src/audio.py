# Imports

# > Standard Library
import logging
import time
from typing import Optional
from threading import Event

# > Third-party Libraries
import sounddevice as sd
import numpy as np

# > Local Dependencies
from .config import DEFAULT_VOLUME

log = logging.getLogger("AUDIO")


def normalize_audio_rms(audio_data: np.ndarray, target_db: float = -20.0) -> np.ndarray:
    """
    Normalizes audio based on RMS (perceived loudness).
    """
    rms = np.sqrt(np.mean(audio_data**2))
    if rms == 0:
        return audio_data

    scalar = 10 ** (target_db / 20) / rms
    normalized = audio_data * scalar

    max_val = np.max(np.abs(normalized))
    if max_val > 1.0:
        normalized = normalized / max_val

    return normalized


def play_audio(
    audio_data: np.ndarray,
    samplerate: int,
    volume: Optional[float] = None,
    stop_event: Optional[Event] = None
) -> None:
    """
    Plays audio using sounddevice.
    Uses a polling loop instead of sd.wait() to ensure it can be interrupted immediately.

    Parameters
    ----------
    audio_data : np.ndarray
        Audio samples.
    samplerate : int
        Sample rate.
    volume : float, optional
        Volume multiplier.
    stop_event : threading.Event, optional
        Event to check for cancellation.
    """
    if audio_data is None or len(audio_data) == 0:
        return

    if volume is None:
        volume = DEFAULT_VOLUME

    try:
        # 1. Normalize & Apply Volume
        clean_audio = normalize_audio_rms(audio_data)
        final_audio = clean_audio * volume

        # 2. Calculate Duration
        duration = len(final_audio) / samplerate

        # 3. Start Playback (Non-blocking)
        sd.play(final_audio, samplerate)
        speaker.play(final_audio, samplerate=samplerate)

        # 5. Smart Sleep Loop (Interruptible)
        start_time = time.time()
        while time.time() - start_time < duration:
            # Check if F12 was pressed
            if stop_event is not None and stop_event.is_set():
                sd.stop()  # Kill hardware stream immediately
                return

            # Sleep in small chunks to remain responsive
            time.sleep(0.05)

        # Ensure stream is totally finished before returning (optional but safe)
        sd.stop()

    except Exception as e:
        log.error(f"Audio Playback Error: {e}")


def stop_audio() -> None:
    """
    Forcefully stops the sounddevice stream.
    """
    try:
        sd.stop()
    except Exception as e:
        log.error(f"Failed to stop audio: {e}")
