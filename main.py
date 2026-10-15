# Imports

# > Standard Library
import argparse
import os
from pathlib import Path

# Force AI models to download into the user data directory
from src.config.ConfigManager import ConfigManager

# > Local Dependencies
from src.engine_startup import EngineStartup

os.environ["HF_HOME"] = str(ConfigManager.USER_DATA_DIR / "models" / "huggingface")
os.environ["TORCH_HOME"] = str(ConfigManager.USER_DATA_DIR / "models" / "torch")


def _run_calibration(mode: str):
    """Launch the calibration script for the given mode.

    Retail and Echoes are calibrated from a screenshot (Voice Lab or
    the setup wizard); only static mode has a calibration script.
    """
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


def _start_engine(mode: str, device: str, voice_mix: bool = False) -> None:
    """Start the narrator, ensuring the character identity is known.

    Every entry point that runs the TTS (launcher scripts, menu choices,
    --mode runs) goes through here. The identity replaces the
    ${PLAYER}/${RACE}/${CLASS} placeholders in database quest text; if
    it has never been configured, the user is asked now - this is what
    replaces the generic 'Traveler' fallback with the real name.
    """
    from src.wizard import ensure_player_identity

    ensure_player_identity()
    EngineStartup(mode, device, voice_mix=voice_mix)


def print_header():
    """Print the startup banner."""
    print(r"""
    ========================================
       LOTRO NARRATOR - AI VOICE OVER
    ========================================
    """)


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
        choices=["static"],
        help="Run static-mode calibration (other modes calibrate from a screenshot)",
    )
    parser.add_argument(
        "--voice-lab",
        action="store_true",
        help="Launch the Voice Lab configuration suite",
    )
    parser.add_argument(
        "--voice-mix",
        action="store_true",
        help="[Experimental] Use separate voices for NPC dialogue (quoted) and narrator text",
    )
    parser.add_argument(
        "--install-retail-plugin",
        action="store_true",
        help="Install the getNPCNames LOTRO plugin",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run the first-time setup wizard again",
    )
    return parser.parse_args()


def _select_device() -> str:
    """Prompt the user to choose a TTS backend."""
    print("\n[SELECT AUDIO ENGINE]")
    print("1. CPU (Kokoro) [Default]")
    print("   -> Fast, Reliable. Works on all PCs.")
    print("2. GPU (OmniVoice)")
    print("   -> Higher Quality. REQUIRES NVIDIA GPU.")
    device_input = input("\nEnter choice (1 or 2): ").strip()
    return "gpu" if device_input == "2" else "cpu"


def get_device_arg(args: argparse.Namespace) -> str:
    """Return the TTS backend choice from *args* or prompt the user."""
    if args.device:
        return args.device
    return _select_device()


def _interactive_menu():
    """Show an interactive menu when launched with no arguments."""
    print("What would you like to do?\n")
    print("  1. Start Retail Mode (Auto-detect quest window)")
    print("  2. Start Echoes of Angmar Mode")
    print("  3. Start Static Mode (Fixed quest window)")
    print("  4. Calibrate Static Mode")
    print("  5. Voice Lab & Configuration (incl. screenshot calibration)")
    print("  6. Install LOTRO Plugin")
    print("  7. Start Retail Mode + Voice Mix (Experimental)")
    print("  8. Start Echoes Mode + Voice Mix (Experimental)")
    print("  9. Start Static Mode + Voice Mix (Experimental)")
    print()

    choice = input("Enter choice (1-9): ").strip()

    match choice:
        case "1":
            _start_engine("retail", _select_device())
        case "2":
            _start_engine("echoes", _select_device())
        case "3":
            _start_engine("static", _select_device())
        case "4":
            _run_calibration("static")
        case "5":
            _run_voice_lab()
        case "6":
            _run_install_plugin()
        case "7":
            _start_engine("retail", _select_device(), voice_mix=True)
        case "8":
            _start_engine("echoes", _select_device(), voice_mix=True)
        case "9":
            _start_engine("static", _select_device(), voice_mix=True)
        case _:
            print(f"Invalid choice: {choice}")


def main():
    """Main entry point for Khazad-Voice TTS."""
    print_header()

    args = get_args()

    # First-run wizard (also via --setup): detects hardware, asks game
    # version, stores preferences, then launches the narrator directly.
    from src.wizard import maybe_run_wizard

    if maybe_run_wizard():
        return

    if args.calibrate:
        _run_calibration(args.calibrate)
        return

    if args.voice_lab:
        _run_voice_lab()
        return

    if args.install_retail_plugin:
        _run_install_plugin()
        return

    if args.mode:
        _start_engine(args.mode, get_device_arg(args), voice_mix=args.voice_mix)
    else:
        _interactive_menu()


if __name__ == "__main__":
    main()
