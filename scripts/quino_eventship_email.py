#!/usr/bin/env python3
import argparse
import datetime as dt
import json
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
CHAT_TOKEN_CANDIDATES = [
    GCAL_DIR / "token_sys_send.json",
    GCAL_DIR / "token_chat_send.json",
]
TARGET_CALENDAR_IDS = ["eric@thesocial.study"]
CHAT_SPACE_FILE = GCAL_DIR / "eventship_chat_space.txt"
CHAT_RECIPIENTS = [
    "users/eric@thesocial.study",
    "users/quino@thesocial.study",
    "users/nick@thesocial.study",
]


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
            has_calendar = any(s.startswith("https://www.googleapis.com/auth/calendar") for s in scopes)
            if not has_calendar:
                errors.append(f"{token_path.name}: missing calendar scope")
                continue
            return creds
        except RefreshError as e:
            errors.append(f"{token_path.name}: refresh failed ({e})")
    raise SystemExit("No usable calendar token; " + " | ".join(errors))


def load_chat_creds():
    existing = [p for p in CHAT_TOKEN_CANDIDATES if p.exists()]
    if not existing:
        raise SystemExit("No chat token found")
    errors = []
    for token_path in existing:
        try:
            creds, scopes = _load_token(token_path)
            has_chat_send = (
                "https://www.googleapis.com/auth/chat.messages.create" in scopes
                or "https://www.googleapis.com/auth/chat.messages" in scopes
            )
            has_chat_spaces = (
                "https://www.googleapis.com/auth/chat.spaces" in scopes
                or "https://www.googleapis.com/auth/chat.spaces.create" in scopes
            )
            if not has_chat_send:
                errors.append(f"{token_path.name}: missing chat.messages.create scope")
                continue
            return creds, has_chat_spaces
        except RefreshError as e:
            errors.append(f"{token_path.name}: refresh failed ({e})")
    raise SystemExit("No usable chat token; " + " | ".join(errors))


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
    if organizer == "events@eventship.com" or creator == "events@eventship.com":
        return True
    hay = " ".join(
        [
            ev.get("summary", "") or "",
            ev.get("description", "") or "",
            ev.get("location", "") or "",
            ev.get("htmlLink", "") or "",
        ]
    ).lower()
    return "eventship" in hay


def get_target_events(cal_service, days_out=3):
    now = dt.datetime.now(LA)
    target_day = now.date() + dt.timedelta(days=days_out)

    start = dt.datetime.combine(target_day, dt.time(0, 0), tzinfo=LA)
    end = start + dt.timedelta(days=1)
    time_min = start.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    time_max = end.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")

    events = []
    calendars = []
    for cal_id in TARGET_CALENDAR_IDS:
        try:
            meta = cal_service.calendars().get(calendarId=cal_id).execute()
            calendars.append({"id": cal_id, "summary": meta.get("summary", cal_id)})
        except Exception:
            continue

    if not calendars:
        raise SystemExit("No accessible target calendars. Ensure token can read eric@thesocial.study")

    for c in calendars:
        rows = (
            cal_service.events()
            .list(
                calendarId=c["id"],
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
                    "calendar": c["summary"],
                }
            )

    events.sort(key=lambda x: (x["date"], x["time"], x["title"]))
    return target_day, events


def ensure_chat_space(chat_service, can_create_space: bool) -> str:
    if CHAT_SPACE_FILE.exists():
        s = CHAT_SPACE_FILE.read_text().strip()
        if s.startswith("spaces/"):
            return s

    if not can_create_space:
        raise SystemExit("Missing stored chat space id and token lacks chat.spaces create scope")

    body = {
        "space": {"spaceType": "GROUP_CHAT", "displayName": "Eventship 3-day alerts"},
        "memberships": [{"member": {"name": m}} for m in CHAT_RECIPIENTS],
    }
    created = chat_service.spaces().setup(body=body).execute()
    space = created.get("name")
    if not space:
        raise SystemExit("Failed to create Chat space")
    CHAT_SPACE_FILE.write_text(space + "\n")
    return space


def build_message(events):
    lines = [
        "Heads up: these Eventship events are 3 days out.",
        "Please confirm ticket release time, venue, and speaker for each:",
        "",
    ]
    for e in events:
        venue = e.get("venue") or "(venue missing — confirm venue)"
        lines.append(f"• {e['date']} • {e['time']} — {e['title']}")
        lines.append("  - Ticket release time: (confirm)")
        lines.append(f"  - Venue: {venue}")
        lines.append("  - Speaker: (confirm)")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cal_creds = load_calendar_creds()
    chat_creds, can_create_space = load_chat_creds()
    cal = build("calendar", "v3", credentials=cal_creds, cache_discovery=False)
    chat = build("chat", "v1", credentials=chat_creds, cache_discovery=False)

    target_day, events = get_target_events(cal, days_out=3)
    if not events:
        print("NO_REPLY")
        return

    text = build_message(events)
    if args.dry_run:
        print(text)
        return

    space = ensure_chat_space(chat, can_create_space)
    chat.spaces().messages().create(parent=space, body={"text": text}).execute()
    print(f"SENT {len(events)} to {space}")


if __name__ == "__main__":
    main()
