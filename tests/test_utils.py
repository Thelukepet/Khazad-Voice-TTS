"""
Tests for the utils module.

Tests utility functions like load/save memory, coordinate handling,
and template loading.
"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.utils import (
    load_npc_memory,
    save_npc_memory,
    get_memory_file_path,
    get_file_paths,
    load_user_templates,
    load_user_config
)


class TestMemoryFunctions:
    """Tests for NPC memory load/save functions."""

    def setup_method(self):
        """Setup test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_mode = "retail"
        self.test_backend = "kokoro"

    def teardown_method(self):
        """Cleanup temp files."""
        import shutil
        shutil.rmtree(self.test_dir)

    def test_get_memory_file_path(self):
        """Test memory file path generation."""
        with patch('src.utils.DATA_DIR', Path(self.test_dir)):
            path = get_memory_file_path(self.test_mode, self.test_backend)
            
            assert path.exists() is False  # File doesn't exist yet
            assert path.name == "npc_memory_retail_kokoro.json"

    def test_get_file_paths(self):
        """Test legacy file path generation."""
        with patch('src.utils.DATA_DIR', Path(self.test_dir)):
            coords_path, legacy_path = get_file_paths(self.test_mode)
            
            assert coords_path.name == "coords_retail.json"
            assert legacy_path.name == "npc_memory_retail.json"

    def test_save_and_load_npc_memory(self):
        """Test saving and loading NPC memory."""
        test_memory = {
            "thr anduil": {
                "name": "Thranduil",
                "race": "Elf",
                "gender": "Male",
                "voice_id": "test_voice",
                "category": "elf_male"
            }
        }
        
        with patch('src.utils.DATA_DIR', Path(self.test_dir)):
            save_npc_memory(test_memory, self.test_mode, self.test_backend)
            
            loaded_memory = load_npc_memory(self.test_mode, self.test_backend)
            
            assert loaded_memory == test_memory
            assert "thr anduil" in loaded_memory
            assert loaded_memory["thr anduil"]["voice_id"] == "test_voice"

    def test_load_empty_memory(self):
        """Test loading memory when file doesn't exist."""
        with patch('src.utils.DATA_DIR', Path(self.test_dir)):
            memory = load_npc_memory(self.test_mode, self.test_backend)
            
            assert memory == {}

    def test_save_memory_creates_file(self):
        """Test that save creates the memory file."""
        test_memory = {"test": "value"}
        
        with patch('src.utils.DATA_DIR', Path(self.test_dir)):
            save_npc_memory(test_memory, self.test_mode, self.test_backend)
            
            memory_file = get_memory_file_path(self.test_mode, self.test_backend)
            assert memory_file.exists()


class TestTemplateFunctions:
    """Tests for template loading functions."""

    def test_load_user_templates_retail(self):
        """Test loading retail templates returns valid data or None."""
        templates = load_user_templates("retail")
        
        # Can be dict with templates or None if missing
        assert templates is None or isinstance(templates, dict)

    def test_load_user_templates_echoes(self):
        """Test loading echoes templates returns valid data or None."""
        templates = load_user_templates("echoes")
        
        # Can be dict with templates or None if missing
        assert templates is None or isinstance(templates, dict)


class TestConfigFunctions:
    """Tests for config loading functions."""

    def test_load_user_config(self):
        """Test loading user config returns valid data."""
        config = load_user_config("retail")
        
        # Can be dict with config or empty dict if missing
        assert isinstance(config, dict)


class TestGetFilePaths:
    """Tests for get_file_paths function."""

    def test_file_paths_retail(self):
        """Test file paths for retail mode."""
        coords_path, legacy_path = get_file_paths("retail")
        
        assert "retail" in coords_path.name
        assert "retail" in legacy_path.name

    def test_file_paths_echoes(self):
        """Test file paths for echoes mode."""
        coords_path, legacy_path = get_file_paths("echoes")
        
        assert "echoes" in coords_path.name
        assert "echoes" in legacy_path.name
