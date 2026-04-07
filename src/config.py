# Imports

# > Standard Library
import os
from pathlib import Path

# --- PATHS ---
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SAMPLES_DIR = DATA_DIR / "screenshots"
REF_AUDIO_DIR = DATA_DIR / "reference_audio"
NPC_DATA_PATH = DATA_DIR / "npc_data.csv"

# --- WIKI SETTINGS ---
WIKI_BASE_URL = "https://lotro-wiki.com"
MISSING_TEXT_INDICATOR = "There is currently no text in this page"

# --- DETECTION SETTINGS ---
# Thresholds for template matching
TEMPLATE_THRESHOLD = 0.7
STATIC_TEMPLATE_THRESHOLD = 0.7

# Debug: log every template match score (name, value, threshold, pass/fail)
# Set to True to see detailed matching info in the console output.
DEBUG_TEMPLATE_SCORES = False

# Offsets for text box extraction (Cascading Logic)
CORNER_OFFSET_X = 5
CORNER_OFFSET_Y = 5
PADDING_ICON_Y = 5
PADDING_INTERSECT_X = 5
MIN_BOX_DIM = 50

# Base resolution for template scaling — all default templates were captured at 1440p
BASE_RESOLUTION = (2560, 1440)

# Default layout offsets for retail mode (calibrated at BASE_RESOLUTION)
# Used as fallback when layout_retail.json is missing
DEFAULT_RETAIL_OFFSETS = {
    "CORNER_OFFSET_X": 11,
    "CORNER_OFFSET_Y": 10,
    "PADDING_INTERSECT_X": -10,
    "PADDING_ICON_Y": 17,
}

# Default layout offsets for echoes mode (calibrated at BASE_RESOLUTION)
# Used as fallback when layout_echoes.json is missing
DEFAULT_ECHOES_OFFSETS = {
    "body_left_margin": 11,
    "body_top_margin": 10,
    "body_right_padding": 0,
    "body_bottom_padding": 0,
}

# Retail Mode Paths
SCRIPT_LOG = os.path.join(
    os.path.expanduser("~"), "Documents", "The Lord of the Rings Online", "Script.log"
)
TEMPLATES_DIR = BASE_DIR / "templates"

# --- DEVICE ---
# Lazy: torch is only imported when DEVICE is first accessed at runtime,
# so the test suite doesn't need a GPU stack just to import config.


def _get_device() -> str:
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


DEVICE = None  # Set on first access via __getattr__ below


def __getattr__(name):
    if name == "DEVICE":
        global DEVICE
        if DEVICE is None:
            DEVICE = _get_device()
        return DEVICE
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# --- AUDIO SETTINGS ---
SAMPLE_RATE = 24000
DEFAULT_VOLUME = 0.4

# --- TTS SETTINGS ---
TTS_SPEED = 1.1  # Lower speed to prevent cutoffs
TTS_WAVE_STEPS = 16  # OmniVoice diffusion steps (32 = high quality, 16 = fast). Can be changed in the configure.bat / configure.sh file

# --- OCR SETTINGS ---
# We check standard Windows paths to find Tesseract automatically
possible_paths = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\admin\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
]

TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # Default value in the configure.bat  / configure.sh file

for p in possible_paths:
    if os.path.exists(p):
        TESSERACT_CMD = p
        break

# --- LOGGING ---
LOG_LEVEL = "INFO"

# --- FEATURES ---
# TODO: reconsider usefulness / accuracy of wiki lookups
ENABLE_WIKI = False  # Set to True to enable Wiki lookups, False for instant OCR

LUX_VOLUME = 0.5

# --- QUEST WINDOW DETECTION MODES ---
# "auto"   = Template matching finds the quest window anywhere on screen.
#            Trigger: automatic via Script.log NPC watcher (requires getNPCNames plugin).
#            Run calibrate_retail.bat to capture templates.
# "static" = Fixed bounding box (QUEST_WINDOW_BOX). Window must NOT move.
#            Trigger: manual hotkey press (middle mouse button by default).
#            Run calibrate_static.bat to set coordinates.
QUEST_WINDOW_MODE = "auto"

# For static mode: [x, y, width, height] of quest window body area
# Set these via calibrate_static.bat after drawing bounding box
QUEST_WINDOW_BOX = [555, 380, 425, 539]

# --- TRIGGER SETTINGS (legacy, kept for calibrate_static.py compat) ---
# main.py now derives the trigger from QUEST_WINDOW_MODE:
#   auto   -> log watcher triggers capture automatically
#   static -> hotkey triggers capture manually
# These values are only used by calibrate_static.py when writing config.
QUEST_TRIGGER_MODE = "manual"

# Hotkey for static mode
# Supported: "middle_mouse", "left", "right", or keyboard key names like "f8", "t", "q"
QUEST_TRIGGER_KEY = "middle_mouse"

# Maximum age (in seconds) for NPC names from the log file in manual mode.
# If the last NPC entry is older than this, the engine falls back to the
# default narrator voice instead of using a potentially stale name.
NPC_NAME_MAX_AGE = 60
