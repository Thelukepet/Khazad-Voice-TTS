# Imports

# > Third party imports
import sounddevice as sd
import numpy as np

# > Local dependencies
from .utils import setup_logger

log = setup_logger("AUDIO")


def normalize_audio(audio_data):
    """
    Normalizes audio to ensure it doesn't clip (exceed -1.0 to 1.0 range).

    Parameters
    ----------
    audio_data : np.ndarray
        The input audio waveform data.

    Returns
    -------
    np.ndarray
        The normalized audio data scaled to fit within [-1.0, 1.0].
    """
    max_val = np.max(np.abs(audio_data))
    if max_val > 0:
        return audio_data / max_val
    return audio_data


def play_audio(audio_data, samplerate, volume=1.0):
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

    try:
        # 1. Normalize (Safety check to prevent distortion)
        # clean_audio = normalize_audio(audio_data)

        # 2. Apply Volume
        final_audio = audio_data * volume

        # 3. Play
        sd.play(final_audio, samplerate)
        sd.wait()  # Block until finished

    except Exception as e:
        log.error(f"Audio Playback Error: {e}")
