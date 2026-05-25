# Imports

# > Standard library
import csv
import difflib
import sqlite3
from typing import Dict, List, Optional, Tuple


# > Local dependencies
from .utils import setup_logger
from .config.ConfigManager import ConfigManager

log = setup_logger(__name__)


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

        # Fill if empty
        cursor = self.conn.execute("SELECT COUNT(*) FROM npcs")
        count = cursor.fetchone()[0]
        if count == 0:
            self.fill_database(db_path)

        # Cache all npc names for fuzzy matching
        cursor = self.conn.execute("SELECT name_lower FROM npcs")
        self.all_names = sorted(set(row[0] for row in cursor.fetchall()))

        log.info(f"Database ready: {len(self.all_names)} NPCs loaded")

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

        # 2. Fuzzy match using difflib (similarity > 60%)
        close_matches = difflib.get_close_matches(
            name.lower().strip(), self.all_names, n=1, cutoff=0.6
        )

        if close_matches:
            best_match = close_matches[0]
            cursor = self.conn.execute(
                "SELECT gender, race, name FROM npcs WHERE name_lower = ?",
                (best_match,),
            )
            row = cursor.fetchone()
            if row:
                log.info(f"Fuzzy match: '{name}' -> '{row[2]}'")
                return row[0], row[1], row[2]

        return None, None, name

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
