# Imports

# > Standard Library
import os
import shutil
import platform
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
# 1. Priority: Check System PATH
# This finds tesseract automatically on Linux/Gentoo (usually /usr/bin/tesseract)
# and on Windows if the user added it to their environment variables.
TESSERACT_CMD = shutil.which("tesseract")

# 2. Fallback: Check standard installation directories if not in PATH
if TESSERACT_CMD is None:
    if platform.system() == "Windows":
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            # Dynamic check for User AppData (Local\Programs)
            os.path.join(os.getenv('LOCALAPPDATA', ''), r"Programs\Tesseract-OCR\tesseract.exe"),
        ]
        
        # Default Windows string (needed by pytesseract if detection fails)
        TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

        for p in possible_paths:
            if os.path.exists(p):
                TESSERACT_CMD = p
                break
    else:
        # Linux fallback (if shutil.which failed for some reason)
        linux_paths = ["/usr/bin/tesseract", "/usr/local/bin/tesseract"]
        for p in linux_paths:
            if os.path.exists(p):
                TESSERACT_CMD = p
                break

# Final Safety: If still None, just use the command string and hope the OS finds it
if TESSERACT_CMD is None:
    TESSERACT_CMD = "tesseract"

# --- LOGGING ---
LOG_LEVEL = "INFO"

# --- FEATURES ---
# TODO: reconsider usefulness / accuracy of wiki lookups
ENABLE_WIKI = False  # Set to True to enable Wiki lookups, False for instant OCR

LUX_VOLUME = 0.5
