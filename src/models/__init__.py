"""
Domain models for Khazad-Voice TTS.

This module contains all dataclasses representing the core entities
of the quest narration system.
"""

from .npc import NPC
from .quest import QuestText, QuestTextLine, TextSourceType
from .voice import VoiceSelection

__all__ = ["NPC", "QuestText", "QuestTextLine", "TextSourceType", "VoiceSelection"]
