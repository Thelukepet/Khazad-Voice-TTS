# Imports

# > Standard Library
from typing import Tuple, Optional, List, Dict
import difflib

# > Third-party Libraries
import pandas as pd

# > Local Dependencies
from .utils import setup_logger
from .config import NPC_DATA_PATH

log = setup_logger(__name__)


class NPCDatabase:
    """
    Manages loading NPC data (CSV) and performing exact or fuzzy name matching.

    Parameters
    ----------
    csv_path : str
        Path to the `npc_data.csv` file.
    """

    def __init__(self, csv_path: str = str(NPC_DATA_PATH)):
        self.data = None
        self.all_names = []
        try:
            self.data = pd.read_csv(csv_path)
            # Create a lowercase column for easier searching
            self.data["Name_Lower"] = (
                self.data["Name"].astype(str).str.lower().str.strip()
            )
            self.all_names = sorted(self.data["Name"].dropna().unique().tolist())
            log.info(f"✅ Database loaded: {len(self.data)} NPCs found.")
        except Exception as e:
            log.error(f"❌ Failed to load database: {e}")

    def get_random_npcs(self, count: int = 10) -> List[Dict]:
        """
        Returns a random sample of NPCs from the database.

        Parameters
        ----------
        count : int, optional
            Number of NPCs to retrieve (default is 10).

        Returns
        -------
        List[Dict]
            A list of dictionaries representing NPC rows.
        """
        if self.data is None or self.data.empty:
            return []
        sample_size = min(count, len(self.data))
        sample = self.data.sample(n=sample_size)
        return sample.to_dict("records")

    def lookup(self, name: str) -> Tuple[Optional[str], Optional[str], str]:
        """
        Attempts to find an NPC by name using exact then fuzzy matching.

        Parameters
        ----------
        name : str
            The name to look up (e.g., from OCR).

        Returns
        -------
        Tuple[Optional[str], Optional[str], str]
            Returns (Gender, Race, RealName).
            Gender/Race will be None if no match is found.
            RealName returns the corrected name if matched, or the original input if not.
        """
        if self.data is None or not name:
            return None, None, name

        name_clean = name.lower().strip()

        # 1. Exact Match
        match = self.data[self.data["Name_Lower"] == name_clean]
        if not match.empty:
            row = match.iloc[0]
            return row["Gender"], row["Race"], row["Name"]

        # 2. Fuzzy Match (using difflib)
        # Finds closest match if similarity is > 60%
        close_matches = difflib.get_close_matches(name, self.all_names, n=1, cutoff=0.6)

        if close_matches:
            best_match = close_matches[0]
            match = self.data[self.data["Name"] == best_match]
            if not match.empty:
                row = match.iloc[0]
                log.info(f"🔍 Fuzzy Match: '{name}' -> '{best_match}'")
                return row["Gender"], row["Race"], best_match

        return None, None, name
