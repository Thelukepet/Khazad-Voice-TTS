"""
Khazad Voice TTS — Windows Installer (Experimental)

One-click setup wizard using `uv` for ultra-fast Python package management.
Compiles to a standalone .exe via PyInstaller (see build_installer.py).

Usage:
    python setup.py              # Run as script (needs tkinter)
    pyinstaller build_installer.py   # Compile to .exe
"""

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import urllib.request
import zipfile
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Optional

# ─── Constants ────────────────────────────────────────────────────────────────

APP_NAME = "Khazad Voice TTS"
GITHUB_ZIP_URL = "https://github.com/Thelukepet/Khazad-Voice-TTS/archive/refs/heads/experimental-installer.zip"
OMNIVOICE_PIP = "omnivoice"
UV_BINARY_URL = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
DEFAULT_INSTALL_DIR = r"C:\Khazad-Voice-TTS"

TORCH_INDEX_URLS = {
    1: "https://download.pytorch.org/whl/cu121",
    2: "https://download.pytorch.org/whl/nightly/cu128",
    3: "https://download.pytorch.org/whl/cpu",
}

TORCH_LABELS = {
    1: "CUDA 12.1",
    2: "CUDA 12.8 (Nightly)",
    3: "CPU Only",
}

# Colors
BG_DARK = "#1a1a2e"
BG_PANEL = "#16213e"
BG_ENTRY = "#0f0f23"
FG_CYAN = "#00d4ff"
FG_YELLOW = "#e4c518"
FG_GREEN = "#00ff88"
FG_RED = "#ff4444"
FG_WHITE = "#e0e0e0"
FG_DIM = "#888888"
ACCENT = "#0f3460"
BTN_CYAN = "#00b8d4"
BTN_HOVER = "#00e5ff"


class InstallerApp:
    """Multi-step wizard for installing Khazad Voice TTS."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} — Setup")
        self.root.geometry("740x750")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_DARK)

        # Center on screen
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 740) // 2
        y = (self.root.winfo_screenheight() - 750) // 2
        self.root.geometry(f"+{x}+{y}")

        # ── State ──
        self.install_dir = tk.StringVar(value=DEFAULT_INSTALL_DIR)
        self.gpu_choice = tk.IntVar(value=0)
        self.current_step = 0
        self.has_nvidia = False
        self.gpu_name: Optional[str] = None
        self._cancel = False
        self._install_success = False
        self._is_update = False

        # Detect hardware
        self._detect_gpu()

        # Set default choice based on detection
        self.gpu_choice.set(1 if self.has_nvidia else 3)

        # Set window icon (logo.ico is created at build time from logo.jpg)
        if getattr(sys, "frozen", False):
            icon_dir = Path(sys._MEIPASS)
        else:
            icon_dir = Path(__file__).resolve().parent
        icon_path = icon_dir / "logo.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

        # Build UI
        self._build_ui()
        self._show_welcome()

    # ─── Hardware Detection ────────────────────────────────────────────────

    def _detect_gpu(self):
        """Check for an NVIDIA GPU via nvidia-smi, then WMI as fallback."""
        # Method 1: nvidia-smi (fast, but may not be on PATH)
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                self.has_nvidia = True
                self.gpu_name = result.stdout.strip().split("\n")[0]
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Method 2: WMI query (built into Windows, works without nvidia-smi)
        try:
            result = subprocess.run(
                [
                    "wmic",
                    "path",
                    "win32_VideoController",
                    "get",
                    "name",
                    "/format:csv",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Output looks like:
                # Node,Name
                # ,NVIDIA GeForce RTX 4070
                # ,Intel(R) UHD Graphics 630
                for line in result.stdout.strip().splitlines():
                    line = line.strip()
                    if not line or line.startswith("Node"):
                        continue
                    # Strip the leading comma from the CSV format
                    name = line.split(",", 1)[-1].strip()
                    if not name:
                        continue
                    name_lower = name.lower()
                    if (
                        "nvidia" in name_lower
                        or "geforce" in name_lower
                        or "rtx" in name_lower
                        or "gtx" in name_lower
                    ):
                        self.has_nvidia = True
                        self.gpu_name = name
                        return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        self.has_nvidia = False
        self.gpu_name = None

    # ─── UI Construction ───────────────────────────────────────────────────

    def _build_ui(self):
        """Build the static chrome: header, content frame, footer."""
        # Header bar
        header = tk.Frame(self.root, bg=BG_PANEL, height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text=f"{APP_NAME}",
            font=("Segoe UI", 18, "bold"),
            fg=FG_CYAN,
            bg=BG_PANEL,
        ).pack(side=tk.LEFT, padx=20, pady=10)

        tk.Label(
            header,
            text="Setup Wizard",
            font=("Segoe UI", 12),
            fg=FG_DIM,
            bg=BG_PANEL,
        ).pack(side=tk.LEFT, padx=5, pady=14)

        # Content area (steps are drawn here)
        self.content = tk.Frame(self.root, bg=BG_DARK)
        self.content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Footer with nav buttons
        footer = tk.Frame(self.root, bg=BG_PANEL, height=50)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        self.btn_back = tk.Button(
            footer,
            text="Back",
            command=self._on_back,
            bg=ACCENT,
            fg=FG_WHITE,
            activebackground=BG_DARK,
            activeforeground=FG_WHITE,
            font=("Segoe UI", 10),
            width=12,
            cursor="hand2",
            relief=tk.FLAT,
            bd=0,
        )

        self.btn_next = tk.Button(
            footer,
            text="Next",
            command=self._on_next,
            bg=BTN_CYAN,
            fg=BG_DARK,
            activebackground=BTN_HOVER,
            activeforeground=BG_DARK,
            font=("Segoe UI", 10, "bold"),
            width=12,
            cursor="hand2",
            relief=tk.FLAT,
            bd=0,
        )
        self.btn_next.pack(side=tk.RIGHT, padx=10, pady=8)

        self.step_label = tk.Label(
            footer,
            text="Step 1 of 4",
            font=("Segoe UI", 9),
            fg=FG_DIM,
            bg=BG_PANEL,
        )
        self.step_label.pack(side=tk.RIGHT, padx=20)

    def _clear_content(self):
        """Remove all widgets from the content area."""
        for w in self.content.winfo_children():
            w.destroy()

    def _show_back(self, show: bool = True):
        if show:
            self.btn_back.pack(side=tk.LEFT, padx=10, pady=8)
        else:
            self.btn_back.pack_forget()

    # ─── Step 1 — Welcome ─────────────────────────────────────────────────

    def _show_welcome(self):
        self.current_step = 0
        self._clear_content()
        self._show_back(False)

        f = self.content

        # Check for existing installation
        existing_path = Path(self.install_dir.get())
        has_existing = (existing_path / "main.py").exists()

        if has_existing:
            # ── Update screen ──
            self.step_label.config(text="Update")
            self.btn_next.config(state=tk.DISABLED)

            tk.Label(
                f,
                text="Existing Installation Found",
                font=("Segoe UI", 22, "bold"),
                fg=FG_CYAN,
                bg=BG_DARK,
            ).pack(pady=(30, 8))

            tk.Label(
                f,
                text="Khazad Voice TTS is already installed at:",
                font=("Segoe UI", 10),
                fg=FG_WHITE,
                bg=BG_DARK,
            ).pack(pady=(0, 5))

            tk.Label(
                f,
                text=str(existing_path),
                font=("Consolas", 10),
                fg=FG_CYAN,
                bg=BG_DARK,
            ).pack(pady=(0, 20))

            tk.Label(
                f,
                text=(
                    "Would you like to update to the latest version\n"
                    "or perform a full reinstall?"
                ),
                font=("Segoe UI", 10),
                fg=FG_DIM,
                bg=BG_DARK,
                justify=tk.CENTER,
            ).pack(pady=(0, 25))

            btn_frame = tk.Frame(f, bg=BG_DARK)
            btn_frame.pack(pady=5)

            btn_style = dict(
                font=("Segoe UI", 11),
                cursor="hand2",
                relief=tk.FLAT,
                bd=0,
                ipady=6,
                ipadx=12,
            )

            tk.Button(
                btn_frame,
                text="Update",
                bg=FG_GREEN,
                fg=BG_DARK,
                activebackground="#00cc66",
                command=lambda: self._show_progress(update_mode=True),
                **btn_style,
            ).pack(side=tk.LEFT, padx=15)

            tk.Button(
                btn_frame,
                text="Full Reinstall",
                bg=ACCENT,
                fg=FG_WHITE,
                activebackground=BG_DARK,
                command=self._show_location,
                **btn_style,
            ).pack(side=tk.LEFT, padx=15)

            tk.Label(
                f,
                text=(
                    "Update: downloads latest source code only (fast).\n"
                    "Full Reinstall: redo the entire setup from scratch."
                ),
                font=("Segoe UI", 9),
                fg=FG_DIM,
                bg=BG_DARK,
                justify=tk.CENTER,
            ).pack(pady=(15, 0))

        else:
            # ── Fresh install welcome ──
            self.step_label.config(text="Step 1 of 4")
            self.btn_next.config(text="Next", state=tk.NORMAL, bg=BTN_CYAN)

            tk.Label(
                f,
                text="Welcome to Khazad Voice TTS",
                font=("Segoe UI", 22, "bold"),
                fg=FG_CYAN,
                bg=BG_DARK,
            ).pack(pady=(25, 5))

            tk.Label(
                f,
                text="Thank you for downloading the installer!",
                font=("Segoe UI", 11),
                fg=FG_WHITE,
                bg=BG_DARK,
            ).pack(pady=(0, 5))

            desc = (
                "This wizard will set up everything you need — no manual\n"
                "configuration required. Python, dependencies, and models\n"
                "will be installed automatically using uv.\n\n"
                "Developed by Luke (@thelukepet on GitHub)."
            )
            tk.Label(
                f,
                text=desc,
                font=("Segoe UI", 10),
                fg=FG_DIM,
                bg=BG_DARK,
                justify=tk.CENTER,
            ).pack(pady=(5, 15))

            # GPU detection box (only shown when an NVIDIA GPU is found)
            if self.has_nvidia:
                det_frame = tk.Frame(f, bg=BG_PANEL, padx=15, pady=10)
                det_frame.pack(pady=(10, 0), ipadx=10, ipady=5)

                tk.Label(
                    det_frame,
                    text=f"  NVIDIA GPU detected:  {self.gpu_name}",
                    font=("Segoe UI", 10),
                    fg=FG_GREEN,
                    bg=BG_PANEL,
                ).pack(anchor=tk.W)
                tk.Label(
                    det_frame,
                    text="GPU-accelerated TTS (OmniVoice voice cloning) will be available.",
                    font=("Segoe UI", 9),
                    fg=FG_DIM,
                    bg=BG_PANEL,
                ).pack(anchor=tk.W)

    # ─── Step 2 — Install Location ────────────────────────────────────────

    def _show_location(self):
        self.current_step = 1
        self._clear_content()
        self._show_back(True)
        self.step_label.config(text="Step 2 of 4")
        self.btn_next.config(text="Next", state=tk.NORMAL, bg=BTN_CYAN)

        f = self.content

        tk.Label(
            f,
            text="Installation Directory",
            font=("Segoe UI", 16, "bold"),
            fg=FG_CYAN,
            bg=BG_DARK,
        ).pack(pady=(20, 8))

        tk.Label(
            f,
            text="Select a parent folder. A 'Khazad-Voice-TTS' subfolder will be created.",
            font=("Segoe UI", 10),
            fg=FG_WHITE,
            bg=BG_DARK,
        ).pack(pady=(0, 20))

        # Directory entry + browse
        dir_frame = tk.Frame(f, bg=BG_DARK)
        dir_frame.pack(fill=tk.X, padx=50)

        entry = tk.Entry(
            dir_frame,
            textvariable=self.install_dir,
            font=("Consolas", 10),
            bg=BG_ENTRY,
            fg=FG_WHITE,
            insertbackground=FG_WHITE,
            relief=tk.FLAT,
            bd=4,
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)

        tk.Button(
            dir_frame,
            text="Browse...",
            command=self._browse_dir,
            bg=ACCENT,
            fg=FG_WHITE,
            activebackground=BG_DARK,
            font=("Segoe UI", 9),
            cursor="hand2",
            relief=tk.FLAT,
            bd=0,
        ).pack(side=tk.RIGHT, padx=(10, 0), ipady=3, ipadx=8)

        # Disk space estimates
        note = (
            "Estimated disk space required:\n"
            "  CPU (Kokoro)   ~1.5 GB\n"
            "  GPU CUDA 12.1  ~4.5 GB\n"
            "  GPU CUDA 12.8  ~4.5 GB"
        )
        tk.Label(
            f,
            text=note,
            font=("Consolas", 9),
            fg=FG_DIM,
            bg=BG_DARK,
            justify=tk.LEFT,
        ).pack(pady=(25, 0), padx=50, anchor=tk.W)

    def _browse_dir(self):
        path = filedialog.askdirectory(initialdir=self.install_dir.get())
        if path:
            # Always append project folder name so files don't scatter
            install_path = Path(path) / "Khazad-Voice-TTS"
            self.install_dir.set(str(install_path))

    # ─── Step 3 — GPU Selection ───────────────────────────────────────────

    def _show_gpu_select(self):
        self.current_step = 2
        self._clear_content()
        self._show_back(True)
        self.step_label.config(text="Step 3 of 4")
        self.btn_next.config(text="Install", state=tk.NORMAL, bg=FG_GREEN)

        f = self.content

        tk.Label(
            f,
            text="Select GPU Driver Version",
            font=("Segoe UI", 16, "bold"),
            fg=FG_CYAN,
            bg=BG_DARK,
        ).pack(pady=(20, 8))

        tk.Label(
            f,
            text="Choose the PyTorch / CUDA build for your system.",
            font=("Segoe UI", 10),
            fg=FG_WHITE,
            bg=BG_DARK,
        ).pack(pady=(0, 15))

        options_frame = tk.Frame(f, bg=BG_DARK)
        options_frame.pack(padx=50, fill=tk.X)

        options = [
            (
                1,
                "CUDA 12.1  -  Standard",
                "Recommended for most NVIDIA graphics cards.\n"
                "Works with RTX 20/30/40 series and older GTX cards.",
            ),
            (
                2,
                "CUDA 12.8  -  Nightly",
                "For the latest RTX 50-series cards.\n"
                "Uses PyTorch nightly build (required for RTX 50-series).",
            ),
            (
                3,
                "CPU Only  -  Kokoro",
                "No GPU required. Fast and reliable TTS.\n"
                "OmniVoice (voice cloning) will NOT be available.",
            ),
        ]

        for val, title, desc in options:
            row = tk.Frame(options_frame, bg=BG_DARK)
            row.pack(fill=tk.X, pady=6)

            rb = tk.Radiobutton(
                row,
                variable=self.gpu_choice,
                value=val,
                bg=BG_DARK,
                fg=FG_WHITE,
                selectcolor=BG_PANEL,
                activebackground=BG_DARK,
                activeforeground=FG_CYAN,
                font=("Segoe UI", 11, "bold"),
                cursor="hand2",
                highlightthickness=0,
                bd=0,
            )
            rb.pack(side=tk.LEFT)

            text_frame = tk.Frame(row, bg=BG_DARK)
            text_frame.pack(side=tk.LEFT, padx=(8, 0))

            tk.Label(
                text_frame,
                text=title,
                font=("Segoe UI", 10, "bold"),
                fg=FG_WHITE,
                bg=BG_DARK,
            ).pack(anchor=tk.W)
            tk.Label(
                text_frame,
                text=desc,
                font=("Segoe UI", 9),
                fg=FG_DIM,
                bg=BG_DARK,
                justify=tk.LEFT,
            ).pack(anchor=tk.W)

    # ─── Step 4 — Installation Progress ───────────────────────────────────

    def _show_progress(self, update_mode: bool = False):
        self.current_step = 3
        self._clear_content()
        self._show_back(False)
        self.step_label.config(
            text="Updating..." if update_mode else "Step 4 of 4 - Installing..."
        )
        self.btn_next.config(text="Cancel", state=tk.NORMAL, bg=FG_RED)

        f = self.content

        tk.Label(
            f,
            text="Updating..." if update_mode else "Installing...",
            font=("Segoe UI", 16, "bold"),
            fg=FG_CYAN,
            bg=BG_DARK,
        ).pack(pady=(10, 4))

        self.status_label = tk.Label(
            f,
            text="Preparing...",
            font=("Segoe UI", 10),
            fg=FG_YELLOW,
            bg=BG_DARK,
        )
        self.status_label.pack(pady=(0, 8))

        # Progress bar
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Khazad.Horizontal.TProgressbar",
            troughcolor=BG_ENTRY,
            background=FG_CYAN,
            thickness=18,
        )
        self.progress = ttk.Progressbar(
            f,
            style="Khazad.Horizontal.TProgressbar",
            mode="determinate",
            length=640,
        )
        self.progress.pack(padx=40, pady=(0, 8))

        # Log output area
        log_frame = tk.Frame(f, bg="#0a0a14")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=(0, 10))

        self.log_text = tk.Text(
            log_frame,
            font=("Consolas", 8),
            bg="#0a0a14",
            fg="#aaaaaa",
            wrap=tk.WORD,
            height=14,
            state=tk.DISABLED,
            borderwidth=0,
            highlightthickness=0,
            insertbackground=FG_WHITE,
        )
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=(0, 4))

        # Tags for colored text
        self.log_text.tag_configure("ok", foreground=FG_GREEN)
        self.log_text.tag_configure("warn", foreground=FG_YELLOW)
        self.log_text.tag_configure("err", foreground=FG_RED)
        self.log_text.tag_configure("step", foreground=FG_CYAN)
        self.log_text.tag_configure("dim", foreground="#666666")

        # Start the background installer
        self._cancel = False
        target = self._run_update if update_mode else self._run_install
        threading.Thread(target=target, daemon=True).start()

    # ─── Step 5 — Complete ────────────────────────────────────────────────

    def _show_complete(self, success: bool, message: str = ""):
        self._install_success = success
        self.current_step = 4
        self._clear_content()
        self._show_back(False)

        f = self.content

        if success:
            self.step_label.config(text="Complete!")
            self.btn_next.config(text="Finish", state=tk.NORMAL, bg=BTN_CYAN)

            tk.Label(
                f,
                text="Update Complete!"
                if self._is_update
                else "Installation Complete!",
                font=("Segoe UI", 22, "bold"),
                fg=FG_GREEN,
                bg=BG_DARK,
            ).pack(pady=(18, 6))

            tk.Label(
                f,
                text="Khazad Voice TTS is ready to use.",
                font=("Segoe UI", 11),
                fg=FG_WHITE,
                bg=BG_DARK,
            ).pack(pady=(0, 3))

            # Calibration section (fresh installs only)
            if not self._is_update:
                cal_frame = tk.Frame(f, bg=BG_PANEL, padx=15, pady=10)
                cal_frame.pack(fill=tk.X, padx=30, pady=(3, 6), ipadx=5, ipady=3)

                tk.Label(
                    cal_frame,
                    text="⚡ REQUIRED: Calibrate before your first use",
                    font=("Segoe UI", 10, "bold"),
                    fg=FG_YELLOW,
                    bg=BG_PANEL,
                ).pack(anchor=tk.W)
                tk.Label(
                    cal_frame,
                    text=(
                        "Calibration teaches the app where the quest window is on your screen.\n"
                        "Without it, the app cannot read any quest text."
                    ),
                    font=("Segoe UI", 9),
                    fg=FG_DIM,
                    bg=BG_PANEL,
                    justify=tk.LEFT,
                ).pack(anchor=tk.W, pady=(2, 6))

                # Step-by-step instruction box
                instr_frame = tk.Frame(cal_frame, bg=BG_ENTRY, padx=10, pady=8)
                instr_frame.pack(fill=tk.X, pady=(0, 6))

                tk.Label(
                    instr_frame,
                    text=(
                        "①  Launch LOTRO (or Echoes of Angmar) and log in to the game.\n"
                        "②  Walk up to any NPC and talk to them so a quest window appears.\n"
                        "     Make sure the quest window is fully visible on your primary monitor.\n"
                        "③  Come back here and press the matching button below.\n"
                        "④  Follow the instructions on the new window that opens."
                    ),
                    font=("Segoe UI", 9),
                    fg=FG_CYAN,
                    bg=BG_ENTRY,
                    justify=tk.LEFT,
                ).pack(anchor=tk.W)

                cal_btn_frame = tk.Frame(cal_frame, bg=BG_PANEL)
                cal_btn_frame.pack(anchor=tk.W, pady=(2, 4))

                cal_btn_style = dict(
                    font=("Segoe UI", 9),
                    bg=ACCENT,
                    fg=FG_WHITE,
                    activebackground=BG_DARK,
                    activeforeground=FG_WHITE,
                    cursor="hand2",
                    relief=tk.FLAT,
                    bd=0,
                    ipady=3,
                    ipadx=8,
                )

                tk.Button(
                    cal_btn_frame,
                    text="Calibrate Retail LOTRO",
                    command=lambda: self._launch_app("calibrate_retail"),
                    **cal_btn_style,
                ).pack(side=tk.LEFT, padx=(0, 8))

                tk.Button(
                    cal_btn_frame,
                    text="Calibrate Echoes of Angmar",
                    command=lambda: self._launch_app("calibrate_echoes"),
                    **cal_btn_style,
                ).pack(side=tk.LEFT, padx=(0, 8))

                tk.Button(
                    cal_btn_frame,
                    text="Calibrate Static (Fallback)",
                    command=lambda: self._launch_app("calibrate_static"),
                    **cal_btn_style,
                ).pack(side=tk.LEFT, padx=(0, 8))

                # Show install path for future re-calibration
                install_path = Path(self.install_dir.get())
                tk.Label(
                    cal_frame,
                    text=(
                        f"Need to re-calibrate later? Open the .bat files inside:\n"
                        f"{install_path}\\Windows\\"
                    ),
                    font=("Segoe UI", 8),
                    fg=FG_DIM,
                    bg=BG_PANEL,
                    justify=tk.LEFT,
                ).pack(anchor=tk.W, pady=(2, 0))

            # Launch buttons
            btn_frame = tk.Frame(f, bg=BG_DARK)
            btn_frame.pack(pady=3)

            launch_btn_style = dict(
                font=("Segoe UI", 10),
                bg=ACCENT,
                fg=FG_WHITE,
                activebackground=BG_DARK,
                activeforeground=FG_WHITE,
                cursor="hand2",
                relief=tk.FLAT,
                bd=0,
                ipady=4,
                ipadx=6,
            )

            tk.Button(
                btn_frame,
                text="Launch Retail Mode",
                command=lambda: self._launch_app("retail"),
                **launch_btn_style,
            ).pack(side=tk.LEFT, padx=8)

            tk.Button(
                btn_frame,
                text="Launch Echoes of Angmar",
                command=lambda: self._launch_app("echoes"),
                **launch_btn_style,
            ).pack(side=tk.LEFT, padx=8)

            tk.Button(
                btn_frame,
                text="Voice Lab",
                command=lambda: self._launch_app("lab"),
                **launch_btn_style,
            ).pack(side=tk.LEFT, padx=8)

            # Footer note
            install_path = Path(self.install_dir.get())
            tk.Label(
                f,
                text=(
                    f"Installed to: {install_path}\n"
                    "Desktop shortcuts created.\n"
                    "Visit github.com/thelukepet/Khazad-Voice-TTS for help."
                ),
                font=("Consolas", 8),
                fg=FG_DIM,
                bg=BG_DARK,
                justify=tk.CENTER,
            ).pack(pady=(6, 0))
        else:
            self.step_label.config(text="Installation Failed")
            self.btn_next.config(text="Close", state=tk.NORMAL, bg=FG_RED)

            tk.Label(
                f,
                text="Installation Failed",
                font=("Segoe UI", 22, "bold"),
                fg=FG_RED,
                bg=BG_DARK,
            ).pack(pady=(30, 10))

            tk.Label(
                f,
                text=message or "Check the log above for details.",
                font=("Segoe UI", 10),
                fg=FG_WHITE,
                bg=BG_DARK,
                justify=tk.CENTER,
                wraplength=550,
            ).pack(pady=10)

    # ─── Navigation ───────────────────────────────────────────────────────

    def _on_next(self):
        if self.current_step == 0:
            self._show_location()
        elif self.current_step == 1:
            path = self.install_dir.get().strip()
            if not path:
                return
            self._show_gpu_select()
        elif self.current_step == 2:
            self._show_progress()
        elif self.current_step == 3:
            # Cancel button during installation
            self._cancel = True
            self.btn_next.config(text="Cancelling...", state=tk.DISABLED)
        elif self.current_step == 4:
            self.root.destroy()

    def _on_back(self):
        if self.current_step == 1:
            self._show_welcome()
        elif self.current_step == 2:
            self._show_location()

    # ─── Thread-Safe UI Helpers ───────────────────────────────────────────

    def _log(self, msg: str, tag: str = ""):
        """Append a line to the log widget (thread-safe)."""

        def _append():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, msg + "\n", tag if tag else ())
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)

        if hasattr(self, "log_text"):
            self.root.after(0, _append)

    def _set_status(self, msg: str):
        def _update():
            if hasattr(self, "status_label"):
                self.status_label.config(text=msg)

        self.root.after(0, _update)

    def _set_progress(self, value: float):
        def _update():
            if hasattr(self, "progress"):
                self.progress["value"] = value

        self.root.after(0, _update)

    def _install_finished(self, success: bool, message: str = ""):
        def _update():
            self._show_complete(success, message)

        self.root.after(0, _update)

    # ─── Command Runner ───────────────────────────────────────────────────

    def _run_cmd(
        self,
        cmd: list,
        cwd: Optional[str] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run a subprocess, streaming output to the log in real time."""
        self._log(f"$ {' '.join(str(c) for c in cmd)}", "dim")

        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in proc.stdout:
            stripped = line.rstrip()
            if stripped:
                self._log(f"  {stripped}", "dim")

        proc.wait()

        if check and proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)

        return subprocess.CompletedProcess(cmd, proc.returncode)

    # ─── Download Helper ──────────────────────────────────────────────────

    def _download(self, url: str, dest: Path, label: str = ""):
        """Download a file with logging."""
        self._log(f"Downloading {label or url}...")
        try:
            urllib.request.urlretrieve(url, dest)
        except Exception as e:
            raise RuntimeError(f"Download failed ({url}): {e}")

    # ─── Main Installation Logic ──────────────────────────────────────────

    def _run_install(self):
        """Background thread - the entire installation sequence."""
        try:
            install_path = Path(self.install_dir.get())
            choice = self.gpu_choice.get()
            use_gpu = choice in (1, 2)

            # ── Step 1: Acquire uv ──
            self._set_status("Setting up uv package manager...")
            self._set_progress(2)
            self._log("=" * 50, "step")
            self._log("  STEP 1/9  Acquiring uv", "step")
            self._log("=" * 50, "step")

            uv_exe = self._acquire_uv(install_path)
            self._log(f"uv ready: {uv_exe}", "ok")
            if self._cancel:
                return self._cancelled()

            # ── Step 2: Install Python 3.12 via uv ──
            self._set_status("Installing Python 3.12...")
            self._set_progress(5)
            self._log("", "dim")
            self._log("=" * 50, "step")
            self._log("  STEP 2/9  Installing Python 3.12", "step")
            self._log("=" * 50, "step")

            self._run_cmd([str(uv_exe), "python", "install", "3.12"])
            self._log("Python 3.12 installed.", "ok")
            if self._cancel:
                return self._cancelled()

            # ── Step 3: Download project source ──
            self._set_status("Downloading Khazad Voice TTS...")
            self._set_progress(8)
            self._log("", "dim")
            self._log("=" * 50, "step")
            self._log("  STEP 3/9  Downloading project source", "step")
            self._log("=" * 50, "step")

            self._download_project(install_path)
            if self._cancel:
                return self._cancelled()

            # ── Step 4: Create virtual environment ──
            self._set_status("Creating virtual environment...")
            self._set_progress(14)
            self._log("", "dim")
            self._log("=" * 50, "step")
            self._log("  STEP 4/9  Creating virtual environment", "step")
            self._log("=" * 50, "step")

            venv_path = install_path / "venv"
            if venv_path.exists():
                self._log("Removing existing venv...")
                shutil.rmtree(venv_path)

            self._run_cmd([str(uv_exe), "venv", str(venv_path), "--python", "3.12"])

            python_exe = venv_path / "Scripts" / "python.exe"
            if not python_exe.exists():
                raise FileNotFoundError(f"Python executable not found at {python_exe}")
            self._log(f"venv created: {python_exe}", "ok")
            if self._cancel:
                return self._cancelled()

            # ── Step 5: Install OmniVoice (BEFORE PyTorch) ──
            # OmniVoice may pull in a CPU-only torch as a dependency.
            # We install PyTorch AFTER OmniVoice so the CUDA version wins.
            self._set_status("Installing OmniVoice TTS...")
            self._set_progress(18)
            self._log("", "dim")
            self._log("=" * 50, "step")
            self._log("  STEP 5/9  OmniVoice TTS", "step")
            self._log("=" * 50, "step")

            self._install_omnivoice(install_path, python_exe, uv_exe)

            if self._cancel:
                return self._cancelled()

            self._set_progress(48)

            # ── Step 6: Install PyTorch (AFTER OmniVoice so CUDA wins) ──
            self._set_status(
                f"Installing PyTorch ({TORCH_LABELS.get(choice, 'CPU')})..."
            )
            self._set_progress(52)
            self._log("", "dim")
            self._log("=" * 50, "step")
            self._log(
                f"  STEP 6/9  PyTorch - {TORCH_LABELS.get(choice, 'CPU')}",
                "step",
            )
            self._log("=" * 50, "step")

            torch_cmd = [
                str(uv_exe),
                "pip",
                "install",
                "--python",
                str(python_exe),
            ]
            if choice == 2:
                torch_cmd.append("--pre")
            torch_cmd += ["torch", "torchaudio"]
            torch_cmd += ["--index-url", TORCH_INDEX_URLS[choice]]

            self._run_cmd(torch_cmd)
            self._log("PyTorch installed.", "ok")

            if self._cancel:
                return self._cancelled()

            self._set_progress(68)

            # ── Step 7: Install main requirements ──
            self._set_status("Installing application dependencies...")
            self._set_progress(70)
            self._log("", "dim")
            self._log("=" * 50, "step")
            self._log("  STEP 7/9  Application requirements", "step")
            self._log("=" * 50, "step")

            req_file = install_path / "requirements.txt"
            if req_file.exists():
                self._run_cmd(
                    [
                        str(uv_exe),
                        "pip",
                        "install",
                        "--python",
                        str(python_exe),
                        "-r",
                        str(req_file),
                        "--extra-index-url",
                        TORCH_INDEX_URLS[choice],
                    ],
                    check=False,  # Don't abort on version conflicts
                )
            else:
                self._log("requirements.txt not found - skipping.", "warn")

            # Ensure NLTK is present
            self._run_cmd(
                [
                    str(uv_exe),
                    "pip",
                    "install",
                    "--python",
                    str(python_exe),
                    "nltk",
                ],
                check=False,
            )

            # Voice Lab dependencies (not in requirements.txt)
            self._run_cmd(
                [
                    str(uv_exe),
                    "pip",
                    "install",
                    "--python",
                    str(python_exe),
                    "gradio",
                    "openai-whisper",
                    "soundfile",
                    "--extra-index-url",
                    TORCH_INDEX_URLS[choice],
                ],
                check=False,
            )

            self._log("Dependencies installed.", "ok")
            if self._cancel:
                return self._cancelled()

            self._set_progress(84)

            # ── Step 8: NLTK data + external tools ──
            self._set_status("Downloading NLTK data & checking tools...")
            self._set_progress(86)
            self._log("", "dim")
            self._log("=" * 50, "step")
            self._log("  STEP 8/9  NLTK data & external tools", "step")
            self._log("=" * 50, "step")

            # NLTK data
            self._run_cmd(
                [
                    str(python_exe),
                    "-c",
                    "import nltk; "
                    "nltk.download('punkt'); "
                    "nltk.download('punkt_tab'); "
                    "nltk.download('averaged_perceptron_tagger')",
                ],
                check=False,
            )

            # FFmpeg check
            ffmpeg_found = shutil.which("ffmpeg") is not None
            if ffmpeg_found:
                self._log("FFmpeg found.", "ok")
            else:
                self._log("FFmpeg not found - attempting winget install...", "warn")
                result = self._run_cmd(
                    [
                        "winget",
                        "install",
                        "-e",
                        "--id",
                        "Gyan.FFmpeg",
                        "--accept-source-agreements",
                        "--accept-package-agreements",
                    ],
                    check=False,
                )
                if result.returncode == 0:
                    self._log("FFmpeg installed via winget.", "ok")
                else:
                    self._log(
                        "Could not auto-install FFmpeg. "
                        "Please install manually: https://ffmpeg.org/download.html",
                        "warn",
                    )

            # Tesseract check
            tesseract_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
            tess_found = any(os.path.exists(p) for p in tesseract_paths)
            if tess_found:
                self._log("Tesseract OCR found.", "ok")
            else:
                self._log("Tesseract OCR not found.", "warn")
                self._log(
                    "  Required for quest text recognition. "
                    "Install from: https://github.com/UB-Mannheim/tesseract/wiki",
                    "warn",
                )

            if self._cancel:
                return self._cancelled()

            self._set_progress(94)

            # ── Step 9: Create shortcuts ──
            self._set_status("Creating shortcuts...")
            self._set_progress(96)
            self._log("", "dim")
            self._log("=" * 50, "step")
            self._log("  STEP 9/9  Shortcuts", "step")
            self._log("=" * 50, "step")

            self._create_shortcuts(install_path)

            # ── Done ──
            self._set_progress(100)
            self._log("", "dim")
            self._log("=" * 50, "ok")
            self._log("  INSTALLATION COMPLETE!", "ok")
            self._log("=" * 50, "ok")

            self._install_finished(True)

        except subprocess.CalledProcessError as e:
            cmd_str = " ".join(str(c) for c in e.cmd) if e.cmd else "unknown"
            self._log(f"\nCommand failed (exit {e.returncode}): {cmd_str}", "err")
            self._install_finished(False, f"Command failed:\n{cmd_str}")
        except Exception as e:
            self._log(f"\nError: {e}", "err")
            self._install_finished(False, str(e))

    def _cancelled(self):
        self._log("\nInstallation cancelled by user.", "warn")
        self._install_finished(False, "Installation was cancelled.")

    # ─── Update Logic ────────────────────────────────────────────────────

    def _run_update(self):
        """Background thread — update source code and dependencies only."""
        try:
            install_path = Path(self.install_dir.get())
            choice = self.gpu_choice.get()

            # Find uv and python from existing installation
            uv_exe = self._acquire_uv(install_path)
            python_exe = install_path / "venv" / "Scripts" / "python.exe"

            if not python_exe.exists():
                raise FileNotFoundError(
                    f"Python not found at {python_exe}.\n"
                    "The existing installation may be damaged. Try a Full Reinstall."
                )

            # ── Step 1: Download latest source ──
            self._set_status("Downloading latest source code...")
            self._set_progress(15)
            self._log("=" * 50, "step")
            self._log("  STEP 1/3  Downloading latest source", "step")
            self._log("=" * 50, "step")

            self._update_project(install_path)
            if self._cancel:
                return self._cancelled()

            # ── Step 2: Reinstall requirements ──
            self._set_status("Checking for new dependencies...")
            self._set_progress(55)
            self._log("", "dim")
            self._log("=" * 50, "step")
            self._log("  STEP 2/3  Updating dependencies", "step")
            self._log("=" * 50, "step")

            req_file = install_path / "requirements.txt"
            if req_file.exists():
                self._run_cmd(
                    [
                        str(uv_exe),
                        "pip",
                        "install",
                        "--python",
                        str(python_exe),
                        "-r",
                        str(req_file),
                        "--extra-index-url",
                        TORCH_INDEX_URLS[choice],
                    ],
                    check=False,
                )

            # Also update Voice Lab dependencies
            self._run_cmd(
                [
                    str(uv_exe),
                    "pip",
                    "install",
                    "--python",
                    str(python_exe),
                    "gradio",
                    "openai-whisper",
                    "soundfile",
                    "--extra-index-url",
                    TORCH_INDEX_URLS[choice],
                ],
                check=False,
            )

            self._log("Dependencies updated.", "ok")
            if self._cancel:
                return self._cancelled()

            # ── Step 3: Update shortcuts ──
            self._set_status("Updating shortcuts...")
            self._set_progress(85)
            self._log("", "dim")
            self._log("=" * 50, "step")
            self._log("  STEP 3/3  Shortcuts", "step")
            self._log("=" * 50, "step")

            self._create_shortcuts(install_path)

            # ── Done ──
            self._set_progress(100)
            self._is_update = True
            self._log("", "dim")
            self._log("=" * 50, "ok")
            self._log("  UPDATE COMPLETE!", "ok")
            self._log("=" * 50, "ok")

            self._install_finished(True)

        except subprocess.CalledProcessError as e:
            cmd_str = " ".join(str(c) for c in e.cmd) if e.cmd else "unknown"
            self._log(f"\nCommand failed (exit {e.returncode}): {cmd_str}", "err")
            self._install_finished(False, f"Command failed:\n{cmd_str}")
        except Exception as e:
            self._log(f"\nError: {e}", "err")
            self._install_finished(False, str(e))

    # ─── uv Acquisition ───────────────────────────────────────────────────

    def _acquire_uv(self, install_path: Path) -> Path:
        """Return path to uv.exe - use system install or download it."""
        # 1. Check if uv is already on PATH
        uv_on_path = shutil.which("uv")
        if uv_on_path:
            self._log("Found uv on system PATH.", "ok")
            return Path(uv_on_path)

        # 2. Check if previously downloaded
        uv_dir = install_path / "_uv"
        uv_exe = uv_dir / "uv.exe"
        if uv_exe.exists():
            self._log("Found previously downloaded uv.", "ok")
            return uv_exe

        # 3. Download uv binary
        uv_dir.mkdir(parents=True, exist_ok=True)
        zip_path = uv_dir / "uv.zip"

        self._download(UV_BINARY_URL, zip_path, "uv")

        self._log("Extracting uv...")
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(uv_dir)
        zip_path.unlink()

        if not uv_exe.exists():
            raise FileNotFoundError(f"uv.exe not found after extraction at {uv_exe}")

        self._log("uv downloaded successfully.", "ok")
        return uv_exe

    # ─── Project Download ─────────────────────────────────────────────────

    def _download_project(self, install_path: Path):
        """Download and extract the project source from GitHub."""
        # If the directory exists with a main.py, assume source is present
        if (install_path / "main.py").exists():
            self._log(f"Source already exists at {install_path} - updating files...")
            self._update_project(install_path)
            return

        install_path.mkdir(parents=True, exist_ok=True)
        zip_path = install_path / "source.zip"

        self._download(GITHUB_ZIP_URL, zip_path, "Khazad Voice TTS source")

        self._log("Extracting...")
        self._extract_github_zip(zip_path, install_path)
        zip_path.unlink(missing_ok=True)

        self._log("Source code ready.", "ok")

    def _update_project(self, install_path: Path):
        """Re-download source over an existing installation, preserving user data."""
        zip_path = install_path / "_update_source.zip"

        self._download(GITHUB_ZIP_URL, zip_path, "Khazad Voice TTS update")

        temp_dir = install_path / "_temp_update"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()

        self._log("Extracting update...")
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(temp_dir)

        # Find the root folder inside the zip
        extracted_folders = list(temp_dir.iterdir())
        if len(extracted_folders) == 1 and extracted_folders[0].is_dir():
            source = extracted_folders[0]
        else:
            source = temp_dir

        # Overwrite project files (preserving venv, data, _uv)
        preserved = {"venv", "_uv", "data", "__pycache__", ".pytest_cache"}
        for item in source.iterdir():
            if item.name in preserved:
                continue
            dest = install_path / item.name
            if dest.is_dir():
                shutil.rmtree(dest, ignore_errors=True)
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        shutil.rmtree(temp_dir, ignore_errors=True)
        zip_path.unlink(missing_ok=True)

        self._log("Source files updated.", "ok")

    # ─── OmniVoice Setup ─────────────────────────────────────────────────

    def _install_omnivoice(self, install_path: Path, python_exe: Path, uv_exe: Path):
        """Install OmniVoice TTS for GPU mode."""
        self._log("Installing OmniVoice TTS package...")
        self._run_cmd(
            [
                str(uv_exe),
                "pip",
                "install",
                "--python",
                str(python_exe),
                OMNIVOICE_PIP,
            ],
            check=False,
        )
        self._log("OmniVoice installed.", "ok")

    # ─── Zip Extraction Helper ────────────────────────────────────────────

    def _extract_github_zip(self, zip_path: Path, target_dir: Path):
        """Extract a GitHub zip, stripping the top-level folder."""
        with zipfile.ZipFile(zip_path, "r") as z:
            members = z.namelist()
            if not members:
                raise RuntimeError("Zip archive is empty.")

            # Detect the root folder (e.g. "Khazad-Voice-TTS-main/")
            root_folder = members[0].split("/")[0]

            temp_dir = target_dir.parent / f"_temp_{target_dir.name}"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

            z.extractall(temp_dir)

            extracted = temp_dir / root_folder
            if not extracted.is_dir():
                extracted = temp_dir

            # If target doesn't exist yet, just rename
            if not target_dir.exists():
                shutil.move(str(extracted), str(target_dir))
            else:
                # Merge into existing directory
                for item in extracted.iterdir():
                    dest = target_dir / item.name
                    if dest.is_dir():
                        shutil.rmtree(dest, ignore_errors=True)
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

            shutil.rmtree(temp_dir, ignore_errors=True)

    # ─── Shortcuts ────────────────────────────────────────────────────────

    def _create_shortcuts(self, install_path: Path):
        """Create desktop shortcuts (.lnk) with icons."""
        desktop = Path(os.path.expanduser("~/Desktop"))
        python_exe = install_path / "venv" / "Scripts" / "python.exe"

        # Copy icon to install directory for shortcut use
        icon_dest = install_path / "logo.ico"
        icon_src = self._find_icon()
        if icon_src and not icon_dest.exists():
            try:
                shutil.copy2(str(icon_src), str(icon_dest))
            except Exception:
                pass
        icon_path = str(icon_dest) if icon_dest.exists() else ""

        shortcuts = [
            {
                "name": "Khazad Voice (Retail)",
                "args": "main.py --mode retail",
                "desc": "Khazad Voice - Retail Mode",
            },
            {
                "name": "Khazad Voice (Echoes)",
                "args": "main.py --mode echoes",
                "desc": "Khazad Voice - Echoes of Angmar",
            },
            {
                "name": "Khazad Voice Lab",
                "args": "voice_lab.py",
                "desc": "Khazad Voice Lab",
            },
        ]

        count = 0
        for sc in shortcuts:
            lnk_path = desktop / f"{sc['name']}.lnk"
            try:
                self._create_lnk(
                    shortcut_path=str(lnk_path),
                    target=str(python_exe),
                    args=sc["args"],
                    working_dir=str(install_path),
                    icon_path=icon_path,
                    description=sc["desc"],
                )
                count += 1
            except Exception:
                # Fallback to .bat if .lnk creation fails
                bat_path = desktop / f"{sc['name']}.bat"
                try:
                    bat_path.write_text(
                        f"@echo off\n"
                        f"title {sc['desc']}\n"
                        f'cd /d "{install_path}"\n'
                        f"call venv\\Scripts\\activate.bat\n"
                        f"python {sc['args']}\n"
                        f"pause\n",
                        encoding="utf-8",
                    )
                    count += 1
                except Exception as e2:
                    self._log(f"  Could not create {sc['name']}: {e2}", "warn")

        self._log(f"  Created {count} desktop shortcut(s).", "ok")

    def _find_icon(self) -> Optional[Path]:
        """Find logo.ico from bundled resources or local directory."""
        # PyInstaller bundle
        if getattr(sys, "frozen", False):
            bundled = Path(sys._MEIPASS) / "logo.ico"
            if bundled.exists():
                return bundled
        # Dev / script directory
        local = Path(__file__).resolve().parent / "logo.ico"
        if local.exists():
            return local
        return None

    @staticmethod
    def _create_lnk(shortcut_path, target, args, working_dir, icon_path, description):
        """Create a Windows .lnk shortcut with icon via PowerShell."""

        def esc(s):
            return s.replace("'", "''")

        icon_line = f"$sc.IconLocation = '{esc(icon_path)}'" if icon_path else ""
        ps = f"""
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut('{esc(shortcut_path)}')
$sc.TargetPath = '{esc(target)}'
$sc.Arguments = '{esc(args)}'
$sc.WorkingDirectory = '{esc(working_dir)}'
$sc.Description = '{esc(description)}'
{icon_line}
$sc.Save()
"""
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"PowerShell failed: {result.stderr}")

    # ─── App Launcher ─────────────────────────────────────────────────────

    def _launch_app(self, mode: str):
        """Launch the installed application in a new process."""
        install_path = Path(self.install_dir.get())
        python_exe = str(install_path / "venv" / "Scripts" / "python.exe")

        if mode == "lab":
            script = str(install_path / "voice_lab.py")
            subprocess.Popen(
                [python_exe, script],
                cwd=str(install_path),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        elif mode == "calibrate_retail":
            script = str(install_path / "src" / "calibrate_retail.py")
            subprocess.Popen(
                [python_exe, script],
                cwd=str(install_path),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        elif mode == "calibrate_echoes":
            script = str(install_path / "src" / "calibrate_echoes.py")
            subprocess.Popen(
                [python_exe, script],
                cwd=str(install_path),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        elif mode == "calibrate_static":
            script = str(install_path / "src" / "calibrate_static.py")
            subprocess.Popen(
                [python_exe, script],
                cwd=str(install_path),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            script = str(install_path / "main.py")
            subprocess.Popen(
                [python_exe, script, "--mode", mode],
                cwd=str(install_path),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )


# ─── Entry Point ──────────────────────────────────────────────────────────────


def main():
    root = tk.Tk()
    app = InstallerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
