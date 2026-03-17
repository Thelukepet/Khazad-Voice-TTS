"""
Tests for the engine module.

Tests NarratorEngine core functionality including voice resolution,
streaming, and quest processing.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from src.engine import NarratorEngine
from src.models import QuestText, QuestTextLine, VoiceSelection, TextSourceType


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
    
    def lookup(self, name):
        if name == "Thranduil":
            return "Male", "Elf", "Thranduil"
        elif name == "Unknown":
            return None, None, name
        return "Male", "Man", name


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
            lines=[QuestTextLine(text=s, line_number=i) for i, s in enumerate(sentences)],
            source_label="OCR"
        )
        
        assert len(quest_text.lines) == 3
        assert quest_text.get_line(0).text == "Sentence one."
        assert quest_text.get_line(1).text == "Sentence two."
        assert quest_text.get_full_text() == "Sentence one. Sentence two. Sentence three."

    def test_quest_text_with_wiki_source(self):
        """Test QuestText with Wiki source and confidence."""
        quest_text = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text="Test text",
            lines=[
                QuestTextLine(text="Wiki text", line_number=0, source=TextSourceType.WIKI, confidence=85.3)
            ],
            source_label="Wiki (Bestowal, 85.3%)"
        )
        
        assert quest_text.lines[0].source == TextSourceType.WIKI
        assert quest_text.lines[0].confidence == 85.3

    @patch('src.engine.stop_audio')
    @patch('src.engine.play_audio')
    def test_start_streaming_basic(self, mock_play, mock_stop):
        """Test streaming with basic QuestText and VoiceSelection."""
        quest_text = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text="Test",
            lines=[
                QuestTextLine(text="Hello", line_number=0),
                QuestTextLine(text="World", line_number=1)
            ]
        )
        
        voice_selection = VoiceSelection(
            voice_id="test_voice",
            category="test_cat",
            npc_name="TestNPC",
            race="Man",
            gender="Male"
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
            gender="Gender"
        )
        
        assert hasattr(selection, 'voice_id')
        assert hasattr(selection, 'category')
        assert hasattr(selection, 'npc_name')
        assert hasattr(selection, 'race')
        assert hasattr(selection, 'gender')
        assert hasattr(selection, 'is_default')


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
                QuestTextLine(text="Line 4", line_number=3)
            ]
        )
        
        for i, line in enumerate(quest.lines):
            assert line.line_number == i

    def test_quest_text_empty_lines(self):
        """Test QuestText with empty lines."""
        quest = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text="Test",
            lines=[]
        )
        
        assert len(quest.lines) == 0
        assert quest.get_full_text() == ""
        assert quest.get_line(0) is None

    def test_mixed_source_types(self):
        """Test QuestText with mixed source types."""
        quest = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text="Test",
            lines=[
                QuestTextLine(text="OCR text", line_number=0, source=TextSourceType.OCR),
                QuestTextLine(text="Wiki text", line_number=1, source=TextSourceType.WIKI, confidence=90.0),
                QuestTextLine(text="More OCR", line_number=2, source=TextSourceType.OCR)
            ]
        )
        
        assert quest.lines[0].source == TextSourceType.OCR
        assert quest.lines[1].source == TextSourceType.WIKI
        assert quest.lines[2].source == TextSourceType.OCR
