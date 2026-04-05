# Imports

# > Standard Library
import argparse
import sys
import threading
import time
from threading import Event

# > Third Party Imports
from pynput import keyboard, mouse

# > Local Dependencies
from src.config import (
    NPC_NAME_MAX_AGE,
    QUEST_WINDOW_MODE,
    SCRIPT_LOG,
)
from src.db import NPCDatabase
from src.engine import NarratorEngine
from src.tts import get_tts_backend
from src.utils import capture_screen_areas, setup_logger, watch_npc_file

log = setup_logger("MAIN")

# Shared events for cross-thread signalling
capture_trigger = Event()  # Echoes mode: middle-click
retail_capture_trigger = Event()  # Retail static mode: middle-click


def on_click(x, y, button, pressed):
    """Callback for pynput mouse listener.

    Fires both events so whichever mode is active can respond.
    """
    if pressed and button == mouse.Button.middle:
        capture_trigger.set()
        retail_capture_trigger.set()


def main():
    """
    Main entry point for Khazad-Voice TTS.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=["retail", "echoes"], help="Game mode to start in"
    )
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
    print("2. GPU (OmniVoice)")
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
    if args.mode:
        current_mode = args.mode
    else:
        print("\n[SELECT GAME MODE]")
        print("1. Retail / Live")
        print("2. Echoes of Angmar")
        choice = input("\nEnter choice (1 or 2): ").strip()
        current_mode = "retail" if choice == "1" else "echoes"

    engine = NarratorEngine(db, tts, mode=current_mode)

    # --- KEYBOARD LISTENER (F12 STOP) ---
    def on_key_release(key):
        if key == keyboard.Key.f12:
            engine.stop()

    kb_listener = keyboard.Listener(on_release=on_key_release)
    kb_listener.start()
    # -----------------------------------

    # 4. Start Logic
    if current_mode == "retail":
        print("\n[RETAIL MODE STARTED]")
        print(f"Window Mode: {QUEST_WINDOW_MODE.upper()}")

        if QUEST_WINDOW_MODE == "auto":
            # ----- AUTO MODE: Template matching + Log watcher trigger -----
            # Quest window is found via template matching at any screen position.
            # TTS triggers automatically when the log watcher detects a new NPC
            # in Script.log (requires getNPCNames plugin installed in LOTRO).
            print("Detection : Template matching (finds window anywhere)")
            print("Trigger   : Automatic (NPC appears in Script.log)")
            print(f"Watching  : {SCRIPT_LOG}")
            print()
            print("1. Ensure 'getNPCNames' plugin is installed.")
            print("2. Open a quest dialog with any NPC.")
            print("3. Press F12 to STOP current playback.")

            # Track last played NPC to skip stale log entries that
            # accumulated in Script.log during a previous playback.
            _last_played = {"name": "", "time": 0.0}

            def npc_found_callback(npc_name):
                # Skip stale duplicate: same NPC played within the last 5 seconds.
                # The LOTRO plugin can write the same name multiple times per
                # interaction; these pile up while we're blocked in playback.
                now = time.time()
                if (
                    npc_name == _last_played["name"]
                    and _last_played["time"] > 0
                    and now - _last_played["time"] < 5.0
                ):
                    log.info(
                        f"Skipping stale trigger for '{npc_name}' "
                        f"(same NPC played {now - _last_played['time']:.1f}s ago)"
                    )
                    return

                log.info(f"Auto-trigger: NPC '{npc_name}' detected")

                # Retry screen capture up to 3 times to give the game
                # time to render the quest window after the NPC click.
                q_img = None
                full_img = None
                for attempt in range(3):
                    time.sleep(0.5 + attempt * 0.5)
                    q_img, full_img = capture_screen_areas(mode_prefix="retail")
                    if q_img is not None:
                        break
                    if attempt < 2:
                        log.info(
                            f"Quest window not found, retrying ({attempt + 2}/3)..."
                        )

                if q_img is not None:
                    engine.process_retail(q_img, full_img, npc_name)
                    # process_retail blocks until playback finishes —
                    # record timestamp so stale log entries are skipped
                    _last_played["name"] = npc_name
                    _last_played["time"] = time.time()
                else:
                    log.info(
                        "Auto mode: Quest window not found on screen "
                        "after retries — skipping"
                    )

            watcher_thread = threading.Thread(
                target=watch_npc_file,
                args=(npc_found_callback, SCRIPT_LOG),
                daemon=True,
            )
            watcher_thread.start()

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("Exiting...")

        else:
            # ----- STATIC MODE: Fixed coordinates + Hotkey trigger -----
            # Quest window is assumed to be at QUEST_WINDOW_BOX coordinates.
            # User must NOT move the quest window after calibration.
            # Capture is triggered by the hotkey (middle mouse button).
            # A background NPC log watcher tracks the most recent NPC name
            # for correct voice resolution - but it does NOT trigger capture.
            print("Detection : Static coordinates (window must not move)")
            print("Trigger   : Manual (middle mouse button)")
            print()
            print("1. Press MIDDLE MOUSE to read quest text.")
            print("2. Press F12 to STOP current playback.")

            # Mouse listener for the hotkey trigger
            listener = mouse.Listener(on_click=on_click)
            listener.start()

            # --- NPC name tracking (voice resolution only, not a trigger) ---
            npc_tracking = {"name": "[MANUAL]", "time": 0.0}

            def npc_log_callback(npc_name):
                npc_tracking["name"] = npc_name
                npc_tracking["time"] = time.time()
                log.info(f"NPC tracked from log: {npc_name}")

            watcher_thread = threading.Thread(
                target=watch_npc_file,
                args=(npc_log_callback, SCRIPT_LOG),
                daemon=True,
            )
            watcher_thread.start()
            # ----------------------------------------

            try:
                while True:
                    if retail_capture_trigger.is_set():
                        retail_capture_trigger.clear()
                        print("Manual capture triggered...")
                        time.sleep(0.25)

                        q_img, full_img = capture_screen_areas(mode_prefix="retail")

                        if full_img is not None:
                            # Resolve NPC name from the log (with staleness check)
                            if (
                                npc_tracking["name"] != "[MANUAL]"
                                and time.time() - npc_tracking["time"]
                                <= NPC_NAME_MAX_AGE
                            ):
                                npc_name = npc_tracking["name"]
                                log.info(f"Using tracked NPC: {npc_name}")
                            else:
                                npc_name = "[MANUAL]"
                                if npc_tracking["time"] > 0:
                                    log.info(
                                        "NPC name stale (%.1fs old), "
                                        "falling back to narrator",
                                        time.time() - npc_tracking["time"],
                                    )
                            engine.process_retail(q_img, full_img, npc_name)

                        print("Ready.")
                    time.sleep(0.1)
            except KeyboardInterrupt:
                listener.stop()
                print("Exiting...")

    else:
        # ----- ECHOES MODE -----
        print("\n[ECHOES MODE STARTED]")
        print("1. Open Quest Window.")
        print("2. MIDDLE CLICK to narrate.")
        print("3. Press F12 to STOP current playback.")

        listener = mouse.Listener(on_click=on_click)
        listener.start()

        try:
            while True:
                if capture_trigger.is_set():
                    capture_trigger.clear()
                    print("Capturing...")
                    time.sleep(0.25)

                    q_img, n_img = capture_screen_areas(mode_prefix="echoes")

                    if q_img and n_img:
                        engine.process_capture(q_img, n_img)
                    else:
                        print("Capture failed. Check calibration.")

                    print("Ready.")
                time.sleep(0.1)
        except KeyboardInterrupt:
            listener.stop()
            kb_listener.stop()


if __name__ == "__main__":
    main()
