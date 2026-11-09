import sys
from fastapi.testclient import TestClient
from app.main import app

sys.stdout.reconfigure(encoding="utf-8")


def run_smoke_tests() -> None:
    client = TestClient(app)

    # 1. Test Healthcheck (pentru UptimeRobot / cron-job.org) + Multi-Inbox
    r_health = client.get("/api/health")
    assert r_health.status_code == 200, f"Health failed: {r_health.text}"
    health_data = r_health.json()
    print(
        "[OK] /api/health:",
        health_data["status"],
        "| Active Inbox:",
        health_data["clinic_name"],
        "| Total Inboxes:",
        len(health_data.get("inboxes", [])),
    )

    # 2. Test Status Cal.com + Medici Catalog (/api/doctors) + Chatwoot Inboxes (/api/chatwoot/inboxes)
    r_cal = client.get("/api/calcom/status")
    assert r_cal.status_code == 200, f"Cal.com status failed: {r_cal.text}"
    r_docs = client.get("/api/doctors")
    assert r_docs.status_code == 200, f"Doctors list failed: {r_docs.text}"
    r_inb = client.get("/api/chatwoot/inboxes")
    assert r_inb.status_code == 200, f"Chatwoot inboxes list failed: {r_inb.text}"
    print(
        "[OK] /api/calcom/status, /api/doctors & /api/chatwoot/inboxes | Inboxes:",
        len(r_inb.json().get("inboxes", [])),
    )

    # 3. Test Generator Automat de Mesaje Personalizate pt. Inbox Nou (dev.avanz.ro)
    r_gen = client.post(
        "/api/chatwoot/inboxes/generate",
        json={
            "name": "AvanzCRM — Modul B2B & e-Factura (dev.avanz.ro)",
            "domain": "dev.avanz.ro",
            "site_specificity": "Sincronizare automată e-Factura ANAF SPV, SmartBill, pontaj GPS agenți și catalog SKU.",
        },
    )
    assert r_gen.status_code == 200, f"Inbox generate failed: {r_gen.text}"
    tpl = r_gen.json()["template"]
    print("[OK] /api/chatwoot/inboxes/generate (dev.avanz.ro):", tpl["welcome_message"][:90] + "...")

    # 4. Test Chat pe Inbox-ul dev.avanz.ro + Edge-TTS Română
    r_chat1 = client.post(
        "/api/chat",
        json={
            "session_id": "test-avanz-1",
            "inbox_profile_id": "inbox-avanz-main",
            "message": "Ce module include platforma AvanzCRM pe dev.avanz.ro?",
            "voice": "ro-RO-AlinaNeural",
            "generate_audio": True,
        },
    )
    assert r_chat1.status_code == 200, f"Chat 1 failed: {r_chat1.text}"
    d1 = r_chat1.json()
    print("[OK] /api/chat (dev.avanz.ro):", d1["reply"])
    print("     Tools used:", d1["tools_used"])
    print(
        "     Audio MP3 Base64 generated:",
        bool(d1.get("audio_base64")),
        f"({len(d1.get('audio_base64') or '')} chars)",
    )

    # 5. Test Programare Demo Live prin Chat (Cal.com + Google Calendar link)
    r_chat2 = client.post(
        "/api/chat",
        json={
            "session_id": "test-avanz-1",
            "inbox_profile_id": "inbox-avanz-main",
            "message": "Vreau să mă programez mâine la ora 16:30 pentru un Demo Live pe numele Popescu Vlad, telefon 0722999888",
            "voice": "ro-RO-EmilNeural",
            "generate_audio": True,
        },
    )
    assert r_chat2.status_code == 200, f"Chat 2 failed: {r_chat2.text}"
    d2 = r_chat2.json()
    print("[OK] /api/chat (booking):", d2["reply"])
    print("     Tools used:", d2["tools_used"])
    print("     Total appointments now:", len(d2["appointments"]))

    # 6. Test Cal.com Webhook Receiver (BOOKING_CREATED din Google Calendar / Cal.com)
    r_wh = client.post(
        "/api/webhooks/calcom",
        json={
            "triggerEvent": "BOOKING_CREATED",
            "payload": {
                "bookingId": 9901,
                "title": "Demo Live AvanzCRM",
                "startTime": f"{health_data['tomorrow_date']}T14:00:00Z",
                "attendees": [{"name": "Ionescu Maria", "email": "maria@avanz.ro"}],
                "metadata": {"phone": "0733 123 456"},
            },
        },
    )
    assert r_wh.status_code == 200, f"Cal.com webhook failed: {r_wh.text}"
    print("[OK] /api/webhooks/calcom:", r_wh.json())

    # 7. Test Chatwoot Webhook: conversation_created (Mesaj Automat de Întâmpinare per Inbox dev.avanz.ro)
    r_cw_welcome = client.post(
        "/api/webhooks/chatwoot",
        json={
            "event": "conversation_created",
            "inbox": {"id": 1, "name": "dev.avanz.ro"},
            "conversation": {
                "id": 88,
                "inbox_id": 1,
                "additional_attributes": {"referer": "https://dev.avanz.ro/dashboard"},
            },
            "account": {"id": 1},
        },
    )
    assert (
        r_cw_welcome.status_code == 200
        and r_cw_welcome.json()["status"] == "welcome_sent"
    ), f"Chatwoot welcome failed: {r_cw_welcome.text}"
    print(
        "[OK] /api/webhooks/chatwoot (conversation_created welcome_sent):",
        r_cw_welcome.json()["inbox"],
    )

    # 8. Test Chatwoot Webhook: message_created pe Inbox #2 (Suport Tehnic dev.avanz.ro) + Human Handoff
    r_cw = client.post(
        "/api/webhooks/chatwoot",
        json={
            "event": "message_created",
            "message_type": "incoming",
            "content": "Cum funcționează integrarea e-Factura ANAF și pontajul GPS în dev.avanz.ro?",
            "sender": {"type": "contact"},
            "inbox": {"id": 2, "name": "AvanzCRM — Suport Tehnic & QA (dev.avanz.ro)"},
            "conversation": {"id": 77, "inbox_id": 2},
            "account": {"id": 1},
        },
    )
    assert r_cw.status_code == 200, f"Chatwoot webhook failed: {r_cw.text}"
    print(
        "[OK] /api/webhooks/chatwoot (AI reply on Inbox #2):",
        r_cw.json()["status"],
        "| Inbox:",
        r_cw.json()["inbox"],
    )

    r_cw_handoff = client.post(
        "/api/webhooks/chatwoot",
        json={
            "event": "message_created",
            "message_type": "incoming",
            "content": "Vreau să vorbesc cu un operator uman vă rog",
            "sender": {"type": "contact"},
            "inbox": {"id": 1, "name": "dev.avanz.ro"},
            "conversation": {"id": 77, "inbox_id": 1},
            "account": {"id": 1},
        },
    )
    assert (
        r_cw_handoff.status_code == 200
        and r_cw_handoff.json()["status"] == "handoff_to_human"
    )
    print(
        "[OK] /api/webhooks/chatwoot (Personalized Human Handoff):",
        r_cw_handoff.json()["reply"],
    )

    # 9. Test Embed Widget (/widget.js?inbox=inbox-avanz-main)
    r_widget = client.get("/widget.js?inbox=inbox-avanz-main")
    assert (
        r_widget.status_code == 200
        and "ai-receptionist-widget-root" in r_widget.text
        and "inbox=inbox-avanz-main" in r_widget.text
    )
    print("[OK] /widget.js?inbox=inbox-avanz-main: multi-inbox floating widget verified")


if __name__ == "__main__":
    run_smoke_tests()
