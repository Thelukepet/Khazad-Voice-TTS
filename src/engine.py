# Imports

# > Standard Library
import queue
import threading
import time
from datetime import datetime

# > Third-party Libraries
import nltk

# > Local Dependencies
from .audio import play_audio, stop_audio
from .config.ConfigManager import ConfigManager
from .models import QuestText, QuestTextLine, TextSourceType, VoiceSelection
from .ocr import run_name_ocr, run_ocr, run_title_ocr
from .utils import extract_quest_areas, load_npc_memory, save_npc_memory, setup_logger

log = setup_logger("ENGINE")


class NarratorEngine:
    """
    Core engine that orchestrates the workflow between OCR, Database lookups,
    and Text-to-Speech generation.

    Attributes
    ----------
    db : Database
        The NPC database interface for race/gender lookups.
    tts : TTSBackend
        The initialized Text-to-Speech backend (e.g., Kokoro, OmniVoice).
    mode : str
        The operation mode ('echoes' for manual, 'retail' for auto).
    backend_id: str
        The backend identifier (e.g., 'kokoro', 'omnivoice').
    memory : dict
        A runtime cache of NPC-to-Voice mappings to ensure consistency.
    audio_queue : queue.Queue
        A thread-safe queue for buffering generated audio chunks.
    stop_event : threading.Event
       An event to signal the engine to stop processing.
    """

    def __init__(self, db, tts_backend, mode="echoes", voice_mix=False):
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
        voice_mix : bool, optional
            When True, quoted dialogue uses the NPC voice and narration
            uses a narrator voice.  Experimental feature.
        """
        self.db = db
        self.tts = tts_backend
        self.mode = mode
        self.voice_mix = voice_mix

        self.backend_id = getattr(self.tts, "backend_id", "omnivoice")

        self.memory = load_npc_memory(self.mode, self.backend_id)
        log.info(f"Loaded memory for mode: {self.mode} | Backend: {self.backend_id}")

        self.audio_queue = queue.Queue()
        self.stop_event = threading.Event()
        self._suppress_until = (
            0.0  # cooldown timestamp to prevent auto-retrigger after stop
        )

    def stop(self):
        """
        Immediate stop: Wipes the queue, kills the producer, and kills audio hardware.
        """
        log.info("Stop requested. Interrupting playback...")

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

        log.info("Audio queue wiped and playback stopped.")

    def process_capture(self, quest_img_pil, name_img_pil):
        """
        Handles the 'Echoes' (Classic) mode workflow.

        Reads the NPC name and quest body via OCR, then tries to match
        the OCR text against the offline quest database for pristine text.
        Falls back to raw OCR if no match is found.
        """
        log.info("Reading NPC Name...")
        npc_name = run_name_ocr(name_img_pil) or "Unknown"
        log.info(f"NPC Name: '{npc_name}'")

        # OCR the body (always needed)
        log.info("Reading Quest Text...")
        sentences = run_ocr(quest_img_pil)
        if not sentences:
            log.warning("No quest text found.")
            return

        full_ocr_text = " ".join(sentences)

        # Try to get a title hint from the first line of the body image
        quest_title = None
        try:
            import numpy as np
            import pytesseract

            from .ocr import preprocess_title_image

            title_hint_thresh = preprocess_title_image(quest_img_pil)
            title_hint = (
                pytesseract.pytesseract.image_to_string(
                    title_hint_thresh, config="--psm 7"
                )
                .strip()
                .replace("\n", " ")
            )
            if title_hint:
                quest_title = title_hint
        except Exception:
            pass

        # Try DB match
        source_label = "OCR"
        source_type = TextSourceType.OCR
        final_text = full_ocr_text
        db_npc = None

        if quest_title:
            db_match = self.db.match_quest_text(quest_title, full_ocr_text)
            if db_match:
                final_text = db_match["text"]
                db_npc = db_match["npc_name"]
                source_label = f"OfflineDB ({db_match['score']:.0%})"
                source_type = TextSourceType.OFFLINE_DB

        # Build QuestText
        final_sentences = nltk.sent_tokenize(final_text)
        quest_text = QuestText(
            timestamp=datetime.now(),
            raw_ocr_text=full_ocr_text,
            lines=[
                QuestTextLine(
                    text=s,
                    line_number=i,
                    source=source_type,
                )
                for i, s in enumerate(final_sentences)
            ],
            npc_name=db_npc or npc_name,
            quest_title=quest_title,
            source_label=source_label,
        )

        log.info(f"Source: {source_label}")
        voice_selection = self._resolve_voice(db_npc or npc_name)
        self._start_streaming(quest_text, voice_selection)

    def process_retail(self, _, full_screen_np, npc_name):
        """
        Handles the 'Retail' (Live) mode workflow.

        1. Extracts Title/Body using calibrated layout.
        2. OCR on body (always).
        3. Tries offline DB fuzzy match to get pristine text.
        4. Falls back to raw OCR if DB misses.
        5. Queues text for TTS.
        """
        log.info(f"Detecting Quest Window for: {npc_name}...")

        # 1. Extraction
        title_pil, body_pil = extract_quest_areas(full_screen_np)
        if not body_pil:
            log.info("NPC in log, but valid Quest Window not found.")
            return

        # 2. OCR Title + Body (always)
        quest_title = None
        if title_pil is not None:
            quest_title = run_title_ocr(title_pil)
            log.info(f"Quest Title: '{quest_title}'")

        ocr_sentences = run_ocr(body_pil)
        if not ocr_sentences:
            log.warning("Quest body OCR empty.")
            return

        full_ocr_text = " ".join(ocr_sentences)
        final_text = full_ocr_text
        source_label = "OCR (Default)"
        source_type = TextSourceType.OCR
        db_npc = None

        # 3. Try Offline DB (instant, local fuzzy match)
        if quest_title:
            db_match = self.db.match_quest_text(quest_title, full_ocr_text)
            if db_match:
                final_text = db_match["text"]
                db_npc = db_match["npc_name"]
                source_label = f"OfflineDB ({db_match['score']:.0%})"
                source_type = TextSourceType.OFFLINE_DB
                log.info(f"Source: {source_label}")

        if source_type == TextSourceType.OCR:
            log.info(f"Source: {source_label}")

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
                )
                for i, s in enumerate(final_sentences)
            ],
            npc_name=db_npc or npc_name,
            quest_title=quest_title,
            source_label=source_label,
        )

        # 5. Playback
        voice_selection = self._resolve_voice(db_npc or npc_name)
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

            # If we are on Kokoro (CPU) but found an OmniVoice ID (contains '|'),
            # force a re-roll.
            if self.backend_id == "kokoro" and "|" in voice_id:
                log.warning(
                    f"Found invalid OmniVoice ID '{voice_id}' for Kokoro backend. "
                    f"Re-assigning voice."
                )
            elif (
                self.backend_id == "omnivoice"
                and "|" not in voice_id
                and voice_id != "default"
            ):
                # If on OmniVoice but found a Kokoro ID (no pipe), allow re-roll.
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
            voice_id, category = self.tts.pick_default_voice()
        else:
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

    @staticmethod
    def _tag_quoted_lines(quest_text: QuestText) -> None:
        """Tag each QuestTextLine with ``is_quoted`` using a state machine.

        LOTRO quest text uses single quotes (``'``) to mark NPC speech
        that can span multiple sentences.  A leading ``'`` opens a
        dialogue block; a trailing ``'`` closes it.  Apostrophes inside
        words (e.g. "can't") are ignored because they never appear at the
        absolute start/end of the line.

        This works reliably on pristine database text which has correct
        punctuation.  It is also used as a fallback for raw OCR text
        (where apostrophe errors may cause misclassification).

        Rules applied per line (in order):
        1. If the line starts with ``'``  → enter dialogue mode.
        2. The line is marked quoted / unquoted based on the current state.
        3. If the line ends with ``'`` and we are in dialogue mode → exit.

        Parameters
        ----------
        quest_text : QuestText
            The quest text whose lines will be tagged in-place.
        """
        in_quote = False
        for line in quest_text.lines:
            stripped = line.text.strip()
            starts = stripped.startswith("'")
            ends = stripped.endswith("'")

            if starts:
                in_quote = True

            line.is_quoted = in_quote

            if ends and in_quote:
                in_quote = False

    def _build_quest_from_db(
        self,
        db_segments: list,
        npc_name: str,
        quest_title: str,
    ) -> QuestText:
        """Construct a :class:`QuestText` from offline DB segments.

        Parameters
        ----------
        db_segments : list[dict]
            Output of :meth:`NPCDatabaseSQLite.get_quest_text`.
        npc_name : str
            The NPC name (from OCR or game log).
        quest_title : str
            The quest title matched from the database.

        Returns
        -------
        QuestText
            A fully populated model with ``is_quoted`` pre-tagged.
        """
        lines = []
        for i, seg in enumerate(db_segments):
            lines.append(
                QuestTextLine(
                    text=seg["text"],
                    line_number=i,
                    source=TextSourceType.OFFLINE_DB,
                    is_quoted=seg["is_dialogue"],
                )
            )

        raw_text = " ".join(seg["text"] for seg in db_segments)
        return QuestText(
            timestamp=datetime.now(),
            raw_ocr_text=raw_text,
            lines=lines,
            npc_name=npc_name,
            quest_title=quest_title,
            source_label="OfflineDB",
        )

    def _start_streaming(self, quest_text: QuestText, voice_selection: VoiceSelection):
        """
        Starts the audio generation and playback pipeline.

        Uses a Producer-Consumer model with dual-voice support:
        - Quoted text (NPC dialogue) uses the NPC's voice.
        - Non-quoted text (narration) uses the narrator voice.

        Parameters
        ----------
        quest_text : QuestText
            The quest text model containing parsed lines.
        voice_selection : VoiceSelection
            The voice selection object for the NPC.
        """
        # Guard: if stop was recently requested, suppress this auto-trigger
        if time.time() < self._suppress_until:
            log.info("Suppressed auto-trigger (recent F12 stop)")
            return

        # Reset stop event for new playback
        self.stop_event.clear()

        npc_voice_id = voice_selection.voice_id

        # --- Voice Mix (Experimental) ---
        # When enabled, quoted dialogue uses the NPC voice and narration
        # uses a separate narrator voice.  When disabled, all lines use
        # the NPC voice (stable behaviour).
        if self.voice_mix:
            self._tag_quoted_lines(quest_text)
            narrator_voice_id, _ = self.tts.pick_narrator_voice()

            quoted_count = sum(1 for line in quest_text.lines if line.is_quoted)
            narrator_count = len(quest_text.lines) - quoted_count
            log.info(
                f"[VOICE MIX] Lines: {quoted_count} quoted (NPC) / "
                f"{narrator_count} narration | NPC voice={voice_selection.category}"
            )
        else:
            narrator_voice_id = None

        def _voice_for_line(line: QuestTextLine) -> str:
            """Return the appropriate voice ID for a line."""
            if not self.voice_mix:
                return npc_voice_id
            return npc_voice_id if line.is_quoted else narrator_voice_id

        def producer():
            clean_lines = [line for line in quest_text.lines if line.text.strip()]

            if self.backend_id == "omnivoice":
                _cfg = ConfigManager()
                chunk_size = _cfg.get_int(
                    "TTSSettings", "omnivoice_chunk_size", fallback=2
                )
                for i in range(0, len(clean_lines), chunk_size):
                    if self.stop_event.is_set():
                        return
                    batch = clean_lines[i : i + chunk_size]
                    # Group consecutive lines that share the same voice
                    j = 0
                    while j < len(batch):
                        voice = _voice_for_line(batch[j])
                        group = [batch[j]]
                        k = j + 1
                        while k < len(batch) and _voice_for_line(batch[k]) == voice:
                            group.append(batch[k])
                            k += 1
                        full_text = " ".join(line.text for line in group)
                        if full_text:
                            audio = self.tts.generate(full_text, voice)
                            if self.stop_event.is_set():
                                return
                            self.audio_queue.put(
                                (full_text, audio, self.tts.samplerate, group)
                            )
                        j = k
            else:
                for line in clean_lines:
                    if self.stop_event.is_set():
                        return
                    voice = _voice_for_line(line)
                    audio = self.tts.generate(line.text, voice)
                    if self.stop_event.is_set():
                        return
                    self.audio_queue.put(
                        (line.text, audio, self.tts.samplerate, [line])
                    )

            self.audio_queue.put(None)

        threading.Thread(target=producer, daemon=True).start()

        log.info(
            f"Playback started: NPC={voice_selection.npc_name} | Voice={voice_selection.category}"
        )
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

            voice_label = "NPC" if any(ln.is_quoted for ln in lines) else "Narrator"
            # log.info(
            #     f"Speaking [{voice_label}]: {text[:60]}{'...' if len(text) > 60 else ''}"
            # )
            log.info(f"Speaking [{voice_label}]: {text}")

            if len(audio) > 0:
                _cfg = ConfigManager()
                vol = (
                    _cfg.get_float("TTSSettings", "omnivoice_volume", fallback=0.5)
                    if self.backend_id == "omnivoice"
                    else _cfg.get_float("TTSSettings", "default_volume", fallback=0.4)
                )
                play_audio(audio, sr, volume=vol, stop_event=self.stop_event)

                time.sleep(0.1)

        log.info("Playback ended")
