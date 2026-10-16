"""Screenshot-based automatic calibration.

Replaces the manual calibration flow (six hand-drawn ROI boxes per game
mode) with a fully automatic one: the user provides a screenshot with the
quest window open, this module locates the same anchors the live engine
matches (leaves, body corner, intersection, filter icon / plants and
corners in Echoes mode), crops user templates from the screenshot at the
exact positions they appear on the user's system, and writes the layout
JSON - no point selection required.

Design
------
The shipped default templates, scaled to the screenshot's resolution,
are the bootstrap source: auto-calibration locates the anchors the same
way a factory-fresh install would, so a calibration succeeds precisely
when the live engine would also find the window. Existing user
templates are deliberately ignored during a fresh calibration.

Offsets are not guessed: the manual calibrator derived them from a
user-drawn text box. Instead, auto-calibration recomputes them from the
*default* offsets so the ratio between anchors and text box stays the
skin's native geometry, scaled to the screenshot resolution. This is the
same geometry ``load_user_config`` falls back to when no layout file
exists, so a saved layout never performs worse than no layout at all.

Public entry points
-------------------
- :func:`auto_calibrate_retail` / :func:`auto_calibrate_echoes` ->
  (ok, report) with per-anchor match scores and saved file paths.
- :func:`auto_calibrate` -> mode dispatcher.

All functions write the files the engine loads directly
(``user_*.png`` / ``echoes_*.png`` and ``layout_retail.json`` /
``layout_echoes.json``), so the calibration is picked up without any
further changes.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

from src.config.ConfigManager import ConfigManager
from src.utils import (
    _CORNER_REF_HEIGHT,
    _CORNER_TO_END_LEAF_DY,
    TEMPLATES_DIR,
    get_layout_file,
    load_scaled_template,
    match_template_in_roi,
    match_template_in_roi_multiscale,
)

_cfg = ConfigManager()

# Shipped default templates - the bootstrap source for calibration (a
# screenshot may be calibrated before any user calibration exists, and
# existing user templates must never influence where the anchors are
# searched for a fresh calibration).
_DEFAULT_FILES_RETAIL = {
    "start": "start_leaf.png",
    "end": "end_leaf.png",
    "corner": "body_upper_left_corner.png",
    "intersect": "intersection.png",
    "icon": "filter_icon.png",
}
_DEFAULT_FILES_ECHOES = {
    "left_plant": "example_echoes_left_plant.png",
    "right_plant": "example_echoes_right_plant.png",
    "tl_corner": "example_echoes_tl_corner.png",
    "br_corner": "example_echoes_br_corner.png",
}

# The engine loads these files transparently via
# load_user_templates().
_USER_PATHS_RETAIL = {
    "start": "user_start.png",
    "end": "user_end.png",
    "corner": "user_corner.png",
    "intersect": "user_intersect.png",
    "icon": "user_icon.png",
}
_USER_PATHS_ECHOES = {
    "left_plant": "echoes_left_plant.png",
    "right_plant": "echoes_right_plant.png",
    "tl_corner": "echoes_tl_corner.png",
    "br_corner": "echoes_br_corner.png",
}

# Geometry constants shared with the engine's corner-anchor fallback
# (see src/utils.py). The corner template's reference height (20px at
# 2560x1440) scales the fixed skin offsets to other resolutions.
_CORNER_REF_HEIGHT = 20

# How much of the window to keep around an anchor when cropping the
# user template. The manual calibrator relied on the user drawing a
# slightly generous box; a small expansion reproduces that behaviour
# without asking the user for it.
_CROP_PAD = 2


def _default_offsets(mode: str, scale: float) -> Dict[str, int]:
    """The engine's built-in default offsets, scaled like load_user_config does."""
    if mode == "retail":
        defaults = {
            "CORNER_OFFSET_X": _cfg.get_int(
                "DefaultRetailMode", "layout_corner_offset_x", fallback=11
            ),
            "CORNER_OFFSET_Y": _cfg.get_int(
                "DefaultRetailMode", "layout_corner_offset_y", fallback=10
            ),
            "PADDING_INTERSECT_X": _cfg.get_int(
                "DefaultRetailMode", "layout_padding_intersect_x", fallback=-10
            ),
            "PADDING_ICON_Y": _cfg.get_int(
                "DefaultRetailMode", "layout_padding_icon_y", fallback=17
            ),
        }
    else:
        defaults = {
            "body_left_margin": _cfg.get_int(
                "DefaultRetailOffsets", "body_left_margin", fallback=11
            ),
            "body_top_margin": _cfg.get_int(
                "DefaultRetailOffsets", "body_top_margin", fallback=10
            ),
            "body_right_padding": _cfg.get_int(
                "DefaultRetailOffsets", "body_right_padding", fallback=0
            ),
            "body_bottom_padding": _cfg.get_int(
                "DefaultRetailOffsets", "body_bottom_padding", fallback=0
            ),
        }
    return {k: int(v * scale) for k, v in defaults.items()}


def _save_template(img_bgr: np.ndarray, x: int, y: int, w: int, h: int, path: Path) -> None:
    """Crop an anchor region (grayscale) and save it as a user template."""
    ih, iw = img_bgr.shape[:2]
    x, y = max(0, x), max(0, y)
    w, h = min(w, iw - x), min(h, ih - y)
    crop = img_bgr[y : y + h, x : x + w]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), gray)


def _load_default_templates(mode: str, img_bgr: np.ndarray) -> Optional[Dict[str, np.ndarray]]:
    """Load the shipped default templates scaled to the screenshot's resolution.

    Deliberately ignores existing user templates: a fresh calibration
    must locate the anchors the same way a factory-fresh install would.
    """
    files = _DEFAULT_FILES_RETAIL if mode == "retail" else _DEFAULT_FILES_ECHOES
    resolution = (img_bgr.shape[1], img_bgr.shape[0])
    templates = {}
    for key, fname in files.items():
        path = TEMPLATES_DIR / fname
        if not path.exists():
            return None
        try:
            templates[key] = load_scaled_template(path, resolution)
        except FileNotFoundError:
            return None
    return templates


def _report(
    ok: bool,
    message: str,
    anchors: Optional[Dict[str, Dict[str, Any]]] = None,
    files: Optional[Dict[str, str]] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Build the (ok, report) result tuple."""
    return ok, {
        "ok": ok,
        "message": message,
        "anchors": anchors or {},
        "files": files or {},
    }


def auto_calibrate_retail(img_bgr: np.ndarray) -> Tuple[bool, Dict[str, Any]]:
    """Auto-calibrate retail mode from a screenshot.

    Finds the five retail anchors with the same default-template
    bootstrap the live engine uses (including the multiscale safety net
    for intersection/icon), saves cropped user templates and the layout
    JSON. The window may be anywhere on screen.

    Parameters
    ----------
    img_bgr : np.ndarray
        Full screenshot (BGR) with the quest window fully visible.

    Returns
    -------
    tuple
        (ok, report). ``report`` carries per-anchor match scores
        (``report['anchors'][key]['score']``) and the written file paths.
    """
    threshold = _cfg.get_float("Detection", "template_threshold", fallback=0.7)
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h_img, w_img = img_gray.shape

    # Default templates scaled to the screenshot resolution - the same
    # source a factory-fresh install bootstraps from.
    tmpls = _load_default_templates("retail", img_bgr)
    if not tmpls:
        return _report(False, "Default templates missing - cannot calibrate.")

    anchors: Dict[str, Dict[str, Any]] = {}

    # --- Corner first: the most stable anchor. The engine's own
    # fallback path anchors on the corner and derives the title bar
    # geometry from the fixed skin offsets, so the corner is the one
    # template that must match unconditionally.
    val_c, cx, cy = match_template_in_roi(
        img_gray, tmpls["corner"], 0, 0, w_img, h_img
    )
    if val_c <= threshold:
        return _report(
            False,
            f"The quest window was not found (body corner score "
            f"{val_c:.3f} below {threshold:.2f}). Make sure the quest "
            f"window is fully visible and not covered by other panels.",
        )
    anchors["corner"] = {"score": round(float(val_c), 3), "x": int(cx), "y": int(cy)}

    # --- Start & end leaf: search in the title band derived from the
    # corner (fixed skin geometry, see src/utils.py constants). This
    # rejects spurious full-image leaf matches on unrelated UI, and a
    # relaxed threshold (like the engine's band search) tolerates
    # partially occluded leaves. ---
    scale = tmpls["corner"].shape[0] / _CORNER_REF_HEIGHT
    band_y = int(cy - _CORNER_TO_END_LEAF_DY * scale)
    band_h = 24 + tmpls["start"].shape[0]
    for key, band_x, band_w in (
        ("start", int(cx - 60 * scale), int(400 * scale)),
        ("end", int(cx + 150 * scale), int(750 * scale)),
    ):
        val, lx, ly = match_template_in_roi(
            img_gray, tmpls[key], band_x, band_y - 12, band_w, band_h
        )
        if val < 0.5:  # engine's relaxed band threshold
            return _report(
                False,
                f"The title bar was not found ({key} leaf score {val:.3f} "
                f"in the expected band). The quest window may be partially "
                f"covered.",
                anchors,
            )
        anchors[key] = {"score": round(float(val), 3), "x": int(lx), "y": int(ly)}

    # --- Intersection (width) & icon (height), multiscale safety net ---
    val_int, ix, iy = match_template_in_roi(
        img_gray, tmpls["intersect"], cx + 50, cy - 20,
        w_img - (cx + 50), h_img - cy,
    )
    if val_int <= threshold:
        val_int, ix, iy = match_template_in_roi_multiscale(
            img_gray, tmpls["intersect"], cx + 50, cy - 20,
            w_img - (cx + 50), h_img - cy,
        )
    anchors["intersect"] = {"score": round(float(val_int), 3), "x": int(ix), "y": int(iy)}

    val_i, icx, icy = match_template_in_roi(
        img_gray, tmpls["icon"], 0, cy + 50, w_img, h_img - (cy + 50),
    )
    if val_i <= threshold:
        val_i, icx, icy = match_template_in_roi_multiscale(
            img_gray, tmpls["icon"], 0, cy + 50, w_img, h_img - (cy + 50),
        )
    anchors["icon"] = {"score": round(float(val_i), 3), "x": int(icx), "y": int(icy)}

    # --- Validation: the strict-threshold anchors must all have matched.
    # (The leaves were already validated by the band search with the
    # engine's relaxed threshold - an occluded but correctly placed leaf
    # is acceptable, exactly like in the live engine.) ---
    weak = [
        k
        for k in ("corner", "intersect", "icon")
        if anchors[k]["score"] < threshold
    ]
    if weak:
        return _report(
            False,
            f"Could not find the quest window reliably "
            f"({', '.join(k + ': ' + str(anchors[k]['score']) for k in weak)} "
            f"below {threshold:.2f}). Make sure the quest window is fully "
            f"visible and not covered by other panels.",
            anchors,
        )

    # Same plausibility checks as the engine: the two leaves must flank
    # one title bar, and the intersection/icon must sit right/below the
    # corner - otherwise a template matched on unrelated UI.
    leaf_dy = abs(anchors["start"]["y"] - anchors["end"]["y"])
    leaf_w = anchors["end"]["x"] - (anchors["start"]["x"] + tmpls["start"].shape[1])
    if leaf_dy > 10 or leaf_w <= 50:
        return _report(
            False,
            "The leaf ornaments were not found where a quest title bar "
            "would be - the window may be partially covered.",
            anchors,
        )
    if ix <= cx or icy <= cy:
        return _report(
            False,
            "The intersection and filter icon were not found where the "
            "quest window body would be - the window may be cut off.",
            anchors,
        )

    # --- Save user templates at the found positions ---
    files = {}
    for key, fname in _USER_PATHS_RETAIL.items():
        t = tmpls[key]
        a = anchors[key]
        path = TEMPLATES_DIR / fname
        _save_template(
            img_bgr,
            a["x"] - _CROP_PAD,
            a["y"] - _CROP_PAD,
            t.shape[1] + 2 * _CROP_PAD,
            t.shape[0] + 2 * _CROP_PAD,
            path,
        )
        files[key] = str(path)

    # --- Layout JSON: default skin geometry scaled to this screenshot ---
    scale = w_img / 2560.0
    offsets = _default_offsets("retail", scale)
    layout = {
        "resolution": f"{w_img}x{h_img}",
        "offsets": offsets,
    }
    layout_file = get_layout_file("retail")
    layout_file.parent.mkdir(parents=True, exist_ok=True)
    layout_file.write_text(json.dumps(layout, indent=4))
    files["layout"] = str(layout_file)

    return _report(
        True,
        "Calibration saved. The quest window can now be found anywhere on "
        "your screen.",
        anchors,
        files,
    )


def _detect_npc_nameplate(
    img_bgr: np.ndarray,
    window_rect: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[Dict[str, Any]]:
    """Find the Echoes NPC nameplate: a solid black box with bright text.

    Scans a ladder of dark thresholds so the plate is still separated
    from dark scenery (at a low threshold the plate is darker than its
    surroundings; morphological closing is deliberately avoided - it
    merges the plate into dark backgrounds, which is how the plate
    hides). Candidates are filtered by nameplate geometry and solidity,
    and must not overlap the quest window (the dark title bar looks
    similar) or the bottom UI bar. The best candidate is OCR'd for the
    report; OCR failure does not reject the box.

    Parameters
    ----------
    img_bgr : np.ndarray
        Full screenshot (BGR).
    window_rect : tuple, optional
        (x0, y0, x1, y1) quest-window bounding box (anchors + title
        bar); candidates overlapping it are ignored.

    Returns
    -------
    dict | None
        ``{"box": [x, y, w, h], "name": str}`` (name may be empty) or
        ``None`` when no nameplate is visible.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h_img, w_img = gray.shape
    wx0, wy0, wx1, wy1 = window_rect or (-1, -1, -1, -1)

    best: Optional[Dict[str, Any]] = None
    for thr in (25, 35, 45, 55, 70):
        _, mask = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        for c in contours:
            x, y, bw, bh = cv2.boundingRect(c)
            if not (100 <= bw <= 500 and 18 <= bh <= 40 and bw > 4 * bh):
                continue
            if bw * bh > 0.008 * w_img * h_img:
                continue
            if y + bh > 0.93 * h_img:  # bottom UI bar
                continue
            if x < wx1 and x + bw > wx0 and y < wy1 and y + bh > wy0:
                continue  # overlaps the quest window / title bar
            region = gray[y : y + bh, x : x + bw]
            fill = float(np.count_nonzero(mask[y : y + bh, x : x + bw])) / (bw * bh)
            if fill < 0.75 or float(region.mean()) > 45:
                continue
            if best is None or fill > best["fill"]:
                best = {"box": [int(x), int(y), int(bw), int(bh)], "fill": fill}

    if best is None:
        return None

    # Best-effort name read for the report (never rejects the box)
    name = ""
    try:
        from PIL import Image

        from src.ocr import run_nameplate_ocr

        x, y, bw, bh = best["box"]
        pad = 2
        crop = img_bgr[
            max(0, y - pad) : y + bh + pad, max(0, x - pad) : x + bw + pad
        ]
        pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        name = run_nameplate_ocr(pil)
    except Exception:
        name = ""
    best["name"] = name
    return best


def auto_calibrate_echoes(img_bgr: np.ndarray) -> Tuple[bool, Dict[str, Any]]:
    """Auto-calibrate Echoes of Angmar mode from a screenshot.

    Finds the four anchors (left/right plant, top-left/bottom-right
    corner) with the default-template bootstrap, saves user templates and
    the layout JSON. The Echoes layout JSON also stores the static NPC
    name box; auto-calibration cannot know where the NPC name panel sits
    on the user's screen, so the previous box is preserved (or a
    conservative default derived from the anchors is written on a first
    calibration).

    Parameters
    ----------
    img_bgr : np.ndarray
        Full screenshot (BGR) with the quest window fully visible.

    Returns
    -------
    tuple
        (ok, report) - same shape as :func:`auto_calibrate_retail`.
    """
    threshold = _cfg.get_float("Detection", "template_threshold", fallback=0.7)
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h_img, w_img = img_gray.shape

    tmpls = _load_default_templates("echoes", img_bgr)
    if not tmpls:
        return _report(False, "Default templates missing - cannot calibrate.")

    anchors: Dict[str, Dict[str, Any]] = {}
    for key in ("left_plant", "right_plant", "tl_corner", "br_corner"):
        res = cv2.matchTemplate(img_gray, tmpls[key], cv2.TM_CCOEFF_NORMED)
        _, val, _, loc = cv2.minMaxLoc(res)
        anchors[key] = {"score": round(float(val), 3), "x": int(loc[0]), "y": int(loc[1])}

    weak = [k for k, a in anchors.items() if a["score"] < threshold]
    if weak:
        return _report(
            False,
            f"Could not find the quest window reliably "
            f"({', '.join(k + ': ' + str(anchors[k]['score']) for k in weak)} "
            f"below {threshold:.2f}). Make sure the quest window is fully "
            f"visible.",
            anchors,
        )

    # Plausibility: tl corner above-left of br corner, plants above body.
    tl, br = anchors["tl_corner"], anchors["br_corner"]
    if br["x"] <= tl["x"] or br["y"] <= tl["y"]:
        return _report(
            False,
            "The body corners were not found in the expected arrangement - "
            "the window may be partially covered.",
            anchors,
        )

    files = {}
    for key, fname in _USER_PATHS_ECHOES.items():
        t = tmpls[key]
        a = anchors[key]
        path = TEMPLATES_DIR / fname
        _save_template(
            img_bgr,
            a["x"] - _CROP_PAD,
            a["y"] - _CROP_PAD,
            t.shape[1] + 2 * _CROP_PAD,
            t.shape[0] + 2 * _CROP_PAD,
            path,
        )
        files[key] = str(path)

    scale = w_img / 2560.0
    offsets = _default_offsets("echoes", scale)

    # NPC name box: the nameplate is a solid black box the user can
    # move in their UI, so detect it on the screenshot. Fall back to
    # the previous calibration; without one, record an explicitly
    # unset box instead of guessing a position.
    layout_file = get_layout_file("echoes")

    window_rect = (
        min(anchors["left_plant"]["x"], tl["x"]),
        min(anchors["left_plant"]["y"], tl["y"]),
        br["x"] + tmpls["br_corner"].shape[1],
        br["y"] + tmpls["br_corner"].shape[0],
    )
    plate = _detect_npc_nameplate(img_bgr, window_rect)

    npc_box: Optional[list] = None
    npc_box_source = "none"
    if plate is not None:
        # Exact box: the plate's border edge corrupts OCR reads, and
        # run_nameplate_ocr trims any slack itself.
        npc_box = [int(v) for v in plate["box"]]
        npc_box_source = "detected"
    elif layout_file.exists():
        try:
            previous = json.loads(layout_file.read_text())
            box = previous.get("npc_box")
            if isinstance(box, list) and len(box) == 4 and box[2] > 0 and box[3] > 0:
                npc_box = [int(v) for v in box]
                npc_box_source = "previous"
        except (json.JSONDecodeError, AttributeError):
            pass
    if npc_box is None:
        # No nameplate on the screenshot and no previous calibration:
        # record an explicitly unset box instead of guessing a
        # position. A guessed box silently reads scenery garbage as
        # the NPC name on every capture; an unset box makes the
        # engine skip the name read (with a log warning) until the
        # user recalibrates with the nameplate visible.
        npc_box = [0, 0, 0, 0]

    layout = {
        "resolution": f"{w_img}x{h_img}",
        "offsets": offsets,
        "npc_box": npc_box,
    }
    layout_file.parent.mkdir(parents=True, exist_ok=True)
    layout_file.write_text(json.dumps(layout, indent=4))
    files["layout"] = str(layout_file)

    if plate is not None:
        npc_msg = (
            f"NPC name box found at ({plate['box'][0]}, {plate['box'][1]}) "
            f"reading '{plate['name'] or '?'}'. Do not move the NPC name "
            f"box in your UI after calibrating."
        )
    elif npc_box_source == "previous":
        npc_msg = (
            "The NPC name box was not found on the screenshot - the "
            "previous box was kept. If the NPC name is not read "
            "correctly, retry with a screenshot where the black "
            "nameplate box is visible. Do not move the NPC name box in "
            "your UI after calibrating."
        )
    else:
        npc_msg = (
            "WARNING: the NPC name box was NOT calibrated - no "
            "nameplate was found on the screenshot and no previous "
            "calibration exists. The narrator cannot read NPC names "
            "until you recalibrate with a screenshot where the black "
            "nameplate box is visible."
        )

    ok, report = _report(
        True,
        "Calibration saved. " + npc_msg,
        anchors,
        files,
    )
    report["npc_name_box"] = plate
    return ok, report


def auto_calibrate(img_bgr: np.ndarray, mode: str = "retail") -> Tuple[bool, Dict[str, Any]]:
    """Dispatch to the per-mode auto-calibrator.

    Parameters
    ----------
    img_bgr : np.ndarray
        Full screenshot (BGR) with the quest window fully visible.
    mode : str
        ``retail`` or ``echoes``.

    Returns
    -------
    tuple
        (ok, report).
    """
    if mode == "echoes":
        return auto_calibrate_echoes(img_bgr)
    if mode == "retail":
        return auto_calibrate_retail(img_bgr)
    return _report(False, f"Auto-calibration is not available for mode '{mode}'.")
