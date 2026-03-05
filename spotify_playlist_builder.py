#!/usr/bin/env python3
import json
import os
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
PLAYLIST_ID = os.getenv("SPOTIFY_PLAYLIST_ID", "5a4Sc4Fx3IzkFlaiX0nzrs")
MARKET = os.getenv("SPOTIFY_MARKET", "US")

APPROVED_ARTISTS = [
    "Brooks & Dunn", "Cody Johnson", "Lainey Wilson", "Ella Langley", "Riley Green",
    "Eli Young Band", "Charles Wesley Godwin", "Benjamin Tod", "Bayker Blankenship",
    "Braxton Keith", "Cameron Whitcomb", "Amos Lee", "Brett Young", "Chase Rice",
    "Brandon Wisham", "The Red Clay Strays", "Wyatt Flores", "Treaty Oak Revival",
    "Warren Zeiders", "Gavin Adcock", "Ty Myers", "Zach John King", "Larkin Poe",
    "Marcus King Band", "Josh Ross", "Hudson Westbrook", "Kameron Marlowe",
    "Little Big Town", "Jake Worthington",
]

SCOPES = "playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative"
TOKEN_PATH = os.path.expanduser("~/.openclaw/workspace/.spotify_token.json")


def api(method, path, token, params=None, body=None):
    url = "https://api.spotify.com/v1" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode()
        return json.loads(raw) if raw else {}


def token_exchange(code):
    payload = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }).encode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def token_refresh(refresh_token):
    payload = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }).encode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.loads(r.read().decode())
    j["refresh_token"] = j.get("refresh_token", refresh_token)
    return j


def authorize():
    if os.path.exists(TOKEN_PATH):
        tok = json.load(open(TOKEN_PATH))
        if "refresh_token" in tok:
            fresh = token_refresh(tok["refresh_token"])
            json.dump(fresh, open(TOKEN_PATH, "w"), indent=2)
            return fresh["access_token"]

    code_holder = {"code": None}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code_holder["code"] = (q.get("code") or [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Spotify auth complete. You can close this tab.")

        def log_message(self, *_):
            return

    host = urllib.parse.urlparse(REDIRECT_URI).hostname
    port = urllib.parse.urlparse(REDIRECT_URI).port
    server = HTTPServer((host, port), Handler)
    t = Thread(target=server.handle_request, daemon=True)
    t.start()

    auth_url = (
        "https://accounts.spotify.com/authorize?"
        + urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
        })
    )
    print("Open this URL and approve:\n", auth_url)
    while code_holder["code"] is None:
        time.sleep(0.25)

    tok = token_exchange(code_holder["code"])
    json.dump(tok, open(TOKEN_PATH, "w"), indent=2)
    return tok["access_token"]


def find_artist_id(token, artist_name):
    d = api("GET", "/search", token, params={"q": artist_name, "type": "artist", "limit": 5})
    items = d.get("artists", {}).get("items", [])
    if not items:
        return None, artist_name
    for a in items:
        if a["name"].lower() == artist_name.lower():
            return a["id"], a["name"]
    for a in items:
        if artist_name.lower() in a["name"].lower() or a["name"].lower() in artist_name.lower():
            return a["id"], a["name"]
    return items[0]["id"], items[0]["name"]


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        raise SystemExit("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET first.")

    token = authorize()

    existing_ids = set()
    offset = 0
    while True:
        page = api("GET", f"/playlists/{PLAYLIST_ID}/tracks", token, params={"limit": 100, "offset": offset, "market": MARKET})
        for it in page.get("items", []):
            t = it.get("track") or {}
            tid = t.get("id")
            if tid:
                existing_ids.add(tid)
        if not page.get("next"):
            break
        offset += 100

    add_uris = []
    report = {}

    for artist in APPROVED_ARTISTS:
        aid, canonical = find_artist_id(token, artist)
        if not aid:
            report[artist] = 0
            continue

        pool = []
        top = api("GET", f"/artists/{aid}/top-tracks", token, params={"market": MARKET}).get("tracks", [])
        pool.extend(top)

        if len(pool) < 10:
            q = api("GET", "/search", token, params={"q": f'artist:"{canonical}"', "type": "track", "limit": 50, "market": MARKET})
            pool.extend(q.get("tracks", {}).get("items", []))

        chosen = []
        seen = set()
        for tr in pool:
            tid = tr.get("id")
            if not tid or tid in seen or tid in existing_ids:
                continue
            seen.add(tid)
            names = [a["name"].lower() for a in tr.get("artists", [])]
            if artist.lower() not in names and canonical.lower() not in names:
                continue
            chosen.append(tid)
            if len(chosen) >= 7:  # middle of 5-10 per artist
                break

        report[artist] = len(chosen)
        for tid in chosen:
            existing_ids.add(tid)
            add_uris.append(f"spotify:track:{tid}")

    for i in range(0, len(add_uris), 100):
        api("POST", f"/playlists/{PLAYLIST_ID}/tracks", token, body={"uris": add_uris[i:i+100]})
        time.sleep(0.2)

    print("Added", len(add_uris), "tracks")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
