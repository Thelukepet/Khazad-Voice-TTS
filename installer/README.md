# Khazad Voice TTS — Windows Installer (Experimental)

> A one-click setup wizard that downloads Python, installs all dependencies via **uv**, and gets Khazad Voice TTS running with zero manual configuration.

## What This Is

An experimental `.exe` bootstrapper that replaces the manual `install.bat` / `install.sh` process. End users download a single ~15 MB file, pick their GPU version, and everything else is automatic.

### What it does

1. **Downloads [uv](https://github.com/astral-sh/uv)** — the ultra-fast Python package manager (10–100× faster than pip).
2. **Installs Python 3.12** via `uv python install` — no need for the user to have Python pre-installed.
3. **Downloads the project source** from GitHub (zip archive, no git required).
4. **Creates a virtual environment** via `uv venv`.
5. **Installs PyTorch** with the user's chosen CUDA/CPU version.
6. **Installs OmniVoice** (GPU users only) via pip.
7. **Installs all Python dependencies** via `uv pip install`.
8. **Downloads NLTK data** (punkt, punkt_tab, averaged_perceptron_tagger).
9. **Checks for FFmpeg and Tesseract** — auto-installs FFmpeg via winget if missing.
10. **Creates desktop shortcuts** (`.bat` launchers).

---

## Building the .exe (For Developers)

### Prerequisites

- Python 3.10+ with `tkinter` (included in standard Python on Windows)
- PyInstaller: `pip install pyinstaller`

### Build

```bash
# From the installer/ directory:
python build_installer.py

# Or with a clean build (removes old artifacts first):
python build_installer.py --clean
```

### Output

The built `.exe` will be at:

```
installer/dist/Khazad-Voice-Setup.exe
```

Typical size: **~12–18 MB** (only bundles `tkinter` — everything else is downloaded at runtime).

### Distribute

Upload `Khazad-Voice-Setup.exe` to your GitHub Releases page. End users download and run it — that's it.

---

## End User Experience

### Step 1 — Welcome

The wizard opens with a dark-themed GUI showing GPU auto-detection results.

- ✅ NVIDIA GPU detected → GPU mode (OmniVoice) will be recommended.
- ⚠ No NVIDIA GPU → CPU mode (Kokoro) will be recommended.

### Step 2 — Install Location

Default: `C:\Khazad-Voice-TTS`. The user can browse to change it.

Disk space estimates are shown:
- CPU (Kokoro): ~1.5 GB
- GPU CUDA 12.1: ~4.5 GB
- GPU CUDA 12.8: ~4.5 GB

### Step 3 — GPU Driver Selection

The same three options from `install.bat`:

| Option | Description | PyTorch Index |
|--------|-------------|---------------|
| CUDA 12.1 | Standard — most NVIDIA cards (RTX 20/30/40, GTX series) | `whl/cu121` |
| CUDA 12.8 | Nightly — RTX 50-series | `whl/nightly/cu128` |
| CPU Only | Kokoro TTS, no GPU needed | `whl/cpu` |

If no NVIDIA GPU was detected, CPU mode is pre-selected with a warning.

### Step 4 — Installation

A live log shows every step with a progress bar. The user can cancel at any time.

Steps run:
1. Acquire `uv` (download if not on PATH)
2. Install Python 3.12 via `uv`
3. Download project source from GitHub
4. Create virtual environment
5. Install PyTorch (selected version)
6. Install OmniVoice (GPU only)
7. Install application requirements
8. Download NLTK data + check FFmpeg/Tesseract
9. Create desktop shortcuts

### Step 5 — Complete

The user sees launch buttons for:
- **Retail Mode** — `python main.py --mode retail`
- **Echoes of Angmar** — `python main.py --mode echoes`
- **Voice Lab** — `python voice_lab.py`

Desktop `.bat` shortcuts are also created.

---

## Architecture

```
installer/
├── setup.py              # Main wizard application (tkinter GUI)
├── build_installer.py    # Compiles setup.py → Khazad-Voice-Setup.exe
├── README.md             # This file
├── dist/                 # Build output (created by build_installer.py)
│   └── Khazad-Voice-Setup.exe
└── build/                # PyInstaller temp files
```

### Why this approach (not a PyInstaller monolith)

The installer is a **bootstrapper**, not a bundled application. Reasons:

1. **Size**: Bundling PyTorch + CUDA would make a 4–5 GB `.exe`. The bootstrapper is ~15 MB and downloads only what's needed.
2. **GPU/CPU split**: Users pick ONE PyTorch build. A monolith would need to bundle all three.
3. **Updatability**: The bootstrapper always downloads the latest source from GitHub. No rebuild needed for code changes.
4. **Maintainability**: The installer code is simple Python/tkinter — no hidden import hacks or PyInstaller hooks needed.

### Why uv instead of pip

- **10–100× faster** dependency resolution and installation.
- **Manages Python itself**: `uv python install 3.12` removes the need for users to install Python manually.
- **Compatible**: `uv pip install` accepts the same arguments as pip (including `--index-url` for PyTorch wheels).

---

## Requirements for End Users

| Requirement | Needed Before Running? | Auto-Installed? |
|-------------|----------------------|-----------------|
| Python | ❌ No | ✅ via `uv python install` |
| pip / venv | ❌ No | ✅ via `uv` |
| Git | ❌ No | ❌ (not needed — uses zip downloads) |
| Internet | ✅ **Yes** | — |
| FFmpeg | ❌ No | ✅ via `winget` (if missing) |
| Tesseract OCR | ❌ No | ⚠ Manual (warned if missing) |
| NVIDIA GPU | For GPU mode only | Auto-detected |

---

## Known Limitations

1. **No offline support** — everything is downloaded at install time. An offline installer would require bundling PyTorch (multi-GB).

2. **Tesseract is not auto-installed** — the user must install it manually from [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki). The wizard warns if it's missing. Auto-install could be added in a future version.

3. **Windows only** — this installer targets Windows 10/11. Linux users should continue using `Linux/install.sh`.

4. **FFmpeg auto-install requires winget** — if `winget` is not available (rare on Windows 10), FFmpeg must be installed manually.

5. **No automatic updates** — the installer downloads the latest `main` branch. If the user re-runs it, it will overwrite source files but preserve `venv/`, `data/`, and `templates/`.

6. **Shortcuts are .bat files** — not `.lnk` shortcuts. They open a console window behind the app. This is intentional for simplicity and debuggability.

---

## Troubleshooting

### "uv download failed"
Check internet connection. The uv binary is downloaded from `github.com/astral-sh/uv/releases`. Corporate firewalls may block this — the user can pre-install uv and add it to PATH.

### "PyTorch installation failed"
Usually a network issue downloading from `download.pytorch.org`. Re-run the installer. If it persists, try a different CUDA version or CPU mode.

### "OmniVoice import failed" (GPU mode)
OmniVoice is installed via `pip install omnivoice`. If the install fails, the user falls back to CPU mode automatically at runtime (handled in `src/tts/__init__.py`).

### "Tesseract not found"
Install Tesseract OCR from https://github.com/UB-Mannheim/tesseract/wiki and ensure it's at `C:\Program Files\Tesseract-OCR\tesseract.exe`.

---

## Future Improvements

- [ ] Auto-download and install Tesseract OCR
- [ ] Create proper `.lnk` shortcuts with icons
- [ ] Add a "Repair" option for re-running the installer over an existing install
- [ ] Add an "Uninstall" option
- [ ] Bundle a portable Tesseract binary (~30 MB) in the installer
- [ ] Support offline mode with pre-cached wheels
- [ ] Add version checking — only download if a new version is available