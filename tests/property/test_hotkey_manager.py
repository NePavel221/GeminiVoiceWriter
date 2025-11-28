"""Property-based tests for HotkeyManager.

**Feature: gemini-voice-writer-v2, Properties 4, 6**
**Validates: Requirements 4.1, 4.3**
"""
import pytest
from hypothesis import given, strategies as st, settings, assume

from core.hotkey_manager import HotkeyManager


# Strategy for valid modifier keys
modifier_strategy = st.sampled_from(['ctrl', 'alt', 'shift', 'windows'])

# Strategy for valid trigger keys
trigger_key_strategy = st.one_of(
    st.sampled_from(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
                     'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
                     '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']),
    st.sampled_from(['f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
                     'space', 'enter', 'tab', 'escape'])
)


@given(
    modifiers=st.lists(modifier_strategy, min_size=0, max_size=3, unique=True),
    trigger=trigger_key_strategy
)
@settings(max_examples=100)
def test_hotkey_validation_valid(modifiers, trigger):
    """
    **Feature: gemini-voice-writer-v2, Property 6: Hotkey Validation**
    
    For any hotkey string with valid modifier+key combinations,
    the validation function SHALL return True.
    """
    # Build hotkey string
    parts = modifiers + [trigger]
    hotkey = '+'.join(parts)
    
    valid, error = HotkeyManager.validate_hotkey(hotkey)
    
    assert valid is True, f"Valid hotkey '{hotkey}' should pass validation, got error: {error}"


@given(hotkey=st.text(min_size=1, max_size=30))
@settings(max_examples=100)
def test_hotkey_validation_consistency(hotkey):
    """Test that validation always returns consistent tuple format."""
    valid, error = HotkeyManager.validate_hotkey(hotkey)
    
    assert isinstance(valid, bool), "First return value should be bool"
    assert isinstance(error, str), "Second return value should be string"
    
    if valid:
        assert error == "", "Valid hotkey should have empty error message"
    else:
        assert len(error) > 0, "Invalid hotkey should have error message"


@given(invalid_key=st.text(min_size=2, max_size=10).filter(
    lambda x: x.lower() not in HotkeyManager.VALID_MODIFIERS and 
              x.lower() not in HotkeyManager.VALID_SPECIAL_KEYS and
              not (len(x) == 1 and x.isalnum())
))
@settings(max_examples=50)
def test_hotkey_validation_rejects_invalid_keys(invalid_key):
    """Test that invalid keys are rejected."""
    assume('+' not in invalid_key)  # Avoid confusing the parser
    
    hotkey = f"ctrl+{invalid_key}"
    valid, error = HotkeyManager.validate_hotkey(hotkey)
    
    assert valid is False, f"Invalid key '{invalid_key}' should be rejected"


def test_hotkey_validation_empty():
    """Test that empty hotkey is rejected."""
    valid, error = HotkeyManager.validate_hotkey("")
    assert valid is False
    assert "empty" in error.lower()
    
    valid, error = HotkeyManager.validate_hotkey("   ")
    assert valid is False


def test_hotkey_validation_modifiers_only():
    """Test that modifiers-only hotkey is rejected."""
    valid, error = HotkeyManager.validate_hotkey("ctrl+alt")
    assert valid is False
    assert "non-modifier" in error.lower()


def test_hotkey_validation_multiple_triggers():
    """Test that multiple trigger keys are rejected."""
    valid, error = HotkeyManager.validate_hotkey("ctrl+a+b")
    assert valid is False
    assert "one trigger" in error.lower()


def test_hotkey_manager_initialization():
    """Test HotkeyManager initializes correctly."""
    manager = HotkeyManager()
    
    assert manager.mode == "toggle"
    assert manager.hotkey is None
    assert manager.is_running is False


def test_hotkey_manager_mode_setting():
    """Test mode setting."""
    manager = HotkeyManager(mode="toggle")
    assert manager.mode == "toggle"
    
    manager.set_mode("hold")
    assert manager.mode == "hold"
    
    manager.set_mode("toggle")
    assert manager.mode == "toggle"


def test_hotkey_manager_invalid_mode():
    """Test that invalid mode raises error."""
    manager = HotkeyManager()
    
    with pytest.raises(ValueError):
        manager.set_mode("invalid")


def test_toggle_mode_state_machine():
    """
    **Feature: gemini-voice-writer-v2, Property 4: Toggle Mode State Machine**
    
    Test that toggle mode alternates state with each press.
    """
    manager = HotkeyManager(mode="toggle")
    
    press_count = 0
    
    def on_press():
        nonlocal press_count
        press_count += 1
    
    manager.on_press = on_press
    
    # Simulate multiple presses by calling internal method
    # (We can't actually press keys in tests)
    manager._last_trigger_time = 0  # Reset cooldown
    manager._on_toggle_press()
    assert press_count == 1
    
    manager._last_trigger_time = 0
    manager._on_toggle_press()
    assert press_count == 2
    
    manager._last_trigger_time = 0
    manager._on_toggle_press()
    assert press_count == 3


def test_cooldown_prevents_double_trigger():
    """Test that cooldown prevents rapid double triggering."""
    manager = HotkeyManager(mode="toggle")
    
    press_count = 0
    
    def on_press():
        nonlocal press_count
        press_count += 1
    
    manager.on_press = on_press
    
    # First press
    manager._on_toggle_press()
    assert press_count == 1
    
    # Immediate second press should be blocked by cooldown
    manager._on_toggle_press()
    assert press_count == 1  # Still 1, blocked by cooldown
