"""Tests for NPC voice memory: persistence, stale-voice pruning, and
filename-based resolution across library changes.

The memory must persist across play sessions - pruning only removes
entries whose assigned voice no longer exists (the NPC would otherwise
stay silent), and assignments are remembered by source filename so they
survive library changes that shift the index-based voice ids.
"""

from unittest.mock import patch

from src.engine import NarratorEngine


def _make_engine(library):
    """Bare NarratorEngine with a fake TTS backend and empty memory."""
    eng = NarratorEngine.__new__(NarratorEngine)
    eng.mode = "retail"

    class FakeTTS:
        backend_id = "omnivoice"
        voice_library = library

    eng.tts = FakeTTS()
    eng.memory = {}
    return eng


LIBRARY = {
    "dwarf_male": [
        {"id": 0, "audio": "data/ref/dwarf_male_1.flac", "text": "x"},
        {"id": 1, "audio": "data/ref/dwarf_male_breeze2_01.wav", "text": "x"},
        {"id": 2, "audio": "data/ref/dwarf_male_breeze_05.wav", "text": "x"},
    ]
}


class TestPruneStaleVoices:
    def test_valid_entry_survives(self):
        eng = _make_engine(LIBRARY)
        eng.memory = {
            "thorin": {
                "voice_id": "dwarf_male|1",
                "category": "dwarf_male",
                "voice_file": "dwarf_male_breeze2_01.wav",
            }
        }
        with patch("src.engine.save_npc_memory") as save:
            eng._prune_stale_voices()
        assert "thorin" in eng.memory
        save.assert_not_called()

    def test_missing_source_file_pruned(self):
        eng = _make_engine(LIBRARY)
        eng.memory = {
            "thorin": {
                "voice_id": "dwarf_male|1",
                "category": "dwarf_male",
                "voice_file": "removed_voice.wav",
            }
        }
        with patch("src.engine.save_npc_memory") as save:
            eng._prune_stale_voices()
        assert "thorin" not in eng.memory
        save.assert_called_once()

    def test_stale_index_pruned(self):
        """Old-format entry (no voice_file) with an out-of-range id."""
        eng = _make_engine(LIBRARY)
        eng.memory = {
            "halli": {
                "voice_id": "dwarf_male|15",
                "category": "dwarf_male",
            }
        }
        with patch("src.engine.save_npc_memory"):
            eng._prune_stale_voices()
        assert "halli" not in eng.memory

    def test_valid_old_format_kept(self):
        eng = _make_engine(LIBRARY)
        eng.memory = {
            "tindr": {
                "voice_id": "dwarf_male|2",
                "category": "dwarf_male",
            }
        }
        with patch("src.engine.save_npc_memory") as save:
            eng._prune_stale_voices()
        assert "tindr" in eng.memory
        save.assert_not_called()

    def test_kokoro_ids_untouched(self):
        """Static backend ids (no pipe) are never pruned."""
        eng = _make_engine(LIBRARY)
        eng.memory = {
            "bard": {"voice_id": "am_echo", "category": "narrator"},
        }
        with patch("src.engine.save_npc_memory") as save:
            eng._prune_stale_voices()
        assert "bard" in eng.memory
        save.assert_not_called()

    def test_no_library_noop(self):
        """Kokoro backend has no voice_library - prune must not touch memory."""
        eng = _make_engine(None)
        eng.memory = {
            "bard": {"voice_id": "am_echo", "category": "narrator"},
        }
        with patch("src.engine.save_npc_memory") as save:
            eng._prune_stale_voices()
        assert "bard" in eng.memory
        save.assert_not_called()


class TestCurrentVoiceId:
    def test_filename_survives_index_shift(self):
        """Adding a voice shifted the indices - the file is still there."""
        eng = _make_engine(LIBRARY)
        entry = {
            "voice_id": "dwarf_male|0",  # stale index
            "voice_file": "dwarf_male_breeze_05.wav",  # now at id 2
        }
        assert eng._current_voice_id(entry) == "dwarf_male|2"

    def test_filename_missing_returns_none(self):
        eng = _make_engine(LIBRARY)
        entry = {
            "voice_id": "dwarf_male|1",
            "voice_file": "gone.wav",
        }
        assert eng._current_voice_id(entry) is None

    def test_old_format_valid_index(self):
        eng = _make_engine(LIBRARY)
        entry = {"voice_id": "dwarf_male|1"}
        assert eng._current_voice_id(entry) == "dwarf_male|1"

    def test_old_format_invalid_index(self):
        eng = _make_engine(LIBRARY)
        entry = {"voice_id": "dwarf_male|99"}
        assert eng._current_voice_id(entry) is None

    def test_old_format_bad_category(self):
        eng = _make_engine(LIBRARY)
        entry = {"voice_id": "unknown_cat|0"}
        assert eng._current_voice_id(entry) is None
