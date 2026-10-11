"""Tests for identity-variable extraction from OCR text (db_sqlite).

The game renders ``${PLAYER}``, ``${RACE}`` and ``${CLASS}`` on screen,
so the OCR text contains the actual values. These tests verify that the
alignment-based extraction recovers them, and that replacement falls
back gracefully through config values to the generic defaults.
"""

from src.db_sqlite import _extract_var_values, _replace_player_vars


class TestExtractVarValues:
    """Tests for _extract_var_values."""

    def test_clean_player_name(self):
        db = "Welcome to Hobbiton, ${PLAYER}. It is good to see you."
        ocr = "Welcome to Hobbiton, Luke. It is good to see you."
        values = _extract_var_values(ocr, db)
        assert values["${PLAYER}"] == "Luke"
        assert values["${PLAYER_NAME}"] == "Luke"

    def test_race_and_class(self):
        db = (
            "Thank you, ${RACE}. Your efforts are much appreciated, ${CLASS}."
        )
        ocr = "Thank you, Elf. Your efforts are much appreciated, Hunter."
        values = _extract_var_values(ocr, db)
        assert values["${RACE}"] == "Elf"
        assert values["${CLASS}"] == "Hunter"

    def test_var_at_start(self):
        db = "${RACE}, you are real... my eyes are not deceived!"
        ocr = "Elf, you are real... my eyes are not deceived!"
        values = _extract_var_values(ocr, db)
        assert values["${RACE}"] == "Elf"

    def test_ocr_noise_in_anchor(self):
        db = "Welcome to Hobbiton, ${PLAYER}. It's always nice to see new folk."
        ocr = "We1come to Hobb1ton, Luke. It's always nice to see new folk."
        values = _extract_var_values(ocr, db)
        assert values["${PLAYER}"] == "Luke"

    def test_multiple_occurrences_use_first(self):
        db = "${PLAYER}, I need your help. Please hurry, ${PLAYER}!"
        ocr = "Luke, I need your help. Please hurry, Luke!"
        values = _extract_var_values(ocr, db)
        assert values["${PLAYER}"] == "Luke"

    def test_multi_word_name(self):
        db = "Well met, ${PLAYER}. The road is long."
        ocr = "Well met, Throrin Oakenshield. The road is long."
        values = _extract_var_values(ocr, db)
        assert values["${PLAYER}"] == "Throrin Oakenshield"

    def test_no_vars_returns_empty(self):
        assert _extract_var_values("Hello there", "Hello there") == {}

    def test_unrelated_ocr_returns_empty(self):
        db = "Welcome to Hobbiton, ${PLAYER}."
        ocr = "Completely unrelated text here."
        assert _extract_var_values(ocr, db) == {}

    def test_empty_inputs(self):
        assert _extract_var_values("", "${PLAYER}") == {}
        assert _extract_var_values("some text", "") == {}


class TestReplacePlayerVars:
    """Tests for _replace_player_vars."""

    def test_extracted_values(self):
        text = "Welcome, ${PLAYER}! Go forth, ${CLASS}."
        values = {"${PLAYER}": "Luke", "${CLASS}": "Hunter"}
        assert _replace_player_vars(text, values) == "Welcome, Luke! Go forth, Hunter."

    def test_config_fallback(self):
        text = "Welcome, ${PLAYER} the ${RACE}!"
        fallbacks = {"${PLAYER}": "Luke", "${RACE}": "Elf"}
        assert _replace_player_vars(text, {}, fallbacks) == "Welcome, Luke the Elf!"

    def test_last_resort_defaults(self):
        assert _replace_player_vars("Hello, ${PLAYER}.", {}) == "Hello, Traveler."
        assert _replace_player_vars("Hello, ${RACE}.", {}) == "Hello, adventurer."
        assert _replace_player_vars("Hello, ${CLASS}.", {}) == "Hello, adventurer."

    def test_empty_config_fallback_is_ignored(self):
        # Empty configured values must fall through to the generic default
        fallbacks = {"${PLAYER}": "", "${RACE}": ""}
        assert _replace_player_vars("${PLAYER}", {}, fallbacks) == "Traveler"
        assert _replace_player_vars("${RACE}", {}, fallbacks) == "adventurer"

    def test_extraction_beats_config(self):
        text = "Welcome, ${PLAYER}."
        values = {"${PLAYER}": "Luke"}
        fallbacks = {"${PLAYER}": "ConfiguredName"}
        assert _replace_player_vars(text, values, fallbacks) == "Welcome, Luke."
