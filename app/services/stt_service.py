import httpx
from app.config import settings


class STTService:
    """
    Serviciu Speech-to-Text (Recunoașterea vocii în limba română).
    Folosește Groq Cloud Free Tier (whisper-large-v3-turbo) cu latență ~200ms.
    """

    GROQ_AUDIO_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

    async def transcribe_audio(
        self, audio_bytes: bytes, filename: str = "audio.webm", content_type: str = "audio/webm"
    ) -> str:
        if not settings.groq_api_key:
            return (
                "[Mod Demo fără cheie Groq] Bună ziua, aș dori să știu ce ore aveți libere mâine "
                "pentru o consultație și cât costă un detartraj?"
            )

        headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
        files = {
            "file": (filename, audio_bytes, content_type),
        }
        data = {
            "model": settings.stt_model,
            "language": "ro",
            "response_format": "json",
            "temperature": "0.0",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.GROQ_AUDIO_URL, headers=headers, data=data, files=files
            )
            response.raise_for_status()
            payload = response.json()
            return payload.get("text", "").strip()


stt_service = STTService()
