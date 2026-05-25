"""
Quest text models representing OCR'd quest content and individual lines.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Iterator, List, Optional


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
    is_quoted : bool
        Whether this line is NPC dialogue (in quotes).
        When True, use NPC voice. When False, use narrator voice.
    """

    text: str
    line_number: int
    source: TextSourceType = TextSourceType.OCR
    confidence: Optional[float] = None
    is_quoted: bool = False

    def __repr__(self) -> str:
        return (
            f"QuestTextLine(line={self.line_number}, source={self.source.name}, "
            f"text='{self.text[:40]}...')"
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

    def __str__(self) -> str:
        return (
            f"QuestText(npc='{self.npc_name}', title='{self.quest_title}', "
            f"lines={len(self.lines)}, source='{self.source_label}')"
        )

    def __repr__(self) -> str:
        return (
            f"QuestText(npc='{self.npc_name!r}', title='{self.quest_title!r}', "
            f"lines={len(self.lines)}, source={self.source_label!r})"
        )

    def __getitem__(self, index: int | slice) -> QuestTextLine | List[QuestTextLine]:
        return self.lines[index]

    def __len__(self) -> int:
        return len(self.lines)

    def __iter__(self) -> Iterator[QuestTextLine]:
        return iter(self.lines)

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

    def get_quoted_lines(self) -> List[QuestTextLine]:
        """
        Return only lines marked as NPC dialogue (quoted).
        """
        return [line for line in self.lines if line.is_quoted]

    def get_narrator_lines(self) -> List[QuestTextLine]:
        """
        Return only lines marked as narrator text (non-quoted).
        """
        return [line for line in self.lines if not line.is_quoted]
