# Imports

# > Standard Library
import argparse
import os
import sys

from pathlib import Path
from threading import Event

# > Local Dependencies
import src.calibrate_echoes as echoes_calibrator
import src.calibrate_retail as retail_calibrator
import src.calibrate_static as static_calibrator

from src.engine_startup import EngineStartup
from src.utils import setup_logger
from src.voice_lab.ui import create_ui

# Force AI models to download into the local installation folder
_install_dir = Path(__file__).resolve().parent
os.environ["HF_HOME"] = str(_install_dir / "models" / "huggingface")
os.environ["TORCH_HOME"] = str(_install_dir / "models" / "torch")

# Ensure src is in python path
sys.path.append(str(_install_dir))

log = setup_logger("MAIN")

# Shared events for cross-thread signaling
capture_trigger = Event()  # Echoes mode: middle-click
retail_capture_trigger = Event()  # Retail static mode: middle-click


def main():
    """
    Main entry point for Khazad-Voice TTS.

    Returns
    -------
    None
    """
    print_header()

    args = get_args()

    if args.mode:
        EngineStartup(args.mode, get_device_arg(args))
    elif args.calibrate:
        match args.calibrate:
            case "retail":
                retail_calibrator.main()
            case "echoes":
                echoes_calibrator.main()
            case "static":
                static_calibrator.main()
    elif args.voice_lab:
        voice_lab = create_ui()
        voice_lab.launch(inbrowser=True)
    else:
        print_usage()


def print_header():
    """
    Prints out the header message.

    Returns
    -------
    None
    """
    print(r"""
    ========================================
       LOTRO NARRATOR - AI VOICE OVER
    ========================================
    """)


def print_usage():
    """
    Prints out the usage message.

    Returns
    -------
    None
    """
    print("Usage:")
    print("python main.py --voice-lab")
    print("python main.py --mode <retail/echoes> [--device <cpu/gpu>]")
    print("python main.py --calibrate <retail/echoes/static>")
    print("")


def get_args():
    """
    Gets the CLI arguments.

    Returns
    -------
    argparse.Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["retail", "echoes", "static"], help="Game mode to start in")
    parser.add_argument("--device", choices=["gpu", "cpu"], help="Audio engine to start in")
    parser.add_argument("--calibrate", choices=["retail", "echoes", "static"], help="Game mode to calibrate")
    parser.add_argument("--voice-lab", action='store_true', help="Start Khazad voice lab")
    return parser.parse_args()


def get_device_arg(args: argparse.Namespace):
    """
    Gets the TTS Backend to be used from the CLI arguments or from user input.

    Parameters
    ----------
    args CLI arguments

    Returns
    -------
    str
    """
    if args.device:
        return args.device
    else:
        print("\n[SELECT AUDIO ENGINE]")
        print("1. CPU (Kokoro) [Default]")
        print("   -> Fast, Reliable. Works on all PCs.")
        print("2. GPU (OmniVoice)")
        print("   -> Higher Quality. REQUIRES NVIDIA GPU.")
        device_input = input("\nEnter choice (1 or 2): ").strip()
        return "gpu" if device_input == "2" else "cpu"


if __name__ == "__main__":
    main()