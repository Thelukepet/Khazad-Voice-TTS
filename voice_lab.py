# Imports

# > Standard Library
import os
import sys
import shutil
import traceback
import tempfile
from pathlib import Path

# > Third-Party Dependencies
import torch
import gradio as gr
import soundfile as sf
import numpy as np

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "data" / "reference_audio"
LUX_PATH = BASE_DIR / "LuxTTS"

# Add LuxTTS to Python Path
if LUX_PATH.exists() and str(LUX_PATH) not in sys.path:
    sys.path.append(str(LUX_PATH))

# --- SAMPLE TEXTS ---
SAMPLE_SCRIPTS = [
    "'I will see if I can learn anything from the dwarves here. Mathi Stouthand is the Lord of Gondamon, and he has spoken openly to me in the past. I will judge his conversation to see if he is hiding something.",
    "I cannot believe this, Strider. Can it be true that Saruman commanded these Uruks to attack the folk of Swanfleet? Why would the Wizard wish to do harm to the folk of Mossward? He has ever been a watchful protector of Middle-earth! What can have changed?",
    "'I was walking on the Greenfields, looking for flowers, when I saw a squat, little man off in the distance. He was carrying a spear, and believe me when I tell you that he was a goblin! All of a sudden he dropped to the ground, and it looked to me like he was reaching into a hole of some kind...a rabbit hole most likely.",
    "I did not dare to speak openly of the reason for Master Elrond's request in my letter, for fear that the message might be intercepted. I apologize for drawing you here with so little information, but Master Elrond will explain in detail what I could not."
]

# Create a mapping for the dropdown: "Sample 1" -> Text
SAMPLE_NAMES = [f"Sample {i + 1}" for i in range(len(SAMPLE_SCRIPTS))]
SCRIPT_MAP = dict(zip(SAMPLE_NAMES, SAMPLE_SCRIPTS))

# --- LOAD WHISPER (LAZY LOADING) ---
whisper_model = None


def load_whisper():
    """
    Loads the Whisper model (Base) for transcription.
    Uses CPU to preserve VRAM for LuxTTS.

    Returns
    -------
    whisper.model.Whisper
        The loaded Whisper model.
    """
    global whisper_model
    if whisper_model is None:
        print("Loading Whisper (Base)...")
        import whisper
        whisper_model = whisper.load_model("base", device="cpu")
    return whisper_model


# --- LOAD LUXTTS ---
tts = None
try:
    from zipvoice.luxvoice import LuxTTS
except ImportError:
    try:
        from LuxTTS.zipvoice.luxvoice import LuxTTS
    except ImportError:
        print("[CRITICAL] LuxTTS Import Failed. Ensure dependencies are installed.")
        sys.exit(1)

# Initialize Model
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Initializing LuxTTS on {device}...")

try:
    tts = LuxTTS("YatharthS/LuxTTS", device=device)
    print("Model Ready.")
except Exception as e:
    print(f"Model Initialization Failed: {e}")
    sys.exit(1)


def get_voice_folders():
    """
    Retrieves a list of available voice category folders.

    Returns
    -------
    list[str]
        List of folder names found in data/reference_audio.
    """
    if not AUDIO_DIR.exists():
        return []
    return [d.name for d in AUDIO_DIR.iterdir() if d.is_dir()]


def trim_audio(audio_path, max_duration=20.0):
    """
    Checks audio duration and trims it if it exceeds the limit.
    This ensures Whisper and LuxTTS only process the start of the file.

    Parameters
    ----------
    audio_path : str
        Path to the audio file.
    max_duration : float
        Maximum allowed duration in seconds.

    Returns
    -------
    str
        Path to the original or trimmed audio file.
    """
    if not audio_path:
        return None

    try:
        data, sr = sf.read(audio_path)
        duration = len(data) / sr

        if duration > max_duration:
            print(f"Trimming audio from {duration:.2f}s to {max_duration}s")
            max_samples = int(max_duration * sr)
            trimmed_data = data[:max_samples]

            # Create a safe temp file (Windows compatible)
            fd, tmp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)  # Close file descriptor immediately

            sf.write(tmp_path, trimmed_data, sr)
            return tmp_path

        return audio_path

    except Exception as e:
        print(f"Warning during audio trim: {e}")
        return audio_path


def auto_transcribe(audio_path):
    """
    Transcribes the audio file using OpenAI Whisper.
    Automatically trims audio to 20s before processing.

    Parameters
    ----------
    audio_path : str
        Path to the audio file.

    Returns
    -------
    str
        The transcribed text, or an error message.
    """
    if not audio_path:
        return ""
    try:
        # Ensure we only transcribe the first 20s
        processed_path = trim_audio(audio_path)

        model = load_whisper()
        result = model.transcribe(processed_path)
        return result["text"].strip()
    except Exception as e:
        return f"[Error: {e}]"


def read_text_file(file_obj):
    """
    Reads the content of an uploaded text file.

    Parameters
    ----------
    file_obj : file-like object
        The uploaded file object from Gradio.

    Returns
    -------
    str
        The content of the file.
    """
    if not file_obj:
        return ""
    try:
        path = file_obj.name if hasattr(file_obj, 'name') else file_obj
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        return f"Error reading file: {e}"


def get_script_content(label_name):
    """
    Helper to fetch the script text based on the dropdown label.
    """
    return SCRIPT_MAP.get(label_name, "")


def generate_preview(target_text, ref_audio, ref_transcript, speed):
    """
    Generates a speech preview using the LuxTTS engine.
    Enforces duration limits (2s - 20s).

    Parameters
    ----------
    target_text : str
        The text to be spoken by the AI.
    ref_audio : str
        Path to the reference audio file.
    ref_transcript : str
        The transcript of what is spoken in the reference audio.
    speed : float
        The speed multiplier for the generated speech.

    Returns
    -------
    tuple
        (sample_rate, numpy_array) for audio playback.
    str
        Status message.
    """
    if not ref_audio:
        raise gr.Error("Please upload a reference voice file.")
    if not ref_transcript or len(ref_transcript.strip()) < 2:
        raise gr.Error("Reference Transcript is empty.")

    try:
        # 1. Enforce Trim (Safe redundancy)
        use_path = trim_audio(ref_audio)

        # 2. Check Min Duration
        data, sr = sf.read(use_path)
        duration = len(data) / sr

        if duration < 2.0:
            raise gr.Error(f"Audio is too short ({duration:.2f}s). Must be > 2.0 seconds.")

        # 3. Encode Prompt
        duration_ms = int(duration * 1000)
        encoded_prompt = tts.encode_prompt(
            use_path,
            text=ref_transcript,
            rms=0.01,
            duration=duration_ms
        )

        # 4. Generate Speech
        generated_wav = tts.generate_speech(
            target_text,
            encoded_prompt,
            speed=speed,
            num_steps=10,
            t_shift=0.9
        )

        # 5. Process Output
        if hasattr(generated_wav, "detach"):
            generated_wav = generated_wav.detach().cpu().numpy().squeeze()
        else:
            generated_wav = generated_wav.numpy().squeeze()

        if generated_wav.size < 100:
            raise gr.Error("Generation result was empty.")

        return (48000, generated_wav), "Generation Successful"

    except RuntimeError as re:
        if "Kernel size" in str(re):
            raise gr.Error("Audio alignment failed. Ensure transcript matches audio exactly.")
        raise gr.Error(f"Runtime Error: {re}")
    except Exception as e:
        traceback.print_exc()
        raise gr.Error(f"Error: {str(e)}")


def save_voice(ref_audio, folder_name, voice_name, transcript):
    """
    Saves the reference audio and its transcript to the project library.

    Parameters
    ----------
    ref_audio : str
        Path to the source audio file.
    folder_name : str
        Name of the target category folder (e.g., 'dwarf_male').
    voice_name : str
        Name for the new voice.
    transcript : str
        The transcript text to save.

    Returns
    -------
    str
        Status message indicating success or failure.
    """
    if not ref_audio or not voice_name or not folder_name:
        return "Missing information."

    clean_name = "".join(c for c in voice_name if c.isalnum() or c in (' ', '_', '-')).strip()
    clean_name = clean_name.replace(" ", "_").lower()

    target_dir = AUDIO_DIR / folder_name

    wav_path = target_dir / f"{clean_name}.wav"
    txt_path = target_dir / f"{clean_name}.txt"

    try:
        os.makedirs(target_dir, exist_ok=True)

        # Save Audio
        shutil.copy(ref_audio, wav_path)

        # Save Transcript
        if transcript and len(transcript.strip()) > 0:
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(transcript)
            return f"Saved Audio & Text to: {folder_name}/{clean_name}"
        else:
            return f"Saved Audio (No Text) to: {folder_name}/{clean_name}.wav"

    except Exception as e:
        return f"Save Failed: {str(e)}"


# --- GRADIO UI ---
with gr.Blocks(title="Khazad Voice Sample Lab") as demo:
    gr.Markdown("# Khazad Voice Lab")

    with gr.Row():
        gr.Markdown(
            """
            ### Instructions for Best Results
            1. **Duration:** Audio must be longer than **2 seconds**. Ideally between **10-20 seconds**.
               *(Audio longer than 20 seconds will be automatically trimmed on upload)*
            2. **Language:** Works best with **English** audio.
            3. **Transcription:** Use Auto-Transcribe to retrieve the text from your audio sample or upload a .txt file with the text.
            4. **Quality:** Ensure audio is clear and has **no background noise**. Audio with long pauses will also result in outputs with long pauses.
            5. **Output:** <ins> Don't expect perfect voice-cloning, we are using a relatively small model for voice cloning </ins> ;)
            """
        )

    with gr.Row():
        # LEFT COLUMN
        with gr.Column(scale=1):
            gr.Markdown("### 1. Audio & Transcript")
            ref_input = gr.Audio(label="Reference Sample", type="filepath")

            with gr.Row():
                transcribe_btn = gr.Button("Auto-Transcribe", size="sm")
                upload_txt_btn = gr.UploadButton("Upload .txt", file_types=[".txt"], size="sm")

            ref_text_input = gr.Textbox(
                label="Transcript",
                lines=3,
                placeholder="The text must match the spoken audio exactly..."
            )

            gr.Markdown("### 2. Generate Preview")

            # --- DROPDOWN WITH MAPPING ---
            example_selector = gr.Dropdown(
                choices=SAMPLE_NAMES,  # Shows "Sample 1", "Sample 2" etc.
                value=SAMPLE_NAMES[0],  # Selects "Sample 1" by default
                label="Select Default Script",
                interactive=True
            )

            target_text_input = gr.Textbox(
                label="Text to Generate",
                value=SAMPLE_SCRIPTS[0],  # Fills text for "Sample 1" by default
                lines=3
            )

            speed_slider = gr.Slider(0.5, 1.5, 1.0, 0.1, label="Speed")
            test_btn = gr.Button("Generate", variant="primary")
            audio_output = gr.Audio(label="Result")
            status_msg = gr.Markdown("")

        # RIGHT COLUMN
        with gr.Column(scale=1):
            gr.Markdown("### 3. Save to Library")
            valid_folders = get_voice_folders()
            folder_dropdown = gr.Dropdown(choices=valid_folders, label="Category")
            name_input = gr.Textbox(label="Voice Name")

            save_btn = gr.Button("Save Voice")
            save_status = gr.Markdown("")

    # --- EVENT WIRING ---

    # 1. Trimming on Upload
    ref_input.upload(trim_audio, inputs=[ref_input], outputs=[ref_input])

    # 2. Transcription
    transcribe_btn.click(auto_transcribe, inputs=[ref_input], outputs=[ref_text_input])

    # 3. File Upload
    upload_txt_btn.upload(read_text_file, inputs=[upload_txt_btn], outputs=[ref_text_input])

    # 4. Dropdown Update (Using helper function to map name -> text)
    example_selector.change(
        fn=get_script_content,
        inputs=example_selector,
        outputs=target_text_input
    )

    # 5. Generation
    test_btn.click(
        generate_preview,
        inputs=[target_text_input, ref_input, ref_text_input, speed_slider],
        outputs=[audio_output, status_msg]
    )

    # 6. Save
    save_btn.click(
        save_voice,
        inputs=[ref_input, folder_dropdown, name_input, ref_text_input],
        outputs=[save_status]
    )

if __name__ == "__main__":
    demo.launch(inbrowser=True)