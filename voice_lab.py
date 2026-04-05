import os
import sys
from pathlib import Path

# Force AI models to download into the local installation folder
_install_dir = Path(__file__).resolve().parent
os.environ["HF_HOME"] = str(_install_dir / "models" / "huggingface")
os.environ["TORCH_HOME"] = str(_install_dir / "models" / "torch")

# Ensure src is in python path
sys.path.append(str(_install_dir))

from src.voice_lab.ui import create_ui

if __name__ == "__main__":
    demo = create_ui()
    demo.launch(inbrowser=True)