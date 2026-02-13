import sys
from pathlib import Path

# Ensure src is in python path
sys.path.append(str(Path(__file__).parent))

from src.voice_lab.ui import create_ui

if __name__ == "__main__":
    demo = create_ui()
    demo.launch(inbrowser=True)
