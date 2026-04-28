#!/bin/bash

# Change working directory to the project root
cd "$(dirname "$0")/.."

# --- 1. HEADER  ---
echo -ne "\033]0;CALIBRATE - ECHOES OF ANGMAR\007"

# --- 2. Check for and Activate Virtual Environment ---
if [ -f "venv/bin/activate" ]; then
    echo -e "${CYAN}[INFO]${NC} Activating virtual environment from 'venv'..."
    source venv/bin/activate
else
    echo -e "${RED}[ERROR]${NC} 'venv' folder not found. Please run './Linux/install.sh' first."
    read -p "Press Enter to exit..."
    exit 1
fi

# --- 3. Run the Calibration Script ---
export QT_QPA_PLATFORM=xcb
python src/calibrate_echoes.py

# --- EXIT ---
read -p "Press Enter to exit..."