# Testing Guide

This document describes the testing setup for Khazad-Voice TTS.

## Running Tests

### Run all tests
```bash
pytest
```

### Run with verbose output
```bash
pytest -v
```

### Run specific test file
```bash
pytest tests/test_models.py -v
```

### Run specific test class
```bash
pytest tests/test_models.py::TestQuestText -v
```

### Run specific test function
```bash
pytest tests/test_models.py::TestQuestText::test_quest_text_get_line -v
```

### Run tests by marker
```bash
# Run only slow tests
pytest -m slow -v

# Run only integration tests
pytest -m integration -v

# Skip slow tests
pytest -m "not slow" -v
```

## Test Coverage

### test_models.py
Tests for the dataclass models:
- `TestNPC` - NPC model creation and methods
- `TestQuestTextLine` - Quest text line creation
- `TestQuestText` - Quest text model and methods
- `TestVoiceSelection` - Voice selection model
- `TestTextSourceType` - Enum tests

### test_engine.py
Tests for the NarratorEngine:
- `TestNarratorEngine` - Engine initialization, voice resolution, streaming
- `TestEngineIntegration` - Integration tests for quest text handling

### test_utils.py
Tests for utility functions:
- `TestMemoryFunctions` - NPC memory load/save
- `TestTemplateFunctions` - Template loading
- `TestConfigFunctions` - Config loading
- `TestGetFilePaths` - File path generation

### test_text_splitter.py
Tests for text splitting (existing test file)

## Test Structure

Each test file follows this structure:
- Import necessary modules
- Define test classes with descriptive names
- Use `setup_method()` for test fixtures
- Use `teardown_method()` for cleanup
- Write descriptive docstrings for each test

## Adding New Tests

1. Create a new test file `tests/test_newmodule.py`
2. Import necessary modules from `src`
3. Create test classes following the pattern
4. Add test methods with descriptive names
5. Run `pytest -v` to verify tests work

## CI Integration

To add test coverage reporting:
1. Install pytest-cov: `pip install pytest-cov`
2. Uncomment the coverage line in `pytest.ini`
3. Run: `pytest --cov=src --cov-report=html`

## Fixtures

The `conftest.py` file provides shared fixtures:
- `temp_data_dir` - Temporary directory for test data
- `mock_tts_backend` - Mock TTS backend
- `mock_db` - Mock database
- `sample_quest_text` - Sample QuestText
- `sample_voice_selection` - Sample VoiceSelection
- `sample_npc` - Sample NPC
