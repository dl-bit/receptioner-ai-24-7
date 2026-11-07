import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
import httpx
from app.config import DOCTORS_CATALOG, settings


class CalComService:
    """
    Serviciu complet CRM & Programări conectat la Cal.com (Open-Source / Cloud Free Tier)
    sincronizat bidirecțional cu Google Calendar.
    Suportă:
      - Cal.com API v1 & v2 (Cloud + Self-Hosted Open-Source)
      - Auto-detecție Event Types (nu necesită neapărat ID manual dacă există cheia API)
      - Verificare ore libere pe medici + filtrare Google Calendar Busy Slots
      - Creare programare în Cal.com + generare link direct Google Calendar
      - Anulare programare & Webhook receiver (BOOKING_CREATED / CANCELLED / RESCHEDULED)
    """

    def __init__(self) -> None:
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        day_after = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")

        self.cached_event_types: list[dict[str, Any]] = []
        self.last_sync_status: str = "ready"

        # Programări inițiale pre-populate pentru demonstrație și sincronizare
        self.demo_appointments: list[dict[str, Any]] = [
            {
                "id": "BK-1001",
                "patient_name": "Popescu Alexandru",
                "phone": "0722 111 222",
                "email": "alex.popescu@exemplu.ro",
                "date": tomorrow,
                "time": "10:00",
                "service": "Consultație + Detartraj",
                "doctor": "Dr. Elena Dumitrescu",
                "source": "WhatsApp AI",
                "status": "confirmed",
                "calcom_synced": False,
                "gcal_url": self._build_google_calendar_url(
                    patient_name="Popescu Alexandru",
                    phone="0722 111 222",
                    date_str=tomorrow,
                    time_str="10:00",
                    service="Consultație + Detartraj",
                    doctor="Dr. Elena Dumitrescu",
                ),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            },
            {
                "id": "BK-1002",
                "patient_name": "Marinescu Ioana",
                "phone": "0744 333 444",
                "email": "ioana.marinescu@exemplu.ro",
                "date": tomorrow,
                "time": "15:00",
                "service": "Control Implantologie",
                "doctor": "Dr. Andrei Ionescu",
                "source": "Voice AI Web",
                "status": "confirmed",
                "calcom_synced": False,
                "gcal_url": self._build_google_calendar_url(
                    patient_name="Marinescu Ioana",
                    phone="0744 333 444",
                    date_str=tomorrow,
                    time_str="15:00",
                    service="Control Implantologie",
                    doctor="Dr. Andrei Ionescu",
                ),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            },
            {
                "id": "BK-1003",
                "patient_name": "Stan Cristian",
                "phone": "0766 555 666",
                "email": "cristian.stan@exemplu.ro",
                "date": day_after,
                "time": "11:30",
                "service": "Albire Dentară Philips Zoom",
                "doctor": "Dr. Elena Dumitrescu",
                "source": "Voice AI Web",
                "status": "confirmed",
                "calcom_synced": False,
                "gcal_url": self._build_google_calendar_url(
                    patient_name="Stan Cristian",
                    phone="0766 555 666",
                    date_str=day_after,
                    time_str="11:30",
                    service="Albire Dentară Philips Zoom",
                    doctor="Dr. Elena Dumitrescu",
                ),
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

    @property
    def api_base(self) -> str:
        return (settings.calcom_api_url or "https://api.cal.com").rstrip("/")

    def _build_google_calendar_url(
        self,
        patient_name: str,
        phone: str,
        date_str: str,
        time_str: str,
        service: str,
        doctor: str,
    ) -> str:
        """Generează link direct Google Calendar (Template Event) pentru sincronizare 1-click."""
        try:
            start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            end_dt = start_dt + timedelta(minutes=30)
            dates_param = f"{start_dt.strftime('%Y%m%dT%H%M00')}/{end_dt.strftime('%Y%m%dT%H%M00')}"
        except Exception:
            dates_param = ""

        params = {
            "action": "TEMPLATE",
            "text": f"[{settings.clinic_name}] {service} - {patient_name}",
            "dates": dates_param,
            "details": (
                f"Pacient: {patient_name}\n"
                f"Telefon: {phone}\n"
                f"Serviciu: {service}\n"
                f"Medic: {doctor}\n"
                f"Programat automat de Recepționerul AI 24/7 (Cal.com Sync)."
            ),
            "location": settings.clinic_name,
            "ctz": settings.calcom_timezone,
        }
        return f"https://calendar.google.com/calendar/render?{urlencode(params)}"

    def select_doctor_for_service(
        self, service: str, requested_doctor: str | None = None
    ) -> str:
        """Selectează medicul potrivit în funcție de serviciul solicitat sau numele menționat."""
        if requested_doctor:
            req_low = requested_doctor.lower()
            for doc in DOCTORS_CATALOG:
                if any(part in req_low for part in doc["name"].lower().split()):
                    return doc["name"]

        srv_low = (service or "").lower()
        if any(k in srv_low for k in ["implant", "chirurg", "extrac", "măsea de minte"]):
            return "Dr. Andrei Ionescu"
        if any(k in srv_low for k in ["ortodon", "aparat", "copil", "copii", "pedodon"]):
            return "Dr. Mihai Radu"
        return "Dr. Elena Dumitrescu"

    def get_all_appointments(self) -> list[dict[str, Any]]:
        active = [a for a in self.demo_appointments if a.get("status", "confirmed") != "cancelled"]
        return sorted(
            active,
            key=lambda x: (x.get("date", ""), x.get("time", "")),
        )

    async def discover_event_types(self, api_key: str | None = None) -> list[dict[str, Any]]:
        """
        Interoghează Cal.com API (v1 și v2) pentru a descoperi automat tipurile de programări
        (Event Types) din contul utilizatorului și a seta automat CALCOM_EVENT_TYPE_ID dacă lipsește.
        """
        key = (api_key or settings.calcom_api_key or "").strip()
        if not key:
            return []

        discovered: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Încercăm Cal.com API v1 (/v1/event-types?apiKey=...)
            try:
                r1 = await client.get(
                    f"{self.api_base}/v1/event-types",
                    params={"apiKey": key},
                )
                if r1.status_code == 200:
                    for et in r1.json().get("event_types", []):
                        discovered.append(
                            {
                                "id": str(et.get("id")),
                                "title": et.get("title", "Consultație"),
                                "slug": et.get("slug", ""),
                                "length": et.get("length", 30),
                            }
                        )
            except Exception:
                pass

            # Dacă nu am găsit în v1, încercăm Cal.com API v2 (/v2/event-types cu Bearer token)
            if not discovered:
                try:
                    r2 = await client.get(
                        f"{self.api_base}/v2/event-types",
                        headers={
                            "Authorization": f"Bearer {key}",
                            "cal-api-version": "2024-06-14",
                        },
                    )
                    if r2.status_code == 200:
                        data = r2.json().get("data", [])
                        if isinstance(data, dict):
                            data = data.get("eventTypeGroups", [])
                        for item in data:
                            if "id" in item:
                                discovered.append(
                                    {
                                        "id": str(item.get("id")),
                                        "title": item.get("title", "Consultație"),
                                        "slug": item.get("slug", ""),
                                        "length": item.get("lengthInMinutes", 30),
                                    }
                                )
                except Exception:
                    pass

        if discovered:
            self.cached_event_types = discovered
            if not settings.calcom_event_type_id:
                settings.calcom_event_type_id = discovered[0]["id"]

        return discovered

    async def ensure_event_type_id(self) -> str:
        if settings.calcom_event_type_id:
            return str(settings.calcom_event_type_id)
        if settings.calcom_api_key:
            ets = await self.discover_event_types(settings.calcom_api_key)
            if ets:
                return str(ets[0]["id"])
        return ""

    async def check_availability(
        self,
        date_str: str,
        doctor: str | None = None,
        service: str | None = None,
    ) -> dict[str, Any]:
        """
        Verifică intervalele orare libere ale medicilor în Cal.com (care filtrează automat
        evenimentele ocupate din Google Calendar) + programările locale.
        """
        selected_doctor = (
            self.select_doctor_for_service(service or "", doctor)
            if (doctor or service)
            else None
        )

        event_type_id = await self.ensure_event_type_id()
        calcom_live_slots: list[str] | None = None

        if settings.calcom_api_key and event_type_id:
            start_time = f"{date_str}T00:00:00Z"
            end_time = f"{date_str}T23:59:59Z"
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 1. Cal.com API v1 /slots
                try:
                    params = {
                        "apiKey": settings.calcom_api_key,
                        "eventTypeId": event_type_id,
                        "startTime": start_time,
                        "endTime": end_time,
                        "timeZone": settings.calcom_timezone,
                    }
                    resp = await client.get(f"{self.api_base}/v1/slots", params=params)
                    if resp.status_code == 200:
                        slots_data = resp.json().get("slots", {})
                        day_slots = slots_data.get(date_str, [])
                        calcom_live_slots = [
                            s.get("time", "")[11:16] for s in day_slots if "time" in s
                        ]
                except Exception:
                    pass

                # 2. Fallback la Cal.com API v2 /v2/slots/available
                if calcom_live_slots is None:
                    try:
                        resp_v2 = await client.get(
                            f"{self.api_base}/v2/slots/available",
                            headers={
                                "Authorization": f"Bearer {settings.calcom_api_key}",
                                "cal-api-version": "2024-09-04",
                            },
                            params={
                                "startTime": start_time,
                                "endTime": end_time,
                                "eventTypeId": event_type_id,
                                "timeZone": settings.calcom_timezone,
                            },
                        )
                        if resp_v2.status_code == 200:
                            slots_data = resp_v2.json().get("data", {}).get("slots", {})
                            day_slots = slots_data.get(date_str, [])
                            calcom_live_slots = [
                                s.get("time", "")[11:16] for s in day_slots if "time" in s
                            ]
                    except Exception:
                        pass

        # Orele deja ocupate în memoria locală / sincronizată
        booked_for_day = [
            appt
            for appt in self.get_all_appointments()
            if appt["date"] == date_str
            and (not selected_doctor or appt.get("doctor") == selected_doctor)
        ]
        booked_times = {appt["time"] for appt in booked_for_day}

        base_slots = calcom_live_slots if calcom_live_slots is not None else self.standard_slots
        available = [slot for slot in base_slots if slot not in booked_times]

        # Disponibilitate detaliată pe fiecare medic al clinicii
        doctors_schedule = []
        for doc in DOCTORS_CATALOG:
            doc_booked = {
                appt["time"]
                for appt in self.get_all_appointments()
                if appt["date"] == date_str and appt.get("doctor") == doc["name"]
            }
            doc_free = [s for s in doc["default_slots"] if s not in doc_booked]
            doctors_schedule.append(
                {
                    "doctor": doc["name"],
                    "specialty": doc["specialty"],
                    "available_slots": doc_free,
                    "occupied_slots": sorted(list(doc_booked)),
                }
            )

        provider_name = (
            f"Cal.com Live API + Google Calendar (Event #{event_type_id})"
            if calcom_live_slots is not None
            else "Cal.com + Google Calendar Sync Engine"
        )

        return {
            "date": date_str,
            "provider": provider_name,
            "calcom_live": calcom_live_slots is not None,
            "doctor_filter": selected_doctor or "Toți medicii disponibili",
            "occupied_slots": sorted(list(booked_times)),
            "available_slots": available,
            "doctors_schedule": doctors_schedule,
        }

    async def book_appointment(
        self,
        patient_name: str,
        phone: str,
        date_str: str,
        time_str: str,
        service: str = "Consultație Stomatologică",
        doctor: str | None = None,
        email: str = "pacient@demosmile.ro",
        source: str = "Voice & Web AI",
    ) -> dict[str, Any]:
        """
        Creează o programare în Cal.com (sincronizată automat în Google Calendar-ul medicului)
        și o adaugă în panoul vizual live.
        """
        assigned_doctor = self.select_doctor_for_service(service, doctor)

        # Verificăm dacă ora este deja ocupată la acel medic
        for appt in self.get_all_appointments():
            if (
                appt["date"] == date_str
                and appt["time"] == time_str
                and appt.get("doctor") == assigned_doctor
            ):
                return {
                    "status": "error",
                    "message": (
                        f"Intervalul {time_str} din data de {date_str} la {assigned_doctor} este deja ocupat. "
                        "Te rog propune o altă oră liberă."
                    ),
                }

        calcom_booking_id = None
        calcom_synced = False
        event_type_id = await self.ensure_event_type_id()

        if settings.calcom_api_key and event_type_id:
            start_iso = f"{date_str}T{time_str}:00"
            async with httpx.AsyncClient(timeout=12.0) as client:
                # 1. Cal.com API v1 POST /v1/bookings
                try:
                    payload_v1 = {
                        "eventTypeId": int(event_type_id),
                        "start": start_iso,
                        "responses": {
                            "name": patient_name,
                            "email": email or "pacient@demosmile.ro",
                            "notes": f"Serviciu: {service} | Telefon: {phone} | Medic: {assigned_doctor}",
                            "location": {
                                "value": "inPerson",
                                "optionValue": "",
                            },
                        },
                        "timeZone": settings.calcom_timezone,
                        "language": "ro",
                        "metadata": {
                            "source": source,
                            "phone": phone,
                            "doctor": assigned_doctor,
                            "service": service,
                        },
                    }
                    resp = await client.post(
                        f"{self.api_base}/v1/bookings",
                        params={"apiKey": settings.calcom_api_key},
                        json=payload_v1,
                    )
                    if resp.status_code in (200, 201):
                        data = resp.json()
                        calcom_booking_id = f"CAL-{data.get('id', 'LIVE')}"
                        calcom_synced = True
                except Exception:
                    pass

                # 2. Fallback Cal.com API v2 POST /v2/bookings
                if not calcom_synced:
                    try:
                        payload_v2 = {
                            "start": f"{start_iso}Z",
                            "eventTypeId": int(event_type_id),
                            "attendee": {
                                "name": patient_name,
                                "email": email or "pacient@demosmile.ro",
                                "timeZone": settings.calcom_timezone,
                                "language": "ro",
                            },
                            "metadata": {
                                "phone": phone,
                                "service": service,
                                "doctor": assigned_doctor,
                                "source": source,
                            },
                        }
                        resp2 = await client.post(
                            f"{self.api_base}/v2/bookings",
                            headers={
                                "Authorization": f"Bearer {settings.calcom_api_key}",
                                "cal-api-version": "2024-08-13",
                            },
                            json=payload_v2,
                        )
                        if resp2.status_code in (200, 201):
                            data2 = resp2.json().get("data", {})
                            calcom_booking_id = f"CAL-{data2.get('id') or data2.get('uid', 'LIVE')}"
                            calcom_synced = True
                    except Exception:
                        pass

        booking_id = calcom_booking_id or f"BK-{1001 + len(self.demo_appointments)}"
        gcal_url = self._build_google_calendar_url(
            patient_name=patient_name,
            phone=phone,
            date_str=date_str,
            time_str=time_str,
            service=service,
            doctor=assigned_doctor,
        )

        new_appt = {
            "id": booking_id,
            "patient_name": patient_name,
            "phone": phone,
            "email": email,
            "date": date_str,
            "time": time_str,
            "service": service,
            "doctor": assigned_doctor,
            "source": source,
            "status": "confirmed",
            "calcom_synced": calcom_synced,
            "gcal_url": gcal_url,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        self.demo_appointments.append(new_appt)

        return {
            "status": "confirmed",
            "calcom_synced": calcom_synced,
            "booking": new_appt,
            "gcal_url": gcal_url,
            "message": (
                f"Programarea cu codul {booking_id} a fost înregistrată cu succes pentru "
                f"{patient_name} pe data de {date_str} la ora {time_str} ({service} la {assigned_doctor})."
            ),
        }

    async def cancel_appointment(
        self, booking_id_or_name: str, reason: str = "Anulat la cererea pacientului"
    ) -> dict[str, Any]:
        """Anulează o programare după ID (ex: BK-1001 / CAL-123) sau după numele pacientului."""
        target_q = booking_id_or_name.strip().lower()
        found = None
        for appt in self.demo_appointments:
            if appt.get("status") == "cancelled":
                continue
            if (
                appt["id"].lower() == target_q
                or target_q in appt["patient_name"].lower()
            ):
                found = appt
                break

        if not found:
            return {
                "status": "not_found",
                "message": f"Nu am găsit nicio programare activă pentru „{booking_id_or_name}”.",
            }

        found["status"] = "cancelled"

        # Dacă este o programare Cal.com reală (CAL-...), o anulăm și în Cal.com API
        if found["id"].startswith("CAL-") and settings.calcom_api_key:
            raw_cal_id = found["id"].replace("CAL-", "")
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.delete(
                        f"{self.api_base}/v1/bookings/{raw_cal_id}/cancel",
                        params={
                            "apiKey": settings.calcom_api_key,
                            "allRemainingBookings": "false",
                            "cancellationReason": reason,
                        },
                    )
            except Exception:
                pass

        return {
            "status": "cancelled",
            "cancelled_booking": found,
            "message": (
                f"Programarea {found['id']} pentru {found['patient_name']} din "
                f"{found['date']} ora {found['time']} a fost anulată."
            ),
        }

    async def sync_bookings_from_calcom(self) -> dict[str, Any]:
        """Sincronizează programările viitoare din contul Cal.com al clinicii."""
        if not settings.calcom_api_key:
            return {
                "synced": False,
                "message": "Cheia CALCOM_API_KEY nu este încă setată. Rulează pe motorul local sincronizat.",
                "appointments": self.get_all_appointments(),
            }

        imported_count = 0
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.api_base}/v1/bookings",
                    params={"apiKey": settings.calcom_api_key, "status": "upcoming"},
                )
                if resp.status_code == 200:
                    bookings = resp.json().get("bookings", [])
                    existing_ids = {a["id"] for a in self.demo_appointments}
                    for b in bookings:
                        cal_id = f"CAL-{b.get('id')}"
                        if cal_id in existing_ids or b.get("status") == "CANCELLED":
                            continue
                        start_time = b.get("startTime", "")
                        date_part = start_time[:10] if len(start_time) >= 10 else ""
                        time_part = start_time[11:16] if len(start_time) >= 16 else "10:00"
                        attendees = b.get("attendees", [])
                        att_name = (
                            attendees[0].get("name", "Pacient Cal.com")
                            if attendees
                            else b.get("title", "Pacient Cal.com")
                        )
                        att_email = (
                            attendees[0].get("email", "pacient@cal.com")
                            if attendees
                            else "pacient@cal.com"
                        )
                        meta = b.get("metadata") or {}
                        phone = meta.get("phone", "Sincronizat Cal.com")
                        doctor = meta.get("doctor", "Dr. Elena Dumitrescu")
                        service = meta.get("service") or b.get("title", "Consultație Cal.com")

                        self.demo_appointments.append(
                            {
                                "id": cal_id,
                                "patient_name": att_name,
                                "phone": phone,
                                "email": att_email,
                                "date": date_part,
                                "time": time_part,
                                "service": service,
                                "doctor": doctor,
                                "source": "Cal.com + Google Calendar",
                                "status": "confirmed",
                                "calcom_synced": True,
                                "gcal_url": self._build_google_calendar_url(
                                    patient_name=att_name,
                                    phone=phone,
                                    date_str=date_part,
                                    time_str=time_part,
                                    service=service,
                                    doctor=doctor,
                                ),
                                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            }
                        )
                        imported_count += 1
        except Exception as exc:
            return {
                "synced": False,
                "message": f"Eroare la sincronizarea Cal.com: {exc}",
                "appointments": self.get_all_appointments(),
            }

        return {
            "synced": True,
            "imported_count": imported_count,
            "message": f"Sincronizare Cal.com + Google Calendar reușită ({imported_count} programări noi preluate).",
            "appointments": self.get_all_appointments(),
        }

    def handle_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Procesează webhook-uri în timp real trimise de Cal.com (BOOKING_CREATED,
        BOOKING_CANCELLED, BOOKING_RESCHEDULED) când se modifică ceva în Google Calendar / Cal.com.
        """
        trigger = payload.get("triggerEvent", "")
        data = payload.get("payload", {})
        cal_id = f"CAL-{data.get('bookingId') or data.get('uid', 'WEBHOOK')}"

        if trigger == "BOOKING_CANCELLED":
            for appt in self.demo_appointments:
                if appt["id"] == cal_id:
                    appt["status"] = "cancelled"
            return {"status": "cancelled", "id": cal_id}

        if trigger in ("BOOKING_CREATED", "BOOKING_RESCHEDULED"):
            start_time = data.get("startTime", "")
            date_part = start_time[:10] if len(start_time) >= 10 else (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            time_part = start_time[11:16] if len(start_time) >= 16 else "12:00"
            attendees = data.get("attendees", [])
            patient_name = attendees[0].get("name", "Pacient Cal.com") if attendees else "Pacient Cal.com"
            phone = (data.get("metadata") or {}).get("phone", "Cal.com Webhook")
            service = data.get("title", "Consultație Cal.com")
            doctor = self.select_doctor_for_service(service)

            # Evităm duplicatele la reschedule
            self.demo_appointments = [a for a in self.demo_appointments if a["id"] != cal_id]
            self.demo_appointments.append(
                {
                    "id": cal_id,
                    "patient_name": patient_name,
                    "phone": phone,
                    "email": attendees[0].get("email", "") if attendees else "",
                    "date": date_part,
                    "time": time_part,
                    "service": service,
                    "doctor": doctor,
                    "source": "Cal.com Webhook",
                    "status": "confirmed",
                    "calcom_synced": True,
                    "gcal_url": self._build_google_calendar_url(
                        patient_name=patient_name,
                        phone=phone,
                        date_str=date_part,
                        time_str=time_part,
                        service=service,
                        doctor=doctor,
                    ),
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
            )
            return {"status": "updated", "id": cal_id}

        return {"status": "ignored", "trigger": trigger}

    async def configure_and_test(
        self,
        api_key: str,
        event_type_id: str = "",
        api_url: str = "https://api.cal.com",
        timezone: str = "Europe/Bucharest",
    ) -> dict[str, Any]:
        """
        Salvează configurația Cal.com în memorie și în fișierul .env, detectează automat
        Event Types din Cal.com și sincronizează programările.
        """
        settings.calcom_api_key = api_key.strip()
        settings.calcom_api_url = (api_url or "https://api.cal.com").strip().rstrip("/")
        settings.calcom_timezone = (timezone or "Europe/Bucharest").strip()
        if event_type_id.strip():
            settings.calcom_event_type_id = event_type_id.strip()

        discovered = await self.discover_event_types(settings.calcom_api_key)
        if not settings.calcom_event_type_id and discovered:
            settings.calcom_event_type_id = str(discovered[0]["id"])

        # Persistăm în fișierul .env local
        self._persist_to_env_file(
            {
                "CALCOM_API_URL": settings.calcom_api_url,
                "CALCOM_API_KEY": settings.calcom_api_key,
                "CALCOM_EVENT_TYPE_ID": settings.calcom_event_type_id,
                "CALCOM_TIMEZONE": settings.calcom_timezone,
            }
        )

        sync_res = await self.sync_bookings_from_calcom()
        return {
            "configured": bool(settings.calcom_api_key),
            "calcom_api_url": settings.calcom_api_url,
            "calcom_event_type_id": settings.calcom_event_type_id,
            "discovered_event_types": discovered,
            "sync_result": sync_res,
        }

    def _persist_to_env_file(self, updates: dict[str, str]) -> None:
        env_path = Path(".env")
        if not env_path.exists():
            lines = [f"{k}={v}" for k, v in updates.items()]
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return

        content = env_path.read_text(encoding="utf-8")
        for key, val in updates.items():
            pattern = rf"^{re.escape(key)}=.*$"
            if re.search(pattern, content, flags=re.MULTILINE):
                content = re.sub(pattern, f"{key}={val}", content, flags=re.MULTILINE)
            else:
                content += f"\n{key}={val}"
        env_path.write_text(content, encoding="utf-8")


cal_service = CalComService()
