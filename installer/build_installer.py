"""
Khazad Voice TTS — Installer Builder

Compiles installer/setup.py into a standalone Khazad-Voice-Setup.exe
using PyInstaller. The resulting .exe requires no Python installation
to run — it's a self-contained bootstrapper that downloads everything
via uv on the end user's machine.

Usage:
    python build_installer.py          # Build the .exe
    python build_installer.py --clean  # Clean build artifacts first
"""

import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image

    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

# ─── Configuration ────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTALLER_DIR = PROJECT_ROOT / "installer"
SETUP_SCRIPT = INSTALLER_DIR / "setup.py"
OUTPUT_NAME = "Khazad-Voice-Setup"
DIST_DIR = INSTALLER_DIR / "dist"
BUILD_DIR = INSTALLER_DIR / "build"
SPEC_FILE = INSTALLER_DIR / f"{OUTPUT_NAME}.spec"

LOGO_JPG = INSTALLER_DIR / "logo.jpg"
LOGO_ICO = INSTALLER_DIR / "logo.ico"


def convert_logo_to_ico():
    """Convert logo.jpg to logo.ico for use as .exe and shortcut icon."""
    # Always recreate to pick up source changes
    if LOGO_ICO.exists():
        LOGO_ICO.unlink()

    if not LOGO_JPG.exists():
        print(f"  [WARN] {LOGO_JPG} not found - building without icon.")
        return False

    if not HAS_PILLOW:
        print(f"  [WARN] Pillow not installed - cannot convert logo.jpg to .ico.")
        print(f"         Install with: pip install Pillow")
        return False

    try:
        img = Image.open(LOGO_JPG).convert("RGBA")
        # ICO needs square dimensions; generate all standard Windows icon sizes
        sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
        # Pillow handles resizing internally when saving ICO with sizes parameter
        img.save(
            str(LOGO_ICO),
            format="ICO",
            sizes=sizes,
        )
        print(f"  Converted logo.jpg -> logo.ico ({len(sizes)} sizes)")
        return True
    except Exception as e:
        print(f"  [WARN] Could not convert logo.jpg: {e}")
        return False


def check_pyinstaller() -> str:
    """Ensure PyInstaller is available. Returns the command to invoke it."""
    # Try the python module form first (works in venv)
    try:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [sys.executable, "-m", "PyInstaller"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Try bare command
    try:
        subprocess.run(
            ["pyinstaller", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        return ["pyinstaller"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    print("[ERROR] PyInstaller is not installed.")
    print("Install it with:  pip install pyinstaller")
    sys.exit(1)


def clean_artifacts():
    """Remove previous build artifacts."""
    for d in (BUILD_DIR, DIST_DIR):
        if d.exists():
            print(f"Removing {d}…")
            shutil.rmtree(d)

    if SPEC_FILE.exists():
        SPEC_FILE.unlink()
        print(f"Removing {SPEC_FILE}…")


def build(pi_cmd: list):
    """Run PyInstaller to compile setup.py into a single .exe."""
    if not SETUP_SCRIPT.exists():
        print(f"[ERROR] {SETUP_SCRIPT} not found.")
        sys.exit(1)

    cmd = [
        *pi_cmd,
        "--name",
        OUTPUT_NAME,
        "--onefile",
        "--windowed",  # No console window behind the GUI
        "--clean",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--specpath",
        str(INSTALLER_DIR),
        # Prevent PyInstaller from scanning the entire project tree
        "--contents-directory",
        ".",
    ]

    # Add icon if logo.ico exists
    if LOGO_ICO.exists():
        cmd += ["--icon", str(LOGO_ICO)]
        # Bundle logo.ico into the exe so shortcuts can use it
        cmd += ["--add-data", f"{LOGO_ICO};."]

    cmd.append(str(SETUP_SCRIPT))

    print(f"\n{'═' * 60}")
    print(f"  Building {OUTPUT_NAME}.exe")
    print(f"{'═' * 60}\n")
    print(f"  Command: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=str(INSTALLER_DIR))

    if result.returncode != 0:
        print(f"\n[ERROR] PyInstaller failed with exit code {result.returncode}.")
        sys.exit(1)

    exe_path = DIST_DIR / f"{OUTPUT_NAME}.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n{'═' * 60}")
        print(f"  ✅  Build successful!")
        print(f"{'═' * 60}")
        print(f"  Output : {exe_path}")
        print(f"  Size   : {size_mb:.1f} MB")
        print(f"\n  Distribute this .exe to end users.")
        print(f"  It downloads Python + uv + all dependencies at runtime.\n")
    else:
        print(f"\n[ERROR] Expected output not found: {exe_path}")
        sys.exit(1)


def main():
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    if "--clean" in args:
        clean_artifacts()

    convert_logo_to_ico()
    pi_cmd = check_pyinstaller()
    build(pi_cmd)


if __name__ == "__main__":
    main()
