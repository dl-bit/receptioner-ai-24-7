import base64
from datetime import datetime, timedelta
from typing import Any
import httpx
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import (
    get_doctors_catalog,
    get_inboxes_catalog,
    resolve_inbox_profile,
    settings,
)
from app.services.cal_service import cal_service
from app.services.chatwoot_service import chatwoot_service
from app.services.llm_agent import receptionist_agent
from app.services.storage_service import storage_service
from app.services.stt_service import stt_service
from app.services.tts_service import tts_service

app = FastAPI(
    title="Recepționer & Call-Center AI 24/7 (Multi-Inbox Chatwoot + dev.avanz.ro + Voce + Cal.com)",
    description=(
        "Arhitectură Distribuită Zero-Cost + Multi-Inbox Personalizat Chatwoot (dev.avanz.ro) + "
        "Groq Whisper/LLM + Edge-TTS Română + Cal.com (Google Calendar Sync) + Omnichannel"
    ),
    version="1.4.0",
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
    inbox_profile_id: str = ""
    inbox_id: str = ""


class TTSRequest(BaseModel):
    text: str
    voice: str = "ro-RO-AlinaNeural"


class ManualBookingRequest(BaseModel):
    patient_name: str
    phone: str
    date: str
    time: str
    service: str = "Demo Live AvanzCRM / Consultanță"
    doctor: str | None = None
    email: str = "contact@avanz.ro"


class CalComConfigRequest(BaseModel):
    api_key: str
    event_type_id: str = ""
    api_url: str = "https://api.cal.com"
    timezone: str = "Europe/Bucharest"


class OmnichannelConfigRequest(BaseModel):
    whatsapp_verify_token: str = "receptioner_secret_token_2027"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    telegram_bot_token: str = ""
    public_webhook_base_url: str = ""
    chatwoot_api_url: str = ""
    chatwoot_api_token: str = ""


class DoctorSaveRequest(BaseModel):
    id: str = ""
    name: str
    specialty: str
    default_slots: list[str]
    days: list[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    calcom_event_type_id: str = ""


class InboxProfileSaveRequest(BaseModel):
    id: str = ""
    inbox_id: str = ""
    name: str
    domain: str = "dev.avanz.ro"
    welcome_message: str = ""
    handoff_message: str = ""
    site_specificity: str = ""
    is_default: bool = False
    quick_prompts: list[str] = []


class InboxGenerateRequest(BaseModel):
    name: str
    domain: str = "dev.avanz.ro"
    site_specificity: str = ""
    inbox_id: str = ""


# ============================================================================
# 1. HEALTHCHECK & KEEP-ALIVE (Pentru UptimeRobot / cron-job.org la 10 minute)
# ============================================================================
@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    inboxes = get_inboxes_catalog()
    default_inbox = resolve_inbox_profile()
    return {
        "status": "ok",
        "service": "Receptioner & Call-Center AI 24/7",
        "clinic_name": default_inbox.get("name", settings.clinic_name),
        "timestamp": datetime.now().isoformat(),
        "groq_configured": bool(settings.groq_api_key),
        "llm_model": settings.llm_model,
        "calcom_configured": bool(settings.calcom_api_key),
        "calcom_event_type_id": settings.calcom_event_type_id,
        "calcom_api_url": settings.calcom_api_url,
        "whatsapp_configured": bool(
            settings.whatsapp_access_token and settings.whatsapp_phone_number_id
        ),
        "telegram_configured": bool(settings.telegram_bot_token),
        "chatwoot_configured": bool(
            settings.chatwoot_api_url and settings.chatwoot_api_token
        ),
        "qdrant_configured": bool(settings.qdrant_url),
        "supabase_configured": bool(settings.supabase_url),
        "default_voice": settings.default_tts_voice,
        "supported_voices": tts_service.SUPPORTED_VOICES,
        "doctors": get_doctors_catalog(),
        "inboxes": inboxes,
        "active_inbox": default_inbox,
        "tomorrow_date": tomorrow,
    }


# ============================================================================
# 2. TEXT CHAT + SINTEZĂ VOCALĂ ÎN ROMÂNĂ (Web Widget / Demo Multi-Inbox)
# ============================================================================
@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest) -> dict[str, Any]:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Mesajul nu poate fi gol.")

    inbox_profile = resolve_inbox_profile(
        inbox_id=req.inbox_id,
        profile_id=req.inbox_profile_id,
        auto_register_new=False,
    )

    result = await receptionist_agent.chat(
        session_id=f"{req.session_id}-{inbox_profile.get('id', 'default')}",
        user_message=req.message,
        channel=req.channel,
        inbox_profile=inbox_profile,
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
        "inbox_profile": inbox_profile,
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
    inbox_profile_id: str = Form(""),
) -> dict[str, Any]:
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Fișierul audio este gol.")

    inbox_profile = resolve_inbox_profile(
        profile_id=inbox_profile_id,
        auto_register_new=False,
    )

    # 1. Transcriere cu Groq Whisper (sau fallback demo)
    transcript = await stt_service.transcribe_audio(
        audio_bytes=audio_bytes,
        filename=audio.filename or "voice.webm",
        content_type=audio.content_type or "audio/webm",
    )

    if not transcript:
        transcript = "Bună ziua, ce module oferă AvanzCRM pe dev.avanz.ro?"

    # 2. Răspuns de la Agentul AI + Tool Calling (Cal.com / RAG)
    result = await receptionist_agent.chat(
        session_id=f"{session_id}-{inbox_profile.get('id', 'default')}",
        user_message=transcript,
        channel=f"Voice AI ({inbox_profile.get('domain', 'Web')})",
        inbox_profile=inbox_profile,
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
        "inbox_profile": inbox_profile,
        "audio_base64": audio_b64,
        "appointments": result["appointments"],
    }


@app.post("/api/tts")
async def tts_endpoint(req: TTSRequest) -> Response:
    mp3_bytes = await tts_service.synthesize_mp3(text=req.text, voice=req.voice)
    return Response(content=mp3_bytes, media_type="audio/mpeg")


# ============================================================================
# 4. CALENDAR, MEDICI/CONSULTANȚI & PROGRAMĂRI LIVE (Cal.com + Google Calendar)
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
    receptionist_agent.sessions.clear()
    return {"status": "reset", "session_id": session_id}


# ============================================================================
# 5. CHATWOOT MULTI-INBOX PERSONALIZATION (dev.avanz.ro & Orice Inbox Nou)
# ============================================================================
@app.get("/api/chatwoot/inboxes")
async def list_chatwoot_inboxes() -> dict[str, Any]:
    inboxes = get_inboxes_catalog()
    return {
        "inboxes": inboxes,
        "active_inbox": resolve_inbox_profile(),
        "chatwoot_configured": bool(
            settings.chatwoot_api_url and settings.chatwoot_api_token
        ),
    }


@app.post("/api/chatwoot/inboxes")
async def save_chatwoot_inbox(req: InboxProfileSaveRequest) -> dict[str, Any]:
    return await chatwoot_service.save_or_update_inbox_profile(
        name=req.name,
        domain=req.domain,
        welcome_message=req.welcome_message,
        handoff_message=req.handoff_message,
        site_specificity=req.site_specificity,
        inbox_id=req.inbox_id,
        profile_id=req.id,
        is_default=req.is_default,
        quick_prompts=req.quick_prompts,
    )


@app.delete("/api/chatwoot/inboxes/{profile_id}")
async def delete_chatwoot_inbox(profile_id: str) -> dict[str, Any]:
    inboxes = chatwoot_service.delete_inbox_profile(profile_id)
    return {"status": "deleted", "inboxes": inboxes}


@app.post("/api/chatwoot/inboxes/generate")
async def generate_chatwoot_inbox_template(req: InboxGenerateRequest) -> dict[str, Any]:
    """Generează automat mesajele personalizate și promptul AI pentru un Inbox nou în funcție de specificul site-ului."""
    generated = await receptionist_agent.generate_inbox_profile_with_ai(
        name=req.name,
        domain=req.domain,
        site_specificity=req.site_specificity,
        inbox_id=req.inbox_id,
    )
    return {"status": "generated", "template": generated}


@app.post("/api/chatwoot/inboxes/sync")
async def sync_chatwoot_inboxes_endpoint() -> dict[str, Any]:
    """Sincronizează Inbox-urile din Chatwoot și actualizează mesajele lor de întâmpinare (greeting_message)."""
    return await chatwoot_service.sync_inboxes_from_chatwoot()


# ============================================================================
# 6. OMNICHANNEL: META WHATSAPP CLOUD API, TELEGRAM BOT & CHATWOOT
# ============================================================================
@app.post("/api/omnichannel/configure")
async def configure_omnichannel_endpoint(req: OmnichannelConfigRequest) -> dict[str, Any]:
    """Salvează token-urile WhatsApp, Telegram și Chatwoot în .env și înregistrează automat webhook-urile."""
    updates: dict[str, str] = {}
    if req.whatsapp_verify_token.strip():
        settings.whatsapp_verify_token = req.whatsapp_verify_token.strip()
        updates["WHATSAPP_VERIFY_TOKEN"] = settings.whatsapp_verify_token
    if req.whatsapp_access_token.strip():
        settings.whatsapp_access_token = req.whatsapp_access_token.strip()
        updates["WHATSAPP_ACCESS_TOKEN"] = settings.whatsapp_access_token
    if req.whatsapp_phone_number_id.strip():
        settings.whatsapp_phone_number_id = req.whatsapp_phone_number_id.strip()
        updates["WHATSAPP_PHONE_NUMBER_ID"] = settings.whatsapp_phone_number_id
    if req.telegram_bot_token.strip():
        settings.telegram_bot_token = req.telegram_bot_token.strip()
        updates["TELEGRAM_BOT_TOKEN"] = settings.telegram_bot_token
    if req.chatwoot_api_url.strip():
        settings.chatwoot_api_url = req.chatwoot_api_url.strip().rstrip("/")
        updates["CHATWOOT_API_URL"] = settings.chatwoot_api_url
    if req.chatwoot_api_token.strip():
        settings.chatwoot_api_token = req.chatwoot_api_token.strip()
        updates["CHATWOOT_API_TOKEN"] = settings.chatwoot_api_token

    if updates:
        cal_service._persist_to_env_file(updates)

    telegram_webhook_status = None
    if settings.telegram_bot_token and req.public_webhook_base_url.strip():
        base_url = req.public_webhook_base_url.strip().rstrip("/")
        tg_webhook_url = f"{base_url}/api/webhooks/telegram"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r_tg = await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook",
                    json={"url": tg_webhook_url},
                )
                telegram_webhook_status = r_tg.json()
        except Exception as exc:
            telegram_webhook_status = {"ok": False, "error": str(exc)}

    chatwoot_status = None
    if settings.chatwoot_api_url and settings.chatwoot_api_token:
        chatwoot_status = await chatwoot_service.verify_and_register_webhook(
            api_url=settings.chatwoot_api_url,
            api_token=settings.chatwoot_api_token,
            webhook_target_url=req.public_webhook_base_url,
        )

    return {
        "status": "saved",
        "whatsapp_configured": bool(
            settings.whatsapp_access_token and settings.whatsapp_phone_number_id
        ),
        "telegram_configured": bool(settings.telegram_bot_token),
        "chatwoot_configured": bool(
            settings.chatwoot_api_url and settings.chatwoot_api_token
        ),
        "telegram_webhook": telegram_webhook_status,
        "chatwoot_status": chatwoot_status,
        "inboxes": get_inboxes_catalog(),
    }


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
    """Primește mesajele text și vocale de pe WhatsApp Cloud API (Meta Free Service Tier) și răspunde automat."""
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


@app.post("/api/webhooks/telegram")
async def receive_telegram_webhook(request: Request) -> dict[str, Any]:
    """
    Webhook oficial pentru Telegram Bot API:
    - Suportă mesaje text și mesaje vocale (voice notes transcrise cu Groq Whisper)
    - Răspunde cu text + opțional notă vocală în limba română!
    """
    update = await request.json()
    message = update.get("message") or update.get("edited_message") or {}
    chat_info = message.get("chat") or {}
    chat_id = chat_info.get("id")
    if not chat_id:
        return {"status": "ignored"}

    user_text = message.get("text", "").strip()
    is_voice = False

    # Dacă pacientul a trimis un mesaj vocal pe Telegram
    voice_obj = message.get("voice") or message.get("audio")
    if not user_text and voice_obj and settings.telegram_bot_token:
        file_id = voice_obj.get("file_id")
        if file_id:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    r_file = await client.get(
                        f"https://api.telegram.org/bot{settings.telegram_bot_token}/getFile",
                        params={"file_id": file_id},
                    )
                    file_path = r_file.json().get("result", {}).get("file_path")
                    if file_path:
                        r_bytes = await client.get(
                            f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"
                        )
                        user_text = await stt_service.transcribe_audio(
                            audio_bytes=r_bytes.content,
                            filename="telegram_voice.ogg",
                            content_type="audio/ogg",
                        )
                        is_voice = True
            except Exception:
                user_text = ""

    if not user_text:
        return {"status": "empty"}

    ai_res = await receptionist_agent.chat(
        session_id=f"tg-{chat_id}",
        user_message=user_text,
        channel="Telegram Bot AI",
    )

    if settings.telegram_bot_token:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": ai_res["reply"]},
                )
                # Dacă pacientul a vorbit vocal, îi trimitem și răspunsul audio în română
                if is_voice:
                    mp3_bytes = await tts_service.synthesize_mp3(ai_res["reply"])
                    await client.post(
                        f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendAudio",
                        data={"chat_id": str(chat_id), "title": "Răspuns Vocal AI"},
                        files={"audio": ("raspuns.mp3", mp3_bytes, "audio/mpeg")},
                    )
        except Exception:
            pass

    return {"status": "replied", "reply": ai_res["reply"]}


@app.post("/api/webhooks/chatwoot")
async def receive_chatwoot_webhook(request: Request) -> dict[str, Any]:
    """
    Webhook Multi-Inbox complet compatibil cu Chatwoot Community Edition și Cloud:
    - Detectează Inbox-ul (după inbox_id, nume sau URL referer ex: dev.avanz.ro)
    - La 'conversation_created' trimite automat mesajul de întâmpinare personalizat al acelui Inbox
    - La 'message_created' răspunde prin Agentul AI adaptat la specificul acelui Inbox + Cal.com
    - Include protecție anti-loop și transfer automat către operator uman (Human Handoff).
    """
    payload = await request.json()
    return await chatwoot_service.process_webhook(payload)


# Montăm interfața web statică
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/widget.js")
async def serve_embed_widget(request: Request, inbox: str = Query("")) -> Response:
    """
    Generează un Widget Flotant (Chat + Voce AI) 100% Gratuit care poate primi și parametrul ?inbox=inbox-avanz-main!
    Poate fi integrat pe dev.avanz.ro sau orice site cu: <script src="https://.../widget.js?inbox=inbox-avanz-main"></script>
    """
    base_url = str(request.base_url).rstrip("/")
    iframe_url = f"{base_url}/?inbox={inbox}" if inbox else f"{base_url}/"
    js_code = f"""
(function() {{
  if (document.getElementById('ai-receptionist-widget-root')) return;
  const root = document.createElement('div');
  root.id = 'ai-receptionist-widget-root';
  root.innerHTML = `
    <div id="ai-rec-window" style="display:none;position:fixed;bottom:90px;right:20px;width:370px;height:560px;max-width:92vw;max-height:80vh;border-radius:16px;overflow:hidden;box-shadow:0 20px 50px rgba(0,0,0,0.45);z-index:999999;border:1px solid #334155;background:#0f172a;">
      <iframe src="{iframe_url}" allow="microphone; autoplay" style="width:100%;height:100%;border:none;"></iframe>
    </div>
    <button id="ai-rec-toggle" style="position:fixed;bottom:20px;right:20px;width:60px;height:60px;border-radius:9999px;background:linear-gradient(135deg,#2563eb,#4f46e5);color:#fff;border:none;cursor:pointer;box-shadow:0 10px 25px rgba(37,99,235,0.5);z-index:999999;font-size:26px;display:flex;align-items:center;justify-content:center;">
      🎙️
    </button>
  `;
  document.body.appendChild(root);
  const btn = document.getElementById('ai-rec-toggle');
  const win = document.getElementById('ai-rec-window');
  btn.addEventListener('click', function() {{
    const isHidden = win.style.display === 'none';
    win.style.display = isHidden ? 'block' : 'none';
    btn.textContent = isHidden ? '✕' : '🎙️';
  }});
}})();
"""
    return Response(content=js_code.strip(), media_type="application/javascript")


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse("static/index.html")
