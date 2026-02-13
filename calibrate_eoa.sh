#!/bin/bash

# --- 1. HEADER  ---
echo -ne "\033]0;CALIBRATE - ECHOES OF ANGMAR\007"


# --- 2. Check for and Activate Virtual Environment ---
if [ -f ".venv/bin/activate" ]; then
    echo -e "${CYAN}[INFO]${NC} Activating virtual environment from '.venv'..."
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    echo -e "${CYAN}[INFO]${NC} Activating virtual environment from 'venv'..."
    source venv/bin/activate
else
    # ... (error handling) ...
    exit 1
fi

# --- 3. Run the Calibration Script ---
export QT_QPA_PLATFORM=xcb
python calibrate_echoes.py

# --- EXIT ---
read -p "Press Enter to exit..."
