#!/bin/bash

# Change working directory to the project root
cd "$(dirname "$0")/.."

echo "Khazad-Voice: Static Quest Window Calibration"
source venv/bin/activate
python src/calibrate_static.py