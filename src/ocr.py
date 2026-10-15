# Imports

# > Standard Library
import re
from typing import List

# > Third-party Libraries
import cv2
import nltk
import numpy as np
import pytesseract
from PIL import Image, ImageOps

# > Local Dependencies
from .config.ConfigManager import ConfigManager

_ocr_initialized = False


def _ensure_initialized():
    """Lazy one-time setup for OCR: configure Tesseract path and download NLTK data."""
    global _ocr_initialized
    if _ocr_initialized:
        return
    _cfg = ConfigManager()
    pytesseract.pytesseract.tesseract_cmd = _cfg.tesseract_cmd
    nltk.download("punkt", quiet=True)
    _ocr_initialized = True


def preprocess_image(img_pil: Image.Image) -> np.ndarray:
    """
    Standard preprocessing for Body Text (Paragraphs).
    1. Convert to Grayscale.
    2. Resize 2x (Cubic Interpolation).
    3. Binary Thresholding (120/255).

    Returns
    -------
    np.ndarray
        The preprocessed image ready for OCR.
    """
    img_np = np.array(img_pil.convert("L"))
    img_np = cv2.resize(img_np, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(img_np, 120, 255, cv2.THRESH_BINARY)
    return thresh


# > Green-channel cutoff for title/name text. Gold/cyan/white text sits
# well above this value, the blue window background well below (measured
# across the eval screenshots: text ~150-230, background ~30-60).
_TITLE_THRESH = 100


def preprocess_title_image(
    img_pil: Image.Image, thresh: int = _TITLE_THRESH, channel: int = 1
) -> np.ndarray:
    """
    Preprocessing that completely ignores the blue title background.

    Extracts a single colour channel, which captures the title text while
    rendering the dark blue window background pitch black. The default
    Green channel captures cyan, green, white and gold text; quest titles
    render in level-dependent colours (red = above level, blue = below),
    so callers can request the Red or Blue channel for those.

    Parameters
    ----------
    img_pil : Image.Image
        Title bar crop.
    thresh : int
        Green-channel cutoff for text (see ``_TITLE_THRESH``).
    channel : int
        0 = Red, 1 = Green (default), 2 = Blue.
    """
    img_np = np.array(img_pil)

    # 1. Isolate the text from the blue background
    if len(img_np.shape) == 3 and img_np.shape[2] == 3:
        # The window background is dark blue: low green and low red.
        # Picking a single channel makes the background vanish while
        # keeping text of the matching hue bright.
        gray = img_np[:, :, channel]
    else:
        gray = np.array(img_pil.convert("L"))

    # 2. Resize 3x (Crucial for Tesseract to read small game fonts accurately)
    upscaled = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    # 3. Apply a light blur to soften jagged pixel edges from the upscaling
    blurred = cv2.GaussianBlur(upscaled, (3, 3), 0)

    # 4. Fixed threshold + inversion. The green channel guarantees the
    # setup "bright text on dark background" (blue window background has
    # low green, gold/cyan/white text has high green), so a fixed cutoff
    # is more robust than OTSU: on some crops OTSU splits the background
    # itself into two classes, and the old border-based inversion guess
    # then produced giant black blobs that made Tesseract return nothing.
    # THRESH_BINARY gives white text on black; inverting yields the
    # black-on-white image Tesseract needs.
    _, binary = cv2.threshold(blurred, thresh, 255, cv2.THRESH_BINARY)
    return cv2.bitwise_not(binary)


def remove_leading_artifacts(text: str) -> str:
    """
    Removes OCR artifacts caused by icons (like the left leaf) bleeding into the text box.

    Logic:
    If the text starts with a sequence of lowercase letters, spaces, or weird symbols
    (like '|', 'a', 'ae'), followed immediately by a Capital Letter or Quote,
    we strip the prefix.

    Example:
    "ae o a e f "Greetings" -> "Greetings"
    "a 'I need" -> "'I need"
    """
    # Regex Explanation:
    # ^                 : Start of string
    # [a-z\s|/\\.,;:\-]+: Match 1+ lowercase chars, spaces, or noise symbols
    # (?=['"A-Z])       : Positive Lookahead - ensure it is followed by a Quote or Capital
    cleaned = re.sub(r"^[a-z\s|/\\.,;:\-]+(?=['\"A-Z])", "", text).strip()
    return cleaned


def clean_ocr_errors(sentences: List[str]) -> List[str]:
    """
    Fixes common OCR misinterpretations specific to the LOTRO font.
    e.g., '|' -> 'I', 'Iam' -> 'I am'.

    Also strips RGB markup tags from the game client (e.g.
    ``<rgb=#FF00FF00>...</rgb>``) so they aren't read aloud.

    Word-ambiguous fixes (``1`` → ``I``, ``Ore`` → ``Orc``) are only
    applied to whole words so real words like ``1st`` or the ore of a
    mountain are preserved.
    """
    replacements = {
        "|": "I",
        "\u2018": "'",
        "\u2019": "'",
        "'T": "'I",
        "'Ihe": "The",
        "'l": "I",
        "Iam": "I am",
        "Ihank": "Thank",
    }
    word_replacements = {
        "1": "I",
        "Ore": "Orc",
    }
    cleaned = []
    for s in sentences:
        # Strip RGB markup tags from the game client
        s = re.sub(r"<rgb=[^>]*>", "", s)
        s = re.sub(r"</rgb>", "", s)
        for old, new in replacements.items():
            s = s.replace(old, new)
        # Whole-word replacements only (preserve "1st", "Ore" the material)
        for old, new in word_replacements.items():
            s = re.sub(
                rf"(?<![A-Za-z0-9]){re.escape(old)}(?![A-Za-z0-9])",
                new,
                s,
            )
        s = re.sub(r"'lam\b", "I am", s, flags=re.IGNORECASE)
        s = re.sub(r"\bgoad\b", "good", s, flags=re.IGNORECASE)
        s = s.strip()
        if s:
            cleaned.append(s)
    return cleaned


def run_ocr(img_pil: Image.Image) -> List[str]:
    """
    Runs OCR on the Quest Body.
    """
    _ensure_initialized()
    thresh = preprocess_image(img_pil)

    # PSM 6 = Assume a single uniform block of text
    raw = pytesseract.image_to_string(thresh, config="--psm 6")

    # 1. Merge newlines into spaces to treat as one block
    merged_block = re.sub(r"\s*\n\s*", " ", raw).strip()

    # 2. Cut off at "REWARDS"
    # This discards "REWARDS" and everything following it. (otherwise it will start reading the rewards)
    if "REWARDS" in merged_block:
        merged_block = merged_block.split("REWARDS")[0].strip()

    # 3. Remove "Leaf Artifacts" from the very start of the block
    merged_block = remove_leading_artifacts(merged_block)

    # 4. Tokenize into sentences
    sentences = nltk.sent_tokenize(merged_block)

    # 5. Clean specific word errors
    final_lines = clean_ocr_errors(sentences)

    return final_lines


def run_title_ocr(img_pil: Image.Image) -> str:
    """
    Runs OCR on the Quest Title.
    """
    _ensure_initialized()
    thresh = preprocess_title_image(img_pil)
    raw = pytesseract.image_to_string(thresh, config="--psm 7")
    return raw.strip().replace("\n", " ")


# > Channel/threshold passes for title OCR. Quest titles render in
# level-dependent colours: white/gold on-level, grey/green/blue below,
# red above. Each colour is bright in exactly one channel against the
# dark blue window background, so one pass per colour family is tried
# and the database match picks the plausible reading - wrong-channel
# passes produce garbage that does not resolve.
_TITLE_PASSES = ((1, 80), (1, 100), (0, 80), (2, 160))


def run_title_ocr_candidates(img_pil: Image.Image) -> list:
    """
    Runs title OCR across channel/threshold passes for every title colour.

    The quest title bar is translucent and the text colour depends on the
    quest level relative to the player. The caller resolves each
    candidate against the quest database and keeps the best match - no
    single pass wins on all colours and scenes (measured across the eval
    screenshots and synthetic red/blue titles).

    Returns
    -------
    list[str]
        Unique, non-empty OCR results.
    """
    _ensure_initialized()
    seen = []
    for channel, tv in _TITLE_PASSES:
        thresh = preprocess_title_image(img_pil, thresh=tv, channel=channel)
        raw = (
            pytesseract.image_to_string(thresh, config="--psm 7")
            .strip()
            .replace("\n", " ")
        )
        if raw and raw not in seen:
            seen.append(raw)
    return seen


def run_name_ocr(img_pil: Image.Image) -> str:
    """
    Runs OCR on an NPC Name tag.
    Uses PSM 7 (Treat the image as a single text line).
    """
    _ensure_initialized()
    thresh = preprocess_title_image(img_pil)
    raw = pytesseract.image_to_string(thresh, config="--psm 7")
    clean = raw.strip().replace("\n", " ").replace("|", "I").replace("1", "I")
    return clean


def run_nameplate_ocr(img_pil: Image.Image) -> str:
    """
    Runs OCR on an Echoes NPC nameplate: a solid black box with bright
    text (white/gold). The retail title preprocessing is wrong for this
    (it expects the dark blue window background), so the plate gets its
    own pipeline: grayscale, 2x upscale, bright-text threshold inverted
    to black-on-white, white border padding, PSM 7 with a letters-only
    whitelist.

    Parameters
    ----------
    img_pil : Image.Image
        Nameplate crop (the black box, tightly or generously framed).

    The crop may include surroundings (a calibrated box is rarely
    pixel-tight), so the solid dark plate is located inside the crop
    and the OCR runs on the trimmed plate only - the plate's border
    edge corrupts the read when it slips into the thresholded image.

    Parameters
    ----------
    img_pil : Image.Image
        Nameplate crop (the black box, tightly or generously framed).

    Returns
    -------
    str
        The name read from the plate (may be empty).
    """
    _ensure_initialized()
    gray = np.array(img_pil.convert("L"))

    # Trim to the solid dark plate (largest dark blob in the crop)
    _, dark = cv2.threshold(gray, 45, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(
        dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if contours:
        c = max(contours, key=cv2.contourArea)
        px, py, pw, ph = cv2.boundingRect(c)
        if pw > 20 and ph > 8:
            gray = gray[py : py + ph, px : px + pw]

    big = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(big, 90, 255, cv2.THRESH_BINARY_INV)
    thresh = cv2.copyMakeBorder(
        thresh, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255
    )
    raw = pytesseract.image_to_string(
        thresh,
        config="--psm 7 -c tessedit_char_whitelist="
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz ",
    )
    return raw.strip().replace("\n", " ")
