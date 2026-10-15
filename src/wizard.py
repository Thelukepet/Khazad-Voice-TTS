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


# Character races and classes as rendered by the game for ${RACE}/${CLASS}
_RACES = ["Man", "Elf", "Dwarf", "Hobbit"]
_CLASSES = [
    "Guardian",
    "Champion",
    "Hunter",
    "Burglar",
    "Captain",
    "Minstrel",
    "Lore-master",
    "Rune-keeper",
    "Warden",
    "Beorning",
    "Brawler",
]


def _identity_choice() -> None:
    """Ask for the character's name, race and class.

    These values replace the ``${PLAYER}``, ``${RACE}`` and ``${CLASS}``
    placeholders in database quest text whenever OCR cannot read the
    rendered values off the screen. Existing values (if any) are offered
    as defaults, so re-running the wizard keeps them on Enter.
    """
    cfg = ConfigManager()
    cur_name = cfg.get_str("PlayerIdentity", "character_name", fallback="").strip()
    cur_race = cfg.get_str("PlayerIdentity", "character_race", fallback="").strip()
    cur_class = cfg.get_str("PlayerIdentity", "character_class", fallback="").strip()

    print()
    print("A few questions about your character.")
    print("These personalise the spoken quest dialogue, so NPCs can")
    print("address you by name instead of a generic placeholder.")

    # Name (required - it replaces the generic 'Traveler' fallback)
    while True:
        prompt = f"Character name [{cur_name}]: " if cur_name else "Character name: "
        name = _ask(prompt, default=cur_name or None)
        if name:
            break
        print("  Please enter a name - it is used to personalise dialogue.")

    # Race
    print()
    print("What is your character's race?")
    for i, race in enumerate(_RACES, 1):
        print(f"  {i}. {race}")
    race = _ask(
        "Your choice: ",
        choices=_RACES,
        default=cur_race if cur_race in _RACES else "Man",
    )

    # Class
    print()
    print("What is your character's class?")
    for i, cls in enumerate(_CLASSES, 1):
        print(f"  {i}. {cls}")
    char_class = _ask(
        "Your choice: ",
        choices=_CLASSES,
        default=cur_class if cur_class in _CLASSES else "Hunter",
    )

    _store_identity(name, race, char_class)
    print(f"  -> Got it: {name} the {race} {char_class}.")


def _store_identity(name: str, race: str, char_class: str) -> None:
    """Persist the character identity to the PlayerIdentity config."""
    cfg = ConfigManager()
    if not cfg.config.has_section("PlayerIdentity"):
        cfg.config.add_section("PlayerIdentity")
    cfg.config.set("PlayerIdentity", "character_name", name)
    cfg.config.set("PlayerIdentity", "character_race", race)
    cfg.config.set("PlayerIdentity", "character_class", char_class)
    with open(cfg.config_path, "w") as f:
        cfg.config.write(f)


def ensure_player_identity() -> None:
    """Make sure a character name is configured before the narrator runs.

    Called on every entry point that starts the TTS (launcher scripts,
    menu choices, --mode runs). Prompts only when a name has never been
    entered; once configured, starts happen without interruption.
    """
    try:
        cfg = ConfigManager()
        name = cfg.get_str("PlayerIdentity", "character_name", fallback="").strip()
    except Exception:
        return  # never block the narrator over a config problem
    if name:
        return
    _identity_choice()


def _calibration_choice(mode: str) -> None:
    """Offer screenshot-based calibration (the easy path).

    The narrator can run on the shipped default layout, so this is
    optional - but a screenshot calibration makes detection exact for
    the user's own UI skin and resolution.
    """
    import cv2

    print()
    print("Optional: calibrate the quest-window layout from a screenshot.")
    print("This is only needed if detection misses your quest window.")
    answer = _ask("Calibrate now with a screenshot? [y/N]: ", choices=["y", "n"], default="n")
    if answer == "n":
        print("  -> Skipped - the default layout will be used.")
        return

    print("1. Open the game and a quest window (fully visible).")
    print("2. Take a screenshot (e.g. Print Screen / Win+Print Screen).")
    path = _ask("3. Enter the screenshot file path: ")
    if not path:
        print("  -> No path given - skipped.")
        return

    try:
        img = cv2.imread(path.strip().strip('"'))
        if img is None:
            print("  ⚠️  Could not read that image file - calibration skipped.")
            return
        from src.auto_calibrate import auto_calibrate

        ok, rep = auto_calibrate(img, mode)
    except Exception as exc:
        print(f"  ⚠️  Calibration failed: {exc}")
        return

    if ok:
        print(f"  ✅ {rep['message']}")
    else:
        print(f"  ⚠️  {rep['message']}")
        print("     You can retry later from the Voice Lab (Screenshot Tester")
        print("     tab, 'Calibrate from this screenshot'), or use the manual")
        print("     calibration scripts.")


def run_wizard() -> None:
    """Interactive first-run setup. Detects hardware, asks game version,
    asks character identity, offers screenshot calibration, saves
    preferences, then launches the narrator."""
    _print_header()

    # 1. Audio engine
    device = _device_choice()

    # 2. Game mode
    mode = _game_mode_choice()

    # 3. Character identity (personalises quest dialogue)
    _identity_choice()

    # 4. Optional screenshot calibration
    _calibration_choice(mode)

    # 5. Remember the mode so future launches are one-click
    _store_mode_choice(mode)

    # 5. Launch
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
