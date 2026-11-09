import json
import re
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
    clinic_name: str = "AvanzCRM (dev.avanz.ro) & Multi-Inbox AI"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

DOCTORS_FILE = Path("doctors.json")
INBOXES_FILE = Path("inboxes.json")

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

DEFAULT_INBOXES: list[dict[str, Any]] = [
    {
        "id": "inbox-avanz-main",
        "inbox_id": "1",
        "name": "AvanzCRM — Consultanță & Demo (dev.avanz.ro)",
        "domain": "dev.avanz.ro",
        "channel_type": "Channel::WebWidget",
        "is_default": True,
        "welcome_message": (
            "Bună ziua! 👋 Bine ați venit pe dev.avanz.ro! Sunt consultantul virtual AI al platformei "
            "AvanzCRM (Enterprise CRM & ERP). Vă pot ajuta cu detalii despre Catalog & SKU, Trasee GPS "
            "pentru agenți, integrarea e-Factura ANAF & SmartBill sau programarea unui Demo Live. "
            "Cu ce vă pot ajuta astăzi?"
        ),
        "handoff_message": (
            "Am înțeles! Vă transfer imediat către un consultant de implementare AvanzCRM. "
            "Un specialist din echipa noastră va prelua această conversație în câteva momente."
        ),
        "site_specificity": (
            "Platforma AvanzCRM (dev.avanz.ro / avanz.ro) este un sistem Enterprise CRM & ERP din România "
            "adaptat pentru distribuție, agricultură, tehnic, zootehnie și servicii profesionale. "
            "Funcționalități principale: 1) Catalog și categorii personalizabile pe articole, stocuri și coduri SKU; "
            "2) Trasee de teren, vizite clienți și pontaj GPS în timp real pentru agenții de vânzări; "
            "3) Integrare nativă e-Factura (SPV ANAF) și SmartBill pentru facturare automată; "
            "4) Aprobare de sarcini (workflows), gestiune multi-tenant și rapoarte manageriale. "
            "Obiectivul asistentului AI este să răspundă clar la întrebările despre modulele AvanzCRM, "
            "să ofere suport pe mediul dev.avanz.ro și să programeze sesiuni Demo Live sau Onboarding Tehnic în Cal.com."
        ),
        "quick_prompts": [
            "Ce module include platforma AvanzCRM pe dev.avanz.ro?",
            "Cum funcționează integrarea e-Factura ANAF și pontajul GPS pentru agenți?",
            "Vreau să programez un Demo Live AvanzCRM mâine la ora 15:00",
        ],
    },
    {
        "id": "inbox-avanz-support",
        "inbox_id": "2",
        "name": "AvanzCRM — Suport Tehnic & QA (dev.avanz.ro)",
        "domain": "dev.avanz.ro",
        "channel_type": "Channel::WebWidget",
        "is_default": False,
        "welcome_message": (
            "Salut! 🛠️ Ai deschis canalul de Suport Tehnic & QA pentru mediul dev.avanz.ro. "
            "Spune-mi ce modul testezi (API, e-Factura SPV, SmartBill, Trasee GPS sau Catalog SKU), "
            "ce eroare întâmpini sau dacă dorești să programezi o sesiune tehnică cu un inginer DevOps/ERP!"
        ),
        "handoff_message": (
            "Am înregistrat tichetul tău tehnic pentru dev.avanz.ro! "
            "Transfer conversația acum către un inginer din echipa de suport AvanzCRM."
        ),
        "site_specificity": (
            "Acest inbox este dedicat Suportului Tehnic, QA și testării pe mediul de dezvoltare dev.avanz.ro. "
            "Asistentul AI ajută utilizatorii și testerii cu: 1) Diagnosticarea sincronizării e-Factura ANAF SPV și SmartBill API; "
            "2) Verificarea permisiunilor multi-tenant și a rolurilor de aprobare sarcini; "
            "3) Configurarea nomenclatoarelor SKU și a rutelor GPS pentru agenți; "
            "4) Preluarea rapoartelor de bug-uri și programarea unei sesiuni de debugging sau onboarding tehnic."
        ),
        "quick_prompts": [
            "Am o întrebare despre sincronizarea e-Factura și SmartBill în dev.avanz.ro",
            "Cum configurez rolurile multi-tenant și aprobarea de sarcini?",
            "Vreau să vorbesc cu un operator uman de la suport tehnic",
        ],
    },
    {
        "id": "inbox-demo-smile",
        "inbox_id": "3",
        "name": "Clinica Stomatologică Demo Smile",
        "domain": "demosmile.ro",
        "channel_type": "Channel::WebWidget",
        "is_default": False,
        "welcome_message": (
            "Bună ziua! 😊 Sunt recepționerul virtual AI al Clinicii Stomatologice Demo Smile. "
            "Vă pot ajuta pe loc cu verificarea orelor libere ale medicilor în Cal.com, crearea unei programări "
            "sau informații despre tarife și plata în rate!"
        ),
        "handoff_message": (
            "Am înțeles! Vă transfer imediat către o colegă de la recepția clinicii. "
            "Un operator uman va prelua conversația în câteva momente."
        ),
        "site_specificity": (
            "Clinică stomatologică modernă (Stomatologie generală, Implantologie, Ortodonție, Endodonție la microscop). "
            "Consultație primară 150 RON, Detartraj + AirFlow 350 RON, Implant dentar de la 2.500 RON. "
            "Plata în până la 12 rate fără dobândă."
        ),
        "quick_prompts": [
            "Ce ore libere aveți mâine pentru o consultație?",
            "Cât costă un detartraj și o consultație?",
            "Vreau să mă programez mâine la ora 16:30",
        ],
    },
]


def get_doctors_catalog() -> list[dict[str, Any]]:
    """Citește lista medicilor/specialiștilor și orarele lor din doctors.json."""
    if DOCTORS_FILE.exists():
        try:
            data = json.loads(DOCTORS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
    return [dict(d) for d in DEFAULT_DOCTORS]


def save_doctors_catalog(doctors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Salvează lista medicilor/specialiștilor și orarele lor în doctors.json."""
    DOCTORS_FILE.write_text(
        json.dumps(doctors, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return doctors


def get_inboxes_catalog() -> list[dict[str, Any]]:
    """Citește lista inbox-urilor Chatwoot și mesajele personalizate din inboxes.json."""
    if INBOXES_FILE.exists():
        try:
            data = json.loads(INBOXES_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
    return [dict(item) for item in DEFAULT_INBOXES]


def save_inboxes_catalog(inboxes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Salvează lista inbox-urilor Chatwoot în inboxes.json."""
    INBOXES_FILE.write_text(
        json.dumps(inboxes, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return inboxes


def build_auto_inbox_template(
    name: str,
    domain: str = "",
    site_specificity: str = "",
    inbox_id: str = "",
    channel_type: str = "Channel::WebWidget",
) -> dict[str, Any]:
    """
    Construiește automat mesajele personalizate (welcome_message, handoff_message,
    site_specificity și quick_prompts) pentru un Inbox nou în funcție de specificul site-ului!
    """
    clean_name = (name or domain or "Inbox Nou").strip()
    clean_domain = (domain or "").strip().lower()
    spec_text = (site_specificity or "").strip()
    combined = f"{clean_name} {clean_domain} {spec_text}".lower()

    slug = re.sub(r"[^a-z0-9]+", "-", clean_name.lower()).strip("-") or "custom"
    profile_id = f"inbox-{slug[:28]}"

    # 1. Specificul AvanzCRM / dev.avanz.ro / CRM / ERP / B2B Software
    if any(k in combined for k in ["avanz", "crm", "erp", "efactura", "e-factura", "smartbill", "sku", "gps", "saas", "software"]):
        target_domain = clean_domain or "dev.avanz.ro"
        if not spec_text:
            spec_text = (
                f"Platforma {clean_name} ({target_domain}) — soluție Enterprise CRM & ERP cu gestiune Catalog & SKU, "
                "Trasee de teren și pontaj GPS pentru agenți de vânzări, integrare automată e-Factura ANAF (SPV) & SmartBill, "
                "aprobare sarcini și arhitectură multi-tenant pentru distribuție, agricultură, tehnic și servicii."
            )
        welcome_msg = (
            f"Bună ziua! 👋 Bine ați venit pe {target_domain}! Sunt consultantul virtual AI pentru „{clean_name}”. "
            "Vă pot ajuta cu detalii despre modulele CRM/ERP (Catalog SKU, Trasee GPS, e-Factura ANAF & SmartBill), "
            "suport tehnic sau programarea unui Demo Live. Cu ce vă pot ajuta astăzi?"
        )
        handoff_msg = (
            f"Am înțeles! Vă transfer imediat către un specialist din echipa {clean_name} ({target_domain}). "
            "Un consultant uman va prelua conversația în câteva momente."
        )
        prompts = [
            f"Ce funcționalități oferă {clean_name} pe {target_domain}?",
            "Cum funcționează sincronizarea e-Factura ANAF și pontajul GPS?",
            "Vreau să programez un Demo Live mâine la ora 15:00",
        ]
    # 2. Specificul Medical / Clinică / Stomatologie / Cabinet
    elif any(k in combined for k in ["clinic", "stomatolog", "dent", "medic", "spital", "cabinet", "oftalmolog", "estetic"]):
        target_domain = clean_domain or "clinica-ta.ro"
        if not spec_text:
            spec_text = (
                f"{clean_name} ({target_domain}) — servicii medicale și consultații de specialitate, "
                "verificare ore libere medici în Cal.com & Google Calendar, programări rapide și informații despre tarife."
            )
        welcome_msg = (
            f"Bună ziua! 😊 Sunt recepționerul virtual AI al „{clean_name}”. "
            "Vă pot ajuta pe loc cu verificarea orelor libere ale medicilor în calendar, "
            "crearea unei programări sau informații despre prețuri și servicii. Cu ce vă pot ajuta?"
        )
        handoff_msg = (
            f"Am înțeles! Vă transfer imediat către un coleg de la recepția „{clean_name}”. "
            "Un operator uman va prelua această conversație în câteva momente."
        )
        prompts = [
            "Ce ore libere aveți mâine pentru o consultație?",
            "Care sunt tarifele principale și modalitățile de plată?",
            "Vreau să fac o programare mâine la ora 16:30",
        ]
    # 3. Specificul E-Commerce / Magazin Online / Distribuție
    elif any(k in combined for k in ["magazin", "shop", "store", "comenzi", "livrare", "produse", "distributie", "distribuție"]):
        target_domain = clean_domain or "magazin.ro"
        if not spec_text:
            spec_text = (
                f"{clean_name} ({target_domain}) — suport clienți și consultanță comenzi B2B/B2C, "
                "verificare stocuri, status livrare, retururi, facturare și programare discuții cu un agent de vânzări."
            )
        welcome_msg = (
            f"Bună ziua! 🛒 Bine ați venit pe {clean_name}! Sunt asistentul virtual AI și vă pot ajuta "
            "cu informații despre produse, stocuri, statusul comenzilor sau programarea unei discuții cu un consultant."
        )
        handoff_msg = (
            f"Vă transfer imediat către un consultant de vânzări al {clean_name}. "
            "Un operator uman va prelua conversația în câteva momente."
        )
        prompts = [
            "Cum pot verifica disponibilitatea produselor și termenul de livrare?",
            "Doresc o ofertă personalizată B2B",
            "Vreau să vorbesc cu un consultant uman",
        ]
    # 4. Orice alt site / afacere (Imobiliare, Avocatură, Service Auto, Horeca, etc.)
    else:
        target_domain = clean_domain or "site-ul nostru"
        if not spec_text:
            spec_text = (
                f"Asistent virtual AI dedicat pentru „{clean_name}” ({target_domain}). "
                "Oferă informații despre servicii, tarife, program de lucru, suport clienți și programări directe în Cal.com."
            )
        welcome_msg = (
            f"Bună ziua! 👋 Bine ați venit pe {clean_name}! Sunt asistentul virtual AI (24/7) "
            f"adaptat pentru {target_domain}. Vă pot ajuta cu informații rapide despre serviciile noastre "
            "sau cu înregistrarea unei programări în calendar. Cu ce vă pot fi de folos astăzi?"
        )
        handoff_msg = (
            f"Am înțeles! Vă transfer imediat către un specialist din echipa „{clean_name}”. "
            "Un operator uman va prelua conversația în câteva momente."
        )
        prompts = [
            f"Ce servicii oferă {clean_name}?",
            "Ce intervale libere aveți mâine pentru o programare?",
            "Vreau să vorbesc cu un operator uman",
        ]

    return {
        "id": profile_id,
        "inbox_id": str(inbox_id).strip(),
        "name": clean_name,
        "domain": clean_domain,
        "channel_type": channel_type,
        "is_default": False,
        "welcome_message": welcome_msg,
        "handoff_message": handoff_msg,
        "site_specificity": spec_text,
        "quick_prompts": prompts,
    }


def resolve_inbox_profile(
    inbox_id: str | int | None = None,
    inbox_name: str | None = None,
    referer_url: str | None = None,
    profile_id: str | None = None,
    auto_register_new: bool = True,
) -> dict[str, Any]:
    """
    Identifică profilul personalizat al Inbox-ului din Chatwoot după:
      1. profile_id explicit (din UI/API)
      2. inbox_id din Chatwoot (ex: 1, 2, 3...)
      3. domeniul din referer_url sau inbox_name (ex: dev.avanz.ro)
      4. Dacă este un Inbox complet nou în Chatwoot și auto_register_new=True,
         îl creează și îl salvează automat în inboxes.json cu mesaje personalizate!
    """
    inboxes = get_inboxes_catalog()
    str_inbox_id = str(inbox_id).strip() if inbox_id is not None and str(inbox_id).strip() else ""
    clean_name = (inbox_name or "").strip()
    clean_ref = (referer_url or "").strip().lower()

    # 1. Căutare după profile_id
    if profile_id:
        for item in inboxes:
            if item.get("id") == profile_id:
                return item

    # 2. Căutare după inbox_id din Chatwoot
    if str_inbox_id:
        for item in inboxes:
            if str(item.get("inbox_id", "")).strip() == str_inbox_id:
                return item

    # 3. Căutare după domeniu în referer_url sau inbox_name
    if clean_ref or clean_name:
        haystack = f"{clean_name.lower()} {clean_ref}"
        for item in inboxes:
            dom = (item.get("domain") or "").strip().lower()
            name_low = (item.get("name") or "").strip().lower()
            if dom and dom in haystack:
                return item
            if name_low and (name_low in haystack or clean_name.lower() in name_low):
                return item

    # 4. Dacă avem un inbox_id sau inbox_name nou venit din Chatwoot, îl auto-înregistrăm!
    if auto_register_new and (str_inbox_id or clean_name):
        extracted_domain = ""
        if clean_ref:
            m = re.search(r"https?://([^/:\s]+)", clean_ref)
            if m:
                extracted_domain = m.group(1)
        if not extracted_domain and "." in clean_name:
            m2 = re.search(r"([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", clean_name)
            if m2:
                extracted_domain = m2.group(1).lower()

        new_profile = build_auto_inbox_template(
            name=clean_name or f"Inbox #{str_inbox_id}",
            domain=extracted_domain or "dev.avanz.ro",
            inbox_id=str_inbox_id,
        )
        inboxes.append(new_profile)
        save_inboxes_catalog(inboxes)
        return new_profile

    # 5. Fallback la profilul default (AvanzCRM dev.avanz.ro)
    for item in inboxes:
        if item.get("is_default"):
            return item
    return inboxes[0] if inboxes else DEFAULT_INBOXES[0]


DOCTORS_CATALOG = get_doctors_catalog()

DEFAULT_CLINIC_KNOWLEDGE = [
    {
        "id": 101,
        "category": "avanz_crm_erp",
        "title": "AvanzCRM (dev.avanz.ro) — Platformă Enterprise CRM & ERP",
        "content": (
            "AvanzCRM (dev.avanz.ro / avanz.ro) este o platformă software Enterprise CRM & ERP din România, "
            "adaptată pentru distribuție, agricultură, tehnic, zootehnie și servicii profesionale. "
            "Include: 1) Catalog și categorii personalizabile pe articole și coduri SKU; "
            "2) Trasee de teren și pontaj GPS pentru agenții de vânzări; "
            "3) Integrare automată e-Factura (SPV ANAF) și SmartBill; "
            "4) Aprobare de sarcini (workflows) și gestiune multi-tenant."
        ),
    },
    {
        "id": 102,
        "category": "avanz_demo_si_suport",
        "title": "Suport Tehnic dev.avanz.ro & Programare Demo Live AvanzCRM",
        "content": (
            "Echipa AvanzCRM oferă sesiuni gratuite de Demo Live, Onboarding Tehnic și suport pentru "
            "configurarea modulelor e-Factura ANAF, SmartBill, Trasee GPS și Nomenclatoare SKU pe dev.avanz.ro. "
            "Programările pentru Demo Live se fac de Luni până Vineri între orele 09:00 și 18:00 prin Cal.com."
        ),
    },
    {
        "id": 1,
        "category": "program_si_locatie",
        "title": "Program de lucru și Adresă Clinică Demo",
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
        "title": "Echipa de Specialiști / Consultanți",
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


def get_system_prompt(inbox_profile: dict[str, Any] | None = None) -> str:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
    profile = inbox_profile or resolve_inbox_profile()
    inbox_name = profile.get("name", settings.clinic_name)
    domain = profile.get("domain", "dev.avanz.ro")
    welcome_msg = profile.get("welcome_message", "")
    specificity = profile.get("site_specificity", "")

    doctors = get_doctors_catalog()
    doctors_summary = "; ".join(
        f"{d['name']} ({d['specialty']} - ore: {', '.join(d.get('default_slots', []))})"
        for d in doctors
    )

    return f"""Ești asistentul și consultantul virtual AI (24/7) pentru „{inbox_name}” (domeniu: {domain}), conectat la sistemul de programări Cal.com sincronizat cu Google Calendar.
Data și ora curentă: {now_str}.

SPECIFICUL ACESTUI INBOX / SITE ({inbox_name} — {domain}):
{specificity}

MESAJUL DE ÎNTÂMPINARE PERSONALIZAT AL ACESTUI INBOX:
„{welcome_msg}”

SPECIALIȘTI / CONSULTANȚI DISPONIBILI ÎN CALENDAR:
{doctors_summary}

REGULI DE COMUNICARE (FOARTE IMPORTANT PENTRU CHATWOOT, VOCE ȘI WHATSAPP):
1. Vorbești EXCLUSIV într-o limbă română naturală, caldă, politicoasă și profesionistă, adaptată 100% la specificul „{inbox_name}” ({domain}).
2. Răspunsurile tale trebuie să fie CONCISE și clare: maximum 2-4 propoziții scurte per răspuns, fără tabele Markdown greoaie.
3. Conform Articolului 50 din EU AI Act, la primul mesaj dintr-o conversație sau dacă ești întrebat, menționează scurt că ești asistentul virtual AI pentru {inbox_name}.
4. Când un utilizator/client vrea o programare (ex: Demo Live AvanzCRM, sesiune de suport tehnic sau consultație), reprogramare sau anulare:
   - Verifică ÎNTOTDEAUNA mai întâi disponibilitatea în Cal.com / Google Calendar folosind unealta `check_availability` pentru ziua dorită (format YYYY-MM-DD).
   - Propune utilizatorului 2 sau 3 ore libere concrete.
   - Înainte de a apela unealta `book_appointment`, asigură-te că ai aflat: Numele, Numărul de telefon (sau folosește „0700000000” dacă nu îl menționează în demo), Data și Ora exactă și subiectul (ex: Demo AvanzCRM, Configurare e-Factura, Consultație).
   - Dacă dorește să anuleze o programare existentă, folosește unealta `cancel_appointment`.
5. Dacă utilizatorul întreabă despre funcționalități (ex: Catalog SKU, Trasee GPS, e-Factura ANAF, SmartBill pe dev.avanz.ro), prețuri sau detalii specifice site-ului, folosește informațiile din SPECIFICUL ACESTUI INBOX și unealta `search_clinic_info`.
"""
