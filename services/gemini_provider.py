"""Google Gemini transcription provider."""
import os
from datetime import datetime

import google.generativeai as genai

from .base import TranscriptionProvider, TranscriptionResult, TranscriptionError


class GeminiProvider(TranscriptionProvider):
    """Google Gemini transcription provider using google-generativeai SDK."""
    
    PROVIDER_NAME = "gemini"
    
    # Cost per minute for different models (approximate)
    COST_PER_MINUTE = {
        "gemini-2.5-flash": 0.0015,
        "gemini-2.5-flash-lite": 0.0005,
        "gemini-2.5-pro": 0.0020,
        "gemini-3-pro-preview": 0.0030,
        "gemini-1.5-flash": 0.0015,
        "gemini-1.5-pro": 0.0020,
    }
    
    TRANSCRIPTION_PROMPT = """Please transcribe the following audio file exactly as spoken.
Apply proper punctuation and capitalization.
Return ONLY the transcribed text, no additional commentary or formatting."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        """Initialize Gemini provider.
        
        Args:
            api_key: Google AI API key
            model: Gemini model to use
        """
        super().__init__(api_key, model)
        genai.configure(api_key=self.api_key)
        self._model = genai.GenerativeModel(self.model)
    
    def transcribe(self, audio_path: str) -> TranscriptionResult:
        """Transcribe audio using Gemini API.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            TranscriptionResult with transcribed text
            
        Raises:
            TranscriptionError: If transcription fails
        """
        if not os.path.exists(audio_path):
            raise TranscriptionError(f"Audio file not found: {audio_path}", provider=self.PROVIDER_NAME)
        
        # Get audio duration for cost calculation
        duration = self._get_audio_duration(audio_path)
        
        try:
            # Upload file to Gemini
            audio_file = genai.upload_file(path=audio_path)
            
            # Generate transcription
            response = self._model.generate_content([
                self.TRANSCRIPTION_PROMPT,
                audio_file
            ])
            
            text = response.text.strip()
            cost = self._calculate_cost(duration)
            
            return TranscriptionResult(
                text=text,
                duration=duration,
                cost=cost,
                model=self.model,
                provider=self.PROVIDER_NAME,
                timestamp=datetime.now(),
                raw_response={"candidates": str(response.candidates) if response.candidates else ""}
            )
            
        except Exception as e:
            error_msg = str(e)
            error_code = 500
            
            # Try to extract error code
            if hasattr(e, 'code'):
                error_code = e.code
            elif "400" in error_msg:
                error_code = 400
            elif "401" in error_msg:
                error_code = 401
            elif "403" in error_msg:
                error_code = 403
            elif "429" in error_msg:
                error_code = 429
            
            formatted_error = self.format_error(error_code, error_msg)
            raise TranscriptionError(formatted_error, error_code=error_code, provider=self.PROVIDER_NAME)
    
    def validate_api_key(self) -> bool:
        """Validate Gemini API key format.
        
        Gemini API keys typically start with 'AI' and are 39 characters long.
        
        Returns:
            True if API key format appears valid
        """
        if not self.api_key:
            return False
        # Gemini keys are typically 39 chars and start with 'AI'
        return len(self.api_key) >= 30 and self.api_key.startswith('AI')
    
    def get_models(self) -> list[dict]:
        """Get available Gemini models.
        
        Returns:
            List of model dictionaries
        """
        return [
            {
                "id": "gemini-2.5-flash",
                "name": "Gemini 2.5 Flash",
                "description": "Balanced speed and quality for most tasks"
            },
            {
                "id": "gemini-2.5-flash-lite",
                "name": "Gemini 2.5 Flash-Lite",
                "description": "Fastest and cheapest for short commands"
            },
            {
                "id": "gemini-2.5-pro",
                "name": "Gemini 2.5 Pro",
                "description": "Best quality for complex transcriptions"
            },
            {
                "id": "gemini-3-pro-preview",
                "name": "Gemini 3.0 Pro Preview",
                "description": "Latest model with advanced capabilities"
            },
        ]
    
    def _calculate_cost(self, duration_seconds: float) -> float:
        """Calculate transcription cost based on duration.
        
        Args:
            duration_seconds: Audio duration in seconds
            
        Returns:
            Estimated cost in USD
        """
        cost_per_min = self.COST_PER_MINUTE.get(self.model, 0.0015)
        return (duration_seconds / 60.0) * cost_per_min
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio file duration in seconds.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Duration in seconds
        """
        try:
            import wave
            with wave.open(audio_path, 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return frames / float(rate)
        except Exception:
            return 0.0
