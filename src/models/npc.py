"""
NPC model representing a non-player character in the game.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class NPC:
    """
    Represents an NPC character encountered during quest narration.

    Attributes
    ----------
    name : str
        The OCR-detected name of the NPC.
    race : str, optional
        The race of the NPC (e.g., 'Elf', 'Dwarf', 'Man').
        None if unknown/default.
    gender : str, optional
        The gender of the NPC (e.g., 'Male', 'Female').
        None if unknown/default.
    voice_id : str, optional
        The selected voice ID for this NPC.
    voice_category : str, optional
        The voice category (e.g., 'dwarf_male') used for memory.
    last_seen : datetime, optional
        Timestamp of last encounter.
    matched_name : str, optional
        The corrected name if fuzzy matching was used.
    """
    name: str
    race: Optional[str] = None
    gender: Optional[str] = None
    voice_id: Optional[str] = None
    voice_category: Optional[str] = None
    last_seen: Optional[datetime] = None
    matched_name: Optional[str] = None

    def is_unknown(self) -> bool:
        """Check if NPC has unknown race/gender (defaults to narrator)."""
        return self.race is None or self.gender is None

    def has_voice(self) -> bool:
        """Check if a voice has been assigned."""
        return self.voice_id is not None

    def __repr__(self) -> str:
        return (
            f"NPC(name='{self.name}', race='{self.race}', gender='{self.gender}', "
            f"voice_id='{self.voice_id}')"
        )
