import json
import re
from datetime import datetime, timedelta
from typing import Any
import httpx
from app.config import (
    settings,
    get_system_prompt,
    resolve_inbox_profile,
    build_auto_inbox_template,
)
from app.services.cal_service import cal_service
from app.services.storage_service import storage_service


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": (
                "Verifică intervalele orare libere în sistemul Cal.com "
                "(sincronizat cu Google Calendar) pentru o anumită dată și opțional un consultant/medic sau serviciu."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Data dorită în format YYYY-MM-DD (ex: 2026-11-10).",
                    },
                    "doctor": {
                        "type": "string",
                        "description": "Opțional: Numele specialistului/medicului.",
                    },
                    "service": {
                        "type": "string",
                        "description": "Opțional: Serviciul dorit (ex: Demo Live AvanzCRM, Consultanță ERP, Consultație, Detartraj).",
                    },
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Înregistrează o programare nouă (Demo Live AvanzCRM, Sesiune Suport sau Consultație) în Cal.com + Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "Numele și prenumele clientului/pacientului.",
                    },
                    "phone": {
                        "type": "string",
                        "description": "Numărul de telefon (sau 0700000000 dacă nu este specificat).",
                    },
                    "date": {
                        "type": "string",
                        "description": "Data programării în format YYYY-MM-DD.",
                    },
                    "time": {
                        "type": "string",
                        "description": "Ora programării în format HH:MM (ex: 15:00, 16:30).",
                    },
                    "service": {
                        "type": "string",
                        "description": "Tipul programării (ex: Demo Live AvanzCRM, Onboarding e-Factura, Consultație).",
                    },
                    "doctor": {
                        "type": "string",
                        "description": "Opțional: Numele specialistului/medicului preferat.",
                    },
                },
                "required": ["patient_name", "date", "time", "service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Anulează o programare existentă din Cal.com / Google Calendar după codul programării sau nume.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id_or_name": {
                        "type": "string",
                        "description": "Codul programării (ex: BK-1001, CAL-123) sau numele persoanei.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Motivul anulării.",
                    },
                },
                "required": ["booking_id_or_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_clinic_info",
            "description": "Caută informații despre specificul site-ului/inbox-ului (ex: modulele AvanzCRM pe dev.avanz.ro, e-Factura, GPS, SKU, tarife, program).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Cuvinte cheie despre ce întreabă utilizatorul (ex: avanz, e-factura, gps, sku, pret detartraj, program).",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


class ReceptionistAgent:
    """
    Agentul AI conversațional în limba română cu memorie pe sesiuni, suport Multi-Inbox Chatwoot
    (personalizat pentru dev.avanz.ro și orice inbox nou) și Tool Calling conectat la Cal.com + Google Calendar.
    """

    GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self) -> None:
        self.sessions: dict[str, list[dict[str, Any]]] = {}

    def get_session_messages(
        self, session_id: str, inbox_profile: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        sys_prompt = get_system_prompt(inbox_profile)
        if session_id not in self.sessions:
            self.sessions[session_id] = [{"role": "system", "content": sys_prompt}]
        else:
            # Actualizăm promptul de sistem dacă profilul inbox-ului s-a schimbat
            self.sessions[session_id][0] = {"role": "system", "content": sys_prompt}
        return self.sessions[session_id]

    def reset_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)

    async def execute_tool(
        self, tool_name: str, args: dict[str, Any], channel: str
    ) -> dict[str, Any]:
        if tool_name == "check_availability":
            date_str = args.get("date") or (datetime.now() + timedelta(days=1)).strftime(
                "%Y-%m-%d"
            )
            return await cal_service.check_availability(
                date_str=date_str,
                doctor=args.get("doctor"),
                service=args.get("service"),
            )

        if tool_name == "book_appointment":
            return await cal_service.book_appointment(
                patient_name=args.get("patient_name", "Client Demo"),
                phone=args.get("phone", "0700 000 000"),
                date_str=args.get("date")
                or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                time_str=args.get("time", "16:30"),
                service=args.get("service", "Demo Live / Consultanță"),
                doctor=args.get("doctor"),
                source=channel,
            )

        if tool_name == "cancel_appointment":
            return await cal_service.cancel_appointment(
                booking_id_or_name=args.get("booking_id_or_name", ""),
                reason=args.get("reason", "Anulat prin Asistentul AI"),
            )

        if tool_name == "search_clinic_info":
            docs = storage_service.search_knowledge(args.get("query", ""))
            return {"results": docs}

        return {"error": f"Unknown tool: {tool_name}"}

    async def _local_smart_fallback(
        self,
        user_message: str,
        channel: str,
        inbox_profile: dict[str, Any] | None = None,
    ) -> tuple[str, list[str]]:
        """
        Motor local inteligent de siguranță adaptat atât pentru specificul fiecărui Inbox
        (inclusiv dev.avanz.ro — AvanzCRM), cât și pentru programări în Cal.com.
        """
        profile = inbox_profile or resolve_inbox_profile()
        inbox_name = profile.get("name", settings.clinic_name)
        domain = (profile.get("domain") or "dev.avanz.ro").lower()
        specificity = profile.get("site_specificity", "")
        welcome_msg = profile.get("welcome_message", "")

        msg_lower = user_message.lower()
        tools_used: list[str] = []
        tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        # 0. Dacă utilizatorul dorește anularea unei programări
        if any(k in msg_lower for k in ["anuleaz", "anulare", "renunț", "renunt"]):
            code_match = re.search(r"\b((?:BK|CAL)-\d+)\b", user_message, re.IGNORECASE)
            target = code_match.group(1) if code_match else "Popescu"
            tools_used.append("cancel_appointment")
            res = await cal_service.cancel_appointment(target)
            return (res.get("message", "Am verificat cererea de anulare."), tools_used)

        # 1. Dacă utilizatorul confirmă o programare sau dă numele și o oră
        time_match = re.search(
            r"\b(09:00|10:00|10:30|11:30|12:00|13:00|14:00|15:00|16:30|18:00)\b",
            msg_lower,
        )
        if time_match and any(
            k in msg_lower
            for k in [
                "numele",
                "mă numesc",
                "ma numesc",
                "programează",
                "programeaza",
                "programez",
                "demo",
                "da",
                "vreau la",
                "popescu",
                "ionescu",
            ]
        ):
            chosen_time = time_match.group(1)
            name_match = re.search(
                r"(?:numele|numesc|sunt|pentru)\s+([a-zA-ZăâîșțĂÂÎȘȚ]+\s*[a-zA-ZăâîșțĂÂÎȘȚ]*)",
                user_message,
                re.IGNORECASE,
            )
            patient_name = (
                name_match.group(1).strip().title() if name_match else "Popescu Vlad"
            )
            phone_match = re.search(r"(07\d{2}\s?\d{3}\s?\d{3})", user_message)
            phone = phone_match.group(1) if phone_match else "0722 999 888"

            default_srv = (
                "Demo Live AvanzCRM (dev.avanz.ro)"
                if "avanz" in domain or "avanz" in inbox_name.lower()
                else "Consultație & Plan Tratament"
            )
            tools_used.append("book_appointment")
            res = await cal_service.book_appointment(
                patient_name=patient_name,
                phone=phone,
                date_str=tomorrow_str,
                time_str=chosen_time,
                service=default_srv,
                source=channel,
            )
            if res.get("status") == "confirmed":
                booking = res["booking"]
                return (
                    f"Perfect! Am înregistrat programarea cu codul {booking['id']} pentru {booking['patient_name']}, "
                    f"mâine, {tomorrow_str}, la ora {chosen_time} ({booking['service']}). "
                    "Programarea a fost sincronizată în calendar!",
                    tools_used,
                )
            else:
                return (res.get("message", "Ora este ocupată."), tools_used)

        # 2. Întrebări specifice AvanzCRM / dev.avanz.ro (CRM, ERP, e-Factura, SmartBill, GPS, SKU)
        if any(
            k in msg_lower
            for k in [
                "avanz",
                "crm",
                "erp",
                "efactura",
                "e-factura",
                "smartbill",
                "gps",
                "trasee",
                "pontaj",
                "sku",
                "catalog",
                "multi-tenant",
                "sarcini",
                "modul",
            ]
        ):
            tools_used.append("search_clinic_info")
            return (
                f"Pe platforma {inbox_name} ({domain}), aveți acces la modulele Enterprise CRM & ERP: "
                "catalog personalizabil pe articole și coduri SKU, trasee de teren și pontaj GPS pentru agenții de vânzări, "
                "sincronizare automată e-Factura (SPV ANAF) & SmartBill, plus aprobare de sarcini multi-tenant. "
                "Doriți să programăm o sesiune Demo Live sau de suport tehnic în Cal.com?",
                tools_used,
            )

        # 3. Dacă întreabă de prețuri / tarife / detartraj / consultație
        if any(
            k in msg_lower
            for k in ["preț", "pret", "costă", "costa", "tarif", "detartraj", "albire", "implant", "rate"]
        ):
            tools_used.append("search_clinic_info")
            if "avanz" in domain and not any(w in msg_lower for w in ["detartraj", "albire", "implant"]):
                return (
                    f"Pentru platforma {inbox_name} ({domain}), pachetele de licențiere Enterprise CRM & ERP "
                    "se personalizează în funcție de numărul de utilizatori/agenți și modulele activate (Catalog SKU, GPS, e-Factura, SmartBill). "
                    "Vă putem oferi o cotație exactă în cadrul unui Demo Live gratuit!",
                    tools_used,
                )
            return (
                "La Clinica Demo Smile, o consultație primară costă 150 de lei, iar pachetul complet de igienizare "
                "cu detartraj și AirFlow este 350 de lei. Acceptăm și plata în până la 12 rate fără dobândă. "
                "Doriți să verificăm în Cal.com o oră liberă pentru mâine?",
                tools_used,
            )

        # 4. Dacă întreabă de programare / ore libere / mâine / demo
        if any(
            k in msg_lower
            for k in [
                "programare",
                "liber",
                "mâine",
                "maine",
                "azi",
                "loc",
                "doare",
                "măsea",
                "masea",
                "consult",
                "medic",
                "demo",
            ]
        ):
            tools_used.append("check_availability")
            avail = await cal_service.check_availability(tomorrow_str)
            slots = avail.get("available_slots", [])
            slots_preview = ", ".join(slots[:4]) if slots else "16:30"
            return (
                f"Am verificat calendarul pentru mâine, {tomorrow_str} ({inbox_name}). "
                f"Avem intervale libere la orele: {slots_preview}. "
                "Spuneți-mi, vă rog, ce oră vă avantajează și pe ce nume să înregistrez programarea?",
                tools_used,
            )

        # 5. Răspuns personalizat pe specificul Inbox-ului curent
        if welcome_msg:
            return (
                f"{welcome_msg} ({specificity[:180]}...)"
                if len(welcome_msg) < 90 and specificity
                else welcome_msg,
                tools_used,
            )

        return (
            f"Bună ziua! Sunt asistentul virtual AI pentru {inbox_name} ({domain}). "
            "Vă pot ajuta cu informații specifice platformei noastre sau cu programarea unei sesiuni în Cal.com. Cu ce vă pot ajuta astăzi?",
            tools_used,
        )

    async def chat(
        self,
        session_id: str,
        user_message: str,
        channel: str = "Web Voice/Chat",
        inbox_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        active_profile = inbox_profile or resolve_inbox_profile()
        messages = self.get_session_messages(session_id, active_profile)
        messages.append({"role": "user", "content": user_message})
        tools_used: list[str] = []

        if not settings.groq_api_key:
            reply, tools_used = await self._local_smart_fallback(
                user_message, channel, active_profile
            )
            messages.append({"role": "assistant", "content": reply})
            await storage_service.log_interaction(
                session_id=session_id,
                channel=channel,
                user_message=user_message,
                assistant_reply=reply,
                tools_used=tools_used,
            )
            return {
                "reply": reply,
                "tools_used": tools_used,
                "mode": "demo_smart_fallback",
                "inbox_profile": active_profile,
                "appointments": cal_service.get_all_appointments(),
            }

        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                payload = {
                    "model": settings.llm_model,
                    "messages": messages,
                    "tools": TOOLS_SCHEMA,
                    "tool_choice": "auto",
                    "temperature": 0.3,
                    "max_tokens": 400,
                }
                resp = await client.post(self.GROQ_CHAT_URL, headers=headers, json=payload)
                resp.raise_for_status()
                choice = resp.json()["choices"][0]["message"]

                tool_calls = choice.get("tool_calls")
                if tool_calls:
                    messages.append(choice)
                    for tc in tool_calls:
                        fn_name = tc["function"]["name"]
                        raw_args = tc["function"].get("arguments", "{}")
                        try:
                            parsed_args = json.loads(raw_args)
                        except Exception:
                            parsed_args = {}

                        tools_used.append(fn_name)
                        tool_result = await self.execute_tool(fn_name, parsed_args, channel)

                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "name": fn_name,
                                "content": json.dumps(tool_result, ensure_ascii=False),
                            }
                        )

                    second_payload = {
                        "model": settings.llm_model,
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": 400,
                    }
                    resp2 = await client.post(
                        self.GROQ_CHAT_URL, headers=headers, json=second_payload
                    )
                    resp2.raise_for_status()
                    final_reply = (
                        resp2.json()["choices"][0]["message"].get("content", "").strip()
                    )
                else:
                    final_reply = (choice.get("content") or "").strip()

                if not final_reply:
                    final_reply, fallback_tools = await self._local_smart_fallback(
                        user_message, channel, active_profile
                    )
                    tools_used.extend(fallback_tools)

                messages.append({"role": "assistant", "content": final_reply})
                await storage_service.log_interaction(
                    session_id=session_id,
                    channel=channel,
                    user_message=user_message,
                    assistant_reply=final_reply,
                    tools_used=tools_used,
                )

                return {
                    "reply": final_reply,
                    "tools_used": tools_used,
                    "mode": "groq_live_llm",
                    "inbox_profile": active_profile,
                    "appointments": cal_service.get_all_appointments(),
                }
        except Exception:
            reply, fallback_tools = await self._local_smart_fallback(
                user_message, channel, active_profile
            )
            tools_used.extend(fallback_tools)
            messages.append({"role": "assistant", "content": reply})
            return {
                "reply": reply,
                "tools_used": tools_used,
                "mode": "fallback_after_error",
                "inbox_profile": active_profile,
                "appointments": cal_service.get_all_appointments(),
            }

    async def generate_inbox_profile_with_ai(
        self,
        name: str,
        domain: str = "",
        site_specificity: str = "",
        inbox_id: str = "",
    ) -> dict[str, Any]:
        """
        Generează mesaje personalizate (welcome_message, handoff_message, site_specificity, quick_prompts)
        pentru un Inbox nou în funcție de specificul site-ului, folosind Groq LLM (sau șablonul inteligent local).
        """
        base_template = build_auto_inbox_template(
            name=name,
            domain=domain,
            site_specificity=site_specificity,
            inbox_id=inbox_id,
        )
        if not settings.groq_api_key:
            return base_template

        prompt = f"""Generează un profil JSON pentru un Inbox nou în Chatwoot, în limba română, adaptat 100% la specificul site-ului de mai jos.
Nume Inbox / Proiect: {name}
Domeniu web: {domain or 'dev.avanz.ro'}
Descriere / Specificul site-ului: {site_specificity or base_template['site_specificity']}

Returnează EXCLUSIV un obiect JSON valid cu următoarele chei:
- "welcome_message": mesaj de bun venit cald, profesionist, de 2-3 propoziții, care menționează domeniul/brandul și cu ce poate ajuta asistentul AI.
- "handoff_message": mesaj politicos de 1-2 propoziții când clientul cere transferul către un consultant/operator uman.
- "site_specificity": instrucțiuni și detalii cheie despre specificul site-ului (3-5 propoziții) pentru promptul de sistem al AI-ului.
- "quick_prompts": o listă cu exact 3 întrebări relevante pe care un vizitator le-ar pune pe acest site.
"""
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    self.GROQ_CHAT_URL,
                    headers=headers,
                    json={
                        "model": settings.llm_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "Răspunzi exclusiv cu JSON valid, fără markdown ```json.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.4,
                        "max_tokens": 500,
                    },
                )
                resp.raise_for_status()
                raw = resp.json()["choices"][0]["message"].get("content", "").strip()
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and parsed.get("welcome_message"):
                    base_template["welcome_message"] = str(parsed["welcome_message"]).strip()
                if isinstance(parsed, dict) and parsed.get("handoff_message"):
                    base_template["handoff_message"] = str(parsed["handoff_message"]).strip()
                if isinstance(parsed, dict) and parsed.get("site_specificity"):
                    base_template["site_specificity"] = str(parsed["site_specificity"]).strip()
                if isinstance(parsed, dict) and isinstance(parsed.get("quick_prompts"), list):
                    base_template["quick_prompts"] = [
                        str(x) for x in parsed["quick_prompts"][:3] if str(x).strip()
                    ]
        except Exception:
            pass

        return base_template


receptionist_agent = ReceptionistAgent()
