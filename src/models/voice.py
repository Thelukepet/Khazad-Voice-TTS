"""
Voice selection model representing voice assignment for NPCs.
"""

from dataclasses import dataclass


@dataclass
class VoiceSelection:
    """
    Result of voice selection logic for an NPC.

    Attributes
    ----------
    voice_id : str
        The internal voice ID used by the TTS generator.
    category : str
        The voice category (e.g., 'dwarf_male') for memory caching.
    npc_name : str
        Name of the NPC this voice is assigned to.
    race : str
        The race of the NPC.
    gender : str
        The gender of the NPC.
    is_default : bool
        Whether this is a default/fallback voice (e.g., Narrator).
    """
    voice_id: str
    category: str
    npc_name: str
    race: str
    gender: str
    is_default: bool = False

    def __repr__(self) -> str:
        return (
            f"VoiceSelection(npc='{self.npc_name}', voice='{self.voice_id}', "
            f"category='{self.category}', default={self.is_default})"
        )
