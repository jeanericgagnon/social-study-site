#!/usr/bin/env python3
import re
import sqlite3
from pathlib import Path
from datetime import datetime

WORKSPACE = Path('/Users/ericsysclaw/.openclaw/workspace')
TXT = WORKSPACE / 'exports' / 'qb-mail' / 'finance-ledger-latest.txt'
DB = WORKSPACE / 'exports' / 'qb-mail' / 'finance.db'


def init_db(conn):
    conn.executescript(
        '''
        CREATE TABLE IF NOT EXISTS finance_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_date TEXT,
            tx_type TEXT,
            vendor TEXT,
            memo TEXT,
            category TEXT,
            amount REAL,
            balance REAL,
            source TEXT,
            loaded_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_finance_date ON finance_transactions(tx_date);
        CREATE INDEX IF NOT EXISTS idx_finance_vendor ON finance_transactions(vendor);
        CREATE INDEX IF NOT EXISTS idx_finance_category ON finance_transactions(category);
        '''
    )


def parse_line_tx(text: str):
    rows = []
    # crude line matcher from PDF text extraction; captures date, type, amount, balance
    pat = re.compile(
        r'(?m)^(\d{2}/\d{2}/\d{4})\s+([A-Za-z ]{3,25})\b.*?\s(-?\d{1,3}(?:,\d{3})*\.\d{2})\s+(-?\d{1,3}(?:,\d{3})*\.\d{2})\s*$'
    )
    for m in pat.finditer(text):
        tx_date, tx_type, amount, balance = m.groups()
        rows.append({
            'tx_date': datetime.strptime(tx_date, '%m/%d/%Y').date().isoformat(),
            'tx_type': tx_type.strip(),
            'vendor': '',
            'memo': '',
            'category': '',
            'amount': float(amount.replace(',', '')),
            'balance': float(balance.replace(',', '')),
        })

    # enrich category on nearby lines where possible
    lines = text.splitlines()
    for r in rows:
        ds = datetime.strptime(r['tx_date'], '%Y-%m-%d').strftime('%m/%d/%Y')
        for i, ln in enumerate(lines):
            if ds in ln and r['tx_type'] in ln:
                window = ' '.join(lines[i:i+5])
                # pick a known category phrase
                cm = re.search(r'(Sales|Contract labor|Credit Card - Chase Ink \(0580\)|CREDIT CARD \(6911\)|Event Expenses|Advertising and Marketing|Commissions & fees)', window)
                if cm:
                    r['category'] = cm.group(1)
                vm = re.search(r'(Eventship Payout|VENMO|Thank You - Web|Thank You-Mobile)', window)
                if vm:
                    r['vendor'] = vm.group(1)
                r['memo'] = window[:300]
                break
    return rows


def main():
    if not TXT.exists():
        raise SystemExit(f'Missing source text: {TXT}')

    txt = TXT.read_text(errors='ignore')
    txs = parse_line_tx(txt)

    conn = sqlite3.connect(DB)
    init_db(conn)

    # replace snapshot on each run
    conn.execute("DELETE FROM finance_transactions WHERE source='qb_financial_statements_pdf'")
    now = datetime.utcnow().isoformat() + 'Z'
    conn.executemany(
        '''
        INSERT INTO finance_transactions
        (tx_date, tx_type, vendor, memo, category, amount, balance, source, loaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        [(
            t['tx_date'], t['tx_type'], t['vendor'], t['memo'], t['category'],
            t['amount'], t['balance'], 'qb_financial_statements_pdf', now
        ) for t in txs]
    )
    conn.commit()

    c = conn.cursor()
    total = c.execute('SELECT COUNT(*) FROM finance_transactions').fetchone()[0]
    top = c.execute('''
        SELECT COALESCE(category,'(uncategorized)') cat, ROUND(SUM(ABS(amount)),2) spend
        FROM finance_transactions
        GROUP BY 1 ORDER BY 2 DESC LIMIT 8
    ''').fetchall()
    print(f'Loaded {len(txs)} transactions. DB total rows: {total}')
    print('Top categories by absolute amount:')
    for cat, spend in top:
        print(f'- {cat}: ${spend}')


if __name__ == '__main__':
    main()
