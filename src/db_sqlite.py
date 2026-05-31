# Imports

# > Standard Library
import csv
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from rapidfuzz import fuzz, process

# > Local Dependencies
from .config.ConfigManager import ConfigManager
from .utils import setup_logger

log = setup_logger(__name__)


# > Variables that are progress counters – stripped during ingest because
# they are never part of the narrated dialogue.
_COUNTER_VARS = {
    "${NUMBER}",
    "${TOTAL}",
    "${CURRENT}",
    "${MAX}",
    "${VALUE}",
    "${NOS}",
    "${NAME}",
}

# > Variables that carry player identity – kept in stored text as markers
# so they can be replaced at match time with the actual name read by OCR.
_PLAYER_VARS = {"${PLAYER}", "${PLAYER_NAME}"}
_IDENTITY_VARS = {"${RACE}", "${CLASS}"}


def _replace_player_vars(text: str, player_name: str = "Traveler") -> str:
    """Replace player-identity placeholders in matched DB text.

    Parameters
    ----------
    text : str
        DB text that may contain ``${PLAYER}``, ``${RACE}``, etc.
    player_name : str
        The actual player name to substitute.

    Returns
    -------
    str
        Text with all player variables resolved.
    """
    for var in _PLAYER_VARS:
        text = text.replace(var, player_name)
    for var in _IDENTITY_VARS:
        text = text.replace(var, "adventurer")
    return text


def _extract_player_name(ocr_text: str, db_text: str) -> str:
    """Extract the player name by aligning OCR text with DB text.

    Finds ``${PLAYER}`` in the DB text, locates the same position in
    the OCR text using the surrounding context, and extracts the word(s)
    that appear there.

    Falls back to ``"Traveler"`` when extraction fails.
    """
    marker = "${PLAYER}"
    if marker not in db_text:
        return "Traveler"

    idx = db_text.index(marker)
    prefix = db_text[:idx]
    suffix = db_text[idx + len(marker) :]

    # Find prefix in OCR text (case-insensitive)
    pi = ocr_text.lower().find(prefix.lower())
    if pi == -1:
        return "Traveler"
    start = pi + len(prefix)

    # Find suffix after the prefix position
    si = ocr_text.lower().find(suffix.lower(), start)
    if si == -1:
        # Try just the first few chars of suffix for robustness
        si = ocr_text.lower().find(suffix.lower()[:8], start)
    if si == -1:
        return "Traveler"

    name = ocr_text[start:si].strip().strip(",.!?;:")
    return name if name else "Traveler"


def _clean_xml_text(text: str) -> str:
    """Clean resolved text from the XML database.

    Strips RGB markup tags, replaces ``\\q`` quote markers,
    removes counter variables, and normalises whitespace.
    Player-identity variables (``${PLAYER}``, ``${RACE}``, etc.)
    are **preserved** so they can be replaced at match time with
    the actual values from OCR.
    """
    if not text:
        return ""

    text = re.sub(r"<rgb=[^>]*>(.*?)</rgb>", r"\1", text)
    text = text.replace("\\q", '"')

    for var in _COUNTER_VARS:
        text = text.replace(var, "")

    text = re.sub(r"\s+", " ", text).strip()
    return text


class NPCDatabaseSQLite:
    """
    SQLite-backed NPC database with exact and fuzzy name matching.

    Loads NPC data from CSV into a local SQLite database on first run, then uses indexed lookups.

    Parameters
    ----------
    db_path : str, optional
        Path to the source CSV file. The database will be created alongside
        it with a ``.db`` extension. If ``None``, reads the path from config.

    Attributes
    ----------
    conn : sqlite3.Connection
        The active SQLite connection.
    all_names : list[str]
        Sorted list of lowercase NPC names, cached for fuzzy matching.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            _cfg = ConfigManager()
            db_path = _cfg.get_str("Paths", "npc_data_path")

        # Connect to database / init database if not exists
        self.conn = self.init_database(db_path)

        # Fill NPC table if empty
        cursor = self.conn.execute("SELECT COUNT(*) FROM npcs")
        count = cursor.fetchone()[0]
        if count == 0:
            self.fill_database(db_path)

        # Cache all npc names for fuzzy matching
        cursor = self.conn.execute("SELECT name_lower FROM npcs")
        self.all_names = sorted(set(row[0] for row in cursor.fetchall()))

        # Fill quest tables if empty
        cursor = self.conn.execute("SELECT COUNT(*) FROM quests")
        quest_count = cursor.fetchone()[0]
        if quest_count == 0:
            _cfg = ConfigManager()
            quests_xml = _cfg.get_str("Paths", "quests_xml_path")
            labels_xml = _cfg.get_str("Paths", "quest_labels_xml_path")
            if os.path.exists(quests_xml) and os.path.exists(labels_xml):
                self.fill_quests_from_xml(quests_xml, labels_xml)
            else:
                log.warning(
                    f"Quest XML files not found. Checked: {quests_xml}, {labels_xml}"
                )

        # --- Load quest data into memory for fast lookups ---

        _NON_ALPHA = re.compile(r"[^a-z0-9 ]")
        _MULTI_SPACE = re.compile(r"  +")

        def _normalize(title: str) -> str:
            """Strip punctuation and collapse whitespace for fuzzy-resilient matching."""
            return _MULTI_SPACE.sub(" ", _NON_ALPHA.sub("", title)).strip()

        # title_lower → (quest_id, canonical_title)
        cursor = self.conn.execute("SELECT quest_id, title, title_lower FROM quests")
        self._quest_by_title: Dict[str, tuple] = {}
        self._quest_by_norm: Dict[str, tuple] = {}  # normalized title → result
        for quest_id, title, title_lower in cursor.fetchall():
            entry = (quest_id, title)
            self._quest_by_title[title_lower] = entry
            norm = _normalize(title_lower)
            if norm != title_lower:
                self._quest_by_norm[norm] = entry

        # quest_id → list of (text_type, npc_name, text_content, order_index)
        cursor = self.conn.execute(
            "SELECT quest_id, text_type, npc_name, text_content, order_index "
            "FROM quest_text ORDER BY quest_id, order_index"
        )
        self._segments_by_quest: Dict[str, List[tuple]] = {}
        seg_count = 0
        for (
            quest_id,
            text_type,
            npc_name,
            text_content,
            order_index,
        ) in cursor.fetchall():
            self._segments_by_quest.setdefault(quest_id, []).append(
                (text_type, npc_name, text_content)
            )
            seg_count += 1

        # Pre-compute lowercase comparison text for each segment
        # (avoids repeated .lower() calls during matching)
        self._seg_cmp_text: Dict[str, List[str]] = {}
        for quest_id, segments in self._segments_by_quest.items():
            cmp_list = []
            for text_type, npc_name, text_content in segments:
                cmp = text_content.lower()
                for var in _PLAYER_VARS | _IDENTITY_VARS:
                    cmp = cmp.replace(var, "")
                cmp_list.append(cmp)
            self._seg_cmp_text[quest_id] = cmp_list

        log.info(
            f"Database ready: {len(self.all_names)} NPCs, "
            f"{len(self._quest_by_title)} quests, "
            f"{seg_count} segments loaded in-memory"
        )

    def init_database(self, npc_csv_path: str) -> sqlite3.Connection:
        """
        Connect to the SQLite database and ensure the schema exists.

        Creates the database file (with a ``.db`` extension) if it does not
        exist, and creates the ``npcs`` table and index if they are missing.

        Parameters
        ----------
        npc_csv_path : str
            Path to the source CSV file. The database file is derived by
            replacing the ``.csv`` extension with ``.db``.

        Returns
        -------
        sqlite3.Connection
            An active connection to the database.
        """
        log.info("Connecting to local database...")

        conn = sqlite3.connect(
            npc_csv_path.replace(".csv", ".db"),
            check_same_thread=False,
        )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS npcs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                name_lower TEXT NOT NULL,
                gender TEXT,
                race TEXT,
                url TEXT
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_name_lower ON npcs(name_lower)
        """)

        # Quest tables
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quest_id TEXT NOT NULL,
                title TEXT NOT NULL,
                title_lower TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_quest_title_lower
                ON quests(title_lower)
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS quest_text (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quest_id TEXT NOT NULL,
                text_type TEXT NOT NULL,
                npc_name TEXT,
                text_content TEXT NOT NULL,
                order_index INTEGER NOT NULL,
                objective_index INTEGER
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_qt_quest_id ON quest_text(quest_id)
        """)

        return conn

    def fill_database(self, csv_path: str) -> None:
        """
        Import NPC data from CSV into the SQLite database.

        Uses ``csv.DictReader`` to read the CSV and ``executemany`` for
        efficient bulk insertion. Only runs when the table is empty.

        Parameters
        ----------
        csv_path : str
            Path to the ``npc_data.csv`` file.
        """
        cursor = self.conn.execute("SELECT COUNT(*) FROM npcs")
        count = cursor.fetchone()[0]
        if count > 0:
            return

        rows = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(
                    (
                        row["Name"],
                        row["Name"].lower().strip(),
                        row["Gender"],
                        row["Race"],
                        row["URL"],
                    )
                )

        with self.conn:
            self.conn.executemany(
                "INSERT INTO npcs (name, name_lower, gender, race, url) VALUES (?, ?, ?, ?, ?)",
                rows,
            )
        log.info(f"Imported {len(rows)} NPCs from CSV")

    def lookup(self, name: str) -> Tuple[Optional[str], Optional[str], str]:
        """
        Find an NPC by name using exact then fuzzy matching.

        Parameters
        ----------
        name : str
            The name to look up (e.g., from OCR).

        Returns
        -------
        tuple[str | None, str | None, str]
            Returns ``(Gender, Race, RealName)``. Gender and Race will be
            ``None`` if no match is found. RealName returns the corrected
            name if matched, or the original input if not.
        """
        if not name:
            return None, None, name

        # 1. Exact match
        cursor = self.conn.execute(
            "SELECT gender, race, name FROM npcs WHERE name_lower = ?",
            (name.lower().strip(),),
        )
        row = cursor.fetchone()

        if row:
            return row[0], row[1], row[2]

        match = process.extractOne(
            name.lower().strip(), self.all_names, scorer=fuzz.ratio, score_cutoff=60.0
        )

        if match:
            best_match = match[0]
            cursor = self.conn.execute(
                "SELECT gender, race, name FROM npcs WHERE name_lower = ?",
                (best_match,),
            )
            row = cursor.fetchone()
            if row:
                log.info(f"Fuzzy match: '{name}' -> '{row[2]}'")
                return row[0], row[1], row[2]

        return None, None, name

    def fill_quests_from_xml(self, quests_xml_path: str, labels_xml_path: str) -> None:
        """Parse datamined XML files and populate the quest tables.

        Resolves all ``key:hash1:hash2`` references using the labels file,
        cleans markup, substitutes variables, and inserts into SQLite.

        Parameters
        ----------
        quests_xml_path : str
            Path to ``quests.xml`` containing quest structure.
        labels_xml_path : str
            Path to ``quest_dialogue.xml`` containing localised strings.
        """
        cursor = self.conn.execute("SELECT COUNT(*) FROM quests")
        if cursor.fetchone()[0] > 0:
            return

        log.info("Building quest database from XML...")

        # 1. Load label lookup dict from dialogue XML
        log.info(f"  Parsing labels: {labels_xml_path}")
        labels_root = ET.parse(labels_xml_path).getroot()
        labels: Dict[str, str] = {}
        for label_elem in labels_root.findall(".//label"):
            key = label_elem.get("key")
            value = label_elem.get("value", "")
            if key and value:
                labels[key] = value
        log.info(f"  Loaded {len(labels)} label entries")

        # 2. Parse quests.xml
        log.info(f"  Parsing quests: {quests_xml_path}")
        quests_root = ET.parse(quests_xml_path).getroot()

        quest_rows = []
        text_rows = []
        quest_count = 0

        for quest_elem in quests_root.findall("quest"):
            quest_id = quest_elem.get("id", "")
            title = quest_elem.get("name", "")
            if not quest_id or not title:
                continue

            title_lower = title.lower().strip()
            quest_rows.append((quest_id, title, title_lower))
            order = 0

            # --- Description (narration) ---
            desc_key = quest_elem.get("description", "")
            if desc_key in labels:
                cleaned = _clean_xml_text(labels[desc_key])
                if cleaned:
                    text_rows.append(
                        (quest_id, "description", None, cleaned, order, None)
                    )
                    order += 1

            # --- Bestower dialogue ---
            for bestower in quest_elem.findall("bestower"):
                best_key = bestower.get("text", "")
                best_npc = bestower.get("npcName")
                if best_key in labels:
                    cleaned = _clean_xml_text(labels[best_key])
                    if cleaned:
                        text_rows.append(
                            (quest_id, "bestower", best_npc, cleaned, order, None)
                        )
                        order += 1

            # --- Objectives ---
            for obj_elem in quest_elem.findall(".//objective"):
                obj_idx_str = obj_elem.get("index")
                obj_idx = int(obj_idx_str) if obj_idx_str else None

                # Objective description (narration)
                obj_key = obj_elem.get("text", "")
                if obj_key in labels:
                    cleaned = _clean_xml_text(labels[obj_key])
                    if cleaned:
                        text_rows.append(
                            (
                                quest_id,
                                "objective",
                                None,
                                cleaned,
                                order,
                                obj_idx,
                            )
                        )
                        order += 1

                # Dialog lines within objective (NPC speech)
                for dialog in obj_elem.findall("dialog"):
                    dlg_key = dialog.get("text", "")
                    dlg_npc = dialog.get("npcName")
                    if dlg_key in labels:
                        cleaned = _clean_xml_text(labels[dlg_key])
                        if cleaned:
                            text_rows.append(
                                (
                                    quest_id,
                                    "dialog",
                                    dlg_npc,
                                    cleaned,
                                    order,
                                    obj_idx,
                                )
                            )
                            order += 1

            quest_count += 1
            if quest_count % 5000 == 0:
                log.info(f"  Processed {quest_count} quests...")

        # 3. Bulk insert
        with self.conn:
            self.conn.executemany(
                "INSERT INTO quests (quest_id, title, title_lower) VALUES (?, ?, ?)",
                quest_rows,
            )
            self.conn.executemany(
                "INSERT INTO quest_text "
                "(quest_id, text_type, npc_name, text_content, order_index, objective_index) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                text_rows,
            )

        log.info(
            f"  Imported {len(quest_rows)} quests with {len(text_rows)} text entries"
        )

    _NON_ALPHA = re.compile(r"[^a-z0-9 ]")
    _MULTI_SPACE = re.compile(r"  +")

    @classmethod
    def _normalize(cls, title: str) -> str:
        """Strip punctuation and collapse whitespace."""
        return cls._MULTI_SPACE.sub(" ", cls._NON_ALPHA.sub("", title)).strip()

    def _resolve_quest_id(self, ocr_title: str):
        """Find a quest by OCR title. Returns (quest_id, canonical_title) or (None, None)."""
        if not ocr_title:
            return None, None

        raw = ocr_title.lower().strip()

        # Layer 1: exact match
        if raw in self._quest_by_title:
            return self._quest_by_title[raw]

        # Layer 2: normalised match (strips quotes, semicolons, etc.)
        norm = self._normalize(raw)
        if norm in self._quest_by_norm:
            return self._quest_by_norm[norm]

        # Also try normalised as a plain key (handles case where DB title
        # has no punctuation but OCR added some)
        if norm in self._quest_by_title:
            return self._quest_by_title[norm]

        # Layer 3: RapidFuzz across all normalized titles
        # We drop the old word-overlap pre-filter because RapidFuzz is fast enough
        # to check all quests instantly, and it handles split/mutated words perfectly.
        match = process.extractOne(
            norm, self._quest_by_norm.keys(), scorer=fuzz.ratio, score_cutoff=60.0
        )

        if match:
            best_norm_tl, score, _ = match
            result = self._quest_by_norm.get(best_norm_tl)
            if result:
                log.info(
                    f"Quest title match: '{ocr_title}' -> '{result[1]}' "
                    f"(score={score:.1f}%)"
                )
                return result

        return None, None

    def match_quest_text(self, ocr_title: str, ocr_body: str) -> Optional[Dict]:
        """Fuzzy-match OCR body text against in-memory DB to find pristine text.

        Resolves the quest by title via dict lookup, then compares the OCR
        body against every text segment using :class:`difflib.SequenceMatcher`.
        Segment comparison text is pre-computed at init time.

        Parameters
        ----------
        ocr_title : str
            The quest title as read by OCR.
        ocr_body : str
            The quest body text as read by OCR.

        Returns
        -------
        dict | None
            ``{text, npc_name, text_type, is_dialogue, player_name, score}``
            or ``None`` when no quest or no segment matches.
        """
        if not ocr_body:
            return None

        quest_id, canonical_title = self._resolve_quest_id(ocr_title)
        if not quest_id:
            return None

        segments = self._segments_by_quest.get(quest_id)
        if not segments:
            return None

        cmp_texts = self._seg_cmp_text[quest_id]

        # Fuzzy match: find the DB segment that best matches the OCR body
        ocr_clean = ocr_body.lower().strip()
        best_score = 0.0
        best_idx = -1

        for i, cmp in enumerate(cmp_texts):
            score = fuzz.ratio(ocr_clean, cmp) / 100.0
            if score > best_score:
                best_score = score
                best_idx = i

        if best_score < 0.4 or best_idx < 0:
            log.info(
                f"Quest DB: no segment matched '{canonical_title}' "
                f"(best={best_score:.1%})"
            )
            return None

        text_type, npc_name, db_text = segments[best_idx]

        # Extract player name from OCR and resolve variables
        player_name = _extract_player_name(ocr_body, db_text)
        clean_text = _replace_player_vars(db_text, player_name)

        is_dialogue = text_type in ("bestower", "dialog")

        log.info(
            f"Quest DB match: '{canonical_title}' "
            f"[{text_type}] score={best_score:.1%} "
            f"player={player_name}"
        )

        return {
            "text": clean_text,
            "npc_name": npc_name,
            "text_type": text_type,
            "is_dialogue": is_dialogue,
            "player_name": player_name,
            "score": best_score,
        }

    def get_random_npcs(self, count: int = 10) -> List[Dict]:
        """
        Return a random sample of NPCs from the database.

        Parameters
        ----------
        count : int, optional
            Number of NPCs to retrieve (default is 10).

        Returns
        -------
        list[dict]
            A list of dictionaries representing NPC rows.
        """
        cursor = self.conn.execute(
            "SELECT name, gender, race, url FROM npcs ORDER BY RANDOM() LIMIT ?",
            (count,),
        )
        columns = ["name", "gender", "race", "url"]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
