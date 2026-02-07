# Imports

# > Standard Library
import time
import queue
import threading

# > Third Party Dependencies
import cv2
import nltk

# > Local Dependencies
from .utils import setup_logger, save_npc_memory, load_npc_memory, extract_quest_areas
from .ocr import run_ocr, run_name_ocr, run_title_ocr
from .audio import play_audio
from .config import DEFAULT_VOLUME, ENABLE_WIKI  # <--- Import Flag
from . import wiki

log = setup_logger("ENGINE")


class NarratorEngine:
    """
    Core engine that orchestrates the workflow between OCR, Database lookups,
    Wiki fetching, and Text-to-Speech generation.

    Attributes
    ----------
    db : Database
        The NPC database interface for race/gender lookups.
    tts : TTSBackend
        The initialized Text-to-Speech backend (e.g., Kokoro, Lux).
    mode : str
        The operation mode ('echoes' for manual, 'retail' for auto).
    memory : dict
        A runtime cache of NPC-to-Voice mappings to ensure consistency.
    audio_queue : queue.Queue
        A thread-safe queue for buffering generated audio chunks.
    is_playing : bool
        Flag to track playback state.
    """

    def __init__(self, db, tts_backend, mode="echoes"):
        """
        Initializes the NarratorEngine.

        Parameters
        ----------
        db : Database
            Instance of the database handler.
        tts_backend : TTSBackend
            Instance of the TTS model wrapper.
        mode : str, optional
            The game mode configuration, by default "echoes".
        """
        self.db = db
        self.tts = tts_backend
        self.mode = mode
        self.memory = load_npc_memory(self.mode)
        log.info(f"🧠 Loaded Memory for mode: {self.mode}")
        self.audio_queue = queue.Queue()
        self.is_playing = False

    def process_capture(self, quest_img_pil, name_img_pil):
        """
        Handles the 'Echoes' (Classic) mode workflow, which relies on manual
        screen region selection.

        Parameters
        ----------
        quest_img_pil : PIL.Image.Image
            The cropped image containing the quest body text.
        name_img_pil : PIL.Image.Image
            The cropped image containing the NPC name.
        """
        # ECHOES MODE (Manual)
        log.info("Reading Quest Text...")
        sentences = run_ocr(quest_img_pil)
        if not sentences:
            log.warning("No quest text found.")
            return
        log.info("Reading NPC Name...")
        npc_name = run_name_ocr(name_img_pil) or "Unknown"
        log.info(f"📝 NPC Name: '{npc_name}'")
        voice_id = self._resolve_voice(npc_name)
        self._start_streaming(sentences, voice_id)

    def process_retail(self, _, full_screen_np, npc_name):
        """
        Handles the 'Retail' (Live) mode workflow, which uses automatic detection
        via calibration anchors and log monitoring.

        1. Extracts Title/Body using calibrated layout.
        2. Runs OCR on the extracted areas.
        3. (Optional) Fetches cleaned text from the Wiki to fix OCR errors.
        4. Queues text for TTS.

        Parameters
        ----------
        _ : Any
            Legacy/unused parameter (placeholder for raw quest crop).
        full_screen_np : np.ndarray
            The full screenshot in NumPy format (BGR).
        npc_name : str
            The name of the NPC detected from the game logs.
        """
        # RETAIL MODE (Auto)
        log.info(f"Detecting Quest Window for: {npc_name}...")

        # 1. Extraction
        title_pil, body_pil = extract_quest_areas(full_screen_np)

        if not title_pil or not body_pil:
            log.info("🙈 NPC in log, but valid Quest Window not found.")
            return

        # 2. OCR Body (Always needed for fallback/reference)
        ocr_sentences = run_ocr(body_pil)
        if not ocr_sentences:
            log.warning("Quest body OCR empty.")
            return

        full_ocr_text = " ".join(ocr_sentences)
        final_text = full_ocr_text
        source_label = "OCR (Default)"

        # 3. Wiki Logic (Conditional)
        if ENABLE_WIKI:
            # OCR Title only if we need Wiki
            quest_title = run_title_ocr(title_pil)
            log.info(f"📜 Quest Title: '{quest_title}'")
            log.info("🌍 Checking Wiki...")

            wiki_url = wiki.get_best_wiki_url(quest_title)
            stages = wiki.fetch_quest_data(wiki_url)

            if stages:
                best_stage, matched_text, accuracy = wiki.get_best_match(
                    full_ocr_text, stages
                )

                # Smart Fallback Logic
                if accuracy >= 50.0 and not wiki.has_name_placeholder(matched_text):
                    final_text = matched_text
                    source_label = f"Wiki ({best_stage}, {accuracy:.1f}%)"
                elif wiki.has_name_placeholder(matched_text):
                    source_label = "OCR (Wiki had placeholder)"
                else:
                    source_label = f"OCR (Low Wiki Acc: {accuracy:.1f}%)"
            else:
                source_label = "OCR (No Wiki Data)"
        else:
            log.info("⏩ Skipping Wiki Lookup (Config Disabled)")

        log.info(f"✅ Source: {source_label}")

        # 4. Playback
        voice_id = self._resolve_voice(npc_name)
        final_sentences = nltk.sent_tokenize(final_text)
        self._start_streaming(final_sentences, voice_id)

    def _resolve_voice(self, npc_name: str) -> str:
        """
        Determines the appropriate Voice ID for a given NPC.

        Logic:
        1. Check memory cache.
        2. If new, look up Race/Gender in DB.
        3. If unknown, default to 'Narrator'.
        4. Select a random consistent voice based on tags.
        5. Save to memory.

        Parameters
        ----------
        npc_name : str
            The name of the NPC.

        Returns
        -------
        str
            The specific voice ID (e.g., 'en_us_male_1') to be used by the TTS.
        """
        key = npc_name.lower()
        if key in self.memory:
            return self.memory[key]["voice_id"]

        gender, race, matched_name = self.db.lookup(npc_name)
        if not gender or not race:
            matched_name = "Narrator"
            race, gender = "Narrator", "Narrator"

        voice_id, category = self.tts.pick_voice(gender, race)
        self.memory[key] = {
            "name": matched_name,
            "race": race,
            "gender": gender,
            "voice_id": voice_id,
        }
        save_npc_memory(self.memory, self.mode)
        return voice_id

    def _start_streaming(self, sentences: list[str], voice_id: str):
        """
        Starts the audio generation and playback pipeline.

        Uses a Producer-Consumer model:
        - The Producer (Thread) generates audio using the TTS model.
        - The Consumer (Main Loop) pulls audio from the queue and plays it.

        Parameters
        ----------
        sentences : list[str]
            A list of text sentences to narrate.
        voice_id : str
            The target voice ID for synthesis.
        """
        def producer():
            clean_lines = [s.strip() for s in sentences if s.strip()]
            if type(self.tts).__name__ == "LuxBackend":
                chunk_size = 2
                for i in range(0, len(clean_lines), chunk_size):
                    batch = clean_lines[i : i + chunk_size]
                    full_text = " ".join(batch)
                    if full_text:
                        audio = self.tts.generate(full_text, voice_id)
                        self.audio_queue.put((full_text, audio, self.tts.samplerate))
            else:
                for line in clean_lines:
                    audio = self.tts.generate(line, voice_id)
                    self.audio_queue.put((line, audio, self.tts.samplerate))
            self.audio_queue.put(None)

        threading.Thread(target=producer, daemon=True).start()

        print("\n--- 🟢 PLAYBACK STARTED ---")
        while True:
            item = self.audio_queue.get()
            if item is None:
                break
            text, audio, sr = item
            print(f"▶️ Speaking: {text[:60]}...")
            if len(audio) > 0:
                play_audio(audio, sr, volume=DEFAULT_VOLUME)
                time.sleep(0.1)
        print("--- 🔴 PLAYBACK ENDED ---\n")
