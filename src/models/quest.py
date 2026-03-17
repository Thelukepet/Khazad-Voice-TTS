"""
Quest text models representing OCR'd quest content and individual lines.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from enum import Enum, auto


class TextSourceType(Enum):
    """Source of the text content."""
    OCR = auto()
    WIKI = auto()
    HYBRID = auto()


@dataclass
class QuestTextLine:
    """
    A single line/segment of quest text.

    Attributes
    ----------
    text : str
        The actual text content.
    line_number : int
        Sequential line number (0-indexed).
    source : TextSourceType
        Where this text came from (OCR, Wiki, or Hybrid).
    confidence : float, optional
        Confidence score for wiki matches (0-100).
    is_quoted : bool, optional
        # TODO: Future feature - indicates if text is spoken by NPC (quoted)
        # vs narrated by the system. When True, use NPC voice.
        # When False, use narrator voice.
        # Currently not implemented - defaults to False.
    """
    text: str
    line_number: int
    source: TextSourceType = TextSourceType.OCR
    confidence: Optional[float] = None
    is_quoted: bool = False  # TODO: Not yet implemented

    def __repr__(self) -> str:
        return (
            f"QuestTextLine(line={self.line_number}, source={self.source.name}, "
            f"text='{self.text[:40]}...')",
        )


@dataclass
class QuestText:
    """
    Complete quest text with metadata and parsed lines.

    Attributes
    ----------
    timestamp : datetime
        When the quest text was captured.
    raw_ocr_text : str
        The raw OCR output before processing.
    lines : List[QuestTextLine]
        Parsed individual lines.
    npc_name : str, optional
        Name of the NPC giving the quest.
    quest_title : str, optional
        Title of the quest.
    source_label : str
        Human-readable source description (e.g., "Wiki (Bestowal, 85.3%)").
    """
    timestamp: datetime
    raw_ocr_text: str
    lines: List[QuestTextLine] = field(default_factory=list)
    npc_name: Optional[str] = None
    quest_title: Optional[str] = None
    source_label: str = "OCR"

    def get_line(self, index: int) -> Optional[QuestTextLine]:
        """
        Retrieve a specific line by index.

        Parameters
        ----------
        index : int
            The line index (0-based).

        Returns
        -------
        QuestTextLine or None
            The line if found, None otherwise.
        """
        if 0 <= index < len(self.lines):
            return self.lines[index]
        return None

    def get_full_text(self) -> str:
        """
        Return concatenated full text.

        Returns
        -------
        str
            All lines joined with spaces.
        """
        return " ".join(line.text for line in self.lines)

    # TODO: Future feature - separate quoted vs narrator lines
    def get_quoted_lines(self) -> List[QuestTextLine]:
        """
        Return only lines marked as NPC dialogue (quoted).
        # TODO: Not yet implemented - will return empty list until
        # quote detection logic is added to OCR/wiki processing.
        """
        return [line for line in self.lines if line.is_quoted]

    def get_narrator_lines(self) -> List[QuestTextLine]:
        """
        Return only lines marked as narrator text (non-quoted).
        # TODO: Not yet implemented - will return all lines until
        # quote detection logic is added to OCR/wiki processing.
        """
        return [line for line in self.lines if not line.is_quoted]

    def __repr__(self) -> str:
        return (
            f"QuestText(npc='{self.npc_name}', title='{self.quest_title}', "
            f"lines={len(self.lines)}, source={self.source_label})"
        )
