"""
Text-to-Speech Package Initializer.
Exposes the factory function to select between Kokoro (CPU) and OmniVoice (GPU).
"""

from src.utils import setup_logger

log = setup_logger("TTS_FACTORY")


def get_tts_backend(device_choice: str = "cpu"):
    """
    Factory function to return the requested TTS backend.

    Parameters
    ----------
    device_choice : str
        'cpu' for KokoroBackend, 'gpu' for OmniVoiceBackend.

    Returns
    -------
    TTSBackend
        An instance of the selected backend.
    """
    if device_choice == "gpu":
        log.info("🚀 User selected GPU (OmniVoice). Initializing...")
        try:
            from .omnivoice import OmniVoiceBackend

            return OmniVoiceBackend()
        except Exception as e:
            log.error(f"❌ Failed to load OmniVoice (GPU): {e}")
            log.warning("⚠️ Falling back to Kokoro (CPU) automatically.")
            from .kokoro import KokoroBackend

            return KokoroBackend()
    else:
        log.info("🐢 User selected CPU (Kokoro). Initializing...")
        from .kokoro import KokoroBackend

        return KokoroBackend()
