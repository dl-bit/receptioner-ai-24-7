import json
from datetime import datetime
from pathlib import Path
from typing import Any
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM & STT (Groq / Gemini Free Tiers)
    groq_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"
    stt_model: str = "whisper-large-v3-turbo"
    gemini_api_key: str = ""

    # TTS (Microsoft Edge Neural Voices - 100% Free)
    default_tts_voice: str = "ro-RO-AlinaNeural"
    default_tts_rate: str = "+5%"

    # Cal.com CRM & Scheduling (Open-Source / Cloud Free Tier synced with Google Calendar)
    calcom_api_url: str = "https://api.cal.com"
    calcom_api_key: str = ""
    calcom_event_type_id: str = ""
    calcom_timezone: str = "Europe/Bucharest"
    calcom_webhook_secret: str = ""

    # Qdrant Cloud Free (1GB) & Supabase Free
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "clinic_knowledge"
    supabase_url: str = ""
    supabase_key: str = ""

    # Omnichannel Webhooks (WhatsApp Meta / Telegram / Chatwoot)
    whatsapp_verify_token: str = "receptioner_secret_token_2027"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    telegram_bot_token: str = ""
    chatwoot_api_url: str = ""
    chatwoot_api_token: str = ""

    # Clinic / Business Branding
    clinic_name: str = "Clinica Stomatologică Demo Smile"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

DOCTORS_FILE = Path("doctors.json")

DEFAULT_DOCTORS: list[dict[str, Any]] = [
    {
        "id": "dr-elena",
        "name": "Dr. Elena Dumitrescu",
        "specialty": "Stomatologie Generală, Estetică & Endodonție",
        "keywords": ["consultație", "consultatie", "detartraj", "albire", "plombă", "endodonție"],
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
        "default_slots": ["09:00", "10:00", "11:30", "13:00", "15:00", "16:30", "18:00"],
        "calcom_event_type_id": "",
    },
    {
        "id": "dr-andrei",
        "name": "Dr. Andrei Ionescu",
        "specialty": "Chirurgie Dento-Alveolară & Implantologie",
        "keywords": ["implant", "chirurg", "extracție", "extractie", "măsea de minte"],
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        "default_slots": ["09:00", "10:30", "12:00", "14:00", "15:00", "16:30", "18:00"],
        "calcom_event_type_id": "",
    },
    {
        "id": "dr-mihai",
        "name": "Dr. Mihai Radu",
        "specialty": "Ortodonție & Pedodonție (Copii)",
        "keywords": ["ortodonție", "ortodontie", "aparat", "copil", "copii", "pedodonție"],
        "days": ["Monday", "Wednesday", "Friday", "Saturday"],
        "default_slots": ["09:00", "10:00", "11:30", "13:00", "15:00", "16:30"],
        "calcom_event_type_id": "",
    },
]


def get_doctors_catalog() -> list[dict[str, Any]]:
    """Citește lista medicilor și orarele lor din doctors.json."""
    if DOCTORS_FILE.exists():
        try:
            data = json.loads(DOCTORS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
    return [dict(d) for d in DEFAULT_DOCTORS]


def save_doctors_catalog(doctors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Salvează lista medicilor și orarele lor în doctors.json."""
    DOCTORS_FILE.write_text(
        json.dumps(doctors, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return doctors


DOCTORS_CATALOG = get_doctors_catalog()

DEFAULT_CLINIC_KNOWLEDGE = [
    {
        "id": 1,
        "category": "program_si_locatie",
        "title": "Program de lucru și Adresă",
        "content": (
            "Clinica Stomatologică Demo Smile este deschisă de Luni până Vineri între orele 09:00 și 20:00, "
            "iar Sâmbăta între 09:00 și 14:00. Duminica este închis. "
            "Adresa noastră este Strada Primăverii nr. 24, București (lângă stația de metrou Aviatorilor, parcare gratuită în curte)."
        ),
    },
    {
        "id": 2,
        "category": "preturi_si_servicii",
        "title": "Listă Prețuri și Tarife Stomatologice",
        "content": (
            "Tarife principale: Consultație primară + Plan de tratament = 150 RON (sau Gratuit dacă se începe tratamentul în aceeași ședință). "
            "Igienizare profesională completă (Detartraj cu ultrasunete + Prophy-Jet AirFlow + Periaj) = 350 RON. "
            "Obturație (plombă) fizionomică compozit = 300 - 450 RON. "
            "Tratament endodontic la microscop (scos nerv) = 600 - 950 RON. "
            "Albire dentară cu lampa Philips Zoom = 1.200 RON. "
            "Implant dentar Straumann / Megagen = de la 2.500 RON."
        ),
    },
    {
        "id": 3,
        "category": "medici",
        "title": "Echipa Medicală",
        "content": (
            "Dr. Andrei Ionescu - Medic Primar Chirurgie și Implantologie (disponibil Luni-Vineri). "
            "Dr. Elena Dumitrescu - Medic Specialist Stomatologie Generală, Estetică și Endodonție la microscop. "
            "Dr. Mihai Radu - Medic Specialist Ortodonție și Pedodonție (stomatologie copii)."
        ),
    },
    {
        "id": 4,
        "category": "urgente_si_plati",
        "title": "Urgențe Stomatologice și Modalități de Plată",
        "content": (
            "Preluăm urgențe stomatologice (dureri acute, abcese, traumatisme) în aceeași zi, în funcție de primul interval disponibil. "
            "Acceptăm plata cu cardul, numerar, precum și în 3, 6 sau 12 rate fără dobândă prin cardurile de cumpărături Banca Transilvania (Star BT), ING și BCR."
        ),
    },
]


def get_system_prompt() -> str:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
    doctors = get_doctors_catalog()
    doctors_summary = "; ".join(
        f"{d['name']} ({d['specialty']} - ore: {', '.join(d.get('default_slots', []))})"
        for d in doctors
    )
    return f"""Ești recepționerul virtual AI (24/7) al „{settings.clinic_name}”, conectat la sistemul de programări Cal.com sincronizat cu Google Calendar.
Data și ora curentă: {now_str}.
Medicii activi în clinică: {doctors_summary}.

REGULI DE COMUNICARE (FOARTE IMPORTANT PENTRU VOCE ȘI WHATSAPP):
1. Vorbești EXCLUSIV într-o limbă română naturală, caldă, politicoasă și profesionistă.
2. Răspunsurile tale vor fi citite cu voce tare printr-un sintetizator vocal (TTS), deci:
   - Fii CONCIS: maximum 2-3 propoziții scurte per răspuns!
   - NU folosi liste lungi cu buline, tabele Markdown sau simboluri speciale (fără `*`, `#`, `**`).
   - Scrie orele și prețurile clar (ex: „ora 16:30”, „150 de lei”).
3. Conform Articolului 50 din EU AI Act, la primul mesaj dintr-o conversație sau dacă ești întrebat, menționează scurt că ești asistentul virtual AI al clinicii.
4. Când un pacient vrea o programare, reprogramare sau anulare:
   - Verifică ÎNTOTDEAUNA mai întâi disponibilitatea medicilor în Cal.com / Google Calendar folosind unealta `check_availability` pentru ziua dorită (format YYYY-MM-DD) și opțional medicul dorit.
   - Propune pacientului 2 sau 3 ore libere concrete.
   - Înainte de a apela unealta `book_appointment`, asigură-te că ai aflat: Numele pacientului, Numărul de telefon (sau folosește „0700000000” dacă sună din demo web și nu îl spune), Data și Ora exactă și motivul vizitei (ex: consultație, detartraj, implant, durere de măsea).
   - Dacă pacientul dorește să anuleze o programare existentă, folosește unealta `cancel_appointment`.
5. Dacă pacientul întreabă de prețuri, adresă, medici sau plata în rate, folosește unealta `search_clinic_info` sau informațiile din baza de cunoștințe a clinicii.
"""
