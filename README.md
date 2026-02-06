# ⚒️ Khazad Voice TTS
**Immersive AI Narrator for The Lord of the Rings Online**

**Khazad Voice TTS** is an external utility designed to provide real-time narration for *The Lord of the Rings Online* (LOTRO). By combining Optical Character Recognition (OCR) with advanced Text-to-Speech (TTS) models, this tool captures quest text from your screen and narrates it aloud using context-aware AI voices.

GPU model demo (LuxTTS)

[![Khazad Voice TTS Showcase](https://img.youtube.com/vi/LlAibQ_TlY4/0.jpg)](https://www.youtube.com/watch?v=LlAibQ_TlY4)

CPU model demo (Kokoro82M)

[![Khazad Voice TTS Showcase](https://img.youtube.com/vi/aR_5aRTrMQg/0.jpg)](https://www.youtube.com/watch?v=aR_5aRTrMQg)


## Key Features

* **Dual AI Engines:**
    * **CPU Mode (Kokoro):** A lightweight, fast inference model compatible with most standard CPUs.
    * **GPU Mode (LuxTTS):** A high-fidelity voice cloning engine for superior audio quality (requires an NVIDIA GPU).
* **Dual Game Support:**
    * Compatible with **Official Servers (Retail)**.
    * Compatible with **Private Servers (Echoes of Angmar/Classic)**.

---

## Prerequisites

Before installing, ensure the following dependencies are set up on your system.

### 1. Tesseract OCR
Required for converting screen captures into text.
* **Download:** [UB-Mannheim Tesseract Wiki](https://github.com/UB-Mannheim/tesseract/wiki) (Download the Windows installer).
* **Installation Path:** The application expects Tesseract to be installed at the default location:
    ```text
    C:\Program Files\Tesseract-OCR\tesseract.exe
    ```
* **Guide:** [How to install Tesseract on Windows](https://linuxhint.com/install-tesseract-windows/)

### 2. getNPCNames Plugin (Retail Mode Only)
Required for Retail mode to identify NPC metadata (Race/Gender) for accurate voice selection.
* **Download:** [Dt192.zip](https://github.com/ils94/LOTROToSpeech/raw/master/Helpful%20Stuffs/Plugins/Dt192.zip) *(Credit: dt192)*
* **Installation:** Extract to your LOTRO Plugins folder.
* **Guide:** [LotroInterface Plugin Installation Guide](https://www.lotrointerface.com/wiki/Install_plugins)

---

## Installation

**Note:** Please ensure you have at least **10GB of free disk space** for dependencies and TTS models.

1.  Clone or download this repository.
2.  Run **`install.bat`**.
3.  Follow the on-screen prompts:
    * The script will verify **Python 3.12** and **Git** installation.
    * Select your GPU architecture (CUDA version) when prompted to ensure the correct PyTorch drivers are downloaded.
    * The script will automatically fetch the required voice models.

---

## Usage & Modes

Run **`start.bat`** to launch the application. You will be prompted to select your Audio Engine (CPU/GPU) and your Game Mode.

### 1. Retail (Live Servers)
*Designed for official game servers.*

* **First startup:** The script will take a screenshot of your primary screen. Draw the box around the quest window as shown in the above video demo's.
* **Trigger:** Automatic (Log-based).
* **Mechanism:**
    1.  Monitors the game's `Script.log` file to detect when an NPC interaction begins.
    2.  Scans the screen for the specific Quest Window icon (e.g., the ring icon).
    3.  If detected, it captures and reads the text automatically.

#### Retail Mode Configuration (Templates)
The `templates/` folder contains reference images for the Quest Window icon.
* **Standard Usage:** The default templates work for most users.
* **Troubleshooting:** If the auto-detection fails (due to resolution or UI skin changes), take a screenshot of the quest icon in your game, save it as a `.png`, and place it in the `templates/` folder.


### 2. Echoes of Angmar (Classic Mode)
*Designed for private servers or clean/custom user interfaces.*

* **First startup:** The script will take a screenshot of your primary screen. Draw one box around the quest window as shown in the above video demo's and one box around the NPC's name as below:
https://github.com/user-attachments/assets/4585b850-6c7e-4614-9131-a703f62d117b


* **Trigger:** Middle Mouse Button Click.
* **Mechanism:** Uses manual screen region detection.
* **First Run Setup:** Upon the first launch, you must draw a bounding box around the **Quest Text** area and the **NPC Name** area on your screen to calibrate the OCR.
* 
## FAQ & Troubleshooting

Q: How do I reset the Quest Window coordinates? If you need to recalibrate the screen region detection, simply delete the `coords_retail.json` file located in the Khazad-Voice-TTS data folder. The application will prompt you to redraw the box on the next launch.

Q: How do I reset the NPC Voice Memory? To wipe the saved voice associations for NPCs (resetting who sounds like what), delete the `npc_memory_retail.json` file from the data folder.

Q: Can I add my own custom voice references? Yes! You can add your own voice samples to the library to be used for cloning/generation. 
1. Navigate to the reference_audio directory. 
2. Open the specific Race and Gender folder you want to customize. 
3. Drop your audio files there. Supported formats: .wav and .flac.

## Future Roadmap
* **Narrator & NPC Voice Splitting**: Intelligent detection to distinguish between spoken dialogue (quoted text) and descriptive text (unquoted). The goal is to use a general "Narrator" voice for descriptions and switch to the specific NPC voice for dialogue within the same window.


* **Configuration UI**: A user-friendly interface to adjust reading speed, audio quality, and emotion settings without editing code.
  * Tip: You can currently adjust these settings manually in config.py (requires restarting the application to take effect).


* **Media Hotkeys**: Global shortcuts to stop the current audio or re-play the previous line.


* **Quest History Plugin**: An in-game LOTRO plugin to display the last ~10 narrated quests, allowing you to "queue" them up and listen to them later (perfect for when you accept multiple quests at once and don't want to stand still).


* **Community Requests**: More features based on your feedback!

---

## Credits

* **LOTROToSpeech by ils94:** Inspired by the original [LOTROToSpeech](https://github.com/ils94/LOTROToSpeech) project.
* **Kokoro:** Powered by the [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) model.
* **LuxTTS:** GPU backend adapted from [LuxTTS](https://github.com/ysharma3501/LuxTTS) by Yatharth Sharma.
