# Imports

# > Standard Library
import re
from typing import List

# > Third-party Libraries
import cv2
import numpy as np
import pytesseract
import nltk
from PIL import Image, ImageOps

# > Local Dependencies
from .config import TESSERACT_CMD

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
nltk.download("punkt", quiet=True)


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
    Preprocessing optimized for Single-Line Titles/Names.
    1. Grayscale.
    2. Resize 2x.
    3. Bitwise NOT (Invert colors).
    4. OTSU Thresholding.

    Returns
    -------
    np.ndarray
        The preprocessed image.
    """
    img_np = np.array(img_pil.convert("L"))
    img_np = cv2.resize(img_np, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    img_np = cv2.bitwise_not(img_np)
    _, thresh = cv2.threshold(img_np, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    return thresh


def clean_ocr_errors(sentences: List[str]) -> List[str]:
    """
    Fixes common OCR misinterpretations specific to the LOTRO font.
    e.g., '|' -> 'I', 'Iam' -> 'I am'.
    """
    replacements = {
        "|": "I",
        "‘": "'",
        "’": "'",
        "'T": "'I",
        "1": "I",
        "'Ihe": "The",
        "REWARDS": "",
        "'l": "I",
        "Iam": "I am",
        "Ore": "Orc",
        "Ihank": "Thank"
    }
    cleaned = []
    for s in sentences:
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
    Uses PSM 6 (Assume a single uniform block of text).
    """
    thresh = preprocess_image(img_pil)
    raw = pytesseract.image_to_string(thresh, config="--psm 6")
    merged_block = re.sub(r"\s*\n\s*", " ", raw).strip()
    sentences = nltk.sent_tokenize(merged_block)
    return [line for line in clean_ocr_errors(sentences) if len(line) > 1]


def run_title_ocr(img_pil: Image.Image) -> str:
    """
    Runs OCR on the Quest Title.
    """
    thresh = preprocess_title_image(img_pil)
    raw = pytesseract.image_to_string(thresh, config="--psm 7")
    return raw.strip().replace("\n", " ")


def run_name_ocr(img_pil: Image.Image) -> str:
    """
    Runs OCR on an NPC Name tag.
    Uses PSM 7 (Treat the image as a single text line).
    """
    thresh = preprocess_title_image(img_pil)
    raw = pytesseract.image_to_string(thresh, config="--psm 7")
    clean = raw.strip().replace("\n", " ").replace("|", "I").replace("1", "I")
    return clean
