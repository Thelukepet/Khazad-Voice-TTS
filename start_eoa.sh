#!/bin/bash

# --- 1. Script Setup & Colors ---
set -e # Exit immediately if a command fails.

RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Set the terminal window title
echo -ne "\033]0;KHAZAD VOICE - ECHOES OF ANGMAR\007"

# --- 2. Check for Environment ---
if [ ! -d "venv" ]; then
    echo -e "${RED}[ERROR]${NC} 'venv' folder not found. Please run './install.sh' first."
    read -p "Press Enter to exit..."
    exit 1
fi

# --- 3. Launch Application in Echoes of Angmar Mode ---
echo -e "${CYAN}[INFO]${NC} Starting Echoes of Angmar Mode..."

# Activate the virtual environment
source venv/bin/activate

# Run the main Python script with the '--mode echoes' argument
python main.py --mode echoes

# --- 4. Pause on Exit ---
# This ensures the user can read any final output before the window closes.
read -p "Press Enter to close this window..."
