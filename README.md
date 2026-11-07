---
title: Receptioner AI 24/7 (Voce + WhatsApp)
emoji: 🎙️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# 🎙️ Recepționer & Call-Center AI 24/7 (Voce + WhatsApp + Web)

Acest proiect implementează **Pachetul 2: Recepționer & Call-Center AI 24/7** în limba română, optimizat pentru **Cost 0 €** și gata de lansare pe **Hugging Face Spaces (Docker - 2 vCPU, 16 GB RAM Gratuit)**.

## 🚀 Arhitectura Tehnică (Zero-Cost Stack)

```
[Widget Web Audio/Text / Telegram / Meta WhatsApp / Chatwoot]
       │
       ▼
[FastAPI Server (Port 7860 - Hugging Face Docker Space)]
       ├──► [STT: Groq Whisper-Large-v3-Turbo (Free API)]
       ├──► [RAG & Memorie: Qdrant Cloud Free + Supabase PostgreSQL]
       ├──► [LLM + Tool Calling: Groq (Llama-3.3-70b) / Gemini 2.5 Flash Free]
       ├──► [CRM & Programări: Cal.com API v1/v2 + Google Calendar]
       └──► [TTS Română: Microsoft Edge Neural TTS (ro-RO-AlinaNeural / EmilNeural)]
```

## 📦 Structura Proiectului

- `Dockerfile` — Container optimizat pentru Hugging Face Spaces (utilizator non-root `1000`, port `7860`, `ffmpeg` preinstalat).
- `requirements.txt` — Dependențe Python (`fastapi`, `edge-tts`, `httpx`, `qdrant-client`, `pydantic-settings`).
- `.env.example` — Șablon pentru variabilele de mediu (Secrets în Hugging Face Spaces).
- `app/main.py` — Serverul principal FastAPI (rute pentru Web Voice/Chat, Healthcheck pentru `cron-job.org`, Webhook-uri pentru Meta WhatsApp, Telegram și Chatwoot/Typebot).
- `app/config.py` — Configurare centralizată și prompt-ul de sistem al recepționerului AI.
- `app/services/stt_service.py` — Transcriere vocală ultra-rapidă în limba română prin Groq Whisper API (`whisper-large-v3-turbo`).
- `app/services/tts_service.py` — Sinteză vocală neurală 100% gratuită în limba română (`edge-tts`: `ro-RO-AlinaNeural` și `ro-RO-EmilNeural`).
- `app/services/cal_service.py` — Integrare reală cu **Cal.com API** pentru verificarea orelor libere și crearea programărilor (cu fallback inteligent de simulare pentru demo-uri rapide).
- `app/services/storage_service.py` — Conectori pentru **Qdrant Cloud Free** (bază de cunoștințe RAG: prețuri, servicii, medici) și **Supabase Free** (jurnalizare conversații și programări).
- `app/services/llm_agent.py` — Agentul conversațional cu *Function Calling / Tool Use* (`check_availability`, `book_appointment`, `search_clinic_info`).
- `static/index.html` — Interfață Web modernă de Demo („Clinica Stomatologică Demo Smile”) cu buton de microfon, chat live, selector de voce (`Alina` / `Emil`), panou de programări în timp real și cod de embed pentru site-urile clienților.

---

## 🛠️ Cum îl rulezi pe Hugging Face Spaces (100% Gratuit, Fără Card)

1. Mergi pe [huggingface.co/spaces](https://huggingface.co/spaces) și apasă **Create new Space**.
2. Alege un nume (ex: `receptioner-ai-ro`), selectează **Docker** ca SDK (template **Blank**) și hardware **CPU Basic (Free - 2 vCPU · 16 GB RAM)**.
3. În tab-ul **Settings ➔ Variables and secrets**, adaugă cel puțin cheia gratuită de la Groq:
   - `GROQ_API_KEY` (obținută gratuit de pe [console.groq.com](https://console.groq.com))
   - *(Opțional)* `CALCOM_API_KEY`, `CALCOM_EVENT_TYPE_ID`, `QDRANT_URL`, `QDRANT_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`.
4. Încarcă fișierele din acest folder în Space-ul tău (prin interfața web `Files ➔ Add file ➔ Upload files` sau prin `git push`).
5. Pentru a preveni intrarea în *sleep* după 48h, creează un cont gratuit pe [cron-job.org](https://cron-job.org) sau [UptimeRobot](https://uptimerobot.com) și setează un ping la fiecare 10 minute către:
   `https://<username>-<space-name>.hf.space/api/health`

---

## 💻 Cum îl rulezi Local pe PC-ul tău (Windows)

```powershell
cd C:\Users\Administrator\.gemini\antigravity\scratch\receptioner_ai_24_7
copy .env.example .env
# Editează .env și adaugă GROQ_API_KEY (sau testează direct în modul Demo inteligent!)
uv run --with-requirements requirements.txt uvicorn app.main:app --reload --port 7860
```

Apoi deschide în browser: **http://localhost:7860**
