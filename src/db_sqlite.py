# Imports

# > Standard Library
import csv
import difflib
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

# > Variables that carry player identity - kept in stored text as markers
# so they can be replaced at match time with the actual values read by OCR.
_PLAYER_VARS = {"${PLAYER}", "${PLAYER_NAME}"}
_IDENTITY_VARS = {"${RACE}", "${CLASS}"}
_ALL_IDENTITY_VARS = ("${PLAYER}", "${PLAYER_NAME}", "${RACE}", "${CLASS}")

# > Last-resort replacements when neither OCR extraction nor the
# configured character identity provides a value.
_VAR_FALLBACKS = {
    "${PLAYER}": "Traveler",
    "${PLAYER_NAME}": "Traveler",
    "${RACE}": "adventurer",
    "${CLASS}": "adventurer",
}

# > Marker inside a DB token, e.g. ``${PLAYER},`` or ``friend ${CLASS}!``
_VAR_TOKEN_RE = re.compile(r"\$\{(?:PLAYER_NAME|PLAYER|RACE|CLASS)\}")

# > Alignment tuning: context words used to locate a variable in the OCR
# text, the maximum plausible length of an extracted value, and the
# fuzzy-score floor below which an anchor is considered not found.
_ANCHOR_TOKENS = 3
_MAX_VALUE_TOKENS = 4
_ANCHOR_SCORE_CUTOFF = 60.0

# > Punctuation trimmed from extracted values (straight and curly quotes)
_VALUE_STRIP = ".,!?;:'\"\u201c\u201d\u2018\u2019"


def _norm_token(token: str) -> str:
    """Lowercase a word and strip punctuation for fuzzy comparison."""
    return re.sub(r"[^a-z0-9]", "", token.lower())


def _find_anchor(
    ocr_norm: List[str], anchor: List[str], start: int, limit: Optional[int] = None
) -> Optional[int]:
    """Find the best fuzzy position of an anchor word sequence in OCR text.

    Searches OCR token windows beginning at index ``start`` (and, when
    ``limit`` is given, starting no later than ``limit``) and returns
    the index of the best match, or ``None`` when no window reaches the
    score cutoff. Early-exits on a perfect match.
    """
    n = len(anchor)
    hi = len(ocr_norm) - n + 1
    if limit is not None:
        hi = min(hi, limit + 1)
    if n == 0 or start >= hi:
        return None
    anchor_str = " ".join(anchor)
    best_pos: Optional[int] = None
    best_score = 0.0
    for pos in range(start, hi):
        score = fuzz.ratio(anchor_str, " ".join(ocr_norm[pos : pos + n]))
        if score > best_score:
            best_pos, best_score = pos, score
        if score >= 100.0:
            break
    return best_pos if best_score >= _ANCHOR_SCORE_CUTOFF else None


def _find_anchor_positions(
    ocr_norm: List[str], anchor: List[str], start: int
) -> List[Tuple[int, float]]:
    """All positions (with score) where the anchor matches above cutoff."""
    positions: List[Tuple[int, float]] = []
    n = len(anchor)
    if n == 0 or start + n > len(ocr_norm):
        return positions
    anchor_str = " ".join(anchor)
    for pos in range(start, len(ocr_norm) - n + 1):
        score = fuzz.ratio(anchor_str, " ".join(ocr_norm[pos : pos + n]))
        if score >= _ANCHOR_SCORE_CUTOFF:
            positions.append((pos, score))
    return positions


def _best_window_score(
    ocr_norm: List[str], anchor: List[str], start: int, limit: int
) -> float:
    """Best fuzzy score for the anchor against windows starting in [start, limit]."""
    n = len(anchor)
    hi = min(len(ocr_norm) - n + 1, limit + 1)
    if n == 0 or start >= hi:
        return 0.0
    anchor_str = " ".join(anchor)
    return max(
        fuzz.ratio(anchor_str, " ".join(ocr_norm[pos : pos + n]))
        for pos in range(start, hi)
    )


def _extract_var_values(ocr_text: str, db_text: str) -> Dict[str, str]:
    """Extract identity-variable values by aligning OCR text with DB text.

    The game renders ``${PLAYER}``, ``${RACE}`` and ``${CLASS}`` on
    screen, so the OCR text contains the actual values. For every
    variable occurrence in the DB text, the surrounding words serve as
    anchors to locate the corresponding span in the OCR text; fuzzy
    anchor matching keeps this working through OCR noise.

    Returns
    -------
    dict[str, str]
        Maps variable names to extracted values; only variables whose
        value could be located are included.
    """
    values: Dict[str, str] = {}
    db_tokens = db_text.split()
    ocr_raw = ocr_text.split()
    if not db_tokens or not ocr_raw:
        return values
    ocr_norm = [_norm_token(t) for t in ocr_raw]

    for k, db_tok in enumerate(db_tokens):
        m = _VAR_TOKEN_RE.search(db_tok)
        if not m:
            continue
        var = m.group(0)
        if var in values:
            continue  # first successful extraction wins

        # Two variables back to back ("as a ${CLASS}, ${PLAYER}.") have no
        # local anchor between their rendered values - skip here and let
        # the global-alignment fallback below pair them positionally.
        prev_is_var = k > 0 and bool(_VAR_TOKEN_RE.search(db_tokens[k - 1]))
        next_is_var = (
            k + 1 < len(db_tokens) and bool(_VAR_TOKEN_RE.search(db_tokens[k + 1]))
        )
        if prev_is_var or next_is_var:
            continue

        # Context anchors: nearest non-variable words around the marker
        prefix: List[str] = []
        i = k - 1
        while i >= 0 and len(prefix) < _ANCHOR_TOKENS:
            if _VAR_TOKEN_RE.search(db_tokens[i]):
                break
            prefix.insert(0, _norm_token(db_tokens[i]))
            i -= 1
        suffix: List[str] = []
        i = k + 1
        while i < len(db_tokens) and len(suffix) < _ANCHOR_TOKENS:
            if _VAR_TOKEN_RE.search(db_tokens[i]):
                break
            suffix.append(_norm_token(db_tokens[i]))
            i += 1

        # Left anchor locates where the value starts. The anchor phrase
        # may occur several times in the text (e.g. "near the lake... near
        # the lake, ${PLAYER}!"), so every candidate is scored by how well
        # its prefix matches AND its suffix follows within the bounded
        # value span; the best combined score wins (ties: rightmost).
        start = 0
        if prefix:
            candidates = _find_anchor_positions(ocr_norm, prefix, 0)
            if not candidates:
                continue  # without the left anchor the span is a guess
            best: Optional[Tuple[float, int]] = None
            for cand_pos, cand_score in candidates:
                s = cand_pos + len(prefix)
                if suffix:
                    suffix_score = _best_window_score(
                        ocr_norm, suffix, s, s + _MAX_VALUE_TOKENS
                    )
                    if suffix_score < _ANCHOR_SCORE_CUTOFF:
                        continue
                    combined = cand_score + suffix_score
                else:
                    combined = cand_score
                if best is None or combined >= best[0]:
                    best = (combined, cand_pos)
            if best is None:
                continue
            start = best[1] + len(prefix)

        # Right anchor locates where the value ends
        if suffix:
            pos = _find_anchor(ocr_norm, suffix, start)
            end = (
                pos
                if pos is not None
                else min(start + _MAX_VALUE_TOKENS, len(ocr_raw))
            )
        else:
            end = min(start + _MAX_VALUE_TOKENS, len(ocr_raw))

        # No left anchor: keep only the words directly before the right one
        if not prefix and end - start > _MAX_VALUE_TOKENS:
            start = end - _MAX_VALUE_TOKENS

        if end <= start:
            # The value may have merged with the following word through
            # an ellipsis (e.g. "Luke...I" read as one token); recover it
            # from the head of the boundary token.
            if end == start and start < len(ocr_raw):
                tok = ocr_raw[start]
                if "..." in tok or "…" in tok:
                    head = re.split(r"\.\.\.+|…", tok)[0]
                    head = head.strip(_VALUE_STRIP)
                    if head:
                        values[var] = head
            continue
        value = " ".join(ocr_raw[start:end])
        value = re.split(r"\.\.\.+|…", value)[0].strip(_VALUE_STRIP)
        if not value:
            continue
        values[var] = value

    # Fallback for variables the anchor pass could not locate, e.g. two
    # variables back to back ("as a ${CLASS}, ${PLAYER}."): align the full
    # token sequences and pair values positionally inside replacement
    # blocks whose token counts match on both sides.
    if any(v in db_text and v not in values for v in _ALL_IDENTITY_VARS):
        db_norm = [_norm_token(t) for t in db_tokens]
        # Only trust the global alignment when the OCR text is plausibly
        # the same text; the caller fuzzy-matches the segment first, but
        # keep a floor here so unrelated text cannot yield values.
        if fuzz.ratio(" ".join(db_norm), " ".join(ocr_norm)) < 50.0:
            return values
        sm = difflib.SequenceMatcher(None, db_norm, ocr_norm, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "replace":
                continue
            block = db_tokens[i1:i2]
            if not any(_VAR_TOKEN_RE.search(t) for t in block):
                continue
            ocr_block = ocr_raw[j1:j2]
            if len(block) != len(ocr_block):
                continue
            for db_tok, ocr_tok in zip(block, ocr_block):
                m = _VAR_TOKEN_RE.search(db_tok)
                if not m or m.group(0) in values:
                    continue
                value = ocr_tok.strip(_VALUE_STRIP)
                if value:
                    values[m.group(0)] = value

    # ${PLAYER_NAME} always carries the same value as ${PLAYER}
    if "${PLAYER}" in values:
        values.setdefault("${PLAYER_NAME}", values["${PLAYER}"])
    return values


def _replace_player_vars(
    text: str,
    values: Dict[str, str],
    fallbacks: Optional[Dict[str, str]] = None,
) -> str:
    """Replace identity placeholders in matched DB text.

    Parameters
    ----------
    text : str
        DB text that may contain ``${PLAYER}``, ``${RACE}``, etc.
    values : dict[str, str]
        Values extracted from the OCR text, keyed by variable name.
    fallbacks : dict[str, str], optional
        Configured character identity, used when OCR extraction failed.

    Returns
    -------
    str
        Text with all identity variables resolved.
    """
    fallbacks = fallbacks or {}
    for var in _ALL_IDENTITY_VARS:
        replacement = values.get(var) or fallbacks.get(var) or _VAR_FALLBACKS[var]
        text = text.replace(var, replacement)
    return text


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

        # Player identity fallbacks from config, used when OCR extraction
        # fails. Empty strings mean "not configured" and are ignored, so
        # replacement falls through to the generic defaults.
        _cfg = ConfigManager()
        _name = _cfg.get_str("PlayerIdentity", "character_name").strip()
        self._identity_fallbacks = {
            "${PLAYER}": _name,
            "${PLAYER_NAME}": _name,
            "${RACE}": _cfg.get_str("PlayerIdentity", "character_race").strip(),
            "${CLASS}": _cfg.get_str("PlayerIdentity", "character_class").strip(),
        }

        # Fill NPC table if empty
        cursor = self.conn.execute("SELECT COUNT(*) FROM npcs")
        count = cursor.fetchone()[0]
        if count == 0:
            self.fill_database(db_path)

        # Cache all npc names for fuzzy matching
        cursor = self.conn.execute("SELECT name_lower FROM npcs")
        self.all_names = sorted(set(row[0] for row in cursor.fetchall()))

        # Manual NPC additions / corrections (highest-priority lookups)
        self._csv_path = db_path
        self._manual_npcs = {}
        self._load_manual_additions()

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
            # Index every quest under its normalized title, not just the
            # ones where normalization changed something: the fuzzy layer
            # searches only this index, so punctuation-free titles must be
            # present here too or OCR noise on them can never be corrected.
            self._quest_by_norm[_normalize(title_lower)] = entry

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

    def _load_manual_additions(self) -> None:
        """Load manually-corrected NPCs from data/npc_manual.csv.

        These override any fuzzy/failing lookups: NPCs missing from the
        LOTRO Companion dataset (e.g. starter-instance characters) or
        with wrong race data can be corrected here. Format:

            Name,Gender,Race

        Race must be one of: dwarf, elf, hobbit, man.
        """
        import csv
        from pathlib import Path

        manual_path = Path(getattr(self, "_csv_path", "")).parent / "npc_manual.csv"
        if not manual_path.exists():
            return
        count = 0
        with open(manual_path, newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                if not row or row[0].strip().startswith("#"):
                    continue
                if len(row) < 3:
                    continue
                nm, gender, race = row[0].strip(), row[1].strip(), row[2].strip()
                nm_lower = nm.lower()
                self._manual_npcs[nm_lower] = (gender.capitalize(), race.capitalize())
                count += 1
        # Also register in the in-memory name list so fuzzy finds them
        if count:
            log.info(f"Loaded {count} manual NPC additions from npc_manual.csv")

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

        # 0. Manual additions (highest priority)
        manual = getattr(self, "_manual_npcs", {}).get(name.lower().strip())
        if manual:
            gender, race = manual
            return gender, race, name.strip()

        # 1. Exact match
        cursor = self.conn.execute(
            "SELECT gender, race, name FROM npcs WHERE name_lower = ?",
            (name.lower().strip(),),
        )
        row = cursor.fetchone()

        if row:
            return row[0], row[1], row[2]

        query = name.lower().strip()

        # Token-aware fuzzy matching. Plain fuzz.ratio lets a shared title
        # word ("Foreman Otur" -> "Foreman Rosethorn", 75.9) override the
        # actually-identifying tokens. Score = 0.5*ratio + 0.5*token_set_ratio,
        # and the candidate's surname token must fuzzily match the query's
        # surname token when both have one.
        query_tokens = query.split()
        query_surname = query_tokens[-1] if len(query_tokens) > 1 else None

        candidates = process.extract(
            query,
            self.all_names,
            scorer=fuzz.ratio,
            score_cutoff=60.0,
            limit=20,
        )
        best = None
        for cand_name, cand_score, _ in candidates:
            cand_tokens = cand_name.split()
            cand_surname = cand_tokens[-1] if len(cand_tokens) > 1 else None
            if query_surname and cand_surname:
                surname_score = fuzz.ratio(query_surname, cand_surname)
                if surname_score < 70.0:
                    # Surnames don't correspond - different NPC
                    continue
            combined = 0.5 * cand_score + 0.5 * fuzz.token_set_ratio(query, cand_name)
            if best is None or combined > best[1]:
                best = (cand_name, combined)

        if best:
            best_match = best[0]
            cursor = self.conn.execute(
                "SELECT gender, race, name FROM npcs WHERE name_lower = ?",
                (best_match,),
            )
            row = cursor.fetchone()
            if row:
                log.info(f"Fuzzy match: '{name}' -> '{row[2]}' ({best[1]:.0f})")
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

    def resolve_quest_id_best(self, candidates: List[str]):
        """Resolve the best-matching quest from several OCR title candidates.

        Different threshold passes read dim/bright title bars differently;
        each candidate is resolved against the database and ranked by the
        fuzzy score it achieved, so the most plausible reading wins.

        Parameters
        ----------
        candidates : list[str]
            OCR readings of the quest title (e.g. from
            ``run_title_ocr_candidates``).

        Returns
        -------
        tuple
            (quest_id, canonical_title) or (None, None).
        """
        best = (None, None, -1.0)
        for cand in candidates:
            if not cand:
                continue
            quest_id, title = self._resolve_quest_id(cand)
            if not quest_id:
                continue
            score = fuzz.ratio(
                self._normalize(cand.lower()), self._normalize(title.lower())
            )
            if score > best[2]:
                best = (quest_id, title, score)
        return best[0], best[1]

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

        if best_score < 0.5 or best_idx < 0:
            if best_score >= 0.4:
                # Near-miss: worth seeing in logs to tune the threshold
                log.info(
                    f"Quest DB: near-miss for '{canonical_title}' "
                    f"(best={best_score:.1%}, below 0.5 floor)"
                )
            else:
                log.info(
                    f"Quest DB: no segment matched '{canonical_title}' "
                    f"(best={best_score:.1%})"
                )
            return None

        text_type, npc_name, db_text = segments[best_idx]

        # Extract identity values (name/race/class) from OCR and
        # resolve variables, falling back to configured character identity
        var_values = _extract_var_values(ocr_body, db_text)
        clean_text = _replace_player_vars(db_text, var_values, self._identity_fallbacks)
        player_name = (
            var_values.get("${PLAYER}")
            or self._identity_fallbacks.get("${PLAYER}")
            or "Traveler"
        )

        is_dialogue = text_type in ("bestower", "dialog")

        log.info(
            f"Quest DB match: '{canonical_title}' "
            f"[{text_type}] score={best_score:.1%} "
            f"player={player_name} vars={var_values or '-'}"
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
