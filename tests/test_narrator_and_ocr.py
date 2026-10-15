"""Tests for narrator voice selection and OCR word-boundary fixes."""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# Stub heavy third-party deps so the backend module imports on machines
# without torch/omnivoice installed (e.g. CI runners).
for mod_name in ("torch", "omnivoice"):
    if mod_name not in sys.modules:
        stub = types.ModuleType(mod_name)
        if mod_name == "omnivoice":
            stub.OmniVoice = MagicMock()
        sys.modules[mod_name] = stub

from src.tts.omnivoice import OmniVoiceBackend  # noqa: E402
from src.ocr import clean_ocr_errors  # noqa: E402


def _backend_with_narrators(filenames):
    """Build an OmniVoiceBackend skeleton with a fake narrator library."""
    backend = OmniVoiceBackend.__new__(OmniVoiceBackend)
    backend.voice_library = {
        "narrator": [
            {"id": i, "text": f"transcript {i}", "audio": f"/ref/narrator/{name}", "type": "wav"}
            for i, name in enumerate(filenames)
        ]
    }
    return backend


class TestNarratorSelection:
    def test_configured_narrator_is_picked(self):
        backend = _backend_with_narrators(
            ["quest_narrator.wav", "narrator_male_01.wav", "narrator_gandalf_01.wav"]
        )
        cfg = MagicMock()
        cfg.get_str.return_value = "narrator_gandalf_01.wav"
        with patch("src.tts.omnivoice.ConfigManager", return_value=cfg):
            voice_id, category = backend.pick_narrator_voice()
        assert voice_id == "narrator|2"
        assert category == "narrator"

    def test_narrator_is_stable_across_calls(self):
        """Same config -> same voice every time (stable narrator)."""
        backend = _backend_with_narrators(
            ["quest_narrator.wav", "narrator_female_01.wav"]
        )
        cfg = MagicMock()
        cfg.get_str.return_value = "narrator_female_01.wav"
        with patch("src.tts.omnivoice.ConfigManager", return_value=cfg):
            first = backend.pick_narrator_voice()
            second = backend.pick_narrator_voice()
            third = backend.pick_narrator_voice()
        assert first == second == third

    def test_fallback_when_configured_file_missing(self):
        backend = _backend_with_narrators(["quest_narrator.wav"])
        cfg = MagicMock()
        cfg.get_str.return_value = "deleted_voice.wav"
        with patch("src.tts.omnivoice.ConfigManager", return_value=cfg):
            voice_id, category = backend.pick_narrator_voice()
        assert voice_id == "narrator|0"
        assert category == "narrator"

    def test_list_narrator_voices(self):
        backend = _backend_with_narrators(["a.wav", "b.wav"])
        assert backend.list_narrator_voices() == ["a.wav", "b.wav"]

    def test_empty_library_returns_default(self):
        backend = OmniVoiceBackend.__new__(OmniVoiceBackend)
        backend.voice_library = {}
        cfg = MagicMock()
        cfg.get_str.return_value = "quest_narrator.wav"
        with patch("src.tts.omnivoice.ConfigManager", return_value=cfg):
            voice_id, category = backend.pick_narrator_voice()
        assert voice_id == "default"
        assert category == "fallback"


class TestOcrWordBoundaries:
    def test_standalone_digit_one_becomes_I(self):
        assert clean_ocr_errors(["1 am here"]) == ["I am here"]

    def test_ordinal_numbers_preserved(self):
        assert clean_ocr_errors(["The 1st Age ended"]) == ["The 1st Age ended"]

    def test_ore_to_orc_only_as_word(self):
        assert clean_ocr_errors(["Slay the Ore"]) == ["Slay the Orc"]
        assert "iron ore" in " ".join(
            clean_ocr_errors(["Collect iron ore from the mine"])
        ).lower()

    def test_pipe_becomes_i(self):
        assert clean_ocr_errors(["| am here"]) == ["I am here"]
