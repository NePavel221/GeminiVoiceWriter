"""Factory for creating transcription providers."""
from typing import Type

from .base import TranscriptionProvider
from .gemini_provider import GeminiProvider
from .openrouter_provider import OpenRouterProvider
from .openai_provider import OpenAIProvider


class ProviderFactory:
    """Factory for creating transcription provider instances."""
    
    _providers: dict[str, Type[TranscriptionProvider]] = {
        "gemini": GeminiProvider,
        "openrouter": OpenRouterProvider,
        "openai": OpenAIProvider,
    }
    
    @classmethod
    def create(cls, provider_name: str, api_key: str, model: str = None) -> TranscriptionProvider:
        """Create a transcription provider instance.
        
        Args:
            provider_name: Name of the provider ('gemini', 'openrouter', 'openai')
            api_key: API key for the provider
            model: Model to use (optional, uses provider default if not specified)
            
        Returns:
            TranscriptionProvider instance
            
        Raises:
            ValueError: If provider_name is not recognized
        """
        provider_name = provider_name.lower()
        
        if provider_name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(f"Unknown provider: {provider_name}. Available: {available}")
        
        provider_class = cls._providers[provider_name]
        
        # Use default model if not specified
        if model is None:
            default_models = {
                "gemini": "gemini-2.5-flash",
                "openrouter": "openai/whisper-large-v3",
                "openai": "whisper-1",
            }
            model = default_models.get(provider_name, "")
        
        return provider_class(api_key=api_key, model=model)
    
    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get list of available provider names.
        
        Returns:
            List of provider name strings
        """
        return list(cls._providers.keys())
    
    @classmethod
    def get_provider_info(cls) -> list[dict]:
        """Get information about all available providers.
        
        Returns:
            List of provider info dictionaries
        """
        return [
            {
                "id": "gemini",
                "name": "Google Gemini",
                "description": "Google's multimodal AI for transcription"
            },
            {
                "id": "openrouter",
                "name": "OpenRouter",
                "description": "Access multiple AI models via unified API"
            },
            {
                "id": "openai",
                "name": "OpenAI Whisper",
                "description": "OpenAI's dedicated speech-to-text model"
            },
        ]
