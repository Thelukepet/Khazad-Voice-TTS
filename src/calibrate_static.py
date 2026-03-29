# Imports

# > Standard Library
import json
import time
from pathlib import Path

# > Third-party Libraries
import cv2
import numpy as np
from PIL import ImageGrab

# Configuration
BASE_DIR = Path(__file__).parent.parent  # Points to project root (not src/)
DATA_DIR = BASE_DIR / "data"
CONFIG_FILE = BASE_DIR / "src" / "config.py"

# Ensure folders exist
DATA_DIR.mkdir(parents=True, exist_ok=True)


def draw_instructions(img: np.ndarray, text: str) -> None:
    """
    Draws a UI overlay on the image with instructions.

    Parameters
    ----------
    img : np.ndarray
        The screenshot image (BGR format) to draw upon.
    text : str
        The instruction text to display in the banner.
    """
    h, w = img.shape[:2]

    # 1. Draw a dark banner at the top
    banner_height = 160
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, banner_height), (0, 0, 0), -1)
    alpha = 0.85
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

    # 2. Draw Text
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, text, (30, 60), font, 1.2, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(
        img,
        "Click & Drag to draw box. Press SPACE to confirm. Press C to retry.",
        (30, 110),
        font,
        0.7,
        (200, 200, 200),
        1,
        cv2.LINE_AA,
    )


def select_roi(img: np.ndarray, title: str, instruction: str) -> tuple:
    """
    Opens the visual selection window using OpenCV's selectROI.

    Parameters
    ----------
    img : np.ndarray
        The screenshot image (BGR).
    title : str
        The window title for the ROI selector.
    instruction : str
        The text instruction to display to the user.

    Returns
    -------
    tuple or None
        (x, y, w, h) of the selected region, or None if selection was invalid/cancelled.
    """
    display_img = img.copy()
    draw_instructions(display_img, instruction)

    window_name = "Khazad-Voice: Static Quest Window Calibration"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)

    bbox = cv2.selectROI(window_name, display_img, fromCenter=False, showCrosshair=True)
    cv2.destroyWindow(window_name)

    if bbox[2] == 0 or bbox[3] == 0:
        return None

    return bbox


def update_config(box: tuple, trigger_key: str = "middle_mouse"):
    """
    Updates config.py with the new QUEST_WINDOW_BOX values and sets mode to 'static'.

    Parameters
    ----------
    box : tuple
        (x, y, w, h) bounding box coordinates.
    trigger_key : str
        The trigger key to use (default: "middle_mouse")
    """
    x, y, w, h = box
    box_list = [x, y, w, h]

    # Read config.py
    with open(CONFIG_FILE, "r") as f:
        lines = f.readlines()

    # Find and update QUEST_WINDOW_MODE line
    # Find and update QUEST_WINDOW_BOX line
    # Find and update QUEST_TRIGGER_MODE line
    # Find and update QUEST_TRIGGER_KEY line
    new_lines = []
    for line in lines:
        if line.strip().startswith("QUEST_WINDOW_MODE ="):
            new_lines.append('QUEST_WINDOW_MODE = "static"\n')
        elif line.strip().startswith("QUEST_WINDOW_BOX ="):
            new_lines.append(f"QUEST_WINDOW_BOX = {box_list}\n")
        elif line.strip().startswith("QUEST_TRIGGER_MODE ="):
            new_lines.append('QUEST_TRIGGER_MODE = "manual"\n')
        elif line.strip().startswith("QUEST_TRIGGER_KEY ="):
            new_lines.append(f'QUEST_TRIGGER_KEY = "{trigger_key}"\n')
        else:
            new_lines.append(line)

    # Write back
    with open(CONFIG_FILE, "w") as f:
        f.writelines(new_lines)


def main():
    print("=================================================")
    print("   Khazad-Voice: Static Quest Window Calibration")
    print("=================================================")
    print("\nThis tool lets you manually define the quest window bounding box.")
    print("Use this if automatic template matching doesn't work on your setup.")
    print("\n1. Open LOTRO with a quest window visible.")
    print("2. Make sure the quest TEXT body is fully visible (not the title bar).")
    print("3. Switch to the game NOW.")

    print("\nTaking screenshot in 10 seconds...")
    for i in range(10, 0, -1):
        print(f"{i}...")
        time.sleep(1)

    print("📸 SNAP! Screen captured.")

    try:
        screenshot = ImageGrab.grab()
    except OSError:
        print("❌ Error: Could not grab screen. Run as Admin?")
        return

    img_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    # Select the quest text body area
    print("\n📏 Draw a box around the QUEST TEXT BODY area (the main text content).")
    print("   Do NOT include the title bar or borders.")

    box = select_roi(
        img_bgr,
        "Select Quest Text Body",
        "Draw box around the quest text body (main content area)",
    )

    if not box:
        print("\n❌ No valid selection made. Please run again.")
        return

    x, y, w, h = box
    print(f"\n✅ Selected box: x={x}, y={y}, w={w}, h={h}")

    # Ask user for trigger key
    print("\n" + "=" * 60)
    print("  TRIGGER KEY CONFIGURATION")
    print("=" * 60)
    print("\nWhat key would you like to use to trigger quest reading?")
    print("\nOptions:")
    print("  • [Press Enter] - Use middle mouse button (recommended)")
    print("  • Type a keyboard key name (e.g., 'f8', 't', 'q')")
    print("  • Type mouse button name (e.g., 'left', 'right', 'middle')")
    print("\nNote: In manual mode, you press this key whenever you want")
    print("      to read the quest text - no automatic triggering.")
    print("=" * 60)

    trigger_key_input = input(
        "\nEnter trigger key (or press Enter for middle mouse): "
    ).strip()
    trigger_key = trigger_key_input.lower() if trigger_key_input else "middle_mouse"

    # Validate common inputs
    if trigger_key in ["left", "right", "middle", "middle_mouse"]:
        trigger_key = "middle_mouse"
    elif trigger_key == "f8":
        trigger_key = "f8"
    # Add more validations as needed

    print(f"\n✅ Trigger key set to: {trigger_key.upper()}")

    # Save calibration to config.py
    update_config(box, trigger_key)

    print("\n=================================================")
    print("✅ CALIBRATION SUCCESS!")
    print(f"   QUEST_WINDOW_MODE set to 'static'")
    print(f"   QUEST_WINDOW_BOX set to [{x}, {y}, {w}, {h}]")
    print(f"   QUEST_TRIGGER_MODE set to 'manual'")
    print(f"   QUEST_TRIGGER_KEY set to '{trigger_key}'")
    print(f"   Saved to: {CONFIG_FILE}")
    print("=================================================")
    print("\n🎮 HOW TO USE:")
    print(f"   1. Start the application in RETAIL mode")
    print(f"   2. Press {trigger_key.upper()} whenever you want to read quest text")
    print(f"   3. Press F12 to stop current playback")
    print("\n📝 To switch back to auto mode, edit config.py and set:")
    print("   QUEST_WINDOW_MODE = 'auto'")
    print("   QUEST_TRIGGER_MODE = 'auto'")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    input("\nPress Enter to exit...")
