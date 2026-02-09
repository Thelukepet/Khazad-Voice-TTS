# Imports

# > Standard Library
import os
import sys
import shutil
import traceback
from pathlib import Path

# > Third-Party Dependencies
import torch
import gradio as gr

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "data" / "reference_audio"
LUX_PATH = BASE_DIR / "LuxTTS"

# --- FIX: ADD LUXTTS TO PYTHON PATH ---
# This tells Python: "Look inside the LuxTTS folder for code"
if LUX_PATH.exists() and str(LUX_PATH) not in sys.path:
    sys.path.append(str(LUX_PATH))

# --- LOAD MODEL ---
print("Loading LuxTTS (this may take a moment)...")
try:
    # Try the standard import (works if path is correct)
    from zipvoice.luxvoice import LuxTTS
except ImportError:
    try:
        # Fallback for nested structures
        from LuxTTS.zipvoice.luxvoice import LuxTTS
    except ImportError as e:
        print(f"\nCRITICAL ERROR: Could not import LuxTTS.")
        print(f"   Checked path: {LUX_PATH}")
        print(f"   Python Error: {e}")
        print("   Make sure you ran 'install.bat' successfully.\n")
        input("Press Enter to exit...")
        sys.exit(1)

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Library Found. Initializing on {device}...")

# Initialize Model
tts = LuxTTS("YatharthS/LuxTTS", device=device)
print("Model Ready!")


def get_voice_folders():
    """
    Scans data/reference_audio to find valid race_gender folders.

    Returns
    -------
    list[str]
        A list of directory names representing voice categories.
    """
    if not AUDIO_DIR.exists():
        return []
    # Filter for directories that look like 'race_gender'
    return [d.name for d in AUDIO_DIR.iterdir() if d.is_dir()]


def generate_preview(text, ref_audio, speed):
    """
    Generates audio using the uploaded reference file.

    Parameters
    ----------
    text : str
        The text to synthesize.
    ref_audio : str
        The file path to the reference audio (wav/mp3).
    speed : float
        The playback speed multiplier.

    Returns
    -------
    tuple
        A tuple containing (sample_rate, audio_numpy_array) for Gradio,
        and a status string.
    """
    if not ref_audio:
        return None, "Please upload a reference voice first."

    try:
        # 1. Encode the prompt (extract voice style)
        # Using specific parameters for consistent quality
        encoded_prompt = tts.encode_prompt(
            ref_audio,
            text="Warmup text",  # Dummy text for style extraction
            rms=0.01,
            duration=5  # Look at 5 seconds of audio
        )

        # 2. Generate Speech
        generated_wav = tts.generate_speech(
            text,
            encoded_prompt,
            speed=speed,
            num_steps=10,  # Higher steps = better quality
            t_shift=0.9
        )

        # 3. Convert Tensor to Numpy for Gradio
        if hasattr(generated_wav, "detach"):
            generated_wav = generated_wav.detach().cpu().numpy().squeeze()
        else:
            generated_wav = generated_wav.numpy().squeeze()

        # LuxTTS typically outputs 48kHz
        return (48000, generated_wav), "Generation Successful"

    except Exception as e:
        # Print full error to console for debugging
        traceback.print_exc()
        return None, f"Error: {str(e)}"


def save_voice(ref_audio, folder_name, voice_name):
    """
    Copies the verified reference audio to the selected directory.

    Parameters
    ----------
    ref_audio : str
        The source path of the reference audio file.
    folder_name : str
        The target sub-directory name (e.g., 'dwarf_male').
    voice_name : str
        The user-defined name for the voice.

    Returns
    -------
    str
        A status message indicating success or failure.
    """
    if not ref_audio:
        return "No audio file to save."
    if not voice_name:
        return "Please give the voice a name."

    # Clean up filename (remove weird characters)
    clean_name = "".join(c for c in voice_name if c.isalnum() or c in (' ', '_', '-')).strip()
    clean_name = clean_name.replace(" ", "_").lower()

    target_dir = AUDIO_DIR / folder_name
    target_path = target_dir / f"{clean_name}.wav"

    try:
        os.makedirs(target_dir, exist_ok=True)
        # Copy the uploaded file to the destination
        shutil.copy(ref_audio, target_path)
        return f"Saved! Voice added to: {folder_name}/{clean_name}.wav"
    except Exception as e:
        return f"Save Failed: {str(e)}"


# --- GRADIO UI ---
with gr.Blocks(title="Khazad Voice Lab", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Khazad Voice Lab")
    gr.Markdown("Test new voice samples and add them to your Narrator library.")

    with gr.Row():
        # LEFT COLUMN: INPUTS
        with gr.Column(scale=1):
            gr.Markdown("### 1. Upload & Test")

            ref_input = gr.Audio(
                label="Reference Voice (WAV/MP3)",
                type="filepath"
            )

            text_input = gr.Textbox(
                label="Test Sentence",
                value="Baruk Khazad! The dwarves are upon you!",
                lines=2
            )

            speed_slider = gr.Slider(
                minimum=0.5, maximum=1.5, value=1.0, step=0.1,
                label="Speaking Speed"
            )

            test_btn = gr.Button("Generate Preview", variant="primary")

            # OUTPUT
            audio_output = gr.Audio(label="Generated Result")
            status_msg = gr.Markdown("")

        # RIGHT COLUMN: SAVE
        with gr.Column(scale=1):
            gr.Markdown("### 2. Save to Library")
            gr.Markdown("If you like the result, save the **original reference file** to your game data.")

            # Dynamic dropdown based on actual folders found
            valid_folders = get_voice_folders()

            folder_dropdown = gr.Dropdown(
                choices=valid_folders,
                value=valid_folders[0] if valid_folders else None,
                label="Category (Race & Gender)"
            )

            name_input = gr.Textbox(
                label="Voice Name",
                placeholder="e.g. angry_dwarf_leader"
            )

            save_btn = gr.Button("Save Voice to Library")
            save_status = gr.Markdown("")

    # --- WIRING ---
    test_btn.click(
        generate_preview,
        inputs=[text_input, ref_input, speed_slider],
        outputs=[audio_output, status_msg]
    )

    save_btn.click(
        save_voice,
        inputs=[ref_input, folder_dropdown, name_input],
        outputs=[save_status]
    )

if __name__ == "__main__":
    demo.launch(inbrowser=True)