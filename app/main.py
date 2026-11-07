import base64
from datetime import datetime, timedelta
from typing import Any
import httpx
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import get_doctors_catalog, settings
from app.services.cal_service import cal_service
from app.services.llm_agent import receptionist_agent
from app.services.storage_service import storage_service
from app.services.stt_service import stt_service
from app.services.tts_service import tts_service

app = FastAPI(
    title="Recepționer & Call-Center AI 24/7 (Voce + WhatsApp + Cal.com)",
    description=(
        "Arhitectură Distribuită Zero-Cost pe Hugging Face Spaces (16 GB RAM) + "
        "Groq Whisper/LLM + Edge-TTS Română + Cal.com (Google Calendar Sync) + Qdrant/Supabase"
    ),
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str = "demo-session"
    message: str
    voice: str = "ro-RO-AlinaNeural"
    generate_audio: bool = True
    channel: str = "Web Voice/Chat"


class TTSRequest(BaseModel):
    text: str
    voice: str = "ro-RO-AlinaNeural"


class ManualBookingRequest(BaseModel):
    patient_name: str
    phone: str
    date: str
    time: str
    service: str = "Consultație + Plan Tratament"
    doctor: str | None = None
    email: str = "pacient@demosmile.ro"


class CalComConfigRequest(BaseModel):
    api_key: str
    event_type_id: str = ""
    api_url: str = "https://api.cal.com"
    timezone: str = "Europe/Bucharest"


class DoctorSaveRequest(BaseModel):
    id: str = ""
    name: str
    specialty: str
    default_slots: list[str]
    days: list[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    calcom_event_type_id: str = ""


# ============================================================================
# 1. HEALTHCHECK & KEEP-ALIVE (Pentru UptimeRobot / cron-job.org la 10 minute)
# ============================================================================
@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    return {
        "status": "ok",
        "service": "Receptioner & Call-Center AI 24/7",
        "clinic_name": settings.clinic_name,
        "timestamp": datetime.now().isoformat(),
        "groq_configured": bool(settings.groq_api_key),
        "llm_model": settings.llm_model,
        "calcom_configured": bool(settings.calcom_api_key),
        "calcom_event_type_id": settings.calcom_event_type_id,
        "calcom_api_url": settings.calcom_api_url,
        "qdrant_configured": bool(settings.qdrant_url),
        "supabase_configured": bool(settings.supabase_url),
        "default_voice": settings.default_tts_voice,
        "supported_voices": tts_service.SUPPORTED_VOICES,
        "doctors": get_doctors_catalog(),
        "tomorrow_date": tomorrow,
    }


# ============================================================================
# 2. TEXT CHAT + SINTEZĂ VOCALĂ ÎN ROMÂNĂ (Web Widget / Demo)
# ============================================================================
@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest) -> dict[str, Any]:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Mesajul nu poate fi gol.")

    result = await receptionist_agent.chat(
        session_id=req.session_id,
        user_message=req.message,
        channel=req.channel,
    )

    audio_b64 = None
    if req.generate_audio:
        try:
            mp3_bytes = await tts_service.synthesize_mp3(
                text=result["reply"], voice=req.voice
            )
            audio_b64 = base64.b64encode(mp3_bytes).decode("utf-8")
        except Exception:
            audio_b64 = None

    return {
        "reply": result["reply"],
        "tools_used": result["tools_used"],
        "mode": result["mode"],
        "audio_base64": audio_b64,
        "appointments": result["appointments"],
    }


# ============================================================================
# 3. VOICE TURN (WebRTC / Microfon Browser -> STT Groq -> LLM -> Edge-TTS RO)
# ============================================================================
@app.post("/api/voice-turn")
async def voice_turn_endpoint(
    audio: UploadFile = File(...),
    session_id: str = Form("demo-voice-session"),
    voice: str = Form("ro-RO-AlinaNeural"),
) -> dict[str, Any]:
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Fișierul audio este gol.")

    # 1. Transcriere cu Groq Whisper (sau fallback demo)
    transcript = await stt_service.transcribe_audio(
        audio_bytes=audio_bytes,
        filename=audio.filename or "voice.webm",
        content_type=audio.content_type or "audio/webm",
    )

    if not transcript:
        transcript = "Bună ziua, aveți loc mâine la o consultație?"

    # 2. Răspuns de la Agentul AI + Tool Calling (Cal.com / RAG)
    result = await receptionist_agent.chat(
        session_id=session_id,
        user_message=transcript,
        channel="Voice AI WebRTC",
    )

    # 3. Sinteză vocală neurală în limba română (Edge-TTS Gratuit)
    audio_b64 = None
    try:
        mp3_bytes = await tts_service.synthesize_mp3(
            text=result["reply"], voice=voice
        )
        audio_b64 = base64.b64encode(mp3_bytes).decode("utf-8")
    except Exception:
        audio_b64 = None

    return {
        "transcript": transcript,
        "reply": result["reply"],
        "tools_used": result["tools_used"],
        "mode": result["mode"],
        "audio_base64": audio_b64,
        "appointments": result["appointments"],
    }


@app.post("/api/tts")
async def tts_endpoint(req: TTSRequest) -> Response:
    mp3_bytes = await tts_service.synthesize_mp3(text=req.text, voice=req.voice)
    return Response(content=mp3_bytes, media_type="audio/mpeg")


# ============================================================================
# 4. CALENDAR, MEDICI & PROGRAMĂRI LIVE (Cal.com + Google Calendar Sync)
# ============================================================================
@app.get("/api/doctors")
async def list_doctors_endpoint() -> dict[str, Any]:
    return {"doctors": get_doctors_catalog()}


@app.post("/api/doctors")
async def save_doctor_endpoint(req: DoctorSaveRequest) -> dict[str, Any]:
    saved = cal_service.add_or_update_doctor(
        name=req.name,
        specialty=req.specialty,
        default_slots=req.default_slots,
        days=req.days,
        calcom_event_type_id=req.calcom_event_type_id,
        doctor_id=req.id,
    )
    # Resetăm sesiunile active astfel încât promptul de sistem al AI-ului să preia imediat noul medic
    receptionist_agent.sessions.clear()
    return {
        "status": "saved",
        "doctor": saved,
        "doctors": get_doctors_catalog(),
    }


@app.delete("/api/doctors/{doctor_id}")
async def delete_doctor_endpoint(doctor_id: str) -> dict[str, Any]:
    doctors = cal_service.delete_doctor(doctor_id)
    receptionist_agent.sessions.clear()
    return {"status": "deleted", "doctors": doctors}


@app.get("/api/appointments")
async def list_appointments(
    date: str | None = None,
    doctor: str | None = None,
) -> dict[str, Any]:
    target_date = date or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    avail = await cal_service.check_availability(target_date, doctor=doctor)
    return {
        "appointments": cal_service.get_all_appointments(),
        "availability": avail,
        "doctors": get_doctors_catalog(),
        "calcom_configured": bool(settings.calcom_api_key),
        "calcom_event_type_id": settings.calcom_event_type_id,
        "audit_logs": storage_service.audit_logs[:15],
    }


@app.post("/api/appointments")
async def create_manual_appointment(req: ManualBookingRequest) -> dict[str, Any]:
    res = await cal_service.book_appointment(
        patient_name=req.patient_name,
        phone=req.phone,
        date_str=req.date,
        time_str=req.time,
        service=req.service,
        doctor=req.doctor,
        email=req.email,
        source="Programare Directă",
    )
    return {
        "result": res,
        "appointments": cal_service.get_all_appointments(),
    }


@app.delete("/api/appointments/{booking_id}")
async def cancel_appointment_endpoint(booking_id: str) -> dict[str, Any]:
    res = await cal_service.cancel_appointment(booking_id)
    return {
        "result": res,
        "appointments": cal_service.get_all_appointments(),
    }


@app.get("/api/calcom/status")
async def get_calcom_status() -> dict[str, Any]:
    event_types = []
    if settings.calcom_api_key:
        event_types = await cal_service.discover_event_types(settings.calcom_api_key)
    return {
        "configured": bool(settings.calcom_api_key),
        "api_url": settings.calcom_api_url,
        "event_type_id": settings.calcom_event_type_id,
        "timezone": settings.calcom_timezone,
        "event_types": event_types,
        "doctors": get_doctors_catalog(),
    }


@app.post("/api/calcom/configure")
async def configure_calcom_endpoint(req: CalComConfigRequest) -> dict[str, Any]:
    return await cal_service.configure_and_test(
        api_key=req.api_key,
        event_type_id=req.event_type_id,
        api_url=req.api_url,
        timezone=req.timezone,
    )


@app.post("/api/calcom/sync")
async def sync_calcom_endpoint() -> dict[str, Any]:
    return await cal_service.sync_bookings_from_calcom()


@app.post("/api/webhooks/calcom")
async def receive_calcom_webhook(request: Request) -> dict[str, Any]:
    """Webhook în timp real pentru Cal.com (BOOKING_CREATED, BOOKING_RESCHEDULED, BOOKING_CANCELLED)."""
    payload = await request.json()
    res = cal_service.handle_webhook(payload)
    return {"status": "processed", "detail": res}


@app.post("/api/reset-session")
async def reset_session(session_id: str = Query("demo-session")) -> dict[str, str]:
    receptionist_agent.reset_session(session_id)
    return {"status": "reset", "session_id": session_id}


# ============================================================================
# 5. OMNICHANNEL WEBHOOKS: META WHATSAPP CLOUD API, TELEGRAM & CHATWOOT/TYPEBOT
# ============================================================================
@app.get("/api/webhooks/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
) -> Response:
    """Verificare oficială Meta WhatsApp Cloud API Webhook."""
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return Response(content=hub_challenge or "", media_type="text/plain")
    raise HTTPException(status_code=403, detail="Token de verificare WhatsApp invalid.")


@app.post("/api/webhooks/whatsapp")
async def receive_whatsapp_webhook(request: Request) -> JSONResponse:
    """Primește mesajele de pe WhatsApp Cloud API (Meta Free Service Tier) și răspunde automat."""
    body = await request.json()
    try:
        entries = body.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    sender_phone = msg.get("from", "whatsapp-user")
                    msg_type = msg.get("type")
                    user_text = ""
                    if msg_type == "text":
                        user_text = msg.get("text", {}).get("body", "")

                    if user_text:
                        ai_res = await receptionist_agent.chat(
                            session_id=f"wa-{sender_phone}",
                            user_message=user_text,
                            channel="WhatsApp Cloud API",
                        )
                        if (
                            settings.whatsapp_access_token
                            and settings.whatsapp_phone_number_id
                        ):
                            wa_url = (
                                f"https://graph.facebook.com/v21.0/"
                                f"{settings.whatsapp_phone_number_id}/messages"
                            )
                            headers = {
                                "Authorization": f"Bearer {settings.whatsapp_access_token}",
                                "Content-Type": "application/json",
                            }
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender_phone,
                                "type": "text",
                                "text": {"body": ai_res["reply"]},
                            }
                            async with httpx.AsyncClient(timeout=10.0) as client:
                                await client.post(wa_url, headers=headers, json=payload)
    except Exception:
        pass
    return JSONResponse({"status": "received"})


@app.post("/api/webhooks/chatwoot")
async def receive_chatwoot_webhook(request: Request) -> dict[str, Any]:
    """Webhook compatibil cu Chatwoot (Open-Source) și Typebot.io."""
    payload = await request.json()
    message_type = payload.get("message_type")
    content = payload.get("content", "")
    conversation_id = str(payload.get("conversation", {}).get("id", "chatwoot-1"))

    if message_type == "incoming" and content:
        ai_res = await receptionist_agent.chat(
            session_id=f"cw-{conversation_id}",
            user_message=content,
            channel="Chatwoot Omnichannel",
        )
        return {"status": "replied", "reply": ai_res["reply"]}

    return {"status": "ignored"}


# Montăm interfața web statică
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse("static/index.html")
