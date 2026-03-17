"""
Pytest configuration and shared fixtures.

This file provides common fixtures and configuration for all tests.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for testing data files."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_tts_backend():
    """Create a mock TTS backend for testing."""
    mock = Mock()
    mock.backend_id = "kokoro"
    mock.samplerate = 24000
    mock.pick_voice.return_value = ("test_voice", "test_category")
    mock.generate.return_value = bytearray([65] * 100)
    return mock


@pytest.fixture
def mock_db():
    """Create a mock database for testing."""
    mock = Mock()
    mock.lookup.side_effect = lambda name: (
        ("Male", "Elf", "Thranduil") if name == "Thranduil"
        else (None, None, name)
    )
    return mock


@pytest.fixture
def sample_quest_text():
    """Create sample QuestText for testing."""
    from src.models import QuestText, QuestTextLine, TextSourceType
    from datetime import datetime
    
    return QuestText(
        timestamp=datetime.now(),
        raw_ocr_text="Test quest text",
        lines=[
            QuestTextLine(text="Line 1", line_number=0, source=TextSourceType.OCR),
            QuestTextLine(text="Line 2", line_number=1, source=TextSourceType.WIKI, confidence=85.0),
            QuestTextLine(text="Line 3", line_number=2, source=TextSourceType.OCR)
        ],
        npc_name="Thranduil",
        quest_title="Test Quest",
        source_label="Mixed"
    )


@pytest.fixture
def sample_voice_selection():
    """Create sample VoiceSelection for testing."""
    from src.models import VoiceSelection
    
    return VoiceSelection(
        voice_id="en_us_elf_male",
        category="elf_male",
        npc_name="Thranduil",
        race="Elf",
        gender="Male",
        is_default=False
    )


@pytest.fixture
def sample_npc():
    """Create sample NPC for testing."""
    from src.models import NPC
    from datetime import datetime
    
    return NPC(
        name="Thranduil",
        race="Elf",
        gender="Male",
        voice_id="en_us_elf_male",
        voice_category="elf_male",
        last_seen=datetime.now(),
        matched_name="Thranduil"
    )


# Pytest configuration
def pytest_configure(config):
    """Configure pytest options."""
    # Add custom markers
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m not slow')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
