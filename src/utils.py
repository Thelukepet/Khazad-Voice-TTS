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

# --- USER CALIBRATION PATHS ---
LAYOUT_FILE = DATA_DIR / "user_layout.json"
PATHS = {
    "start": TEMPLATES_DIR / "user_start.png",
    "end": TEMPLATES_DIR / "user_end.png",
    "corner": TEMPLATES_DIR / "user_corner.png",
    "intersect": TEMPLATES_DIR / "user_intersect.png",
    "icon": TEMPLATES_DIR / "user_icon.png",
}


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


# --- DATA MANAGEMENT ---


def get_file_paths(mode: str) -> Tuple[Path, Path]:
    safe_mode = mode.lower().strip()
    return (
        DATA_DIR / f"coords_{safe_mode}.json",
        DATA_DIR / f"npc_memory_{safe_mode}.json",
    )


def load_coords(mode: str) -> dict:
    coords_file, _ = get_file_paths(mode)
    if coords_file.exists():
        try:
            with open(coords_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def save_coords(coords: dict, mode: str):
    coords_file, _ = get_file_paths(mode)
    with open(coords_file, "w") as f:
        json.dump(coords, f, indent=4)


def load_npc_memory(mode: str) -> dict:
    _, memory_file = get_file_paths(mode)
    if memory_file.exists():
        try:
            with open(memory_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def save_npc_memory(memory: dict, mode: str):
    _, memory_file = get_file_paths(mode)
    with open(memory_file, "w") as f:
        json.dump(memory, f, indent=4)


# --- LOG WATCHER ---


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


# --- TEMPLATE MATCHING & EXTRACTION ---


def load_user_templates() -> dict:
    """
    Loads the user-calibrated templates from disk.

    Returns
    -------
    dict or None
        A dictionary of {key: cv2_image} if all templates exist,
        otherwise None.
    """
    loaded = {}
    missing = False
    for key, path in PATHS.items():
        if path.exists():
            loaded[key] = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        else:
            missing = True

    if missing:
        return None
    return loaded


def load_user_offsets() -> dict:
    """
    Loads the calculated offsets from the user_layout.json file.

    Returns
    -------
    dict
        A dictionary containing offsets like CORNER_OFFSET_X, PADDING_ICON_Y, etc.
    """
    if LAYOUT_FILE.exists():
        try:
            with open(LAYOUT_FILE, "r") as f:
                data = json.load(f)
                return data.get("offsets", {})
        except:
            pass
    return {}


def match_template_in_roi(
    img_gray: np.ndarray, template: np.ndarray, x: int, y: int, w: int, h: int
) -> Tuple[float, int, int]:
    """
    Performs template matching within a specific Region of Interest (ROI).

    Parameters
    ----------
    img_gray : np.ndarray
        The full grayscale image.
    template : np.ndarray
        The template to search for.
    x, y, w, h : int
        The bounding box of the ROI to search within.

    Returns
    -------
    Tuple[float, int, int]
        (max_val, match_x, match_y).
        max_val is the confidence score (0.0 to 1.0).
        match_x, match_y are the global coordinates of the match.
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


def extract_quest_areas(
    full_img_np: np.ndarray,
) -> Tuple[Optional[Image.Image], Optional[Image.Image]]:
    """
    Extracts the Quest Title and Body using the user-calibrated geometric search.

    The logic follows a 5-step cascading dependency:
    1. Title Bar: Finds Start and End leaves.
    2. Corner: Finds the top-left corner of the text body.
    3. Intersection: Finds the right boundary.
    4. Icon: Finds the bottom boundary.
    5. Crop: Applies calibrated offsets to cut out the text.

    Parameters
    ----------
    full_img_np : np.ndarray
        The full screenshot in BGR format.

    Returns
    -------
    Tuple[Optional[Image.Image], Optional[Image.Image]]
        (title_image, body_image) as PIL Images. Returns (None, None) if detection fails.
    """
    if len(full_img_np.shape) == 3:
        img_gray = cv2.cvtColor(full_img_np, cv2.COLOR_BGR2GRAY)
    else:
        img_gray = full_img_np

    # 1. Load User Calibration
    tmpls = load_user_templates()
    offsets = load_user_offsets()

    if not tmpls or not offsets:
        log.warning("Calibration missing. Please run 'calibrate.bat'.")
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

    # 5. Apply User Offsets (The Magic Part)
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


# --- SCREEN CAPTURE UTILS ---


def get_crop_roi_interactive(
    img_np: np.ndarray, prompt_title: str = "SELECT AREA", full_screen: bool = False
) -> Optional[Tuple[int, int, int, int]]:
    """
    Opens an interactive OpenCV window for ROI selection.

    Parameters
    ----------
    img_np : np.ndarray
        The image to select from.
    prompt_title : str
        The window title.
    full_screen : bool
        Whether to force full screen mode.

    Returns
    -------
    Optional[Tuple[int, int, int, int]]
        (x, y, w, h) or None if cancelled.
    """
    if img_np is None:
        return None
    print(f"\n--- {prompt_title} ---")
    window_name = prompt_title
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    if full_screen:
        cv2.setWindowProperty(
            window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN
        )
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
    cv2.imshow(window_name, img_np)
    cv2.waitKey(1)
    r = cv2.selectROI(window_name, img_np, fromCenter=False, showCrosshair=True)
    cv2.destroyAllWindows()
    if r[2] == 0 or r[3] == 0:
        return None
    return int(r[0]), int(r[1]), int(r[2]), int(r[3])


def capture_screen_areas(mode_prefix: str = "echoes") -> Tuple[Any, Any]:
    """
    Captures the screen and (if in 'echoes' mode) crops using manual ROIs.
    In 'retail' mode, returns the full screenshot.
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

    all_coords = load_coords(mode_prefix)
    q_key = f"{mode_prefix}_quest"
    n_key = f"{mode_prefix}_name"

    if q_key not in all_coords or n_key not in all_coords:
        if q_key not in all_coords:
            q_roi = get_crop_roi_interactive(screenshot_np, f"SELECT QUEST TEXT", True)
            if q_roi:
                all_coords[q_key] = q_roi
        if n_key not in all_coords:
            n_roi = get_crop_roi_interactive(screenshot_np, "SELECT NPC NAME", True)
            if n_roi:
                all_coords[n_key] = n_roi
        save_coords(all_coords, mode_prefix)

    qx, qy, qw, qh = all_coords.get(q_key, (0, 0, 0, 0))
    nx, ny, nw, nh = all_coords.get(n_key, (0, 0, 0, 0))

    if qw == 0 or nw == 0:
        return None, None
    q_np = screenshot_np[qy : qy + qh, qx : qx + qw]
    n_np = screenshot_np[ny : ny + nh, nx : nx + nw]

    return (
        Image.fromarray(cv2.cvtColor(q_np, cv2.COLOR_BGR2RGB)),
        Image.fromarray(cv2.cvtColor(n_np, cv2.COLOR_BGR2RGB)),
    )
