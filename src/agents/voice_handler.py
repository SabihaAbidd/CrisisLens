import json
import google.generativeai as genai
from src.config import gemini_model

def transcribe_voice(audio_path: str) -> dict:
    """
    Transcribes and translates an emergency audio file using Gemini.
    Attempts upload_file first, falling back to inline data on permission/key failure.
    """
    # 1. Define prompt
    prompt = """
   You are a multilingual emergency transcription assistant.
   This audio may be in Urdu, Roman Urdu, or English.
   
   1. Transcribe the audio exactly as spoken
   2. Translate it to English if not already English
   3. Extract any emergency details mentioned
   
   Return ONLY a raw JSON object, no markdown:
   {
     "transcription": "exact words spoken",
     "language_detected": "Urdu / Roman Urdu / English",
     "translation": "English translation",
     "incident_mentioned": "what emergency they describe",
     "location_mentioned": "any location words spoken or None",
     "urgency_tone": "calm / panicked / distressed"
   }
   """

    # 2. Upload file or fall back to inline bytes
    try:
        audio_file = genai.upload_file(audio_path)
        contents = [prompt, audio_file]
    except Exception:
        # Fallback to inline binary data if upload_file fails
        mime_type = "audio/wav"
        if audio_path.endswith(".mp3"):
            mime_type = "audio/mp3"
        elif audio_path.endswith(".ogg"):
            mime_type = "audio/ogg"
        elif audio_path.endswith(".m4a"):
            mime_type = "audio/m4a"

        with open(audio_path, "rb") as f:
            audio_data = f.read()

        contents = [
            prompt,
            {
                "mime_type": mime_type,
                "data": audio_data
            }
        ]

    response = gemini_model.generate_content(contents)

    # 3. Strip markdown, parse JSON
    raw = response.text.strip()
    raw_clean = raw.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(raw_clean)
    except Exception:
        data = {
            "transcription": response.text,
            "language_detected": "Unknown",
            "translation": response.text,
            "incident_mentioned": "Unknown",
            "location_mentioned": "None",
            "urgency_tone": "Unknown"
        }

    # 4. Print confirmation
    print(f"[Voice] Transcribed: {data['language_detected']} — {data['incident_mentioned']}")

    return data
