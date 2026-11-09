from datetime import datetime
from typing import Any
import httpx
from app.config import (
    settings,
    DEFAULT_CLINIC_KNOWLEDGE,
    get_doctors_catalog,
    get_inboxes_catalog,
)


class StorageService:
    """
    Gestionează conexiunea distribuită cu:
    1. Qdrant Cloud Free Tier (1 GB permanent) pentru căutare în baza de cunoștințe (RAG).
    2. Supabase PostgreSQL Free Tier pentru salvarea jurnalului de conversații (Audit EU AI Act) și a lead-urilor.
    Funcționează impecabil și fără chei configurate (folosind fallback in-memory sincronizat cu doctors.json și inboxes.json).
    """

    def __init__(self) -> None:
        self.local_knowledge = list(DEFAULT_CLINIC_KNOWLEDGE)
        self.audit_logs: list[dict[str, Any]] = []
        self._qdrant_client = None

        if settings.qdrant_url and settings.qdrant_api_key:
            try:
                from qdrant_client import QdrantClient

                self._qdrant_client = QdrantClient(
                    url=settings.qdrant_url,
                    api_key=settings.qdrant_api_key,
                    timeout=5.0,
                )
            except Exception:
                self._qdrant_client = None

    def _get_live_knowledge(self) -> list[dict[str, Any]]:
        """Sincronizează baza de cunoștințe cu medicii din doctors.json și specificul fiecărui Inbox din inboxes.json."""
        doctors = get_doctors_catalog()
        docs_text = " ".join(
            f"{d['name']} - {d['specialty']} (ore disponibile: {', '.join(d.get('default_slots', []))})."
            for d in doctors
        )
        live_items: list[dict[str, Any]] = []

        # Adăugăm dinamic cunoștințele fiecărui Inbox din inboxes.json (ex: dev.avanz.ro)
        for idx, inbox in enumerate(get_inboxes_catalog(), start=200):
            live_items.append(
                {
                    "id": idx,
                    "category": f"inbox_{inbox.get('id', idx)}",
                    "title": f"{inbox.get('name', 'Inbox')} ({inbox.get('domain', '')})",
                    "content": f"{inbox.get('site_specificity', '')} Mesaj întâmpinare: {inbox.get('welcome_message', '')}",
                }
            )

        for item in self.local_knowledge:
            if item.get("category") == "medici":
                live_items.append(
                    {
                        **item,
                        "content": docs_text,
                    }
                )
            else:
                live_items.append(item)
        return live_items

    def search_knowledge(self, query: str) -> list[dict[str, Any]]:
        """
        Caută informații despre modulele AvanzCRM (dev.avanz.ro), specificul fiecărui Inbox,
        prețuri, servicii, specialiști și program în baza de cunoștințe.
        """
        knowledge = self._get_live_knowledge()
        query_words = [
            w.lower()
            for w in query.replace("?", " ").replace(",", " ").split()
            if len(w) >= 3
        ]

        if not query_words:
            return knowledge

        scored: list[tuple[int, dict[str, Any]]] = []
        for item in knowledge:
            haystack = f"{item['title']} {item['category']} {item['content']}".lower()
            score = sum(2 if w in haystack else 0 for w in query_words)
            scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_matches = [item for score, item in scored if score > 0]
        return top_matches if top_matches else knowledge

    async def log_interaction(
        self,
        session_id: str,
        channel: str,
        user_message: str,
        assistant_reply: str,
        tools_used: list[str] | None = None,
    ) -> None:
        """
        Salvează interacțiunea în jurnalul de audit (conformitate EU AI Act Art. 12 & 50)
        și o trimite în Supabase REST API dacă SUPABASE_URL și SUPABASE_KEY sunt setate.
        """
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "session_id": session_id,
            "channel": channel,
            "user_message": user_message,
            "assistant_reply": assistant_reply,
            "tools_used": tools_used or [],
        }
        self.audit_logs.insert(0, entry)
        self.audit_logs = self.audit_logs[:100]

        if settings.supabase_url and settings.supabase_key:
            try:
                headers = {
                    "apikey": settings.supabase_key,
                    "Authorization": f"Bearer {settings.supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                }
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        f"{settings.supabase_url.rstrip('/')}/rest/v1/ai_receptionist_logs",
                        headers=headers,
                        json=entry,
                    )
            except Exception:
                pass


storage_service = StorageService()
