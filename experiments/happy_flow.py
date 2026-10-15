"""Happy-flow test: auto-calibrate on every example screenshot, then run the
full screenshot_tester pipeline with the calibration it just produced.

For each retail screenshot in experiments/test_screenshots/ (per ground_truth.csv):
1. Wipe any previous calibration (fresh-install condition).
2. auto_calibrate_retail(screenshot) -> must return ok=True with all anchors.
3. Verify all 5 user templates + layout_retail.json were written.
4. screenshot_tester.run_test(screenshot) -> must reach verdict OK
   (window found, title OCR'd, quest resolved in DB, body matched).
5. resolved_title must equal the ground-truth title.

Run from repo root on 192.168.2.8:  python3 happy_flow.py
Results are appended to happy_flow_results.jsonl.
"""

import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

from src.auto_calibrate import auto_calibrate_retail  # noqa: E402
from src.config.ConfigManager import ConfigManager  # noqa: E402
from src.utils import TEMPLATES_DIR, get_layout_file  # noqa: E402
from src.voice_lab import screenshot_tester  # noqa: E402

SHOTS = BASE / "experiments" / "test_screenshots"
USER_TEMPLATES = [TEMPLATES_DIR / f"user_{k}.png" for k in
                  ("start", "end", "corner", "intersect", "icon")]
LAYOUT = get_layout_file("retail")
RESULTS = BASE / "experiments" / "happy_flow_results.jsonl"


def wipe_calibration():
    for p in USER_TEMPLATES:
        p.unlink(missing_ok=True)
    LAYOUT.unlink(missing_ok=True)


def main():
    rows = list(csv.DictReader(open(SHOTS / "ground_truth.csv")))
    retail = [r for r in rows if r["mode"] == "retail"]
    print(f"{len(retail)} retail screenshots to test\n")

    out = open(RESULTS, "a")
    summary = {"pass": 0, "fail": 0}

    for r in retail:
        name = r["file"]
        expected = r["expected_title"]
        rec = {"file": name, "expected": expected}

        try:
            img = cv2.imread(str(SHOTS / name))
            assert img is not None, "could not read image"
            h, w = img.shape[:2]
            rec["resolution"] = f"{w}x{h}"

            # Step 1: fresh calibration
            wipe_calibration()
            ok, report = auto_calibrate_retail(img)
            rec["calib_ok"] = ok
            rec["calib_message"] = report["message"]
            rec["anchors"] = report.get("anchors", {})
            if not ok:
                rec["stage"] = "CALIBRATION FAILED"
                rec["pass"] = False
                summary["fail"] += 1
                print(f"FAIL [calibration] {name}: {report['message']}")
                out.write(json.dumps(rec) + "\n")
                out.flush()
                continue

            # Step 2: files written?
            missing = [p.name for p in USER_TEMPLATES if not p.exists()]
            if LAYOUT.exists():
                lay = json.loads(LAYOUT.read_text())
                rec["layout_resolution"] = lay.get("resolution")
            else:
                missing.append(LAYOUT.name)
            if missing:
                rec["stage"] = "FILES MISSING"
                rec["missing"] = missing
                rec["pass"] = False
                summary["fail"] += 1
                print(f"FAIL [files] {name}: missing {missing}")
                out.write(json.dumps(rec) + "\n")
                out.flush()
                continue
            rec["files_written"] = True

            # Step 3: full pipeline with the fresh calibration
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            res = screenshot_tester.run_test(img_rgb, mode="retail")
            rec["verdict"] = res["verdict"]
            rec["title_ocr"] = res["title_ocr"]
            rec["resolved_title"] = res["resolved_title"]
            rec["body_score"] = res["body_score"]
            rec["text_type"] = res.get("text_type", "")
            rec["player_name"] = res.get("player_name", "")
            rec["npc_name"] = res.get("npc_name", "")
            rec["narrated_chars"] = len(res.get("narrated_text") or "")

            if res["verdict"] != "OK":
                rec["stage"] = f"PIPELINE {res['verdict']}"
                rec["error"] = res["error"]
                rec["pass"] = False
                summary["fail"] += 1
                print(f"FAIL [pipeline:{res['verdict']}] {name}: {res['error'][:120]}")
                out.write(json.dumps(rec) + "\n")
                out.flush()
                continue

            # Step 4: resolved title vs ground truth
            match = (res["resolved_title"] or "").strip().lower() == expected.strip().lower()
            rec["title_matches_ground_truth"] = match
            if not match:
                rec["stage"] = "TITLE MISMATCH"
                rec["pass"] = False
                summary["fail"] += 1
                print(f"FAIL [title] {name}: got '{res['resolved_title']}' "
                      f"wanted '{expected}'")
            else:
                rec["stage"] = "PASS"
                rec["pass"] = True
                summary["pass"] += 1
                print(f"PASS {name}: '{res['resolved_title']}' "
                      f"body={res['body_score']:.3f} type={rec['text_type']}")
        except Exception as e:
            rec["stage"] = "EXCEPTION"
            rec["error"] = repr(e)
            rec["pass"] = False
            summary["fail"] += 1
            print(f"FAIL [exception] {name}: {e!r}")

        out.write(json.dumps(rec) + "\n")
        out.flush()

    out.close()
    print(f"\n=== {summary['pass']} passed / {summary['fail']} failed ===")


if __name__ == "__main__":
    main()
