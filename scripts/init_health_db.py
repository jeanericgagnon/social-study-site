#!/usr/bin/env python3
import sqlite3
from pathlib import Path

ROOT = Path('/Users/ericsysclaw/.openclaw/workspace')
DB_DIR = ROOT / 'knowledge' / 'advisory' / 'db'
DB_PATH = DB_DIR / 'health_advisory.db'
SCHEMA_PATH = DB_DIR / 'schema.sql'


def main():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()
    print(DB_PATH)


if __name__ == '__main__':
    main()
