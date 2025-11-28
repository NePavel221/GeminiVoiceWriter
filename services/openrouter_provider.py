"""OpenRouter transcription provider (OpenAI-compatible API)."""
import base64
import os
from datetime import datetime

import requests

from .base import TranscriptionProvider, TranscriptionResult, TranscriptionError


class OpenRouterProvider(TranscriptionProvider):
    """OpenRouter transcription provider using OpenAI-compatible API."""
    
    PROVIDER_NAME = "openrouter"
    API_BASE = "https://openrouter.ai/api/v1"
    
    # Cost per minute for different models (approximate)
    COST_PER_MINUTE = {
        "openai/whisper-large-v3": 0.001,
        "openai/whisper-1": 0.001,
    }
    
    def __init__(self, api_key: str, model: str = "openai/whisper-large-v3"):
        """Initialize OpenRouter provider.
        
        Args:
            api_key: OpenRouter API key
            model: Model to use for transcription
        """
        super().__init__(api_key, model)
    
    def transcribe(self, audio_path: str) -> TranscriptionResult:
        """Transcribe audio using OpenRouter API.
        
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
            # Read and encode audio file
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/gemini-voice-writer",
                "X-Title": "Gemini Voice Writer"
            }
            
            # Use chat completions with audio
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Please transcribe this audio exactly as spoken. Apply proper punctuation and capitalization. Return ONLY the transcribed text."
                            },
                            {
                                "type": "audio_url",
                                "audio_url": {
                                    "url": f"data:audio/wav;base64,{audio_base64}"
                                }
                            }
                        ]
                    }
                ]
            }
            
            response = requests.post(
                f"{self.API_BASE}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code != 200:
                error_msg = response.text
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', response.text)
                except:
                    pass
                formatted_error = self.format_error(response.status_code, error_msg)
                raise TranscriptionError(formatted_error, error_code=response.status_code, provider=self.PROVIDER_NAME)
            
            result = response.json()
            text = result['choices'][0]['message']['content'].strip()
            cost = self._calculate_cost(duration)
            
            return TranscriptionResult(
                text=text,
                duration=duration,
                cost=cost,
                model=self.model,
                provider=self.PROVIDER_NAME,
                timestamp=datetime.now(),
                raw_response=result
            )
            
        except requests.RequestException as e:
            formatted_error = self.format_error(500, str(e))
            raise TranscriptionError(formatted_error, error_code=500, provider=self.PROVIDER_NAME)
        except TranscriptionError:
            raise
        except Exception as e:
            formatted_error = self.format_error(500, str(e))
            raise TranscriptionError(formatted_error, error_code=500, provider=self.PROVIDER_NAME)
    
    def validate_api_key(self) -> bool:
        """Validate OpenRouter API key format.
        
        OpenRouter keys are typically alphanumeric strings.
        
        Returns:
            True if API key format appears valid
        """
        if not self.api_key:
            return False
        # OpenRouter keys are alphanumeric, typically 32+ chars
        return len(self.api_key) >= 20 and self.api_key.replace('-', '').replace('_', '').isalnum()
    
    def get_models(self) -> list[dict]:
        """Get available OpenRouter models for audio transcription.
        
        Returns:
            List of model dictionaries
        """
        return [
            {
                "id": "openai/whisper-large-v3",
                "name": "Whisper Large V3",
                "description": "OpenAI's best transcription model via OpenRouter"
            },
            {
                "id": "openai/whisper-1",
                "name": "Whisper 1",
                "description": "OpenAI's standard transcription model"
            },
        ]
    
    def _calculate_cost(self, duration_seconds: float) -> float:
        """Calculate transcription cost based on duration."""
        cost_per_min = self.COST_PER_MINUTE.get(self.model, 0.001)
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
