# Imports

# > Standard Library
import argparse
import os
from pathlib import Path

# Force AI models to download into the user data directory
from src.config.ConfigManager import ConfigManager

os.environ["HF_HOME"] = str(ConfigManager.USER_DATA_DIR / "models" / "huggingface")
os.environ["TORCH_HOME"] = str(ConfigManager.USER_DATA_DIR / "models" / "torch")

# > Local Dependencies
from src.engine_startup import EngineStartup
from src.utils import setup_logger

log = setup_logger("MAIN")


# ---------------------------------------------------------------------------
# Sub-command helpers
# ---------------------------------------------------------------------------


def _run_calibration(mode: str):
    """Launch the calibration script for the given mode."""
    if mode == "retail":
        from src.calibrate_retail import main as calibrate_main
    elif mode == "echoes":
        from src.calibrate_echoes import main as calibrate_main
    else:
        from src.calibrate_static import main as calibrate_main
    calibrate_main()


def _run_voice_lab():
    """Launch the Voice Lab configuration suite."""
    from src.voice_lab.ui import create_ui

    demo = create_ui()
    demo.launch(inbrowser=True)


def _run_install_plugin():
    """Install the getNPCNames LOTRO plugin to the user's Documents folder."""
    import shutil

    base_dir = ConfigManager._find_project_root()
    src_plugin = base_dir / "plugins" / "Dt192"
    if not src_plugin.exists():
        print(f"ERROR: Plugin source not found at {src_plugin}")
        return

    # Standard LOTRO plugin directory
    lotro_plugins = (
        Path.home() / "Documents" / "The Lord of the Rings Online" / "plugins"
    )
    dst_plugin = lotro_plugins / "Dt192"

    if dst_plugin.exists():
        print(f"Plugin already installed at {dst_plugin}")
        print("Updating...")
        shutil.rmtree(dst_plugin)

    shutil.copytree(src_plugin, dst_plugin)
    print(f"Plugin installed to {dst_plugin}")
    print("You may need to reload plugins in-game with /plugins refresh")


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def print_header():
    """Print the startup banner."""
    print(r"""
    ========================================
       LOTRO NARRATOR - AI VOICE OVER
    ========================================
    """)


def print_usage():
    """Print CLI usage information."""
    print("Usage:")
    print("python main.py --voice-lab")
    print("python main.py --mode <retail/static/echoes> [--device <cpu/gpu>]")
    print("python main.py --calibrate <retail/echoes/static>")
    print("python main.py --install-retail-plugin")
    print("")


def get_args():
    """Parse and return CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Khazad Voice TTS – AI Narrator for LOTRO"
    )
    parser.add_argument(
        "--mode", choices=["retail", "static", "echoes"], help="Game mode to start in"
    )
    parser.add_argument(
        "--device", choices=["gpu", "cpu"], help="Audio engine to start in"
    )
    parser.add_argument(
        "--calibrate",
        choices=["retail", "echoes", "static"],
        help="Run calibration for the given game mode",
    )
    parser.add_argument(
        "--voice-lab",
        action="store_true",
        help="Launch the Voice Lab configuration suite",
    )
    parser.add_argument(
        "--install-retail-plugin",
        action="store_true",
        help="Install the getNPCNames LOTRO plugin",
    )
    return parser.parse_args()


def get_device_arg(args: argparse.Namespace) -> str:
    """Return the TTS backend choice from *args* or prompt the user."""
    if args.device:
        return args.device

    print("\n[SELECT AUDIO ENGINE]")
    print("1. CPU (Kokoro) [Default]")
    print("   -> Fast, Reliable. Works on all PCs.")
    print("2. GPU (OmniVoice)")
    print("   -> Higher Quality. REQUIRES NVIDIA GPU.")
    device_input = input("\nEnter choice (1 or 2): ").strip()
    return "gpu" if device_input == "2" else "cpu"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    """Main entry point for Khazad-Voice TTS."""
    print_header()

    args = get_args()

    # --- Sub-commands that exit early ---
    if args.calibrate:
        _run_calibration(args.calibrate)
        return

    if args.voice_lab:
        _run_voice_lab()
        return

    if args.install_retail_plugin:
        _run_install_plugin()
        return

    # --- Engine start (requires device selection) ---
    if args.mode:
        EngineStartup(args.mode, get_device_arg(args))
    else:
        print_usage()


if __name__ == "__main__":
    main()
