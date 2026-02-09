# Imports

# > Third party imports
import sounddevice as sd
import numpy as np

# > Local dependencies
from .utils import setup_logger
from .config import DEFAULT_VOLUME

log = setup_logger("AUDIO")


def normalize_audio_rms(audio_data, target_db=-20.0):
    """
    Normalizes audio based on RMS (perceived loudness) rather than just peaks.
    Target dB is usually -20dB for standard speech.
    """
    rms = np.sqrt(np.mean(audio_data ** 2))

    if rms == 0:
        return audio_data

    # Calculate the scalar to reach target dB
    scalar = 10 ** (target_db / 20) / rms

    # Apply scalar
    normalized = audio_data * scalar

    # Safety Check: Prevent clipping if the boost was too high
    max_val = np.max(np.abs(normalized))
    if max_val > 1.0:
        normalized = normalized / max_val

    return normalized

def play_audio(audio_data, samplerate, volume=None):
    """
    Plays audio data using sounddevice.

    Parameters
    ----------
    audio_data : np.ndarray
        The audio waveform to play.
    samplerate : int
        The sample rate of the audio (e.g., 24000, 44100).
    volume : float, optional
        Volume multiplier (default is 1.0).
    """
    if len(audio_data) == 0:
        return

    # Use the passed volume, or fall back to the global config DEFAULT_VOLUME
    if volume is None:
        volume = DEFAULT_VOLUME

    try:
        # 1. Normalize (Standardize loudness to -20dB)
        clean_audio = normalize_audio_rms(audio_data)

        # 2. Apply Volume
        final_audio = clean_audio * volume

        # 3. Play
        sd.play(final_audio, samplerate)
        sd.wait()

    except Exception as e:
        log.error(f"Audio Playback Error: {e}")