from datetime import datetime, timedelta
from typing import Any
import httpx
from app.config import settings


class CalComService:
    """
    Serviciu CRM & Programări conectat la Cal.com API (sincronizat cu Google Calendar).
    Include un motor local de programări (In-Memory Demo Calendar) astfel încât
    demo-ul să funcționeze instantaneu cu 0 configurări și să afișeze programările pe ecran!
    """

    CAL_API_V1_BASE = "https://api.cal.com/v1"

    def __init__(self) -> None:
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")

        # Programări inițiale pre-populate pentru ca demonstrația live să arate realist
        self.demo_appointments: list[dict[str, Any]] = [
            {
                "id": "BK-1001",
                "patient_name": "Popescu Alexandru",
                "phone": "0722 111 222",
                "date": tomorrow,
                "time": "10:00",
                "service": "Consultație + Detartraj",
                "doctor": "Dr. Elena Dumitrescu",
                "source": "WhatsApp AI",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            },
            {
                "id": "BK-1002",
                "patient_name": "Marinescu Ioana",
                "phone": "0744 333 444",
                "date": tomorrow,
                "time": "15:00",
                "service": "Control Implantologie",
                "doctor": "Dr. Andrei Ionescu",
                "source": "Voice AI Web",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            },
            {
                "id": "BK-1003",
                "patient_name": "Stan Cristian",
                "phone": "0766 555 666",
                "date": day_after,
                "time": "11:30",
                "service": "Albire Dentară Philips Zoom",
                "doctor": "Dr. Elena Dumitrescu",
                "source": "Voice AI Web",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            },
        ]

        self.standard_slots = [
            "09:00",
            "10:00",
            "11:30",
            "13:00",
            "15:00",
            "16:30",
            "18:00",
        ]

    def get_all_appointments(self) -> list[dict[str, Any]]:
        return sorted(
            self.demo_appointments,
            key=lambda x: (x.get("date", ""), x.get("time", "")),
        )

    async def check_availability(self, date_str: str) -> dict[str, Any]:
        """Verifică intervalele orare libere în Cal.com (sau în calendarul de Demo)."""
        # Dacă utilizatorul a configurat cheia Cal.com reală
        if settings.calcom_api_key and settings.calcom_event_type_id:
            try:
                start_time = f"{date_str}T00:00:00Z"
                end_time = f"{date_str}T23:59:59Z"
                params = {
                    "apiKey": settings.calcom_api_key,
                    "eventTypeId": settings.calcom_event_type_id,
                    "startTime": start_time,
                    "endTime": end_time,
                    "timeZone": settings.calcom_timezone,
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(f"{self.CAL_API_V1_BASE}/slots", params=params)
                    if resp.status_code == 200:
                        slots_data = resp.json().get("slots", {})
                        day_slots = slots_data.get(date_str, [])
                        extracted_hours = [
                            s.get("time", "")[11:16] for s in day_slots if "time" in s
                        ]
                        if extracted_hours:
                            return {
                                "date": date_str,
                                "provider": "Cal.com Live API",
                                "available_slots": extracted_hours,
                            }
            except Exception:
                pass

        # Fallback la calendarul interactiv de Demo
        booked_times = {
            appt["time"]
            for appt in self.demo_appointments
            if appt["date"] == date_str
        }
        available = [slot for slot in self.standard_slots if slot not in booked_times]

        return {
            "date": date_str,
            "provider": "Cal.com / Demo Sync",
            "occupied_slots": sorted(list(booked_times)),
            "available_slots": available,
        }

    async def book_appointment(
        self,
        patient_name: str,
        phone: str,
        date_str: str,
        time_str: str,
        service: str = "Consultație Stomatologică",
        doctor: str = "Dr. Andrei Ionescu",
        source: str = "Voice & Web AI",
    ) -> dict[str, Any]:
        """Creează o programare în Cal.com și o adaugă în panoul vizual live."""
        # Verificăm dacă ora este deja ocupată în demo
        for appt in self.demo_appointments:
            if appt["date"] == date_str and appt["time"] == time_str:
                return {
                    "status": "error",
                    "message": (
                        f"Intervalul {time_str} din data de {date_str} este deja ocupat. "
                        "Te rog propune altă oră disponibilă."
                    ),
                }

        calcom_booking_id = None
        if settings.calcom_api_key and settings.calcom_event_type_id:
            try:
                start_iso = f"{date_str}T{time_str}:00"
                payload = {
                    "eventTypeId": int(settings.calcom_event_type_id),
                    "start": start_iso,
                    "responses": {
                        "name": patient_name,
                        "email": "pacient@demosmile.ro",
                        "notes": f"Serviciu: {service} | Telefon: {phone} | Medic: {doctor}",
                    },
                    "timeZone": settings.calcom_timezone,
                    "language": "ro",
                    "metadata": {"source": source, "phone": phone},
                }
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.post(
                        f"{self.CAL_API_V1_BASE}/bookings",
                        params={"apiKey": settings.calcom_api_key},
                        json=payload,
                    )
                    if resp.status_code in (200, 201):
                        calcom_booking_id = f"CAL-{resp.json().get('id', 'LIVE')}"
            except Exception:
                pass

        booking_id = calcom_booking_id or f"BK-{1001 + len(self.demo_appointments)}"
        new_appt = {
            "id": booking_id,
            "patient_name": patient_name,
            "phone": phone,
            "date": date_str,
            "time": time_str,
            "service": service,
            "doctor": doctor,
            "source": source,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        self.demo_appointments.append(new_appt)

        return {
            "status": "confirmed",
            "booking": new_appt,
            "message": (
                f"Programarea cu codul {booking_id} a fost înregistrată cu succes pentru "
                f"{patient_name} pe data de {date_str} la ora {time_str} ({service})."
            ),
        }


cal_service = CalComService()
