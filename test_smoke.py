import sys
from fastapi.testclient import TestClient
from app.main import app

sys.stdout.reconfigure(encoding="utf-8")


def run_smoke_tests() -> None:
    client = TestClient(app)

    # 1. Test Healthcheck (pentru UptimeRobot / cron-job.org)
    r_health = client.get("/api/health")
    assert r_health.status_code == 200, f"Health failed: {r_health.text}"
    health_data = r_health.json()
    print("[OK] /api/health:", health_data["status"], "| Clinic:", health_data["clinic_name"])

    # 2. Test Status Cal.com + Medici Catalog
    r_cal = client.get("/api/calcom/status")
    assert r_cal.status_code == 200, f"Cal.com status failed: {r_cal.text}"
    cal_data = r_cal.json()
    print("[OK] /api/calcom/status | Medici disponibili:", len(cal_data.get("doctors", [])))

    # 3. Test Verificare Ore Libere prin Chat + Edge-TTS Română
    r_chat1 = client.post(
        "/api/chat",
        json={
            "session_id": "test-1",
            "message": "Bună ziua! Ce ore libere aveți mâine pentru o consultație?",
            "voice": "ro-RO-AlinaNeural",
            "generate_audio": True,
        },
    )
    assert r_chat1.status_code == 200, f"Chat 1 failed: {r_chat1.text}"
    d1 = r_chat1.json()
    print("[OK] /api/chat (availability):", d1["reply"])
    print("     Tools used:", d1["tools_used"])
    print("     Audio MP3 Base64 generated:", bool(d1.get("audio_base64")), f"({len(d1.get('audio_base64') or '')} chars)")

    # 4. Test Programare Nouă prin Chat (Cal.com + Google Calendar link)
    r_chat2 = client.post(
        "/api/chat",
        json={
            "session_id": "test-1",
            "message": "Vreau să mă programez mâine la ora 16:30 pe numele Popescu Vlad, telefon 0722999888",
            "voice": "ro-RO-EmilNeural",
            "generate_audio": True,
        },
    )
    assert r_chat2.status_code == 200, f"Chat 2 failed: {r_chat2.text}"
    d2 = r_chat2.json()
    print("[OK] /api/chat (booking):", d2["reply"])
    print("     Tools used:", d2["tools_used"])
    print("     Total appointments now:", len(d2["appointments"]))

    # 5. Test Cal.com Webhook Receiver (BOOKING_CREATED din Google Calendar / Cal.com)
    r_wh = client.post(
        "/api/webhooks/calcom",
        json={
            "triggerEvent": "BOOKING_CREATED",
            "payload": {
                "bookingId": 9901,
                "title": "Consultație Implantologie",
                "startTime": f"{health_data['tomorrow_date']}T14:00:00Z",
                "attendees": [{"name": "Ionescu Maria", "email": "maria@exemplu.ro"}],
                "metadata": {"phone": "0733 123 456"},
            },
        },
    )
    assert r_wh.status_code == 200, f"Cal.com webhook failed: {r_wh.text}"
    print("[OK] /api/webhooks/calcom:", r_wh.json())


if __name__ == "__main__":
    run_smoke_tests()
