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

# Check for user-specified Python binary
if [ "$1" != "" ]; then
  arg1="$1"
  val1="$2"
  if [ "$arg1" == "--python-bin" -a "$val1" != "" ]; then
    PYTHON_CMD=$val1
  fi
fi

if [ "$PYTHON_CMD" == "" ]; then
  # Try to find Python 3.12 (preferred) or fallback to system python
  PYTHON_CMD="python3"
  if command -v python3.12 > /dev/null; then
    echo "[INFO] Found Python 3.12."
    PYTHON_CMD="python3.12"
  else
    # Fallback check
    if ! command -v python3 > /dev/null; then
      echo -e "${YELLOW}[ERROR] Python is not installed or not in PATH.${NC}"
      echo "Please install Python 3.12."
      read -n 1 -s -r -p "Press any key to continue..."
      echo ""
      exit 1
    fi
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
$PYTHON_CMD -m pip install --upgrade pip setuptools wheel
# Install NLTK immediately to ensure it is present regardless of later conflicts
$PYTHON_CMD -m pip install nltk

# --- 3. OmniVoice Setup (BEFORE PyTorch to prevent torch overwrite) ---
echo ""
echo "[4/6] Summoning the Voice (Installing OmniVoice TTS)..."

echo "Installing OmniVoice package..."
pip install omnivoice
if [ $? -ne 0 ]; then error_exit; fi

# --- 4. PyTorch Setup (AFTER OmniVoice so CUDA version wins) ---
echo ""
echo "=================================================="
echo "           SELECT YOUR GPU DRIVER VERSION"
echo "=================================================="
echo ""
echo "[1] CUDA 12.1 (Legacy   - driver 527+, RTX 20/30/40 series)"
echo "[2] CUDA 12.6 (Standard - driver 560+, RTX 20/30/40 series, recommended)"
echo "[3] CUDA 12.8 (Latest   - driver 570+, required for RTX 50-series)"
echo "[4] CPU Only  (Slow - OmniVoice voice cloning will NOT be available)"
echo ""
read -p "Enter selection [1, 2, 3, or 4]: " choice

if [ "$choice" == "1" ]; then
  pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
elif [ "$choice" == "2" ]; then
  pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126
elif [ "$choice" == "3" ]; then
  pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
else
  pip install torch torchaudio
fi

if [ $? -ne 0 ]; then error_exit; fi

# --- 5. Main Requirements ---
echo ""
echo "[5/6] Finalizing the Craft (Installing Main Requirements)..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
  echo -e "${YELLOW}[WARNING] Main requirements reported an error.${NC}"
  echo "This is usually a version conflict. NLTK was pre-installed to ensure safety."
fi

# --- 6. NLTK Data Download ---
echo ""
echo "[6/6] Teaching the Runes (Downloading NLTK Data)..."
$PYTHON_CMD -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('averaged_perceptron_tagger')"

cat >~/.local/share/applications/Khazad\ Voice\ TTS\ \(LOTRO\).desktop <<EOL
[Desktop Entry]
Name=Khazad Voice TTS (LOTRO)
Comment=Immersive AI Narrator for The Lord of the Rings Online
Path=$PWD
Exec=$PWD/Linux/start_lotro.sh
Icon=$PWD/installer/logo.ico
Terminal=true
Type=Application
Categories=Game;
EOL

cat >~/.local/share/applications/Khazad\ Voice\ TTS\ \(EOA\).desktop <<EOL
[Desktop Entry]
Name=Khazad Voice TTS (EOA)
Comment=Immersive AI Narrator for The Lord of the Rings Online
Path=$PWD
Exec=$PWD/Linux/start_eoa.sh
Icon=$PWD/installer/logo.ico
Terminal=true
Type=Application
Categories=Game;
EOL

cat >~/.local/share/applications/Khazad\ Voice\ TTS\ Configuration\ Suite.desktop <<EOL
[Desktop Entry]
Name=Khazad Voice TTS Configuration Suite
Comment=TTS engine configuration
Path=$PWD
Exec=$PWD/Linux/configure.sh
Icon=$PWD/installer/logo.ico
Terminal=true
Type=Application
Categories=Game;
EOL

echo ""
echo "=================================================="
echo "           INSTALLATION COMPLETE!"
echo "=================================================="
echo "The Khazad Voice TTS is ready. Follow the calibrate instructions on the github page."
read -n 1 -s -r -p "Press any key to continue..."
echo ""
exit 0
