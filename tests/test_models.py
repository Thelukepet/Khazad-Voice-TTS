"""
Tests for the models module (dataclasses).

Tests NPC, QuestText, QuestTextLine, VoiceSelection, and TextSourceType.
"""

import pytest
from datetime import datetime
from src.models import NPC, QuestText, QuestTextLine, VoiceSelection, TextSourceType


class TestNPC:
    """Tests for NPC dataclass."""

    def test_npc_creation(self):
        """Test creating an NPC with all attributes."""
        npc = NPC(
            name="Thranduil",
            race="Elf",
            gender="Male",
            voice_id="en_us_elf_male",
            voice_category="elf_male",
            last_seen=datetime.now(),
            matched_name="Thranduil"
        )
        
        assert npc.name == "Thranduil"
        assert npc.race == "Elf"
        assert npc.gender == "Male"
        assert npc.voice_id == "en_us_elf_male"
        assert npc.voice_category == "elf_male"
        assert npc.is_unknown() is False
        assert npc.has_voice() is True

    def test_npc_unknown(self):
        """Test NPC with unknown race/gender defaults to narrator."""
        npc = NPC(name="UnknownNPC")
        
        assert npc.race is None
        assert npc.gender is None
        assert npc.is_unknown() is True
        assert npc.has_voice() is False

    def test_npc_repr(self):
        """Test NPC string representation."""
        npc = NPC(name="Test", race="Man", gender="Male", voice_id="test_voice")
        repr_str = repr(npc)
        
        assert "Test" in repr_str
        assert "Man" in repr_str
        assert "Male" in repr_str


class TestQuestTextLine:
    """Tests for QuestTextLine dataclass."""

    def test_quest_text_line_creation(self):
        """Test creating a QuestTextLine."""
        line = QuestTextLine(
            text="Greetings traveler!",
            line_number=0,
            source=TextSourceType.OCR,
            confidence=None,
            is_quoted=False
        )
        
        assert line.text == "Greetings traveler!"
        assert line.line_number == 0
        assert line.source == TextSourceType.OCR
        assert line.confidence is None
        assert line.is_quoted is False

    def test_quest_text_line_wiki_source(self):
        """Test QuestTextLine with Wiki source and confidence."""
        line = QuestTextLine(
            text="I have a task for you.",
            line_number=1,
            source=TextSourceType.WIKI,
            confidence=85.3,
            is_quoted=False
        )
        
        assert line.source == TextSourceType.WIKI
        assert line.confidence == 85.3

    def test_quest_text_line_quoted(self):
        """Test QuestTextLine with quoted flag (future feature)."""
        line = QuestTextLine(
            text='"Greetings traveler!"',
            line_number=2,
            source=TextSourceType.OCR,
            is_quoted=True
        )
        
        assert line.is_quoted is True


class TestQuestText:
    """Tests for QuestText dataclass."""

    def test_quest_text_creation(self):
        """Test creating a QuestText with lines."""
        quest = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text="Greetings traveler! I have a task for you.",
            lines=[
                QuestTextLine(text="Greetings traveler!", line_number=0),
                QuestTextLine(text="I have a task for you.", line_number=1)
            ],
            npc_name="Thranduil",
            quest_title="The Elf Quest",
            source_label="OCR"
        )
        
        assert quest.npc_name == "Thranduil"
        assert quest.quest_title == "The Elf Quest"
        assert len(quest.lines) == 2
        assert quest.source_label == "OCR"

    def test_quest_text_get_line(self):
        """Test QuestText.get_line() method."""
        quest = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text="Test text",
            lines=[
                QuestTextLine(text="Line 0", line_number=0),
                QuestTextLine(text="Line 1", line_number=1),
                QuestTextLine(text="Line 2", line_number=2)
            ]
        )
        
        assert quest.get_line(0).text == "Line 0"
        assert quest.get_line(1).text == "Line 1"
        assert quest.get_line(2).text == "Line 2"
        assert quest.get_line(5) is None  # Out of bounds
        assert quest.get_line(-1) is None  # Negative index

    def test_quest_text_get_full_text(self):
        """Test QuestText.get_full_text() method."""
        quest = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text="Test",
            lines=[
                QuestTextLine(text="Hello", line_number=0),
                QuestTextLine(text="World", line_number=1),
                QuestTextLine(text="!", line_number=2)
            ]
        )
        
        full_text = quest.get_full_text()
        assert full_text == "Hello World !"

    def test_quest_text_get_quoted_lines(self):
        """Test QuestText.get_quoted_lines() method (future feature)."""
        quest = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text="Test",
            lines=[
                QuestTextLine(text="Narrator text", line_number=0, is_quoted=False),
                QuestTextLine(text='"NPC dialogue"', line_number=1, is_quoted=True),
                QuestTextLine(text="More narrator", line_number=2, is_quoted=False),
                QuestTextLine(text='"More dialogue"', line_number=3, is_quoted=True)
            ]
        )
        
        quoted = quest.get_quoted_lines()
        assert len(quoted) == 2
        assert quoted[0].text == '"NPC dialogue"'
        assert quoted[1].text == '"More dialogue"'

    def test_quest_text_get_narrator_lines(self):
        """Test QuestText.get_narrator_lines() method (future feature)."""
        quest = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text="Test",
            lines=[
                QuestTextLine(text="Narrator text", line_number=0, is_quoted=False),
                QuestTextLine(text='"NPC dialogue"', line_number=1, is_quoted=True),
                QuestTextLine(text="More narrator", line_number=2, is_quoted=False)
            ]
        )
        
        narrator = quest.get_narrator_lines()
        assert len(narrator) == 2
        assert narrator[0].text == "Narrator text"
        assert narrator[1].text == "More narrator"

    def test_quest_text_repr(self):
        """Test QuestText string representation."""
        quest = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text="Test",
            lines=[QuestTextLine(text="Test", line_number=0)],
            npc_name="TestNPC",
            quest_title="Test Quest",
            source_label="OCR"
        )
        
        repr_str = repr(quest)
        assert "TestNPC" in repr_str
        assert "Test Quest" in repr_str
        assert "1" in repr_str  # Number of lines


class TestVoiceSelection:
    """Tests for VoiceSelection dataclass."""

    def test_voice_selection_creation(self):
        """Test creating a VoiceSelection."""
        selection = VoiceSelection(
            voice_id="en_us_elf_male",
            category="elf_male",
            npc_name="Thranduil",
            race="Elf",
            gender="Male",
            is_default=False
        )
        
        assert selection.voice_id == "en_us_elf_male"
        assert selection.category == "elf_male"
        assert selection.npc_name == "Thranduil"
        assert selection.race == "Elf"
        assert selection.gender == "Male"
        assert selection.is_default is False

    def test_voice_selection_default(self):
        """Test VoiceSelection with default narrator voice."""
        selection = VoiceSelection(
            voice_id="narrator_default",
            category="narrator",
            npc_name="Unknown",
            race="Narrator",
            gender="Narrator",
            is_default=True
        )
        
        assert selection.is_default is True
        assert selection.race == "Narrator"

    def test_voice_selection_repr(self):
        """Test VoiceSelection string representation."""
        selection = VoiceSelection(
            voice_id="test_voice",
            category="test_cat",
            npc_name="TestNPC",
            race="Man",
            gender="Male"
        )
        
        repr_str = repr(selection)
        assert "TestNPC" in repr_str
        assert "test_voice" in repr_str


class TestTextSourceType:
    """Tests for TextSourceType enum."""

    def test_enum_values(self):
        """Test TextSourceType enum has correct values."""
        assert TextSourceType.OCR is not None
        assert TextSourceType.WIKI is not None
        assert TextSourceType.HYBRID is not None

    def test_enum_comparison(self):
        """Test TextSourceType comparison."""
        assert TextSourceType.OCR != TextSourceType.WIKI
        assert TextSourceType.OCR == TextSourceType.OCR
