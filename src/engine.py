# Imports

# > Standard Library
import queue
import threading
import time
from datetime import datetime

# > Third Party Dependencies
import cv2
import nltk

from .audio import play_audio, stop_audio
from .models import NPC, QuestText, QuestTextLine, TextSourceType, VoiceSelection
from .ocr import run_name_ocr, run_ocr, run_title_ocr

# > Local Dependencies
from .utils import extract_quest_areas, load_npc_memory, save_npc_memory, setup_logger

try:
    from .config import DEFAULT_VOLUME, ENABLE_WIKI, LUX_VOLUME
except ImportError:
    # Fallback if config hasn't been updated by the tool yet
    from .config import DEFAULT_VOLUME, ENABLE_WIKI

    LUX_VOLUME = DEFAULT_VOLUME
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
    backend_id: str
        The backend identifier (e.g., 'kokoro', 'lux').
    memory : dict
        A runtime cache of NPC-to-Voice mappings to ensure consistency.
    audio_queue : queue.Queue
        A thread-safe queue for buffering generated audio chunks.
    stop_event : threading.Event
       An event to signal the engine to stop processing.
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

        self.backend_id = getattr(self.tts, "backend_id", "lux")

        self.memory = load_npc_memory(self.mode, self.backend_id)
        log.info(f"🧠 Loaded Memory for mode: {self.mode} | Backend: {self.backend_id}")

        self.audio_queue = queue.Queue()
        self.stop_event = threading.Event()
        self._suppress_until = (
            0.0  # cooldown timestamp to prevent auto-retrigger after stop
        )

    def stop(self):
        """
        Immediate stop: Wipes the queue, kills the producer, and kills audio hardware.
        """
        log.info("🛑 Stop requested. Interrupting playback...")

        # 1. Signal threads to stop
        self.stop_event.set()

        # 2. Kill the active audio stream immediately
        stop_audio()

        # 3. Wipe the pending queue
        with self.audio_queue.mutex:
            self.audio_queue.queue.clear()

        # 4. Suppress auto-retrigger for 2 seconds (prevents watcher from
        #    immediately re-firing after F12 wipe)
        self._suppress_until = time.time() + 2.0

        log.info("🛑 Audio queue wiped and playback stopped.")

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

        # Build QuestText model
        quest_text = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text=" ".join(sentences),
            lines=[
                QuestTextLine(text=s, line_number=i) for i, s in enumerate(sentences)
            ],
            source_label="OCR",
        )

        log.info("Reading NPC Name...")
        npc_name = run_name_ocr(name_img_pil) or "Unknown"
        quest_text.npc_name = npc_name
        log.info(f"📝 NPC Name: '{npc_name}'")

        voice_selection = self._resolve_voice(npc_name)
        self._start_streaming(quest_text, voice_selection)

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
        # RETAIL MODE (Auto/Static)
        log.info(f"Detecting Quest Window for: {npc_name}...")

        # 1. Extraction
        title_pil, body_pil = extract_quest_areas(full_screen_np)

        # In static mode, title_pil may be None (we only extract body)
        # In auto mode, both should be present
        if not body_pil:
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
        source_type = TextSourceType.OCR
        quest_title = None

        # 3. Wiki Logic (Conditional)
        if ENABLE_WIKI and title_pil is not None:
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
                    source_type = TextSourceType.WIKI
                elif wiki.has_name_placeholder(matched_text):
                    source_label = "OCR (Wiki had placeholder)"
                else:
                    source_label = f"OCR (Low Wiki Acc: {accuracy:.1f}%)"
            else:
                source_label = "OCR (No Wiki Data)"
        elif ENABLE_WIKI and title_pil is None:
            log.info("⏩ Skipping Wiki Lookup (Static mode - no title)")
        else:
            log.info("⏩ Skipping Wiki Lookup (Config Disabled)")

        log.info(f"✅ Source: {source_label}")

        # 4. Build QuestText model
        final_sentences = nltk.sent_tokenize(final_text)
        quest_text = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text=full_ocr_text,
            lines=[
                QuestTextLine(
                    text=s,
                    line_number=i,
                    source=source_type,
                    confidence=accuracy if source_type == TextSourceType.WIKI else None,
                )
                for i, s in enumerate(final_sentences)
            ],
            npc_name=npc_name,
            quest_title=quest_title,
            source_label=source_label,
        )

        # 5. Playback
        voice_selection = self._resolve_voice(npc_name)
        self._start_streaming(quest_text, voice_selection)

    def _resolve_voice(self, npc_name: str) -> VoiceSelection:
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
        VoiceSelection
            A VoiceSelection object containing voice_id, category, and metadata.
        """
        key = npc_name.lower()
        is_default = False

        if key in self.memory:
            voice_id = self.memory[key]["voice_id"]
            category = self.memory[key].get("category", "")

            # If we are on Kokoro (CPU) but found a Lux ID (contains '|'), force a re-roll.
            if self.backend_id == "kokoro" and "|" in voice_id:
                log.warning(
                    f"⚠️ Found invalid Lux ID '{voice_id}' for Kokoro backend. Re-assigning voice."
                )
            elif (
                self.backend_id == "lux"
                and "|" not in voice_id
                and voice_id != "default"
            ):
                # If on Lux but found a Kokoro ID (no pipe), allow re-roll logic (optional)
                pass
            else:
                matched_name = self.memory[key].get("name", npc_name)
                race = self.memory[key].get("race", "")
                gender = self.memory[key].get("gender", "")
                return VoiceSelection(
                    voice_id=voice_id,
                    category=category,
                    npc_name=matched_name,
                    race=race,
                    gender=gender,
                    is_default=is_default,
                )

        # New NPC - look up in database
        gender, race, matched_name = self.db.lookup(npc_name)
        if not gender or not race:
            matched_name = "Narrator"
            race, gender = "Narrator", "Narrator"
            is_default = True

        voice_id, category = self.tts.pick_voice(gender, race)
        self.memory[key] = {
            "name": matched_name,
            "race": race,
            "gender": gender,
            "voice_id": voice_id,
            "category": category,
        }
        save_npc_memory(self.memory, self.mode)

        return VoiceSelection(
            voice_id=voice_id,
            category=category,
            npc_name=matched_name,
            race=race,
            gender=gender,
            is_default=is_default,
        )

    def _start_streaming(self, quest_text: QuestText, voice_selection: VoiceSelection):
        """
        Starts the audio generation and playback pipeline.

        Uses a Producer-Consumer model:
        - The Producer (Thread) generates audio using the TTS model.
        - The Consumer (Main Loop) pulls audio from the queue and plays it.

        Parameters
        ----------
        quest_text : QuestText
            The quest text model containing parsed lines.
        voice_selection : VoiceSelection
            The voice selection object for the NPC.

        # TODO: Future feature - separate quoted vs narrator voice
        # Currently all text uses the NPC voice. When quote detection is
        # implemented, quoted text will use NPC voice and non-quoted text
        # will use a separate narrator voice.
        """
        # Guard: if stop was recently requested, suppress this auto-trigger
        if time.time() < self._suppress_until:
            log.info("⏸️ Suppressed auto-trigger (recent F12 stop)")
            return

        # Reset stop event for new playback
        self.stop_event.clear()

        # TODO: Future feature - implement narrator voice selection
        # narrator_voice_id = self._get_narrator_voice()  # Not yet implemented
        # For now, all text uses the NPC voice
        voice_id = voice_selection.voice_id

        def producer():
            clean_lines = [line for line in quest_text.lines if line.text.strip()]

            if self.backend_id == "lux":
                chunk_size = 2
                for i in range(0, len(clean_lines), chunk_size):
                    if self.stop_event.is_set():
                        return
                    batch = clean_lines[i : i + chunk_size]
                    full_text = " ".join(line.text for line in batch)
                    if full_text:
                        audio = self.tts.generate(full_text, voice_id)
                        if self.stop_event.is_set():
                            return
                        self.audio_queue.put(
                            (full_text, audio, self.tts.samplerate, batch)
                        )
            else:
                for line in clean_lines:
                    if self.stop_event.is_set():
                        return
                    audio = self.tts.generate(line.text, voice_id)
                    if self.stop_event.is_set():
                        return
                    self.audio_queue.put(
                        (line.text, audio, self.tts.samplerate, [line])
                    )

            self.audio_queue.put(None)

        threading.Thread(target=producer, daemon=True).start()

        print("\n--- 🟢 PLAYBACK STARTED ---")
        print(f"  NPC: {voice_selection.npc_name} | Voice: {voice_selection.category}")
        while not self.stop_event.is_set():
            try:
                # Polling wait to keep loop responsive
                item = self.audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if item is None:
                break

            text, audio, sr, lines = item

            if self.stop_event.is_set():
                break

            print(f"▶️ Speaking: {text[:60]}...")
            if len(audio) > 0:
                vol = LUX_VOLUME if self.backend_id == "lux" else DEFAULT_VOLUME
                play_audio(audio, sr, volume=vol, stop_event=self.stop_event)

                time.sleep(0.1)

        print("--- 🔴 PLAYBACK ENDED ---\n")
