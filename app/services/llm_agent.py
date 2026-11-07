import json
import re
from datetime import datetime, timedelta
from typing import Any
import httpx
from app.config import settings, get_system_prompt
from app.services.cal_service import cal_service
from app.services.storage_service import storage_service


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Verifică intervalele orare libere din calendarul clinicii pentru o anumită dată.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Data dorită în format YYYY-MM-DD (ex: 2026-11-08).",
                    }
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Înregistrează o programare nouă în calendarul clinicii (Cal.com / Google Calendar).",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "Numele și prenumele pacientului.",
                    },
                    "phone": {
                        "type": "string",
                        "description": "Numărul de telefon al pacientului (sau 0700000000 dacă nu este specificat).",
                    },
                    "date": {
                        "type": "string",
                        "description": "Data programării în format YYYY-MM-DD.",
                    },
                    "time": {
                        "type": "string",
                        "description": "Ora programării în format HH:MM (ex: 16:30).",
                    },
                    "service": {
                        "type": "string",
                        "description": "Tipul serviciului (ex: Consultație, Detartraj, Urgență).",
                    },
                },
                "required": ["patient_name", "date", "time", "service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_clinic_info",
            "description": "Caută informații despre prețuri, tarife, medici, adresă, program sau plata în rate.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Cuvinte cheie despre ce întreabă pacientul (ex: pret detartraj, medici, adresa).",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


class ReceptionistAgent:
    """
    Agentul AI conversațional în limba română cu memorie pe sesiuni și suport complet de Tool Calling.
    Funcționează cu Groq Cloud Free Tier (Llama-3.3-70b) și include un motor inteligent
    de fallback local dacă utilizatorul nu a introdus încă cheia API!
    """

    GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self) -> None:
        self.sessions: dict[str, list[dict[str, Any]]] = {}

    def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        if session_id not in self.sessions:
            self.sessions[session_id] = [
                {"role": "system", "content": get_system_prompt()}
            ]
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
            return await cal_service.check_availability(date_str)

        if tool_name == "book_appointment":
            return await cal_service.book_appointment(
                patient_name=args.get("patient_name", "Pacient Demo"),
                phone=args.get("phone", "0700 000 000"),
                date_str=args.get("date")
                or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                time_str=args.get("time", "16:30"),
                service=args.get("service", "Consultație Stomatologică"),
                source=channel,
            )

        if tool_name == "search_clinic_info":
            docs = storage_service.search_knowledge(args.get("query", ""))
            return {"results": docs}

        return {"error": f"Unknown tool: {tool_name}"}

    async def _local_smart_fallback(
        self, user_message: str, channel: str
    ) -> tuple[str, list[str]]:
        """
        Motor local inteligent pentru situația în care utilizatorul testează aplicația
        înainte de a adăuga cheia GROQ_API_KEY în .env. Poate verifica orele, face programări reale
        și răspunde la întrebări despre prețuri!
        """
        msg_lower = user_message.lower()
        tools_used: list[str] = []
        tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        # 1. Dacă utilizatorul confirmă o programare sau dă numele și o oră
        time_match = re.search(r"\b(09:00|10:00|11:30|13:00|15:00|16:30|18:00)\b", msg_lower)
        if time_match and any(
            k in msg_lower
            for k in ["numele", "mă numesc", "ma numesc", "programează", "programeaza", "da", "vreau la", "popescu", "ionescu"]
        ):
            chosen_time = time_match.group(1)
            # Încercăm să extragem un nume
            name_match = re.search(
                r"(?:numele|numesc|sunt|pentru)\s+([a-zA-ZăâîșțĂÂÎȘȚ]+\s*[a-zA-ZăâîșțĂÂÎȘȚ]*)",
                user_message,
                re.IGNORECASE,
            )
            patient_name = (
                name_match.group(1).strip().title()
                if name_match
                else "Popescu Vlad (Demo)"
            )
            phone_match = re.search(r"(07\d{2}\s?\d{3}\s?\d{3})", user_message)
            phone = phone_match.group(1) if phone_match else "0722 999 888"

            tools_used.append("book_appointment")
            res = await cal_service.book_appointment(
                patient_name=patient_name,
                phone=phone,
                date_str=tomorrow_str,
                time_str=chosen_time,
                service="Consultație & Plan Tratament",
                source=channel,
            )
            if res.get("status") == "confirmed":
                booking = res["booking"]
                return (
                    f"Perfect! Am înregistrat programarea cu codul {booking['id']} pentru {booking['patient_name']}, "
                    f"mâine, {tomorrow_str}, la ora {chosen_time}. O puteți vedea deja în calendarul live din dreapta!",
                    tools_used,
                )
            else:
                return (res.get("message", "Ora este ocupată."), tools_used)

        # 2. Dacă întreabă de prețuri / tarife / detartraj / consultație
        if any(
            k in msg_lower
            for k in ["preț", "pret", "costă", "costa", "tarif", "detartraj", "albire", "implant", "rate"]
        ):
            tools_used.append("search_clinic_info")
            return (
                "La Clinica Demo Smile, o consultație primară costă 150 de lei, iar pachetul complet de igienizare "
                "cu detartraj și AirFlow este 350 de lei. Acceptăm și plata în până la 12 rate fără dobândă. "
                "Doriți să verificăm o oră liberă pentru mâine?",
                tools_used,
            )

        # 3. Dacă întreabă de programare / ore libere / mâine / durere
        if any(
            k in msg_lower
            for k in ["programare", "liber", "mâine", "maine", "azi", "loc", "doare", "măsea", "masea", "consult"]
        ):
            tools_used.append("check_availability")
            avail = await cal_service.check_availability(tomorrow_str)
            slots = avail.get("available_slots", [])
            slots_preview = ", ".join(slots[:4]) if slots else "16:30"
            return (
                f"Am verificat calendarul pentru mâine, {tomorrow_str}. Avem intervale libere la orele: {slots_preview}. "
                "Spuneți-mi, vă rog, ce oră vă avantajează și pe ce nume să fac programarea?",
                tools_used,
            )

        # Răspuns implicit de întâmpinare
        return (
            f"Bună ziua! Sunt asistentul virtual AI al {settings.clinic_name}. "
            "Vă pot ajuta pe loc cu o programare în calendar, verificarea orelor libere sau informații despre tarife și medici. "
            "Cu ce vă pot ajuta astăzi?",
            tools_used,
        )

    async def chat(
        self, session_id: str, user_message: str, channel: str = "Web Voice/Chat"
    ) -> dict[str, Any]:
        messages = self.get_session_messages(session_id)
        messages.append({"role": "user", "content": user_message})
        tools_used: list[str] = []

        if not settings.groq_api_key:
            reply, tools_used = await self._local_smart_fallback(user_message, channel)
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
                "appointments": cal_service.get_all_appointments(),
            }

        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                # Primul apel către LLM cu Tools activate
                payload = {
                    "model": settings.llm_model,
                    "messages": messages,
                    "tools": TOOLS_SCHEMA,
                    "tool_choice": "auto",
                    "temperature": 0.3,
                    "max_tokens": 350,
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

                    # Al doilea apel către LLM pentru formularea răspunsului final în română
                    second_payload = {
                        "model": settings.llm_model,
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": 350,
                    }
                    resp2 = await client.post(
                        self.GROQ_CHAT_URL, headers=headers, json=second_payload
                    )
                    resp2.raise_for_status()
                    final_reply = (
                        resp2.json()["choices"][0]["message"].get("content", "").strip()
                    )
                else:
                    final_reply = choice.get("content", "").strip()

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
                    "appointments": cal_service.get_all_appointments(),
                }
        except Exception:
            reply, fallback_tools = await self._local_smart_fallback(
                user_message, channel
            )
            tools_used.extend(fallback_tools)
            messages.append({"role": "assistant", "content": reply})
            return {
                "reply": reply,
                "tools_used": tools_used,
                "mode": "fallback_after_error",
                "appointments": cal_service.get_all_appointments(),
            }


receptionist_agent = ReceptionistAgent()
