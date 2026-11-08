# 🧠 GEMINI.md — Arhitectură de Referință & Blueprint Reutilizabil
## Proiect: Recepționer & Call-Center AI 24/7 (Voce + Omnichannel + CRM & Calendar)

Acest document servește ca **Memorie Tehnică (Master Blueprint)** pentru **Antigravity / Gemini** și poate fi copiat în orice proiect viitor (clinici medicale, saloane, cabinete avocatură, restaurante, service-uri auto, imobiliare) pentru a replica instantaneu arhitectura completă **Zero-Cost (0 €/lună)**.

🔗 **Repository de Referință:** [https://github.com/dl-bit/receptioner-ai-24-7](https://github.com/dl-bit/receptioner-ai-24-7)

---

## 1. 🎯 Viziune și Arhitectură Tehnică (Zero-Cost Stack)

Obiectivul arhitecturii este livrarea unui **Recepționer AI 24/7 (Voce + Text)** în limba română, complet conform cu **EU AI Act (Art. 12 & Art. 50)**, fără costuri lunare recurente de infrastructură sau licențe SaaS.

```text
[Canale Pacienți / Clienți]
  ├── Widget Web Flotant (/widget.js) — Voce WebRTC + Chat
  ├── Telegram Bot (@BotFather) — Text + Note Vocale în Română
  ├── Meta WhatsApp Cloud API — Mesaje directe (0 € Service Tier)
  └── Chatwoot Community Edition (Self-Hosted Docker) — Inbox Unificat + Human Handoff
          │
          ▼
[Backend Principal: FastAPI Python 3.11+ (Port 7860)]
  ├── 🎙️ STT (Speech-to-Text): Groq Cloud Free Tier -> model `whisper-large-v3-turbo` (limba `ro`)
  ├── 🧠 LLM + Tool Calling: Groq Cloud Free Tier -> model `openai/gpt-oss-120b`
  ├── 🔊 TTS (Text-to-Speech): Microsoft Edge Neural TTS (`edge-tts` — 100% Gratuit, fără cheie API)
  │       └── Voci neurale RO: `ro-RO-AlinaNeural` (Feminin) & `ro-RO-EmilNeural` (Masculin)
  ├── 📅 CRM & Programări: Cal.com (Open-Source / Cloud Free) sincronizat cu Google Calendar
  │       ├── Suport dublu API v1 (`/v1/slots`, `/v1/bookings`) & API v2 (`/v2/slots/available`)
  │       ├── Auto-detecție `Event Types` (`/v1/event-types` & `/v2/event-types`)
  │       ├── Orare dinamice pe medici/specialiști în `doctors.json` + alocare automată după serviciu
  │       └── Link direct 1-click Google Calendar (`gcal_url`) + Webhook bidirecțional (`/api/webhooks/calcom`)
  └── 🗄️ RAG & Audit: Qdrant Cloud Free (1 GB) + Supabase PostgreSQL Free (cu fallback local In-Memory)
```

---

## 2. 📂 Structura Standard a Proiectului

```text
receptioner_ai_24_7/
├── app/
│   ├── __init__.py
│   ├── config.py                  # Settings (Pydantic), încărcare doctors.json & System Prompt RO
│   ├── main.py                    # Toate rutele FastAPI, Webhooks Omnichannel și /widget.js
│   └── services/
│       ├── __init__.py
│       ├── stt_service.py         # Transcriere audio Groq Whisper (whisper-large-v3-turbo)
│       ├── tts_service.py         # Sinteză vocală neurală Edge-TTS (MP3 în memorie)
│       ├── llm_agent.py           # Agent AI cu Function Calling + Smart Local Fallback
│       ├── cal_service.py         # Integrare Cal.com (v1/v2) + Google Calendar + CRUD Medici
│       ├── chatwoot_service.py    # Conector Chatwoot CE Docker + Anti-Loop + Human Handoff
│       └── storage_service.py     # RAG (bază de cunoștințe sincronizată cu doctors.json) + Audit Logs
├── static/
│   └── index.html                 # Dashboard Web complet + Modale de configurare live
├── chatwoot_hf_space/
│   └── Dockerfile                 # Dockerfile optimizat pentru Chatwoot CE pe Render / HF Spaces
├── doctors.json                   # Catalog persistent medici/specialiști, orare și ID-uri Cal.com
├── Dockerfile                     # Container principal FastAPI (non-root user 1000, port 7860, ffmpeg)
├── docker-compose.chatwoot.yml    # Stack complet local/VPS (FastAPI + Chatwoot CE + Postgres + Redis)
├── render.yaml                    # Blueprint Multi-Service pe același cont Render
├── requirements.txt               # Dependențe Python minimale și rapide
├── .env.example                   # Șablon variabile de mediu (fără chei secrete!)
├── start_local.ps1                # Script PowerShell pentru pornire instantanee cu `uv`
├── test_smoke.py                  # Suită completă de teste automate (End-to-End Smoke Tests)
└── GEMINI.md                      # Acest document de referință arhitecturală
```

---

## 3. ⚙️ Reguli Critice & Lecții Tehnice (Best Practices pentru Proiecte Viitoare)

### 3.1. Modele Groq Active (Actualizare 2026)
- **IMPORTANT:** Modelul vechi `llama-3.3-70b-versatile` a fost retras/deprecat pe anumite conturi Groq (returnează `404 model_not_found`).
- Folosește întotdeauna:
  - `LLM_MODEL=openai/gpt-oss-120b` (suportă nativ *Tool Calling / Function Calling* și limba română la viteză mare).
  - `STT_MODEL=whisper-large-v3-turbo` pentru transcriere vocală în limba română.
- Include întotdeauna un **motor de fallback local (`_local_smart_fallback`)** în `llm_agent.py` astfel încât aplicația să funcționeze 100% chiar și fără cheie API sau când API-ul extern are latență.

### 3.2. Integrarea Cal.com + Google Calendar (`cal_service.py`)
- **Auto-Discovery pentru `CALCOM_EVENT_TYPE_ID`:** Nu obliga utilizatorul să caute manual ID-ul numeric al evenimentului în Cal.com. Când utilizatorul furnizează `CALCOM_API_KEY` (`cal_live_...`), interoghează automat `GET /v1/event-types?apiKey=...` (și fallback `GET /v2/event-types` cu header `Authorization: Bearer ...`) și setează automat primul Event Type activ.
- **Alocare pe Medici / Specialiști (`doctors.json`):**
  - Fiecare specialist are propriul obiect în `doctors.json` cu `name`, `specialty`, `keywords`, `days`, `default_slots` și opțional propriul `calcom_event_type_id` (pentru sincronizare cu propriul său Google Calendar).
  - Când se adaugă sau se modifică un medic prin `POST /api/doctors`, golește cache-ul de sesiuni (`receptionist_agent.sessions.clear()`) pentru ca promptul de sistem al AI-ului să includă imediat noul medic.

### 3.3. Rularea Chatwoot Community Edition (Open-Source Docker) pe Render Free & HF Spaces
- **De ce Chatwoot Community Edition (Self-Hosted):** Varianta găzduită `app.chatwoot.com` restricționează *API Access Tokens* și *Agent Bots* pe planul gratuit. Imaginea oficială Docker `chatwoot/chatwoot:latest` (Community Edition) are **toate funcțiile API 100% deblocate și gratuite**.
- **3 Reguli Obligatorii pentru rularea `chatwoot/chatwoot:latest` pe Render (`render.yaml` & `chatwoot_hf_space/Dockerfile`):**
  1. **Evită `dockerCommand` cu comenzi înlănțuite (`sh -c "cmd1 && cmd2"`) pe `runtime: image` în Render:** Entrypoint-ul `docker/entrypoints/rails.sh` din imaginea Chatwoot face `exec "$@"` și eșuează cu `Exited with status 127`. Folosește întotdeauna `runtime: docker` cu un script `/app/start_render.sh` ca `ENTRYPOINT` în `Dockerfile`.
  2. **Setează explicit `POSTGRES_PORT=5432`:** Utilitarul `pg_isready -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USERNAME` eșuează cu `too many command-line arguments (first is "chatwoot")` dacă `POSTGRES_PORT` este gol!
  3. **Optimizări de Memorie RAM pentru Render Free (512 MB RAM):** Setează variabilele de mediu pentru Ruby Garbage Collector și jemalloc ca să menții consumul sub ~380 MB RAM:
     ```yaml
     WEB_CONCURRENCY: "0"
     RAILS_MAX_THREADS: "3"
     MALLOC_ARENA_MAX: "2"
     RUBY_GC_HEAP_GROWTH_FACTOR: "1.05"
     RUBY_GC_MALLOC_LIMIT: "16777216"
     RUBY_GC_OLDMALLOC_LIMIT: "16777216"
     ```
- **Alternativă Gratuită fără Chatwoot:** Ruta nativă `GET /widget.js` din `app/main.py` generează o bulă flotantă de Chat + Voce AI care poate fi pusă pe orice site cu `<script src="https://.../widget.js"></script>`, fără niciun serviciu extern!

### 3.4. Protecție Anti-Loop & Human Handoff în Chatwoot (`chatwoot_service.py`)
- Răspunde **doar** când `message_type == "incoming"`, `private == False` și `sender.type == "contact"`. Ignoră mesajele trimise de `user` sau `agent_bot` pentru a preveni buclele infinite!
- Dacă pacientul scrie cuvinte precum `operator`, `om real`, `recepționeră`, `transfer`, apelează automat:
  1. Mesaj public de confirmare a transferului.
  2. Notă internă privată (`private: True`) cu rezumatul cererii.
  3. `POST /api/v1/accounts/{account_id}/conversations/{conversation_id}/toggle_status` cu `{"status": "open"}`.

---

## 4. 🔌 Uneltele Agentului AI (Function Calling Schema)

Agentul AI are definite 4 unelte principale în `app/services/llm_agent.py`:
1. **`check_availability(date, doctor, service)`** — Verifică intervalele libere în Cal.com / Google Calendar și `doctors.json`.
2. **`book_appointment(patient_name, phone, date, time, service, doctor)`** — Creează programarea în Cal.com + Google Calendar și returnează codul programării (`CAL-...` sau `BK-...`) și linkul Google Calendar.
3. **`cancel_appointment(booking_id_or_name, reason)`** — Anulează o programare activă din Cal.com și din calendarul local.
4. **`search_clinic_info(query)`** — Caută tarife, servicii, program, adresă, plata în rate și lista medicilor activi.

---

## 5. 🚀 Cum Adaptezi Acest Proiect pentru un Client Nou (în 5 Minute)

1. **Schimbă numele și domeniul afacerii:**
   - În `.env`: setează `CLINIC_NAME=Numele Afacerii Clientului`.
   - În `app/config.py`: actualizează `DEFAULT_CLINIC_KNOWLEDGE` cu prețurile, adresa și serviciile noului client.
2. **Configurează specialiștii și orarele lor:**
   - Editează `doctors.json` (sau folosește butonul **👨‍⚕️ Medici & Orare** direct din interfața web `http://localhost:7860`).
3. **Conectează Cal.com + Google Calendar:**
   - Adaugă `CALCOM_API_KEY` din contul gratuit Cal.com al clientului (prin butonul **⚙️ Cal.com API** din UI sau în `.env`).
4. **Conectează Canalele Omnichannel (Telegram / WhatsApp / Chatwoot CE / Widget Web):**
   - Folosește butonul **💬 Configurare Canale** din UI sau încorporează direct `<script src="https://domeniul-tau/widget.js"></script>` pe site-ul clientului.
5. **Verifică totul cu suita de teste automate:**
   ```powershell
   uv run --with-requirements requirements.txt python test_smoke.py
   ```
