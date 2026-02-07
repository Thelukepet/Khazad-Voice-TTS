# Imports

# > Standard library
import time
import sys
import threading
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
    if pressed and button == mouse.Button.middle:
        capture_trigger.set()


def main():
    print(r"""
    ========================================
       LOTRO NARRATOR - AI VOICE OVER
    ========================================
    """)

    # 1. Select TTS Backend (CPU vs GPU)
    print("\n[SELECT AUDIO ENGINE]")
    print("1. CPU (Kokoro)")
    print("   -> Fast, Reliable, Standard Quality.")
    print("   -> Works on all computers.")
    print("2. GPU (LuxTTS)")
    print("   -> High Quality Voice Cloning.")
    print("   -> REQUIRES NVIDIA GPU")

    device_input = input("\nEnter choice (1 or 2): ").strip()
    device_choice = "gpu" if device_input == "2" else "cpu"

    # 2. Initialize Heavy Components
    try:
        db = NPCDatabase()
        # Pass the user's choice to the factory
        tts = get_tts_backend(device_choice=device_choice)
    except Exception as e:
        log.error(f"Initialization Failed: {e}")
        input("Press Enter to exit...")
        sys.exit(1)

    # 3. Select Game Mode
    print("\n[SELECT GAME MODE]")
    print("1. Retail / Live (Official)")
    print("   -> Trigger: Automatic (via Log)")
    print("   -> Mechanism: Log Watcher + Template Check")
    print("2. Echoes of Angmar (Classic/Private)")
    print("   -> Trigger: Middle Mouse Click")
    print("   -> Mechanism: OCR Reading")

    choice = input("\nEnter choice (1 or 2): ").strip()
    is_retail = choice == "1"

    # Define mode string and Instantiate Engine
    current_mode = "retail" if is_retail else "echoes"
    engine = NarratorEngine(db, tts, mode=current_mode)

    if is_retail:
        print("\n[RETAIL MODE STARTED]")
        print(f"Watching Log: {SCRIPT_LOG}")
        print("1. Ensure 'Narrator' plugin (or similar) is logging to Script.log.")
        print("2. Ensure 'templates/' folder has Quest Window icons.")

        def npc_found_callback(npc_name):
            # Wait for UI fade-in
            time.sleep(0.3)
            q_img, full_img = capture_screen_areas(mode_prefix="retail")

            if q_img is not None:
                engine.process_retail(q_img, full_img, npc_name)

        # Start Watcher
        watcher_thread = threading.Thread(
            target=watch_npc_file, args=(npc_found_callback, SCRIPT_LOG), daemon=True
        )
        watcher_thread.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Exiting...")

    else:
        # --- ECHOES / CLASSIC MODE ---
        print("\n[ECHOES MODE STARTED]")
        print("1. Open a quest window.")
        print("2. CLICK MIDDLE MOUSE BUTTON to narrate.")

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

                    print("✅ Ready.")
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("Exiting...")
            listener.stop()


if __name__ == "__main__":
    main()
