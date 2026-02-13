# Imports

# > Standard Library
import sys
import traceback
from pathlib import Path
from typing import Any, Tuple, Optional, Callable

# > Third-party Libraries
import torch
import soundfile as sf
import numpy as np

# Add LuxTTS to path
LUX_PATH = Path("LuxTTS").resolve()
if LUX_PATH.exists() and str(LUX_PATH) not in sys.path:
    sys.path.append(str(LUX_PATH))

whisper_model = None
tts_model = None


def load_whisper() -> Any:
    """
    Loads the Whisper model (Base) for transcription on CPU.
    Lazy loads the model only when first requested.

    Returns
    -------
    whisper.model.Whisper
        The loaded Whisper model instance.
    """
    global whisper_model
    if whisper_model is None:
        print("Loading Whisper (Base)...")
        import whisper

        whisper_model = whisper.load_model("base", device="cpu")
    return whisper_model


def load_lux() -> Any:
    """
    Initializes the LuxTTS model on the best available device (CUDA/CPU).
    Lazy loads the model only when first requested.

    Returns
    -------
    LuxTTS
        The initialized LuxTTS wrapper instance.
    """
    global tts_model
    if tts_model is None:
        print("Initializing LuxTTS...")
        try:
            from zipvoice.luxvoice import LuxTTS
        except ImportError:
            from LuxTTS.zipvoice.luxvoice import LuxTTS

        device = "cuda" if torch.cuda.is_available() else "cpu"
        tts_model = LuxTTS("YatharthS/LuxTTS", device=device)
    return tts_model


def auto_transcribe(audio_path: str, trim_func: Callable[[str, float], str]) -> str:
    """
    Transcribes audio using Whisper. Trims to 20s before processing.

    Parameters
    ----------
    audio_path : str
        Path to the audio file.
    trim_func : Callable
        A function to trim the audio (from library module).

    Returns
    -------
    str
        The transcribed text or an error message string.
    """
    if not audio_path:
        return ""
    try:
        path = trim_func(audio_path, 20.0)
        model = load_whisper()
        res = model.transcribe(path)
        return res["text"].strip()
    except Exception as e:
        return f"[Error: {e}]"


def generate_preview(
    target_text: str,
    ref_audio: str,
    ref_transcript: str,
    speed: float,
    steps_override: int,
    trim_func: Callable[[str, float], str],
) -> Tuple[int, np.ndarray]:
    """
    Generates a TTS audio preview using LuxTTS.

    Parameters
    ----------
    target_text : str
        The text to be spoken.
    ref_audio : str
        Path to the reference voice file.
    ref_transcript : str
        Transcript of the reference audio for alignment.
    speed : float
        Speed multiplier for speech generation.
    steps_override : int
        Number of diffusion steps.
    trim_func : Callable
        Function to trim audio (ensuring prompts aren't too long).

    Returns
    -------
    tuple
        (sample_rate, waveform_array) compatible with Gradio Audio output.
    """
    if not ref_audio:
        raise ValueError("Reference audio required.")

    tts = load_lux()
    audio_path = trim_func(ref_audio, 20.0)

    try:
        data, sr = sf.read(audio_path)
        duration_ms = int((len(data) / sr) * 1000)

        encoded_prompt = tts.encode_prompt(
            audio_path, text=ref_transcript, rms=0.01, duration=duration_ms
        )
        wav = tts.generate_speech(
            target_text,
            encoded_prompt,
            speed=speed,
            num_steps=steps_override,
            t_shift=0.9,
        )

        if hasattr(wav, "detach"):
            wav = wav.detach().cpu().numpy().squeeze()
        else:
            wav = wav.numpy().squeeze()

        return 48000, wav
    except Exception as e:
        traceback.print_exc()
        raise Exception(str(e))
