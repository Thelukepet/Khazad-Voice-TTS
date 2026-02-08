# Imports

# > Standard Library
import os
import json
import time
import logging
from pathlib import Path
from typing import List, Union, Tuple, Optional, Any

# > Third-party Libraries
import cv2
import numpy as np
from PIL import Image, ImageGrab

# > Local Dependencies
from .config import (
    DATA_DIR,
    LOG_LEVEL,
    TEMPLATES_DIR,
    TEMPLATE_THRESHOLD,
)

DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- CONFIGURATION FILES ---
LAYOUT_RETAIL = DATA_DIR / "layout_retail.json"
LAYOUT_ECHOES = DATA_DIR / "layout_echoes.json"


def setup_logger(name: str) -> logging.Logger:
    """Configures a standard logger outputting to console."""
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    if not logger.handlers:
        ch = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - [%(name)s] - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
        )
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger


log = setup_logger("UTILS")


# --- DATA MANAGEMENT (RESTORED) ---


def get_file_paths(mode: str) -> Tuple[Path, Path]:
    """
    Generates file paths for coordinates and NPC memory based on the mode.

    Parameters
    ----------
    mode : str
        The game mode ('retail' or 'echoes').

    Returns
    -------
    Tuple[Path, Path]
        (path_to_coords_json, path_to_npc_memory_json)
    """
    safe_mode = mode.lower().strip()
    return (
        DATA_DIR / f"coords_{safe_mode}.json",
        DATA_DIR / f"npc_memory_{safe_mode}.json",
    )


def load_coords(mode: str) -> dict:
    """
    Loads saved coordinates for the specified mode.
    """
    coords_file, _ = get_file_paths(mode)
    if coords_file.exists():
        try:
            with open(coords_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def save_coords(coords: dict, mode: str):
    """
    Saves coordinates to the disk for the specified mode.
    """
    coords_file, _ = get_file_paths(mode)
    with open(coords_file, "w") as f:
        json.dump(coords, f, indent=4)


def load_npc_memory(mode: str) -> dict:
    """
    Loads the database of previously seen NPCs (for voice consistency).
    """
    _, memory_file = get_file_paths(mode)
    if memory_file.exists():
        try:
            with open(memory_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def save_npc_memory(memory: dict, mode: str):
    """
    Saves the NPC memory database to disk.
    """
    _, memory_file = get_file_paths(mode)
    with open(memory_file, "w") as f:
        json.dump(memory, f, indent=4)


# --- CONFIGURATION LOADERS ---


def get_layout_file(mode: str) -> Path:
    """Returns the appropriate layout file path based on the game mode."""
    return LAYOUT_RETAIL if mode == "retail" else LAYOUT_ECHOES


def load_user_templates(mode: str = "retail") -> Optional[dict]:
    """
    Loads the user-calibrated templates from disk specific to the game mode.

    Parameters
    ----------
    mode : str
        The game mode ('retail' or 'echoes').

    Returns
    -------
    dict or None
        Dictionary of {key: cv2_image} or None if missing.
    """
    templates = {}

    if mode == "retail":
        keys = ["start", "end", "corner", "intersect", "icon"]
        prefix = "user"
    else:
        keys = ["left_plant", "right_plant", "tl_corner", "br_corner"]
        prefix = "echoes"

    missing = False
    for key in keys:
        path = TEMPLATES_DIR / f"{prefix}_{key}.png"
        if path.exists():
            templates[key] = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        else:
            missing = True

    if missing:
        return None
    return templates


def load_user_config(mode: str) -> dict:
    """
    Loads the calibrated configuration (offsets/NPC box) from the JSON file.
    """
    path = get_layout_file(mode)
    if path.exists():
        try:
            with open(path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {}


# --- LOG WATCHER (Retail Only) ---


def watch_npc_file(callback, log_path: str, ready_event=None):
    """
    Tails the LOTRO script.log. When a new line appears, triggers callback.
    """
    watcher_log = setup_logger("WATCHER")
    while not os.path.exists(log_path):
        watcher_log.warning(f"Log file {log_path} not found - waiting...")
        time.sleep(2)

    last_size = os.path.getsize(log_path)
    if ready_event is not None:
        ready_event.set()

    watcher_log.info(f"Watching: {log_path}")

    while True:
        try:
            if not os.path.exists(log_path):
                time.sleep(1)
                continue
            size = os.path.getsize(log_path)
            if size > last_size:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(last_size)
                    new_lines = f.readlines()
                last_size = size
                for line in new_lines:
                    name = line.strip()
                    if name:
                        watcher_log.info(f"New NPC detected: {name}")
                        callback(name)
        except Exception as exc:
            watcher_log.exception(f"Watcher error: {exc}")
        time.sleep(0.5)


# --- TEMPLATE MATCHING UTILS ---


def match_template_in_roi(
    img_gray: np.ndarray, template: np.ndarray, x: int, y: int, w: int, h: int
) -> Tuple[float, int, int]:
    """
    Performs template matching within a specific Region of Interest (ROI).

    Returns
    -------
    Tuple[float, int, int]
        (max_val, match_x, match_y).
    """
    img_h, img_w = img_gray.shape
    x, y = int(max(0, x)), int(max(0, y))
    w, h = int(min(w, img_w - x)), int(min(h, img_h - y))

    if w < template.shape[1] or h < template.shape[0]:
        return 0.0, 0, 0

    roi = img_gray[y : y + h, x : x + w]
    res = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    return max_val, x + max_loc[0], y + max_loc[1]


# --- RETAIL EXTRACTION LOGIC ---


def extract_quest_areas(
    full_img_np: np.ndarray,
) -> Tuple[Optional[Image.Image], Optional[Image.Image]]:
    """
    Extracts the Quest Title and Body using the Retail logic (Cascading Dependency).
    """
    if len(full_img_np.shape) == 3:
        img_gray = cv2.cvtColor(full_img_np, cv2.COLOR_BGR2GRAY)
    else:
        img_gray = full_img_np

    # 1. Load User Calibration (Retail)
    tmpls = load_user_templates("retail")
    config = load_user_config("retail")
    offsets = config.get("offsets", {}) if "offsets" in config else config

    if not tmpls or not offsets:
        log.warning("Retail Calibration missing. Please run 'calibrate_retail.bat'.")
        return None, None

    h_img, w_img = img_gray.shape

    # 2. Match Start/End Leaves (Title Bar)
    res_s = cv2.matchTemplate(img_gray, tmpls["start"], cv2.TM_CCOEFF_NORMED)
    _, val_s, _, loc_s = cv2.minMaxLoc(res_s)

    res_e = cv2.matchTemplate(img_gray, tmpls["end"], cv2.TM_CCOEFF_NORMED)
    _, val_e, _, loc_e = cv2.minMaxLoc(res_e)

    if val_s <= TEMPLATE_THRESHOLD or val_e <= TEMPLATE_THRESHOLD:
        return None, None

    # Title Geometry
    w_start = tmpls["start"].shape[1]
    title_x = loc_s[0] + w_start
    title_y = loc_s[1]
    title_w = loc_e[0] - title_x
    title_h = tmpls["start"].shape[0]
    title_bot = title_y + title_h

    # 3. Match Corner (Body Top-Left)
    # Search strictly below title
    val_c, cx, cy = match_template_in_roi(
        img_gray, tmpls["corner"], 0, title_bot, w_img, h_img - title_bot
    )

    if val_c <= TEMPLATE_THRESHOLD:
        return None, None

    # 4. Match Intersection (Width Definer) & Icon (Height Definer)

    # Intersect: Right of Corner
    # We use MIN_BOX_DIM (50) as a minimum width assumption
    val_int, ix, iy = match_template_in_roi(
        img_gray, tmpls["intersect"], cx + 50, cy - 20, w_img - (cx + 50), h_img - cy
    )

    # Icon: Below Corner
    val_i, icx, icy = match_template_in_roi(
        img_gray, tmpls["icon"], 0, cy + 50, w_img, h_img - (cy + 50)
    )

    if val_int <= TEMPLATE_THRESHOLD or val_i <= TEMPLATE_THRESHOLD:
        return None, None

    # 5. Apply User Offsets
    off_x = offsets.get("CORNER_OFFSET_X", 5)
    off_y = offsets.get("CORNER_OFFSET_Y", 5)
    pad_ix = offsets.get("PADDING_INTERSECT_X", 5)
    pad_iy = offsets.get("PADDING_ICON_Y", 5)

    body_x = cx + off_x
    body_y = cy + off_y
    body_w = (ix - pad_ix) - body_x
    body_h = (icy - pad_iy) - body_y

    # Validation
    if body_w <= 0 or body_h <= 0:
        return None, None

    if body_x + body_w > w_img:
        body_w = w_img - body_x
    if body_y + body_h > h_img:
        body_h = h_img - body_y

    # Crop
    title_crop = full_img_np[title_y : title_y + title_h, title_x : title_x + title_w]
    body_crop = full_img_np[body_y : body_y + body_h, body_x : body_x + body_w]

    return (
        Image.fromarray(cv2.cvtColor(title_crop, cv2.COLOR_BGR2RGB)),
        Image.fromarray(cv2.cvtColor(body_crop, cv2.COLOR_BGR2RGB)),
    )


# --- ECHOES EXTRACTION LOGIC ---


def extract_echoes_areas(
    full_img_np: np.ndarray,
) -> Tuple[Optional[Image.Image], Optional[Image.Image]]:
    """
    Extracts Quest Text and NPC Name using Echoes (Classic) logic.
    1. Anchors (Plants, Corners).
    2. Margins (Calibrated).
    3. Static NPC Box.
    4. Stitches Title+Body.
    """
    img_gray = cv2.cvtColor(full_img_np, cv2.COLOR_BGR2GRAY)

    # 1. Load Data
    tmpls = load_user_templates("echoes")
    config = load_user_config("echoes")

    if not tmpls or not config:
        log.warning("Echoes calibration missing. Run 'calibrate_eoa.bat'")
        return None, None

    offsets = config.get("offsets", {})
    npc_box = config.get("npc_box", [0, 0, 0, 0])

    # 2. Find Anchors
    def find_best(tmpl):
        res = cv2.matchTemplate(img_gray, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        return max_loc, max_val

    pos_lp, val_lp = find_best(tmpls["left_plant"])
    pos_rp, val_rp = find_best(tmpls["right_plant"])
    pos_tl, val_tl = find_best(tmpls["tl_corner"])
    pos_br, val_br = find_best(tmpls["br_corner"])

    if any(v < 0.7 for v in [val_lp, val_rp, val_tl, val_br]):
        log.warning("Anchors not found in Echoes mode.")
        return None, None

    # 3. Calculate Quest Title
    tx = pos_lp[0] + tmpls["left_plant"].shape[1]
    ty = pos_lp[1]
    tw = pos_rp[0] - tx
    th = max(tmpls["left_plant"].shape[0], tmpls["right_plant"].shape[0])

    # 4. Calculate Quest Body
    bx = pos_tl[0] + offsets.get("body_left_margin", 0)
    by = pos_tl[1] + offsets.get("body_top_margin", 0)
    bx_end = pos_br[0] - offsets.get("body_right_padding", 0)
    by_end = pos_br[1] - offsets.get("body_bottom_padding", 0)

    bw = bx_end - bx
    bh = by_end - by

    # 5. Crop & Stitch
    try:
        # Title
        crop_title = full_img_np[ty : ty + th, tx : tx + tw]

        # Body
        crop_body = full_img_np[by : by + bh, bx : bx + bw]

        # NPC (Static)
        nx, ny, nw, nh = npc_box
        if nw > 0 and nh > 0:
            crop_npc = full_img_np[ny : ny + nh, nx : nx + nw]
        else:
            crop_npc = np.zeros((50, 200, 3), dtype=np.uint8)

        # Stitch
        sep_h = 10
        max_w = max(crop_title.shape[1], crop_body.shape[1])
        separator = np.full((sep_h, max_w, 3), 255, dtype=np.uint8)

        def resize_w(img, target_w):
            h, w = img.shape[:2]
            if w == target_w:
                return img
            return cv2.resize(img, (target_w, h))

        if crop_title.shape[1] != max_w:
            crop_title = resize_w(crop_title, max_w)
        if crop_body.shape[1] != max_w:
            crop_body = resize_w(crop_body, max_w)

        stitched_quest = np.vstack([crop_title, separator, crop_body])

        return (
            Image.fromarray(cv2.cvtColor(stitched_quest, cv2.COLOR_BGR2RGB)),
            Image.fromarray(cv2.cvtColor(crop_npc, cv2.COLOR_BGR2RGB)),
        )

    except Exception as e:
        log.error(f"Echoes Crop Error: {e}")
        return None, None


# --- SCREEN CAPTURE ENTRY POINT ---


def capture_screen_areas(mode_prefix: str = "retail") -> Tuple[Any, Any]:
    """
    Captures screen and extracts areas based on mode.

    Returns
    -------
    Tuple[Any, Any]
        Retail: (Full_Screenshot_PIL, Full_Screenshot_NP)
        Echoes: (Stitched_Quest_PIL, NPC_Name_PIL)
    """
    try:
        screenshot = ImageGrab.grab()
    except OSError:
        log.error("Failed to grab screen.")
        return None, None

    screenshot_np = np.array(screenshot)
    screenshot_np = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)

    if mode_prefix == "retail":
        return Image.fromarray(screenshot_np), screenshot_np

    elif mode_prefix == "echoes":
        return extract_echoes_areas(screenshot_np)

    return None, None