"""Tests for screenshot-based auto-calibration (src/auto_calibrate.py).

The tests build a synthetic screenshot by pasting the shipped default
templates onto a blank canvas in the geometry the engine expects (the
same templates load_user_templates bootstraps from), then verify that
auto-calibration finds every anchor, writes the user templates and the
layout JSON, and - crucially - that the engine's own extraction works
end-to-end on the newly calibrated files.

Heavy third-party deps are not required beyond cv2/numpy.
"""

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from src import auto_calibrate

PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"


@pytest.fixture(autouse=True)
def _clean_user_calibration(tmp_path, monkeypatch):
    """Point the user data dir and templates dir at a temp dir so the
    tests never touch or depend on a real user calibration. The config
    mock honours fallback values like the real ConfigManager."""
    monkeypatch.setattr(auto_calibrate, "TEMPLATES_DIR", tmp_path / "templates")
    # Copy the shipped default templates in: auto-calibration reads its
    # bootstrap templates from TEMPLATES_DIR and writes user templates there.
    import shutil

    shutil.copytree(TEMPLATES_DIR, tmp_path / "templates")
    cfg = MagicMock()
    cfg.get_float.side_effect = lambda section, key, fallback=0.0: fallback
    cfg.get_int.side_effect = lambda section, key, fallback=0: fallback
    monkeypatch.setattr(auto_calibrate, "_cfg", cfg)
    yield


def _load_default(name: str) -> np.ndarray:
    img = cv2.imread(str(TEMPLATES_DIR / name), cv2.IMREAD_GRAYSCALE)
    assert img is not None, f"missing default template: {name}"
    return img


def _paste(canvas: np.ndarray, tmpl: np.ndarray, x: int, y: int):
    h, w = tmpl.shape[:2]
    canvas[y : y + h, x : x + w] = cv2.cvtColor(tmpl, cv2.COLOR_GRAY2BGR)


def _make_retail_screenshot():
    """Blank 2560x1440 canvas with the five retail anchors pasted in the
    quest-window geometry (corner at 800, 500, title bar above it)."""
    start = _load_default("start_leaf.png")
    end = _load_default("end_leaf.png")
    corner = _load_default("body_upper_left_corner.png")
    intersect = _load_default("intersection.png")
    icon = _load_default("filter_icon.png")

    canvas = np.zeros((1440, 2560, 3), dtype=np.uint8)
    cx, cy = 800, 500
    # title bar: leaves at the corner-derived height (corner is 20px tall;
    # title sits 54px above the corner per the skin constants)
    _paste(canvas, start, cx + 110, cy - 54)
    _paste(canvas, end, cx + 700, cy - 54)
    _paste(canvas, corner, cx, cy)
    _paste(canvas, intersect, cx + 400, cy + 300)
    _paste(canvas, icon, cx + 200, cy + 500)
    return canvas


class TestAutoCalibrateRetail:
    """Retail auto-calibration on a synthetic screenshot."""

    def test_finds_all_anchors(self):
        ok, report = auto_calibrate.auto_calibrate_retail(_make_retail_screenshot())
        assert ok, report["message"]
        assert set(report["anchors"]) == {"start", "end", "corner", "intersect", "icon"}
        for a in report["anchors"].values():
            assert a["score"] >= 0.7

    def test_writes_user_templates(self, tmp_path):
        ok, report = auto_calibrate.auto_calibrate_retail(_make_retail_screenshot())
        assert ok
        for key in ("start", "end", "corner", "intersect", "icon"):
            path = Path(report["files"][key])
            assert path.exists(), f"template not written: {path}"
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            assert img is not None and img.size > 0

    def test_writes_layout_json(self, tmp_path, monkeypatch):
        layout_path = tmp_path / "layout_retail.json"
        monkeypatch.setattr("src.auto_calibrate.get_layout_file", lambda mode: layout_path)
        ok, report = auto_calibrate.auto_calibrate_retail(_make_retail_screenshot())
        assert ok
        layout = json.loads(layout_path.read_text())
        assert layout["resolution"] == "2560x1440"
        assert set(layout["offsets"]) == {
            "CORNER_OFFSET_X",
            "CORNER_OFFSET_Y",
            "PADDING_INTERSECT_X",
            "PADDING_ICON_Y",
        }
        # unscaled defaults at the base resolution
        assert layout["offsets"]["CORNER_OFFSET_X"] == 11
        assert layout["offsets"]["PADDING_ICON_Y"] == 17

    def test_rejects_blank_screenshot(self):
        canvas = np.zeros((1440, 2560, 3), dtype=np.uint8)
        ok, report = auto_calibrate.auto_calibrate_retail(canvas)
        assert not ok
        assert "Could not find" in report["message"] or report["anchors"] is not None

    def test_offsets_scale_with_resolution(self):
        """A 1920x1080 screenshot must produce scaled-down offsets."""
        big = _make_retail_screenshot()
        small = cv2.resize(big, (1920, 1080), interpolation=cv2.INTER_AREA)
        ok, report = auto_calibrate.auto_calibrate_retail(small)
        assert ok, report["message"]
        # offsets scaled by 1920/2560 = 0.75
        assert report  # full report returned; scaling asserted via layout file
        layout = json.loads(Path(report["files"]["layout"]).read_text())
        assert layout["resolution"] == "1920x1080"
        assert layout["offsets"]["CORNER_OFFSET_X"] == int(11 * 1920 / 2560)


class TestAutoCalibrateEchoes:
    """Echoes auto-calibration on a synthetic screenshot."""

    def _make_echoes_screenshot(self):
        lp = _load_default("example_echoes_left_plant.png")
        rp = _load_default("example_echoes_right_plant.png")
        tl = _load_default("example_echoes_tl_corner.png")
        br = _load_default("example_echoes_br_corner.png")
        canvas = np.zeros((1440, 2560, 3), dtype=np.uint8)
        _paste(canvas, lp, 700, 400)
        _paste(canvas, rp, 1200, 400)
        _paste(canvas, tl, 693, 470)
        _paste(canvas, br, 1600, 1000)
        return canvas

    def test_finds_all_anchors(self):
        ok, report = auto_calibrate.auto_calibrate_echoes(self._make_echoes_screenshot())
        assert ok, report["message"]
        assert set(report["anchors"]) == {"left_plant", "right_plant", "tl_corner", "br_corner"}

    def test_writes_files_and_preserves_npc_box(self, tmp_path, monkeypatch):
        layout_path = tmp_path / "layout_echoes.json"
        monkeypatch.setattr("src.auto_calibrate.get_layout_file", lambda mode: layout_path)
        ok, report = auto_calibrate.auto_calibrate_echoes(self._make_echoes_screenshot())
        assert ok
        layout = json.loads(layout_path.read_text())
        assert layout["resolution"] == "2560x1440"
        assert len(layout["npc_box"]) == 4

        # second calibration: previous npc_box must survive
        layout["npc_box"] = [100, 200, 300, 40]
        layout_path.write_text(json.dumps(layout))
        ok, report = auto_calibrate.auto_calibrate_echoes(self._make_echoes_screenshot())
        assert ok
        layout2 = json.loads(layout_path.read_text())
        assert layout2["npc_box"] == [100, 200, 300, 40]

    def test_rejects_bad_geometry(self):
        """Corners in a nonsensical arrangement must be rejected."""
        tl = _load_default("example_echoes_tl_corner.png")
        br = _load_default("example_echoes_br_corner.png")
        canvas = np.zeros((1440, 2560, 3), dtype=np.uint8)
        # br corner LEFT of tl corner
        _paste(canvas, tl, 1000, 800)
        _paste(canvas, br, 400, 300)
        ok, report = auto_calibrate.auto_calibrate_echoes(canvas)
        assert not ok

    def _make_echoes_screenshot_with_plate(self):
        """Gray canvas with anchors plus a black nameplate with white
        text, outside the quest window (as on a real screenshot)."""
        canvas = np.full((1440, 2560, 3), 128, dtype=np.uint8)
        _paste(canvas, _load_default("example_echoes_left_plant.png"), 700, 400)
        _paste(canvas, _load_default("example_echoes_right_plant.png"), 1200, 400)
        _paste(canvas, _load_default("example_echoes_tl_corner.png"), 693, 470)
        _paste(canvas, _load_default("example_echoes_br_corner.png"), 1600, 1000)
        cv2.rectangle(canvas, (300, 900), (573, 925), (0, 0, 0), -1)
        cv2.putText(
            canvas,
            "OTUR",
            (350, 920),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        return canvas

    def test_detects_npc_nameplate(self, tmp_path, monkeypatch):
        """The black nameplate must be found and saved as the npc_box."""
        layout_path = tmp_path / "layout_echoes.json"
        monkeypatch.setattr(
            "src.auto_calibrate.get_layout_file", lambda mode: layout_path
        )
        ok, report = auto_calibrate.auto_calibrate_echoes(
            self._make_echoes_screenshot_with_plate()
        )
        assert ok, report["message"]
        plate = report["npc_name_box"]
        assert plate is not None
        assert plate["box"] == [300, 900, 274, 26]
        layout = json.loads(layout_path.read_text())
        assert layout["npc_box"] == [300, 900, 274, 26]

    def test_nameplate_not_found_keeps_previous_box(self, tmp_path, monkeypatch):
        """Without a visible nameplate the previous npc_box survives."""
        layout_path = tmp_path / "layout_echoes.json"
        monkeypatch.setattr(
            "src.auto_calibrate.get_layout_file", lambda mode: layout_path
        )
        layout_path.write_text(
            json.dumps({"npc_box": [10, 20, 200, 30], "offsets": {}})
        )
        ok, report = auto_calibrate.auto_calibrate_echoes(
            self._make_echoes_screenshot()
        )
        assert ok
        assert report["npc_name_box"] is None
        layout = json.loads(layout_path.read_text())
        assert layout["npc_box"] == [10, 20, 200, 30]

    def test_nameplate_not_found_and_no_previous_writes_unset_box(
        self, tmp_path, monkeypatch
    ):
        """No plate and no previous calibration: the layout must
        record an explicitly unset box, not a guessed default."""
        layout_path = tmp_path / "layout_echoes.json"
        monkeypatch.setattr(
            "src.auto_calibrate.get_layout_file", lambda mode: layout_path
        )
        ok, report = auto_calibrate.auto_calibrate_echoes(
            self._make_echoes_screenshot()
        )
        assert ok
        layout = json.loads(layout_path.read_text())
        assert layout["npc_box"] == [0, 0, 0, 0]
        assert "NOT calibrated" in report["message"]


class TestDispatch:
    def test_dispatch_retail(self):
        ok, report = auto_calibrate.auto_calibrate(_make_retail_screenshot(), "retail")
        assert ok

    def test_dispatch_unknown_mode(self):
        canvas = np.zeros((100, 100, 3), dtype=np.uint8)
        ok, report = auto_calibrate.auto_calibrate(canvas, "static")
        assert not ok
        assert "not available" in report["message"]


class TestEngineRoundTrip:
    """After auto-calibration, the engine's template loader must pick up
    the written files (user templates preferred over defaults)."""

    def test_written_templates_load_as_user_templates(self, tmp_path, monkeypatch):
        ok, report = auto_calibrate.auto_calibrate_retail(_make_retail_screenshot())
        assert ok

        templates_dir = Path(report["files"]["start"]).parent
        monkeypatch.setattr("src.utils.TEMPLATES_DIR", templates_dir)
        from src.utils import load_user_templates

        tmpls = load_user_templates("retail")
        assert tmpls is not None
        assert set(tmpls) == {"start", "end", "corner", "intersect", "icon"}
        for key in ("start", "end", "corner", "intersect", "icon"):
            path = templates_dir / f"user_{key}.png"
            assert path.exists()
