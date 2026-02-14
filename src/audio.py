# Imports

# > Standard Library
import logging
import time
from typing import Optional
from threading import Event

# > Third-party Libraries
import sounddevice as sd
import soundcard as sc
import numpy as np
import threading

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

        # 3. Force Stereo
        if isinstance(final_audio, np.ndarray) and final_audio.ndim == 1:
            final_audio = np.column_stack((final_audio, final_audio))

        # 4. Playback with Interrupt Support
        # We use soundcard's player context manager.
        default_speaker = sc.default_speaker()

        # Calculate chunk size (e.g., 0.1 seconds) for responsiveness
        chunk_size = int(samplerate * 0.1)

        with default_speaker.player(samplerate=samplerate) as player:
            # Loop through the audio in small chunks
            for i in range(0, len(final_audio), chunk_size):
                # Check for F12 Stop Signal
                if stop_event is not None and stop_event.is_set():
                    return # Exit function immediately (stops audio)

                # Play the current chunk
                chunk = final_audio[i : i + chunk_size]
                player.play(chunk)

    except Exception as e:
        log.error(f"Audio Playback Error: {e}")


def stop_audio() -> None:
    """
    Forcefully stops the sounddevice stream.
    """
    #try:
    #    sd.stop()
    #except Exception as e:
    #    log.error(f"Failed to stop audio: {e}")
    pass
