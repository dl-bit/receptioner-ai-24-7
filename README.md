---
title: Receptioner AI 24/7 (Voce + WhatsApp + Cal.com)
emoji: 🎙️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# 🎙️ Recepționer & Call-Center AI 24/7 (Voce + WhatsApp + Cal.com & Google Calendar)

Acest proiect implementează **Recepționerul & Call-Center-ul AI 24/7** în limba română, optimizat pentru **Cost 0 €** și pregătit pentru rulare locală sau în cloud (**Hugging Face Spaces Docker — 2 vCPU, 16 GB RAM Gratuit**, **Render** sau **Docker**).

🔗 **Repository GitHub:** [https://github.com/dl-bit/receptioner-ai-24-7](https://github.com/dl-bit/receptioner-ai-24-7)

---

## 🚀 Arhitectura Tehnică (Zero-Cost Stack)

```text
[Widget Web Audio/Text / Meta WhatsApp / Telegram / Chatwoot]
       │
       ▼
[FastAPI Server (Port 7860 - Local / Hugging Face / Render)]
       ├──► [STT: Groq Whisper-Large-v3-Turbo (Free API)]
       ├──► [LLM + Tool Calling: Groq (openai/gpt-oss-120b)]
       ├──► [CRM & Programări: Cal.com API (v1 & v2) ◄──► Google Calendar Sync]
       ├──► [Management Medici & Orare: doctors.json + Panou Web Live]
       ├──► [RAG & Audit EU AI Act: Qdrant Cloud Free + Supabase PostgreSQL]
       └──► [TTS Română: Microsoft Edge Neural TTS (ro-RO-AlinaNeural / EmilNeural)]
```

---

## ✨ Funcționalități Noi și Actualizări Recente

### 1. 📅 Integrare Completă CRM & Programări: Cal.com + Google Calendar
- **Suport Cal.com Open-Source & Cloud Free (API v1 + v2):** Funcționează atât cu contul gratuit de pe `https://api.cal.com`, cât și cu instanțe Cal.com self-hosted (`CALCOM_API_URL`).
- **Auto-Detecție `Event Types`:** Este suficient să introduci cheia `CALCOM_API_KEY` (`cal_live_...`), iar aplicația interoghează automat `/v1/event-types` și `/v2/event-types` pentru a descoperi tipurile de programări fără configurare manuală.
- **Verificare Ore Libere în Timp Real (`check_availability`):** Agentul AI verifică intervalele libere din Cal.com (care filtrează automat evenimentele ocupate din **Google Calendar**-ul medicilor) și propune pacientului orele disponibile.
- **Creare & Anulare Programări (`book_appointment` / `cancel_appointment`):** Înregistrează programarea direct în Cal.com + Google Calendar și generează pentru fiecare programare un link direct **📅 Google Calendar ↗**.
- **Webhook Bidirecțional (`POST /api/webhooks/calcom`):** Primește notificări în timp real (`BOOKING_CREATED`, `BOOKING_RESCHEDULED`, `BOOKING_CANCELLED`) atunci când o programare este creată, reprogramată sau anulată direct în Cal.com sau Google Calendar.
- **Modal Web de Configurare Rapidă (`⚙️ Cal.com API`):** Permite salvarea cheii `CALCOM_API_KEY` direct din interfața web în fișierul `.env` și testarea conexiunii cu 1 click.

### 2. 👨‍⚕️ Administrare Dinamică Medici & Calendare (`doctors.json` + UI)
- **Panou Vizual `👨‍⚕️ Medici & Orare` în Interfața Web:** Poți adăuga medici noi, modifica orele disponibile (`09:00, 10:30, 12:00...`), specialitatea sau șterge medici direct din browser, fără să modifici codul sursă.
- **Mapare Individuală pe Google Calendar (`calcom_event_type_id`):** Fiecare medic poate avea propriul său `calcom_event_type_id` sincronizat cu propriul său Google Calendar în Cal.com.
- **Sincronizare Automată cu Promptul AI:** Orice modificare a medicilor în `doctors.json` sau în interfața web actualizează instantaneu promptul de sistem al agentului AI și filtrele din calendar.

---

## 📦 Structura Proiectului

- `app/main.py` — Serverul FastAPI (rute pentru Chat, Voice Turn WebRTC, Cal.com configurare/sincronizare/webhook, CRUD medici în `/api/doctors`, programări `/api/appointments` și webhook-uri WhatsApp/Chatwoot).
- `app/config.py` — Configurare centralizată (`Settings`), încărcare/salvare dinamică `doctors.json` și generarea promptului de sistem al recepționerului AI.
- `app/services/cal_service.py` — Conector complet **Cal.com API v1/v2 + Google Calendar**, alocare automată a medicului pe baza serviciului stomatologic, generare linkuri Google Calendar și procesare webhook-uri.
- `app/services/llm_agent.py` — Agentul conversațional AI (`openai/gpt-oss-120b` pe Groq) cu *Function Calling / Tool Use*:
  - `check_availability(date, doctor, service)`
  - `book_appointment(patient_name, phone, date, time, service, doctor)`
  - `cancel_appointment(booking_id_or_name, reason)`
  - `search_clinic_info(query)`
- `app/services/stt_service.py` — Transcriere vocală în limba română prin Groq Whisper API (`whisper-large-v3-turbo`).
- `app/services/tts_service.py` — Sinteză vocală neurală gratuită în limba română (`edge-tts`: `ro-RO-AlinaNeural` și `ro-RO-EmilNeural`).
- `app/services/storage_service.py` — Conectori pentru **Qdrant Cloud Free** (RAG) și **Supabase Free** (jurnalizare conversații conform EU AI Act Art. 12 & 50).
- `doctors.json` — Catalogul persistent al medicilor clinicii, specialităților, cuvintelor-cheie, zilelor lucrătoare, orelor disponibile și ID-urilor Cal.com.
- `static/index.html` — Interfața Web modernă cu microfon live, chat AI, filtru de calendar după medic și dată, fereastră de administrare **👨‍⚕️ Medici & Orare** și fereastră de conectare **⚙️ Cal.com API**.
- `test_smoke.py` — Suită de teste automate pentru Healthcheck, Cal.com status, verificare disponibilitate AI, creare programare, sinteză audio MP3 și webhook Cal.com.

---

## 🔌 Rute API Principale

| Metodă | Rută | Descriere |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Healthcheck & Keep-Alive (stare Groq, Cal.com, lista medici) |
| `POST` | `/api/chat` | Conversație text cu Agentul AI + Tool Calling + Audio MP3 Base64 |
| `POST` | `/api/voice-turn` | Conversație vocală completă (Audio WebM ➔ STT ➔ LLM ➔ Cal.com ➔ TTS) |
| `GET` | `/api/appointments` | Listează programările și orele libere (filtrabil după `?date=YYYY-MM-DD&doctor=...`) |
| `POST` | `/api/appointments` | Creează o programare manuală în Cal.com + Google Calendar |
| `DELETE` | `/api/appointments/{id}` | Anulează o programare existentă în Cal.com și panoul local |
| `GET` | `/api/doctors` | Returnează lista medicilor și orarele lor din `doctors.json` |
| `POST` | `/api/doctors` | Adaugă un medic nou sau actualizează orarul/calendarul unui medic existent |
| `DELETE` | `/api/doctors/{id}` | Șterge un medic din `doctors.json` |
| `GET` | `/api/calcom/status` | Verifică starea conexiunii Cal.com și descoperă automat `Event Types` |
| `POST` | `/api/calcom/configure` | Salvează cheia `CALCOM_API_KEY` în `.env`, detectează `Event Types` și sincronizează |
| `POST` | `/api/calcom/sync` | Sincronizează programările viitoare din Cal.com în panoul live |
| `POST` | `/api/webhooks/calcom` | Webhook în timp real pentru evenimente Cal.com / Google Calendar |

---

## 🛠️ Cum Conectezi Cal.com (Gratuit) + Google Calendar

1. Creează un cont gratuit pe [app.cal.com](https://app.cal.com) (sau folosește propria instanță open-source) și conectează **Google Calendar** din **Apps ➔ Google Calendar**.
2. Mergi în [Settings ➔ Developer ➔ API Keys](https://app.cal.com/settings/developer/api-keys) și generează o cheie API (`cal_live_...`).
3. Deschide aplicația la **http://localhost:7860**, apasă pe butonul **⚙️ Cal.com API** (sau editează `.env`) și lipește cheia `cal_live_...`. Aplicația va detecta automat `Event Types` și va sincroniza programările!
4. Pentru a aloca Google Calendar-uri diferite pentru fiecare medic, creează câte un *Event Type* în Cal.com pentru fiecare medic și treci ID-ul respectiv în fereastra **👨‍⚕️ Medici & Orare** (sau în `doctors.json` la `calcom_event_type_id`).

---

## 💻 Cum Rulezi Local pe Windows

```powershell
cd C:\Users\Administrator\.gemini\antigravity\scratch\receptioner_ai_24_7
.\start_local.ps1
```

Sau direct cu `uv`:

```powershell
uv run --with-requirements requirements.txt uvicorn app.main:app --reload --port 7860
```

Apoi deschide în browser: **http://localhost:7860**

Pentru rularea testelor automate:

```powershell
uv run --with-requirements requirements.txt python test_smoke.py
```
