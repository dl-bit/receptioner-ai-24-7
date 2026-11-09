import re
from typing import Any
import httpx
from app.config import (
    settings,
    get_inboxes_catalog,
    save_inboxes_catalog,
    resolve_inbox_profile,
    build_auto_inbox_template,
)
from app.services.llm_agent import receptionist_agent


class ChatwootCEService:
    """
    Conector avansat Multi-Inbox pentru Chatwoot Community Edition / Cloud:
      - Detectează automat Inbox-ul (după inbox.id, inbox.name sau URL-ul paginii referer ex: dev.avanz.ro)
      - Trimite automat mesajul de întâmpinare personalizat (welcome_message) la evenimentul 'conversation_created'
      - Răspunde la 'message_created' folosind promptul și baza de cunoștințe specifice acelui Inbox
      - Human Handoff personalizat pe fiecare Inbox ('handoff_message')
      - Sincronizează lista de Inbox-uri din Chatwoot (/api/v1/accounts/{id}/inboxes) și actualizează
        mesajul de întâmpinare nativ (greeting_message) direct în Chatwoot!
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
        "consultant uman",
        "inginer",
    ]

    def __init__(self) -> None:
        self._greeted_conversations: set[str] = set()

    @property
    def base_url(self) -> str:
        return (settings.chatwoot_api_url or "http://localhost:3000").rstrip("/")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "api_access_token": settings.chatwoot_api_token,
            "Content-Type": "application/json",
        }

    def _extract_inbox_context(self, payload: dict[str, Any]) -> dict[str, str]:
        """Extrage inbox_id, inbox_name și referer_url din payload-ul Webhook-ului Chatwoot."""
        inbox_obj = payload.get("inbox") or {}
        conversation = payload.get("conversation") or {}

        inbox_id = str(
            inbox_obj.get("id")
            or conversation.get("inbox_id")
            or payload.get("inbox_id")
            or ""
        ).strip()
        inbox_name = str(inbox_obj.get("name") or "").strip()

        add_attrs = conversation.get("additional_attributes") or {}
        meta_sender = (conversation.get("meta") or {}).get("sender") or {}
        sender_attrs = meta_sender.get("additional_attributes") or {}
        custom_attrs = payload.get("custom_attributes") or conversation.get("custom_attributes") or {}

        referer_url = str(
            add_attrs.get("referer")
            or sender_attrs.get("referer")
            or custom_attrs.get("referer")
            or custom_attrs.get("site_url")
            or ""
        ).strip()

        return {
            "inbox_id": inbox_id,
            "inbox_name": inbox_name,
            "referer_url": referer_url,
        }

    async def process_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Procesează evenimentele trimise de Chatwoot ('conversation_created' și 'message_created').
        Adaptează automat mesajele și AI-ul în funcție de Inbox-ul din care provine conversația!
        """
        event = payload.get("event", "message_created")
        conversation = payload.get("conversation") or {}
        conversation_id = conversation.get("id") or payload.get("id") or 1
        account = payload.get("account") or {}
        account_id = account.get("id") or 1

        ctx = self._extract_inbox_context(payload)
        inbox_profile = resolve_inbox_profile(
            inbox_id=ctx["inbox_id"],
            inbox_name=ctx["inbox_name"],
            referer_url=ctx["referer_url"],
            auto_register_new=True,
        )

        # 1. Dacă s-a deschis o conversație nouă în Chatwoot (conversation_created),
        # trimitem automat mesajul de întâmpinare personalizat pentru acel Inbox!
        if event == "conversation_created":
            conv_key = f"{account_id}:{conversation_id}"
            welcome_msg = inbox_profile.get("welcome_message", "").strip()
            if welcome_msg and conv_key not in self._greeted_conversations:
                self._greeted_conversations.add(conv_key)
                await self.send_message(
                    account_id=account_id,
                    conversation_id=conversation_id,
                    content=welcome_msg,
                    private=False,
                )
            return {
                "status": "welcome_sent",
                "inbox": inbox_profile.get("name"),
                "domain": inbox_profile.get("domain"),
                "welcome_message": welcome_msg,
            }

        if event and event != "message_created":
            return {"status": "ignored_event", "event": event}

        message_type = payload.get("message_type")
        private = payload.get("private", False)
        sender = payload.get("sender") or {}
        sender_type = sender.get("type", "contact")

        # Ignorăm mesajele outgoing (trimise de bot/agent) sau notele private (protecție Anti-Loop)
        if message_type != "incoming" or private or sender_type in ("user", "agent_bot"):
            return {"status": "ignored_non_incoming"}

        content = (payload.get("content") or "").strip()
        if not content:
            return {"status": "ignored_empty"}

        # 2. Verificăm dacă utilizatorul cere transfer către un operator uman în Chatwoot
        if any(k in content.lower() for k in self.HUMAN_HANDOFF_KEYWORDS):
            handoff_reply = inbox_profile.get("handoff_message") or (
                f"Am înțeles! Vă transfer imediat către un specialist din echipa {inbox_profile.get('name', 'noastră')}. "
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
                content=(
                    f"🔔 [AI Handoff — {inbox_profile.get('name')} ({inbox_profile.get('domain')})] "
                    f"Utilizatorul a solicitat preluarea de către un operator uman. Mesaj: „{content}”"
                ),
                private=True,
            )
            await self.toggle_conversation_status(
                account_id=account_id,
                conversation_id=conversation_id,
                status="open",
            )
            return {
                "status": "handoff_to_human",
                "inbox": inbox_profile.get("name"),
                "reply": handoff_reply,
            }

        # 3. Apelăm Agentul AI cu profilul personalizat al acestui Inbox (ex: dev.avanz.ro)
        channel_label = f"Chatwoot ({inbox_profile.get('name', 'Inbox')})"
        ai_res = await receptionist_agent.chat(
            session_id=f"cw-{inbox_profile.get('id', 'default')}-{conversation_id}",
            user_message=content,
            channel=channel_label,
            inbox_profile=inbox_profile,
        )

        # Trimitem răspunsul înapoi în conversația Chatwoot
        if settings.chatwoot_api_url and settings.chatwoot_api_token:
            await self.send_message(
                account_id=account_id,
                conversation_id=conversation_id,
                content=ai_res["reply"],
                private=False,
            )

        return {
            "status": "replied",
            "inbox": inbox_profile.get("name"),
            "domain": inbox_profile.get("domain"),
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
        """Trimite un mesaj (public sau notă internă privată) în Chatwoot."""
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
        """Schimbă statusul conversației în Chatwoot ('open', 'resolved', 'pending')."""
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

    async def push_inbox_greeting_to_chatwoot(
        self, inbox_id: str | int, welcome_message: str, account_id: int = 1
    ) -> bool:
        """
        Actualizează mesajul de întâmpinare nativ (greeting_message & greeting_enabled)
        direct în setările Inbox-ului din Chatwoot prin API!
        """
        if not (settings.chatwoot_api_url and settings.chatwoot_api_token and str(inbox_id).isdigit()):
            return False
        url = f"{self.base_url}/api/v1/accounts/{account_id}/inboxes/{inbox_id}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.patch(
                    url,
                    headers=self.headers,
                    json={
                        "greeting_enabled": True,
                        "greeting_message": welcome_message,
                    },
                )
                return resp.status_code in (200, 201)
        except Exception:
            return False

    async def save_or_update_inbox_profile(
        self,
        name: str,
        domain: str,
        welcome_message: str,
        handoff_message: str,
        site_specificity: str,
        inbox_id: str = "",
        profile_id: str = "",
        is_default: bool = False,
        quick_prompts: list[str] | None = None,
    ) -> dict[str, Any]:
        """Salvează sau actualizează un profil de Inbox în inboxes.json și sincronizează cu Chatwoot."""
        inboxes = get_inboxes_catalog()
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "custom"
        target_id = profile_id.strip() or f"inbox-{slug[:28]}"

        if is_default:
            for item in inboxes:
                item["is_default"] = False

        auto_tpl = build_auto_inbox_template(
            name=name,
            domain=domain,
            site_specificity=site_specificity,
            inbox_id=inbox_id,
        )

        record = {
            "id": target_id,
            "inbox_id": str(inbox_id).strip(),
            "name": name.strip(),
            "domain": domain.strip() or "dev.avanz.ro",
            "channel_type": "Channel::WebWidget",
            "is_default": is_default,
            "welcome_message": welcome_message.strip() or auto_tpl["welcome_message"],
            "handoff_message": handoff_message.strip() or auto_tpl["handoff_message"],
            "site_specificity": site_specificity.strip() or auto_tpl["site_specificity"],
            "quick_prompts": quick_prompts if quick_prompts else auto_tpl["quick_prompts"],
        }

        updated = False
        for idx, existing in enumerate(inboxes):
            if existing.get("id") == target_id or (
                record["inbox_id"] and str(existing.get("inbox_id")) == record["inbox_id"]
            ):
                if not is_default and existing.get("is_default"):
                    record["is_default"] = True
                inboxes[idx] = record
                updated = True
                break

        if not updated:
            inboxes.append(record)

        save_inboxes_catalog(inboxes)
        receptionist_agent.sessions.clear()

        cw_pushed = await self.push_inbox_greeting_to_chatwoot(
            inbox_id=record["inbox_id"],
            welcome_message=record["welcome_message"],
        )
        return {
            "status": "saved",
            "profile": record,
            "chatwoot_greeting_updated": cw_pushed,
            "inboxes": inboxes,
        }

    def delete_inbox_profile(self, profile_id: str) -> list[dict[str, Any]]:
        inboxes = [i for i in get_inboxes_catalog() if i.get("id") != profile_id]
        if not inboxes:
            inboxes = get_inboxes_catalog()[:1]
        save_inboxes_catalog(inboxes)
        receptionist_agent.sessions.clear()
        return inboxes

    async def sync_inboxes_from_chatwoot(self, account_id: int = 1) -> dict[str, Any]:
        """
        Interoghează Chatwoot API (/api/v1/accounts/{id}/inboxes), importă automat
        orice Inbox nou în inboxes.json cu mesaje personalizate pe specificul site-ului
        și sincronizează greeting_message în Chatwoot!
        """
        inboxes = get_inboxes_catalog()
        if not (settings.chatwoot_api_url and settings.chatwoot_api_token):
            return {
                "synced": False,
                "message": "Setează CHATWOOT_API_URL și CHATWOOT_API_TOKEN în Configurare Canale pentru sincronizare live cu serverul Chatwoot.",
                "inboxes": inboxes,
            }

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                r_prof = await client.get(f"{self.base_url}/api/v1/profile", headers=self.headers)
                if r_prof.status_code == 200:
                    account_id = r_prof.json().get("account_id") or account_id

                r_inb = await client.get(
                    f"{self.base_url}/api/v1/accounts/{account_id}/inboxes",
                    headers=self.headers,
                )
                if r_inb.status_code != 200:
                    return {
                        "synced": False,
                        "message": f"Chatwoot a returnat codul {r_inb.status_code} la citirea Inbox-urilor.",
                        "inboxes": inboxes,
                    }

                payload = r_inb.json()
                cw_inboxes = payload.get("payload", payload) if isinstance(payload, dict) else payload
                if not isinstance(cw_inboxes, list):
                    cw_inboxes = []

                added_count = 0
                updated_greetings = 0
                for cw in cw_inboxes:
                    cw_id = str(cw.get("id", "")).strip()
                    cw_name = (cw.get("name") or f"Inbox #{cw_id}").strip()
                    cw_domain = (cw.get("website_url") or cw.get(" forwarding_email") or "").strip()
                    cw_domain = re.sub(r"^https?://", "", cw_domain).rstrip("/") or "dev.avanz.ro"
                    cw_channel = cw.get("channel_type", "Channel::WebWidget")

                    existing = next(
                        (
                            item
                            for item in inboxes
                            if str(item.get("inbox_id", "")).strip() == cw_id
                            or item.get("name", "").lower() == cw_name.lower()
                        ),
                        None,
                    )
                    if existing:
                        existing["inbox_id"] = cw_id
                        existing["channel_type"] = cw_channel
                        if not existing.get("domain"):
                            existing["domain"] = cw_domain
                        pushed = await self.push_inbox_greeting_to_chatwoot(
                            inbox_id=cw_id,
                            welcome_message=existing.get("welcome_message", ""),
                            account_id=account_id,
                        )
                        if pushed:
                            updated_greetings += 1
                    else:
                        new_prof = build_auto_inbox_template(
                            name=cw_name,
                            domain=cw_domain,
                            inbox_id=cw_id,
                            channel_type=cw_channel,
                        )
                        if cw.get("greeting_message"):
                            new_prof["welcome_message"] = cw["greeting_message"]
                        inboxes.append(new_prof)
                        added_count += 1
                        pushed = await self.push_inbox_greeting_to_chatwoot(
                            inbox_id=cw_id,
                            welcome_message=new_prof["welcome_message"],
                            account_id=account_id,
                        )
                        if pushed:
                            updated_greetings += 1

                save_inboxes_catalog(inboxes)
                receptionist_agent.sessions.clear()
                return {
                    "synced": True,
                    "discovered_count": len(cw_inboxes),
                    "added_count": added_count,
                    "updated_greetings": updated_greetings,
                    "inboxes": inboxes,
                    "message": (
                        f"Sincronizare reușită! Am găsit {len(cw_inboxes)} Inbox-uri în Chatwoot "
                        f"({added_count} noi adăugate, {updated_greetings} mesaje de întâmpinare actualizate)."
                    ),
                }
        except Exception as exc:
            return {
                "synced": False,
                "message": f"Eroare la conectarea cu Chatwoot: {exc}",
                "inboxes": inboxes,
            }

    async def verify_and_register_webhook(
        self,
        api_url: str,
        api_token: str,
        webhook_target_url: str = "",
        account_id: int = 1,
    ) -> dict[str, Any]:
        """
        Verifică conexiunea cu instanța Chatwoot (prin /api/v1/profile), înregistrează
        automat webhook-ul (cu subscripțiile 'message_created' și 'conversation_created')
        și sincronizează Inbox-urile!
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
                        "message": f"Chatwoot a returnat codul {r_prof.status_code}. Verifică URL-ul și Access Token-ul.",
                    }

                if webhook_target_url.strip():
                    target_wh = f"{webhook_target_url.strip().rstrip('/')}/api/webhooks/chatwoot"
                    r_wh = await client.post(
                        f"{clean_url}/api/v1/accounts/{account_id}/webhooks",
                        headers=headers,
                        json={
                            "webhook": {
                                "url": target_wh,
                                "subscriptions": [
                                    "message_created",
                                    "conversation_created",
                                ],
                            }
                        },
                    )
                    webhook_registered = r_wh.status_code in (200, 201)
        except Exception as exc:
            return {
                "connected": False,
                "message": f"Nu am putut contacta instanța Chatwoot la {clean_url}: {exc}",
            }

        sync_res = await self.sync_inboxes_from_chatwoot(account_id=account_id)
        return {
            "connected": True,
            "profile": profile_info,
            "webhook_registered": webhook_registered,
            "inboxes_sync": sync_res,
            "message": "Conectat cu succes la Chatwoot și sincronizat Inbox-urile!",
        }


chatwoot_service = ChatwootCEService()
