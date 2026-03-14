# Models Module

This module contains all domain models (dataclasses) for the Khazad-Voice TTS system.

## Models

### `NPC`

Represents a non-player character encountered during quest narration.

```python
@dataclass
class NPC:
    name: str
    race: Optional[str] = None
    gender: Optional[str] = None
    voice_id: Optional[str] = None
    voice_category: Optional[str] = None
    last_seen: Optional[datetime] = None
    matched_name: Optional[str] = None
```

### `QuestText`

Complete quest text with metadata and parsed lines.

```python
@dataclass
class QuestText:
    timestamp: datetime
    raw_ocr_text: str
    lines: List[QuestTextLine]
    npc_name: Optional[str] = None
    quest_title: Optional[str] = None
    source_label: str = "OCR"
```

### `QuestTextLine`

A single line/segment of quest text.

```python
@dataclass
class QuestTextLine:
    text: str
    line_number: int
    source: TextSourceType = TextSourceType.OCR
    confidence: Optional[float] = None
    is_quoted: bool = False  # TODO: Not yet implemented
```

### `VoiceSelection`

Result of voice selection logic for an NPC.

```python
@dataclass
class VoiceSelection:
    voice_id: str
    category: str
    npc_name: str
    race: str
    gender: str
    is_default: bool = False
```

### `TextSourceType` (Enum)

Source of the text content.

- `OCR` - Text from OCR
- `WIKI` - Text from Wiki lookup
- `HYBRID` - Mixed source

## Future Feature: Quote Detection

The `QuestTextLine.is_quoted` flag is reserved for future quote detection logic.

When implemented:
- `is_quoted=True` → Use NPC voice
- `is_quoted=False` → Use narrator voice

This will allow different voices for NPC dialogue vs narrator text.

## Usage Example

```python
from src.models import QuestText, QuestTextLine, NPC, VoiceSelection

# Create quest text
quest = QuestText(
    timestamp=datetime.now(),
    raw_ocr_text="Greetings traveler...",
    lines=[
        QuestTextLine(text="Greetings traveler!", line_number=0),
        QuestTextLine(text="I have a task for you.", line_number=1)
    ],
    npc_name="Thranduil",
    source_label="OCR"
)

# Access individual lines
first_line = quest.get_line(0)
print(first_line.text)  # "Greetings traveler!"

# Get full text
print(quest.get_full_text())
```
