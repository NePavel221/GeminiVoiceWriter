"""Property-based tests for transcription providers.

**Feature: gemini-voice-writer-v2, Properties 7, 9, 13**
**Validates: Requirements 5.1, 5.2, 5.3, 5.6, 7.5**
"""
import pytest
from hypothesis import given, strategies as st, settings

from services import (
    ProviderFactory, 
    TranscriptionProvider,
    GeminiProvider, 
    OpenRouterProvider, 
    OpenAIProvider
)
from services.base import TranscriptionError


@given(provider_name=st.sampled_from(["gemini", "openrouter", "openai"]))
@settings(max_examples=100)
def test_provider_factory_correctness(provider_name):
    """
    **Feature: gemini-voice-writer-v2, Property 7: Provider Factory Correctness**
    
    For any valid provider name ("gemini", "openrouter", "openai"), 
    the ProviderFactory SHALL return an instance of the corresponding provider class.
    """
    expected_classes = {
        "gemini": GeminiProvider,
        "openrouter": OpenRouterProvider,
        "openai": OpenAIProvider,
    }
    
    provider = ProviderFactory.create(provider_name, api_key="test_key")
    
    assert isinstance(provider, TranscriptionProvider), \
        f"Provider should be instance of TranscriptionProvider"
    assert isinstance(provider, expected_classes[provider_name]), \
        f"Provider for '{provider_name}' should be {expected_classes[provider_name].__name__}"
    assert provider.PROVIDER_NAME == provider_name, \
        f"Provider name should be '{provider_name}'"


@given(invalid_name=st.text(min_size=1, max_size=20).filter(
    lambda x: x.lower() not in ["gemini", "openrouter", "openai"]
))
@settings(max_examples=50)
def test_provider_factory_rejects_invalid(invalid_name):
    """Test that factory rejects invalid provider names."""
    with pytest.raises(ValueError) as exc_info:
        ProviderFactory.create(invalid_name, api_key="test_key")
    
    assert "Unknown provider" in str(exc_info.value)


@given(
    error_code=st.sampled_from([400, 401, 403, 404, 429, 500, 503]),
    error_message=st.text(min_size=1, max_size=100)
)
@settings(max_examples=100)
def test_error_message_formatting(error_code, error_message):
    """
    **Feature: gemini-voice-writer-v2, Property 9: Error Message Formatting**
    
    For any API error with code and message, the formatted user-friendly error 
    SHALL contain both the error code and a suggestion for resolution.
    """
    formatted = TranscriptionProvider.format_error(error_code, error_message)
    
    # Should contain error code
    assert str(error_code) in formatted, \
        f"Formatted error should contain error code {error_code}"
    
    # Should contain suggestion
    assert "Suggestion:" in formatted, \
        "Formatted error should contain a suggestion"


@given(
    prefix=st.text(min_size=0, max_size=30),
    keyword=st.sampled_from(["location", "region", "Location", "Region", "LOCATION", "REGION"]),
    suffix=st.text(min_size=0, max_size=30)
)
@settings(max_examples=50)
def test_error_message_region_detection(prefix, keyword, suffix):
    """Test that region-related errors get VPN suggestion."""
    error_message = f"{prefix}{keyword}{suffix}"
    formatted = TranscriptionProvider.format_error(400, error_message)
    
    assert "VPN" in formatted or "region" in formatted.lower(), \
        "Region-related errors should suggest VPN"


# API Key Validation Tests

@given(api_key=st.text(min_size=30, max_size=50).map(lambda x: "AI" + x[2:]))
@settings(max_examples=100)
def test_gemini_api_key_validation_valid(api_key):
    """
    **Feature: gemini-voice-writer-v2, Property 13: API Key Validation Format (Gemini)**
    
    For any API key starting with 'AI' and length >= 30, 
    Gemini validation SHALL return True.
    """
    provider = GeminiProvider(api_key=api_key, model="gemini-2.5-flash")
    assert provider.validate_api_key() is True


@given(api_key=st.one_of(
    st.text(max_size=29),  # Too short
    st.text(min_size=30, max_size=50).filter(lambda x: not x.startswith("AI"))  # Wrong prefix
))
@settings(max_examples=100)
def test_gemini_api_key_validation_invalid(api_key):
    """Test that invalid Gemini API keys are rejected."""
    provider = GeminiProvider(api_key=api_key, model="gemini-2.5-flash")
    assert provider.validate_api_key() is False


@given(api_key=st.text(min_size=30, max_size=60).map(lambda x: "sk-" + x[3:]))
@settings(max_examples=100)
def test_openai_api_key_validation_valid(api_key):
    """
    **Feature: gemini-voice-writer-v2, Property 13: API Key Validation Format (OpenAI)**
    
    For any API key starting with 'sk-' and length >= 30,
    OpenAI validation SHALL return True.
    """
    provider = OpenAIProvider(api_key=api_key, model="whisper-1")
    assert provider.validate_api_key() is True


@given(api_key=st.one_of(
    st.text(max_size=29),  # Too short
    st.text(min_size=30, max_size=50).filter(lambda x: not x.startswith("sk-"))  # Wrong prefix
))
@settings(max_examples=100)
def test_openai_api_key_validation_invalid(api_key):
    """Test that invalid OpenAI API keys are rejected."""
    provider = OpenAIProvider(api_key=api_key, model="whisper-1")
    assert provider.validate_api_key() is False


@given(api_key=st.text(
    min_size=20, 
    max_size=50, 
    alphabet=st.characters(whitelist_categories=('L', 'N'), whitelist_characters='-_')
))
@settings(max_examples=100)
def test_openrouter_api_key_validation_valid(api_key):
    """
    **Feature: gemini-voice-writer-v2, Property 13: API Key Validation Format (OpenRouter)**
    
    For any alphanumeric API key with length >= 20,
    OpenRouter validation SHALL return True.
    """
    provider = OpenRouterProvider(api_key=api_key, model="openai/whisper-large-v3")
    assert provider.validate_api_key() is True


def test_provider_factory_available_providers():
    """Test that factory returns correct list of available providers."""
    providers = ProviderFactory.get_available_providers()
    
    assert "gemini" in providers
    assert "openrouter" in providers
    assert "openai" in providers
    assert len(providers) == 3


def test_provider_models_not_empty():
    """Test that each provider returns non-empty model list."""
    for provider_name in ["gemini", "openrouter", "openai"]:
        provider = ProviderFactory.create(provider_name, api_key="test")
        models = provider.get_models()
        
        assert len(models) > 0, f"{provider_name} should have at least one model"
        
        for model in models:
            assert "id" in model, "Model should have 'id' field"
            assert "name" in model, "Model should have 'name' field"
            assert "description" in model, "Model should have 'description' field"
