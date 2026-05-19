#!/bin/bash

# Change working directory to the project root
cd "$(dirname "$0")/.."

# --- 1. Script Setup & Colors ---
set -e # Exit immediately if a command fails.

RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Set the terminal window title
echo -ne "\033]0;KHAZAD VOICE - STATIC MODE\007"

# --- 2. Check for Environment ---
if [ ! -d "venv" ]; then
    echo -e "${RED}[ERROR]${NC} 'venv' folder not found. Please run './Linux/install.sh' first."
    read -p "Press Enter to exit..."
    exit 1
fi

# --- 3. Launch Application in Static Mode ---
echo -e "${CYAN}[INFO]${NC} Starting Static Mode..."

# Activate the virtual environment
source venv/bin/activate

# Run the main Python script with the '--mode static' argument
python main.py --mode static

# --- 4. Pause on Exit ---
# This ensures the user can read any final output before the window closes.
read -p "Press Enter to close this window..."
