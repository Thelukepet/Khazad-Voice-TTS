"""
Unit tests for the text splitter module.
"""
import unittest
from src.tts.text_splitter import split_text, TextSegment


class TestTextSplitter(unittest.TestCase):
    """Test cases for the text splitter functionality."""
    
    def test_standalone_dialogue(self):
        """Test standalone dialogue is labeled as dialogue."""
        text = "\"Hello!\""
        segments = split_text(text)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].text, "Hello!")
        self.assertEqual(segments[0].segment_type, "dialogue")
    
    def test_standalone_narration(self):
        """Test standalone narration is labeled as narration."""
        text = "The dwarf looks at you."
        segments = split_text(text)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].text, "The dwarf looks at you.")
        self.assertEqual(segments[0].segment_type, "narration")
    
    def test_mixed_content(self):
        """Test mixed content splits into separate segments."""
        text = "The dwarf says, \"Hello!\""
        segments = split_text(text)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].text, "The dwarf says,")
        self.assertEqual(segments[0].segment_type, "narration")
        self.assertEqual(segments[1].text, "Hello!")
        self.assertEqual(segments[1].segment_type, "dialogue")
    
    def test_empty_string(self):
        """Test empty string returns empty list."""
        segments = split_text("")
        self.assertEqual(len(segments), 0)
    
    def test_whitespace_only(self):
        """Test whitespace-only string returns empty list."""
        segments = split_text("   ")
        self.assertEqual(len(segments), 0)
    
    def test_curly_quotes(self):
        """Test curly quotes are recognized."""
        text = "He said, \"Hello!\""
        segments = split_text(text)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].segment_type, "narration")
        self.assertEqual(segments[1].segment_type, "dialogue")
    
    def test_single_quotes(self):
        """Test single quotes are recognized."""
        text = "He said, 'Hello!'"
        segments = split_text(text)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].segment_type, "narration")
        self.assertEqual(segments[1].segment_type, "dialogue")
    
    def test_multiple_dialogues(self):
        """Test multiple dialogue segments."""
        text = "He said, \"Hello!\" and \"Goodbye!\""
        segments = split_text(text)
        self.assertEqual(len(segments), 4)
        self.assertEqual(segments[0].segment_type, "narration")
        self.assertEqual(segments[1].segment_type, "dialogue")
        self.assertEqual(segments[2].segment_type, "narration")
        self.assertEqual(segments[3].segment_type, "dialogue")
    
    def test_dialogue_only(self):
        """Test text with only dialogue."""
        text = "\"Hello!\""
        segments = split_text(text)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].segment_type, "dialogue")
    
    def test_narration_only(self):
        """Test text with only narration."""
        text = "The dwarf walks away."
        segments = split_text(text)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].segment_type, "narration")
    
    def test_complex_mixed(self):
        """Test complex mixed content."""
        text = "The dwarf says, \"Hello!\" You reply, \"Hi!\" and he says, \"Goodbye!\""
        segments = split_text(text)
        self.assertEqual(len(segments), 6)
        self.assertEqual(segments[0].segment_type, "narration")
        self.assertEqual(segments[1].segment_type, "dialogue")
        self.assertEqual(segments[2].segment_type, "narration")
        self.assertEqual(segments[3].segment_type, "dialogue")
        self.assertEqual(segments[4].segment_type, "narration")
        self.assertEqual(segments[5].segment_type, "dialogue")


if __name__ == '__main__':
    unittest.main()
