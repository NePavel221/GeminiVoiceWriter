import google.generativeai as genai
import os

class GeminiTranscriber:
    def __init__(self, api_key, model_name='gemini-1.5-flash'):
        self.api_key = api_key
        self.model_name = model_name
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)

    def transcribe(self, audio_file_path):
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        print(f"Uploading file: {audio_file_path}")
        try:
            # Upload the file to Gemini
            audio_file = genai.upload_file(path=audio_file_path)
            print(f"File uploaded: {audio_file.name}")
        except Exception as e:
            raise Exception(f"Failed to upload file: {e}")
        
        print("Generating content...")
        try:
            # Prompt the model to transcribe
            response = self.model.generate_content(
                [
                    "Please transcribe the following audio file exactly as spoken. Return ONLY the transcribed text, no additional commentary.",
                    audio_file
                ]
            )
            return response.text
        except Exception as e:
            print(f"Transcriber Error: {e}")
            # Try to extract more details if available
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                 print(f"Response text: {e.response.text}")
            raise Exception(f"Transcriber Error: {e}")
        
        # Cleanup: Delete the file from Gemini storage to avoid clutter (optional but good practice)
        # genai.delete_file(audio_file.name)
