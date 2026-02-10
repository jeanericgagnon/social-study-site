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

LA = ZoneInfo("America/Los_Angeles")
GCAL_DIR = Path("/Users/ericsysclaw/.openclaw/workspace/gcal")
TOKEN_CANDIDATES = [
    GCAL_DIR / "token_sys_send.json",
    GCAL_DIR / "token_sys.json",
    GCAL_DIR / "token_all.json",
    GCAL_DIR / "token.json",
]


def load_creds():
    token_path = next((p for p in TOKEN_CANDIDATES if p.exists()), None)
    if not token_path:
        raise SystemExit("No Google token found")

    data = json.loads(token_path.read_text())
    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes", []),
    )
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        data["token"] = creds.token
        token_path.write_text(json.dumps(data, indent=2))

    scopes = set(data.get("scopes") or [])
    if "https://www.googleapis.com/auth/gmail.send" not in scopes:
        raise SystemExit("Token missing gmail.send scope")

    return creds


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
    calendars = cal_service.calendarList().list().execute().get("items", [])
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

    lines = [
        "Hi Quino,",
        "",
        "Reminder: these Eventship/Social Study events are 3 days out:",
        "",
    ]
    for e in events:
        lines.append(f"- {e['date']} • {e['time']} — {e['title']}")
    lines += ["", "Thanks,", "Sys"]

    subject = f"[3-day reminder] {len(events)} Eventship event(s) for {target_day.isoformat()}"
    send_email(gmail, "quino@thesocial.study", subject, "\n".join(lines))
    print(f"SENT {len(events)} to quino@thesocial.study")


if __name__ == "__main__":
    main()
