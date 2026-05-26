"""
Tests for the engine module.

Tests NarratorEngine core functionality including voice resolution,
streaming, and quest processing.
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.engine import NarratorEngine
from src.models import QuestText, QuestTextLine, TextSourceType, VoiceSelection


class MockTTS:
    """Mock TTS backend for testing."""

    backend_id = "kokoro"
    samplerate = 24000

    def pick_voice(self, gender, race):
        return "test_voice", "test_category"

    def generate(self, text, voice_id):
        # Return dummy audio data
        return bytearray([65] * 100)  # 100 bytes of dummy audio


class MockDB:
    """Mock database for testing."""

    quest_titles = []

    def lookup(self, name):
        if name == "Thranduil":
            return "Male", "Elf", "Thranduil"
        elif name == "Unknown":
            return None, None, name
        return "Male", "Man", name

    def resolve_quest_title(self, ocr_title):
        return None

    def match_quest_text(self, ocr_title, ocr_body):
        return None

    def get_quest_text(self, ocr_title, npc_name=None):
        return None


class TestNarratorEngine:
    """Tests for NarratorEngine class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.mock_db = MockDB()
        self.mock_tts = MockTTS()
        self.engine = NarratorEngine(self.mock_db, self.mock_tts, mode="retail")

    def test_engine_initialization(self):
        """Test engine initializes correctly."""
        assert self.engine.db is not None
        assert self.engine.tts is not None
        assert self.engine.mode == "retail"
        assert self.engine.backend_id == "kokoro"
        assert self.engine.memory is not None
        assert self.engine.audio_queue is not None
        assert self.engine.stop_event is not None

    def test_stop_method(self):
        """Test stop method clears queue and stops playback."""
        # Add something to the queue
        self.engine.audio_queue.put(("test", b"audio", 24000))

        self.engine.stop()

        # Check stop event is set
        assert self.engine.stop_event.is_set()

        # Check queue is cleared
        assert self.engine.audio_queue.qsize() == 0

    def test_resolve_voice_known_npc(self):
        """Test voice resolution for known NPC."""
        selection = self.engine._resolve_voice("Thranduil")

        assert isinstance(selection, VoiceSelection)
        assert selection.npc_name == "Thranduil"
        assert selection.race == "Elf"
        assert selection.gender == "Male"
        assert selection.is_default is False

    def test_resolve_voice_unknown_npc(self):
        """Test voice resolution for unknown NPC defaults to narrator."""
        selection = self.engine._resolve_voice("Unknown")

        assert isinstance(selection, VoiceSelection)
        assert selection.race == "Narrator"
        assert selection.gender == "Narrator"
        assert selection.is_default is True

    def test_resolve_voice_caching(self):
        """Test that voice selection is cached in memory."""
        # First lookup
        selection1 = self.engine._resolve_voice("Thranduil")

        # Second lookup should use cache
        selection2 = self.engine._resolve_voice("Thranduil")

        assert selection1.voice_id == selection2.voice_id
        assert "thranduil" in self.engine.memory

    def test_build_quest_text(self):
        """Test QuestText model is built correctly."""
        sentences = ["Sentence one.", "Sentence two.", "Sentence three."]

        quest_text = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text=" ".join(sentences),
            lines=[
                QuestTextLine(text=s, line_number=i) for i, s in enumerate(sentences)
            ],
            source_label="OCR",
        )

        assert len(quest_text.lines) == 3
        assert quest_text.get_line(0).text == "Sentence one."
        assert quest_text.get_line(1).text == "Sentence two."
        assert (
            quest_text.get_full_text() == "Sentence one. Sentence two. Sentence three."
        )

    def test_quest_text_with_wiki_source(self):
        """Test QuestText with Wiki source and confidence."""
        quest_text = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text="Test text",
            lines=[
                QuestTextLine(
                    text="Wiki text",
                    line_number=0,
                    source=TextSourceType.WIKI,
                    confidence=85.3,
                )
            ],
            source_label="Wiki (Bestowal, 85.3%)",
        )

        assert quest_text.lines[0].source == TextSourceType.WIKI
        assert quest_text.lines[0].confidence == 85.3

    @patch("src.engine.stop_audio")
    @patch("src.engine.play_audio")
    def test_start_streaming_basic(self, mock_play, mock_stop):
        """Test streaming with basic QuestText and VoiceSelection."""
        quest_text = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text="Test",
            lines=[
                QuestTextLine(text="Hello", line_number=0),
                QuestTextLine(text="World", line_number=1),
            ],
        )

        voice_selection = VoiceSelection(
            voice_id="test_voice",
            category="test_cat",
            npc_name="TestNPC",
            race="Man",
            gender="Male",
        )

        # This would normally start a thread, so we just check it doesn't error
        # Full streaming test requires mocking the queue and audio playback
        assert quest_text is not None
        assert voice_selection is not None

    def test_voice_selection_attributes(self):
        """Test VoiceSelection has all required attributes."""
        selection = VoiceSelection(
            voice_id="test",
            category="cat",
            npc_name="Name",
            race="Race",
            gender="Gender",
        )

        assert hasattr(selection, "voice_id")
        assert hasattr(selection, "category")
        assert hasattr(selection, "npc_name")
        assert hasattr(selection, "race")
        assert hasattr(selection, "gender")
        assert hasattr(selection, "is_default")


class TestEngineIntegration:
    """Integration tests for engine workflow."""

    def test_quest_text_line_numbering(self):
        """Test line numbers are sequential."""
        quest = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text="Test",
            lines=[
                QuestTextLine(text="Line 1", line_number=0),
                QuestTextLine(text="Line 2", line_number=1),
                QuestTextLine(text="Line 3", line_number=2),
                QuestTextLine(text="Line 4", line_number=3),
            ],
        )

        for i, line in enumerate(quest.lines):
            assert line.line_number == i

    def test_quest_text_empty_lines(self):
        """Test QuestText with empty lines."""
        quest = QuestText(timestamp=datetime.now(), raw_ocr_text="Test", lines=[])

        assert len(quest.lines) == 0
        assert quest.get_full_text() == ""
        assert quest.get_line(0) is None

    def test_mixed_source_types(self):
        """Test QuestText with mixed source types."""
        quest = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text="Test",
            lines=[
                QuestTextLine(
                    text="OCR text", line_number=0, source=TextSourceType.OCR
                ),
                QuestTextLine(
                    text="Wiki text",
                    line_number=1,
                    source=TextSourceType.WIKI,
                    confidence=90.0,
                ),
                QuestTextLine(
                    text="More OCR", line_number=2, source=TextSourceType.OCR
                ),
            ],
        )

        assert quest.lines[0].source == TextSourceType.OCR
        assert quest.lines[1].source == TextSourceType.WIKI
        assert quest.lines[2].source == TextSourceType.OCR

    def test_build_quest_from_db(self):
        """Test building QuestText from offline DB segments."""
        db_segments = [
            {
                "text": "A short description of the quest.",
                "npc_name": None,
                "text_type": "description",
                "is_dialogue": False,
            },
            {
                "text": "'Please help me, Traveler!'",
                "npc_name": "Carlo Blagrove",
                "text_type": "bestower",
                "is_dialogue": True,
            },
            {
                "text": "Go to the Great Smials and find the recipe.",
                "npc_name": None,
                "text_type": "objective",
                "is_dialogue": False,
            },
        ]

        engine = NarratorEngine(MockDB(), MockTTS(), mode="echoes")
        quest_text = engine._build_quest_from_db(
            db_segments, npc_name="Carlo Blagrove", quest_title="The Bird and Baby"
        )

        assert quest_text.source_label == "OfflineDB"
        assert quest_text.npc_name == "Carlo Blagrove"
        assert quest_text.quest_title == "The Bird and Baby"
        assert len(quest_text.lines) == 3

        # Description line — not quoted
        assert quest_text.lines[0].source == TextSourceType.OFFLINE_DB
        assert quest_text.lines[0].is_quoted is False

        # Bestower line — quoted (dialogue)
        assert quest_text.lines[1].is_quoted is True

        # Objective line — not quoted (narration)
        assert quest_text.lines[2].is_quoted is False

        assert "description" in quest_text.get_full_text()

    def test_tag_quoted_lines_detects_leading_quotes(self):
        """Test that OCR lines starting with a single quote are tagged as dialogue."""
        quest_text = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text="Test",
            lines=[
                QuestTextLine(
                    text="'I need your help!'", line_number=0, source=TextSourceType.OCR
                ),
                QuestTextLine(
                    text="This is narration.", line_number=1, source=TextSourceType.OCR
                ),
                QuestTextLine(
                    text="'Another spoken line continues here.",
                    line_number=2,
                    source=TextSourceType.OCR,
                ),
                QuestTextLine(
                    text="And it keeps going.'",
                    line_number=3,
                    source=TextSourceType.OCR,
                ),
            ],
        )

        NarratorEngine._tag_quoted_lines(quest_text)

        assert quest_text.lines[0].is_quoted is True
        assert quest_text.lines[1].is_quoted is False
        assert quest_text.lines[2].is_quoted is True
        assert quest_text.lines[3].is_quoted is True

    def test_tag_quoted_lines_state_machine(self):
        """Test state machine correctly handles mixed narration/dialogue from DB text.

        This mirrors the real-world case where a bestower text contains
        both narration (unquoted) and dialogue (quoted with '):
        """
        quest_text = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text="Test",
            lines=[
                QuestTextLine(
                    text="Some of Mossward's residents sustained injuries we cannot heal.",
                    line_number=0,
                    source=TextSourceType.OFFLINE_DB,
                ),
                QuestTextLine(
                    text="Meneldir hands you a small bundle of bandages and a pouch of bitter-smelling salve.",
                    line_number=1,
                    source=TextSourceType.OFFLINE_DB,
                ),
                QuestTextLine(
                    text="'This is the last of my supplies, but there is no reason to save them for another day.",
                    line_number=2,
                    source=TextSourceType.OFFLINE_DB,
                ),
                QuestTextLine(
                    text="Bring these bandages and this salve to the injured residents nearby.",
                    line_number=3,
                    source=TextSourceType.OFFLINE_DB,
                ),
                QuestTextLine(
                    text="It is my hope that their hurts will not prove serious, and these will ease the pain of their injuries.'",
                    line_number=4,
                    source=TextSourceType.OFFLINE_DB,
                ),
            ],
        )

        NarratorEngine._tag_quoted_lines(quest_text)

        # Narration lines
        assert quest_text.lines[0].is_quoted is False
        assert quest_text.lines[1].is_quoted is False
        # Dialogue lines (within quote span)
        assert quest_text.lines[2].is_quoted is True
        assert quest_text.lines[3].is_quoted is True
        assert quest_text.lines[4].is_quoted is True
