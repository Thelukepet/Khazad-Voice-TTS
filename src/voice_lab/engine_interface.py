# Imports

# > Standard Library
import traceback
from typing import Any, Callable, Tuple

# > Third-party Libraries
import numpy as np
import soundfile as sf

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


def load_omnivoice() -> Any:
    """
    Initializes the OmniVoice model on the best available device (CUDA/CPU).
    Lazy loads the model only when first requested.

    Returns
    -------
    OmniVoice
        The initialized OmniVoice model instance.
    """
    global tts_model
    if tts_model is None:
        print("Initializing OmniVoice...")
        import torch
        from omnivoice import OmniVoice

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        tts_model = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice", device_map=device, dtype=dtype
        )
    return tts_model


def auto_transcribe(audio_path: str, trim_func: Callable) -> str:
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
    trim_func: Callable,
) -> Tuple[int, np.ndarray]:
    """
    Generates a TTS audio preview using OmniVoice.

    Parameters
    ----------
    target_text : str
        The text to be spoken.
    ref_audio : str
        Path to the reference voice file.
    ref_transcript : str
        Transcript of the reference audio for alignment.
        Can be empty — OmniVoice will auto-transcribe via Whisper.
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

    tts = load_omnivoice()
    audio_path = trim_func(ref_audio, 20.0)

    try:
        # OmniVoice voice cloning: pass ref_audio and ref_text directly.
        # ref_text can be None or empty — the model will auto-transcribe via Whisper.
        result = tts.generate(
            text=target_text,
            ref_audio=audio_path,
            ref_text=ref_transcript if ref_transcript else None,
            num_step=steps_override,
            speed=speed,
        )

        audio = result[0]
        if hasattr(audio, "detach"):
            wav = audio.detach().cpu().numpy().squeeze()
        else:
            wav = np.asarray(audio).squeeze()

        return 24000, wav
    except Exception as e:
        traceback.print_exc()
        raise Exception(str(e))
