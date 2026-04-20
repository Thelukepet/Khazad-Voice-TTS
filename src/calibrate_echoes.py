# Imports

# > Standard Library
import json
import time
from pathlib import Path

# > Third-party Libraries
import cv2
import numpy as np
from PIL import ImageGrab

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).parent.parent  # Points to project root (not src/)
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
LAYOUT_FILE = DATA_DIR / "layout_echoes.json"

# Ensure folders exist
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Where we SAVE the user's specific calibration
USER_PATHS = {
    "left_plant": TEMPLATES_DIR / "echoes_left_plant.png",
    "right_plant": TEMPLATES_DIR / "echoes_right_plant.png",
    "tl_corner": TEMPLATES_DIR / "echoes_tl_corner.png",
    "br_corner": TEMPLATES_DIR / "echoes_br_corner.png",
}

# Example images to show the user what to look for
EXAMPLE_PATHS = {
    "left_plant": TEMPLATES_DIR / "example_echoes_left_plant.png",
    "right_plant": TEMPLATES_DIR / "example_echoes_right_plant.png",
    "tl_corner": TEMPLATES_DIR / "example_echoes_tl_corner.png",
    "br_corner": TEMPLATES_DIR / "example_echoes_br_corner.png",
}


def draw_instructions(img: np.ndarray, text: str, example_path: Path = None) -> None:
    """
    Draws a UI overlay on the image with instructions and an optional example image.
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

    # 3. Draw Example Image (if it exists)
    if example_path and example_path.exists():
        try:
            ex_img = cv2.imread(str(example_path))
            if ex_img is not None:
                eh, ew = ex_img.shape[:2]
                scale = 100 / eh  # Scale to 100px height
                new_w, new_h = int(ew * scale), int(eh * scale)
                ex_resized = cv2.resize(ex_img, (new_w, new_h))

                # Add border
                ex_resized = cv2.copyMakeBorder(
                    ex_resized, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(255, 255, 255)
                )
                new_h, new_w = ex_resized.shape[:2]

                # Position: Top Right
                x_offset = w - new_w - 50
                y_offset = (banner_height - new_h) // 2

                img[y_offset : y_offset + new_h, x_offset : x_offset + new_w] = (
                    ex_resized
                )
                cv2.putText(
                    img,
                    "Look for this:",
                    (x_offset, y_offset - 10),
                    font,
                    0.6,
                    (200, 200, 255),
                    1,
                    cv2.LINE_AA,
                )
        except Exception:
            pass


def select_roi(
    clean_img: np.ndarray, title: str, instruction: str, example_key: str = None
) -> tuple:
    """
    Opens the visual selection window using OpenCV's selectROI.
    """
    display_img = clean_img.copy()

    # Add UI Overlay
    example_path = EXAMPLE_PATHS.get(example_key) if example_key else None
    draw_instructions(display_img, instruction, example_path)

    window_name = f"Echoes Calibration - {title}"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)

    bbox = cv2.selectROI(window_name, display_img, fromCenter=False, showCrosshair=True)
    cv2.destroyWindow(window_name)

    if bbox[2] == 0 or bbox[3] == 0:
        return None

    return bbox


def save_template(img: np.ndarray, bbox: tuple, path: Path) -> None:
    x, y, w, h = bbox
    crop = img[y : y + h, x : x + w]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    cv2.imwrite(str(path), gray)
    print(f"   ✅ Saved to {path.name}")


def main():
    print("=================================================")
    print("   Khazad-Voice: Echoes of Angmar Calibration")
    print("=================================================")
    print("1. Open Quest Window.")
    print("2. Ensure NPC Name is visible.")
    print("3. Switch to Game NOW.")

    print("\nTaking screenshot in 10 seconds...")
    time.sleep(10)

    print("📸 SNAP! Screen captured.")

    try:
        screenshot = ImageGrab.grab()
    except OSError:
        print("❌ Error: Could not grab screen. Run as Admin?")
        return

    img_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    # --- STEP 1: LEFT PLANT ---
    r_lp = select_roi(
        img_bgr, "Step 1", "Select LEFT PLANT (Title Start)", "left_plant"
    )
    if not r_lp:
        return
    save_template(img_bgr, r_lp, USER_PATHS["left_plant"])

    # --- STEP 2: RIGHT PLANT ---
    r_rp = select_roi(
        img_bgr, "Step 2", "Select RIGHT PLANT (Title End)", "right_plant"
    )
    if not r_rp:
        return
    save_template(img_bgr, r_rp, USER_PATHS["right_plant"])

    # --- STEP 3: TOP-LEFT CORNER ---
    r_tl = select_roi(
        img_bgr, "Step 3", "Select TOP-LEFT CORNER (Start of Body)", "tl_corner"
    )
    if not r_tl:
        return
    save_template(img_bgr, r_tl, USER_PATHS["tl_corner"])

    # --- STEP 4: BOTTOM-RIGHT CORNER ---
    r_br = select_roi(
        img_bgr, "Step 4", "Select BOTTOM-RIGHT CORNER (End of Body)", "br_corner"
    )
    if not r_br:
        return
    save_template(img_bgr, r_br, USER_PATHS["br_corner"])

    # --- STEP 5: BODY TEXT (REFERENCE) ---
    r_text = select_roi(
        img_bgr,
        "Step 5",
        "Draw a box around the ACTUAL TEXT BODY (To learn margins)",
        None,
    )
    if not r_text:
        return

    # --- STEP 6: NPC NAME (STATIC) ---
    r_npc = select_roi(img_bgr, "Step 6", "Select the NPC NAME (Static Position)", None)
    if not r_npc:
        return

    # --- CALCULATE & SAVE ---

    # 1. Body Calculation
    tx, ty, _, _ = r_tl  # TL Corner Pos
    bx, by, bw, bh = r_text  # Text Pos
    brx, bry, _, _ = r_br  # BR Corner Pos

    # Calculate margins relative to the anchors
    offsets = {
        "body_left_margin": int(bx - tx),
        "body_top_margin": int(by - ty),
        "body_right_padding": int(brx - (bx + bw)),
        "body_bottom_padding": int(bry - (by + bh)),
    }

    # 2. NPC Calculation (Static)
    nx, ny, nw, nh = r_npc

    data = {
        "resolution": f"{img_bgr.shape[1]}x{img_bgr.shape[0]}",
        "offsets": offsets,
        "npc_box": [int(nx), int(ny), int(nw), int(nh)],
    }

    with open(LAYOUT_FILE, "w") as f:
        json.dump(data, f, indent=4)

    print("\n=================================================")
    print("✅ CALIBRATION SUCCESS!")
    print(f"Saved to: {LAYOUT_FILE}")
    print("=================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
    input("\nPress Enter to exit...")
