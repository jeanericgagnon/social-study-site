#!/usr/bin/env python3
import argparse
import base64
import datetime as dt
import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError

SPEAKER_SHEET_IDS = {
    "denver": "1YSm5-vQpLO3UXbyGnD_GiKLHyW_aYllt4eygQvNsR7s",
    "san_diego": "1QwuvyafuH70TRiMTRsx1sWVq4BQcWjuWdwDzAX0fAg8",
    "orange_county": "17bWdWuWCm1ngX3A1MK5Dzccu3RMUxrtO2F4GX5h-YAk",
}
CITY_TO_COUNTY = {
    "mission valley": "San Diego County",
    "old town": "San Diego County",
    "normal heights": "San Diego County",
    "north park": "San Diego County",
    "miramar": "San Diego County",
    "santa ana": "Orange County",
    "huntington beach": "Orange County",
    "costa mesa": "Orange County",
    "anaheim": "Orange County",
    "placentia": "Orange County",
    "lodo": "Denver County",
    "downtown": "Denver County",
    "north park hill": "Denver County",
    "englewood": "Arapahoe County",
    "arvada": "Jefferson County",
}
DISCLAIMER = "Note: If the spreadsheet hasn’t been updated, speaker names and venues may be outdated."

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


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _parse_event_day(value: str):
    if not value:
        return None
    v = value.strip().replace("st", "").replace("nd", "").replace("rd", "").replace("th", "")
    for fmt in ("%B %d", "%b %d", "%B %d, %Y", "%b %d, %Y"):
        try:
            d = dt.datetime.strptime(v, fmt).date()
            if d.year == 1900:
                d = d.replace(year=dt.datetime.now(LA).year)
            return d
        except ValueError:
            continue
    return None


def _read_calendar_rows_from_xlsx_bytes(xlsx_bytes: bytes):
    z = zipfile.ZipFile(io.BytesIO(xlsx_bytes))
    sst = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        for si in root.findall("a:si", ns):
            sst.append("".join((t.text or "") for t in si.findall(".//a:t", ns)))

    wb = ET.fromstring(z.read("xl/workbook.xml"))
    ns = {
        "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    rid = None
    for s in wb.findall("a:sheets/a:sheet", ns):
        if s.attrib.get("name") == "Calendar":
            rid = s.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            break
    if not rid:
        return []

    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    nsr = {"a": "http://schemas.openxmlformats.org/package/2006/relationships"}
    id_to_target = {r.attrib["Id"]: r.attrib["Target"] for r in rels.findall("a:Relationship", nsr)}
    target = "xl/" + id_to_target[rid].lstrip("/")

    root = ET.fromstring(z.read(target))
    ns2 = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

    def col_to_idx(col: str) -> int:
        n = 0
        for c in col:
            n = n * 26 + ord(c) - 64
        return n - 1

    rows = []
    for row in root.findall(".//a:sheetData/a:row", ns2):
        vals = {}
        for c in row.findall("a:c", ns2):
            ref = c.attrib.get("r", "A1")
            m = re.match(r"([A-Z]+)", ref)
            idx = col_to_idx(m.group(1)) if m else 0
            t = c.attrib.get("t")
            v = c.find("a:v", ns2)
            val = ""
            if v is not None:
                raw = v.text or ""
                if t == "s" and raw.isdigit() and int(raw) < len(sst):
                    val = sst[int(raw)]
                else:
                    val = raw
            vals[idx] = val.strip()
        if vals:
            maxc = max(vals)
            rows.append([vals.get(i, "") for i in range(maxc + 1)])
    return rows


def get_speaker_lookup(drive_service):
    rows = []
    for _, fid in SPEAKER_SHEET_IDS.items():
        try:
            data = (
                drive_service.files()
                .export_media(
                    fileId=fid,
                    mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                .execute()
            )
            rows.extend(_read_calendar_rows_from_xlsx_bytes(data))
        except Exception:
            continue

    out = []
    for r in rows[1:]:
        pad = r + [""] * max(0, 10 - len(r))
        event_date = _parse_event_day(pad[2] if len(pad) > 2 else "")
        speaker = (pad[3] if len(pad) > 3 else "").strip()
        venue = (pad[5] if len(pad) > 5 and pad[5] else (pad[4] if len(pad) > 4 else "")).strip()
        title = (pad[9] if len(pad) > 9 and pad[9] else (pad[8] if len(pad) > 8 else "")).strip()
        if not event_date:
            continue
        city = (pad[8] if len(pad) > 8 and pad[8] else (pad[6] if len(pad) > 6 else "")).strip()
        out.append({
            "date": event_date,
            "speaker": speaker,
            "venue": venue,
            "city": city,
            "title": title,
            "title_n": _normalize(title),
            "venue_n": _normalize(venue),
        })
    return out


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
            raw_loc = (ev.get("location") or "").strip()
            loc_parts = [p.strip() for p in raw_loc.split(",") if p.strip()]
            events.append(
                {
                    "title": ev.get("summary", "(no title)"),
                    "date": str(target_day),
                    "time": local_time_label(raw),
                    "venue": raw_loc,
                    "city": loc_parts[1] if len(loc_parts) > 1 else "",
                    "link": ev.get("htmlLink") or "",
                    "speaker": "",
                }
            )

    events.sort(key=lambda x: (x["date"], x["time"], x["title"]))
    return target_day, events


def attach_speakers_from_sheet(events, speaker_rows):
    for e in events:
        t = _normalize(e.get("title", ""))
        v = _normalize((e.get("venue") or "").split(",", 1)[0])
        event_date = dt.date.fromisoformat(e["date"])
        match = None
        for row in speaker_rows:
            if row.get("date") != event_date:
                continue
            if row.get("title_n") and row["title_n"] == t:
                match = row
                break
            if row.get("venue_n") and row["venue_n"] and row["venue_n"] == v:
                match = row
        if match:
            if match.get("speaker"):
                e["speaker"] = _speaker_titlecase(match["speaker"])
            if match.get("venue"):
                e["venue"] = match["venue"]
            if match.get("city"):
                e["city"] = match["city"]


def _gmail_compose_url(subject: str, body: str) -> str:
    return (
        "https://mail.google.com/mail/?view=cm&fs=1"
        f"&su={quote(subject)}&body={quote(body)}"
    )


def _speaker_titlecase(name: str) -> str:
    return " ".join(w.capitalize() for w in (name or "").split())


def _infer_county(e: dict) -> str:
    city_area = (e.get("city") or "").strip().lower()
    if city_area in CITY_TO_COUNTY:
        return CITY_TO_COUNTY[city_area]
    venue = (e.get("venue") or "").lower()
    if "club 616" in venue or "novo" in venue or "societe" in venue:
        return "San Diego County" if "societe" in venue or "novo" in venue else "Orange County"
    if "station 26" in venue or "wynkoop" in venue:
        return "Denver County"
    return "County unknown"


def build_message(events):
    lines = [
        f"Heads up: The Social Study events are 3 days out ({len(events)} total).",
        "Remember to release returned tickets, confirm speaker, and confirm venue:",
        "",
    ]
    for e in events:
        raw_venue = (e.get("venue") or "").strip()
        venue = raw_venue.split(",", 1)[0].strip() if raw_venue else "(venue missing — confirm venue)"
        speaker_raw = (e.get("speaker") or "").strip()
        speaker = _speaker_titlecase(speaker_raw) if speaker_raw else "(speaker missing — confirm speaker)"
        county = _infer_county(e)

        venue_subject = f"Venue Check-In | {e['date']} | {venue}"
        venue_body = (
            f"Hi there,\n\nQuick check-in for The Social Study event on {e['date']} at {venue}. "
            "Can you confirm everything is set on your end?\n\nThanks!"
        )
        speaker_subject = f"Speaker Check-In | {e['date']} | {e['title']}"
        speaker_body = (
            f"Hi {speaker.split()[0] if speaker and '(' not in speaker else ''},\n\n"
            f"Quick check-in for your The Social Study talk on {e['date']} at {venue}. "
            "Looking forward to having you.\n\nThanks!"
        ).strip()

        lines.append(f"• {e['title']}")
        lines.append(f"  - Date/Time: {e['date']} • {e['time']}")
        lines.append(f"  - Speaker: {speaker}")
        lines.append(f"  - County: {county}")
        if e.get("link"):
            lines.append(f"  - Calendar link: {e['link']}")
        lines.append("  - Release returned tickets")
        lines.append("  - Confirm speaker")
        lines.append(f"  - Confirm venue: {venue}")
        lines.append(f"  - Venue draft link: {_gmail_compose_url(venue_subject, venue_body)}")
        lines.append(f"  - Speaker draft link: {_gmail_compose_url(speaker_subject, speaker_body)}")
        lines.append("")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def build_message_html(events):
    html = [
        f"<p><strong>Heads up: The Social Study events are 3 days out ({len(events)} total).</strong><br>"
        "Remember to release returned tickets, confirm speaker, and confirm venue:</p>",
        "<ul>",
    ]
    for e in events:
        raw_venue = (e.get("venue") or "").strip()
        venue = raw_venue.split(",", 1)[0].strip() if raw_venue else "(venue missing — confirm venue)"
        speaker_raw = (e.get("speaker") or "").strip()
        speaker = _speaker_titlecase(speaker_raw) if speaker_raw else "(speaker missing — confirm speaker)"
        county = _infer_county(e)
        title = e.get("title", "(no title)")
        link = e.get("link") or ""
        title_html = f'<a href="{link}">{title}</a>' if link else title
        venue_subject = f"Venue Check-In | {e['date']} | {venue}"
        venue_body = (
            f"Hi there,\n\nQuick check-in for The Social Study event on {e['date']} at {venue}. "
            "Can you confirm everything is set on your end?\n\nThanks!"
        )
        speaker_subject = f"Speaker Check-In | {e['date']} | {e['title']}"
        speaker_body = (
            f"Hi {speaker.split()[0] if speaker and '(' not in speaker else ''},\n\n"
            f"Quick check-in for your The Social Study talk on {e['date']} at {venue}. "
            "Looking forward to having you.\n\nThanks!"
        ).strip()
        html.append("<li>")
        html.append(f"<div><strong>{title_html}</strong></div>")
        html.append(f"<div>Date/Time: {e['date']} • {e['time']}</div>")
        html.append(f"<div>Speaker: {speaker}</div>")
        html.append(f"<div>County: {county}</div>")
        html.append("<div>Release returned tickets</div>")
        html.append("<div>Confirm speaker</div>")
        html.append(f"<div>Confirm venue: {venue}</div>")
        html.append(f"<div><a href=\"{_gmail_compose_url(venue_subject, venue_body)}\">Venue draft link</a></div>")
        html.append(f"<div><a href=\"{_gmail_compose_url(speaker_subject, speaker_body)}\">Speaker draft link</a></div>")
        html.append("</li>")
    html.append("</ul>")
    html.append(f"<p><em>{DISCLAIMER}</em></p>")
    return "\n".join(html)


def send_email(gmail_service, to_addr: str, subject: str, body_text: str, body_html: str):
    msg = MIMEMultipart("alternative")
    msg["to"] = to_addr
    msg["subject"] = subject
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))
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
    drive = build("drive", "v3", credentials=cal_creds, cache_discovery=False)
    gmail = build("gmail", "v1", credentials=send_creds, cache_discovery=False)

    target_day, events = get_target_events(cal, days_out=3)
    if not events:
        print("NO_REPLY")
        return

    try:
        speaker_rows = get_speaker_lookup(drive)
        attach_speakers_from_sheet(events, speaker_rows)
    except Exception:
        pass

    text = build_message(events)
    html = build_message_html(events)
    if args.dry_run:
        print(text)
        return

    subject = f"[3-day check] The Social Study events for {target_day.isoformat()}"
    recipients = [args.test_to] if args.test_to else RECIPIENTS
    for r in recipients:
        send_email(gmail, r, subject, text, html)
    print(f"SENT {len(events)} event(s) to {', '.join(recipients)}")


if __name__ == "__main__":
    main()
