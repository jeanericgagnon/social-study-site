#!/usr/bin/env python3
import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]

HERE = Path(__file__).resolve().parent
CLIENT_SECRET = HERE / "client_secret.json"
TOKEN_PATH = HERE / "token_eric_readonly.json"


def main():
    if not CLIENT_SECRET.exists():
        raise SystemExit(f"Missing {CLIENT_SECRET}")

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(host="localhost", port=0, open_browser=True)

    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }

    TOKEN_PATH.write_text(json.dumps(data, indent=2))
    print(f"Wrote token to {TOKEN_PATH}")


if __name__ == "__main__":
    main()
