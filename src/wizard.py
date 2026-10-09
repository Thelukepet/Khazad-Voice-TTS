# Imports

# > Standard Library
import sys

# > Local Dependencies
from src.config.ConfigManager import ConfigManager
from src.utils import setup_logger

log = setup_logger("WIZARD")


def _ask(prompt: str, choices: list[str] | None = None, default: str | None = None) -> str:
    """Simple, forgiving input helper for non-technical users.

    Accepts case-insensitive input, numbers as aliases for choices,
    and falls back to the default on empty input or invalid input
    (after re-asking once).
    """
    while True:
        raw = input(prompt).strip()
        if not raw and default is not None:
            return default
        if choices is None:
            return raw
        # Exact (case-insensitive) match
        for c in choices:
            if raw.lower() == c.lower():
                return c
        # Numeric alias: 1 -> first choice
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        print(f"  Please answer with one of: {', '.join(choices)}"
              + (f" (or just press Enter for '{default}')" if default else ""))


def _print_header() -> None:
    print()
    print("=" * 46)
    print("  Welcome to the Khazad Voice setup wizard")
    print("  Answer a few questions - you only do this once.")
    print("=" * 46)
    print()


def _detect_gpu() -> bool:
    """Best-effort NVIDIA GPU detection."""
    try:
        import torch

        return torch.cuda.is_available()
    except Exception:
        return False


def _device_choice() -> str:
    """Ask for the audio engine with GPU auto-detection."""
    gpu = _detect_gpu()
    if gpu:
        print("An NVIDIA graphics card was detected on this PC.")
        answer = _ask(
            "Use it for higher voice quality? [Y/n]: ",
            choices=["y", "n"],
            default="y",
        )
        if answer == "y":
            print("  -> Using high quality mode (GPU).")
            return "gpu"
        print("  -> Using fast mode (CPU).")
        return "cpu"

    print("No NVIDIA graphics card was detected, so Khazad will use fast mode (CPU).")
    _ask("Press Enter to continue...", default="")
    return "cpu"


def _game_mode_choice() -> str:
    """Ask which game version the user plays."""
    print()
    print("Which version of the game do you play?")
    print("  1. The Lord of the Rings Online (official servers) [most common]")
    print("  2. Echoes of Angmar (classic private server)")
    answer = _ask("Your choice (1 or 2): ", choices=["1", "2"], default="1")
    mode = "retail" if answer == "1" else "echoes"
    print(f"  -> {answer}.")
    return mode


def _store_mode_choice(mode: str) -> None:
    """Remember the game mode so the launcher can skip the wizard next time."""
    cfg = ConfigManager()
    if not cfg.config.has_section("Wizard"):
        cfg.config.add_section("Wizard")
    cfg.config.set("Wizard", "game_mode", mode)
    with open(cfg.config_path, "w") as f:
        cfg.config.write(f)


def _wizard_mode_chosen() -> str | None:
    """Return the stored game mode from a previous wizard run, if any."""
    try:
        cfg = ConfigManager()
        mode = cfg.config.get("Wizard", "game_mode", fallback=None)
        if mode in ("retail", "echoes", "static"):
            return mode
    except Exception:
        pass
    return None


def run_wizard() -> None:
    """Interactive first-run setup. Detects hardware, asks game version,
    saves preferences, then launches the narrator directly."""
    _print_header()

    # 1. Audio engine
    device = _device_choice()

    # 2. Game mode
    mode = _game_mode_choice()

    # 3. Remember the mode so future launches are one-click
    _store_mode_choice(mode)

    # 4. Launch
    print()
    print("Setup complete! Starting the narrator...")
    print("(Press F12 at any time to stop the voice. To change these")
    print(" settings later, run:  khazad --setup)")
    print()

    from src.engine_startup import EngineStartup

    EngineStartup(mode, device)


def maybe_run_wizard() -> bool:
    """Decide whether to launch the wizard on startup.

    Returns True if the wizard was launched (caller should do nothing else).
    The wizard runs when: no game mode is stored yet (first run), or the
    user explicitly asked for --setup.
    """
    if "--setup" in sys.argv:
        run_wizard()
        return True
    if _wizard_mode_chosen() is not None:
        return False
    # First run: no stored preference
    run_wizard()
    return True
