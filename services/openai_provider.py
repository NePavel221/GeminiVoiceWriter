"""OpenAI Whisper transcription provider."""
import os
from datetime import datetime

from openai import OpenAI

from .base import TranscriptionProvider, TranscriptionResult, TranscriptionError


class OpenAIProvider(TranscriptionProvider):
    """OpenAI Whisper transcription provider."""
    
    PROVIDER_NAME = "openai"
    
    # Cost per minute for Whisper API
    COST_PER_MINUTE = {
        "whisper-1": 0.006,  # $0.006 per minute
    }
    
    def __init__(self, api_key: str, model: str = "whisper-1"):
        """Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key
            model: Whisper model to use
        """
        super().__init__(api_key, model)
        self._client = OpenAI(api_key=self.api_key)
    
    def transcribe(self, audio_path: str) -> TranscriptionResult:
        """Transcribe audio using OpenAI Whisper API.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            TranscriptionResult with transcribed text
            
        Raises:
            TranscriptionError: If transcription fails
        """
        if not os.path.exists(audio_path):
            raise TranscriptionError(f"Audio file not found: {audio_path}", provider=self.PROVIDER_NAME)
        
        duration = self._get_audio_duration(audio_path)
        
        try:
            with open(audio_path, 'rb') as audio_file:
                response = self._client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    response_format="text",
                    prompt="Please transcribe with proper punctuation and capitalization."
                )
            
            # Response is just the text when response_format="text"
            text = response.strip() if isinstance(response, str) else response.text.strip()
            cost = self._calculate_cost(duration)
            
            return TranscriptionResult(
                text=text,
                duration=duration,
                cost=cost,
                model=self.model,
                provider=self.PROVIDER_NAME,
                timestamp=datetime.now(),
                raw_response={"text": text}
            )
            
        except Exception as e:
            error_msg = str(e)
            error_code = 500
            
            # Try to extract error code from OpenAI exceptions
            if hasattr(e, 'status_code'):
                error_code = e.status_code
            elif "401" in error_msg:
                error_code = 401
            elif "429" in error_msg:
                error_code = 429
            elif "400" in error_msg:
                error_code = 400
            
            formatted_error = self.format_error(error_code, error_msg)
            raise TranscriptionError(formatted_error, error_code=error_code, provider=self.PROVIDER_NAME)
    
    def validate_api_key(self) -> bool:
        """Validate OpenAI API key format.
        
        OpenAI keys start with 'sk-' and are typically 51 characters.
        
        Returns:
            True if API key format appears valid
        """
        if not self.api_key:
            return False
        # OpenAI keys start with 'sk-' (or 'sk-proj-' for project keys)
        return self.api_key.startswith('sk-') and len(self.api_key) >= 30
    
    def get_models(self) -> list[dict]:
        """Get available OpenAI Whisper models.
        
        Returns:
            List of model dictionaries
        """
        return [
            {
                "id": "whisper-1",
                "name": "Whisper",
                "description": "OpenAI's speech-to-text model"
            },
        ]
    
    def _calculate_cost(self, duration_seconds: float) -> float:
        """Calculate transcription cost based on duration."""
        cost_per_min = self.COST_PER_MINUTE.get(self.model, 0.006)
        return (duration_seconds / 60.0) * cost_per_min
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio file duration in seconds."""
        try:
            import wave
            with wave.open(audio_path, 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return frames / float(rate)
        except Exception:
            return 0.0
