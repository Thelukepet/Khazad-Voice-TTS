# Imports

# > Standard Library
import time
import json
from pathlib import Path

# > Third-party Libraries
import cv2
import numpy as np
from PIL import ImageGrab

# Configuration
DATA_DIR = Path(__file__).parent / "data"
TEMPLATES_DIR = Path(__file__).parent / "templates"
LAYOUT_FILE = DATA_DIR / "layout_retail.json"

# Where we SAVE the user's specific calibration
USER_PATHS = {
    "start": TEMPLATES_DIR / "user_start.png",
    "end": TEMPLATES_DIR / "user_end.png",
    "corner": TEMPLATES_DIR / "user_corner.png",
    "intersect": TEMPLATES_DIR / "user_intersect.png",
    "icon": TEMPLATES_DIR / "user_icon.png",
}

# The STANDARD templates (used as visual examples for the user)
EXAMPLE_PATHS = {
    "start": TEMPLATES_DIR / "start_leaf.png",
    "end": TEMPLATES_DIR / "end_leaf.png",
    "corner": TEMPLATES_DIR / "body_upper_left_corner.png",
    "intersect": TEMPLATES_DIR / "intersection.png",
    "icon": TEMPLATES_DIR / "filter_icon.png",
}

# Ensure folders exist
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


def draw_instructions(img: np.ndarray, text: str, example_path: Path = None) -> None:
    """
    Draws a UI overlay on the image with instructions and an optional example image.

    Parameters
    ----------
    img : np.ndarray
        The screenshot image (BGR format) to draw upon.
    text : str
        The instruction text to display in the banner.
    example_path : Path, optional
        Path to an example image (template) to display as a visual guide.
    """
    h, w = img.shape[:2]

    # 1. Draw a dark banner at the top
    banner_height = 160
    # Semi-transparent overlay
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (w, banner_height), (0, 0, 0), -1)
    alpha = 0.85
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

    # 2. Draw Text
    font = cv2.FONT_HERSHEY_SIMPLEX
    # Main instruction
    cv2.putText(img, text, (30, 60), font, 1.2, (255, 255, 255), 2, cv2.LINE_AA)
    # Sub-instruction
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
                # Resize example for visibility (max height 100px)
                eh, ew = ex_img.shape[:2]
                scale = 100 / eh
                new_w, new_h = int(ew * scale), int(eh * scale)
                ex_resized = cv2.resize(ex_img, (new_w, new_h))

                # Add a white border around the example
                ex_resized = cv2.copyMakeBorder(
                    ex_resized, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(255, 255, 255)
                )
                new_h, new_w = ex_resized.shape[:2]

                # Position: Top Right area of the banner
                x_offset = w - new_w - 50
                y_offset = (banner_height - new_h) // 2

                # Overlay
                img[y_offset : y_offset + new_h, x_offset : x_offset + new_w] = (
                    ex_resized
                )

                # Label for the example
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
            pass  # Fail silently on image load error, text is enough


def select_roi(
    clean_img: np.ndarray, title: str, instruction: str, example_key: str = None
) -> tuple:
    """
    Opens the visual selection window using OpenCV's selectROI.

    Draws instructions on a temporary copy of the image so the returned
    coordinates correspond to the clean, original image.

    Parameters
    ----------
    clean_img : np.ndarray
        The original screenshot image (BGR).
    title : str
        The window title for the ROI selector.
    instruction : str
        The text instruction to display to the user.
    example_key : str, optional
        The key in EXAMPLE_PATHS to retrieve the visual guide image.

    Returns
    -------
    tuple or None
        (x, y, w, h) of the selected region, or None if selection was invalid/cancelled.
    """
    # Create a copy for display so we don't draw text on the actual screenshot
    display_img = clean_img.copy()

    # Add UI Overlay
    example_path = EXAMPLE_PATHS.get(example_key) if example_key else None
    draw_instructions(display_img, instruction, example_path)

    window_name = "Khazad-Voice Calibration"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)

    # Select ROI on the annotated image
    bbox = cv2.selectROI(window_name, display_img, fromCenter=False, showCrosshair=True)
    cv2.destroyWindow(window_name)

    # Validate
    if bbox[2] == 0 or bbox[3] == 0:
        return None

    return bbox


def save_template(img: np.ndarray, bbox: tuple, path: Path) -> None:
    """
    Crops the image based on the bounding box, converts to grayscale, and saves to disk.

    Parameters
    ----------
    img : np.ndarray
        The source image (BGR).
    bbox : tuple
        (x, y, w, h) bounding box.
    path : Path
        The file path to save the template to.
    """
    x, y, w, h = bbox
    crop = img[y : y + h, x : x + w]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    cv2.imwrite(str(path), gray)
    print(f"   ✅ Saved to {path.name}")


def main():
    print("=================================================")
    print("   Khazad-Voice: Calibration")
    print("=================================================")
    print("1. Open LOTRO Quest Window.")
    print("2. Make sure it is fully visible.")
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

    # Convert to OpenCV format (BGR)
    img_bgr = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    # --- STEP 1: LEFT LEAF ---
    r_start = select_roi(
        img_bgr, "Step 1", "Select the LEFT LEAF icon (Start of Title)", "start"
    )
    if not r_start:
        return
    save_template(img_bgr, r_start, USER_PATHS["start"])

    # --- STEP 2: RIGHT LEAF ---
    r_end = select_roi(
        img_bgr, "Step 2", "Select the RIGHT LEAF icon (End of Title)", "end"
    )
    if not r_end:
        return
    save_template(img_bgr, r_end, USER_PATHS["end"])

    # --- STEP 3: BODY CORNER ---
    r_corner = select_roi(
        img_bgr, "Step 3", "Select the TOP-LEFT CORNER inside the text box", "corner"
    )
    if not r_corner:
        return
    save_template(img_bgr, r_corner, USER_PATHS["corner"])

    # --- STEP 4: INTERSECTION ---
    r_int = select_roi(
        img_bgr, "Step 4", "Select the RIGHT INTERSECTION (Defines Width)", "intersect"
    )
    if not r_int:
        return
    save_template(img_bgr, r_int, USER_PATHS["intersect"])

    # --- STEP 5: ICON ---
    r_icon = select_roi(
        img_bgr, "Step 5", "Select the FILTER ICON (Defines Height)", "icon"
    )
    if not r_icon:
        return
    save_template(img_bgr, r_icon, USER_PATHS["icon"])

    # --- STEP 6: CALCULATION ---
    r_text = select_roi(
        img_bgr,
        "Step 6",
        "Draw a box around the ACTUAL TEXT area to verify margins",
        None,
    )
    if not r_text:
        return

    # Calculate offsets based on user selection
    cx, cy = r_corner[0], r_corner[1]  # Corner Pos
    bx, by = r_text[0], r_text[1]  # Actual Text Pos

    ix, icy = r_int[0], r_icon[1]  # Intersect X and Icon Y
    bw, bh = r_text[2], r_text[3]  # Text Width/Height

    # 1. How far is text from the corner?
    off_x = bx - cx
    off_y = by - cy

    # 2. Padding calculation (Reverse engineering the working logic)
    # Logic: body_w = (ix - PADDING_X) - body_x
    # So: PADDING_X = ix - (body_x + body_w)
    pad_int_x = ix - (bx + bw)

    # Logic: body_h = (icy - PADDING_Y) - body_y
    # So: PADDING_Y = icy - (body_y + body_h)
    pad_icon_y = icy - (by + bh)

    layout_data = {
        "resolution": f"{img_bgr.shape[1]}x{img_bgr.shape[0]}",
        "offsets": {
            "CORNER_OFFSET_X": int(off_x),
            "CORNER_OFFSET_Y": int(off_y),
            "PADDING_INTERSECT_X": int(pad_int_x),
            "PADDING_ICON_Y": int(pad_icon_y),
        },
    }

    with open(LAYOUT_FILE, "w") as f:
        json.dump(layout_data, f, indent=4)

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
