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
* **Resolution Independent:**
    * Includes a **Calibration Tool** that creates a digital fingerprint of your UI.
    * Works on **1080p, 1440p, 4K**, and Ultrawide monitors.
    * Supports dynamic window resizing (you can widen/shorten the quest window and the bot adapts automatically).
* **Dual Game Support:**
    * Compatible with **Official Servers (Retail)** via automatic detection.
    * Compatible with **Private Servers (Echoes of Angmar/Classic)** via manual selection.

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

## Configuration & Calibration (Important)

Before running the bot for the first time, you must calibrate it to your screen resolution and UI layout.

1.  Open LOTRO and log in.
2.  **Open any Quest Window** by clicking on an NPC. Ensure the window is fully visible.
3.  Double-click **`calibrate.bat`** in the project folder.
4.  Follow the on-screen visual guide. You will be asked to draw boxes around 5 specific anchors:
    * **Step 1 & 2:** The Left and Right Leaf icons (Title Bar).
    * **Step 3:** The Top-Left corner of the text body.
    * **Step 4:** The intersection between the left and right panels (defines width).
    * **Step 5:** The Filter icon at the bottom (defines height).
    * **Step 6:** A confirmation box around the actual text.

Follow my YouTube video for a detailed guide on how to draw these boxes accurately:

[![Khazad Voice TTS Calibration Tutorial](https://img.youtube.com/vi/6otQUGYiFx4/0.jpg)](https://www.youtube.com/watch?v=6otQUGYiFx4)


Once finished, the bot will save a `user_layout.json` file. You generally only need to do this once, unless you change your UI skin or game resolution.

---

## Usage & Modes

Run **`start.bat`** to launch the application.

### 1. Retail (Live Servers)
*Designed for official game servers.*

* **Trigger:** Automatic (Log-based).
* **Mechanism:**
    1.  Monitors the game's `Script.log` file to detect when an NPC interaction begins.
    2.  Uses your **Calibration Data** to instantly locate the quest window.
    3.  Captures and reads the text automatically.
* **Note:** Because this uses the calibration data, you are free to move and resize the quest window in-game; the bot will adapt dynamically.

### 2. Echoes of Angmar (Classic Mode)
*Designed for private servers or clean/custom user interfaces.*

* **Trigger:** Middle Mouse Button Click.
* **Mechanism:** Uses manual screen region detection.
* **First Run Setup:** Upon the first launch, the bot will take a screenshot. You must draw:
    1.  A bounding box around the **Quest Text** area.
    2.  A bounding box around the **NPC Name** area.
    *(See the demo images above for reference).*

---

## FAQ & Troubleshooting

**Q: The bot isn't detecting the quest window in Retail mode.**
A: Run **`calibrate.bat`** again. Ensure you draw tight boxes around the requested icons. If you change your game resolution or apply a custom UI skin, you must recalibrate.

**Q: How do I reset the NPC Voice Memory?**
A: To wipe the saved voice associations for NPCs (resetting who sounds like what), delete the `npc_memory_retail.json` file from the `data/` folder.

**Q: Can I add my own custom voice references?**
A: Yes! You can add your own voice samples to the library to be used for cloning/generation.
1.  Navigate to the `data/reference_audio` directory.
2.  Open the specific Race and Gender folder you want to customize.
3.  Drop your audio files there. Supported formats: `.wav` and `.flac`.

---

## Future Roadmap

* **Narrator & NPC Voice Splitting**: Intelligent detection to distinguish between spoken dialogue (quoted text) and descriptive text (unquoted).
* **Configuration UI**: A user-friendly interface to adjust reading speed, audio quality, and emotion settings without editing code.
* **Media Hotkeys**: Global shortcuts to stop the current audio or re-play the previous line.
* **Quest History Plugin**: An in-game LOTRO plugin to display the last ~10 narrated quests.

---

## Credits

* **LOTROToSpeech by ils94:** Inspired by the original [LOTROToSpeech](https://github.com/ils94/LOTROToSpeech) project.
* **Kokoro:** Powered by the [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) model.
* **LuxTTS:** GPU backend adapted from [LuxTTS](https://github.com/ysharma3501/LuxTTS) by Yatharth Sharma.