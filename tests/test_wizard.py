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
from src.wizard import _ask, _device_choice, _game_mode_choice  # noqa: E402


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
