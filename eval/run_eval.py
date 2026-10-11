"""OCR evaluation harness: measures quest-title resolution accuracy on screenshots.

Usage
-----
1. Drop full-screen screenshots into ``experiments/test_screenshots/``.
2. Run ``uv run python eval/run_eval.py`` once - it creates/updates
   ``ground_truth.csv`` next to the images with one row per screenshot.
3. Fill in the ``expected_title`` column (the in-game quest title) and
   set ``mode`` to ``retail`` or ``echoes`` where needed. Use the
   special value ``(none)`` for screenshots where no quest window
   should be detected (e.g. mid-animation captures).
4. Re-run the harness - it scores every labeled screenshot and prints
   a summary of title-resolution accuracy and body-match rate.

Options
-------
--shots DIR       Screenshot folder (default: experiments/test_screenshots)
--save-crops      Write the extracted title/body crops to <shots>/debug/
                  for visual inspection of what the extractor produced.
--db-path PATH    Override the NPC database path.

Exit code is 0 when all labeled screenshots resolve correctly, 1 otherwise.
"""

import argparse
import csv
import sys
from pathlib import Path

# Make the project root importable when run as a plain script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[1]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


def load_screenshot(path: Path):
    """Load a screenshot the same way the live capture does (BGR numpy)."""
    import cv2
    import numpy as np
    from PIL import Image

    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def run_retail(db, img_np, save_crops, debug_dir, stem):
    """Mirror the retail pipeline: extract -> title OCR -> body OCR -> match."""
    from src.ocr import run_ocr, run_title_ocr_candidates
    from src.utils import extract_quest_areas

    title_pil, body_pil = extract_quest_areas(img_np)
    if title_pil is None and body_pil is None:
        return {"status": "NO WINDOW", "title_ocr": "", "body_ocr": ""}
    if save_crops and debug_dir:
        if title_pil is not None:
            title_pil.save(debug_dir / f"{stem}_title.png")
        if body_pil is not None:
            body_pil.save(debug_dir / f"{stem}_body.png")

    candidates = run_title_ocr_candidates(title_pil) if title_pil is not None else []
    body_sentences = run_ocr(body_pil) if body_pil is not None else []
    body = " ".join(body_sentences)
    return {
        "status": "OK",
        "title_ocr": candidates[0] if candidates else "",
        "title_candidates": candidates,
        "body_ocr": body,
    }


def run_echoes(db, img_np, save_crops, debug_dir, stem):
    """Mirror the echoes pipeline: stitched text + name box, title from first line."""
    import pytesseract

    from src.ocr import preprocess_title_image, run_name_ocr, run_ocr
    from src.utils import extract_echoes_areas

    quest_pil, name_pil = extract_echoes_areas(img_np)
    if quest_pil is None:
        return {"status": "NO WINDOW", "title_ocr": "", "body_ocr": ""}

    if save_crops and debug_dir:
        quest_pil.save(debug_dir / f"{stem}_quest.png")
        if name_pil is not None:
            name_pil.save(debug_dir / f"{stem}_name.png")

    body = " ".join(run_ocr(quest_pil))
    npc = run_name_ocr(name_pil) if name_pil is not None else ""

    # Title hint: first line of the stitched quest image (as in engine.py)
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
    return {"status": "OK", "title_ocr": title, "body_ocr": body, "npc_ocr": npc}


def read_ground_truth(gt_path: Path, shots: list) -> dict:
    """Load ground_truth.csv, adding rows for any new screenshots.

    Returns a dict {filename: {"expected_title": str, "mode": str}}.
    The CSV is rewritten when new screenshots appeared, so the user only
    ever fills in the expected_title column.
    """
    entries = {}
    if gt_path.exists():
        with open(gt_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if not row:
                    continue
                # Tolerate hand-edited rows where a title containing
                # commas was not quoted: treat everything between the
                # first and last column as the title.
                if len(row) > 3:
                    row = [row[0], ",".join(row[1:-1]), row[-1]]
                if len(row) < 3:
                    row = row + [""] * (3 - len(row))
                file, title, mode = row[0].strip(), row[1].strip(), row[2].strip()
                if mode not in ("retail", "echoes"):
                    if mode:
                        print(
                            f"[GT] Unknown mode '{mode}' for {file} - using retail"
                        )
                    mode = "retail"
                entries[file] = {"expected_title": title, "mode": mode}

    missing = [s.name for s in shots if s.name not in entries]
    if missing or not gt_path.exists():
        for name in missing:
            entries[name] = {"expected_title": "", "mode": "retail"}
        with open(gt_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["file", "expected_title", "mode"])
            for s in shots:  # keep rows in folder order
                e = entries[s.name]
                writer.writerow([s.name, e["expected_title"], e["mode"]])
        if missing:
            print(
                f"[GT] Added {len(missing)} new screenshot(s) to {gt_path.name} - "
                "fill in their expected_title column, then re-run."
            )
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--shots",
        default=str(REPO_ROOT / "experiments" / "test_screenshots"),
        help="Folder with full-screen screenshots",
    )
    parser.add_argument(
        "--save-crops",
        action="store_true",
        help="Save extracted title/body crops to <shots>/debug/",
    )
    parser.add_argument("--db-path", default=None, help="Override NPC database path")
    args = parser.parse_args()

    shots_dir = Path(args.shots)
    shots = sorted(
        p for p in shots_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS
    )
    if not shots:
        print(f"No screenshots found in {shots_dir}")
        return 1

    gt = read_ground_truth(shots_dir / "ground_truth.csv", shots)

    debug_dir = None
    if args.save_crops:
        debug_dir = shots_dir / "debug"
        debug_dir.mkdir(exist_ok=True)

    # Keep the report readable: the pipeline loggers are chatty at DEBUG
    import logging

    for name in ("UTILS", "OCR", "src.db_sqlite", "ENGINE"):
        logging.getLogger(name).setLevel(logging.WARNING)

    # Database: loaded once, reused for every screenshot
    from src.db_sqlite import NPCDatabaseSQLite

    db = NPCDatabaseSQLite(db_path=args.db_path) if args.db_path else NPCDatabaseSQLite()

    results = []
    for shot in shots:
        entry = gt.get(shot.name, {"expected_title": "", "mode": "retail"})
        expected = entry["expected_title"]
        mode = entry["mode"]

        img_np = load_screenshot(shot)
        runner = run_retail if mode == "retail" else run_echoes
        try:
            r = runner(db, img_np, args.save_crops, debug_dir, shot.stem)
        except Exception as e:
            r = {"status": f"ERROR: {e}", "title_ocr": "", "body_ocr": ""}

        r["file"] = shot.name
        r["mode"] = mode
        r["expected"] = expected

        # "(none)" marks screenshots where no quest window should be
        # detected (e.g. window mid fade-animation, or no window at all)
        if expected == "(none)":
            r["verdict"] = "CORRECT" if r["status"] == "NO WINDOW" else "UNEXPECTED WINDOW"
            results.append(r)
            continue

        if r["status"] != "OK" and not r["status"].startswith("ERROR"):
            # NO WINDOW: nothing more to compute
            results.append(r)
            continue

        # Resolve the OCR title against the database (same call the engine makes)
        quest_id, canonical = db.resolve_quest_id_best(
            r.get("title_candidates") or [r["title_ocr"]]
        )
        r["quest_id"] = quest_id
        r["resolved"] = canonical or ""

        if expected:
            exp_id, exp_title = db._resolve_quest_id(expected)
            if exp_id is None:
                r["verdict"] = "BAD GT"
            elif quest_id is None:
                r["verdict"] = "NO MATCH"
            elif quest_id == exp_id:
                r["verdict"] = "CORRECT"
            else:
                r["verdict"] = "WRONG QUEST"
        else:
            r["verdict"] = "UNLABELED"

        # Body segment match (what the engine would narrate)
        if quest_id is not None and r["body_ocr"]:
            m = db.match_quest_text(r["title_ocr"], r["body_ocr"])
            if m:
                r["body_match"] = f"{m['score']:.0%} [{m['text_type']}]"
                r["narrated"] = m["text"]
            else:
                r["body_match"] = "none"
        results.append(r)

    # ---- Report ----
    labeled = [r for r in results if r.get("verdict") not in (None, "UNLABELED")]
    print()
    print("=" * 78)
    print(f"{'Screenshot':<38} {'Verdict':<12} {'Title OCR / Resolved'}")
    print("=" * 78)
    for r in results:
        verdict = r.get("verdict", r["status"])
        title_info = r.get("title_ocr", "") or "(empty OCR)" if r["status"] == "OK" else r["status"]
        if r.get("resolved"):
            title_info += f"  ->  {r['resolved']}"
        print(f"{r['file'][:37]:<38} {verdict:<12} {title_info[:60]}")
        if r.get("verdict") in ("WRONG QUEST", "NO MATCH", "BAD GT") and r.get("expected"):
            print(f"{'':<38} {'expected':<12} {r['expected'][:60]}")
        if r.get("body_match"):
            print(f"{'':<38} {'body match':<12} {r['body_match']}")

    print("=" * 78)
    if labeled:
        correct = sum(1 for r in labeled if r["verdict"] == "CORRECT")
        matched = sum(1 for r in labeled if r["verdict"] in ("CORRECT", "WRONG QUEST"))
        windows = [r for r in labeled if r["status"] == "OK"]
        body_ok = sum(1 for r in windows if r.get("body_match") and r["body_match"] != "none")
        print(f"Labeled: {len(labeled)}   Title correct: {correct} ({correct/len(labeled):.0%})")
        print(f"Title resolved to *a* quest: {matched}/{len(labeled)}")
        if windows:
            print(f"Body segment matched: {body_ok}/{len(windows)} (windows found)")
        unlabeled = len(results) - len(labeled)
        if unlabeled:
            print(f"Unlabeled (fill ground_truth.csv): {unlabeled}")
        return 0 if correct == len(labeled) else 1
    print(
        "No labeled screenshots yet - fill in the expected_title column"
    )
    print(f"of {shots_dir / 'ground_truth.csv'} and re-run."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
