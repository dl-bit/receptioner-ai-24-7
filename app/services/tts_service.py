import io
import re
import edge_tts
from app.config import settings


class TTSService:
    """
    Serviciu Text-to-Speech 100% Gratuit în Limba Română.
    Folosește Microsoft Edge Neural TTS (ro-RO-AlinaNeural și ro-RO-EmilNeural) fără cheie API.
    """

    SUPPORTED_VOICES = {
        "ro-RO-AlinaNeural": "Alina (Voce Feminină Naturală - RO)",
        "ro-RO-EmilNeural": "Emil (Voce Masculină Naturală - RO)",
    }

    @staticmethod
    def clean_text_for_speech(text: str) -> str:
        """Curăță simbolurile Markdown pentru ca sinteza vocală să sune 100% natural."""
        cleaned = re.sub(r"[*_#`~>]+", "", text)
        cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    async def synthesize_mp3(
        self, text: str, voice: str | None = None, rate: str | None = None
    ) -> bytes:
        selected_voice = voice if voice in self.SUPPORTED_VOICES else settings.default_tts_voice
        selected_rate = rate or settings.default_tts_rate
        clean_text = self.clean_text_for_speech(text)

        if not clean_text:
            clean_text = "Cu drag! Vă mai pot ajuta cu altă informație?"

        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=selected_voice,
            rate=selected_rate,
        )

        audio_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])

        return audio_buffer.getvalue()


tts_service = TTSService()
