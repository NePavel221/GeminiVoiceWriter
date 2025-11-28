"""Property-based tests for TextInjector.

**Feature: gemini-voice-writer-v2, Properties 10, 11**
**Validates: Requirements 6.2, 6.5**
"""
import pytest
from hypothesis import given, strategies as st, settings, assume

import pyperclip

from core.text_injector import TextInjector


@given(text=st.text(
    min_size=0, 
    max_size=500,
    alphabet=st.characters(blacklist_characters='\x00')  # Exclude null byte
))
@settings(max_examples=100)
def test_clipboard_roundtrip(text):
    """
    **Feature: gemini-voice-writer-v2, Property 10: Clipboard Round-Trip**
    
    For any text string (excluding null bytes), copying to clipboard and reading back 
    SHALL return the identical string.
    """
    injector = TextInjector()
    
    # Copy to clipboard
    success = injector.copy_to_clipboard(text)
    assert success is True, "copy_to_clipboard should succeed"
    
    # Read back
    retrieved = TextInjector.get_clipboard_content()
    
    assert retrieved == text, f"Clipboard round-trip failed: '{repr(text)}' != '{repr(retrieved)}'"


@given(text=st.text(
    min_size=1, 
    max_size=100,
    alphabet=st.characters(
        whitelist_categories=('L', 'N', 'P', 'S', 'Z'),
        whitelist_characters='\n\t'
    )
))
@settings(max_examples=50)
def test_special_character_clipboard(text):
    """
    **Feature: gemini-voice-writer-v2, Property 11: Special Character Injection**
    
    For any text containing special characters (unicode, newlines, tabs),
    the clipboard operations SHALL correctly handle all characters without corruption.
    """
    injector = TextInjector()
    
    # Copy to clipboard
    success = injector.copy_to_clipboard(text)
    assert success is True
    
    # Read back
    retrieved = TextInjector.get_clipboard_content()
    
    assert retrieved == text, \
        f"Special characters corrupted: expected '{repr(text)}', got '{repr(retrieved)}'"


def test_text_injector_initialization():
    """Test TextInjector initializes correctly."""
    injector = TextInjector()
    assert injector.typing_speed == 50
    
    injector2 = TextInjector(typing_speed=100)
    assert injector2.typing_speed == 100


def test_text_injector_speed_setting():
    """Test typing speed setting."""
    injector = TextInjector()
    
    injector.set_typing_speed(100)
    assert injector.typing_speed == 100
    
    injector.set_typing_speed(0)
    assert injector.typing_speed == 0
    
    # Negative should be clamped to 0
    injector.set_typing_speed(-10)
    assert injector.typing_speed == 0


def test_empty_text_injection():
    """Test that empty text injection succeeds."""
    injector = TextInjector()
    
    result = injector.inject("")
    assert result is True


def test_clipboard_copy_success():
    """Test basic clipboard copy."""
    injector = TextInjector()
    
    test_text = "Hello, World!"
    success = injector.copy_to_clipboard(test_text)
    
    assert success is True
    assert pyperclip.paste() == test_text


def test_unicode_clipboard():
    """Test unicode text in clipboard."""
    injector = TextInjector()
    
    # Various unicode characters
    test_texts = [
        "Привет мир",  # Russian
        "你好世界",     # Chinese
        "مرحبا بالعالم",  # Arabic
        "🎉🚀💻",      # Emoji
        "café résumé naïve",  # Accented
    ]
    
    for text in test_texts:
        success = injector.copy_to_clipboard(text)
        assert success is True, f"Failed to copy: {text}"
        
        retrieved = pyperclip.paste()
        assert retrieved == text, f"Unicode mismatch: {text} != {retrieved}"


def test_newlines_and_tabs():
    """Test text with newlines and tabs."""
    injector = TextInjector()
    
    test_text = "Line 1\nLine 2\n\tIndented\n\t\tDouble indent"
    
    success = injector.copy_to_clipboard(test_text)
    assert success is True
    
    retrieved = pyperclip.paste()
    assert retrieved == test_text


def test_get_clipboard_content():
    """Test static clipboard getter."""
    test_text = "Test content"
    pyperclip.copy(test_text)
    
    content = TextInjector.get_clipboard_content()
    assert content == test_text
