"""Screenshot-based pipeline test for the Voice Lab.

Runs the full recognition pipeline (window detection, title OCR, database
resolution, body segment match) on an uploaded screenshot and reports
exactly what the narrator would do - so a user can verify the app works
on their system without starting the game.

The heavy database is loaded lazily and shared across runs.
"""

from typing import Any, Dict, Optional

import numpy as np

# Lazily created shared database (loading takes a few seconds)
_DB = None


def _get_db():
    global _DB
    if _DB is None:
        from src.db_sqlite import NPCDatabaseSQLite

        _DB = NPCDatabaseSQLite()
    return _DB


def run_test(img_rgb: np.ndarray, mode: str = "retail") -> Dict[str, Any]:
    """Run the recognition pipeline on a screenshot.

    Parameters
    ----------
    img_rgb : np.ndarray
        Screenshot as HxWx3 RGB array (as provided by Gradio).
    mode : str
        Game mode: ``retail`` or ``echoes``.

    Returns
    -------
    dict
        ``verdict`` (short status string), ``title_ocr``, ``resolved_title``,
        ``body_score``, ``text_type``, ``narrated_text``, ``player_name``,
        ``title_crop`` / ``body_crop`` (PIL images or None), ``error``.
    """
    import cv2

    result: Dict[str, Any] = {
        "verdict": "",
        "title_ocr": "",
        "resolved_title": "",
        "body_score": None,
        "text_type": "",
        "narrated_text": "",
        "player_name": "",
        "title_crop": None,
        "body_crop": None,
        "error": "",
    }

    try:
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    except Exception as e:
        result["error"] = f"Could not read the image: {e}"
        result["verdict"] = "ERROR"
        return result

    try:
        if mode == "echoes":
            _run_echoes(img_bgr, result)
        else:
            _run_retail(img_bgr, result)
    except Exception as e:
        result["error"] = str(e)
        result["verdict"] = "ERROR"
    return result


def _run_retail(img_bgr: np.ndarray, result: Dict[str, Any]) -> None:
    """Retail pipeline: extract -> title OCR -> body OCR -> DB match."""
    from src.ocr import run_ocr, run_title_ocr
    from src.utils import extract_quest_areas

    title_pil, body_pil = extract_quest_areas(img_bgr)
    if title_pil is None and body_pil is None:
        result["verdict"] = "NO WINDOW"
        result["error"] = (
            "No quest window was found on the screenshot. Make sure the "
            "quest window is fully visible and not covered by other panels."
        )
        return

    result["title_crop"] = title_pil
    result["body_crop"] = body_pil

    title = run_title_ocr(title_pil) if title_pil is not None else ""
    result["title_ocr"] = title
    body = " ".join(run_ocr(body_pil)) if body_pil is not None else ""

    _match_against_db(title, body, result)


def _run_echoes(img_bgr: np.ndarray, result: Dict[str, Any]) -> None:
    """Echoes pipeline: stitched text + name box, title from first line."""
    import pytesseract

    from src.ocr import preprocess_title_image, run_ocr
    from src.utils import extract_echoes_areas

    quest_pil, name_pil = extract_echoes_areas(img_bgr)
    if quest_pil is None:
        result["verdict"] = "NO WINDOW"
        result["error"] = (
            "No quest window was found. Echoes mode requires a calibrated "
            "layout - run the Echoes calibration first."
        )
        return

    result["body_crop"] = quest_pil
    result["title_crop"] = name_pil  # name box stands in for the title crop

    body = " ".join(run_ocr(quest_pil))
    title = ""
    try:
        thresh = preprocess_title_image(quest_pil)
        title = (
            pytesseract.pytesseract.image_to_string(thresh, config="--psm 7")
            .strip()
            .replace("\n", " ")
        )
    except Exception:
        pass
    result["title_ocr"] = title

    _match_against_db(title, body, result)


def _match_against_db(title: str, body: str, result: Dict[str, Any]) -> None:
    """Resolve the OCR title against the database and match the body."""
    db = _get_db()

    quest_id, canonical = db._resolve_quest_id(title)
    result["resolved_title"] = canonical or ""

    if quest_id is None:
        result["verdict"] = "TITLE NOT RECOGNIZED"
        result["error"] = (
            "The quest window was found, but the title could not be matched "
            "to a quest in the database. The narrator will read the raw OCR "
            "text instead of pristine database text."
        )
        return

    if body:
        match = db.match_quest_text(title, body)
        if match:
            result["verdict"] = "OK"
            result["body_score"] = match["score"]
            result["text_type"] = match["text_type"]
            result["narrated_text"] = match["text"]
            result["player_name"] = match.get("player_name", "")
        else:
            result["verdict"] = "BODY NOT MATCHED"
            result["error"] = (
                "The quest was recognized, but the shown text was not found "
                "among its database segments. The narrator will read the raw "
                "OCR text instead."
            )
    else:
        result["verdict"] = "OK"
        result["error"] = "Quest recognized (no body text was read)."
