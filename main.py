# Imports

# > Standard library
import time
import sys
import threading
import argparse
from threading import Event

# > Third party imports
from pynput import mouse

# > Local dependencies
from src.utils import setup_logger, capture_screen_areas, watch_npc_file
from src.db import NPCDatabase
from src.tts import get_tts_backend
from src.engine import NarratorEngine
from src.config import SCRIPT_LOG

log = setup_logger("MAIN")
capture_trigger = Event()


def on_click(x, y, button, pressed):
    """Callback for pynput mouse listener."""
    if pressed and button == mouse.Button.middle:
        capture_trigger.set()


def main():
    """
    Main entry point for Khazad-Voice TTS.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["retail", "echoes"], help="Game mode to start in")
    args = parser.parse_args()

    print(r"""
    ========================================
       LOTRO NARRATOR - AI VOICE OVER
    ========================================
    """)

    # 1. Select TTS Backend
    print("\n[SELECT AUDIO ENGINE]")
    print("1. CPU (Kokoro) [Default]")
    print("   -> Fast, Reliable. Works on all PCs.")
    print("2. GPU (LuxTTS)")
    print("   -> Higher Quality. REQUIRES NVIDIA GPU.")

    device_input = input("\nEnter choice (1 or 2): ").strip()
    device_choice = "gpu" if device_input == "2" else "cpu"

    # 2. Initialize Heavy Components
    try:
        db = NPCDatabase()
        tts = get_tts_backend(device_choice=device_choice)
    except Exception as e:
        log.error(f"Initialization Failed: {e}")
        input("Press Enter to exit...")
        sys.exit(1)

    # 3. Determine Mode
    # If passed via CLI (bat file), use it. Otherwise prompt (fallback).
    if args.mode:
        current_mode = args.mode
    else:
        print("\n[SELECT GAME MODE]")
        print("1. Retail / Live")
        print("2. Echoes of Angmar")
        choice = input("\nEnter choice (1 or 2): ").strip()
        current_mode = "retail" if choice == "1" else "echoes"

    engine = NarratorEngine(db, tts, mode=current_mode)

    # 4. Start Logic
    if current_mode == "retail":
        print("\n[RETAIL MODE STARTED]")
        print(f"Watching Log: {SCRIPT_LOG}")
        print("1. Ensure 'getNPCNames' LOTRO plugin is installed and loaded for your character.")

        def npc_found_callback(npc_name):
            time.sleep(0.3)
            q_img, full_img = capture_screen_areas(mode_prefix="retail")
            if q_img is not None:
                engine.process_retail(q_img, full_img, npc_name)

        watcher_thread = threading.Thread(
            target=watch_npc_file, args=(npc_found_callback, SCRIPT_LOG), daemon=True
        )
        watcher_thread.start()

        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            print("Exiting...")

    else:
        # ECHOES MODE
        print("\n[ECHOES MODE STARTED]")
        print("1. Open Quest Window.")
        print("2. MIDDLE CLICK to narrate.")

        listener = mouse.Listener(on_click=on_click)
        listener.start()

        try:
            while True:
                if capture_trigger.is_set():
                    capture_trigger.clear()
                    print("⏳ Capturing...")
                    time.sleep(0.5)

                    q_img, n_img = capture_screen_areas(mode_prefix="echoes")

                    if q_img and n_img:
                        engine.process_capture(q_img, n_img)
                    else:
                        print("❌ Capture failed. Check calibration.")

                    print("✅ Ready.")
                time.sleep(0.1)
        except KeyboardInterrupt:
            listener.stop()


if __name__ == "__main__":
    main()