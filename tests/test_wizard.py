"""Tests for the first-run wizard."""

import io
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Stub heavy deps so imports work without torch installed
if "torch" not in sys.modules:
    torch_stub = types.ModuleType("torch")
    torch_stub.cuda = MagicMock()
    torch_stub.cuda.is_available = lambda: False
    sys.modules["torch"] = torch_stub

from src.config.ConfigManager import ConfigManager  # noqa: E402
from src.wizard import (  # noqa: E402
    _ask,
    _device_choice,
    _game_mode_choice,
    _identity_choice,
    ensure_player_identity,
)


class TestAskHelper:
    def test_default_on_empty_input(self):
        with patch("builtins.input", return_value=""):
            assert _ask("Go? [Y/n]: ", choices=["y", "n"], default="y") == "y"

    def test_numeric_alias_selects_choice(self):
        with patch("builtins.input", return_value="2"):
            assert _ask("Pick: ", choices=["retail", "echoes"]) == "echoes"

    def test_case_insensitive(self):
        with patch("builtins.input", return_value="Y"):
            assert _ask("Go? ", choices=["y", "n"]) == "y"

    def test_reasks_on_invalid(self):
        answers = iter(["banana", "1"])
        with patch("builtins.input", side_effect=lambda _: next(answers)):
            assert _ask("Pick: ", choices=["retail", "echoes"]) == "retail"


class TestDeviceChoice:
    def test_gpu_detected_defaults_gpu(self):
        with patch("src.wizard._detect_gpu", return_value=True), patch(
            "builtins.input", return_value=""
        ):
            assert _device_choice() == "gpu"

    def test_no_gpu_forces_cpu(self):
        with patch("src.wizard._detect_gpu", return_value=False), patch(
            "builtins.input", return_value=""
        ):
            assert _device_choice() == "cpu"

    def test_gpu_user_declines_cpu(self):
        with patch("src.wizard._detect_gpu", return_value=True), patch(
            "builtins.input", return_value="n"
        ):
            assert _device_choice() == "cpu"


class TestGameModeChoice:
    def test_default_retail(self):
        with patch("builtins.input", return_value=""):
            assert _game_mode_choice() == "retail"

    def test_echoes(self):
        with patch("builtins.input", return_value="2"):
            assert _game_mode_choice() == "echoes"


class TestWizardFlow:
    def test_maybe_run_wizard_first_run(self, tmp_path):
        """No stored game mode -> wizard launches."""
        from src import wizard as wz

        cfg = MagicMock()
        cfg.config = MagicMock()
        cfg.config.get.return_value = None  # no stored mode

        with patch("src.wizard.ConfigManager", return_value=cfg), patch(
            "src.wizard.run_wizard"
        ) as rw, patch("sys.argv", ["khazad"]):
            assert wz.maybe_run_wizard() is True
            rw.assert_called_once()

    def test_maybe_run_wizard_skips_when_configured(self):
        """Stored game mode and no --setup -> wizard skipped."""
        from src import wizard as wz

        cfg = MagicMock()
        cfg.config = MagicMock()
        cfg.config.get.return_value = "retail"

        with patch("src.wizard.ConfigManager", return_value=cfg), patch(
            "sys.argv", ["khazad"]
        ):
            assert wz.maybe_run_wizard() is False

    def test_setup_flag_forces_wizard(self):
        from src import wizard as wz

        cfg = MagicMock()
        cfg.config = MagicMock()
        cfg.config.get.return_value = "retail"

        with patch("src.wizard.ConfigManager", return_value=cfg), patch(
            "src.wizard.run_wizard"
        ) as rw, patch("sys.argv", ["khazad", "--setup"]):
            assert wz.maybe_run_wizard() is True
            rw.assert_called_once()


class _FakeConfig:
    """Minimal ConfigManager stand-in backed by a real INI file."""

    def __init__(self, path):
        import configparser

        self.config = configparser.ConfigParser()
        self.config_path = str(path)

    def get_str(self, section, key, fallback=""):
        try:
            return self.config.get(section, key, fallback=fallback)
        except Exception:
            return fallback


class TestIdentityChoice:
    def test_prompts_and_stores(self, tmp_path):
        cfg = _FakeConfig(tmp_path / "config.ini")
        answers = iter(["Luke", "2", "3"])  # name, Elf, Hunter

        with patch("src.wizard.ConfigManager", return_value=cfg), patch(
            "builtins.input", side_effect=lambda _: next(answers)
        ):
            _identity_choice()

        assert cfg.get_str("PlayerIdentity", "character_name") == "Luke"
        assert cfg.get_str("PlayerIdentity", "character_race") == "Elf"
        assert cfg.get_str("PlayerIdentity", "character_class") == "Hunter"

    def test_existing_values_are_defaults(self, tmp_path):
        """Re-running the wizard keeps stored values on Enter."""
        cfg = _FakeConfig(tmp_path / "config.ini")
        cfg.config.add_section("PlayerIdentity")
        cfg.config.set("PlayerIdentity", "character_name", "Luke")
        cfg.config.set("PlayerIdentity", "character_race", "Elf")
        cfg.config.set("PlayerIdentity", "character_class", "Hunter")

        with patch("src.wizard.ConfigManager", return_value=cfg), patch(
            "builtins.input", side_effect=lambda _: ""
        ):
            _identity_choice()

        assert cfg.get_str("PlayerIdentity", "character_name") == "Luke"
        assert cfg.get_str("PlayerIdentity", "character_race") == "Elf"
        assert cfg.get_str("PlayerIdentity", "character_class") == "Hunter"

    def test_empty_name_reasks(self, tmp_path):
        cfg = _FakeConfig(tmp_path / "config.ini")
        answers = iter(["", "Luke", "1", "1"])

        with patch("src.wizard.ConfigManager", return_value=cfg), patch(
            "builtins.input", side_effect=lambda _: next(answers)
        ):
            _identity_choice()

        assert cfg.get_str("PlayerIdentity", "character_name") == "Luke"


class TestEnsurePlayerIdentity:
    def test_skips_when_name_configured(self, tmp_path):
        cfg = _FakeConfig(tmp_path / "config.ini")
        cfg.config.add_section("PlayerIdentity")
        cfg.config.set("PlayerIdentity", "character_name", "Luke")

        with patch("src.wizard.ConfigManager", return_value=cfg), patch(
            "src.wizard._identity_choice"
        ) as ic:
            ensure_player_identity()
            ic.assert_not_called()

    def test_prompts_when_name_missing(self, tmp_path):
        cfg = _FakeConfig(tmp_path / "config.ini")

        with patch("src.wizard.ConfigManager", return_value=cfg), patch(
            "src.wizard._identity_choice"
        ) as ic:
            ensure_player_identity()
            ic.assert_called_once()

    def test_never_raises_on_config_error(self):
        with patch(
            "src.wizard.ConfigManager", side_effect=RuntimeError("boom")
        ):
            ensure_player_identity()  # must not raise
