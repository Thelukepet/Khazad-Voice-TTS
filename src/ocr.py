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


def preprocess_title_image(img_pil: Image.Image) -> np.ndarray:
    """
    Preprocessing that completely ignores the blue title background.
    Extracts the Green color channel, which captures Cyan, Green, White,
    and Gold text perfectly while rendering the blue background pitch black.
    """
    img_np = np.array(img_pil)

    # 1. Isolate the text from the blue background
    if len(img_np.shape) == 3 and img_np.shape[2] == 3:
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        # Split into Blue, Green, and Red channels
        b, g, r = cv2.split(img_bgr)

        # The Green channel is the magic bullet here.
        # Cyan text = High Green + High Blue
        # Blue background = Low Green + High Blue
        # By using ONLY the Green channel, the background vanishes!
        gray = g
    else:
        gray = np.array(img_pil.convert("L"))

    # 2. Resize 3x (Crucial for Tesseract to read small game fonts accurately)
    upscaled = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    # 3. Apply a light blur to soften jagged pixel edges from the upscaling
    blurred = cv2.GaussianBlur(upscaled, (3, 3), 0)

    # 4. OTSU Thresholding (Calculates the perfect cutoff)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    # 5. DYNAMIC INVERSION (Tesseract needs Black text on White background)
    top = thresh[0, :]
    bottom = thresh[-1, :]
    left = thresh[:, 0]
    right = thresh[:, -1]

    border_pixels = np.concatenate((top, bottom, left, right))
    white_count = np.count_nonzero(border_pixels == 255)
    black_count = np.count_nonzero(border_pixels == 0)

    # Because we dropped the blue channel, the border will be mostly black.
    # This inverts the image so the background becomes pure white and text becomes black.
    if black_count > white_count:
        thresh = cv2.bitwise_not(thresh)

    return thresh


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
    """
    replacements = {
        "|": "I",
        "\u2018": "'",
        "\u2019": "'",
        "'T": "'I",
        "1": "I",
        "'Ihe": "The",
        "'l": "I",
        "Iam": "I am",
        "Ore": "Orc",
        "Ihank": "Thank",
    }
    cleaned = []
    for s in sentences:
        # Strip RGB markup tags from the game client
        s = re.sub(r"<rgb=[^>]*>", "", s)
        s = re.sub(r"</rgb>", "", s)
        for old, new in replacements.items():
            s = s.replace(old, new)
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
