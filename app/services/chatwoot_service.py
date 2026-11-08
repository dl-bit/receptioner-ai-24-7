from typing import Any
import httpx
from app.config import settings
from app.services.llm_agent import receptionist_agent


class ChatwootCEService:
    """
    Conector dedicat pentru Chatwoot Community Edition (Open-Source Docker — 100% Gratuit,
    fără restricții pe API Access Tokens sau Agent Bots).
    Funcționalități:
      - Preluare mesaje din Webhook-ul Chatwoot CE (message_created)
      - Trimitere răspunsuri AI în conversația Chatwoot CE
      - Human Handoff automat: dacă pacientul cere un operator uman, schimbă statusul
        conversației în 'open' și lasă o notă privată pentru recepție
      - Înregistrare automată a Webhook-ului în Chatwoot CE prin API
    """

    HUMAN_HANDOFF_KEYWORDS = [
        "operator",
        "om real",
        "persoană",
        "persoana",
        "recepționeră",
        "receptionera",
        "vorbesc cu cineva",
        "transfer",
    ]

    @property
    def base_url(self) -> str:
        return (settings.chatwoot_api_url or "http://localhost:3000").rstrip("/")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "api_access_token": settings.chatwoot_api_token,
            "Content-Type": "application/json",
        }

    async def process_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Procesează evenimentele trimise de Chatwoot Community Edition.
        Răspunde doar la mesajele 'incoming' trimise de pacient ('contact'),
        evitând buclele infinite.
        """
        event = payload.get("event", "message_created")
        if event and event != "message_created":
            return {"status": "ignored_event", "event": event}

        message_type = payload.get("message_type")
        private = payload.get("private", False)
        sender = payload.get("sender") or {}
        sender_type = sender.get("type", "contact")

        # Ignorăm mesajele outgoing (trimise de bot/agent) sau notele private
        if message_type != "incoming" or private or sender_type in ("user", "agent_bot"):
            return {"status": "ignored_non_incoming"}

        content = (payload.get("content") or "").strip()
        if not content:
            return {"status": "ignored_empty"}

        conversation = payload.get("conversation") or {}
        conversation_id = conversation.get("id") or payload.get("id") or 1
        account = payload.get("account") or {}
        account_id = account.get("id") or 1

        # Verificăm dacă pacientul cere transfer către un operator uman în Chatwoot
        if any(k in content.lower() for k in self.HUMAN_HANDOFF_KEYWORDS):
            handoff_reply = (
                "Am înțeles! Vă transfer imediat către un coleg de la recepția clinicii. "
                "Un operator uman va prelua această conversație în câteva momente."
            )
            await self.send_message(
                account_id=account_id,
                conversation_id=conversation_id,
                content=handoff_reply,
                private=False,
            )
            await self.send_message(
                account_id=account_id,
                conversation_id=conversation_id,
                content=f"🔔 [AI Handoff] Pacientul a solicitat preluarea de către un operator uman. Mesaj: „{content}”",
                private=True,
            )
            await self.toggle_conversation_status(
                account_id=account_id,
                conversation_id=conversation_id,
                status="open",
            )
            return {"status": "handoff_to_human", "reply": handoff_reply}

        # Apelăm Agentul AI (conectat la Cal.com & Google Calendar)
        ai_res = await receptionist_agent.chat(
            session_id=f"cw-{conversation_id}",
            user_message=content,
            channel="Chatwoot CE (Open-Source)",
        )

        # Trimitem răspunsul înapoi în conversația Chatwoot CE
        if settings.chatwoot_api_url and settings.chatwoot_api_token:
            await self.send_message(
                account_id=account_id,
                conversation_id=conversation_id,
                content=ai_res["reply"],
                private=False,
            )

        return {
            "status": "replied",
            "reply": ai_res["reply"],
            "tools_used": ai_res.get("tools_used", []),
        }

    async def send_message(
        self,
        account_id: int | str,
        conversation_id: int | str,
        content: str,
        private: bool = False,
    ) -> dict[str, Any]:
        """Trimite un mesaj (public sau notă internă privată) în Chatwoot CE."""
        if not (settings.chatwoot_api_url and settings.chatwoot_api_token):
            return {"sent": False, "reason": "missing_credentials"}

        url = (
            f"{self.base_url}/api/v1/accounts/{account_id}/"
            f"conversations/{conversation_id}/messages"
        )
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    headers=self.headers,
                    json={
                        "content": content,
                        "message_type": "outgoing",
                        "private": private,
                    },
                )
                return {"sent": resp.status_code in (200, 201), "status_code": resp.status_code}
        except Exception as exc:
            return {"sent": False, "error": str(exc)}

    async def toggle_conversation_status(
        self,
        account_id: int | str,
        conversation_id: int | str,
        status: str = "open",
    ) -> None:
        """Schimbă statusul conversației în Chatwoot CE ('open', 'resolved', 'pending')."""
        if not (settings.chatwoot_api_url and settings.chatwoot_api_token):
            return
        url = (
            f"{self.base_url}/api/v1/accounts/{account_id}/"
            f"conversations/{conversation_id}/toggle_status"
        )
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                await client.post(url, headers=self.headers, json={"status": status})
        except Exception:
            pass

    async def verify_and_register_webhook(
        self,
        api_url: str,
        api_token: str,
        webhook_target_url: str = "",
        account_id: int = 1,
    ) -> dict[str, Any]:
        """
        Verifică conexiunea cu instanța Chatwoot CE (prin /api/v1/profile) și, dacă
        este furnizat webhook_target_url, înregistrează automat webhook-ul în Chatwoot CE!
        """
        clean_url = api_url.strip().rstrip("/")
        headers = {
            "api_access_token": api_token.strip(),
            "Content-Type": "application/json",
        }
        profile_info: dict[str, Any] = {}
        webhook_registered = False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r_prof = await client.get(f"{clean_url}/api/v1/profile", headers=headers)
                if r_prof.status_code == 200:
                    prof_data = r_prof.json()
                    profile_info = {
                        "name": prof_data.get("name") or prof_data.get("available_name", "Admin"),
                        "email": prof_data.get("email", ""),
                        "account_id": prof_data.get("account_id", account_id),
                    }
                    account_id = profile_info["account_id"] or account_id
                else:
                    return {
                        "connected": False,
                        "status_code": r_prof.status_code,
                        "message": f"Chatwoot CE a returnat codul {r_prof.status_code}. Verifică URL-ul și Access Token-ul.",
                    }

                if webhook_target_url.strip():
                    target_wh = f"{webhook_target_url.strip().rstrip('/')}/api/webhooks/chatwoot"
                    r_wh = await client.post(
                        f"{clean_url}/api/v1/accounts/{account_id}/webhooks",
                        headers=headers,
                        json={
                            "webhook": {
                                "url": target_wh,
                                "subscriptions": ["message_created"],
                            }
                        },
                    )
                    webhook_registered = r_wh.status_code in (200, 201)
        except Exception as exc:
            return {
                "connected": False,
                "message": f"Nu am putut contacta instanța Chatwoot CE la {clean_url}: {exc}",
            }

        return {
            "connected": True,
            "profile": profile_info,
            "webhook_registered": webhook_registered,
            "message": "Conectat cu succes la Chatwoot Community Edition (Docker)!",
        }


chatwoot_service = ChatwootCEService()
