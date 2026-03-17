"""
Text splitter utility for distinguishing between narration and dialogue in text.
"""
import re
from typing import List


class TextSegment:
    """Represents a segment of text with a label indicating its type."""
    
    def __init__(self, text: str, segment_type: str):
        self.text = text
        self.segment_type = segment_type  # "narration" or "dialogue"
    
    def __repr__(self):
        return f"TextSegment(text='{self.text}', type='{self.segment_type}')"


def split_text(text: str) -> List[TextSegment]:
    """
    Split text into narration and dialogue segments.
    
    Args:
        text: Input text to split
        
    Returns:
        List of TextSegment objects labeled as "narration" or "dialogue"
    """
    if not text or not text.strip():
        return []
    
    # Define quote patterns (straight, curly, angle quotes)
    quote_patterns = [
        r'"([^"]*)"',  # "text"
        r"'([^']*)'",  # 'text'
        r'“([^”]*)”',  # "text"
        r'«([^»]*)»',  # «text»
        r'„([^“]*)“',  # „text"
        r'‹([^›]*)›',  # ‹text›
    ]
    
    segments = []
    remaining_text = text
    
    # Find all quoted text first
    all_matches = []
    
    # Collect all matches from all patterns
    for pattern in quote_patterns:
        matches = list(re.finditer(pattern, remaining_text))
        all_matches.extend(matches)
    
    # Sort matches by position
    all_matches.sort(key=lambda m: m.start())
    
    # Process matches in order
    last_end = 0
    for match in all_matches:
        # Add narration before the quote
        start = match.start()
        if start > last_end:
            narration_text = remaining_text[last_end:start].strip()
            if narration_text:
                segments.append(TextSegment(narration_text, "narration"))
        
        # Add dialogue (the quoted text)
        dialogue_text = match.group(1).strip()
        if dialogue_text:
            segments.append(TextSegment(dialogue_text, "dialogue"))
        
        # Update last_end
        last_end = match.end()
    
    # Add any remaining text as narration
    if last_end < len(remaining_text):
        remaining_text = remaining_text[last_end:]
        if remaining_text.strip():
            segments.append(TextSegment(remaining_text.strip(), "narration"))
    
    return segments


def split_text_to_dict(text: str) -> List[tuple]:
    """
    Split text and return as list of (text, type) tuples for backward compatibility.
    
    Args:
        text: Input text to split
        
    Returns:
        List of tuples (text, segment_type)
    """
    segments = split_text(text)
    return [(seg.text, seg.segment_type) for seg in segments]
