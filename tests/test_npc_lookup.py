"""Tests for NPC name lookup: surname-token matching + manual additions.

Regression case: "Foreman Otur" (a starter-instance Dwarf) fuzzy-matched to
"Foreman Rosethorn" (a Man) at 75.9 because they share the title word
"Foreman". The fix requires surname correspondence and blends
token_set_ratio into the score.
"""

import sys
import types
from pathlib import Path

import pytest

# Stub heavy optional deps before import - but never shadow the real
# package when it is installed, otherwise later imports of src.db_sqlite
# would receive the empty stub and fail.
try:
    import rapidfuzz  # noqa: F401
except ImportError:
    for mod_name in ("rapidfuzz",):
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)


class _StubDB:
    """Minimal stand-in for NPCDatabaseSQLite exposing the patched logic."""

    def __init__(self, names, manual=None):
        self.names = list(names)  # original casing, for the name column
        self.all_names = sorted(n.lower() for n in names)
        self._manual_npcs = manual or {}


def _run_lookup_patch(db, name):
    """Import the real lookup() implementation from db_sqlite."""
    # Import the module with heavy parts stubbed
    import importlib

    src_path = Path(__file__).resolve().parents[1] / "src" / "db_sqlite.py"
    code = compile(src_path.read_text(encoding="utf-8"), str(src_path), "exec")

    from rapidfuzz import fuzz, process  # real rapidfuzz in test env

    ns = {}
    # execute only the needed helpers by exec'ing module then using its class
    try:
        module = importlib.import_module("src.db_sqlite")
    except Exception:
        pytest.skip("full import needs project deps")

    instance = module.NPCDatabaseSQLite.__new__(module.NPCDatabaseSQLite)
    instance.all_names = db.all_names
    instance._manual_npcs = db._manual_npcs

    # Real in-memory DB so the exact-match query (and the final row fetch
    # after a fuzzy hit) work; lookup() queries SQL before any fuzzy logic.
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE npcs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT NOT NULL, name_lower TEXT NOT NULL, "
        "gender TEXT, race TEXT, url TEXT)"
    )
    conn.executemany(
        "INSERT INTO npcs (name, name_lower) VALUES (?, ?)",
        [(n, n.lower()) for n in db.names],
    )
    instance.conn = conn

    # Bind lookup as if it were an unbound method on our stub
    lookup_fn = module.NPCDatabaseSQLite.lookup.__get__(instance)
    return lookup_fn(name)


class TestSurnameTokenMatching:
    def test_foreman_otur_does_not_match_foreman_rosethorn(self):
        """Shared title word must not override the surname mismatch."""
        db = _StubDB(
            ["Foreman Rosethorn", "Otur Nimblehands", "Bart Rosethorn"]
        )
        gender, race, matched = _run_lookup_patch(db, "Foreman Otur")
        assert matched != "Foreman Rosethorn"
        assert gender is None  # unknown -> engine defaults, no wrong identity

    def test_near_miss_with_matching_surname_still_matches(self):
        """OCR noise in an otherwise-correct name should still resolve."""
        db = _StubDB(["Gormr Doursmith"])
        gender, race, matched = _run_lookup_patch(db, "Gormr Doursmitb")
        assert matched == "Gormr Doursmith"


class TestManualAdditions:
    def test_manual_npc_wins_over_fuzzy(self):
        """npc_manual.csv entries take priority over everything else."""
        db = _StubDB(
            ["Foreman Rosethorn"],
            manual={"foreman otur": ("Male", "Dwarf")},
        )
        gender, race, matched = _run_lookup_patch(db, "Foreman Otur")
        assert (gender, race) == ("Male", "Dwarf")
        assert matched == "Foreman Otur"
