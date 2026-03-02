#!/usr/bin/env python3
import base64
import datetime as dt
import json
from email.mime.text import MIMEText
from pathlib import Path
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError

LA = ZoneInfo("America/Los_Angeles")
GCAL_DIR = Path("/Users/ericsysclaw/.openclaw/workspace/gcal")
TOKEN_CANDIDATES = [
    GCAL_DIR / "token_sys_send.json",
    GCAL_DIR / "token_sys.json",
    GCAL_DIR / "token_all.json",
    GCAL_DIR / "token.json",
]

# Authoritative source calendar(s) for this reminder.
TARGET_CALENDAR_IDS = [
    "eric@thesocial.study",
]


def load_creds():
    existing = [p for p in TOKEN_CANDIDATES if p.exists()]
    if not existing:
        raise SystemExit("No Google token found")

    errors = []
    for token_path in existing:
        data = json.loads(token_path.read_text())
        scopes = set(data.get("scopes") or [])
        has_gmail_send = (
            "https://www.googleapis.com/auth/gmail.send" in scopes
            or "https://mail.google.com/" in scopes
        )
        if not has_gmail_send:
            errors.append(f"{token_path.name}: missing gmail.send scope")
            continue

        creds = Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=data.get("scopes", []),
        )

        try:
            # Proactively validate the token so revoked/invalid refresh tokens
            # fail fast here (instead of failing later mid-request).
            if creds and creds.refresh_token:
                creds.refresh(Request())
                data["token"] = creds.token
                token_path.write_text(json.dumps(data, indent=2))
            elif not creds.valid:
                errors.append(f"{token_path.name}: token invalid and no refresh_token")
                continue
            return creds
        except RefreshError as e:
            errors.append(f"{token_path.name}: refresh failed ({e})")
            continue

    raise SystemExit("No usable Google token found; " + " | ".join(errors))


def to_local_day(value: str) -> dt.date:
    if "T" in value:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(LA).date()
    return dt.date.fromisoformat(value)


def local_time_label(value: str) -> str:
    if "T" not in value:
        return "all-day"
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(LA).strftime("%-I:%M %p")


def is_eventship(ev: dict) -> bool:
    hay = " ".join(
        [
            ev.get("summary", "") or "",
            ev.get("description", "") or "",
            ev.get("location", "") or "",
            ev.get("htmlLink", "") or "",
        ]
    ).lower()
    return "eventship" in hay


def get_target_events(cal_service):
    now = dt.datetime.now(LA)
    target_day = now.date() + dt.timedelta(days=3)

    start = dt.datetime.combine(target_day, dt.time(0, 0), tzinfo=LA)
    end = start + dt.timedelta(days=1)
    time_min = start.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    time_max = end.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")

    events = []
    calendars = []
    for cal_id in TARGET_CALENDAR_IDS:
        try:
            meta = cal_service.calendars().get(calendarId=cal_id).execute()
            cal_name = meta.get("summary", cal_id)
            calendars.append({"id": cal_id, "summary": cal_name})
        except Exception:
            # If explicit calendar is not accessible, skip it.
            continue

    if not calendars:
        raise SystemExit(
            "No accessible target calendars. Ensure this token can read eric@thesocial.study."
        )

    for c in calendars:
        cal_id = c.get("id")
        cal_name = c.get("summary", "(unknown)")
        rows = (
            cal_service.events()
            .list(
                calendarId=cal_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
            .get("items", [])
        )
        for ev in rows:
            st = ev.get("start", {})
            raw = st.get("dateTime") or st.get("date")
            if not raw:
                continue
            if to_local_day(raw) != target_day:
                continue
            if not is_eventship(ev):
                continue
            events.append(
                {
                    "title": ev.get("summary", "(no title)"),
                    "date": str(target_day),
                    "time": local_time_label(raw),
                    "venue": (ev.get("location") or "").strip(),
                    "calendar": cal_name,
                }
            )

    events.sort(key=lambda x: (x["date"], x["time"], x["title"]))
    return target_day, events


def send_email(gmail_service, to_addr: str, subject: str, body: str):
    msg = MIMEText(body)
    msg["to"] = to_addr
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()


def main():
    creds = load_creds()
    cal = build("calendar", "v3", credentials=creds, cache_discovery=False)
    gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)

    target_day, events = get_target_events(cal)
    if not events:
        print("NO_REPLY")
        return

    recipients = ["eric@thesocial.study", "quino@thesocial.study"]

    lines = [
        "Hi Eric and Quino,",
        "",
        "Heads up: these Eventship/Social Study events are 3 days out.",
        "Please confirm ticket release time, venue, and speaker for each:",
        "",
    ]
    for e in events:
        venue = e.get("venue") or "(venue missing — confirm venue)"
        lines.append(f"- {e['date']} • {e['time']} — {e['title']}")
        lines.append(f"  - Ticket release time: (confirm)")
        lines.append(f"  - Venue: {venue}")
        lines.append(f"  - Speaker: (confirm)")
    lines += ["", "Thanks,", "Sys"]

    subject = f"[3-day event check] {len(events)} Eventship event(s) for {target_day.isoformat()}"
    body = "\n".join(lines)
    for recipient in recipients:
        send_email(gmail, recipient, subject, body)
    print(f"SENT {len(events)} to {', '.join(recipients)}")


if __name__ == "__main__":
    main()
