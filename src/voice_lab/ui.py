# Imports

# > Standard Library
from typing import Tuple, Optional, Any

# > Third-party Libraries
import gradio as gr
import numpy as np

# > Local Dependencies
from . import config_manager as cfg
from . import library as lib
from . import engine_interface as engine

# --- CONSTANTS ---
SAMPLE_SCRIPTS = [
    "'I will see if I can learn anything from the dwarves here. Mathi Stouthand is the Lord of Gondamon, and he has spoken openly to me in the past. I will judge his conversation to see if he is hiding something.",
    "I cannot believe this, Strider. Can it be true that Saruman commanded these Uruks to attack the folk of Swanfleet? Why would the Wizard wish to do harm to the folk of Mossward? He has ever been a watchful protector of Middle-earth!",
    "'I was walking on the Greenfields, looking for flowers, when I saw a squat, little man off in the distance. He was carrying a spear, and believe me when I tell you that he was a goblin!",
    "I did not dare to speak openly of the reason for Master Elrond's request in my letter, for fear that the message might be intercepted. I apologize for drawing you here with so little information.",
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
            # TAB 1: SYSTEM CONFIGURATION
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
                        # Note: Both engines currently share 'TTS_SPEED' in config.py.
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
                        gr.Markdown("## GPU Mode (LuxTTS)")
                        lux_vol_slider = gr.Slider(
                            0.1,
                            1.0,
                            value=defaults.get("lux_volume", 0.4),
                            step=0.1,
                            label="Lux Volume",
                        )

                        # Note: We display the SAME speed slider here visually if they share the underlying config.
                        # Or, if you want Lux to have a different speed, we reuse the same 'TTS_SPEED' logic.
                        # To avoid confusion in the UI, usually one master speed slider is better unless they differ.
                        # However, based on your request, I will place speed controls here too, but they will update the same 'TTS_SPEED'.

                        gr.Markdown(
                            "*Note: TTS Speed setting (left) applies to LuxTTS as well.*"
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
            # TAB 2: TTS TESTER
            # ==================================
            with gr.Tab("🎙️ LuxTTS Tester & Custom Voice Adder", id="test_tab"):
                gr.Markdown("### Test Configuration & Add New Voices (LuxTTS Only)")

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
                            lib_category = gr.Dropdown(
                                choices=lib.get_library_categories(),
                                label="STEP 1: Pick a voice category",
                                interactive=True,
                            )
                            lib_sample = gr.Dropdown(
                                choices=[], label="STEP 2: Select Sample File", interactive=True
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

                        test_btn = gr.Button("STEP 3: Generate Preview (first generated result will take longer)", variant="primary")
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
                def save_wrapper(vol, lux_vol, spd, stp, tess, chk_idx, thresh):
                    real_chunk = 2 if chk_idx == 0 else 1
                    msg, new_speed, new_steps = cfg.save_settings(
                        vol, lux_vol, spd, stp, thresh, tess, real_chunk
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
                        lux_vol_slider,
                        speed_slider_conf,
                        steps_slider_conf,
                        tess_input,
                        chunk_radio,
                        thresh_slider,
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
                    return gr.Dropdown(
                        choices=lib.get_samples_for_category(cat), value=None
                    )

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

                save_voice_btn.click(
                    lib.save_voice,
                    inputs=[ref_input, folder_dropdown, name_input, ref_text_input],
                    outputs=[save_status],
                )

    return demo
