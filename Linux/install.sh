#!/bin/bash

# Change working directory to the project root
cd "$(dirname "$0")/.."

# Set Terminal Title
echo -ne "\033]0;KHAZAD VOICE TTS - INSTALLER\007"

# Color 0E (Yellow text on Black background approximation)
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Error handling function to mimic 'goto :error'
function error_exit {
  echo ""
  echo "=================================================="
  echo -e "${YELLOW}[ERROR] The installation failed!${NC}"
  echo "Check the error message above."
  echo "=================================================="
  read -n 1 -s -r -p "Press any key to continue..."
  echo ""
  exit 1
}

echo "=========================================================="
echo "                 KHAZAD VOICE TTS"
echo "      \"Baruk Khazad! The Voice of the Dwarves is upon you!\""
echo "=========================================================="
echo ""

# --- 1. Tool Checks (Git & Python) ---

# Check for Git
if ! git --version &>/dev/null; then
  echo -e "${YELLOW}[ERROR] Git is not installed.${NC}"
  echo "The Khazad cannot work without their tools."
  read -n 1 -s -r -p "Press any key to continue..."
  echo ""
  exit 1
fi

# Try to find Python 3.12 (preferred) or fallback to system python
PYTHON_CMD="python3"

if command -v python3.12 &>/dev/null; then
  echo "[INFO] Found Python 3.12."
  PYTHON_CMD="python3.12"
else
  # Fallback check
  if ! command -v python3 &>/dev/null; then
    echo -e "${YELLOW}[ERROR] Python is not installed or not in PATH.${NC}"
    echo "Please install Python 3.12."
    read -n 1 -s -r -p "Press any key to continue..."
    echo ""
    exit 1
  fi
fi

echo "[INFO] Using Python: $PYTHON_CMD"
echo ""
echo "[1/6] Igniting the Forge (Creating Virtual Environment)..."
$PYTHON_CMD -m venv venv
if [ $? -ne 0 ]; then error_exit; fi

echo "[2/6] Stoking the Fires (Activating Environment)..."
source venv/bin/activate

echo "[3/6] Sharpening the Axe (Updating Setup Tools)..."
python -m pip install --upgrade pip setuptools wheel
# Install NLTK immediately to ensure it is present regardless of later conflicts
python -m pip install nltk

echo ""
echo "=================================================="
echo "           SELECT YOUR GPU DRIVER VERSION"
echo "=================================================="
echo ""
echo "[1] CUDA 12.1 (Standard - Recommended for most Nvidia Graphics cards)"
echo "[2] CUDA 12.8 (Nightly - For the latest RTX 50-Series)"
echo "[3] CPU Only  (Slow - Not recommended for using OmniVoice, will still work with Kokoro)"
echo ""
read -p "Enter selection [1, 2, or 3]: " choice

if [ "$choice" == "1" ]; then
  pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
elif [ "$choice" == "2" ]; then
  pip install --pre torch torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
else
  pip install torch torchaudio
fi

if [ $? -ne 0 ]; then error_exit; fi

# --- 3. OmniVoice Setup ---
echo ""
echo "[4/6] Summoning the Voice (Installing OmniVoice TTS)..."

echo "Installing OmniVoice package..."
pip install omnivoice
if [ $? -ne 0 ]; then error_exit; fi

# --- 4. Main Requirements ---
echo ""
echo "[5/6] Finalizing the Craft (Installing Main Requirements)..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
  echo -e "${YELLOW}[WARNING] Main requirements reported an error.${NC}"
  echo "This is usually a version conflict. NLTK was pre-installed to ensure safety."
fi

# --- 5. NLTK Data Download ---
echo ""
echo "[6/6] Teaching the Runes (Downloading NLTK Data)..."
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('averaged_perceptron_tagger')"

echo ""
echo "=================================================="
echo "           INSTALLATION COMPLETE!"
echo "=================================================="
echo "The Khazad Voice TTS is ready. Follow the calibrate instructions on the github page."
read -n 1 -s -r -p "Press any key to continue..."
echo ""
exit 0
