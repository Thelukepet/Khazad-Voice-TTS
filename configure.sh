#!/bin/bash

# Define Colors (Matches the "0B" Aqua/Cyan vibe)
CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Ensure we run from the script folder
cd "$(dirname "${BASH_SOURCE[0]}")" || exit

# Clear screen to mimic cls/@echo off
clear

echo -e "${CYAN}==========================================================${NC}"
echo -e "${CYAN}                KHAZAD VOICE CONFIGURATION                ${NC}"
echo -e "${CYAN}    \"Forge your settings. Config your settings for CPU or GPU.\"${NC}"
echo -e "${CYAN}==========================================================${NC}"
echo ""

# --- Check for Venv ---
if [ ! -d "venv" ]; then
    echo -e "${RED}[ERROR] Virtual environment not found. Run install.sh first.${NC}"
    echo "Note: Do not copy a 'venv' folder from Windows; it must be recreated on Linux."
    read -rp "Press Enter to exit..."
    exit 1
fi

# --- 1. CHECK FFMPEG ---
echo -e "${GREEN}[INFO] Checking for FFmpeg...${NC}"

if ! command -v ffmpeg &> /dev/null; then
    echo ""
    echo -e "${RED}[CRITICAL] FFmpeg is missing!${NC}"
    echo "The Voice Lab requires FFmpeg to process audio files."
    echo ""
    
    read -rp "Attempt to install FFmpeg automatically? (y/n): " install_choice
    if [[ "$install_choice" =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}[INFO] Attempting installation... (Root password may be required)${NC}"
        
        # Detect Package Manager and Install
        if command -v apt &> /dev/null; then
            sudo apt update && sudo apt install -y ffmpeg
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y ffmpeg
        elif command -v pacman &> /dev/null; then
            sudo pacman -S --noconfirm ffmpeg
        elif command -v brew &> /dev/null; then
            brew install ffmpeg
        else
            echo -e "${RED}[ERROR] Package manager not found. Please install FFmpeg manually.${NC}"
            read -rp "Press Enter to exit..."
            exit 1
        fi

        # Check if install succeeded
        if ! command -v ffmpeg &> /dev/null; then
             echo -e "${RED}[ERROR] Install failed. Please install FFmpeg manually.${NC}"
             read -rp "Press Enter to exit..."
             exit 1
        fi

        echo ""
        echo -e "${GREEN}[IMPORTANT] FFmpeg installed. Please restart this script.${NC}"
        read -rp "Press Enter to exit..."
        exit 0
    else
        echo "Please install FFmpeg manually."
        read -rp "Press Enter to exit..."
        exit 1
    fi
fi

echo -e "${GREEN}[OK] FFmpeg found.${NC}"

# --- 2. LAUNCH APP ---
echo -e "${GREEN}[INFO] Activating environment...${NC}"
# Linux venv structure uses /bin/activate, not \Scripts\activate
source venv/bin/activate

echo ""
echo -e "${GREEN}[INFO] Ensuring Lab Dependencies are installed...${NC}"
# Installing dependencies
pip install gradio openai-whisper soundfile -q

echo ""
echo -e "${GREEN}[INFO] Starting Configuration Suite...${NC}"

# Run the python script
python voice_lab.py

# Capture exit code and pause if there was an error
if [ $? -ne 0 ]; then
    read -rp "An error occurred. Press Enter to exit..."
fi

