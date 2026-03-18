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
TEMPLATE_THRESHOLD = 0.5
STATIC_TEMPLATE_THRESHOLD = 0.7

# Offsets for text box extraction (Cascading Logic)
CORNER_OFFSET_X = 5
CORNER_OFFSET_Y = 5
PADDING_ICON_Y = 5
PADDING_INTERSECT_X = 5
MIN_BOX_DIM = 50

# Retail Mode Paths
SCRIPT_LOG = os.path.join(os.path.expanduser("~"), "Documents", "The Lord of the Rings Online", "Script.log")
TEMPLATES_DIR = BASE_DIR / "templates"

# --- DEVICE ---
import torch

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# --- AUDIO SETTINGS ---
SAMPLE_RATE = 24000
DEFAULT_VOLUME = 0.4

# --- TTS SETTINGS ---
TTS_SPEED = 1.1  # Lower speed to prevent cutoffs
TTS_WAVE_STEPS = 4  # Quality steps default is max performance, can be changed in the configure.bat / configure.sh

# --- OCR SETTINGS ---
# We check standard Windows paths to find Tesseract automatically
possible_paths = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\admin\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
]

TESSERACT_CMD =  r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # Default value in the configure.bat  / configure.sh file

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
# "auto" = use template matching (requires calibration)
# "static" = use fixed bounding box coordinates (user-defined)
QUEST_WINDOW_MODE = "auto"

# For static mode: [x, y, width, height] of quest window body area
# Set these via calibrate_static.bat after drawing bounding box
QUEST_WINDOW_BOX = [496, 329, 429, 538]
