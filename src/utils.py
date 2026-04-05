# Imports

# > Standard Library
import ctypes
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# > Third-party Libraries
import cv2
import numpy as np
from PIL import Image, ImageGrab

# > Local Dependencies
from .config import (
    BASE_RESOLUTION,
    DATA_DIR,
    DEBUG_TEMPLATE_SCORES,
    DEFAULT_ECHOES_OFFSETS,
    DEFAULT_RETAIL_OFFSETS,
    LOG_LEVEL,
    QUEST_WINDOW_BOX,
    QUEST_WINDOW_MODE,
    TEMPLATE_THRESHOLD,
    TEMPLATES_DIR,
)

DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- CONFIGURATION FILES ---
LAYOUT_RETAIL = DATA_DIR / "layout_retail.json"
LAYOUT_ECHOES = DATA_DIR / "layout_echoes.json"

# --- RESOLUTION DETECTION & TEMPLATE SCALING ---

# Cached resolution values (populated on first call to get_screen_resolution)
_cached_resolution: Optional[Tuple[int, int]] = None
_cached_scale_factor: Optional[float] = None


def get_screen_resolution() -> Tuple[int, int]:
    """
    Returns the actual screen resolution in pixels,
    accounting for Windows DPI scaling.

    Uses ctypes to call GetDeviceCaps for the physical resolution,
    falling back to PIL/ImageGrab if ctypes is unavailable.
    """
    global _cached_resolution
    if _cached_resolution is not None:
        return _cached_resolution

    try:
        import ctypes.wintypes

        hdc = ctypes.windll.user32.GetDC(0)
        # LOGPIXELSX = 88, LOGPIXELSY = 90 — DPI in each axis
        HORZRES = ctypes.windll.gdi32.GetDeviceCaps(hdc, 8)  # Desktop width
        VERTRES = ctypes.windll.gdi32.GetDeviceCaps(hdc, 10)  # Desktop height
        LOGPIXELSX = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
        ctypes.windll.user32.ReleaseDC(0, hdc)

        if LOGPIXELSX > 0 and HORZRES > 0:
            # Scale virtual pixels by DPI ratio to get physical pixels
            _cached_resolution = (
                int(HORZRES * LOGPIXELSX / 96),
                int(VERTRES * LOGPIXELSX / 96),
            )
            log.info(
                f"🖥️ Physical resolution: {_cached_resolution[0]}x{_cached_resolution[1]} "
                f"(DPI scale: {LOGPIXELSX / 96:.2f}x)"
            )
            return _cached_resolution
    except Exception:
        pass

    # Fallback: use PIL screen size
    try:
        from PIL import ImageGrab

        img = ImageGrab.grab()
        _cached_resolution = (img.size[0], img.size[1])
        log.info(
            f"🖥️ Resolution (PIL fallback): {_cached_resolution[0]}x{_cached_resolution[1]}"
        )
        return _cached_resolution
    except Exception:
        pass

    # Last resort: assume base resolution
    _cached_resolution = BASE_RESOLUTION
    log.warning(
        f"⚠️ Could not detect resolution, assuming {BASE_RESOLUTION[0]}x{BASE_RESOLUTION[1]}"
    )
    return _cached_resolution


def get_scale_factor() -> float:
    """
    Returns the scale factor relative to the base resolution (2560x1440).

    LOTRO's UI scales linearly with resolution, so we use width ratio:
        1080p -> 1920/2560 = 0.75
        1440p -> 2560/2560 = 1.0
        4K     -> 3840/2560 = 1.5
    """
    global _cached_scale_factor
    if _cached_scale_factor is not None:
        return _cached_scale_factor

    res = get_screen_resolution()
    _cached_scale_factor = res[0] / BASE_RESOLUTION[0]
    log.info(
        f"📏 Scale factor: {_cached_scale_factor:.3f}x (base: {BASE_RESOLUTION[0]}x{BASE_RESOLUTION[1]})"
    )
    return _cached_scale_factor


def load_scaled_template(
    template_path: Path,
    target_resolution: Optional[Tuple[int, int]] = None,
) -> np.ndarray:
    """
    Loads a template image and scales it to match the target resolution.

    Parameters
    ----------
    template_path : Path
        Path to the template image file.
    target_resolution : tuple, optional
        Target (width, height). Defaults to detected screen resolution.

    Returns
    -------
    np.ndarray
        Grayscale template, scaled to the target resolution.
    """
    if target_resolution is None:
        target_resolution = get_screen_resolution()

    template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
    if template is None:
        raise FileNotFoundError(f"Template not found: {template_path}")

    scale = target_resolution[0] / BASE_RESOLUTION[0]

    # Skip scaling if we're already at (or very close to) base resolution
    if abs(scale - 1.0) < 0.01:
        return template

    h, w = template.shape[:2]
    new_w = max(5, int(w * scale))
    new_h = max(5, int(h * scale))

    # Use INTER_AREA for downscale (anti-aliasing), INTER_CUBIC for upscale
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    scaled = cv2.resize(template, (new_w, new_h), interpolation=interpolation)

    log.debug(
        f"📐 Scaled template {template_path.name}: "
        f"{w}x{h} -> {new_w}x{new_h} (scale: {scale:.3f})"
    )
    return scaled


def match_template_fallback(
    img_gray: np.ndarray,
    template: np.ndarray,
    base_threshold: float = 0.5,
) -> Tuple[float, int, int]:
    """
    Tries template matching at multiple scale factors around the computed one.
    Returns the best match found.

    Used as a safety net when the initial single-scale match fails.
    Scale sweep: [0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15]
    Threshold relaxes by 0.05 each iteration.

    Parameters
    ----------
    img_gray : np.ndarray
        Source grayscale image.
    template : np.ndarray
        Template image (already scaled to detected resolution).
    base_threshold : float
        Starting match threshold.

    Returns
    -------
    Tuple[float, int, int]
        (max_val, match_x, match_y). Returns (0.0, 0, 0) if nothing matches.
    """
    h, w = template.shape[:2]
    img_h, img_w = img_gray.shape

    best_val = 0.0
    best_x, best_y = 0, 0

    for scale in [0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15]:
        new_w = max(5, int(w * scale))
        new_h = max(5, int(h * scale))

        if new_w > img_w or new_h > img_h:
            continue

        interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
        scaled_tmpl = cv2.resize(template, (new_w, new_h), interpolation=interpolation)

        result = cv2.matchTemplate(img_gray, scaled_tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val > best_val:
            best_val = max_val
            best_x, best_y = max_loc

        # Early exit if we already have a strong match
        if max_val >= base_threshold:
            break

    return best_val, best_x, best_y


def setup_logger(name: str) -> logging.Logger:
    """
    Configures a standard logger outputting to console.

    Parameters
    ----------
    name : str
        Name of the logger.

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
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
    """
    Generates legacy file paths for coordinates (used by calibration).
    Note: NPC memory handling is now managed by `get_memory_file_path`.

    Parameters
    ----------
    mode : str
        The game mode ('retail' or 'echoes').

    Returns
    -------
    Tuple[Path, Path]
        (path_to_coords_json, legacy_memory_path)
    """
    safe_mode = mode.lower().strip()
    return (
        DATA_DIR / f"coords_{safe_mode}.json",
        DATA_DIR / f"npc_memory_{safe_mode}.json",
    )


def get_memory_file_path(mode: str, backend: str) -> Path:
    """
    Constructs the path for the NPC memory file based on mode and backend.
    This ensures Kokoro (CPU) and OmniVoice (GPU) maintain separate voice databases.

    Parameters
    ----------
    mode : str
        Game mode ('retail' or 'echoes').
    backend : str
        TTS backend ('lux' or 'kokoro').

    Returns
    -------
    Path
        The full path to the json file.
    """
    return DATA_DIR / f"npc_memory_{mode.lower()}_{backend.lower()}.json"


def load_coords(mode: str) -> Dict:
    """
    Loads saved coordinates for the specified mode.

    Parameters
    ----------
    mode : str
        Game mode.

    Returns
    -------
    dict
        Dictionary of coordinates.
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

    Parameters
    ----------
    coords : dict
        Coordinates to save.
    mode : str
        Game mode.
    """
    coords_file, _ = get_file_paths(mode)
    with open(coords_file, "w") as f:
        json.dump(coords, f, indent=4)


def load_npc_memory(mode: str, backend: str = "lux") -> Dict:
    """
    Loads the database of previously seen NPCs for the specific engine backend.

    Parameters
    ----------
    mode : str
        Game mode ('retail' or 'echoes').
    backend : str
        TTS backend name ('lux' or 'kokoro').

    Returns
    -------
    dict
        Memory database.
    """
    memory_file = get_memory_file_path(mode, backend)

    # Fallback to legacy file if new backend-specific file doesn't exist yet
    # This prevents data loss for existing users updating to the new version.
    if not memory_file.exists() and backend == "lux":
        _, legacy_path = get_file_paths(mode)
        if legacy_path.exists():
            log.info(f"Migrating legacy memory file to {memory_file}")
            try:
                with open(legacy_path, "r") as f:
                    data = json.load(f)
                save_npc_memory(data, mode, backend)
                return data
            except json.JSONDecodeError:
                pass

    if memory_file.exists():
        try:
            with open(memory_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def save_npc_memory(memory: Dict, mode: str, backend: str = "lux"):
    """
    Saves the NPC memory database to disk, specific to the backend.

    Parameters
    ----------
    memory : Dict
        Data to save (dict of {npc_key: NPC dict}).
    mode : str
        Game mode.
    backend : str
        TTS backend ('lux' or 'kokoro').
    """
    memory_file = get_memory_file_path(mode, backend)
    with open(memory_file, "w") as f:
        json.dump(memory, f, indent=4)


# --- CONFIGURATION LOADERS ---


def get_layout_file(mode: str) -> Path:
    """
    Returns the appropriate layout file path based on the game mode.

    Parameters
    ----------
    mode : str
        Game mode.

    Returns
    -------
    Path
        Path to layout json.
    """
    return LAYOUT_RETAIL if mode == "retail" else LAYOUT_ECHOES


def load_user_templates(mode: str = "retail") -> Optional[Dict]:
    """
    Loads calibrated templates for the given game mode.

    Resolution-aware logic:
    1. If user-calibrated templates (user_*.png / echoes_*.png) exist → load
       them as-is (they were captured at the user's native resolution).
    2. If user templates are missing → load the default templates shipped
       with the app and auto-scale them to the detected screen resolution.

    Parameters
    ----------
    mode : str
        The game mode ('retail' or 'echoes').

    Returns
    -------
    dict or None
        Dictionary of {key: cv2_image} or None if both sources are missing.
    """
    # Mapping: template key → user filename prefix and default filename
    if mode == "retail":
        keys = ["start", "end", "corner", "intersect", "icon"]
        user_prefix = "user"
        default_files = {
            "start": "start_leaf.png",
            "end": "end_leaf.png",
            "corner": "body_upper_left_corner.png",
            "intersect": "intersection.png",
            "icon": "filter_icon.png",
        }
    else:
        keys = ["left_plant", "right_plant", "tl_corner", "br_corner"]
        user_prefix = "echoes"
        default_files = {
            "left_plant": "example_echoes_left_plant.png",
            "right_plant": "example_echoes_right_plant.png",
            "tl_corner": "example_echoes_tl_corner.png",
            "br_corner": "example_echoes_br_corner.png",
        }

    # --- Step 1: Try loading user-calibrated templates ---
    templates = {}
    all_present = True
    for key in keys:
        path = TEMPLATES_DIR / f"{user_prefix}_{key}.png"
        if path.exists():
            templates[key] = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        else:
            all_present = False

    if all_present:
        log.debug(f"📐 Using user-calibrated templates for {mode}")
        return templates

    # --- Step 2: Fall back to auto-scaled default templates ---
    log.info(
        f"📐 User templates missing for {mode} — "
        f"auto-scaling defaults to detected resolution"
    )
    templates = {}
    for key in keys:
        default_path = TEMPLATES_DIR / default_files[key]
        if not default_path.exists():
            log.warning(f"⚠️ Default template missing: {default_path.name}")
            return None
        try:
            templates[key] = load_scaled_template(default_path)
        except FileNotFoundError:
            log.warning(f"⚠️ Could not load default template: {default_path.name}")
            return None

    log.info(f"📐 Loaded {len(templates)} auto-scaled default templates for {mode}")
    return templates


def load_user_config(mode: str) -> Dict:
    """
    Loads the calibrated configuration (offsets/NPC box) from the JSON file.

    If the layout file is missing, returns default offsets scaled to the
    current screen resolution so auto-detection works out-of-the-box.

    Parameters
    ----------
    mode : str
        Game mode.

    Returns
    -------
    dict
        User configuration data with 'offsets' key.
    """
    path = get_layout_file(mode)
    if path.exists():
        try:
            with open(path, "r") as f:
                config = json.load(f)
                if "offsets" in config:
                    # Scale offsets if the layout was calibrated at a different
                    # resolution than the current screen (e.g. calibrated at
                    # 1440p but now running at 1080p or 4K).
                    stored_res = config.get("resolution", "")
                    if stored_res:
                        try:
                            stored_w = int(stored_res.split("x")[0])
                            current_w = get_screen_resolution()[0]
                            if stored_w != current_w:
                                ratio = current_w / stored_w
                                config["offsets"] = {
                                    k: int(v * ratio)
                                    for k, v in config["offsets"].items()
                                }
                                log.info(
                                    f"📐 Scaled {mode} offsets by {ratio:.3f}x "
                                    f"(layout was {stored_res})"
                                )
                        except (ValueError, IndexError):
                            pass
                    return config
        except json.JSONDecodeError:
            pass

    # No layout file or missing offsets — return scaled defaults
    defaults = DEFAULT_RETAIL_OFFSETS if mode == "retail" else DEFAULT_ECHOES_OFFSETS
    scale = get_scale_factor()
    scaled = {k: int(v * scale) for k, v in defaults.items()}
    log.info(f"📐 No layout file for {mode} — using scaled default offsets: {scaled}")
    return {"offsets": scaled}


# --- LOG WATCHER (Retail Only) ---


def watch_npc_file(callback, log_path: str, ready_event=None):
    """
    Tails the LOTRO script.log. When a new line appears, triggers callback.

    Parameters
    ----------
    callback : function
        Function to call with the new line text.
    log_path : str
        Path to the script.log file.
    ready_event : threading.Event, optional
        Event to set when the watcher is ready.
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


# --- TEMPLATE MATCHING UTILS ---


def match_template_in_roi(
    img_gray: np.ndarray, template: np.ndarray, x: int, y: int, w: int, h: int
) -> Tuple[float, int, int]:
    """
    Performs template matching within a specific Region of Interest (ROI).

    Parameters
    ----------
    img_gray : np.ndarray
        Source grayscale image.
    template : np.ndarray
        Template image to match.
    x, y, w, h : int
        ROI coordinates.

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


def _extract_retail_auto(
    img_gray: np.ndarray,
    full_img_np: np.ndarray,
    tmpls: Dict,
    offsets: Dict,
    h_img: int,
    w_img: int,
) -> Tuple[Optional[Image.Image], Optional[Image.Image]]:
    """
    Core auto-detection logic for retail quest window extraction.

    Uses template matching to find the quest window at any screen position,
    then applies layout offsets to extract the title and body text areas.

    Called by both auto mode and static mode (when templates are available)
    to avoid code duplication and ensure consistent behavior.

    Parameters
    ----------
    img_gray : np.ndarray
        Full screenshot in grayscale.
    full_img_np : np.ndarray
        Full screenshot in BGR format.
    tmpls : dict
        Template images dict from load_user_templates().
    offsets : dict
        Layout offsets dict from load_user_config().
    h_img, w_img : int
        Screen dimensions.

    Returns
    -------
    Tuple[Image, Image] or Tuple[None, None]
        (Title Image, Body Image) or (None, None) if detection fails.
    """
    # Match Start/End Leaves (Title Bar)
    res_s = cv2.matchTemplate(img_gray, tmpls["start"], cv2.TM_CCOEFF_NORMED)
    _, val_s, _, loc_s = cv2.minMaxLoc(res_s)

    res_e = cv2.matchTemplate(img_gray, tmpls["end"], cv2.TM_CCOEFF_NORMED)
    _, val_e, _, loc_e = cv2.minMaxLoc(res_e)

    if DEBUG_TEMPLATE_SCORES:
        log.debug(
            f"Template scores — start_leaf: {val_s:.3f}, end_leaf: {val_e:.3f} "
            f"(threshold: {TEMPLATE_THRESHOLD})"
        )

    if val_s <= TEMPLATE_THRESHOLD or val_e <= TEMPLATE_THRESHOLD:
        return None, None

    # Title Geometry
    w_start = tmpls["start"].shape[1]
    title_x = loc_s[0] + w_start
    title_y = loc_s[1]
    title_w = loc_e[0] - title_x
    title_h = tmpls["start"].shape[0]
    title_bot = title_y + title_h

    # Match Corner (Body Top-Left) — search strictly below title
    val_c, cx, cy = match_template_in_roi(
        img_gray, tmpls["corner"], 0, title_bot, w_img, h_img - title_bot
    )

    if DEBUG_TEMPLATE_SCORES:
        log.debug(
            f"Template scores — corner: {val_c:.3f} at ({cx}, {cy}) "
            f"(threshold: {TEMPLATE_THRESHOLD})"
        )

    if val_c <= TEMPLATE_THRESHOLD:
        return None, None

    # Match Intersection (Width) & Icon (Height)
    val_int, ix, iy = match_template_in_roi(
        img_gray,
        tmpls["intersect"],
        cx + 50,
        cy - 20,
        w_img - (cx + 50),
        h_img - cy,
    )

    val_i, icx, icy = match_template_in_roi(
        img_gray,
        tmpls["icon"],
        0,
        cy + 50,
        w_img,
        h_img - (cy + 50),
    )

    if DEBUG_TEMPLATE_SCORES:
        log.debug(
            f"Template scores — intersect: {val_int:.3f} at ({ix}, {iy}), "
            f"icon: {val_i:.3f} at ({icx}, {icy}) "
            f"(threshold: {TEMPLATE_THRESHOLD})"
        )

    if val_int <= TEMPLATE_THRESHOLD or val_i <= TEMPLATE_THRESHOLD:
        return None, None

    # Apply Layout Offsets
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


def extract_quest_areas(
    full_img_np: np.ndarray,
) -> Tuple[Optional[Image.Image], Optional[Image.Image]]:
    """
    Extracts the Quest Title and Body using the Retail logic.
    Supports both 'auto' (template matching) and 'static' (fixed box) modes.

    Modes
    -----
    - auto   : Template matching finds the quest window at any screen position.
               Triggered automatically by the NPC log watcher.
    - static : Fixed bounding box (QUEST_WINDOW_BOX). The user is responsible
               for keeping the quest window at the calibrated position.
               Triggered manually by the hotkey (middle mouse button).

    Parameters
    ----------
    full_img_np : np.ndarray
        Full screen screenshot in numpy array format (BGR).

    Returns
    -------
    Tuple[Image, Image]
        (Title Image, Body Image) or (None, None) if detection fails.
    """
    if len(full_img_np.shape) == 3:
        img_gray = cv2.cvtColor(full_img_np, cv2.COLOR_BGR2GRAY)
    else:
        img_gray = full_img_np

    h_img, w_img = img_gray.shape

    # --- STATIC MODE ---
    # Simple fixed-box extraction. Assumes the quest window has not moved
    # since calibration. The user triggers capture manually via hotkey.
    if QUEST_WINDOW_MODE == "static":
        box = QUEST_WINDOW_BOX
        if len(box) != 4:
            log.warning("QUEST_WINDOW_BOX must be [x, y, width, height]")
            return None, None

        body_x, body_y, body_w, body_h = box

        # Validate coordinates
        if body_x < 0 or body_y < 0 or body_w <= 0 or body_h <= 0:
            log.warning(f"Invalid QUEST_WINDOW_BOX coordinates: {box}")
            return None, None

        # Clamp to screen bounds to prevent crashes
        if body_x + body_w > w_img:
            body_w = w_img - body_x
        if body_y + body_h > h_img:
            body_h = h_img - body_y

        log.info(
            f"📦 Static mode: coordinates [{body_x}, {body_y}, {body_w}, {body_h}]"
        )

        body_crop = full_img_np[body_y : body_y + body_h, body_x : body_x + body_w]
        body_pil = Image.fromarray(cv2.cvtColor(body_crop, cv2.COLOR_BGR2RGB))

        return None, body_pil

    # --- AUTO MODE ---
    # Template matching finds the quest window anywhere on screen.
    # Returns (None, None) if the window is not visible. The log watcher
    # trigger means this only runs when an NPC interaction just happened,
    # so a miss simply means the window isn't open yet.
    tmpls = load_user_templates("retail")
    config = load_user_config("retail")
    offsets = config.get("offsets", {}) if "offsets" in config else config

    if not tmpls or not offsets:
        log.warning("Retail Calibration missing. Please run 'calibrate_retail.bat'.")
        return None, None

    result = _extract_retail_auto(img_gray, full_img_np, tmpls, offsets, h_img, w_img)
    if result == (None, None):
        log.info("Auto mode: Quest window not found on screen - skipping")
    return result


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

    Parameters
    ----------
    full_img_np : np.ndarray
        Screenshot.

    Returns
    -------
    Tuple[Image, Image]
        (Stitched Text Image, NPC Name Image).
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

    Parameters
    ----------
    mode_prefix : str
        Game mode ('retail' or 'echoes').

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
