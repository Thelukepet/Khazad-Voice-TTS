# Imports

# > Standard Library
from typing import Any, Optional, Tuple

# > Third-party Libraries
import gradio as gr
import numpy as np

# > Local Dependencies
from . import config_manager as cfg
from . import engine_interface as engine
from . import library as lib


def guided_detect_gpu() -> bool:
    """Best-effort GPU detection for the Guided Setup device default."""
    try:
        from . import guided_setup

        return guided_setup.detect_gpu()
    except Exception:
        return False

# --- CONSTANTS ---
SAMPLE_SCRIPTS = [
    "'I will see if I can learn anything from the dwarves here. Mathi Stouthand is the Lord of Gondamon, and he has spoken openly to me in the past. I will judge his conversation to see if he is hiding something.",
    "I cannot believe this, Strider. Can it be true that Saruman commanded these Uruks to attack the folk of Swanfleet? Why would the Wizard wish to do harm to the folk of Mossward? He has ever been a watchful protector of Middle-earth!",
    "'I was walking on the Greenfields, looking for flowers, when I saw a squat, little man off in the distance. He was carrying a spear, and believe me when I tell you that he was a goblin!",
    "I did not dare to speak openly of the reason for Master Elrond's request in my letter, for fear that the message might be intercepted. I apologize for drawing you here with so little information.",
    "As the symbol glows, power courses through you. Authority.",
    "As you look down, you see a glimmering blade hidden behind the barman's hairy hand. It is shining menacingly.",
]
SAMPLE_NAMES = [f"Sample {i + 1}" for i in range(len(SAMPLE_SCRIPTS))]
SCRIPT_MAP = dict(zip(SAMPLE_NAMES, SAMPLE_SCRIPTS))


def create_ui() -> gr.Blocks:
    """
    Builds and returns the Gradio Interface blocks for the Configuration Suite.

    Returns
    -------
    gradio.Blocks
        The constructed Gradio app instance ready to be launched.
    """
    defaults = cfg.get_current_settings()

    with gr.Blocks(
        title="Khazad Configuration", theme=gr.themes.Soft(primary_hue="orange")
    ) as demo:
        gr.Markdown("# ⚒️ Khazad Voice: Configuration Suite")

        tabs = gr.Tabs()

        with tabs:
            # ==================================
            # TAB 1: GUIDED SETUP
            # ==================================
            with gr.Tab("🧭 Guided Setup"):
                gr.Markdown(
                    "### Set up Khazad in three steps\n\n"
                    "1. Test a screenshot from your game. 2. Hear the voice "
                    "the narrator would use. 3. Save volume and speed."
                )

                gr.Markdown("## Step 1: Test a screenshot")
                with gr.Row():
                    with gr.Column():
                        gs_device = gr.Dropdown(
                            choices=["cpu", "gpu"],
                            value="gpu" if guided_detect_gpu() else "cpu",
                            label="Audio engine (GPU = higher quality)",
                        )
                        gs_shot = gr.Image(
                            label="Screenshot (quest window open)", type="numpy"
                        )
                        gs_test_btn = gr.Button("Run Test", variant="primary")
                    with gr.Column():
                        gs_verdict = gr.Markdown("")
                        gs_title_img = gr.Image(label="Extracted title")
                        gs_body_img = gr.Image(label="Extracted text")
                gs_state = gr.State(None)

                gr.Markdown("## Step 2: Hear the voice")
                gs_voice_info = gr.Markdown("*Run the test first.*")
                gs_preview_btn = gr.Button(
                    "Generate voice preview (loads the TTS model on first use)"
                )
                gs_audio = gr.Audio(label="Preview")

                gr.Markdown("## Step 3: Volume & speed")
                with gr.Row():
                    gs_vol = gr.Slider(
                        0.0, 1.0,
                        value=defaults.get("volume", 0.4),
                        label="Volume",
                    )
                    gs_speed = gr.Slider(
                        0.5, 2.0,
                        value=defaults.get("speed", 1.1),
                        label="Speaking speed",
                    )
                gs_save_btn = gr.Button("Save settings", variant="primary")
                gs_save_status = gr.Markdown("")

                def gs_run_test(img, device):
                    if img is None:
                        return "Please upload a screenshot first.", None, None, None
                    from . import screenshot_tester

                    res = screenshot_tester.run_test(img, "retail")
                    return (
                        _format_shot_verdict(res),
                        res["title_crop"],
                        res["body_crop"],
                        res,
                    )

                def gs_preview(state, device):
                    if not state or not state.get("narrated_text"):
                        return (
                            "*Run the test first - the preview speaks the "
                            "matched quest text.*",
                            None,
                        )
                    from . import guided_setup

                    try:
                        voice = guided_setup.resolve_voice(
                            state.get("npc_name", ""), device
                        )
                        rate, wav = guided_setup.generate_snippet(
                            state["narrated_text"], device, voice["voice_id"]
                        )
                        who = voice["matched_name"] or "unknown"
                        info = (
                            f"**Quest giver:** {who} "
                            f"({voice['gender']} {voice['race']})"
                        )
                        return info, (rate, wav)
                    except Exception as e:
                        return (f"*Preview failed: {e}*", None)

                def gs_save(vol, speed):
                    msg, _, _ = cfg.save_settings(
                        vol,
                        defaults.get("omnivoice_volume", 0.4),
                        speed,
                        defaults.get("steps", 16),
                        defaults.get("threshold", 0.5),
                        defaults.get("tesseract", ""),
                        defaults.get("chunk_size", 2),
                    )
                    return (
                        msg
                        + "\n\nSettings saved. To start using the TTS, "
                        "run `start_lotro.bat` (retail) or `start_eoa.bat` "
                        "(Echoes of Angmar) from the Windows folder - or use "
                        "the desktop shortcuts. **Close this Voice Lab "
                        "(terminal and browser tab) first** - while it is "
                        "open, two TTS models would load and the narrator "
                        "falls back to CPU."
                    )

                gs_test_btn.click(
                    gs_run_test,
                    inputs=[gs_shot, gs_device],
                    outputs=[gs_verdict, gs_title_img, gs_body_img, gs_state],
                )
                gs_preview_btn.click(
                    gs_preview,
                    inputs=[gs_state, gs_device],
                    outputs=[gs_voice_info, gs_audio],
                )
                gs_save_btn.click(
                    gs_save,
                    inputs=[gs_vol, gs_speed],
                    outputs=[gs_save_status],
                )

            # ==================================
            # TAB 2: SYSTEM CONFIGURATION
            # ==================================
            with gr.Tab("⚙️ Configuration"):
                gr.Markdown("### 🎛️ Engine Calibration")
                gr.Markdown(
                    "Adjust settings based on your hardware. **GPU users** could lower quality and chunk size to speed up computations."
                )

                with gr.Row():
                    # --- CPU MODE ---
                    with gr.Column(variant="panel"):
                        gr.Markdown("## CPU Mode (Kokoro)")
                        vol_slider = gr.Slider(
                            0.1,
                            1.0,
                            value=defaults.get("volume", 0.4),
                            step=0.1,
                            label="Kokoro Volume",
                            info="Overall loudness",
                        )

                        # Kokoro-Specific Speed Slider (Using the shared TTS_SPEED config variable)
                        # Note: Both engines currently share 'TTS_SPEED' in khazad_config.ini.
                        # If you want them truly separate, we'd need a 'KOKORO_SPEED' config variable.
                        # For now, we assume this slider controls the global speed.
                        speed_slider_conf = gr.Slider(
                            0.5,
                            2.0,
                            value=defaults.get("speed", 1.1),
                            step=0.1,
                            label="TTS Speed",
                            info="Higher = Faster",
                        )

                    # --- GPU MODE ---
                    with gr.Column(variant="panel"):
                        gr.Markdown("## GPU Mode (OmniVoice)")
                        omnivoice_vol_slider = gr.Slider(
                            0.1,
                            1.0,
                            value=defaults.get("omnivoice_volume", 0.4),
                            step=0.1,
                            label="OmniVoice Volume",
                        )

                        # Both engines currently share 'TTS_SPEED' in khazad_config.ini.
                        # The slider in the CPU panel controls the shared speed.

                        gr.Markdown(
                            "*Note: TTS Speed setting (left) applies to OmniVoice as well.*"
                        )

                        steps_slider_conf = gr.Slider(
                            minimum=4,
                            maximum=16,
                            value=defaults.get("steps", 4),
                            step=1,
                            label="Diffusion Quality (Steps)",
                            info="4 = Fastest. 10+ = Best Quality (higher quality takes longer to compute).",
                        )

                        chunk_radio = gr.Radio(
                            choices=["2 (Standard)", "1 (Ultra Fast)"],
                            type="index",
                            value="2 (Standard)"
                            if defaults.get("chunk_size", 2) == 2
                            else "1 (Ultra Fast)",
                            label="Chunk Size",
                            info="Set to '1' if TTS is still taking too long to compute after reducing Diffusion Quality",
                        )

                with gr.Group():
                    gr.Markdown("### 🎭 Narrator Voice (stable voice for non-spoken text)")
                    gr.Markdown(
                        "*Pick the voice that reads quest descriptions and narration. "
                        "It stays the same for every quest, so choose one you like listening to.*"
                    )
                    narrator_files = lib.get_samples_for_category("narrator")
                    current_narrator = defaults.get("narrator_voice_file", "narrator_1.flac")
                    narrator_dropdown = gr.Dropdown(
                        choices=narrator_files if narrator_files else [current_narrator],
                        value=current_narrator if current_narrator in (narrator_files or [current_narrator]) else (narrator_files[0] if narrator_files else current_narrator),
                        label="Narrator Voice File",
                        info="Voice used for narration (voice-mix mode) and unknown NPCs fall back to the narrator pool.",
                        allow_custom_value=True,
                    )

                with gr.Group():
                    gr.Markdown("### Detection & OCR")
                    with gr.Row():
                        tess_input = gr.Textbox(
                            value=defaults.get("tesseract", ""),
                            label="Tesseract Path",
                            info="Full path to tesseract.exe",
                            scale=2,
                        )
                        thresh_slider = gr.Slider(
                            0.3,
                            0.7,
                            value=defaults.get("threshold", 0.5),
                            step=0.05,
                            label="Quest Window Detection Sensitivity",
                            info="Standard: 0.5, reduce if quest window is not recognised all the time in-game",
                            scale=1,
                        )

                save_btn = gr.Button("💾 Save Configuration", variant="primary")
                save_output = gr.Textbox(label="Status", interactive=False)

            # ==================================
            # TAB 3: TTS TESTER
            # ==================================
            with gr.Tab("🎙️ OmniVoice Tester & Custom Voice Adder", id="test_tab"):
                gr.Markdown("### Test Configuration & Add New Voices (OmniVoice Only)")

                mode_radio = gr.Radio(
                    choices=["📂 Use Existing Voice", "📤 Upload New Voice"],
                    value="📂 Use Existing Voice",
                    label="Voice Source",
                    type="value",
                )

                with gr.Row():
                    # LEFT COLUMN: INPUT
                    with gr.Column():
                        # Library Group
                        with gr.Group(visible=True) as grp_library:
                            categories = lib.get_library_categories()
                            default_cat = categories[0] if categories else None

                            lib_category = gr.Dropdown(
                                choices=categories,
                                value=default_cat,
                                label="STEP 1: Pick a voice category",
                                interactive=True,
                            )

                            lib_sample = gr.Dropdown(
                                # Dynamically fill the first one based on the default category
                                choices=lib.get_samples_for_category(default_cat)
                                if default_cat
                                else [],
                                value=next(
                                    iter(lib.get_samples_for_category(default_cat)),
                                    None,
                                )
                                if default_cat
                                else None,
                                label="STEP 2: Select Sample File",
                                interactive=True,
                            )
                            btn_load_lib = gr.Button("Load Voice Data", size="sm")

                        # Upload Group
                        with gr.Group(visible=False) as grp_upload:
                            gr.Markdown(
                                "*Upload a clean voice sample (wav/flac) and make sure the transcript matches the audio.*"
                            )
                            upload_file_btn = gr.File(
                                label="Upload Audio",
                                file_count="single",
                                file_types=[".wav", ".flac", ".mp3"],
                            )

                        # Shared Player & Transcript
                        ref_input = gr.Audio(
                            label="Reference Audio Player",
                            type="filepath",
                            interactive=True,
                        )
                        transcribe_btn = gr.Button(
                            "Auto-Transcribe (Whisper)", size="sm"
                        )
                        ref_text_input = gr.Textbox(
                            label="Transcript (auto-transcripts trimmed to 20s)",
                            lines=2,
                            placeholder="Text matches the audio...",
                        )

                    # RIGHT COLUMN: OUTPUT
                    with gr.Column():
                        target_text_input = gr.Textbox(
                            label="Text to Speak (or type your own)",
                            value=SAMPLE_SCRIPTS[0],
                            lines=2,
                        )
                        example_selector = gr.Dropdown(
                            choices=SAMPLE_NAMES,
                            value=SAMPLE_NAMES[0],
                            label="Load Sample Text",
                        )

                        with gr.Group():
                            gr.Markdown("#### Current Settings (Auto-Applied)")
                            lab_speed = gr.Slider(
                                0.5,
                                2.0,
                                value=defaults.get("speed", 1.1),
                                label="Test Speed",
                            )
                            lab_steps = gr.Slider(
                                4,
                                16,
                                value=defaults.get("steps", 6),
                                step=1,
                                label="Test Steps",
                            )

                        test_btn = gr.Button(
                            "STEP 3: Generate Preview (first generated result will take longer)",
                            variant="primary",
                        )
                        audio_output = gr.Audio(label="Result")
                        status_msg = gr.Markdown("")

                gr.Markdown("### STEP 4: Save to Library")
                with gr.Row():
                    folder_dropdown = gr.Dropdown(
                        choices=lib.get_voice_folders(),
                        label="Category",
                        allow_custom_value=True,
                    )
                    name_input = gr.Textbox(label="Voice Name (e.g. 'high_elf_1')")
                    save_voice_btn = gr.Button("Save Voice")
                save_status = gr.Markdown("")

                # --- EVENTS & LOGIC ---

                # 1. Save Configuration
                def save_wrapper(vol, omnivoice_vol, spd, stp, tess, chk_idx, thresh, narrator_file):
                    real_chunk = 2 if chk_idx == 0 else 1
                    msg, new_speed, new_steps = cfg.save_settings(
                        vol, omnivoice_vol, spd, stp, thresh, tess, real_chunk,
                        narrator_voice_file=(narrator_file or "").strip(),
                    )
                    return (
                        msg + "\n\n🚀 Configuration Saved! Switch tabs to test.",
                        new_speed,
                        new_steps,
                    )

                save_btn.click(
                    save_wrapper,
                    inputs=[
                        vol_slider,
                        omnivoice_vol_slider,
                        speed_slider_conf,
                        steps_slider_conf,
                        tess_input,
                        chunk_radio,
                        thresh_slider,
                        narrator_dropdown,
                    ],
                    outputs=[save_output, lab_speed, lab_steps],
                )

                # 2. UI Toggles
                def toggle_mode(mode):
                    is_lib = mode == "📂 Use Existing Voice"
                    return gr.Group(visible=is_lib), gr.Group(visible=not is_lib)

                mode_radio.change(
                    toggle_mode, inputs=mode_radio, outputs=[grp_library, grp_upload]
                )

                # 3. Library Handling
                def update_samples(cat):
                    choices = lib.get_samples_for_category(cat)
                    initial_value = choices[0] if choices else None
                    return gr.Dropdown(choices=choices, value=initial_value)

                lib_category.change(
                    update_samples, inputs=lib_category, outputs=lib_sample
                )

                def load_from_lib(cat, samp):
                    path, text = lib.load_library_sample(cat, samp)
                    if not path:
                        return None, "Error: File not found."
                    return path, text

                btn_load_lib.click(
                    load_from_lib,
                    inputs=[lib_category, lib_sample],
                    outputs=[ref_input, ref_text_input],
                )
                lib_sample.change(
                    load_from_lib,
                    inputs=[lib_category, lib_sample],
                    outputs=[ref_input, ref_text_input],
                )

                # 4. Upload & Processing
                upload_file_btn.change(
                    lambda f: f, inputs=upload_file_btn, outputs=ref_input
                )
                ref_input.upload(
                    lib.trim_audio, inputs=[ref_input], outputs=[ref_input]
                )

                def run_transcribe(audio):
                    return engine.auto_transcribe(audio, lib.trim_audio)

                transcribe_btn.click(
                    run_transcribe, inputs=[ref_input], outputs=[ref_text_input]
                )

                example_selector.change(
                    lambda x: SCRIPT_MAP[x],
                    inputs=example_selector,
                    outputs=target_text_input,
                )

                # 5. Generation
                def run_gen(text, audio, transcript, spd, steps):
                    try:
                        # audio_data comes as (rate, numpy_array) from engine
                        audio_data = engine.generate_preview(
                            text, audio, transcript, spd, steps, lib.trim_audio
                        )
                        return audio_data, "Generation Successful"
                    except Exception as e:
                        return None, f"Error: {str(e)}"

                test_btn.click(
                    run_gen,
                    inputs=[
                        target_text_input,
                        ref_input,
                        ref_text_input,
                        lab_speed,
                        lab_steps,
                    ],
                    outputs=[audio_output, status_msg],
                )

                def save_and_refresh(ref_audio, folder_name, voice_name, transcript):
                    status = lib.save_voice(
                        ref_audio, folder_name, voice_name, transcript
                    )

                    # Refresh the category dropdown – keep the saved category selected
                    categories = lib.get_library_categories()
                    selected_cat = (
                        folder_name
                        if folder_name in categories
                        else (categories[0] if categories else None)
                    )

                    # Refresh the sample dropdown – auto-select the first sample
                    samples = (
                        lib.get_samples_for_category(selected_cat)
                        if selected_cat
                        else []
                    )
                    selected_sample = samples[0] if samples else None

                    return (
                        status,
                        gr.Dropdown(choices=categories, value=selected_cat),
                        gr.Dropdown(choices=samples, value=selected_sample),
                    )

                save_voice_btn.click(
                    save_and_refresh,
                    inputs=[ref_input, folder_dropdown, name_input, ref_text_input],
                    outputs=[save_status, lib_category, lib_sample],
                )

            # ==================================
            # TAB 4: SCREENSHOT TESTER
            # ==================================
            with gr.Tab("🧪 Screenshot Tester"):
                gr.Markdown(
                    "### Check if the narrator works on your system\n"
                    "Upload a screenshot of your game with a **quest window open**. "
                    "The test runs the same pipeline the narrator uses and shows "
                    "exactly what it would read. **Calibrate** writes the layout "
                    "settings from the same screenshot - no manual box-drawing."
                )
                with gr.Row():
                    with gr.Column():
                        shot_input = gr.Image(
                            label="Screenshot (quest window open)", type="numpy"
                        )
                        shot_mode = gr.Dropdown(
                            choices=["retail", "echoes"],
                            value="retail",
                            label="Game mode",
                        )
                        shot_btn = gr.Button("Run Test", variant="primary")
                        cal_btn = gr.Button(
                            "✨ Calibrate from this screenshot", variant="secondary"
                        )
                    with gr.Column():
                        shot_verdict = gr.Markdown("")
                        shot_title_img = gr.Image(label="Extracted title")
                        shot_body_img = gr.Image(label="Extracted text")

                def run_shot_wrapper(img, mode):
                    if img is None:
                        return "Please upload a screenshot first.", None, None
                    from . import screenshot_tester

                    res = screenshot_tester.run_test(img, mode or "retail")
                    return (
                        _format_shot_verdict(res),
                        res["title_crop"],
                        res["body_crop"],
                    )

                def _format_shot_verdict(res):
                    icons = {
                        "OK": "✅",
                        "NO WINDOW": "❌",
                        "TITLE NOT RECOGNIZED": "⚠️",
                        "BODY NOT MATCHED": "⚠️",
                        "ERROR": "❌",
                    }
                    icon = icons.get(res["verdict"], "❓")
                    lines = [f"## {icon} {res['verdict']}"]
                    if res.get("title_ocr"):
                        lines.append(f"**Title OCR:** `{res['title_ocr']}`")
                    if res.get("resolved_title"):
                        lines.append(f"**Recognized quest:** {res['resolved_title']}")
                    if res.get("body_score") is not None:
                        lines.append(
                            f"**Text match:** {res['body_score']:.0%} "
                            f"({res['text_type']})"
                        )
                    if res.get("player_name"):
                        lines.append(f"**Player name read:** {res['player_name']}")
                    if res.get("npc_name_ocr"):
                        lines.append(
                            f"**NPC name OCR:** `{res['npc_name_ocr']}`"
                        )
                    elif res.get("npc_name_ocr") is not None:
                        lines.append(
                            "**NPC name OCR:** nothing read - check the "
                            "NPC name box calibration"
                        )
                    if res.get("narrated_text"):
                        preview = res["narrated_text"]
                        if len(preview) > 400:
                            preview = preview[:400] + "..."
                        lines.append(f"**The narrator would say:**\n\n> {preview}")
                    if res.get("error"):
                        lines.append(f"\n*{res['error']}*")
                    return "\n".join(lines)

                def run_calibration(img, mode):
                    """Auto-calibrate the layout from the uploaded screenshot."""
                    if img is None:
                        return "Please upload a screenshot first.", None, None
                    import cv2

                    from src.auto_calibrate import auto_calibrate

                    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                    ok, rep = auto_calibrate(img_bgr, mode or "retail")
                    if not ok:
                        return f"## ❌ Calibration failed\n\n{rep['message']}", None, None

                    score_rows = "\n".join(
                        f"- {key}: {a['score']:.0%}"
                        for key, a in rep["anchors"].items()
                    )
                    msg = (
                        f"## ✅ Calibration saved\n\n{rep['message']}\n\n"
                        f"**Anchor match scores:**\n\n{score_rows}"
                    )
                    return msg, None, None

                shot_btn.click(
                    run_shot_wrapper,
                    inputs=[shot_input, shot_mode],
                    outputs=[shot_verdict, shot_title_img, shot_body_img],
                )
                cal_btn.click(
                    run_calibration,
                    inputs=[shot_input, shot_mode],
                    outputs=[shot_verdict, shot_title_img, shot_body_img],
                )

    return demo
