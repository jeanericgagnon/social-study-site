#!/usr/bin/env python3
import argparse
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
CAL_TOKEN_CANDIDATES = [
    GCAL_DIR / "token_eric_readonly.json",
    GCAL_DIR / "token_sys_send.json",
    GCAL_DIR / "token_sys.json",
]
SEND_TOKEN_CANDIDATES = [
    GCAL_DIR / "token_sys_send.json",
]
TARGET_CALENDAR_IDS = ["eric@thesocial.study"]
RECIPIENTS = ["eric@thesocial.study", "quino@thesocial.study", "nick@thesocial.study"]


def _load_token(path: Path):
    data = json.loads(path.read_text())
    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes", []),
    )
    if creds and creds.refresh_token:
        creds.refresh(Request())
        data["token"] = creds.token
        path.write_text(json.dumps(data, indent=2))
    return creds, set(data.get("scopes") or [])


def load_calendar_creds():
    existing = [p for p in CAL_TOKEN_CANDIDATES if p.exists()]
    if not existing:
        raise SystemExit("No calendar token found")
    errors = []
    for token_path in existing:
        try:
            creds, scopes = _load_token(token_path)
            if not any(s.startswith("https://www.googleapis.com/auth/calendar") for s in scopes):
                errors.append(f"{token_path.name}: missing calendar scope")
                continue
            return creds
        except RefreshError as e:
            errors.append(f"{token_path.name}: refresh failed ({e})")
    raise SystemExit("No usable calendar token; " + " | ".join(errors))


def load_send_creds():
    existing = [p for p in SEND_TOKEN_CANDIDATES if p.exists()]
    if not existing:
        raise SystemExit("No gmail send token found")
    errors = []
    for token_path in existing:
        try:
            creds, scopes = _load_token(token_path)
            has_send = (
                "https://www.googleapis.com/auth/gmail.send" in scopes
                or "https://mail.google.com/" in scopes
            )
            if not has_send:
                errors.append(f"{token_path.name}: missing gmail send scope")
                continue
            return creds
        except RefreshError as e:
            errors.append(f"{token_path.name}: refresh failed ({e})")
    raise SystemExit("No usable send token; " + " | ".join(errors))


def to_local_day(value: str) -> dt.date:
    if "T" in value:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(LA).date()
    return dt.date.fromisoformat(value)


def local_time_label(value: str) -> str:
    if "T" not in value:
        return "all-day"
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(LA).strftime("%-I:%M %p")


def is_eventship(ev: dict) -> bool:
    organizer = ((ev.get("organizer") or {}).get("email") or "").lower()
    creator = ((ev.get("creator") or {}).get("email") or "").lower()
    hay = " ".join(
        [
            ev.get("summary", "") or "",
            ev.get("description", "") or "",
            ev.get("location", "") or "",
            ev.get("htmlLink", "") or "",
        ]
    ).lower()
    return organizer == "events@eventship.com" or creator == "events@eventship.com" or "eventship" in hay


def get_target_events(cal_service, days_out=3):
    now = dt.datetime.now(LA)
    target_day = now.date() + dt.timedelta(days=days_out)

    start = dt.datetime.combine(target_day, dt.time(0, 0), tzinfo=LA)
    end = start + dt.timedelta(days=1)
    time_min = start.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    time_max = end.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")

    events = []
    for cal_id in TARGET_CALENDAR_IDS:
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
                }
            )

    events.sort(key=lambda x: (x["date"], x["time"], x["title"]))
    return target_day, events


def build_message(events):
    lines = [
        f"Heads up: The Social Study events are 3 days out ({len(events)} total).",
        "Remember to release returned tickets, confirm speaker, and confirm venue:",
        "",
    ]
    for e in events:
        raw_venue = (e.get("venue") or "").strip()
        venue = raw_venue.split(",", 1)[0].strip() if raw_venue else "(venue missing — confirm venue)"
        lines.append(f"• {e['title']}")
        lines.append(f"  - Date/Time: {e['date']} • {e['time']}")
        lines.append("  - Release returned tickets")
        lines.append("  - Confirm speaker")
        lines.append(f"  - Confirm venue: {venue}")
    return "\n".join(lines)


def send_email(gmail_service, to_addr: str, subject: str, body: str):
    msg = MIMEText(body)
    msg["to"] = to_addr
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test-to", default="")
    args = ap.parse_args()

    cal_creds = load_calendar_creds()
    send_creds = load_send_creds()
    cal = build("calendar", "v3", credentials=cal_creds, cache_discovery=False)
    gmail = build("gmail", "v1", credentials=send_creds, cache_discovery=False)

    target_day, events = get_target_events(cal, days_out=3)
    if not events:
        print("NO_REPLY")
        return

    text = build_message(events)
    if args.dry_run:
        print(text)
        return

    subject = f"[3-day check] The Social Study events for {target_day.isoformat()}"
    recipients = [args.test_to] if args.test_to else RECIPIENTS
    for r in recipients:
        send_email(gmail, r, subject, text)
    print(f"SENT {len(events)} event(s) to {', '.join(recipients)}")


if __name__ == "__main__":
    main()
