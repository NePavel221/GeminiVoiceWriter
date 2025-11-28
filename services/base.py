"""Base classes for transcription providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class TranscriptionResult:
    """Result of a transcription operation."""
    text: str
    duration: float
    cost: float
    model: str
    provider: str
    timestamp: datetime = field(default_factory=datetime.now)
    raw_response: dict = field(default_factory=dict)


class TranscriptionProvider(ABC):
    """Abstract base class for transcription providers."""
    
    PROVIDER_NAME: str = "base"
    
    def __init__(self, api_key: str, model: str):
        """Initialize provider with API key and model.
        
        Args:
            api_key: API key for the provider
            model: Model identifier to use
        """
        self.api_key = api_key
        self.model = model
    
    @abstractmethod
    def transcribe(self, audio_path: str) -> TranscriptionResult:
        """Transcribe audio file.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            TranscriptionResult with transcribed text and metadata
            
        Raises:
            TranscriptionError: If transcription fails
        """
        pass
    
    @abstractmethod
    def validate_api_key(self) -> bool:
        """Validate API key format.
        
        Returns:
            True if API key format is valid
        """
        pass
    
    @abstractmethod
    def get_models(self) -> list[dict]:
        """Get available models for this provider.
        
        Returns:
            List of model dictionaries with 'id', 'name', 'description' keys
        """
        pass
    
    @staticmethod
    def format_error(error_code: int, error_message: str) -> str:
        """Format error message for user display.
        
        Args:
            error_code: HTTP error code or provider-specific code
            error_message: Raw error message
            
        Returns:
            User-friendly error message with suggestion
        """
        suggestions = {
            400: "Check your request parameters.",
            401: "Invalid API key. Please check your settings.",
            403: "Access denied. Your API key may not have required permissions.",
            404: "Resource not found. The model may not be available.",
            429: "Rate limit exceeded. Please wait and try again.",
            500: "Server error. Please try again later.",
            503: "Service unavailable. Please try again later.",
        }
        
        suggestion = suggestions.get(error_code, "Please check your configuration and try again.")
        
        # Check for region-specific errors
        if "location" in error_message.lower() or "region" in error_message.lower():
            suggestion = "Region restricted. Consider using a VPN (US/Europe)."
        
        return f"Error {error_code}: {error_message}\nSuggestion: {suggestion}"


class TranscriptionError(Exception):
    """Exception raised when transcription fails."""
    
    def __init__(self, message: str, error_code: Optional[int] = None, provider: str = "unknown"):
        self.message = message
        self.error_code = error_code
        self.provider = provider
        super().__init__(self.message)
