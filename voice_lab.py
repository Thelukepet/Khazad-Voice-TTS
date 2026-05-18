import os
import sys
from pathlib import Path

# Force AI models to download into the user data directory
from src.config.ConfigManager import ConfigManager

os.environ["HF_HOME"] = str(ConfigManager.USER_DATA_DIR / "models" / "huggingface")
os.environ["TORCH_HOME"] = str(ConfigManager.USER_DATA_DIR / "models" / "torch")

# Ensure src is in python path
sys.path.append(str(Path(__file__).resolve().parent))

from src.voice_lab.ui import create_ui

if __name__ == "__main__":
    demo = create_ui()
    demo.launch(inbrowser=True)
