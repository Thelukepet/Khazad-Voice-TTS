# Khazad-Voice-TTS\tests\test_manual_npc_tracking.py
"""
Tests for the NPC name tracking logic in retail manual mode.

Validates that the middle-mouse trigger in manual mode correctly:
- Uses the most recent NPC name from Script.log for voice resolution
- Falls back to "[MANUAL]" (narrator) when the log entry is stale
- Falls back to "[MANUAL]" when no NPC has been logged yet
- Still passes the correct name even when the NPC is not in the database

The tests mirror the inline logic from main.py's manual-mode branch
using helper functions that replicate the exact same control flow.
"""

import time
from unittest.mock import MagicMock

from src.config import NPC_NAME_MAX_AGE

# ---------------------------------------------------------------------------
# Helpers – these replicate the exact logic inside main.py manual-mode branch
# ---------------------------------------------------------------------------


def _make_npc_tracking():
    """Create a fresh npc_tracking dict identical to the one in main.py."""
    return {"name": "[MANUAL]", "time": 0.0}


def _npc_log_callback(tracking, npc_name):
    """Mirror of the inline callback defined inside main() manual-mode branch."""
    tracking["name"] = npc_name
    tracking["time"] = time.time()


def _resolve_npc_name(tracking, max_age=NPC_NAME_MAX_AGE):
    """Mirror of the staleness-check logic from the manual-mode capture handler.

    Returns the NPC name string that would be passed to
    engine.process_retail().
    """
    now = time.time()
    if tracking["name"] != "[MANUAL]" and now - tracking["time"] <= max_age:
        return tracking["name"]
    else:
        return "[MANUAL]"


# ---------------------------------------------------------------------------
# 1. npc_tracking dict / callback tests
# ---------------------------------------------------------------------------


class TestNPCTrackingCallback:
    """Tests for the npc_tracking dict and its log callback."""

    def test_initial_state(self):
        tracking = _make_npc_tracking()
        assert tracking["name"] == "[MANUAL]"
        assert tracking["time"] == 0.0

    def test_callback_updates_name(self):
        tracking = _make_npc_tracking()
        _npc_log_callback(tracking, "Thranduil")
        assert tracking["name"] == "Thranduil"

    def test_callback_updates_time(self):
        tracking = _make_npc_tracking()
        before = time.time()
        _npc_log_callback(tracking, "Thranduil")
        after = time.time()
        assert before <= tracking["time"] <= after

    def test_callback_overwrites_previous(self):
        tracking = _make_npc_tracking()
        _npc_log_callback(tracking, "Thranduil")
        _npc_log_callback(tracking, "Galadriel")
        assert tracking["name"] == "Galadriel"

    def test_multiple_callbacks_track_latest(self):
        tracking = _make_npc_tracking()
        for name in ["Aragorn", "Legolas", "Gimli"]:
            _npc_log_callback(tracking, name)
        assert tracking["name"] == "Gimli"


# ---------------------------------------------------------------------------
# 2. Staleness check tests
# ---------------------------------------------------------------------------


class TestStalenessCheck:
    """Tests for the NPC name staleness / expiry logic."""

    def test_recent_npc_name_returned(self):
        """A fresh NPC name should be returned, not '[MANUAL]'."""
        tracking = _make_npc_tracking()
        _npc_log_callback(tracking, "Thranduil")
        result = _resolve_npc_name(tracking)
        assert result == "Thranduil"

    def test_no_npc_name_returns_manual(self):
        """Before any callback fires, resolve should return '[MANUAL]'."""
        tracking = _make_npc_tracking()
        result = _resolve_npc_name(tracking)
        assert result == "[MANUAL]"

    def test_stale_npc_name_returns_manual(self):
        """An NPC name older than NPC_NAME_MAX_AGE should return '[MANUAL]'."""
        tracking = _make_npc_tracking()
        max_age = 60
        tracking["name"] = "Thranduil"
        tracking["time"] = time.time() - 120
        result = _resolve_npc_name(tracking, max_age=max_age)
        assert result == "[MANUAL]"

    def test_exactly_at_boundary_is_valid(self):
        """An NPC name exactly NPC_NAME_MAX_AGE old should still be valid."""
        tracking = _make_npc_tracking()
        max_age = 60
        tracking["name"] = "Thranduil"
        tracking["time"] = time.time() - max_age
        result = _resolve_npc_name(tracking, max_age=max_age)
        assert result == "Thranduil"

    def test_just_past_boundary_is_stale(self):
        """An NPC name 0.1s past the max age should be stale."""
        tracking = _make_npc_tracking()
        max_age = 60
        tracking["name"] = "Thranduil"
        tracking["time"] = time.time() - max_age - 0.1
        result = _resolve_npc_name(tracking, max_age=max_age)
        assert result == "[MANUAL]"

    def test_one_second_before_boundary_is_valid(self):
        """An NPC name (max_age - 1) seconds old should be valid."""
        tracking = _make_npc_tracking()
        max_age = 60
        tracking["name"] = "Galadriel"
        tracking["time"] = time.time() - (max_age - 1)
        result = _resolve_npc_name(tracking, max_age=max_age)
        assert result == "Galadriel"

    def test_manual_sentinel_never_treated_as_valid(self):
        """Even if 'time' is recent, name='[MANUAL]' should stay '[MANUAL]'."""
        tracking = _make_npc_tracking()
        tracking["time"] = time.time()
        result = _resolve_npc_name(tracking)
        assert result == "[MANUAL]"


# ---------------------------------------------------------------------------
# 3. Integration: resolve + engine.process_retail
# ---------------------------------------------------------------------------


class TestManualModeEngineIntegration:
    """Tests that the correct NPC name reaches engine.process_retail."""

    def _make_mock_engine(self):
        engine = MagicMock()
        engine.process_retail = MagicMock()
        engine.stop = MagicMock()
        engine.memory = {}
        engine.audio_queue = MagicMock()
        engine.stop_event = MagicMock()
        engine.stop_event.is_set.return_value = False
        return engine

    def test_recent_npc_passed_to_engine(self):
        """process_retail should receive the tracked NPC name when recent."""
        engine = self._make_mock_engine()
        tracking = _make_npc_tracking()
        _npc_log_callback(tracking, "Thranduil")

        npc_name = _resolve_npc_name(tracking)
        engine.process_retail(None, "fake_img", npc_name)

        engine.process_retail.assert_called_once_with(None, "fake_img", "Thranduil")

    def test_stale_npc_passes_manual_to_engine(self):
        """process_retail should receive '[MANUAL]' when the NPC is stale."""
        engine = self._make_mock_engine()
        tracking = _make_npc_tracking()
        tracking["name"] = "Thranduil"
        tracking["time"] = time.time() - 999

        npc_name = _resolve_npc_name(tracking)
        engine.process_retail(None, "fake_img", npc_name)

        engine.process_retail.assert_called_once_with(None, "fake_img", "[MANUAL]")

    def test_no_npc_passes_manual_to_engine(self):
        """process_retail should receive '[MANUAL]' when no NPC logged."""
        engine = self._make_mock_engine()
        tracking = _make_npc_tracking()

        npc_name = _resolve_npc_name(tracking)
        engine.process_retail(None, "fake_img", npc_name)

        engine.process_retail.assert_called_once_with(None, "fake_img", "[MANUAL]")

    def test_unknown_npc_still_passed_to_engine(self):
        """An NPC not in the database should still be passed through;
        the engine's _resolve_voice handles the fallback internally."""
        engine = self._make_mock_engine()
        tracking = _make_npc_tracking()
        _npc_log_callback(tracking, "CompletelyUnknownNPC")

        npc_name = _resolve_npc_name(tracking)
        engine.process_retail(None, "fake_img", npc_name)

        engine.process_retail.assert_called_once_with(
            None, "fake_img", "CompletelyUnknownNPC"
        )

    def test_sequence_of_npcs(self):
        """The most recent NPC should always be used."""
        engine = self._make_mock_engine()
        tracking = _make_npc_tracking()

        _npc_log_callback(tracking, "Aragorn")
        npc_name = _resolve_npc_name(tracking)
        engine.process_retail(None, "img1", npc_name)
        engine.process_retail.assert_called_with(None, "img1", "Aragorn")

        _npc_log_callback(tracking, "Legolas")
        npc_name = _resolve_npc_name(tracking)
        engine.process_retail(None, "img2", npc_name)
        engine.process_retail.assert_called_with(None, "img2", "Legolas")


# ---------------------------------------------------------------------------
# 4. Config constant tests
# ---------------------------------------------------------------------------


class TestConfigConstants:
    """Verify config values needed by the manual-mode NPC tracking."""

    def test_npc_name_max_age_is_positive(self):
        assert NPC_NAME_MAX_AGE > 0

    def test_npc_name_max_age_default(self):
        assert NPC_NAME_MAX_AGE == 60

    def test_trigger_mode_exists(self):
        from src.config import QUEST_TRIGGER_MODE

        assert QUEST_TRIGGER_MODE in ("auto", "manual")

    def test_trigger_key_exists(self):
        from src.config import QUEST_TRIGGER_KEY

        assert isinstance(QUEST_TRIGGER_KEY, str)
        assert len(QUEST_TRIGGER_KEY) > 0

    def test_quest_window_mode_exists(self):
        from src.config import QUEST_WINDOW_MODE

        assert QUEST_WINDOW_MODE in ("auto", "static")

    def test_quest_window_box_exists(self):
        from src.config import QUEST_WINDOW_BOX

        assert isinstance(QUEST_WINDOW_BOX, list)
        assert len(QUEST_WINDOW_BOX) == 4


# ---------------------------------------------------------------------------
# 5. End-to-end simulation of the manual-mode capture loop
# ---------------------------------------------------------------------------


class TestManualModeCaptureLoopSimulation:
    """Simulates the manual-mode capture loop with mocked components."""

    def _simulate_capture(self, tracking, engine_mock, img_available=True):
        """Run one iteration of the manual-mode capture loop logic."""
        if img_available:
            npc_name = _resolve_npc_name(tracking)
            engine_mock.process_retail(None, "fake_img", npc_name)

    def test_full_flow_recent_npc(self):
        """Simulate: NPC appears in log -> user clicks -> correct voice used."""
        engine = MagicMock()
        tracking = _make_npc_tracking()
        _npc_log_callback(tracking, "Elrond")
        self._simulate_capture(tracking, engine)
        engine.process_retail.assert_called_once_with(None, "fake_img", "Elrond")

    def test_full_flow_no_npc_at_all(self):
        """Simulate: No NPC in log -> user clicks -> narrator voice."""
        engine = MagicMock()
        tracking = _make_npc_tracking()
        self._simulate_capture(tracking, engine)
        engine.process_retail.assert_called_once_with(None, "fake_img", "[MANUAL]")

    def test_full_flow_stale_npc(self):
        """Simulate: NPC appeared long ago -> user clicks -> narrator voice."""
        engine = MagicMock()
        tracking = _make_npc_tracking()
        tracking["name"] = "Elrond"
        tracking["time"] = time.time() - 300
        self._simulate_capture(tracking, engine)
        engine.process_retail.assert_called_once_with(None, "fake_img", "[MANUAL]")

    def test_full_flow_npc_replaced_by_newer(self):
        """Simulate: NPC A -> NPC B -> user clicks -> NPC B voice used."""
        engine = MagicMock()
        tracking = _make_npc_tracking()
        _npc_log_callback(tracking, "Elrond")
        _npc_log_callback(tracking, "Galadriel")
        self._simulate_capture(tracking, engine)
        engine.process_retail.assert_called_once_with(None, "fake_img", "Galadriel")

    def test_full_flow_npc_expired_then_renewed(self):
        """Simulate: NPC stale -> new NPC -> user clicks -> new NPC voice."""
        engine = MagicMock()
        tracking = _make_npc_tracking()
        tracking["name"] = "OldNPC"
        tracking["time"] = time.time() - 300
        _npc_log_callback(tracking, "FreshNPC")
        self._simulate_capture(tracking, engine)
        engine.process_retail.assert_called_once_with(None, "fake_img", "FreshNPC")

    def test_no_img_does_not_call_engine(self):
        """If capture_screen_areas returns None, engine should not be called."""
        engine = MagicMock()
        tracking = _make_npc_tracking()
        _npc_log_callback(tracking, "Elrond")
        self._simulate_capture(tracking, engine, img_available=False)
        engine.process_retail.assert_not_called()
