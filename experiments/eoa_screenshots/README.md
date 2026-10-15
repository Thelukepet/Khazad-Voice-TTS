# Echoes of Angmar screenshot eval suite

Full-screen Echoes of Angmar screenshots with the quest window open,
used by `eval/run_eval.py` to measure detection and title-resolution
accuracy for the echoes pipeline.

## Usage

1. Drop full-screen screenshots (quest window fully visible) into this
   folder.
2. Run once to generate the rows:

   ```
   uv run python eval/run_eval.py --shots experiments/eoa_screenshots --mode echoes
   ```

3. Fill in the `expected_title` column in `ground_truth.csv` (the
   in-game quest title). Use `(none)` as the title for screenshots
   where no quest window should be detected.
4. Re-run - it scores every labeled screenshot and exits non-zero when
   any labeled screenshot fails.

Add `--save-crops` to write the extracted title-bar, quest-body and
NPC-name crops to `debug/` for visual inspection.

## Notes

- The echoes pipeline reads the NPC name from the static `npc_box` in
  the calibrated layout (`layout_echoes.json`). Screenshot
  auto-calibration detects the black nameplate box on the screenshot,
  OCRs it and saves it as the `npc_box` automatically. If the
  nameplate is not visible on a screenshot, retry with one where it
  is; users whose UI calibration keeps failing fall back to Static
  Mode.
- Do not move the NPC name box in your UI after calibrating - the
  narrator reads the name from that fixed position. If you move it,
  re-run the calibration.
- The harness OCRs the NPC name (`npc name` row) but does not score it
  against ground truth; a `(nothing read)` row means the nameplate was
  not at the calibrated position on that screenshot (e.g. the box was
  moved after that screenshot was taken).
