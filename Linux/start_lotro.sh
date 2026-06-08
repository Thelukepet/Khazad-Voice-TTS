#!/bin/bash

# Change working directory to the project root
cd "$(dirname "$0")/.."

# --- 1. Script Setup & Colors ---
set -e # Exit immediately if a command fails.

RED='\033[0;31m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Set the terminal window title
echo -ne "\033]0;KHAZAD VOICE - RETAIL MODE\007"

# --- 2. Check for Environment ---
if [ ! -d "venv" ]; then
    echo -e "${RED}[ERROR]${NC} 'venv' folder not found. Please run './Linux/install.sh' first."
    read -p "Press Enter to exit..."
    exit 1
fi

# --- 3. Mode Selection ---
echo -e "${CYAN}[INFO]${NC} Starting Retail Mode..."
echo ""
echo "  1. Retail Mode"
echo -e "  2. Retail Mode + Voice Mix ${YELLOW}[Experimental]${NC}"
echo ""
read -p "Enter choice (1 or 2): " choice

source venv/bin/activate

if [ "$choice" = "2" ]; then
    echo -e "${CYAN}[INFO]${NC} Starting Retail Mode with Voice Mix..."
    python main.py --mode retail --voice-mix
else
    echo -e "${CYAN}[INFO]${NC} Starting Retail Mode..."
    python main.py --mode retail
fi

# --- 4. Pause on Exit ---
read -p "Press Enter to close this window..."
